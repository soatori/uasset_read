# Issue 77 Native UFunction Script Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse UE 5.0-5.8 Blueprint function implementations from each owning `Function/UFunction` export, reconstruct logical Kismet bytecode addresses, and expose verified code or structured failure without heuristic substitution.

**Architecture:** A bounded native UFunction reader consumes tagged UObject properties, the source-backed UStruct prefix, native FFields, and the Script size header. A dual-cursor Kismet archive then separates serialized bytes from the reconstructed 64-bit Script address space; the existing AST and translator consume only this native result. BPGC ordinal mapping and production serial scanning are removed, while an explicit diagnostic scanner remains isolated from normal output.

**Tech Stack:** Python 3.10+, standard library only, existing `FArchive`/`ByteArchive`, existing Kismet AST/CFG/translator, pytest, JSON Schema, UE 5.8 C++ source under `E:/Develop/lib/UnrealEngine`.

## Global Constraints

- Work only in `E:/Develop/uasset_read/.worktrees/issue-77-ufunction-script` on branch `codex/issue-77-ufunction-script`; do not implement in the primary checkout.
- Target editor-saved/unbaked UE 5.0 through UE 5.8 packages and a 64-bit logical Script pointer size of exactly 8 bytes; UE4 and 32-bit Script layouts are out of scope.
- Require `file_version_ue4 >= 399` and `file_version_licensee >= 0`, the minimum UE Script VM serialization versions; reject older layouts with `unsupported_serialization_version`.
- Keep zero runtime dependencies and do not run `pip install`.
- Start every export read at `ObjectExport.serial_offset`, bound every read by `serial_size`, and use ScriptSerialization offsets only as diagnostic cross-checks.
- Use exact package/custom-version data; do not infer binary layouts from `saved_by_engine_version.minor`.
- Treat missing custom versions as `-1`; compare package-stored little-endian GUID keys, not canonical GUID text.
- Accept only `function_export` as a production bytecode source. BPGC mapping and serial-scan candidates must never construct a decompiled function result.
- Unknown native fields and unknown expression tokens fail at the exact offset in strict and tolerant entry points; tolerant mode may wrap the failure but may not skip bytes.
- Keep graph topology compatible as `logic_source=graph_topology`, but never let it upgrade `bytecode_status` or `translation_status`.
- Put every new Python test in `tests/temp/`; do not modify the six root benchmark/sample test files without separate user confirmation.
- Run tests with `$env:PYTHONPATH='src'` and confirm `uasset_read.__file__` points inside this worktree before real-sample acceptance.
- Preserve unrelated user changes; before each task, run `git status --short` and stop if a changed scoped file was not produced by an earlier plan task.
- Code comments, errors, and repository documentation remain English.

---

## File Structure

- `src/uasset_read/kismet/ufunction_reader.py`: bounded Function export navigation, exact version gates, UStruct prefix, Script header, and structured native-read result.
- `src/uasset_read/kismet/value_types.py`: shared lossless `FNameRef` value model used by native fields and Script operands.
- `src/uasset_read/kismet/native_fields.py`: source-backed FField/FProperty declarations and recursive inner-field serializers only.
- `src/uasset_read/kismet/archive.py`: serialized cursor, logical bytecode cursor, transfer primitives, and structured expression errors.
- `src/uasset_read/kismet/property_pointer.py`: serialized `FName`, `FFieldPath`, and field-pointer value models.
- `src/uasset_read/kismet/diagnostics.py`: explicit serial-scan diagnostics that cannot enter production decompilation.
- `src/uasset_read/kismet/bytecode_extractor.py`: orchestration from native Script result to expression parse result.
- `src/uasset_read/kismet/pipeline.py` and `src/uasset_read/pipeline/post_process.py`: Function-only selection, translation, and failure preservation.
- `src/uasset_read/kismet/result.py`, `src/uasset_read/models/ir.py`, `src/uasset_read/models/status.py`, `src/uasset_read/ir_builder.py`: status/error contract and package-level degradation.
- `src/uasset_read/renderers/json_renderer.py`, `src/uasset_read/renderers/markdown_renderer.py`, `schemas/package.schema.json`: identical public status and diagnostic fields.
- `tests/temp/test_issue_77_ufunction_reader.py`: synthetic native serialization coverage.
- `tests/temp/test_issue_77_kismet_archive.py`: dual-cursor, FName/FFieldPath, terminator, literal-width, and invariant coverage.
- `tests/temp/test_issue_77_pipeline_contract.py`: production-source, function classification, graph-enrichment, status, IR, renderer, and schema coverage.
- `tests/temp/test_issue_77_real_samples.py`: opt-in six-package UE 5.0-5.8 acceptance matrix.

---

### Task 1: Lock exact custom-version and export-boundary behavior

**Files:**
- Create: `src/uasset_read/kismet/ufunction_reader.py`
- Create: `tests/temp/test_issue_77_ufunction_reader.py`

**Interfaces:**
- Consumes: `FArchive`, `ByteArchive`, `ObjectExport`, `PackageFileSummary`, `read_property_tag`, `resolve_class_name`.
- Produces: `get_kismet_custom_version(summary: PackageFileSummary, serialized_guid: str) -> int`, `FunctionScriptFailure`, `FunctionScriptReadResult`, and `_read_native_payload_start(archive, export, summary, name_map, import_map, export_map) -> tuple[ByteArchive, int]`.

- [ ] **Step 1: Write failing version-key and boundary tests**

Define these exact constants and fixtures in the test:

