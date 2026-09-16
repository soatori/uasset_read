# Complete Static UAsset Parsing and Blueprint C++ Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current mixed parsing/enrichment path with a modular pure-Python parser that statically reconstructs package, Blueprint, Kismet, and Material semantics and projects Blueprint declarations and migration-oriented logic into C++.

**Architecture:** Keep one package-first `PackageDocument`, but introduce explicit Source/Container, Layout, Property, Object, Domain IR, Static Analysis, and Projection boundaries. Legacy and Zen are separate readers; Blueprint graph and Kismet bytecode converge only in a correlation/analysis layer; C++ is a projection and never a second parser.

**Tech Stack:** Python 3.10+, existing standard-library implementation, `pytest`, JSON golden fixtures, optional local Unreal source only for evidence. No CUE4Parse/UAssetAPI/UAssetGUI/UnrealBPInspect/FModel bridge and no Unreal Editor runtime dependency.

**Spec:** `docs/superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md`

## Global Constraints

- Pure Python 3.10+; no runtime bridge, subprocess bridge, FFI bridge, or dependency on the reference projects.
- `PackageDocument` remains the only package-level aggregate; every export remains addressable.
- Legacy and Zen packages use separate readers and converge on shared models.
- Tagged and unversioned properties use separate readers and converge on shared values.
- No runtime Blueprint execution; all control-flow and calls are static analysis.
- No fabricated data for cooked-away graphs, unknown serialization, encryption, missing chunks, or native C++ bodies.
- Every unknown region is decoded, opaque, payload-addressable, or unavailable with offset/size/reason.
- A breaking document schema is allowed; use `format_version: "3.0"` for the rebuilt output.
- Generated C++ has declaration and migration modes; migration output carries per-instruction translation status.
- Existing unrelated dirty files and `reference/` are not staged or modified.
- New probes and generated files belong under `temp/` unless they are committed fixtures or tests.

## File Map

The implementation should converge on these focused modules instead of adding more responsibilities to `package.py` or `handlers_impl.py`:

- `src/uasset_read/sources.py`: bounded random-access source protocol and file/memory/composite implementations.
- `src/uasset_read/containers.py`: Pak and IoStore/Zen source discovery, chunk lookup, decompression status, and container diagnostics.
- `src/uasset_read/layout.py`: validated Legacy/Zen layout selection and shared layout metadata.
- `src/uasset_read/models/byte_ranges.py`: source ranges, opaque regions, payload references, and byte accounting.
- `src/uasset_read/models/analysis.py`: normalized Blueprint/Kismet/Material IR and capability statuses.
- `src/uasset_read/parsers/legacy_reader.py`: Legacy table/object orchestration only.
- `src/uasset_read/parsers/zen_reader.py`: Zen table/object orchestration only.
- `src/uasset_read/parsers/properties/tagged.py`: Tagged property state machine.
- `src/uasset_read/parsers/properties/unversioned.py`: Unversioned property state machine.
- `src/uasset_read/parsers/properties/schema.py`: Mapping/schema provider.
- `src/uasset_read/parsers/properties/opaque.py`: Native tails and opaque-region preservation.
- `src/uasset_read/parsers/asset_types/registry.py`: Handler registration and dispatch.
- `src/uasset_read/parsers/blueprint/graph.py`: Blueprint graph decoder.
- `src/uasset_read/parsers/blueprint/bytecode.py`: Kismet instruction normalization.
- `src/uasset_read/parsers/blueprint/control_flow.py`: Basic blocks and CFG construction.
- `src/uasset_read/parsers/blueprint/correlation.py`: Graph/bytecode/source-node correlation.
- `src/uasset_read/parsers/blueprint/cpp_ast.py`: C++ projection AST.
- `src/uasset_read/parsers/blueprint/cpp_render.py`: Header/source rendering.
- `src/uasset_read/parsers/material/graph.py`: Material expression graph decoder.
- `src/uasset_read/projection.py`: JSON/CLI/Agent projection from `PackageDocument`.
- `src/uasset_read/package.py`: thin public entrypoint and cache key construction.
- `tests/fixtures.py`: named sample paths, parser helpers, and reusable pytest fixtures used by the task tests.
- `tests/test_sources.py`, `tests/test_containers.py`, `tests/test_layout.py`: binary input boundaries.
- `tests/test_properties.py`: tagged/unversioned/opaque property contracts.
- `tests/test_blueprint_ir.py`, `tests/test_blueprint_cfg.py`, `tests/test_blueprint_cpp.py`: Blueprint static analysis and C++ output.
- `tests/test_material_graph.py`: Material expression graph contracts.
- `tests/test_complete_samples.py`: sample acceptance and byte-accounting gates.

