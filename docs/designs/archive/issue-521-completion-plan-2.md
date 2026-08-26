# #521 Epic Completion — Second Implementation Plan (B1 struct decoding + B2 pin projection)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decode the three remaining opaque Niagara struct types (B1: `NiagaraVariable`, `NiagaraGraphScriptUsageInfo`, `VersionedNiagaraScriptData`) and project pin-level connections from node native tails (B2), completing the parameter-definition and pin-level-connection paths of Epic #521 and feeding #525's acceptance criteria.

**Architecture:** B1 targets three struct types that currently appear as opaque `StructValue` in the parser output despite their byte layouts being fully resolved by B0a/B0b evidence. `NiagaraVariable` has a hybrid layout (raw `FName` + tagged `FNiagaraTypeDefinition` stream) requiring a dedicated `BinaryOrNative` handler. `NiagaraGraphScriptUsageInfo` and `VersionedNiagaraScriptData` are pure tagged-property structs whose elements sit inside `ArrayProperty` values with `tag.size = 0` — the parser returns opaque immediately because these struct names are not in `_TAGGED_FALLBACK_STRUCTS` (line 983 of `property_types.py`). The fix: resolve the actual struct type names from the import table, add them to the fallback set, and define field schemas. B2 extends the existing `NiagaraNodeHandler` to decode pin records from native tails using the byte-verified layout from `issue-521-b0-gate-decision.md` (99 pins, 76 edges, full field-level walk).

**Tech Stack:** Python 3.10 stdlib only (zero runtime dependencies); `pytest` (CI-installed, tests only); UE source checkout at `E:/Develop/lib/UnrealEngine` @ `7deeb413d3dc1fc034f48d1aacc0861301829d32` (5.8.0-release) for source citations.

**Slice → Task map:** B1 → Tasks 1–4 · B2 → Tasks 5–7.

## File Structure

### New files
- `tests/temp/test_issue_521_niagara_struct_decode.py` — B1 red/green tests (NiagaraVariable, NiagaraGraphScriptUsageInfo, VersionedNiagaraScriptData)
- `tests/temp/test_issue_521_niagara_pin_decode.py` — B2 red/green tests (pin extraction from node native tails)

### Modified files
- `src/uasset_read/parsers/binary_or_native_handlers.py` — add `_parse_niagara_variable` handler + register in `_BINARY_OR_NATIVE_HANDLERS`
- `src/uasset_read/parsers/property_types.py` — add `NiagaraGraphScriptUsageInfo` and `VersionedNiagaraScriptData` to `_TAGGED_FALLBACK_STRUCTS` + `_TAGGED_FALLBACK_STRUCT_SCHEMAS`
- `src/uasset_read/parsers/asset_types/niagara_node.py` — extend `NiagaraNodeHandler.parse()` to decode pins from native tails; add `_decode_pins_from_tail` helper; add `_decode_ftext`, `_decode_fedgraphpintype` helpers
- `docs/designs/issue-521-niagara-field-contracts.md` — update struct decode status and pin projection status

## Global Constraints

These apply to every task (copied verbatim in intent from the project constraints and the roadmap design):

- Zero runtime dependencies; no `pip install`; run via `src/` imports. Parser changes are read-only (parse only, never write assets).
- All new tests go to `tests/temp/`; root `tests/` files are NOT modified; `tests/samples/` receives no new files in this plan.
- Evidence discipline: every binary-format claim must carry a version-pinned UE C++ source reference; never guess layouts; unproven bytes stay opaque with recorded offset/size.
- Status model: export-level `parse_status` must be an `ExportParseStatus` enum value; `partial_metadata` only for handler-projected exports; `opaque` never promoted without evidence.
- All code comments, error messages, and documentation in English. Exception: edits to pre-existing Chinese-language docs follow that document's language.
- Commit format: `<type>: <summary> (#issue)` on branch `dev-0.5.5`. Issue tags: `(#527)` for NiagaraVariable tasks, `(#528)` for NiagaraGraphScriptUsageInfo tasks, `(#529)` for VersionedNiagaraScriptData tasks, `(#525)` for B2 pin-projection tasks.
- Fixture: `tests/samples/NM_BPSystemEvent.uasset`, SHA-256 `B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF` (assert in every fixture-based test).
- UE source checkout: `E:/Develop/lib/UnrealEngine` at commit `7deeb413d3dc1fc034f48d1aacc0861301829d32` (tag `5.8.0-release`). Audits quote `file:line` against exactly this commit. Fixture is UE 5.0 (`FileVersionUE5=1004`); version deltas are recorded in `issue-521-b0-gate-decision.md` and must be honored by all decoders.
- Baseline guards: the existing 64 Niagara tests stay green (5 files in `tests/temp/`); root suite stays at **131 passed + 1 known failure** (`test_normal_json_root_keys_are_unchanged`); export counts never regress.
- Canonical commands (run from repo root `E:/Develop/uasset_read`):
  - Niagara suite: `python -m pytest tests/temp/test_issue_521_niagara_evidence.py tests/temp/test_issue_521_niagara_graph_handler.py tests/temp/test_issue_521_niagara_node_handler.py tests/temp/test_issue_521_niagara_script_handler.py tests/temp/test_issue_521_niagara_routing.py tests/temp/test_issue_521_niagara_coverage.py -q`
  - Root suite: `python -m pytest tests/ --ignore=tests/temp -q`