```python
FRAMEWORK_GUID = "3f74fccf8044b043df14919373201d17"
CORE_GUID = "3cc15e37fb48e406f08400b57e712a26"
FORTNITE_GUID = "86181d60844f64acded316aad6c7ea0d"
RELEASE_GUID = "22d5549cbe4f26a846072194d082b461"

def test_custom_version_uses_serialized_guid_and_missing_is_minus_one():
    summary = make_summary(custom_versions=[CustomVersion(FRAMEWORK_GUID, 37)])
    assert get_kismet_custom_version(summary, FRAMEWORK_GUID) == 37
    assert get_kismet_custom_version(summary, CORE_GUID) == -1

def test_native_start_consumes_tags_from_serial_offset_and_cross_checks_offsets():
    payload = serialization_control_none_terminator() + b"NATIVE"
    archive, export, summary, names, imports, exports = make_function_export(payload)
    export.script_serialization_start_offset = 0
    export.script_serialization_end_offset = len(serialization_control_none_terminator())
    window, native_start = _read_native_payload_start(
        archive, export, summary, names, imports, exports,
    )
    assert native_start == export.script_serialization_end_offset
    assert window.read(6) == b"NATIVE"

def test_native_start_rejects_mismatched_script_property_offsets():
    # The None terminator is eight bytes; the declared end deliberately says seven.
    payload = fname(0, 0) + b"NATIVE"
    archive, export, summary, names, imports, exports = make_function_export(payload)
    export.script_serialization_start_offset = 0
    export.script_serialization_end_offset = 7
    result = read_ufunction_script(archive, export, summary, names, imports, exports)
    assert result.status == "failed"
    assert result.failure.error_code == "invalid_script_property_range"
```

Also add UE5 version 1011 fixtures for control byte `0x00`, control byte `0x02`
followed by one override-operation byte, and an unknown control bit. Assert the
first two align on the same `None` tag and the unknown bit returns
`unsupported_serialization_version` without entering tagged-property parsing.

The helper `make_function_export` must place the payload after 13 padding bytes, set `serial_offset=13`, and resolve class index `-1` to `ObjectImport(class_package="/Script/CoreUObject", class_name="Class", outer_index=PackageIndex(0), object_name="Function")`; this proves the implementation cannot assume export offset zero.

- [ ] **Step 2: Run the red tests**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/temp/test_issue_77_ufunction_reader.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'uasset_read.kismet.ufunction_reader'`.

- [ ] **Step 3: Implement bounded tagged-property navigation**

Implement serialized GUID constants, missing value `-1`, and these result models:

```python
@dataclass(frozen=True)
class FunctionScriptFailure:
    error_code: str
    error_message: str
    function_name: str
    export_index: int
    class_name: str
    package_offset: int
    export_offset: int
    bytecode_index: int | None = None
    bytecode_buffer_size: int | None = None
    serialized_script_size: int | None = None
    remaining_serialized: int | None = None

@dataclass
class FunctionScriptReadResult:
    status: Literal["extracted", "no_script", "failed"]
    serialized_script: bytes = b""
    bytecode_buffer_size: int = 0
    serialized_script_size: int = 0
    serialized_start: int | None = None
    native_fields: list[NativeFieldDeclaration] = field(default_factory=list)
    failure: FunctionScriptFailure | None = None
```

Use `from __future__ import annotations` so the Task 1 result model can name
`NativeFieldDeclaration` before Task 3 introduces its implementation module.

Copy exactly `serial_size` bytes from `serial_offset` into `ByteArchive`; set `_file_version_ue4` and `_file_version_ue5` on the bounded archive. For UE5 version 1011+, consume one serialization-control byte and one override-operation byte only when bit `0x02` is set. Reject other control bits with `unsupported_serialization_version`. Repeatedly call `read_property_tag`, seek to each tag's `value_end_offset`, and stop only at the `None` tag. Validate nonzero ScriptSerialization offsets against the measured `[0, native_start]` range without seeking from those offsets.

- [ ] **Step 4: Run the focused tests green**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_ufunction_reader.py -q`

Expected: all custom-version, export-boundary, serialization-control, and offset
cross-check tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add src/uasset_read/kismet/ufunction_reader.py tests/temp/test_issue_77_ufunction_reader.py
git diff --cached --check
git commit -m "fix: bound native UFunction payload reads (#77)"
```

---

### Task 2: Read the UStruct prefix and Script size header

**Files:**
- Modify: `src/uasset_read/kismet/ufunction_reader.py`
- Modify: `tests/temp/test_issue_77_ufunction_reader.py`

**Interfaces:**
- Consumes: Task 1 bounded archive and custom versions.
- Produces: `read_ufunction_script(archive, export, summary, name_map, import_map, export_map) -> FunctionScriptReadResult` for zero-property UStruct payloads; framework gate `RemoveUField_Next=29` and core gate `FProperties=4`.

- [ ] **Step 1: Add failing UStruct/header tests**

Add synthetic payload builders for this exact order:

```text
SuperStruct: int32
Children: int32 legacy pointer OR int32 count followed by count int32 pointers
NativePropertyCount: int32 when Core version >= 4
BytecodeBufferSize: int32
SerializedScriptSize: int32
SerializedScript: SerializedScriptSize bytes
```

Add assertions:

```python
def test_modern_zero_property_function_extracts_script():
    script = bytes([EExprToken.EX_EndOfScript])
    result = read_synthetic_function(
        native=modern_ustruct_prefix(property_count=0) + i32(1) + i32(1) + script,
    )
    assert result.status == "extracted"
    assert result.serialized_script == script
    assert result.bytecode_buffer_size == 1
    assert result.serialized_script_size == 1

def test_zero_zero_header_is_no_script():
    result = read_synthetic_function(
        native=modern_ustruct_prefix(property_count=0) + i32(0) + i32(0),
    )
    assert result.status == "no_script"

@pytest.mark.parametrize("buffer_size, serialized_size", [(-1, 0), (0, -1), (1, 0), (0, 1)])
def test_invalid_script_size_pairs_fail(buffer_size, serialized_size):
    result = read_synthetic_function(
        native=modern_ustruct_prefix(property_count=0) + i32(buffer_size) + i32(serialized_size),
    )
    assert result.status == "failed"
    assert result.failure.error_code == "invalid_script_size"

def test_truncated_script_reports_declared_and_remaining_sizes():
    result = read_synthetic_function(
        native=modern_ustruct_prefix(property_count=0) + i32(4) + i32(4) + b"\x53",
    )
    assert result.status == "failed"
    assert result.failure.error_code == "truncated_script"
    assert result.failure.remaining_serialized == 1