The following test helpers are introduced in Task 1 and are the only shared test vocabulary used below:

```python
def sample_path(name: str) -> Path: ...
def parse_sample(name: str, *, depth: str = "decode") -> PackageDocument: ...
def find_function(document: PackageDocument, name: str) -> FunctionAnalysis: ...
def find_blueprint_object(document: PackageDocument) -> ObjectRecord: ...
def find_material_graph(document: PackageDocument) -> MaterialGraph: ...
```

`tests/fixtures.py` also defines the named pytest fixtures used by the focused tests: `tagged_fixture`, `unversioned_fixture`, `fake_source`, `object_record`, `package_context`, `package_document`, `graph_fixture`, `ue58_blueprint_document`, `function_analysis`, `stackobot_document`, `stackobot_material`, `cooked_material`, `stackobot_semantic`, `ue58_semantic`, and `document`. Each fixture is built from a real sample or a bounded synthetic byte window and returns the model named by the test that consumes it.

---

### Task 1: Freeze the new contract and repair the baseline gates

**Files:**
- Modify: `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`
- Modify: `docs/designs/README.md`
- Modify: `tests/size-baseline.json`
- Modify: `tests/test_core.py`
- Create: `tests/test_contract_v3.py`
- Create: `tests/fixtures.py`
- Test: `tests/test_contract_v3.py`, `tests/test_core.py`, `tests/test_size_baseline.py`

**Interfaces:**
- Consumes: existing `parse_package_document()` and current `PackageDocument` fields.
- Produces: `format_version == "3.0"`, explicit capability statuses, and a documented migration target for later tasks.
- Test helpers: `sample_path`, `parse_sample`, `find_function`, `find_blueprint_object`, and `find_material_graph` with the signatures defined in the File Map.

- [ ] **Step 1: Write the failing contract tests**

```python
def test_rebuilt_document_declares_v3_and_package_first():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="package")
    assert document.format_version == "3.0"
    assert document.objects
    assert all(obj.id.startswith(("export:", "import:")) for obj in document.objects)


def test_incomplete_regions_have_reasoned_statuses():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    for region in document.byte_accounting.regions:
        assert region.status in {"decoded", "opaque", "payload", "unavailable"}
        assert region.reason is not None or region.status == "decoded"
```

- [ ] **Step 2: Run the focused tests and verify the expected failures**

Run: `PYTHONPATH=src python -m pytest tests/test_contract_v3.py tests/test_core.py::test_test_suite_structure_gate tests/test_size_baseline.py -q`

Expected: the new format/status assertions fail, and the existing baseline failures identify the exact expected-file and count drift.

- [ ] **Step 3: Update the canonical design and quality baseline**

Record in the canonical design that the approved target is pure Python, has no compatibility requirement, uses schema v3, and includes Blueprint C++ declaration/migration projections. Update the structure and size baselines only to the measured values after the test tree is correct.

- [ ] **Step 4: Implement `tests/fixtures.py` and the smallest contract projection**

Implement the five helper signatures from the File Map using `tests/samples` and `parse_package_document()`. Then change only the document metadata/status model needed for the tests; do not add parser behavior in this task.

- [ ] **Step 5: Run the gate and commit**

Run: `PYTHONPATH=src python -m pytest tests/test_contract_v3.py tests/test_core.py tests/test_size_baseline.py -q`

Commit: `git add docs/designs/2026-08-26-package-first-uasset-parser-refactor.md docs/designs/README.md tests/size-baseline.json tests/test_core.py tests/test_contract_v3.py; git commit -m "docs: define complete parser v3 contract"`

### Task 2: Introduce bounded sources and package container inputs

**Files:**
- Create: `src/uasset_read/sources.py`
- Create: `src/uasset_read/containers.py`
- Modify: `src/uasset_read/iostore.py`
- Modify: `src/uasset_read/package.py`
- Create: `tests/test_sources.py`
- Create: `tests/test_containers.py`

**Interfaces:**
- Consumes: existing `FArchive`, `PackageBundle`, `open_package_bundle()`.
- Produces: `ByteSource`, `FileSource`, `MemorySource`, `CompositeSource`, `PakEntrySource`, `IoStoreChunkSource`, and `open_source(path_or_container)`.

- [ ] **Step 1: Add failing source boundary tests**

```python
def test_composite_source_maps_sidecar_ranges(tmp_path):
    main = tmp_path / "A.uasset"
    sidecar = tmp_path / "A.uexp"
    main.write_bytes(b"HEAD")
    sidecar.write_bytes(b"PAYLOAD")
    source = CompositeSource.from_package(main)
    assert source.read_at(0, 4) == b"HEAD"
    assert source.read_at(4, 7) == b"PAYLOAD"


def test_source_rejects_out_of_bounds_reads():
    source = MemorySource(b"abc")
    with pytest.raises(ParseError):
        source.read_at(2, 2)
```

