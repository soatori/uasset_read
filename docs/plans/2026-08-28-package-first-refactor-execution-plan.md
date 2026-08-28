# Package-First UAsset Parser Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** Current-state execution plan. This file does not replace the canonical design and does not claim that target behavior is implemented.

**Goal:** Replace the current v2-over-v1 adapter with one read-only, package-first Python API whose CLI, JSON projection, and Agent tools expose every export, bounded diagnostics, and only sample-backed semantics.

**Architecture:** Move the reusable legacy binary stages below the v2 public boundary instead of duplicating serializers. A `LegacyPackageReader` reads an addressable `Source` through bounded slices and builds `PackageDocument` directly; projections and handlers consume that document. Unsupported layouts and property families remain explicit diagnostics until a redistributable fixture and UE-source-backed implementation exist.

**Tech Stack:** Python 3.10+, standard library, existing `uasset_read` serializers/linker/property parsers, pytest, Ruff, JSON Schema, GitHub Issues.

**Spec:** `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`

## Global Constraints

- Python support remains `>=3.10`; the blocking local gate is Windows with Python 3.14.
- Core behavior remains cross-platform even while Linux/macOS execution is deferred.
- The first v2 milestone is read-only; no writer API or binary rewrite path is introduced.
- Every export remains addressable; `bIsAsset` adds the `asset` role and never filters objects.
- Legacy and Zen package layouts are selected from verifiable structure/container metadata, never from the UE major version.
- Tagged and unversioned properties use separate readers and converge on one JSON-safe value model.
- Every table count, offset, export region, property region, and output byte budget is bounded before use.
- Library code returns structured diagnostics and never configures process-global logging.
- JSON, CLI, Python, and Agent tools project from the same `PackageDocument` and the same projection function.
- Large payload bytes are never embedded by default; output carries descriptors and explicit extraction limits.
- Real-fixture support claims require UE-source evidence, manifest hash/size evidence, and strict structural assertions.
- Missing fixtures do not create `skip`, `xfail`, broad-exception aggregate tests, or speculative production branches.
- Investigation output stays under ignored `temp/`; reusable checks live in package APIs or `tests/`.
- Preserve unrelated changes in the dirty worktree.

---

## Verified Baseline

Snapshot used to write this plan:

- Branch: `dev-0.6.0`
- Baseline commit: `cec8a6b3 docs: synchronize package-first implementation status`
- Phase 0 issue: [#622](https://github.com/soatori/uasset_read/issues/622), closed
- Parent refactor issue: [#621](https://github.com/soatori/uasset_read/issues/621), open
- Current test collection: 197 root-level contract tests (after v2 suite removal); all pass with no skips/xfail
- Current v2 call path: `parse_package_document()` -> `LegacyPackageReader` directly via `v2/api.py`; dead `build_package_document()` adapter removed
- Current blockers confirmed in source: Zen, IoStore, Unversioned-with-schema, and payload extraction are stubs. Tagged property parsing, run_handlers, depth, and max_bytes all work end-to-end.

## Fixture Decision Matrix

| Capability/type | Tracked fixture | `external/` evidence | Can enter tracked tests now? | Plan decision |
|---|---|---|---|---|
| Legacy package, tagged properties | 47 legacy samples | many corroborating cases | yes | execute Tasks 1-10 |
| Multi-asset package | several, including `ABP_RifleAnimLayers.uasset` | present | yes | keep strict regression |
| Exports with zero `bIsAsset` | missing | 9 `uasset-rs` UE4.10 samples pass current parser with zero asset roles | yes, after attribution | promote the smallest sample in Task 1 |
| Loose `.uexp/.ubulk` | missing | UAssetAPI has 3 complete triplets | no; its TestAssets notice grants no redistribution rights | deferred to [#627](https://github.com/soatori/uasset_read/issues/627) |
| Unversioned + USMAP | unconfirmed/missing | UAssetAPI explicitly tests traditional unversioned packages with `.usmap` | no; same redistribution restriction | deferred to [#623](https://github.com/soatori/uasset_read/issues/623) |
| Zen package / IoStore | missing | no `.utoc` or `.ucas` anywhere under `external/` | no | deferred to [#624](https://github.com/soatori/uasset_read/issues/624) |
| Pak container | missing | no `.pak` under `external/` | no | deferred to [#625](https://github.com/soatori/uasset_read/issues/625) |
| CurveTable | missing | zero `CurveTable` binary name-map hits across 627 external `.uasset` and 16 `.umap` files | no | deferred to [#626](https://github.com/soatori/uasset_read/issues/626) |
| StringTable | missing | direct UAssetAPI `ST_Attributes.uasset` reference | no redistribution grant | tracked by [#615](https://github.com/soatori/uasset_read/issues/615) |
| BlendSpace / AnimComposite | no standalone asset | no standalone external case found | no | tracked by [#618](https://github.com/soatori/uasset_read/issues/618) |
| AnimLayerInterface | missing | direct UAssetAPI reference | no redistribution grant | tracked by [#618](https://github.com/soatori/uasset_read/issues/618) |
| PhysicsAsset | no standalone asset | references only; no usable primary fixture | no | tracked by [#619](https://github.com/soatori/uasset_read/issues/619) |
| PhysicalMaterial | no standalone asset | direct UAssetAPI references | no redistribution grant | tracked by [#619](https://github.com/soatori/uasset_read/issues/619) |

The main path does not implement any row marked “deferred.” Closing the parent refactor remains blocked until the relevant fixture issue is resolved and a follow-up implementation slice passes its own gate.

## File Responsibility Map

| File | Responsibility after this plan |
|---|---|
| `src/uasset_read/v2/source.py` | Addressable sources plus bounded archive-compatible slices; no UObject logic |
| `src/uasset_read/v2/package/legacy.py` | Legacy summary/tables/object/property reading and direct `PackageDocument` construction |
| `src/uasset_read/v2/package/__init__.py` | Public package-reader exports only; no v1 `ParseResult` adapter |
| `src/uasset_read/v2/api.py` | Layout dispatch and the public Python document API |
| `src/uasset_read/v2/properties.py` | Tagged value normalization and shared property descriptors; schema protocol remains for the deferred unversioned slice |
| `src/uasset_read/v2/handlers.py` | Object-local semantic enrichment and handler diagnostics |
| `src/uasset_read/v2/projection.py` | The only dict/JSON projection, including view/depth/selection/pagination/byte limits |
| `src/uasset_read/v2/agent_tools.py` | Thin calls to public parse + projection APIs |
| `src/uasset_read/cli.py` | Argument parsing and projection output; no independent serializer |
| `src/uasset_read/pipeline/core.py` | Temporary v1 compatibility wrapper that calls the v2 legacy reader; removed only after migration gates pass |
| `tests/test_*_contract.py` | One strict contract layer per current capability |
| `tests/samples/manifest.json` | Review-controlled fixture hashes, sizes, layout, sidecars, source, and expected structural facts |

## Dependency Order

`Task 1 -> Task 2 -> Task 3 -> Task 4 -> Task 5 -> Task 6 -> Task 7 -> Tasks 8-10 -> Task 11`

Tasks 8-10 may run independently after Task 7. Deferred fixture issues do not run in parallel with the main path because they require human provenance/licensing work rather than parser code.

---

### Task 1: Promote a licensed zero-`bIsAsset` fixture

**Files:**

- Copy: `external/uasset-rs/assets/UE410/SimpleRefs/SimpleRefsSoftRef.uasset` -> `tests/samples/uasset_rs_UE410_SimpleRefsSoftRef.uasset`
- Create: `tests/samples/README.md`
- Modify: `tests/samples/manifest.json`
- Modify: `tests/test_manifest_contract.py`
- Modify: `tests/test_document_contract.py`

**Interfaces:**

- Consumes: the current manifest JSON and `parse_package_document(path, tolerant=True)`.
- Produces: one tracked 4,037-byte legacy sample with SHA-256 `c7d31152d98a68156e1afeb9c64ca1d0032ad023786ff9807f06900ce1721458`, 6 exports, and 0 `bIsAsset` exports.

- [ ] **Step 1: Copy the exact binary and record provenance**

```powershell
Copy-Item -LiteralPath 'external\uasset-rs\assets\UE410\SimpleRefs\SimpleRefsSoftRef.uasset' -Destination 'tests\samples\uasset_rs_UE410_SimpleRefsSoftRef.uasset'
Get-FileHash -Algorithm SHA256 'tests\samples\uasset_rs_UE410_SimpleRefsSoftRef.uasset'
(Get-Item 'tests\samples\uasset_rs_UE410_SimpleRefsSoftRef.uasset').Length
```

Expected hash and size are the values in the interface block. `tests/samples/README.md` must name `https://github.com/jorgenpt/uasset-rs`, source commit `b1d5a7f5b4414ae3e443b882bed3eb51caf21596`, and the upstream MIT/Apache-2.0 licenses.

- [ ] **Step 2: Add the manifest entry and strict assertions**

```python
def test_zero_asset_role_fixture_is_manifested(manifest):
    entry = next(
        item
        for item in manifest["samples"]
        if item["name"] == "uasset_rs_UE410_SimpleRefsSoftRef.uasset"
    )
    assert entry["size_bytes"] == 4037
    assert entry["engine_layout"] == "legacy"
    assert entry["export_count"] == 6
    assert entry["b_is_asset_count"] == 0


def test_exports_survive_without_asset_role(samples_dir):
    doc = parse_package_document(samples_dir / "uasset_rs_UE410_SimpleRefsSoftRef.uasset")
    assert len(doc.objects) == 6
    assert doc.summary.asset_object_ids == ()
```

- [ ] **Step 3: Run the focused gate**

Run: `python -m pytest tests/test_manifest_contract.py tests/test_document_contract.py -q`

Expected: all tests pass; no skip/xfail is collected.

- [ ] **Step 4: Commit the fixture boundary**

```powershell
git add tests/samples/uasset_rs_UE410_SimpleRefsSoftRef.uasset tests/samples/README.md tests/samples/manifest.json tests/test_manifest_contract.py tests/test_document_contract.py
git commit -m "test: add package without asset-role exports"
```

---

### Task 2: Make bounded sources usable by existing serializers

**Files:**

- Modify: `src/uasset_read/v2/source.py`
- Modify: `tests/test_reader_contract.py`

**Interfaces:**

- Consumes: `Source.read_at(offset: int, size: int) -> bytes` and the existing `ArchiveLike` protocol.
- Produces: `SliceReader` methods `close() -> None`, `total_size() -> int`, and `set_byte_swapping(enabled: bool) -> None`, allowing it to back `PackageArchive` without a second binary primitive stack.

- [ ] **Step 1: Write the archive compatibility test**

```python
def test_slice_reader_satisfies_archive_like():
    from uasset_read.package import PackageArchive
    from uasset_read.v2.source import MemorySource, SliceReader

    reader = SliceReader(MemorySource(b"abcdef"), 1, 4)
    archive = PackageArchive(reader)
    assert archive.total_size() == 4
    archive.set_byte_swapping(True)
    assert archive.read(2) == b"bc"
    archive.close()
```

- [ ] **Step 2: Run the test and verify the missing protocol methods fail**

Run: `python -m pytest tests/test_reader_contract.py::test_slice_reader_satisfies_archive_like -q`

Expected: fail before implementation because `SliceReader` does not satisfy `ArchiveLike`.

- [ ] **Step 3: Add only the three required methods**

```python
def total_size(self) -> int:
    return self._length

def set_byte_swapping(self, enabled: bool) -> None:
    pass  # byte order is applied by PackageArchive's primitive readers

def close(self) -> None:
    pass  # Source owns no persistent handle
```

- [ ] **Step 4: Run the complete reader contract**

Run: `python -m pytest tests/test_reader_contract.py -q`

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/uasset_read/v2/source.py tests/test_reader_contract.py
git commit -m "refactor: bridge bounded sources to package archive"
```

---

### Task 3: Build `PackageDocument` directly with `LegacyPackageReader`

**Files:**

- Create: `src/uasset_read/v2/package/legacy.py`
- Modify: `src/uasset_read/v2/package/__init__.py`
- Modify: `src/uasset_read/v2/api.py`
- Modify: `src/uasset_read/v2/object_model.py`
- Modify: `src/uasset_read/v2/diagnostics.py`
- Modify: `tests/test_document_contract.py`
- Modify: `tests/test_manifest_contract.py`

**Interfaces:**

- Consumes: `FileSource`, `SliceReader`, `PackageArchive`, `read_package_summary`, `read_name_table`, `read_import_map`, `read_export_map`, `read_depends_map`, `read_preload_dependencies`, and `build_version_context_from_summary`.
- Produces:

```python
class LegacyPackageReader:
    def __init__(
        self,
        source: Source,
        *,
        tolerant: bool = True,
        mappings_path: str | None = None,
        game: str | None = None,
    ) -> None: ...

    def read(
        self,
        *,
        depth: str = "package",
        object_ids: Sequence[str] | None = None,
    ) -> PackageDocument: ...
```

`parse_package_document()` constructs `FileSource` and calls this reader. It no longer imports `parse_uasset_with_linker` or accepts a v1 `ParseResult`.

```python
def parse_package_document(
    file_path: str | Path,
    *,
    tolerant: bool = True,
    mappings_path: str | None = None,
    game: str | None = None,
    depth: Literal["package", "object", "asset", "decode"] = "asset",
    object_ids: Sequence[str] | None = None,
) -> PackageDocument: ...
```

- [ ] **Step 1: Add a failing test that forbids the v1 adapter call**

```python
def test_v2_api_does_not_call_v1_pipeline(monkeypatch, sample_path):
    import uasset_read.pipeline.core as old_core

    def forbidden(*args, **kwargs):
        raise AssertionError("v1 pipeline called")

    monkeypatch.setattr(old_core, "parse_uasset_with_linker", forbidden)
    doc = parse_package_document(sample_path, depth="package")
    assert doc.package.layout == "legacy"
    assert doc.summary.total_exports == len(doc.objects)
```

- [ ] **Step 2: Run the focused test and verify it fails through `v2/api.py`**

Run: `python -m pytest tests/test_document_contract.py::test_v2_api_does_not_call_v1_pipeline -q`

Expected: fail with `AssertionError: v1 pipeline called`.

- [ ] **Step 3: Implement the direct table path**

The reader must:

1. wrap the source in `SliceReader(source, 0, source.size())` and `PackageArchive`;
2. read summary, names, imports, exports, depends, and preload dependencies with the existing serializers;
3. validate count/offset ranges before table reads;
4. build immutable `VersionContext` from the summary;
5. create one `ObjectRecord` for every export, including `class_ref`, `outer_ref`, `super_ref`, and `template_ref`;
6. derive `class_of`, `outer_of`, `super_of`, `template_of`, and depends/preload relations from package indices;
7. convert caught boundary failures into `Diagnostic(stage, code, object_id, offset, size, recoverable)`;
8. leave object properties and semantics unset at `depth="package"`.

- [ ] **Step 4: Add table parity across every tracked legacy fixture**

```python
def test_legacy_reader_matches_manifest_tables(manifest, samples_dir):
    for entry in manifest["samples"]:
        if entry["engine_layout"] != "legacy":
            continue
        doc = parse_package_document(samples_dir / entry["name"], depth="package")
        assert doc.package.layout == "legacy", entry["name"]
        assert doc.package.export_count == entry["export_count"], entry["name"]
        assert len(doc.objects) == entry["export_count"], entry["name"]
        assert len(doc.summary.asset_object_ids) == entry["b_is_asset_count"], entry["name"]
```

- [ ] **Step 5: Run the package contracts**

Run: `python -m pytest tests/test_document_contract.py tests/test_manifest_contract.py -q`

Expected: all tracked legacy fixtures pass; one malformed fixture failure names its sample and stage rather than being swallowed.

- [ ] **Step 6: Commit**

```powershell
git add src/uasset_read/v2/package/legacy.py src/uasset_read/v2/package/__init__.py src/uasset_read/v2/api.py src/uasset_read/v2/object_model.py src/uasset_read/v2/diagnostics.py tests/test_document_contract.py tests/test_manifest_contract.py
git commit -m "refactor: read legacy packages directly into documents"
```

---

### Task 4: Migrate tagged properties and preserve unknown regions

**Files:**

- Modify: `src/uasset_read/v2/package/legacy.py`
- Modify: `src/uasset_read/v2/properties.py`
- Modify: `src/uasset_read/v2/object_model.py`
- Create: `tests/test_property_contract.py`
- Create: `tests/test_diagnostics_contract.py`

**Interfaces:**

- Consumes: existing `parse_properties_from_export()` and `build_properties_dict()` behavior inside a bounded export slice.
- Produces:

```python
def normalize_property_bag(properties: Sequence[Any]) -> dict[str, Any]: ...

@dataclass(frozen=True)
class OpaqueValue:
    type_name: str
    offset: int
    size: int
    reason: str
```

At `depth="object"`, only requested object IDs are parsed. Unknown values become descriptors plus diagnostics; raw bytes remain source-addressable and are not emitted in JSON.

- [ ] **Step 1: Add the object-depth selection test**

```python
def test_object_depth_parses_only_requested_export(sample_path):
    doc = parse_package_document(sample_path, depth="object", object_ids=["export:1"])
    parsed = [obj.id for obj in doc.objects if obj.properties is not None]
    assert parsed == ["export:1"]
    assert len(doc.objects) == doc.package.export_count
```

- [ ] **Step 2: Add the JSON-safe unknown-value test**

```python
def test_unknown_property_is_descriptor_not_blob():
    bag = normalize_property_bag([
        SimpleNamespace(
            name="Mystery",
            value=PropertyFallback(
                name="Mystery",
                type="UnknownProperty",
                size=4,
                raw_bytes=b"\x01\x02\x03\x04",
                reason=FallbackReason.UNSUPPORTED_TYPE,
            ),
        )
    ])
    assert bag["Mystery"]["kind"] == "opaque"
    assert bag["Mystery"]["size"] == 4
    assert "raw_bytes" not in bag["Mystery"]
    json.dumps(bag)
```

- [ ] **Step 3: Run both tests and verify the current empty property path fails**

Run: `python -m pytest tests/test_property_contract.py -q`

Expected: fail before implementation because v2 objects do not hold normalized properties.

- [ ] **Step 4: Implement bounded tagged parsing**

Use `SliceReader.sub_slice(export.serial_offset, export.serial_size)` or the equivalent validated package slice for each requested export. Reuse current tag/value readers; do not copy their switch tables. Catch only declared parse/bounds exceptions at this boundary, set object status to `partial` or `opaque`, append a structured diagnostic, and continue with the next export.

- [ ] **Step 5: Run property and failure-isolation contracts**

Run: `python -m pytest tests/test_property_contract.py tests/test_diagnostics_contract.py tests/test_document_contract.py -q`

Expected: pass; a failed export cannot remove later objects.

- [ ] **Step 6: Commit**

```powershell
git add src/uasset_read/v2/package/legacy.py src/uasset_read/v2/properties.py src/uasset_read/v2/object_model.py tests/test_property_contract.py tests/test_diagnostics_contract.py tests/test_document_contract.py
git commit -m "refactor: add bounded tagged properties to package documents"
```

---

### Task 5: Make projection controls real and byte-bounded

**Files:**

- Modify: `src/uasset_read/v2/projection.py`
- Modify: `src/uasset_read/v2/document.py`
- Modify: `tests/test_projection_contract.py`
- Create: `tests/test_schema_contract.py`
- Modify: `docs/designs/contract/package_document_v2.schema.json`
- Modify: `docs/designs/contract/package_document_v2.example.json`

**Interfaces:**

- Consumes: one fully built `PackageDocument` and stable table-order object IDs.
- Produces:

```python
def project_document(
    doc: PackageDocument,
    *,
    view: Literal["semantic", "raw", "debug"] = "semantic",
    depth: Literal["package", "object", "asset", "decode"] = "asset",
    object_ids: Sequence[str] | None = None,
    roles: Sequence[str] | None = None,
    classes: Sequence[str] | None = None,
    fields: Sequence[str] | None = None,
    offset: int = 0,
    limit: int | None = None,
    max_bytes: int | None = None,
) -> dict[str, Any]: ...
```

`PackageDocument.to_dict()` delegates to `project_document()` through a local import; there is no second serializer.

- [ ] **Step 1: Add depth and byte-budget failures**

```python
def test_depth_changes_parse_cost(sample_path):
    package_doc = parse_package_document(sample_path, depth="package")
    object_doc = parse_package_document(sample_path, depth="object", object_ids=["export:1"])
    assert all(obj.properties is None for obj in package_doc.objects)
    assert object_doc.objects[1].properties is not None


def test_max_bytes_is_enforced_and_continuable(doc):
    page = project_document(doc, limit=100, max_bytes=4096)
    encoded = json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert len(encoded) <= 4096
    assert page["truncation"]["reason"] == "max_bytes"
    assert page["next_offset"] > 0
    assert any(d["code"] == "TRUNCATED" for d in page["diagnostics"])
```

- [ ] **Step 2: Run the focused projection tests**

Run: `python -m pytest tests/test_projection_contract.py -q`

Expected: fail because current `depth` is only copied and `max_bytes` is unused.

- [ ] **Step 3: Implement one deterministic projection**

Validate enum values and non-negative limits. Filter in table order, include only relations/dependencies/payload descriptors reachable from the returned object page, append bounded entries one at a time, and measure compact UTF-8 JSON with the standard library. The object-table offset is the continuation cursor; every omitted reachable entry produces a truncation diagnostic. If the encoded minimal envelope exceeds `max_bytes`, raise `ValueError` with the required byte count before producing output; CLI and Agent boundaries translate that error to `OUTPUT_BUDGET_TOO_SMALL`. Never return bytes above the requested limit.

- [ ] **Step 4: Regenerate the checked contract example through the projection API**

The example remains semantic + asset, omits flags/raw property trees/blob bytes, and validates against `package_document_v2.schema.json`.

- [ ] **Step 5: Run projection and schema gates**

Run: `python -m pytest tests/test_projection_contract.py tests/test_schema_contract.py -q`

Expected: pass for all views and pagination continuation.

- [ ] **Step 6: Commit**

```powershell
git add src/uasset_read/v2/projection.py src/uasset_read/v2/document.py tests/test_projection_contract.py docs/designs/contract/package_document_v2.schema.json docs/designs/contract/package_document_v2.example.json
git commit -m "feat: enforce package projection depth and byte budgets"
```

---

### Task 6: Route CLI, Python, and Agent tools through one projection

**Files:**

- Modify: `src/uasset_read/cli.py`
- Modify: `src/uasset_read/v2/agent_tools.py`
- Modify: `src/uasset_read/__init__.py`
- Modify: `src/uasset_read/pipeline/core.py`
- Modify: `tests/test_application_contract.py`

**Interfaces:**

- Consumes: `parse_package_document()` and `project_document()` from Tasks 3-5.
- Produces: CLI and six Agent functions whose object IDs, status, diagnostics, pagination, and byte limits match Python projection output exactly.

- [ ] **Step 1: Add equality tests across all three entry points**

```python
def run_cli_json(*args):
    result = subprocess.run(
        [sys.executable, "-m", "uasset_read", *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_cli_agent_python_share_projection(sample_path):
    doc = parse_package_document(sample_path, depth="package")
    expected = project_document(doc, depth="package", limit=2, max_bytes=4096)
    cli = run_cli_json("--v2", "--depth", "package", "--limit", "2", "--max-bytes", "4096", sample_path)
    agent = inspect_package(sample_path, depth="package", limit=2, max_bytes=4096)
    for actual in (cli, agent):
        assert [o["id"] for o in actual["objects"]] == [o["id"] for o in expected["objects"]]
        assert actual["diagnostics"] == expected["diagnostics"]
```

- [ ] **Step 2: Replace CLI `doc.to_dict()` and Agent hand-built dicts**

CLI argument parsing may remain in `cli.py`; all data shaping calls `project_document`. Agent tools may add tool-specific envelopes such as `total`, but object records and diagnostics are copied from projection results rather than rebuilt.

- [ ] **Step 3: Fix logging lifecycle assertions**

```python
def test_disabled_logging_has_no_files_or_root_mutation(tmp_path, sample_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = (logging.root.level, tuple(logging.root.handlers))
    parse_package_document(sample_path, depth="package")
    assert list(tmp_path.iterdir()) == []
    assert (logging.root.level, tuple(logging.root.handlers)) == before
```

Add `logging.NullHandler()` only to the package logger. Remove unconditional `configure_project_logging()` from the legacy compatibility function; explicit CLI logging remains the only configuration owner.

- [ ] **Step 4: Run application contracts**

Run: `python -m pytest tests/test_application_contract.py tests/test_projection_contract.py -q`

Expected: pass; all byte limits are enforced and no library call creates a file.

- [ ] **Step 5: Commit**

```powershell
git add src/uasset_read/cli.py src/uasset_read/v2/agent_tools.py src/uasset_read/__init__.py src/uasset_read/pipeline/core.py tests/test_application_contract.py
git commit -m "refactor: unify cli and agent package projection"
```

---

### Task 7: Wire object-local handlers into the runtime

**Files:**

- Modify: `src/uasset_read/v2/handlers.py`
- Modify: `src/uasset_read/v2/package/legacy.py`
- Modify: `src/uasset_read/v2/object_model.py`
- Modify: `tests/test_handler_contract.py`
- Modify: `tests/test_diagnostics_contract.py`

**Interfaces:**

- Consumes: parsed `ObjectRecord`, `VersionContext`, all package objects, and reader-owned package data.
- Produces:

```python
def run_handlers(
    obj: ObjectRecord,
    context: VersionContext,
    all_objects: Sequence[ObjectRecord],
    package_data: Any,
) -> tuple[dict[str, Any] | None, list[CoverageEntry], list[Diagnostic]]: ...
```

`depth="asset"` runs light handlers for asset-role objects; `depth="decode"` runs only explicitly selected heavy handlers. Handler failure changes only that object's semantic status and diagnostics.

- [ ] **Step 1: Replace the current vacuous end-to-end assertion**

```python
def test_datatable_handler_runs_from_public_api(samples_dir):
    doc = parse_package_document(samples_dir / "ALS_FootstepDataTable.uasset", depth="asset")
    obj = next(o for o in doc.objects if o.class_name == "DataTable")
    assert obj.semantic is not None
    assert obj.semantic["kind"] == "data_table"
    assert obj.status.semantic in {"complete", "partial"}
    assert any(c.feature == "handler.DataTable" for c in obj.coverage)
```

- [ ] **Step 2: Add handler failure isolation**

```python
def test_handler_exception_becomes_object_diagnostic(monkeypatch, samples_dir):
    import uasset_read.v2.handlers as handlers
    from uasset_read.v2.api import parse_package_document

    class RaisingHandler:
        def supports(self, obj, context):
            return True

        def enrich(self, obj, context, all_objects, package_data):
            raise ValueError("broken handler")

    monkeypatch.setattr(handlers, "_HANDLERS", [RaisingHandler()])
    sample_doc = parse_package_document(
        samples_dir / "ALS_FootstepDataTable.uasset",
        depth="object",
        object_ids=["export:1"],
    )
    semantic, coverage, diagnostics = handlers.run_handlers(
        sample_doc.objects[0], VersionContext(), sample_doc.objects, None
    )
    assert semantic is None
    assert coverage[0].status == "missing"
    assert diagnostics[0].stage == "semantic.handler"
    assert diagnostics[0].object_id == sample_doc.objects[0].id
```

- [ ] **Step 3: Run and verify the public API test fails before wiring**

Run: `python -m pytest tests/test_handler_contract.py -q`

Expected: the DataTable public API test fails because current runtime never calls `run_handlers`.

- [ ] **Step 4: Wire handlers once in `LegacyPackageReader.read()`**

Do not run handlers in projection or Agent tools. Store semantic, coverage, and diagnostics on the same object. Preserve table order and continue after any handler boundary exception.

- [ ] **Step 5: Run handler and diagnostics gates**

Run: `python -m pytest tests/test_handler_contract.py tests/test_diagnostics_contract.py -q`

Expected: pass; no conditional assertion allows `semantic is None` for a supported real sample.

- [ ] **Step 6: Commit**

```powershell
git add src/uasset_read/v2/handlers.py src/uasset_read/v2/package/legacy.py src/uasset_read/v2/object_model.py tests/test_handler_contract.py tests/test_diagnostics_contract.py
git commit -m "feat: run v2 asset handlers on package objects"
```

---

### Task 8: Complete sample-backed data, texture, and sound handlers

**Files:**

- Modify: `src/uasset_read/v2/handlers.py`
- Modify: `tests/test_handler_contract.py`
- Create: `tests/test_payload_contract.py`
- Update issue: [#602](https://github.com/soatori/uasset_read/issues/602)
- Update issue: [#605](https://github.com/soatori/uasset_read/issues/605)

**Interfaces:**

- Consumes: normalized object properties and existing reader-owned native metadata.
- Produces stable `semantic.kind` values `data_table`, `user_defined_enum`, `user_defined_struct`, `texture`, and `sound`, plus payload descriptors without bytes.

- [ ] **Step 1: Add strict real-sample assertions**

```python
@pytest.mark.parametrize(
    ("sample", "class_name", "kind"),
    [
        ("ALS_FootstepDataTable.uasset", "DataTable", "data_table"),
        ("Lyra_Enum_PanelType.uasset", "UserDefinedEnum", "user_defined_enum"),
        ("StackOBot_Struct_Objective.uasset", "UserDefinedStruct", "user_defined_struct"),
        ("FirstPerson_T_GridChecker_A.uasset", "Texture2D", "texture"),
        ("MutableSample_GrayLightTextureCube.uasset", "TextureCube", "texture"),
        ("ALS_Concrete_Step_01_SoundWave.uasset", "SoundWave", "sound"),
    ],
)
def test_sample_backed_handler(sample, class_name, kind, samples_dir):
    doc = parse_package_document(samples_dir / sample, depth="asset")
    obj = next(o for o in doc.objects if o.class_name == class_name)
    assert obj.semantic["kind"] == kind
    assert obj.coverage
```

- [ ] **Step 2: Assert domain invariants rather than field presence only**

DataTable `row_count` equals the number of emitted rows; enum/struct member counts equal emitted members; texture dimensions and mip count are positive; sound duration/channels/sample rate use `partial` coverage when absent. Payload descriptors include owner, source region, offset, size, and status but never bytes.

- [ ] **Step 3: Run the handler subset**

Run: `python -m pytest tests/test_handler_contract.py tests/test_payload_contract.py -q`

Expected: pass for the listed tracked samples. StringTable and CurveTable are not collected; they remain blocked by #615 and #626.

- [ ] **Step 4: Update issue evidence and commit**

Read back #602 and #605 after adding exact test names and pass output. Commit only source/tests in this slice.

```powershell
git add src/uasset_read/v2/handlers.py tests/test_handler_contract.py tests/test_payload_contract.py
git commit -m "feat: add sample-backed data texture and sound semantics"
```

---

### Task 9: Complete sample-backed skeleton and mesh summaries

**Files:**

- Modify: `src/uasset_read/v2/handlers.py`
- Modify: `tests/test_handler_contract.py`
- Update issue: [#603](https://github.com/soatori/uasset_read/issues/603)

**Interfaces:**

- Consumes: `Skeleton`, `StaticMesh`, and available skeletal mesh metadata from tracked legacy fixtures.
- Produces `semantic.kind` values `skeleton` and `mesh`; counts equal emitted lists, references use stable package object IDs when resolvable.

- [ ] **Step 1: Add real-sample invariants**

```python
def test_skeleton_summary_is_internally_consistent(samples_dir):
    doc = parse_package_document(samples_dir / "ALS_Mannequin_Skeleton.uasset", depth="asset")
    obj = next(o for o in doc.objects if o.class_name == "Skeleton")
    assert obj.semantic["kind"] == "skeleton"
    assert obj.semantic["bone_count"] == len(obj.semantic["bones"])
    assert obj.semantic["bone_count"] > 0


def test_static_mesh_summary_is_internally_consistent(samples_dir):
    doc = parse_package_document(samples_dir / "StarterContent_SM_Chair.uasset", depth="asset")
    obj = next(o for o in doc.objects if o.class_name == "StaticMesh")
    assert obj.semantic["kind"] == "mesh"
    assert obj.semantic["lod_count"] == len(obj.semantic["lods"])
```

- [ ] **Step 2: Implement only fields proven by the fixtures**

Emit bone name/parent index; mesh LOD/section/material-reference summaries; attach partial coverage for unavailable render payloads. PhysicsAsset fields are excluded and remain in #619.

- [ ] **Step 3: Run, update #603, and commit**

Run: `python -m pytest tests/test_handler_contract.py -q`

```powershell
git add src/uasset_read/v2/handlers.py tests/test_handler_contract.py
git commit -m "feat: add package object skeleton and mesh summaries"
```

---

### Task 10: Migrate graph and Blueprint extensions behind `depth=decode`

**Files:**

- Modify: `src/uasset_read/v2/handlers.py`
- Modify: `src/uasset_read/v2/package/legacy.py`
- Modify: `tests/test_handler_contract.py`
- Modify: `tests/test_projection_contract.py`
- Update issue: [#620](https://github.com/soatori/uasset_read/issues/620)

**Interfaces:**

- Consumes: current Material/Niagara/Blueprint/AnimBlueprint/Kismet extractors and stable package object relations.
- Produces light summaries at `depth="asset"`; full graph/node/pin/bytecode data only for explicitly selected objects at `depth="decode"`.

- [ ] **Step 1: Prove asset depth stays bounded**

```python
def test_asset_depth_omits_heavy_graph_arrays(samples_dir):
    doc = parse_package_document(samples_dir / "ABP_RifleAnimLayers.uasset", depth="asset")
    obj = next(o for o in doc.objects if o.class_name == "AnimBlueprintGeneratedClass")
    assert obj.semantic["kind"] == "anim_blueprint"
    assert "nodes" not in obj.semantic
    assert "bytecode" not in obj.semantic
```

- [ ] **Step 2: Prove decode is explicit and reference-safe**

```python
def test_decode_graph_references_existing_nodes(samples_dir):
    doc = parse_package_document(
        samples_dir / "ABP_RifleAnimLayers.uasset",
        depth="decode",
        object_ids=["export:2"],
    )
    graph = doc.objects[2].semantic["graph"]
    node_ids = {node["id"] for node in graph["nodes"]}
    assert all(edge["from_node"] in node_ids and edge["to_node"] in node_ids for edge in graph["edges"])
```

- [ ] **Step 3: Reuse existing extractors as handler internals**

Move no binary parser into projection. Adapter functions may translate existing IR objects into object-local semantic dictionaries, but the v2 handler owns status/coverage and the top-level format remains `uasset_read.package`.

- [ ] **Step 4: Run graph/decode contracts**

Run: `python -m pytest tests/test_handler_contract.py tests/test_projection_contract.py -q`

Expected: tracked Material, Niagara, Blueprint, and AnimBlueprint samples pass; no unsupported asset type is silently marked complete.

- [ ] **Step 5: Update #620 and commit**

```powershell
git add src/uasset_read/v2/handlers.py src/uasset_read/v2/package/legacy.py tests/test_handler_contract.py tests/test_projection_contract.py
git commit -m "refactor: move graph semantics behind object decode depth"
```

---

### Task 11: Close the executable gate and synchronize current documentation

**Files:**

- Modify: `README.md`
- Modify: `docs/designs/README.md`
- Modify: `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` only for implementation-status notes, not target changes
- Modify: `docs/reference/agent-dev-reference.md`
- Modify: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Modify: `.github/workflows/ci.yml` only if current dirty changes belong to this refactor
- Update issue: [#621](https://github.com/soatori/uasset_read/issues/621)

**Interfaces:**

- Consumes: Tasks 1-10 and their exact test output.
- Produces: current docs that claim only implemented legacy/tagged/sample-backed behavior, plus a parent issue checklist separating passed gates from fixture-blocked work.

- [ ] **Step 1: Run the full local gate from a clean Python process**

```powershell
python --version
python -m pytest --collect-only -q
python -m pytest -q
python -m ruff check src tests
python -m build
git diff --check
git status --short
```

Expected: Python 3.14 on the blocking machine; no unexpected skip/xfail; all commands exit 0. If Ruff/build tooling is absent, install the project development tools before claiming the gate.

- [ ] **Step 2: Run real-sample spot checks through every entry point**

```powershell
python -m uasset_read --v2 --depth package --limit 2 tests/samples/ABP_RifleAnimLayers.uasset
python -m uasset_read --v2 --depth asset --limit 2 tests/samples/ALS_FootstepDataTable.uasset
```

Compare Python, CLI, and Agent outputs for IDs, status, diagnostics, truncation, and absence of blob bytes.

- [ ] **Step 3: Update current-state documentation**

Document Legacy + Tagged + implemented handler families as current only after the gate passes. Keep Unversioned, sidecars, Zen/IoStore, Pak, CurveTable, StringTable, Anim extras, and Physics marked deferred with their issue links.

- [ ] **Step 4: Update and read back #621**

The parent must link this plan, list completed task commits, and retain open checkboxes for #623-#627, #615, #618, and #619. Do not close #621 while any canonical acceptance gate is blocked.

- [ ] **Step 5: Commit documentation synchronization**

```powershell
git add README.md docs/designs/README.md docs/designs/2026-08-26-package-first-uasset-parser-refactor.md docs/reference/agent-dev-reference.md .github/ISSUE_TEMPLATE/bug_report.yml .github/workflows/ci.yml
git commit -m "docs: synchronize package-first implementation status"
```

---

## Deferred Continuation Gates

These are deliberately outside the executable task chain:

1. [#623](https://github.com/soatori/uasset_read/issues/623) must provide a redistributable unversioned package + mapping before `UnversionedPropertyReader` or `UsmapSchemaProvider` receives production branches.
2. [#627](https://github.com/soatori/uasset_read/issues/627) must provide redistributable `.uexp/.ubulk` packages before sidecar regions and successful payload extraction are claimed.
3. [#624](https://github.com/soatori/uasset_read/issues/624) must provide `.utoc/.ucas` before Zen layout detection and IoStore range reading are implemented.
4. [#625](https://github.com/soatori/uasset_read/issues/625) must provide a Pak before Pak integration becomes a v2 support claim.
5. [#626](https://github.com/soatori/uasset_read/issues/626), [#615](https://github.com/soatori/uasset_read/issues/615), [#618](https://github.com/soatori/uasset_read/issues/618), and [#619](https://github.com/soatori/uasset_read/issues/619) gate the named handler families.
6. Phase 6 deletion of Semantic 1.x, old IR/renderers, compatibility wrappers, and old logging code begins only after all public callers are on v2 and the Phase 5 fixture-backed path passes. Until then, v1 code is a compatibility consumer of shared lower layers, never the implementation behind the v2 API.

## Self-Review Record

- Spec coverage: current executable work covers Legacy reader, package/object model, tagged properties, projections, CLI/Python/Agent consistency, logging, and every handler family backed by tracked fixtures.
- Explicit gaps: Unversioned, sidecars/payload extraction, Zen/IoStore, Pak, CurveTable, StringTable, Anim extras, and Physics are linked to live issues and excluded from implementation claims.
- Type consistency: `Source`, `SliceReader`, `LegacyPackageReader.read()`, `parse_package_document()`, `project_document()`, and `run_handlers()` signatures are defined before dependent tasks.
- Placeholder scan: the plan contains no unspecified implementation step; fixture-blocked work has measurable acquisition criteria in its issue.