```

Also cover framework version 28 with one legacy `Children` index and framework version 29 with a two-element array. Add parameterized summaries with `file_version_ue4=398` and `file_version_licensee=-1`; both must fail before UStruct parsing with `unsupported_serialization_version`.

- [ ] **Step 2: Run the new tests red**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_ufunction_reader.py -q`

Expected: failures show that `read_ufunction_script` does not yet consume SuperStruct/Children/header fields.

- [ ] **Step 3: Implement the minimal UStruct reader**

Validate child and property counts with nonnegative bounds derived from `window.remaining() // 4`. For core versions below 4, omit native fields. For core versions 4+, accept only `property_count == 0` in this task and return `unsupported_native_field` for a positive count. Define `0/0` as `no_script`; reject negative, one-sided zero, oversized, and truncated sizes before reading bytes. Preserve package and export-relative offsets in every failure.

- [ ] **Step 4: Run Task 1-2 tests green**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_ufunction_reader.py -q`

Expected: all native-reader tests pass.

- [ ] **Step 5: Commit Task 2**

```powershell
git add src/uasset_read/kismet/ufunction_reader.py tests/temp/test_issue_77_ufunction_reader.py
git diff --cached --check
git commit -m "fix: read UFunction Script headers (#77)"
```

---

### Task 3: Deserialize base and leaf native FProperties

**Files:**
- Create: `src/uasset_read/kismet/value_types.py`
- Create: `src/uasset_read/kismet/native_fields.py`
- Modify: `src/uasset_read/kismet/ufunction_reader.py`
- Modify: `tests/temp/test_issue_77_ufunction_reader.py`

**Interfaces:**
- Consumes: bounded `ByteArchive`, name map, summary package flags, import/export maps.
- Produces: shared `FNameRef(name_index: int, number: int, base_name: str)`, `NativeFieldContext`, `NativeFieldDeclaration`, `read_native_field(archive: ByteArchive, type_name: FNameRef, context: NativeFieldContext) -> NativeFieldDeclaration`, `read_native_fields(archive: ByteArchive, count: int, context: NativeFieldContext) -> list[NativeFieldDeclaration]`, and `native_field_cpp_type(field: NativeFieldDeclaration) -> str`. `NativeFieldContext` resolves every UObject package index through the import/export maps while preserving the raw index.

- [ ] **Step 1: Add failing base/leaf field tests**

Build a serialized FProperty prefix with `NamePrivate`, optional `FlagsPrivate`, `ArrayDim`, `ElementSize`, `PropertyFlags`, zero `RepIndex`, `RepNotifyFunc`, and a one-byte replication condition only when the Release custom version is at least `PropertiesSerializeRepCondition=21`. Add a Release 20 fixture that omits that byte and a Release 21 fixture that consumes it. Assert these exact source layouts:

```python
def test_uncooked_field_reads_metadata_and_bool_layout():
    field = serialize_field(
        "BoolProperty", "Enabled", metadata={"Category": "Input"},
        tail=bytes([1, 0, 1, 1, 1, 1]),
    )
    declarations, end = read_fields_from_bytes(field, package_flags=0)
    assert declarations[0].name == "Enabled"
    assert declarations[0].metadata == {"Category": "Input"}
    assert declarations[0].type_name == "BoolProperty"
    assert end == len(field)

def test_filtered_editor_only_field_omits_field_flags():
    field = serialize_field("IntProperty", "Count", include_field_flags=False)
    declarations, end = read_fields_from_bytes(field, package_flags=PKG_FilterEditorOnly)
    assert declarations[0].name == "Count"
    assert end == len(field)

def test_object_and_class_fields_read_package_indices():
    object_field = serialize_field("ObjectProperty", "Target", tail=i32(-3))
    class_field = serialize_field("ClassProperty", "Type", tail=i32(-3) + i32(-4))
    declarations, _ = read_fields_from_bytes(object_field + class_field, count=2)
    assert declarations[0].references == [-3]
    assert declarations[0].reference_names == ["Actor"]
    assert declarations[1].references == [-3, -4]
    assert declarations[1].reference_names == ["Actor", "Pawn"]
```

Use property flags `CPF_Parm=0x80`, `CPF_OutParm=0x100`, `CPF_ReturnParm=0x400`, and `CPF_ReferenceParm=0x08000000` in a test that verifies a return field and two parameters retain their raw flags.

- [ ] **Step 2: Run the leaf tests red**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_ufunction_reader.py -q`

Expected: import of `uasset_read.kismet.native_fields` fails.

- [ ] **Step 3: Implement exact base and leaf recipes**

`NativeFieldDeclaration` must retain `type_name`, `name`, `array_dim`, `element_size`, `property_flags`, `rep_notify_name`, `replication_condition`, `metadata`, raw `references`, aligned resolved `reference_names: list[str | None]`, and `inner_fields`. Package index zero remains an explicit `None` when the UE serializer permits a null reference; specifically, a `ByteProperty` with a null Enum maps to `uint8`. A nonzero out-of-range index produces a structured native-field failure and cannot become a guessed concrete type. `native_field_cpp_type(field)` uses `reference_names` and recursively mapped inner declarations, so `StructProperty(FVector)`, `ObjectProperty(AActor)`, `EnumProperty(EType)`, and their containers remain concrete without needing archive context later.

Implement these exact recipes after the common FProperty prefix:

```text
No extra bytes: Int8, Int16, Int, Int64, UInt16, UInt32, UInt64,
                Float, Double, Name, Str, Text properties
BoolProperty: six uint8 values
ByteProperty: one int32 UObject reference
Object/WeakObject/LazyObject/SoftObjectProperty: one int32 class reference
Class/SoftClassProperty: base class reference plus one int32 meta-class reference
InterfaceProperty: one int32 interface-class reference
StructProperty: one int32 struct reference
Delegate and all MulticastDelegate variants: one int32 signature-function reference
FieldPathProperty: one serialized FName field-class name
```

For uncooked packages, read the metadata boolean and, when true, an int32 map count followed by `FName`/`FString` pairs. Reject negative or export-overrunning counts. Unknown field classes return `unsupported_native_field` without seeking.

- [ ] **Step 4: Integrate fields into the UFunction reader and run green**