- [ ] **Step 2: Run the tests and confirm missing interfaces fail**

Run: `PYTHONPATH=src python -m pytest tests/test_sources.py -q`

Expected: import or attribute failures for the new source classes.

- [ ] **Step 3: Implement the source protocol with explicit ranges**

Use `read_at(offset, size)` with non-negative integer validation, exact-size reads, source descriptions, and no unbounded reads. `CompositeSource` must expose a mapping from virtual package offsets to physical files.

- [ ] **Step 4: Add container fixtures and diagnostics**

Use `tests/samples/containers/MyProject-Windows.pak`, `MyProject-Windows.utoc`, and the available `global.ucas` metadata. Return `unavailable` with a reason for absent `.ucas`, encryption keys, or unknown compression instead of falling back to a false Legacy parse.

- [ ] **Step 5: Run source/container tests and commit**

Run: `PYTHONPATH=src python -m pytest tests/test_sources.py tests/test_containers.py -q`

Commit: `git add src/uasset_read/sources.py src/uasset_read/containers.py src/uasset_read/iostore.py src/uasset_read/package.py tests/test_sources.py tests/test_containers.py; git commit -m "feat: add bounded package sources and containers"`

### Task 3: Split Legacy and Zen layout readers

**Files:**
- Create: `src/uasset_read/layout.py`
- Modify: `src/uasset_read/parsers/legacy_reader.py`
- Create: `src/uasset_read/parsers/zen_reader.py`
- Modify: `src/uasset_read/package.py`
- Create: `tests/test_layout.py`
- Create: `tests/test_zen_reader.py`

**Interfaces:**
- Consumes: `ByteSource`, `VersionContext`, existing package summary/table readers.
- Produces: `PackageLayoutDetector.detect(source) -> PackageLayout` and reader methods `read_package(source, *, depth, object_ids) -> PackageDocument`.

- [ ] **Step 1: Define layout and reader protocol tests**

```python
def test_loose_sample_selects_legacy_reader(sample_path):
    source = CompositeSource.from_package(sample_path)
    layout = PackageLayoutDetector().detect(source)
    assert layout.kind == "legacy"


def test_reader_selection_does_not_use_ue_major_version_only(fake_source):
    layout = PackageLayoutDetector().detect(fake_source)
    assert layout.detection_reason in {"validated_legacy", "validated_zen", "unknown"}
```

- [ ] **Step 2: Run tests to confirm the protocol is absent**

Run: `PYTHONPATH=src python -m pytest tests/test_layout.py tests/test_zen_reader.py -q`

Expected: missing class/protocol failures.

- [ ] **Step 3: Implement validated Legacy detection and orchestration**

Move only table/object orchestration into `LegacyPackageReader`; all reads must consume `ByteSource` windows and return `PackageLayout` metadata. Preserve `.uasset/.uexp/.ubulk/.uptnl` physical mapping.

- [ ] **Step 4: Implement Zen reader boundaries**

Parse only fields supported by validated source evidence. Keep Zen-specific offsets and chunk references inside `zen_reader.py`; return structured `unavailable` records for missing chunk bytes or keys.

- [ ] **Step 5: Run both reader tests and commit**

Run: `PYTHONPATH=src python -m pytest tests/test_layout.py tests/test_zen_reader.py tests/test_core.py -q`

Commit: `git add src/uasset_read/layout.py src/uasset_read/parsers/legacy_reader.py src/uasset_read/parsers/zen_reader.py src/uasset_read/package.py tests/test_layout.py tests/test_zen_reader.py; git commit -m "refactor: separate legacy and zen package readers"`

### Task 4: Modularize property decoding and byte accounting

**Files:**
- Create: `src/uasset_read/parsers/properties/__init__.py`
- Create: `src/uasset_read/parsers/properties/tagged.py`
- Create: `src/uasset_read/parsers/properties/unversioned.py`
- Create: `src/uasset_read/parsers/properties/schema.py`
- Create: `src/uasset_read/parsers/properties/opaque.py`
- Modify: `src/uasset_read/parsers/property_parser.py`
- Modify: `src/uasset_read/models/properties.py`
- Create: `src/uasset_read/models/byte_ranges.py`
- Create: `tests/test_properties.py`

**Interfaces:**
- Consumes: bounded object slices, `VersionContext`, mappings, and existing normalized property values.
- Produces: `PropertyReadResult(values, consumed, regions, diagnostics, status)` and `OpaqueRegion(start, size, reason, payload_ref)`.