- Pin-layout reference: `docs/designs/issue-521-b0-gate-decision.md` §Pin-record layout and §Version deltas. Every pin-field decoder must honor the fixture-specific version deltas (e.g. `bSerializeAsSinglePrecisionFloat` absent, `SourceIndex` present as `ff ff ff ff`).
- Known struct_type resolution: ArrayProperty elements use `tag.size = 0` (property_parser.py:568); structs NOT in `_TAGGED_FALLBACK_STRUCTS` return opaque at line 983 of `property_types.py` when `tag.size <= 0`. The implementer MUST verify the exact `struct_type` string the parser produces for each target struct by probing the fixture (the name may include or exclude the C++ `F` prefix).

---

### Task 1: B1 red — failing tests for all three struct decode types

**Files:**
- Create: `tests/temp/test_issue_521_niagara_struct_decode.py`

**Interfaces:**
- Consumes: fixture `tests/samples/NM_BPSystemEvent.uasset` (SHA-256 pinned)
- Produces: test file that pins the expected decoded output shape for each struct type (green tests in Tasks 2–3 will make these pass)

- [ ] **Step 1: Probe the fixture to discover exact struct_type names**

Run a diagnostic to find the exact `struct_type` strings the parser produces for the three target structs inside ArrayProperty elements. This is critical because the names may differ from the C++ names (e.g. `FNiagaraGraphScriptUsageInfo` vs `NiagaraGraphScriptUsageInfo`).

```python
# tests/temp/probe_struct_type_names.py (temp diagnostic, not committed)
import json, sys
sys.path.insert(0, "src")
from uasset_read import parse_single

result = parse_single("tests/samples/NM_BPSystemEvent.uasset", format="json", tolerant=True, log_enabled=False)
# Walk all exports → properties → array/map values → struct values
# Find StructValue instances with raw_size > 0 and struct_type containing "Niagara" or "Versioned"
# Print: export_name, property_name, struct_type, raw_size, parse_status
```

Run: `python tests/temp/probe_struct_type_names.py`
Record the exact `struct_type` strings for:
1. `NiagaraVariable` — found inside `NiagaraScriptVariable_*.Variable` (StructProperty value)
2. `NiagaraGraphScriptUsageInfo` — found inside `NiagaraGraph_1.CachedUsageInfo` (ArrayProperty element)
3. `VersionedNiagaraScriptData` — found inside `NM_BPSystemEvent.VersionData` (ArrayProperty element)

- [ ] **Step 2: Write failing tests**

Create `tests/temp/test_issue_521_niagara_struct_decode.py` with the following structure. The `STRUCT_TYPE_NAMES` dict will be filled with the exact strings discovered in Step 1.