Replace Task 2's positive-count failure with `read_native_fields`; return declarations in `FunctionScriptReadResult.native_fields`. Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_ufunction_reader.py -q`

Expected: all tests pass and the Script header begins immediately after the final field.

- [ ] **Step 5: Commit Task 3**

```powershell
git add src/uasset_read/kismet/value_types.py src/uasset_read/kismet/native_fields.py src/uasset_read/kismet/ufunction_reader.py tests/temp/test_issue_77_ufunction_reader.py
git diff --cached --check
git commit -m "fix: deserialize native UFunction fields (#77)"
```

---

### Task 4: Deserialize recursive container and enum fields

**Files:**
- Modify: `src/uasset_read/kismet/native_fields.py`
- Modify: `tests/temp/test_issue_77_ufunction_reader.py`

**Interfaces:**
- Consumes: Task 3 common/leaf field reader.
- Produces: recursive `SerializeSingleField` behavior for enum, array, set, map, and optional properties.

- [ ] **Step 1: Add failing nested-field tests**

Add one nested serialization fixture per recipe:

```text
EnumProperty: int32 enum reference, then FName inner-type and serialized inner field
ArrayProperty: FName inner-type and serialized inner field
SetProperty: FName element-type and serialized element field
MapProperty: key FName/field followed by value FName/field
OptionalProperty: FName value-type and serialized value field
```

Assert `TMap<FName, FString>` maps to `TMap<FName, FString>`, `TArray<FVector>` maps to `TArray<FVector>`, and `TOptional<bool>` maps to `TOptional<bool>` through `native_field_cpp_type`. Add a fixture whose inner FName is `None` and assert `unsupported_native_field` at that inner-field offset.

- [ ] **Step 2: Run nested tests red**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_ufunction_reader.py -q`

Expected: container cases stop at the first unconsumed inner-field type name.

- [ ] **Step 3: Implement recursive `SerializeSingleField`**

Implement `_read_single_field` as `FName type`; `None` returns `None`, otherwise it calls the same `read_native_field` recursively. Enforce a depth limit of 32 and return `unsupported_native_field` on a null required inner field. Map scalar/reference types to stable C++ spellings and build `TArray<>`, `TSet<>`, `TMap<, >`, and `TOptional<>` recursively.

- [ ] **Step 4: Run all native serialization tests green**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_ufunction_reader.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit Task 4**

```powershell
git add src/uasset_read/kismet/native_fields.py tests/temp/test_issue_77_ufunction_reader.py
git diff --cached --check
git commit -m "fix: read recursive native properties (#77)"
```

---

### Task 5: Add the dual-cursor archive and correct FFieldPath

**Files:**
- Modify: `src/uasset_read/kismet/archive.py`
- Modify: `src/uasset_read/kismet/property_pointer.py`
- Create: `tests/temp/test_issue_77_kismet_archive.py`

**Interfaces:**
- Consumes: serialized Script bytes, expected `bytecode_buffer_size`, summary, names, imports, exports, and Task 3's shared `FNameRef`.
- Produces: `FKismetArchive.serialized_offset`, `FKismetArchive.bytecode_index`, correct `FFieldPath`, `xfer_fname`, `xfer_object_pointer`, `xfer_field_pointer`, `xfer_code_skip`, `xfer_ansi_string`, and `xfer_unicode_string`.

- [ ] **Step 1: Add failing cursor and pointer tests**

```python
def test_object_pointer_is_four_serialized_bytes_and_eight_logical_bytes():
    ar = make_kismet_archive(i32(-3), bytecode_buffer_size=8)
    assert ar.xfer_object_pointer().index == -3
    assert ar.serialized_offset == 4
    assert ar.bytecode_index == 8

def test_fname_keeps_index_and_number():
    ar = make_kismet_archive(i32(2) + i32(7), names=["None", "A", "Move"], bytecode_buffer_size=8)
    value = ar.xfer_fname()
    assert (value.name_index, value.number, value.base_name) == (2, 7, "Move")
    assert (ar.serialized_offset, ar.bytecode_index) == (8, 8)

def test_field_path_with_owner_has_variable_disk_size_but_pointer_logical_size():
    disk = i32(2) + fname(3, 0) + fname(4, 2) + i32(5)
    ar = make_kismet_archive(disk, fortnite_version=33, bytecode_buffer_size=8)
    value = ar.xfer_field_pointer()
    assert [part.number for part in value.path] == [0, 2]
    assert value.resolved_owner.index == 5
    assert ar.serialized_offset == len(disk)
    assert ar.bytecode_index == 8
```

Add the owner-absent branch with both Fortnite and Release versions below their thresholds, an owner-present branch where Fortnite remains below 33 but Release alone is 30, plus ANSI and UTF-16 tests that prove terminators are consumed.

- [ ] **Step 2: Run cursor tests red**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_kismet_archive.py -q`

Expected: missing `serialized_offset`, `bytecode_index`, and transfer methods fail.

- [ ] **Step 3: Implement dual-cursor transfers**

Keep `tell()` as the serialized cursor for FArchive compatibility. Make primitive reads advance both cursors equally. `xfer_object_pointer` reads one int32 package index, then adds four extra logical bytes. `xfer_field_pointer` records the starting logical index, deserializes `TArray<FName>` plus the owner when Fortnite version >= 33 or Release version >= 30, then sets the logical index to `start + 8`. Remove `bNew`, `Old`, and `New`; an UE5 field pointer is a versioned FFieldPath only.