- [ ] **Step 1: Write strict tagged/unversioned tests**

```python
def test_tagged_reader_reports_consumed_boundary(tagged_fixture):
    result = TaggedPropertyReader().read(tagged_fixture)
    assert result.consumed >= 0
    assert result.regions[-1].end == tagged_fixture.start + result.consumed


def test_unversioned_reader_does_not_guess_without_schema(unversioned_fixture):
    result = UnversionedPropertyReader(schema=None).read(unversioned_fixture)
    assert result.status in {"opaque", "unavailable"}
    assert result.diagnostics[0].reason == "schema_required"
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `PYTHONPATH=src python -m pytest tests/test_properties.py tests/test_unversioned_fixtures.py -q`

Expected: missing reader/result classes or incorrect schema behavior.

- [ ] **Step 3: Move tagged parsing into a bounded state machine**

Keep type-specific value parsing separate from property-tag iteration. Every tag records its serialized range and either decoded value or opaque payload reference.

- [ ] **Step 4: Implement schema-backed unversioned parsing**

Make schema lookup explicit. If a field cannot be mapped, stop at the safe boundary and record the remaining range as opaque; never infer field width from the following bytes.

- [ ] **Step 5: Run property and hardening tests and commit**

Run: `PYTHONPATH=src python -m pytest tests/test_properties.py tests/test_unversioned_fixtures.py tests/test_parse_hardening.py tests/test_memory_safety.py -q`

Commit: `git add src/uasset_read/parsers/properties src/uasset_read/parsers/property_parser.py src/uasset_read/models/properties.py src/uasset_read/models/byte_ranges.py tests/test_properties.py; git commit -m "refactor: separate property readers and byte accounting"`

### Task 5: Replace the monolithic handler path with a registry and domain contracts

**Files:**
- Create: `src/uasset_read/parsers/asset_types/registry.py`
- Modify: `src/uasset_read/parsers/asset_types/handlers_impl.py`
- Modify: `src/uasset_read/models/object_model.py`
- Modify: `src/uasset_read/models/document.py`
- Create: `tests/test_handler_registry.py`

**Interfaces:**
- Consumes: `ObjectRecord`, normalized properties, package context, and domain decoder results.
- Produces: `AssetDecoder.decode(obj, context) -> DomainResult` and registry lookup by exact UE class name/family.
- Aggregate API: `AssetDecoderRegistry.decode_package(document: PackageDocument) -> PackageDocument`.

- [ ] **Step 1: Write registry and failure isolation tests**

```python
def test_unknown_handler_is_explicitly_unavailable(object_record, package_context):
    result = AssetDecoderRegistry().decode(object_record, package_context)
    assert result.status == "unavailable"
    assert result.reason == "no_domain_decoder"


def test_one_domain_decoder_failure_does_not_hide_other_objects(package_document):
    result = AssetDecoderRegistry().decode_package(package_document)
    assert len(result.objects) == len(package_document.objects)
```

- [ ] **Step 2: Run the tests and verify the current monolith does not satisfy them**

Run: `PYTHONPATH=src python -m pytest tests/test_handler_registry.py -q`

Expected: missing registry/result boundaries.

- [ ] **Step 3: Define `DomainResult` and registry dispatch**

Define `DomainResult(status, semantic, coverage, diagnostics)` and `AssetDecoderRegistry.decode(obj, context) -> DomainResult`. The registry must return structured status and diagnostics without broad exception swallowing. A decoder may enrich one object but may not replace the package envelope.

- [ ] **Step 4: Move existing summary handlers behind the registry**

Preserve currently supported summary behavior while moving Blueprint and Material decoding into their dedicated modules in later tasks.

- [ ] **Step 5: Run handler and core tests and commit**

Run: `PYTHONPATH=src python -m pytest tests/test_handler_registry.py tests/test_handler_capability_ledger.py tests/test_capability_hardening.py tests/test_core.py -q`

Commit: `git add src/uasset_read/parsers/asset_types/registry.py src/uasset_read/parsers/asset_types/handlers_impl.py src/uasset_read/models/object_model.py src/uasset_read/models/document.py tests/test_handler_registry.py; git commit -m "refactor: isolate asset decoder registry"`

### Task 6: Build the Blueprint graph IR

**Files:**
- Create: `src/uasset_read/parsers/blueprint/__init__.py`
- Create: `src/uasset_read/parsers/blueprint/graph.py`
- Modify: `src/uasset_read/serializers/blueprint_graph.py`
- Modify: `src/uasset_read/serializers/graph_node.py`
- Modify: `src/uasset_read/serializers/graph_pin.py`
- Modify: `src/uasset_read/models/analysis.py`
- Create: `tests/test_blueprint_ir.py`

**Interfaces:**
- Consumes: object slices and current graph/node/pin serializers.
- Produces: `BlueprintGraphDecoder.decode(obj, context) -> list[BlueprintGraph]`, with owner-aware `NodeId`, `PinId`, and `Link` objects.

- [ ] **Step 1: Add graph identity and duplicate-GUID tests**

```python
def test_graph_identity_includes_owner_for_duplicate_guids(graph_fixture):
    graphs = BlueprintGraphDecoder().decode(graph_fixture.obj, graph_fixture.context)
    ids = [node.id for graph in graphs for node in graph.nodes]
    assert len(ids) == len(set(ids))