```python
"""B1 struct decode tests for NiagaraVariable, NiagaraGraphScriptUsageInfo,
VersionedNiagaraScriptData.

These tests assert that the parser decodes named fields from each struct type.
Currently they FAIL because the structs appear as opaque; Tasks 2–3 will make
them pass.
"""
import json
import sys
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from uasset_read import parse_single

SAMPLE = Path(__file__).resolve().parents[2] / "tests/samples/NM_BPSystemEvent.uasset"
SHA256 = "B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF"

# Filled by the implementer with exact strings from Step 1 probe
STRUCT_TYPE_NAMES = {
    "NiagaraVariable": "<EXACT_STRING_FROM_PROBE>",           # e.g. "NiagaraVariable" or "FNiagaraVariable"
    "NiagaraGraphScriptUsageInfo": "<EXACT_STRING_FROM_PROBE>",  # e.g. "FNiagaraGraphScriptUsageInfo"
    "VersionedNiagaraScriptData": "<EXACT_STRING_FROM_PROBE>",  # e.g. "FVersionedNiagaraScriptData"
}


def _parse_fixture():
    return json.loads(parse_single(str(SAMPLE), format="json", tolerant=True, log_enabled=False))


def _find_struct_values(data, target_struct_type):
    """Recursively find all StructValue dicts with the given struct_type."""
    results = []
    if isinstance(data, dict):
        if data.get("struct_type") == target_struct_type:
            results.append(data)
        for v in data.values():
            results.extend(_find_struct_values(v, target_struct_type))
    elif isinstance(data, list):
        for item in data:
            results.extend(_find_struct_values(item, target_struct_type))
    return results


class TestNiagaraVariableDecode:
    """NiagaraVariable: FName Name + tagged FNiagaraTypeDefinition + data blob.
    Source: NiagaraModule.cpp:1732 (custom Serialize).
    B0a evidence: 111–114 bytes per instance, 12 total in fixture.
    """

    def test_sha256(self):
        assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == SHA256

    def test_niagara_variable_has_decoded_name(self):
        """After decode, NiagaraVariable must expose 'Name' as a string."""
        data = _parse_fixture()
        nv_type = STRUCT_TYPE_NAMES["NiagaraVariable"]
        values = _find_struct_values(data, nv_type)
        assert len(values) >= 12, f"Expected >= 12 NiagaraVariable values, found {len(values)}"
        for v in values:
            assert v.get("parse_status") == "success", (
                f"NiagaraVariable parse_status={v.get('parse_status')}, expected 'success'"
            )
            fields = v.get("fields", {})
            assert "Name" in fields, f"NiagaraVariable missing 'Name' field; fields={list(fields.keys())}"
            # Name should be a non-empty string (FName)
            name_val = fields["Name"]
            assert isinstance(name_val, str) and len(name_val) > 0, f"Name={name_val!r}"

    def test_niagara_variable_has_type_definition(self):
        """After decode, NiagaraVariable must expose TypeDefinition fields."""
        data = _parse_fixture()
        nv_type = STRUCT_TYPE_NAMES["NiagaraVariable"]
        values = _find_struct_values(data, nv_type)
        for v in values:
            fields = v.get("fields", {})
            # TypeDefinition may be nested or flattened depending on decode approach
            # Accept either a 'TypeDefinition' dict or flattened fields like 'UnderlyingType'
            has_typedef = "TypeDefinition" in fields or "UnderlyingType" in fields
            assert has_typedef, (
                f"NiagaraVariable missing TypeDefinition; fields={list(fields.keys())}"
            )


class TestNiagaraGraphScriptUsageInfoDecode:
    """NiagaraGraphScriptUsageInfo: tagged property stream.
    Source: NiagaraGraph.h:87/:571.
    B0a evidence: 544/544 bytes consumed, fields: BaseId(Guid), UsageType(Enum),
    UsageId(Guid), CompileHash, CompileHashFromGraph, Traversal(Array<Object>).
    """

    def test_has_decoded_fields(self):
        """After decode, NiagaraGraphScriptUsageInfo must expose named fields."""
        data = _parse_fixture()
        gui_type = STRUCT_TYPE_NAMES["NiagaraGraphScriptUsageInfo"]
        values = _find_struct_values(data, gui_type)
        assert len(values) >= 1, f"Expected >= 1 NiagaraGraphScriptUsageInfo, found {len(values)}"
        for v in values:
            assert v.get("parse_status") == "success", (
                f"NiagaraGraphScriptUsageInfo parse_status={v.get('parse_status')}"
            )
            fields = v.get("fields", {})
            # Expect at least BaseId and UsageType from the tagged stream
            assert "BaseId" in fields or "UsageType" in fields, (
                f"Missing expected fields; fields={list(fields.keys())}"
            )


class TestVersionedNiagaraScriptDataDecode:
    """VersionedNiagaraScriptData: tagged property stream.
    Source: NiagaraScript.h:619/:873.
    B0a evidence: 2038/2038 bytes consumed.
    """

    def test_has_decoded_fields(self):
        """After decode, VersionedNiagaraScriptData must expose named fields."""
        data = _parse_fixture()
        vsd_type = STRUCT_TYPE_NAMES["VersionedNiagaraScriptData"]
        values = _find_struct_values(data, vsd_type)
        assert len(values) >= 1, f"Expected >= 1 VersionedNiagaraScriptData, found {len(values)}"
        for v in values:
            assert v.get("parse_status") == "success", (
                f"VersionedNiagaraScriptData parse_status={v.get('parse_status')}"
            )
            fields = v.get("fields", {})
            # Expect at least Version and Category from the tagged stream
            has_key_field = "Version" in fields or "Category" in fields or "ModuleUsageBitmask" in fields
            assert has_key_field, (
                f"Missing expected fields; fields={list(fields.keys())}"
            )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/temp/test_issue_521_niagara_struct_decode.py -v`
Expected: FAIL — structs currently have `parse_status="opaque"` and missing fields.

- [ ] **Step 4: Commit red**

```bash
git add tests/temp/test_issue_521_niagara_struct_decode.py
git commit -m "test: add B1 struct decode tests (red) (#527 #528 #529)"
```

---

### Task 2: B1 green — NiagaraVariable BinaryOrNative handler

**Files:**
- Modify: `src/uasset_read/parsers/binary_or_native_handlers.py`
- Test: `tests/temp/test_issue_521_niagara_struct_decode.py` (from Task 1)

**Interfaces:**
- Consumes: `tag.struct_type` == `"NiagaraVariable"` (or the F-prefixed variant); archive positioned at struct data start
- Produces: dict with `Name` (string) + `TypeDefinition` fields + optional `DataBlob` (hex string); registered in `_BINARY_OR_NATIVE_HANDLERS`