- [ ] **Step 4: Run pointer tests green**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_kismet_archive.py -q`

Expected: all cursor deltas and FFieldPath branches pass.

- [ ] **Step 5: Commit Task 5**

```powershell
git add src/uasset_read/kismet/archive.py src/uasset_read/kismet/property_pointer.py tests/temp/test_issue_77_kismet_archive.py
git diff --cached --check
git commit -m "fix: track serialized and logical Kismet offsets (#77)"
```

---

### Task 6: Correct expression transfers and consume nested terminators

**Files:**
- Modify: `src/uasset_read/kismet/expressions/assignments.py`
- Modify: `src/uasset_read/kismet/expressions/casts.py`
- Modify: `src/uasset_read/kismet/expressions/containers.py`
- Modify: `src/uasset_read/kismet/expressions/context.py`
- Modify: `src/uasset_read/kismet/expressions/delegates.py`
- Modify: `src/uasset_read/kismet/expressions/functions.py`
- Modify: `src/uasset_read/kismet/expressions/literals.py`
- Modify: `src/uasset_read/kismet/expressions/special.py`
- Modify: `src/uasset_read/kismet/expressions/string_consts.py`
- Modify: `src/uasset_read/kismet/expressions/structs.py`
- Modify: `src/uasset_read/kismet/expressions/variables.py`
- Modify: `src/uasset_read/kismet/archive.py`
- Modify: `tests/temp/test_issue_77_kismet_archive.py`

**Interfaces:**
- Consumes: Task 5 transfer methods.
- Produces: source-backed operand transfers and `read_expression_array(end_token)` that consumes but does not return its terminator.

- [ ] **Step 1: Add failing virtual/final call and terminator tests**

Serialize these two exact streams:

```python
virtual = token(EX_VirtualFunction) + fname(2, 0) + token(EX_IntOne) + token(EX_EndFunctionParms)
final = token(EX_FinalFunction) + i32(-4) + token(EX_True) + token(EX_EndFunctionParms)
```

Assert the virtual name is resolved from FName, the final function pointer adds eight logical bytes, each call has one parameter, `EX_EndFunctionParms` is not in the returned child list, and the next serialized/logical position is immediately after the terminator. Add nested array/map terminator tests and string tests with no caller-side `skip`.

- [ ] **Step 2: Run expression tests red**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_kismet_archive.py -q`

Expected: virtual calls misread FString data and terminators leak to the outer stream.

- [ ] **Step 3: Replace raw reads with the source transfer table**

Apply this exact mapping:

```text
Function/delegate names and EX_NameConst -> xfer_fname
Function/class/struct/object references -> xfer_object_pointer
Property references in let/variable/context/container expressions -> xfer_field_pointer
Jump/skip operands -> xfer_code_skip
ASCII and UTF-16 literals -> consuming string transfer methods
All primitive integer/float operands -> normal reads with equal cursor advance
```

Rewrite `read_expression_array` to call `read_expression` until the returned token equals the requested terminator; do not peek, seek backward, or append the terminator. Remove all null-terminator `skip` calls. Preserve `FNameRef` raw values on expressions while keeping resolved string fields used by the translator.

- [ ] **Step 4: Run Task 5-6 tests green**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_kismet_archive.py -q`

Expected: all pointer, call, nested terminator, and string tests pass.

- [ ] **Step 5: Commit Task 6**

```powershell
git add src/uasset_read/kismet/archive.py src/uasset_read/kismet/expressions src/uasset_read/kismet/property_pointer.py tests/temp/test_issue_77_kismet_archive.py
git diff --cached --check
git commit -m "fix: mirror Kismet expression transfers (#77)"
```

---

### Task 7: Enforce Script invariants, logical jumps, and LWC widths

**Files:**
- Modify: `src/uasset_read/kismet/archive.py`
- Modify: `src/uasset_read/kismet/bytecode_extractor.py`
- Modify: `src/uasset_read/kismet/expressions/control_flow.py`
- Modify: `src/uasset_read/kismet/expressions/rtfm.py`
- Modify: `src/uasset_read/kismet/expressions/special.py`
- Modify: `src/uasset_read/kismet/expressions/vector_consts.py`
- Modify: `tests/temp/test_issue_77_kismet_archive.py`

**Interfaces:**
- Consumes: expected physical/logical sizes and parsed expression tree.
- Produces: strict `parse_bytecode_stream(serialized_script: bytes, name_map: list[str], summary: PackageFileSummary, import_map: list[ObjectImport], export_map: list[ObjectExport], *, bytecode_buffer_size: int, tolerant: bool = False) -> list[KismetExpression]`, absolute control-flow validation, and versioned vector/rotation/transform constants.

- [ ] **Step 1: Add failing size/end/jump/version tests**

Add parameterized failures for:

```text
physical bytes remain -> serialized_size_mismatch
logical index smaller/larger than BytecodeBufferSize -> bytecode_size_mismatch
last top-level token is not EX_EndOfScript -> missing_end_of_script
EX_Jump/EX_JumpIfNot/EX_PushExecutionFlow/Switch/AutoRtfm target is not a top-level StatementIndex -> invalid_jump_target
unknown byte 0x6E, 0x6F, 0xF9, 0xFD, 0xFE, or 0xFF -> unknown_expr_token
```

Run each unknown-token case through strict `parse_bytecode_stream` and tolerant `decompile_single_function`; strict raises a coded error and the tolerant pipeline returns a failed function result with the same physical/logical offsets. Add UE5 pre-LWC float fixtures and UE5 LWC double fixtures for vector, rotation, and ten-component transform values; `EX_Vector3fConst` always consumes three floats.
Add successful control-flow fixtures for a forward jump, backward loop edge,
and a jump to the top-level `EX_EndOfScript` statement index so validation does
not reject legal targets.

- [ ] **Step 2: Run invariant tests red**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_kismet_archive.py -q`

Expected: current tolerant parsing skips unknown bytes, `EX_Max` is accepted, and all vector constants use floats.

- [ ] **Step 3: Implement strict closure and logical-target validation**

Stop top-level parsing immediately after `EX_EndOfScript`, then require serialized cursor equality and logical cursor equality. Remove private placeholder expression registrations and the EX_Max end marker. Validate absolute branch targets against the set of top-level `StatementIndex` values. Keep relative Context/Skip lengths separate from absolute jump targets. Read vector/rotation/transform components as doubles when `summary.file_version_ue5 >= UE5_LARGE_WORLD_COORDINATES` (`1004` from `uasset_read.constants`); keep Vector3f float.