def test_unresolved_pin_owner_is_diagnostic(graph_fixture):
    result = BlueprintGraphDecoder().decode_with_diagnostics(graph_fixture.obj, graph_fixture.context)
    assert any(d.reason == "pin_owner_unresolved" for d in result.diagnostics)
```

- [ ] **Step 2: Run graph tests and verify the new IR is absent**

Run: `PYTHONPATH=src python -m pytest tests/test_blueprint_ir.py tests/test_blueprint_graph.py -q`

Expected: missing IR classes or identity assertions fail.

- [ ] **Step 3: Define graph dataclasses and stable IDs**

Use package/object/export identity first and Node GUID as an attribute, not the sole key. Preserve node/pin raw ranges and unknown node properties.

- [ ] **Step 4: Adapt current serializers to populate the IR**

Keep the current bounded caps as explicit truncation diagnostics. Link resolution must retain both original reference and resolved owner-aware identity.

- [ ] **Step 5: Run Blueprint graph regressions and commit**

Run: `PYTHONPATH=src python -m pytest tests/test_blueprint_ir.py tests/test_blueprint_graph.py tests/test_review_pins.py -q`

Commit: `git add src/uasset_read/parsers/blueprint src/uasset_read/serializers/blueprint_graph.py src/uasset_read/serializers/graph_node.py src/uasset_read/serializers/graph_pin.py src/uasset_read/models/analysis.py tests/test_blueprint_ir.py; git commit -m "feat: add owner-aware blueprint graph IR"`

### Task 7: Normalize Kismet bytecode into instructions and CFG

**Files:**
- Create: `src/uasset_read/parsers/blueprint/bytecode.py`
- Create: `src/uasset_read/parsers/blueprint/control_flow.py`
- Modify: `src/uasset_read/kismet/bytecode_extractor.py`
- Modify: `src/uasset_read/kismet/expressions.py`
- Modify: `src/uasset_read/kismet/decompile_bridge.py`
- Create: `tests/test_blueprint_cfg.py`

**Interfaces:**
- Consumes: `FunctionScriptReadResult` and existing Kismet expression records.
- Produces: `BytecodeInstruction`, `BasicBlock`, `ControlFlowGraph`, `FunctionAnalysis`.

- [ ] **Step 1: Write instruction and branch tests**

```python
def test_jump_if_not_creates_true_and_false_edges(ue58_blueprint_document):
    function = find_function(ue58_blueprint_document, "NewFunction")
    assert "EX_JumpIfNot" in [item.opcode for item in function.instructions]
    assert {edge.kind for edge in function.cfg.edges} >= {"true", "false"}


def test_instruction_ranges_are_monotonic(function_analysis):
    offsets = [item.offset for item in function_analysis.instructions]
    assert offsets == sorted(offsets)
    assert all(item.end_offset > item.offset for item in function_analysis.instructions)