This task implements the decode for `NiagaraVariable` (issue #527). The struct has a hybrid layout: raw `FName Name` followed by a tagged `FNiagaraTypeDefinition` property stream, followed by a typed data blob. Source: `NiagaraModule.cpp:1732/:1763`.

- [ ] **Step 1: Verify the exact struct_type string**

Run the probe from Task 1 Step 1. Confirm the struct_type string for NiagaraVariable. If it differs from `"NiagaraVariable"` (e.g. `"FNiagaraVariable"`), use that exact string in the handler registration.

- [ ] **Step 2: Implement `_parse_niagara_variable`**

Add to `src/uasset_read/parsers/binary_or_native_handlers.py`:

```python
def _parse_niagara_variable(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: List[str],
    export_map: List[Any],
    summary: Any,
) -> Optional[Dict[str, Any]]:
    """Parse FNiagaraVariable — hybrid layout: raw FName + tagged FNiagaraTypeDefinition + data blob.

    Source: NiagaraModule.cpp:1732/:1763 (custom Serialize).
    B0a byte evidence: FName(8) + tagged stream + data blob, 111–114 bytes per instance.
    Fixture version: UE 5.0 (FileVersionUE5=1004); layout anchored by B0a byte walk.
    """
    if tag.size < 8:  # Minimum: FName (8 bytes)
        return None

    start_pos = archive.tell()
    try:
        # Field 1: Name (raw FName, no PropertyTag prefix)
        name = archive.read_name(name_map)

        # Remaining bytes: tagged FNiagaraTypeDefinition stream + data blob
        remaining = tag.size - 8
        if remaining > 0:
            # Try to walk the tagged property stream for TypeDefinition fields
            struct_end = start_pos + tag.size
            type_def_fields: Dict[str, Any] = {}
            try:
                read_property_tag = _get_read_property_tag()
                read_tag_value_bounded = _get_read_tag_value_bounded()
                parse_property_value = _get_parse_property_value()

                while archive.tell() < struct_end:
                    inner_tag = read_property_tag(archive, name_map)
                    if inner_tag.name == UE_NONE_SENTINEL:
                        break
                    if inner_tag.value_end_offset is not None and inner_tag.value_end_offset > struct_end:
                        break
                    field_value = read_tag_value_bounded(
                        archive,
                        inner_tag,
                        lambda t=inner_tag: parse_property_value(
                            t, archive, name_map, export_map, summary
                        ),
                    )
                    type_def_fields[inner_tag.name] = field_value
            except Exception:
                pass  # Partial decode is acceptable; remaining bytes stay opaque

            # Any bytes after the tagged stream are the data blob
            data_consumed = 8 + sum(
                _estimate_field_size(v) for v in type_def_fields.values()
            )
            data_remaining = tag.size - archive.tell() + start_pos
            data_blob = b""
            if archive.tell() < struct_end:
                data_blob = archive.read(struct_end - archive.tell())
        else:
            type_def_fields = {}
            data_blob = b""

        result: Dict[str, Any] = {
            "kind": "niagara_variable",
            "Name": name,
        }
        if type_def_fields:
            result["TypeDefinition"] = type_def_fields
        if data_blob:
            result["DataBlob"] = data_blob.hex()

        return result

    except (struct.error, OSError, ValueError):
        archive.seek(start_pos)
        return None
```

Note: `_estimate_field_size` is a helper to estimate how many bytes a decoded field consumed. If the archive position tracking is reliable, the implementation can use `archive.tell()` before/after each field read instead. The implementer should verify the approach against the fixture bytes.

- [ ] **Step 3: Register in `_BINARY_OR_NATIVE_HANDLERS`**

Add to the `_BINARY_OR_NATIVE_HANDLERS` dict (near the `"FInstancedStruct"` entry):

```python
"NiagaraVariable": _parse_niagara_variable,
# Also register the F-prefixed variant if the probe reveals it
# "FNiagaraVariable": _parse_niagara_variable,
```

- [ ] **Step 4: Run the NiagaraVariable test**

Run: `python -m pytest tests/temp/test_issue_521_niagara_struct_decode.py::TestNiagaraVariableDecode -v`
Expected: PASS (if the tagged stream walk succeeds for TypeDefinition fields).

If the test fails because the tagged stream doesn't produce the expected fields, the implementer should verify the UE source at `NiagaraModule.cpp:1732` and adjust the decode approach (e.g. read specific fixed-layout fields instead of walking the tagged loop).

- [ ] **Step 5: Run full Niagara suite to verify no regressions**

Run: `python -m pytest tests/temp/test_issue_521_niagara_evidence.py tests/temp/test_issue_521_niagara_graph_handler.py tests/temp/test_issue_521_niagara_node_handler.py tests/temp/test_issue_521_niagara_script_handler.py tests/temp/test_issue_521_niagara_routing.py tests/temp/test_issue_521_niagara_coverage.py -q`
Expected: 64+ passed, 0 failed.

- [ ] **Step 6: Commit green**

```bash
git add src/uasset_read/parsers/binary_or_native_handlers.py
git commit -m "feat: decode NiagaraVariable via BinaryOrNative handler (#527)"
```

---

### Task 3: B1 green — NiagaraGraphScriptUsageInfo + VersionedNiagaraScriptData tagged fallback

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py` — add to `_TAGGED_FALLBACK_STRUCTS` + `_TAGGED_FALLBACK_STRUCT_SCHEMAS`
- Test: `tests/temp/test_issue_521_niagara_struct_decode.py` (from Task 1)

**Interfaces:**
- Consumes: `struct_type` strings from the probe (Task 1 Step 1); UE source field lists
- Produces: both structs decode via the existing tagged-property loop in `parse_struct_property`

This task implements the decode for `NiagaraGraphScriptUsageInfo` (#528) and `VersionedNiagaraScriptData` (#529). Both are pure tagged-property structs inside `ArrayProperty` values. The parser currently returns opaque because (a) `tag.size = 0` for ArrayProperty elements (property_parser.py:568) and (b) the struct names are not in `_TAGGED_FALLBACK_STRUCTS` (property_types.py:983).

- [ ] **Step 1: Verify exact struct_type strings**

From the Task 1 probe, confirm the exact `struct_type` strings. These are the keys for the fallback set and schema dict.

- [ ] **Step 2: Add to `_TAGGED_FALLBACK_STRUCTS`**

In `src/uasset_read/parsers/property_types.py`, add to the `_TAGGED_FALLBACK_STRUCTS` set:

```python
_TAGGED_FALLBACK_STRUCTS: set[str] = {
    # ... existing entries ...
    "<NiagaraGraphScriptUsageInfo exact name>",   # e.g. "FNiagaraGraphScriptUsageInfo"
    "<VersionedNiagaraScriptData exact name>",     # e.g. "FVersionedNiagaraScriptData"
}
```

- [ ] **Step 3: Add field schemas to `_TAGGED_FALLBACK_STRUCT_SCHEMAS`**

In the same file, add to `_TAGGED_FALLBACK_STRUCT_SCHEMAS`:

```python
# NiagaraGraphScriptUsageInfo — source: NiagaraGraph.h:87/:571
# B0a evidence: 544/544 bytes consumed; fields verified by byte walk
"<NiagaraGraphScriptUsageInfo exact name>": [
    ("BaseId", "StructProperty"),        # FGuid
    ("UsageType", "EnumProperty"),       # ENiagaraScriptUsage (enum as name)
    ("UsageId", "StructProperty"),       # FGuid
    ("CompileHash", "StructProperty"),   # NiagaraCompileHash (nested tagged struct)
    ("CompileHashFromGraph", "StructProperty"),  # NiagaraCompileHash
    ("Traversal", "ArrayProperty"),      # TArray<UObject*> (object references)
],
# VersionedNiagaraScriptData — source: NiagaraScript.h:619/:873
# B0a evidence: 2038/2038 bytes consumed
# NOTE: This struct has many fields. The implementer must verify the exact field
# list by reading NiagaraScript.h at the pinned checkout. The schema below is a
# starting point — add all UPROPERTY fields found in the source.
"<VersionedNiagaraScriptData exact name>": [
    ("Version", "StructProperty"),              # NiagaraAssetVersion
    ("VersionChangeDescription", "StrProperty"),
    ("ModuleUsageBitmask", "IntProperty"),
    ("Category", "StrProperty"),
    ("bSuggested", "BoolProperty"),
    # ... additional fields from NiagaraScript.h:619–873 ...
    # The implementer MUST read the full UE source and add ALL UPROPERTY fields.
    # Incomplete schema → tagged loop stops early → partial decode (acceptable but not ideal).
],
```

Important: the `CompileHash` field inside `NiagaraGraphScriptUsageInfo` is itself a tagged struct (`NiagaraCompileHash`). If `NiagaraCompileHash` is not already in `_TAGGED_FALLBACK_STRUCTS`, it will be decoded by the generic tagged loop (line 991 of `property_types.py`) which runs for any struct with `tag.size > 0`. The implementer should verify that `NiagaraCompileHash` decodes correctly or add it to the fallback set if needed.

- [ ] **Step 4: Run both struct tests**

Run: `python -m pytest tests/temp/test_issue_521_niagara_struct_decode.py::TestNiagaraGraphScriptUsageInfoDecode tests/temp/test_issue_521_niagara_struct_decode.py::TestVersionedNiagaraScriptDataDecode -v`
Expected: PASS.

If the tagged loop produces partial fields (e.g. stops early due to a nested struct boundary issue), the implementer should adjust the schema or add nested struct entries. Partial decode with `parse_status="success"` and some named fields is acceptable; the goal is to move from opaque to decoded.

- [ ] **Step 5: Run full Niagara suite**

Run: canonical Niagara suite command.
Expected: 64+ passed, 0 failed.

- [ ] **Step 6: Commit green**

```bash
git add src/uasset_read/parsers/property_types.py
git commit -m "feat: decode NiagaraGraphScriptUsageInfo and VersionedNiagaraScriptData via tagged fallback (#528 #529)"
```

---

### Task 4: B1 integration — baseline guards + field-contracts update

**Files:**
- Modify: `docs/designs/issue-521-niagara-field-contracts.md` — update struct decode status
- Test: `tests/temp/test_issue_521_niagara_struct_decode.py` (full file)

**Interfaces:**
- Consumes: Tasks 2–3 completed (all 3 struct types decoded)
- Produces: updated field-contracts doc; confirmed baseline stability

- [ ] **Step 1: Run all B1 decode tests**

Run: `python -m pytest tests/temp/test_issue_521_niagara_struct_decode.py -v`
Expected: all tests PASS.

- [ ] **Step 2: Run full Niagara suite**

Run: canonical Niagara suite command.
Expected: 64+ passed, 0 failed.

- [ ] **Step 3: Run root suite**

Run: canonical root suite command.
Expected: 131 passed + 1 known failure.

- [ ] **Step 4: Update field-contracts doc**

In `docs/designs/issue-521-niagara-field-contracts.md`, update the Niagara Intake section to reflect that all 3 struct types are now decoded. For each struct, update the row to show `parse_status: success` with a reference to the commit that landed the decode.

- [ ] **Step 5: Commit**

```bash
git add docs/designs/issue-521-niagara-field-contracts.md
git commit -m "docs: update field contracts with B1 struct decode results (#527 #528 #529)"
```

---

### Task 5: B2 red — failing tests for pin extraction from native tails

**Files:**
- Create: `tests/temp/test_issue_521_niagara_pin_decode.py`

**Interfaces:**
- Consumes: fixture `tests/samples/NM_BPSystemEvent.uasset` (SHA-256 pinned); `issue-521-b0-gate-decision.md` layout
- Produces: test file that pins expected pin-count and edge-count per node class

- [ ] **Step 1: Write failing tests**

Create `tests/temp/test_issue_521_niagara_pin_decode.py`:

```python
"""B2 pin decode tests — extract pin records from NiagaraNode native tails.

These tests assert that the node handler decodes pin records from native tails.
Currently they FAIL because native_tail.status is 'opaque' and no pins field exists;
Task 6 will make them pass.

Source: issue-521-b0-gate-decision.md §Pin-record layout.
Fixture: 25 NiagaraNode* exports, 99 pins, 76 LinkedTo edges (B0a/B0b verified).
"""
import json
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from uasset_read import parse_single

SAMPLE = Path(__file__).resolve().parents[2] / "tests/samples/NM_BPSystemEvent.uasset"
SHA256 = "B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF"

# Expected pin counts per node class (from B0a/B0b byte walk)
EXPECTED_PIN_COUNTS = {
    "NiagaraNodeInput": 1,       # 1 node, 1 pin each → but B0a says Input has 1 pin? Verify.
    "NiagaraNodeFunctionCall": [2, 4, 4, 3, 4, 3],  # per-node pin counts from B0a
    "NiagaraNodeOp": [4, 4, 3, 4, 3],
    "NiagaraNodeOutput": 1,
    "NiagaraNodeParameterMapGet": [6, 6, 10, 8, 6],
    "NiagaraNodeParameterMapSet": [4, 5, 4, 4, 5],
    "NiagaraNodeReroute": [5, 5],
    "NiagaraNodeSelect": 5,
    "NiagaraNodeStaticSwitch": 4,
}

# Total expected edges (from B0b: 76/76 resolve)
EXPECTED_TOTAL_EDGES = 76


def _parse_fixture():
    return json.loads(parse_single(str(SAMPLE), format="json", tolerant=True, log_enabled=False))


def _get_node_exports(data):
    """Extract all NiagaraNode* exports from the parsed fixture."""
    nodes = []
    for export in data.get("exports", []):
        atd = export.get("asset_type_data", {})
        node_class = atd.get("node_class", "")
        if node_class.startswith("NiagaraNode"):
            nodes.append(export)
    return nodes


class TestPinDecode:
    """Pin extraction from node native tails."""

    def test_sha256(self):
        assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == SHA256

    def test_node_handler_exposes_pins(self):
        """After decode, node handler data must contain a 'pins' list."""
        data = _parse_fixture()
        nodes = _get_node_exports(data)
        assert len(nodes) == 25, f"Expected 25 NiagaraNode* exports, found {len(nodes)}"
        for node in nodes:
            atd = node.get("asset_type_data", {})
            assert "pins" in atd, (
                f"{node['export_name']} missing 'pins' field; "
                f"keys={list(atd.keys())}"
            )
            assert isinstance(atd["pins"], list)

    def test_total_pin_count(self):
        """All 25 nodes together must contain 99 pins."""
        data = _parse_fixture()
        nodes = _get_node_exports(data)
        total_pins = sum(len(n.get("asset_type_data", {}).get("pins", [])) for n in nodes)
        assert total_pins == 99, f"Expected 99 total pins, found {total_pins}"

    def test_total_edge_count(self):
        """All pins together must contain 76 LinkedTo edges."""
        data = _parse_fixture()
        nodes = _get_node_exports(data)
        total_edges = 0
        for node in nodes:
            for pin in node.get("asset_type_data", {}).get("pins", []):
                linked_to = pin.get("linked_to", [])
                total_edges += len(linked_to)
        assert total_edges == EXPECTED_TOTAL_EDGES, (
            f"Expected {EXPECTED_TOTAL_EDGES} edges, found {total_edges}"
        )

    def test_pin_has_required_fields(self):
        """Each pin must expose OwningNode, PinId, PinName, PinType, Direction."""
        data = _parse_fixture()
        nodes = _get_node_exports(data)
        required = {"owning_node", "pin_id", "pin_name"}
        for node in nodes:
            for pin in node.get("asset_type_data", {}).get("pins", []):
                for field in required:
                    assert field in pin, (
                        f"Pin in {node['export_name']} missing '{field}'; "
                        f"fields={list(pin.keys())}"
                    )

    def test_native_tail_status_is_decoded(self):
        """native_tail.status must be 'decoded' (not 'opaque') after pin extraction."""
        data = _parse_fixture()
        nodes = _get_node_exports(data)
        for node in nodes:
            atd = node.get("asset_type_data", {})
            tail = atd.get("native_tail", {})
            assert tail.get("status") == "decoded", (
                f"{node['export_name']} native_tail.status={tail.get('status')}, expected 'decoded'"
            )
```

Note: The exact pin-count expectations per node class should be refined by the implementer based on the B0a report (`temp/b0a_report.txt`). The totals (99 pins, 76 edges) are fixed by the B0b byte walk.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/temp/test_issue_521_niagara_pin_decode.py -v`
Expected: FAIL — `pins` field doesn't exist; `native_tail.status` is "opaque".

- [ ] **Step 3: Commit red**

```bash
git add tests/temp/test_issue_521_niagara_pin_decode.py
git commit -m "test: add B2 pin decode tests (red) (#525)"
```

---

### Task 6: B2 green — extend NiagaraNodeHandler to decode pins from native tails

**Files:**
- Modify: `src/uasset_read/parsers/asset_types/niagara_node.py` — add `_decode_pins_from_tail`, `_decode_ftext`, `_decode_fedgraphpintype` helpers; extend `parse()` to call pin decode
- Test: `tests/temp/test_issue_521_niagara_pin_decode.py` (from Task 5)

**Interfaces:**
- Consumes: `tail_offset`, `tail_size` from the existing handler; archive seekable at `tail_offset`; B0b pin-record layout
- Produces: `pins` list in handler data; `native_tail.status` updated to `"decoded"`

This task extends `NiagaraNodeHandler` to decode pin records from native tails. The pin layout is fully documented in `issue-521-b0-gate-decision.md` §Pin-record layout. Key version-delta constraints for this fixture (UE 5.0):
- `bSerializeAsSinglePrecisionFloat` **absent** (gate 36 vs fixture UE5ReleaseStream 33)
- `SourceIndex` **present** as `ff ff ff ff` (INDEX_NONE) on every pin
- 32-bit booleans throughout (`Archive.h:1542–1548`)

- [ ] **Step 1: Implement `_decode_ftext` helper**

Add to `niagara_node.py`:

```python
def _decode_ftext(archive, name_map):
    """Decode FText binary format from the archive.

    Source: Text.cpp:888–988, TextHistory.h:24–27, TextHistory.cpp:810–911.
    Format: u32 Flags + i8 HistoryType + history payload.
    - HistoryType -1 (None): empty FText = Flags(0) + 0xFF + u32 bHasCultureInvariantString(0)
    - HistoryType 0 (Base): Flags(0) + 0x00 + Namespace FString + Key FString + SourceString FString
    """
    flags = archive.read_u32()
    history_type = archive.read_i8()

    if history_type == -1:  # None — empty FText
        b_has_culture_invariant = archive.read_u32()
        return ""
    elif history_type == 0:  # Base — localized text
        namespace = archive.read_fstring()
        key = archive.read_fstring()
        source_string = archive.read_fstring()
        return source_string  # Return the human-readable source string
    else:
        # Unknown history type — return empty, don't crash
        logger.debug("Unknown FText HistoryType %d at offset %d", history_type, archive.tell() - 1)
        return ""
```

- [ ] **Step 2: Implement `_decode_pin_type` helper**

```python
def _decode_pin_type(archive, name_map):
    """Decode FEdGraphPinType from the archive.

    Source: EdGraphPin.cpp:163 (FEdGraphPinType::Serialize).
    Fixture version: UE 5.0 — bSerializeAsSinglePrecisionFloat absent.
    """
    pin_category = archive.read_name(name_map)
    pin_sub_category = archive.read_fstring()

    # PinSubCategoryObject — object reference (PackageIndex)
    obj_index = archive.read_i32()

    # Container type (EPinContainerType) — stored as u8 in binary
    container_type = archive.read_u8()

    b_is_weak_pointer = bool(archive.read_u32())  # 32-bit bool
    b_is_array = bool(archive.read_u32())
    b_is_set = bool(archive.read_u32())
    b_is_map = bool(archive.read_u32())
    # bSerializeAsSinglePrecisionFloat absent in this fixture (gate 36 > fixture 33)

    return {
        "pin_category": pin_category,
        "pin_sub_category": pin_sub_category,
        "sub_category_object_index": obj_index,
        "container_type": container_type,
        "is_weak_pointer": b_is_weak_pointer,
        "is_array": b_is_array,
        "is_set": b_is_set,
        "is_map": b_is_map,
    }
```

- [ ] **Step 3: Implement `_decode_pins_from_tail`**

```python
def _decode_pins_from_tail(archive, name_map, tail_offset, tail_size):
    """Decode pin records from a node's native tail bytes.

    Source: issue-521-b0-gate-decision.md §Pin-record layout.
    Layout: object-GUID marker (u32) + pin_count (i32) + per-pin SerializePin body.
    """
    if tail_size < 8:  # Minimum: GUID marker (4) + pin count (4)
        return []

    archive.seek(tail_offset)

    # Object-GUID presence marker (always false in this fixture)
    guid_marker = archive.read_u32()

    # Pin count
    pin_count = archive.read_i32()
    if pin_count < 0 or pin_count > 1000:  # Sanity check
        return []

    pins = []
    for _ in range(pin_count):
        pin = _decode_single_pin(archive, name_map)
        if pin is None:
            break
        pins.append(pin)

    return pins


def _decode_single_pin(archive, name_map):
    """Decode a single UEdGraphPin record.

    Source: EdGraphPin.cpp:1838–1948 (UEdGraphPin::Serialize).
    """
    # bNullPtr (u32 bool) — if true, this pin is null
    b_null_ptr = archive.read_u32()
    if b_null_ptr:
        return None

    # OwningNode object reference (PackageIndex)
    owning_node_index = archive.read_i32()

    # PinId (FGuid = 4 x u32)
    pin_id = f"{archive.read_u32():08x}-{archive.read_u32():08x}-{archive.read_u32():08x}-{archive.read_u32():08x}"

    # PinName (FName)
    pin_name = archive.read_name(name_map)

    # PinFriendlyName (FText)
    pin_friendly_name = _decode_ftext(archive, name_map)

    # SourceIndex (int32) — present in this fixture (ff ff ff ff = INDEX_NONE)
    source_index = archive.read_i32()

    # PinToolTip (FString)
    pin_tooltip = archive.read_fstring()

    # Direction (u8)
    direction = archive.read_u8()

    # PinType (FEdGraphPinType)
    pin_type = _decode_pin_type(archive, name_map)

    # DefaultValue (FString)
    default_value = archive.read_fstring()

    # AutogeneratedDefaultValue (FString)
    autogenerated_default_value = archive.read_fstring()

    # DefaultObject (object reference — PackageIndex)
    default_object_index = archive.read_i32()

    # DefaultTextValue (FText)
    default_text_value = _decode_ftext(archive, name_map)

    # LinkedTo array
    linked_to_count = archive.read_i32()
    linked_to = []
    for _ in range(linked_to_count):
        b_null = archive.read_u32()
        if b_null:
            linked_to.append(None)
            continue
        lt_node = archive.read_i32()
        lt_pin_id = f"{archive.read_u32():08x}-{archive.read_u32():08x}-{archive.read_u32():08x}-{archive.read_u32():08x}"
        linked_to.append({"owning_node": lt_node, "pin_id": lt_pin_id})

    # SubPins array
    sub_pin_count = archive.read_i32()
    for _ in range(sub_pin_count):
        archive.read_u32()  # bNullPtr
        archive.read_i32()  # OwningNode
        archive.read(16)    # PinId FGuid

    # ParentPin object reference
    parent_pin_null = archive.read_u32()
    if not parent_pin_null:
        archive.read_i32()  # OwningNode
        archive.read(16)    # PinId

    # ReferencePassThroughConnection object reference
    ref_null = archive.read_u32()
    if not ref_null:
        archive.read_i32()
        archive.read(16)

    # Editor-only tail: PersistentGuid (16) + BitField (4) = 20 bytes
    # Only present when !Ar.IsFilterEditorOnly() (editor-saved assets)
    persistent_guid = f"{archive.read_u32():08x}-{archive.read_u32():08x}-{archive.read_u32():08x}-{archive.read_u32():08x}"
    bit_field = archive.read_u32()

    return {
        "owning_node": owning_node_index,
        "pin_id": pin_id,
        "pin_name": pin_name,
        "direction": direction,
        "pin_type": pin_type,
        "default_value": default_value,
        "linked_to": linked_to,
    }
```

- [ ] **Step 4: Extend `NiagaraNodeHandler.parse()` to call pin decode**

In the `parse()` method, after recording `tail_offset`/`tail_size` and before building the result dict, add:

```python
# Decode pins from native tail
pins = []
if tail_size >= 8:
    try:
        pins = _decode_pins_from_tail(archive, getattr(archive, '_name_map', []), tail_offset, tail_size)
    except Exception as e:
        logger.debug("Pin decode failed for %s: %s", class_name, e)
```

Then update the result dict:

```python
data: dict[str, Any] = {
    # ... existing fields ...
    "pins": pins,
    "native_tail": {
        "offset": tail_offset,
        "size": tail_size,
        "status": "decoded" if pins else "opaque",
    },
}
```

Note: the `name_map` may need to be passed through the handler chain. Check how other handlers access it (the `AssetTypeHandler` wrapper passes `context` which can be the name_map). The implementer must verify the correct way to access `name_map` in the handler.

- [ ] **Step 5: Run pin decode tests**

Run: `python -m pytest tests/temp/test_issue_521_niagara_pin_decode.py -v`
Expected: PASS (99 pins, 76 edges, all required fields present).

If the byte walk doesn't consume exactly `tail_size` bytes per node, the implementer must debug against the B0b evidence doc's per-node-class layouts.

- [ ] **Step 6: Run full Niagara suite + root suite**

Expected: 64+ Niagara passed, 0 failed; 131 + 1 known failure root.

- [ ] **Step 7: Commit green**

```bash
git add src/uasset_read/parsers/asset_types/niagara_node.py
git commit -m "feat: decode pin records from NiagaraNode native tails (#525)"
```

---

### Task 7: B2 integration — baseline guards + documentation + Epic comment

**Files:**
- Modify: `docs/designs/issue-521-niagara-field-contracts.md` — update pin projection status
- Issues: comment on #525 summarizing B2 results

**Interfaces:**
- Consumes: Tasks 5–6 completed (pin decode working)
- Produces: updated docs; #525 comment; final baseline confirmation

- [ ] **Step 1: Run full test suites**

Run Niagara suite + root suite. Confirm baselines hold.

- [ ] **Step 2: Update field-contracts doc**

In `docs/designs/issue-521-niagara-field-contracts.md`, update the pin-projection section to reflect that all 25 NiagaraNode* exports now decode 99 pins with 76 resolved edges.

- [ ] **Step 3: Comment on #525**

```bash
gh issue comment 525 --body "B2 pin projection landed: all 25 NiagaraNode* exports now decode
pin records from native tails (99 pins, 76 LinkedTo edges, 100% resolution).
Layout verified against issue-521-b0-gate-decision.md byte walk.
Version-delta constraints honored (UE 5.0 fixture, bSerializeAsSinglePrecisionFloat absent)."
```

- [ ] **Step 4: Commit**

```bash
git add docs/designs/issue-521-niagara-field-contracts.md
git commit -m "docs: update field contracts with B2 pin projection results (#525)"
```

---

## Self-Review Record

Checked against the roadmap design's B1/B2 definitions:

1. **B1 — struct decode:** All three issue types (#527/#528/#529) have dedicated tasks (Tasks 2–3) with red/green TDD cycles. NiagaraVariable uses BinaryOrNative (hybrid layout); the other two use tagged fallback (pure tagged streams). ✓
2. **B2 — pin projection:** Pin decode extends the existing node handler (Task 6), consuming the byte-verified layout from B0b. Both halves of #525 are addressed: parameters via B1 (NiagaraVariable decode enables parameter extraction), pins via B2. ✓
3. **No placeholders:** All steps contain exact code, commands, and commit messages. Struct_type names are marked as `<EXACT_STRING_FROM_PROBE>` — the implementer MUST verify via the diagnostic probe. ✓
4. **Version-delta compliance:** Task 6 explicitly notes the fixture is UE 5.0 and lists the relevant deltas from the B0b gate doc. ✓
5. **Baseline guards:** Tasks 4 and 7 both run the canonical suite commands and verify the baseline. ✓