- [ ] **Step 4: Run all archive/expression tests green**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_kismet_archive.py -q`

Expected: all closure, target, unknown-token, and literal-width tests pass.

- [ ] **Step 5: Commit Task 7**

```powershell
git add src/uasset_read/kismet/archive.py src/uasset_read/kismet/bytecode_extractor.py src/uasset_read/kismet/expressions tests/temp/test_issue_77_kismet_archive.py
git diff --cached --check
git commit -m "fix: validate complete Kismet Script streams (#77)"
```

---

### Task 8: Remove production heuristics and select only Function exports

**Files:**
- Create: `src/uasset_read/kismet/diagnostics.py`
- Modify: `src/uasset_read/kismet/bytecode_extractor.py`
- Modify: `src/uasset_read/kismet/pipeline.py`
- Modify: `src/uasset_read/kismet/__init__.py`
- Modify: `src/uasset_read/pipeline/post_process.py`
- Delete: `src/uasset_read/kismet/bpgc_bytecode.py`
- Modify: `tests/temp/test_decompiled_function_provenance.py`
- Create: `tests/temp/test_issue_77_pipeline_contract.py`

**Interfaces:**
- Consumes: `read_ufunction_script`, strict parse result, existing body builder/linker.
- Produces: `FUNCTION_EXPORT_CLASSES = frozenset({"Function", "UFunction"})`, native-only `extract_and_parse`, and `scan_function_export_for_diagnostics(archive, export, summary, name_map, import_map, export_map) -> list[BytecodeCandidateDiagnostic]`.

- [ ] **Step 1: Add failing production-source and classification tests**

```python
def test_only_true_function_exports_are_decompiled(monkeypatch):
    exports = [make_export("Function", "Real"), make_export("K2Node_FunctionEntry", "Entry")]
    results = run_post_process_kismet(exports, monkeypatch)
    assert [item.function_name for item in results] == ["Real"]

def test_production_result_never_uses_bpgc_or_serial_scan():
    result = decompile_synthetic_native_function()
    assert result.bytecode_source == "function_export"
    assert "bpgc_bytecode_extraction" not in result.fallback_reasons
    assert "serial_scan_recovery" not in result.fallback_reasons

def test_diagnostic_scan_result_cannot_become_decompiled_result():
    archive, export, summary, names, imports, exports = diagnostic_fixture()
    candidates = scan_function_export_for_diagnostics(
        archive, export, summary, names, imports, exports,
    )
    assert all(isinstance(item, BytecodeCandidateDiagnostic) for item in candidates)
    assert not any(isinstance(item, KismetDecompiledResult) for item in candidates)
```

Replace provenance tests that expect `fallback_or_serial_scan`, `bpgc_bytecode_extraction`, or `serial_scan_recovery` with assertions that these values are absent from production enums and output.

- [ ] **Step 2: Run pipeline tests red**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/temp/test_issue_77_pipeline_contract.py tests/temp/test_decompiled_function_provenance.py -q
```

Expected: K2Node pseudo-functions remain selected and heuristic provenance values are still produced.

- [ ] **Step 3: Replace extraction orchestration and isolate diagnostics**

Make `extract_and_parse` return native `no_script`, native failure, expression failure, or parsed expressions without calling any fallback. Move the bounded candidate scanner to `diagnostics.py`; its dataclass contains only start/end offsets, expression count, and validation error. Remove BPGC cache globals, retries, reset calls, public exports, ordinal mapping, and the BPGC module. Update both standalone and post-process loops to filter exactly `Function/UFunction` and to retain one result for every such export, including `no_script` and `failed`.

- [ ] **Step 4: Run classification/provenance tests green**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_pipeline_contract.py tests/temp/test_decompiled_function_provenance.py -q`

Expected: only Function exports appear and production provenance is native-only.

- [ ] **Step 5: Commit Task 8**

```powershell
git add src/uasset_read/kismet src/uasset_read/pipeline/post_process.py tests/temp/test_decompiled_function_provenance.py tests/temp/test_issue_77_pipeline_contract.py
git diff --cached --check
git commit -m "fix: remove heuristic function bytecode mapping (#77)"
```

---

### Task 9: Propagate bytecode, translation, and failure status consistently

**Files:**
- Modify: `src/uasset_read/kismet/result.py`
- Modify: `src/uasset_read/kismet/pipeline.py`
- Modify: `src/uasset_read/kismet/semantic.py`
- Modify: `src/uasset_read/models/ir.py`
- Modify: `src/uasset_read/models/status.py`
- Modify: `src/uasset_read/ir_builder.py`
- Modify: `src/uasset_read/renderers/json_renderer.py`
- Modify: `src/uasset_read/renderers/markdown_renderer.py`
- Modify: `schemas/package.schema.json`
- Modify: `tests/temp/test_decompiled_function_provenance.py`
- Modify: `tests/temp/test_issue_77_pipeline_contract.py`

**Interfaces:**
- Consumes: native extraction/parse/translation outcomes.
- Produces: `bytecode_status = parsed | no_script | failed`, `translation_status = complete | partial | failed | not_applicable`, `error_code`, `error_message`, `error_context`, and `script_metrics` in internal result, IR, JSON, Markdown, and schema.

- [ ] **Step 1: Add failing status propagation tests**

Create one result for each allowed pair and assert the full projection:

```python
ALLOWED = {
    ("parsed", "complete"),
    ("parsed", "partial"),
    ("parsed", "failed"),
    ("no_script", "not_applicable"),
    ("failed", "not_applicable"),
}