```

- [ ] **Step 2: Run the tests and verify CFG behavior is missing**

Run: `PYTHONPATH=src python -m pytest tests/test_blueprint_cfg.py tests/test_blueprint_decode.py -q`

Expected: instruction/CFG assertions fail because current output stops at expressions/direct exec summaries.

- [ ] **Step 3: Normalize expression records into instruction records**

Retain opcode, logical offset, consumed bytes, operands, expression, jump targets, call references, and variable references. If byte consumption is uncertain, mark the instruction and remaining stream partial.

- [ ] **Step 4: Build basic blocks and typed edges**

Split at entry, jump targets, conditional fallthrough, and returns. Emit `computed_jump` where targets cannot be statically enumerated. Derive `exec_chains` only after CFG construction.

- [ ] **Step 5: Run the complete Blueprint/Kismet tests and commit**

Run: `PYTHONPATH=src python -m pytest tests/test_blueprint_cfg.py tests/test_blueprint_decode.py tests/test_parse_hardening.py -q`

Commit: `git add src/uasset_read/parsers/blueprint/bytecode.py src/uasset_read/parsers/blueprint/control_flow.py src/uasset_read/kismet/bytecode_extractor.py src/uasset_read/kismet/expressions.py src/uasset_read/kismet/decompile_bridge.py tests/test_blueprint_cfg.py; git commit -m "feat: normalize kismet instructions and control flow"`

### Task 8: Correlate graph nodes, bytecode, calls, and variables

**Files:**
- Create: `src/uasset_read/parsers/blueprint/correlation.py`
- Modify: `src/uasset_read/parsers/asset_types/handlers_impl.py`
- Modify: `src/uasset_read/models/analysis.py`
- Create: `tests/test_blueprint_correlation.py`

**Interfaces:**
- Consumes: `BlueprintGraph`, `FunctionAnalysis`, object table, imports, and properties.
- Produces: `BlueprintSemantic(entrypoints, graphs, functions, calls, variables, components, diagnostics)`.
- API: `BlueprintCorrelation.build(document: PackageDocument) -> BlueprintSemantic`.

- [ ] **Step 1: Write static semantic tests**

```python
def test_stackobot_has_event_entrypoint_and_function_calls(stackobot_document):
    semantic = BlueprintCorrelation().build(stackobot_document)
    assert semantic.entrypoints
    assert semantic.calls
    assert semantic.variables
    assert all(call.execution_mode == "static_reference" for call in semantic.calls)


def test_exec_summary_is_not_runtime_execution(stackobot_document):
    semantic = BlueprintCorrelation().build(stackobot_document)
    assert semantic.exec_chains.metadata["kind"] == "direct_exec_edge_summary"
    assert semantic.control_flow
```

- [ ] **Step 2: Run tests and confirm current output lacks the new contract**

Run: `PYTHONPATH=src python -m pytest tests/test_blueprint_correlation.py tests/test_blueprint_decode.py -q`

Expected: missing call/variable/entrypoint correlation fields or incorrect execution metadata.

- [ ] **Step 3: Implement multi-level correlation**

Match by Export/Object ID, function identity, source-node metadata, and then GUID. Store every match method and confidence. Preserve unresolved references as records.

- [ ] **Step 4: Add Blueprint semantic output under each object**

Do not promote domain content to the document root. Keep all functions, graphs, calls, and variable sets under the corresponding Blueprint/GeneratedClass object.

- [ ] **Step 5: Run sample correlation tests and commit**

Run: `PYTHONPATH=src python -m pytest tests/test_blueprint_correlation.py tests/test_blueprint_graph.py tests/test_blueprint_decode.py -q`

Commit: `git add src/uasset_read/parsers/blueprint/correlation.py src/uasset_read/parsers/asset_types/handlers_impl.py src/uasset_read/models/analysis.py tests/test_blueprint_correlation.py; git commit -m "feat: correlate blueprint graphs and bytecode"`

### Task 9: Decode Material expression graphs

**Files:**
- Create: `src/uasset_read/parsers/material/__init__.py`
- Create: `src/uasset_read/parsers/material/graph.py`
- Modify: `src/uasset_read/parsers/asset_types/handlers_impl.py`
- Create: `tests/test_material_graph.py`

**Interfaces:**
- Consumes: Material/MaterialExpression exports, normalized properties, object references, and graph pins.
- Produces: `MaterialGraph(expressions, links, parameters, function_calls, capability)`.
- API: `MaterialGraphDecoder.decode(document: PackageDocument) -> MaterialGraph`.

- [ ] **Step 1: Write StackOBot and cooked-material tests**

```python
def test_stackobot_material_exposes_expression_nodes_and_links(stackobot_material):
    graph = MaterialGraphDecoder().decode(stackobot_material)
    assert len(graph.expressions) == 39
    assert graph.links
    assert graph.parameters


def test_cooked_material_marks_editor_graph_unavailable(cooked_material):
    graph = MaterialGraphDecoder().decode(cooked_material)
    assert graph.capability in {"limited", "unavailable"}
    assert any(item.feature == "editor_expression_graph" for item in graph.coverage)