def test_function_status_round_trips_through_ir_json_markdown_and_schema():
    result = make_failed_function(
        error_code="unknown_expr_token",
        error_message="Unknown EExprToken 0x6E",
        error_context={"package_offset": 120, "export_offset": 20, "bytecode_index": 8},
    )
    ir = build_ir_with_function(result)
    options = RenderOptions(output_level="standard")
    rendered = json.loads(JSONRenderer().render(ir, options))
    function = rendered["decompiled_functions"][0]
    assert (function["bytecode_status"], function["translation_status"]) == ("failed", "not_applicable")
    assert function["error_code"] == "unknown_expr_token"
    assert "unknown_expr_token" in MarkdownRenderer().render(ir, options)
    schema = json.loads(Path("schemas/package.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(rendered, schema)
```

Add package-status tests: any `failed`, `parsed+partial`, or `parsed+failed` function yields package `partial`; only `no_script+not_applicable` remains neutral. Add rejection tests for every status pair outside `ALLOWED`. Define `script_metrics` precisely: `no_script` exposes declared zero sizes and zero consumed counts; a failure before the Script header uses `null` for all four metrics; a failure after the header preserves declared sizes and uses consumed counts up to the failure. Assert those forms in Python, JSON, Markdown, and Schema. Add a semantic enrichment test where graph topology fills `cpp_code` on a failed function but status stays `failed/not_applicable` and `logic_source` becomes `graph_topology`. Import `json`, `jsonschema`, `Path`, and `RenderOptions` explicitly in the test module; schema validation must execute rather than being represented by a helper stub.

- [ ] **Step 2: Run status tests red**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/temp/test_issue_77_pipeline_contract.py tests/temp/test_decompiled_function_provenance.py -q
```

Expected: `translation_status` and structured error fields are missing, and package status ignores native function failure.

- [ ] **Step 3: Implement the unified function status contract**

Add the five public fields to `KismetDecompiledResult` and `DecompiledFunctionIR`, serialize them in both renderers, and define schema enums exactly. `script_metrics` contains `bytecode_buffer_size`, `serialized_script_size`, `serialized_bytes_consumed`, and `bytecode_bytes_consumed`. Translation is `complete` when code generation has no unsupported construct, `partial` when it emits an explicit unsupported construct, `failed` when translation raises, and `not_applicable` when bytecode is not parsed. Remove heuristic confidence branches; confidence becomes `verified`, `no_script`, `failed`, or `graph_topology`.

Update `_result_status` to return `partial` when any decompiled function is failed or has partial/failed translation. Replace `HEURISTIC_BYTECODE_RECOVERY` with `KISMET_PARTIAL` in IR diagnostics and include failed/partial counts. Ensure graph enrichment changes only `cpp_code`, semantic calls, and `logic_source`.

- [ ] **Step 4: Run status/output tests green**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_pipeline_contract.py tests/temp/test_decompiled_function_provenance.py -q`

Expected: all allowed pairs round-trip, graph enrichment preserves status, and schema validation passes.

- [ ] **Step 5: Commit Task 9**

```powershell
git add src/uasset_read/kismet/result.py src/uasset_read/kismet/pipeline.py src/uasset_read/kismet/semantic.py src/uasset_read/models/ir.py src/uasset_read/models/status.py src/uasset_read/ir_builder.py src/uasset_read/renderers schemas/package.schema.json tests/temp/test_decompiled_function_provenance.py tests/temp/test_issue_77_pipeline_contract.py
git diff --cached --check
git commit -m "fix: expose verified function parse status (#77)"
```

---

### Task 10: Use native fields for signatures and parameter binding

**Files:**
- Modify: `src/uasset_read/kismet/native_fields.py`
- Modify: `src/uasset_read/kismet/result.py`
- Modify: `src/uasset_read/kismet/pipeline.py`
- Modify: `src/uasset_read/ir_builder.py`
- Modify: `tests/temp/test_issue_77_pipeline_contract.py`

**Interfaces:**
- Consumes: `FunctionScriptReadResult.native_fields` and property flags.
- Produces: `build_native_function_signature(function_name, fields) -> tuple[str, list[dict[str, object]], str]`.

- [ ] **Step 1: Add failing signature tests**

Construct fields `ReturnValue: BoolProperty` with `CPF_Parm|CPF_ReturnParm`, `Yaw: FloatProperty` with `CPF_Parm`, and `Target: ObjectProperty` with `CPF_Parm|CPF_OutParm|CPF_ReferenceParm`. Assert:

```python
signature, parameters, return_type = build_native_function_signature("Aim", fields)
assert signature == "bool Aim(float Yaw, UObject*& Target)"
assert return_type == "bool"
assert parameters == [
    {"name": "Yaw", "param_type": "float", "is_input": True, "is_output": False},
    {"name": "Target", "param_type": "UObject*&", "is_input": True, "is_output": True},
]
```

Add an array/map signature test and verify IR uses these structured parameters instead of reparsing a graph-derived string.

- [ ] **Step 2: Run signature tests red**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_pipeline_contract.py -q`

Expected: the pipeline still derives an empty `void Function()` signature from generated code.

- [ ] **Step 3: Build signatures from native property flags**

Select fields with `CPF_Parm`; separate `CPF_ReturnParm`; add `&` for `CPF_ReferenceParm`, preserve `const` for `CPF_ConstParm`, and mark `is_output` for `CPF_OutParm`. Add `parameters: list[dict[str, object]]` and `return_type: str` to `KismetDecompiledResult`, then pass the signature, parameters, and return type directly into IR instead of reparsing the signature string. Do not use graph pins to claim native parameter metadata.

- [ ] **Step 4: Run signature and pipeline contract tests green**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_pipeline_contract.py -q`

Expected: native parameters and return type survive into IR.

- [ ] **Step 5: Commit Task 10**

```powershell
git add src/uasset_read/kismet/native_fields.py src/uasset_read/kismet/result.py src/uasset_read/kismet/pipeline.py src/uasset_read/ir_builder.py tests/temp/test_issue_77_pipeline_contract.py
git diff --cached --check
git commit -m "fix: derive Blueprint signatures from native fields (#77)"
```

---

### Task 11: Prove the six-package real-sample matrix and close out

**Files:**
- Create: `tests/temp/test_issue_77_real_samples.py`
- Conditional modify after a focused red test and UE source verification only: the exact owning module already scoped by Tasks 1-10 (including native fields, archive/pointers, expression, bytecode extraction, CFG/translation, pipeline/status/output) and its focused Issue #77 regression file.
- Verify: all files changed in Tasks 1-10

**Interfaces:**
- Consumes: public parse API, raw parsed function graphs before Kismet post-processing, and `E:/Develop/lib/Samples`.
- Produces: real-output proof for 76 true Function exports across UE 5.0, 5.2, 5.6, 5.7, and 5.8, plus independent node-graph/Script semantic parity for every user-authored function graph.

- [ ] **Step 1: Add the opt-in real-sample matrix**

Use this exact table:

```python
SAMPLES = [
    ("LyraStarterGame/Content/Characters/Heroes/Abilities/GA_Hero_Jump.uasset", 7),
    ("CropoutSampleProject/Content/Blueprint/Villagers/BP_Villager.uasset", 30),
    ("FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset", 12),
    ("StackOBot/Content/StackOBot/Blueprints/GameElements/BP_MovingPlatform.uasset", 8),
    ("GameAnimationSample/Content/Blueprints/Data/BFL_HelpfulFunctions.uasset", 10),
    ("FirstPersonC/Content/Variant_Shooter/Blueprints/BP_ShooterCharacter.uasset", 9),
]
```

Default the sample root to `E:/Develop/lib/Samples` and skip only when that root is absent. For each package, independently resolve Function/UFunction export names from the parsed export map and assert exact equality with public `decompiled_functions` names/count. Assert every result has `bytecode_source == "function_export"`, status in the allowed pair set, no `failed`, no parsed partial/failed translation, exact serialized/logical closure metadata, and no K2Node pseudo-function.

Before invoking Kismet post-processing, derive a `GraphSemanticFingerprint` from each raw user-authored function graph using only node classes, member/variable references, literal and default-pin values, pin direction, and exec/data links. Derive a separate `ScriptSemanticFingerprint` from the native expression tree and CFG using only expressions and statement edges. For every user-authored function graph, require exactly one Function result and assert that every reachable graph call, variable read/write, branch, return, and literal is represented in the Script fingerprint with compatible data-flow connectivity. The graph oracle must not import the translator, read `cpp_code`, or consume semantic-enrichment output. Report counts for user-authored graphs compared, generated functions without source graphs, and all mismatches; an allowlist requires a named UE compiler transformation and a focused fixture.

For FirstPerson assert `Aim` contains `AddControllerYawInput(Yaw)` and `AddControllerPitchInput(Pitch)`; `Move` contains `AddMovementInput(GetActorRightVector(), Left__Right, false)` and `AddMovementInput(GetActorForwardVector(), Forward__Backward, false)`. Across all samples reject `Property_-7`, `Property_23265280`, `Unknown_`, `fallback_or_serial_scan`, `bpgc_bytecode_extraction`, and `serial_scan_recovery` in the rendered JSON.

- [ ] **Step 2: Run the matrix early and close every source-backed coverage gap with TDD**

Run the real matrix before final verification. For each `unsupported_native_field`, `unknown_expr_token`, size/closure error, or semantic-oracle mismatch: stop at the first exact failure; locate the owning serializer or compiler transformation in `E:/Develop/lib/UnrealEngine`; add the smallest synthetic failing test to the corresponding Task 1-10 owning focused suite; implement only the verified layout/translation; rerun that focused test and the complete matrix. Repeat until the matrix has zero native, expression, closure, translation, and oracle failures. Do not add guessed byte skips, generic exception suppression, or broad semantic allowlists.

Run after each focused green test: `$env:PYTHONPATH='src'; python -m pytest tests/temp/test_issue_77_real_samples.py -q -s`

After each gap is green in both its focused suite and the matrix, commit only
the conditional tracked source/test changes before continuing the loop:

```powershell
$issue77GapFiles = @(git diff --name-only -- src/uasset_read/kismet src/uasset_read/pipeline/post_process.py src/uasset_read/ir_builder.py src/uasset_read/models src/uasset_read/renderers schemas/package.schema.json tests/temp/test_issue_77_ufunction_reader.py tests/temp/test_issue_77_kismet_archive.py tests/temp/test_issue_77_pipeline_contract.py tests/temp/test_decompiled_function_provenance.py)
if ($issue77GapFiles.Count -eq 0) { throw "No tracked Issue 77 coverage-gap changes found" }
$issue77GapFiles | ForEach-Object { Write-Output $_ }
git add -- $issue77GapFiles
git diff --cached --check
git diff --cached --name-only
git commit -m "fix: cover source-backed UFunction serialization gap (#77)"
```

Before `git add`, inspect the printed names and stop if any path is outside the
single source-backed gap, its exact Task 1-10 owning module, and its focused
regression. The broad path arguments only discover modified candidates; the
printed list is the mandatory exact staging review.

- [ ] **Step 3: Run all Issue #77 tests**

```powershell
$env:PYTHONPATH='src'
python -c "import uasset_read; print(uasset_read.__file__)"
python -m pytest tests/temp/test_issue_77_ufunction_reader.py tests/temp/test_issue_77_kismet_archive.py tests/temp/test_issue_77_pipeline_contract.py tests/temp/test_decompiled_function_provenance.py -q
python -m pytest tests/temp/test_issue_77_real_samples.py -q -s
```

Expected: the import path begins with `E:\Develop\uasset_read\.worktrees\issue-77-ufunction-script\src`; all focused tests pass; the matrix reports 76 Function exports with no native/translation failure, every user-authored function graph is compared exactly once, and there are zero semantic-oracle mismatches.

- [ ] **Step 4: Run repository-wide verification**

```powershell
$env:PYTHONPATH='src'
python -m pytest -q
python -m ruff check src tests
python -m compileall -q src
git diff --check
```

Expected: the 87 root baseline tests pass, the explicitly run `tests/temp/` Issue #77 suites pass, Ruff and compileall exit zero, and the diff has no whitespace errors.

- [ ] **Step 5: Commit the real-sample acceptance test and prepare review evidence**

```powershell
git add tests/temp/test_issue_77_real_samples.py
git diff --cached --check
git commit -m "test: verify native UFunction scripts across UE5 (#77)"
```

Step 2 must leave no uncommitted coverage-gap implementation. Record branch/HEAD, focused test totals, full-suite totals, the 76-export matrix summary, graph-oracle compared/generated/mismatch counts, and named Aim/Move/Shooter assertions. Run `git status --short --branch` and `git log --oneline --decorate -12`; do not close Issue #77 until an independent spec review and code-quality review both approve the diff and the real matrix is rerun after any review fix.