```

- [ ] **Step 2: Run focused tests and confirm current Material summary is insufficient**

Run: `PYTHONPATH=src python -m pytest tests/test_material_graph.py tests/test_samples.py -q`

Expected: expression/link assertions fail against the current Material summary.

- [ ] **Step 3: Implement expression and pin extraction**

Resolve expression exports by object identity, copy scalar/vector/texture/function-call properties, and preserve unknown expression fields as opaque regions.

- [ ] **Step 4: Implement link reconstruction and capability reporting**

Use input/output pin references where serialized; report missing editor data explicitly for cooked assets.

- [ ] **Step 5: Run Material tests and commit**

Run: `PYTHONPATH=src python -m pytest tests/test_material_graph.py tests/test_capability_hardening.py -q`

Commit: `git add src/uasset_read/parsers/material src/uasset_read/parsers/asset_types/handlers_impl.py tests/test_material_graph.py; git commit -m "feat: decode material expression graphs"`

### Task 10: Build the Blueprint C++ declaration and migration projection

**Files:**
- Create: `src/uasset_read/parsers/blueprint/cpp_ast.py`
- Create: `src/uasset_read/parsers/blueprint/cpp_render.py`
- Modify: `src/uasset_read/models/analysis.py`
- Create: `tests/test_blueprint_cpp.py`

**Interfaces:**
- Consumes: `BlueprintSemantic` and `PackageDocument` object/import/type information.
- Produces: `CppProjection(header_text, source_text, diagnostics, translation_stats)` and `render_cpp(semantic, mode) -> CppProjection` where `mode` is `declaration` or `migration`.

- [ ] **Step 1: Write C++ projection tests**

```python
def test_declaration_mode_contains_blueprint_header_elements(stackobot_semantic):
    result = render_cpp(stackobot_semantic, mode="declaration")
    assert "UCLASS" in result.header_text
    assert "UPROPERTY" in result.header_text
    assert "UFUNCTION" in result.header_text
    assert result.translation_stats["declarations"] > 0


def test_migration_mode_reports_each_untranslated_instruction(ue58_semantic):
    result = render_cpp(ue58_semantic, mode="migration")
    assert result.source_text
    assert result.translation_stats["instructions_seen"] > 0
    assert result.translation_stats["instructions_seen"] == (
        result.translation_stats["translated"]
        + result.translation_stats["represented"]
        + result.translation_stats["untranslated"]
        + result.translation_stats["unavailable"]
    )
```

- [ ] **Step 2: Run the tests and verify the projection is absent**

Run: `PYTHONPATH=src python -m pytest tests/test_blueprint_cpp.py -q`

Expected: missing renderer or projection fields.

- [ ] **Step 3: Implement the C++ AST**

Represent declarations, types, literals, assignments, calls, branches, loops, returns, diagnostic statements, and includes as typed nodes. Do not concatenate arbitrary bytecode strings directly into C++.

- [ ] **Step 4: Implement declaration rendering based on Blueprint Header View scope**

Render parent class, variables, functions, Actor Components, Event Dispatchers, access specifiers, and recoverable metadata. Unresolved types remain diagnostic-bearing names and are never silently replaced with `void` or an unrelated type.

- [ ] **Step 5: Implement migration rendering and output accounting**

Map known instructions to C++ AST constructs. Render unresolved operations through a self-contained diagnostic helper statement so the output remains auditable and syntactically structured. Record the originating instruction offset and node/object ID in comments and sidecar diagnostics.

- [ ] **Step 6: Run C++ projection tests and commit**

Run: `PYTHONPATH=src python -m pytest tests/test_blueprint_cpp.py tests/test_blueprint_cfg.py tests/test_blueprint_correlation.py -q`

Commit: `git add src/uasset_read/parsers/blueprint/cpp_ast.py src/uasset_read/parsers/blueprint/cpp_render.py src/uasset_read/models/analysis.py tests/test_blueprint_cpp.py; git commit -m "feat: project blueprint semantics to cpp"`

### Task 11: Replace output and CLI plumbing with projections

**Files:**
- Modify: `src/uasset_read/projection.py`
- Modify: `src/uasset_read/cli.py`
- Modify: `src/uasset_read/agent_tools.py`
- Modify: `src/uasset_read/package.py`
- Modify: `src/uasset_read/__init__.py`
- Create: `tests/test_projection_v3.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: one fully populated `PackageDocument` plus selection/depth/size options.
- Produces: JSON, JSONL, bounded Agent responses, and C++ files from projection functions only.
- APIs: `project_document(document, *, view) -> dict` and `project_cpp(document, *, object_id, mode) -> CppProjection`.

- [ ] **Step 1: Write projection consistency tests**

```python
def test_json_and_cpp_use_the_same_document():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    json_view = project_document(document, view="semantic")
    cpp_view = project_cpp(document, object_id=find_blueprint_object(document).id, mode="declaration")
    assert json_view["package_id"] == cpp_view.package_id


def test_large_payloads_are_not_embedded_by_default(document):
    output = project_document(document, view="semantic")
    assert output.get("payloads", []) == []
```

- [ ] **Step 2: Run output tests and verify old plumbing fails the v3 assertions**

Run: `PYTHONPATH=src python -m pytest tests/test_projection_v3.py tests/test_cli.py tests/test_payload_extraction.py -q`

Expected: format version, projection, or C++ command assertions fail before migration.

- [ ] **Step 3: Make `package.py` a thin orchestration entrypoint**

Route source detection, reader selection, object decoding, domain analysis, and projection through named modules. Keep cache keys sensitive to all source/container/mapping stats.

- [ ] **Step 4: Add CLI commands for static analysis and C++ projection**

Use explicit commands/options equivalent to `--depth decode`, `--view semantic`, `--cpp declaration`, and `--cpp migration`; return nonzero only for fatal package failures and include structured diagnostics in output.

- [ ] **Step 5: Update Agent tools to project the same document**

Preserve the six existing tool purposes while changing their implementation to call the v3 projection layer. Enforce pagination, selection, and `max_bytes` after semantic projection.

- [ ] **Step 6: Run CLI/Agent/projection tests and commit**

Run: `PYTHONPATH=src python -m pytest tests/test_projection_v3.py tests/test_cli.py tests/test_payload_extraction.py tests/test_core.py -q`

Commit: `git add src/uasset_read/projection.py src/uasset_read/cli.py src/uasset_read/agent_tools.py src/uasset_read/package.py src/uasset_read/__init__.py tests/test_projection_v3.py tests/test_cli.py; git commit -m "refactor: route outputs through package document projections"`

### Task 12: Add sample quality gates and complete verification

**Files:**
- Create: `tests/test_complete_samples.py`
- Modify: `tests/samples/quality_baseline.json`
- Modify: `tests/samples/manifest.json`
- Create: `temp/quality-v3/README.md`
- Modify: `tests/test_quality_baseline_generator.py`
- Modify: `tests/test_size_baseline.py`

**Interfaces:**
- Consumes: complete parser output, sample manifest, reference reports as corroborating evidence only.
- Produces: repeatable acceptance checks for byte accounting, domain coverage, C++ projection coverage, and failure truthfulness.

- [ ] **Step 1: Write sample acceptance tests**

```python
def test_stackobot_blueprint_acceptance():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    assert len(document.objects) == 31
    assert count_kismet_expressions(document) == 85
    assert blueprint_functions(document)
    assert blueprint_control_flow(document)


def test_every_region_has_an_accounting_state(document):
    for region in document.byte_accounting.regions:
        assert region.status in {"decoded", "opaque", "payload", "unavailable"}
        assert region.size >= 0
```

- [ ] **Step 2: Run the sample tests and record real failures**

Run: `PYTHONPATH=src python -m pytest tests/test_complete_samples.py -q`

Expected: failures identify remaining parser gaps by sample and feature, not generic assertion noise.

- [ ] **Step 3: Generate quality-v3 evidence under `temp/`**

Run the parser for StackOBot Blueprint, UE5.8 Blueprint, StackOBot Material, unversioned samples, sidecars, and available container fixtures. Store JSON, diagnostics, C++ declaration/migration output, and a feature matrix under `temp/quality-v3/`.

- [ ] **Step 4: Update only measured baselines**

Update quality and size baselines from the generated evidence. Do not suppress a parser failure by widening a baseline or marking an unavailable feature complete.

- [ ] **Step 5: Run all verification commands**

Run:

```text
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m pytest tests/test_complete_samples.py tests/test_quality_baseline_generator.py tests/test_size_baseline.py -q
python -m compileall -q src
```

Expected: all tests pass, all baseline gates pass, and generated C++ projections contain a translation status for every discovered instruction.

- [ ] **Step 6: Commit the acceptance gate and close the plan**

Commit: `git add tests/test_complete_samples.py tests/samples/quality_baseline.json tests/samples/manifest.json tests/test_quality_baseline_generator.py tests/test_size_baseline.py temp/quality-v3/README.md; git commit -m "test: add complete parser quality gates"`

## Final Review Checklist

- [ ] `PackageDocument` is the only aggregate passed to JSON, CLI, Python, Agent, and C++ projections.
- [ ] No reference project is imported, executed, spawned, or required at runtime.
- [ ] Legacy and Zen readers have separate format-specific code paths.
- [ ] Tagged and unversioned readers cannot silently substitute for each other.
- [ ] `exec_chains` is documented and implemented as a derived direct-edge summary, not runtime simulation.
- [ ] Blueprint functions expose instructions, CFG, calls, variables, and unresolved records.
- [ ] Material expressions expose nodes and links when present.
- [ ] C++ header output covers the Blueprint Header View declaration scope.
- [ ] C++ migration output is traceable, status-bearing, and never claims native-body equivalence.
- [ ] Cooked-away, encrypted, missing, and unknown data are reported as unavailable/opaque with reasons.
- [ ] Full tests, quality baseline, size baseline, and compileall verification pass.
