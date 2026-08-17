# DataTable Semantic JSON Extension Design

> Issue: [#557](https://github.com/soatori/uasset_read/issues/557) (first sub-issue — DataTable)
> Builds on: [#551](https://github.com/soatori/uasset_read/issues/551) (common infrastructure — CLOSED)
> Date: 2026-08-17
> Status: Draft
> Anchor: Unreal Engine 5.8.0

## 1. Goal

Define semantic JSON output for DataTable (`UDataTable`) assets, building on the common infrastructure established by #551.

#557 (Other UAsset asset semantic JSON) covers six heterogeneous asset types (SkeletalMesh, StaticMesh, Skeleton, Texture2D, DataTable, SoundWave) that share almost no domain model. It is decomposed into per-family sub-issues; **DataTable is the first** — the exemplar for "manifest domains" (assets whose data is already parsed by an asset-type handler and projected directly from `ExportIR.asset_type_data`, with no dedicated `PackageIR` field or `ir_builder` change).

The DataTable semantic JSON must:
- Capture the row manifest: row count, per-row name, per-row payload size
- Resolve the `RowStruct` reference (class name, object name, package path)
- Report honest coverage: row manifest available, row values unavailable (external struct)
- Output diagnostics explaining why row values are not parsed — no fabricated semantics

## 2. Background

### 2.1 Common Infrastructure (#551)

#551 established the `semantic/` package with:
- `SemanticIR` (`semantic/models.py`) — mode-independent IR with envelope fields (`format`, `asset_type`, `asset`, `status`, `references`, `coverage`, `diagnostics`, `evidence`) plus a `content` staging dict promoted to top-level JSON by the renderer.
- `build_semantic_ir()` (`semantic/builder.py`) — selects primary export, resolves `asset_type`, calls the registered domain extractor, builds honest status.
- Domain registry (`semantic/extensions.py`) — `register_extension(class_name, extractor, *, domain_format, domain_format_version)` maps UE class names to extractors; `get_domain_format()` marks a class as owning its envelope sections.
- `register_domain_validator(fmt, fn)` + `validate_semantic_document()` (`semantic/validator.py`) — structural contract checks, dispatches to domain validators.
- `render_semantic_json()` (`semantic/render.py`) — deterministic UTF-8/LF JSON; promotes `content` keys to top-level; `content["coverage"|"diagnostics"|"references"]` override envelope values.
- `project_semantic()` (`semantic/projection.py`) — `project_debug(debug) == standard` isomorphism.
- `CoverageModel` (`semantic/coverage.py`) — `track(scope, available)` → `CoverageInfo{scopes_expected, scopes_available, scopes_unavailable, notes}`.
- `kinds.py` — maps UE class names to normalized `asset_type` slugs; `DataTable` → `data_table` is already mapped.
- Schemas in `src/uasset_read/schemas/` (`semantic.schema.json` base + per-domain schemas).

### 2.2 Existing Domain Extensions

#554 (Blueprint), #555 (AnimBlueprint), #556 (Material) are all CLOSED and ship on `dev-0.5.5`. Each registered a domain format (`uasset_read.<domain>_semantic` v1.0.0), a schema, a validator, and an extractor subpackage under `semantic/<domain>/`. All three are *graph domains*: they parse binary graph data needing archive access during `ir_builder`, so each has a dedicated IR dataclass + `PackageIR` field (`blueprint`, `material`).

### 2.3 Current DataTable Parsing State

| Layer | What exists | Gap |
|-------|-------------|-----|
| Asset-type handler (`parsers/asset_types/data_table.py`) | `parse_data_table()` reads `NumRows` + per-row `FName` (index + number) + `RowPayload` (size + raw bytes). Result: `{parse_status, row_count, rows: [{name, name_index, name_number, payload_size}]}` | Row payload bytes are **read and discarded** (`_payload_data` unused). No row values. |
| Handler wiring (`parsers/asset_types/__init__.py`) | `DataTable` registered via optional `AssetTypeHandler` list; result attached to `export._asset_type_data` | Result flows into `ExportIR.asset_type_data` but no semantic projection exists |
| Property parsing | `RowStruct` property (an `ObjectProperty` referencing an import) is parsed by the generic property parser into `export.properties` | Reference is not semantically resolved in JSON output |
| IR (`models/ir.py`) | `ExportIR.asset_type_data: dict | None` carries the manifest | No `PackageIR` DataTable field (not needed for Approach A) |
| Semantic (`semantic/`) | `kinds.py` maps `DataTable` → `data_table`; `structured_domain.py` is an empty stub | No extractor, no schema, no validator, no domain format |

### 2.4 Sample Evidence

Three real DataTable samples exist in `tests/samples/`:

| Sample | `RowStruct` kind | Resolvable in-package? |
|--------|------------------|------------------------|
| `FirstPerson_DT_WeaponList.uasset` | `UserDefinedStruct` (`ST_WeaponTableRow`) imported from `/Game/.../ST_WeaponTableRow` | No — external package |
| `ALS_FootstepDataTable.uasset` | `ScriptStruct` (C++ native) | No — native, no layout |
| `Lyra_DT_SurfaceTypes.uasset` | `ScriptStruct` (C++ native) | No — native, no layout |

**All three samples have external `RowStruct`.** Parsing row values requires the struct's field layout, which lives in another `.uasset` (UserDefinedStruct) or in C++ reflection (ScriptStruct) — neither available to a single-asset parser. Per the #551 "don't fabricate semantics" and the `kinds.py` evidentiary policy ("only classes proven to appear in tracked samples are mapped; never guess"), row-value parsing is deferred until a sample with an in-package resolvable struct exists.

## 3. Approach Decision: Direct-Read Extractor

### 3.1 Options Considered

| Aspect | Approach A: Direct-Read Extractor | Approach B: Dedicated `DataTableIR` | Approach C: Shared `structured_domain` Helper |
|--------|-----------------------------------|-------------------------------------|---------------------------------------------|
| Manifest source | Read `ExportIR.asset_type_data` directly in extractor | Copy manifest dict into a `DataTableIR` dataclass in `ir_builder`, then extractor projects it | Build a reusable row-manifest model in `semantic/structured_domain.py` for DataTable/CurveTable/StringTable |
| New model code | None — reuses `ExportIR.asset_type_data` | `DataTableIR` dataclass + `PackageIR.data_table` field + `_build_data_table_ir()` | Shared helper + per-domain config |
| `ir_builder` change | None | Add `_build_data_table_ir` + wire into `build_package_ir` | Varies |
| Consistency with existing domains | Distinct from graph domains (which need archive access during build) — establishes a second, simpler pattern for manifest domains | Mirrors Material/Blueprint on paper, but those domains built dedicated IR because they parse binary graph data needing archive access; DataTable's manifest is already parsed | Front-loads abstraction for sibling assets that don't exist in this scope |
| Boilerplate | Minimal | Pure re-wrapping of an existing dict | Moderate, speculative |
| Risk | Low — extends existing patterns, smallest diff | Low, but adds ceremony for no functional gain | Medium — abstracting before a second consumer arrives (YAGNI) |

### 3.2 Decision: Approach A

**Approach A (Direct-Read Extractor)** is selected because:

1. **The manifest is already parsed.** `parse_data_table` already produces `{row_count, rows: [{name, payload_size}]}` and stores it on `ExportIR.asset_type_data`. Re-wrapping it into a `DataTableIR` dataclass would be pure boilerplate (YAGNI).
2. **No archive access needed during build.** Graph domains (Blueprint/AnimBP/Material) need a dedicated IR + `ir_builder` step because they parse binary graph data from the archive during `build_package_ir`. DataTable's data is fully parsed by the asset-type handler before IR construction — nothing to build in `ir_builder`.
3. **It establishes the right pattern for the remaining #557 manifest domains** (Texture2D, SoundWave, etc.): domains whose data is already parsed by an asset-type handler project directly from `ExportIR.asset_type_data`; graph domains get a dedicated IR + `PackageIR` field. This directly serves #557's "Identify common semantic patterns across UAsset types" acceptance criterion with a *demonstrated* simple-domain pattern, not a premature shared framework.
4. **Ponytail principle**: simplest solution that covers the acceptance criteria. Approach B adds ceremony for no gain; Approach C front-loads abstraction before a second consumer exists.

### 3.3 What Approach A Still Requires

1. New domain subpackage `semantic/data_table/` (`__init__.py` + `extractor.py`)
2. New schema `src/uasset_read/schemas/data_table_semantic.schema.json`
3. `validate_data_table_document` in `semantic/validator.py` + `_FORMAT_VERSIONS` entry
4. Import the domain subpackage in `semantic/__init__.py` (registration side-effect)
5. Add the domain to `format_to_schema` in `semantic/render.py` (for `--schema`)

No changes to `kinds.py` (already maps), `ir_builder.py`, `models/ir.py`, parsers, or `parse_data_table.py`.

## 4. Design

### 4.1 Domain Format

- `format`: `uasset_read.data_table_semantic`
- `format_version`: `1.0.0`
- `asset_type`: `data_table` (from `kinds.py`)

Registered via `register_extension("DataTable", build_data_table_content, domain_format="uasset_read.data_table_semantic", domain_format_version="1.0.0")`. Because `domain_format` is set, the builder treats the domain as owning its envelope sections (`coverage`/`diagnostics`/`references`) inside `content`.

### 4.2 Content Model

The extractor returns a `content` dict. The renderer (`render.py:47-53`) promotes domain-specific keys to top-level and lets `coverage`/`diagnostics`/`references` from `content` override the envelope. Target JSON (standard mode):

```json
{
  "format": "uasset_read.data_table_semantic",
  "format_version": "1.0.0",
  "mode": "standard",
  "asset_type": "data_table",
  "asset": {"package": "/Game/.../DT_WeaponList", "name": "DT_WeaponList"},
  "status": {"parse": "complete", "representation": "partial"},
  "references": [ ... ],
  "data_table": {
    "row_count": 3,
    "row_struct": {
      "class_name": "UserDefinedStruct",
      "object_name": "ST_WeaponTableRow",
      "package_path": "/Game/Variant_Shooter/Blueprints/Pickups/ST_WeaponTableRow"
    },
    "rows": [
      {"name": "Row1", "payload_size": 24},
      {"name": "Row2", "payload_size": 24}
    ]
  },
  "coverage": {
    "scopes_expected": 2,
    "scopes_available": 1,
    "scopes_unavailable": ["row_values"],
    "notes": ""
  },
  "diagnostics": [
    {
      "severity": "info",
      "code": "ROW_VALUES_UNRESOLVED",
      "message": "Row values not parsed (deferred); row struct 'ST_WeaponTableRow' in package '/Game/Variant_Shooter/Blueprints/Pickups/ST_WeaponTableRow'"
    }
  ]
}
```

Field semantics:
- `data_table.row_count` — `int32` row count from `LoadStructData`.
- `data_table.row_struct` — resolved reference to the `RowStruct` property's target. **Nullable**: a DataTable without a resolvable `RowStruct` property omits the field. Shape mirrors `ReferenceEntry` (subset): `{class_name, object_name, package_path}`. `package_path` is the package containing the struct (resolved through the import's outer chain, same logic as `semantic/references.py`); empty string when unresolvable.
- `data_table.rows[].name` — the row's `FName` (stable within the asset).
- `data_table.rows[].payload_size` — `int32` byte size of the opaque row payload.
- **No URI ID scheme.** DataTable has no graph/pins; row identity is the stable `FName`. This is deliberately distinct from graph domains' `blueprint://...` URIs and is part of the "manifest domain" pattern.
- `coverage` reuses the base `CoverageInfo` **object** shape (not the array shape blueprint uses) — simpler, valid against the base schema, sufficient for a two-scope domain. `diagnostics` reuses the standard `DiagnosticEntry` array.

### 4.3 Extractor

**File**: `src/uasset_read/semantic/data_table/extractor.py`

Signature (v2 contract — no `mode` parameter; DataTable has no debug-specific evidence beyond the common envelope):

```python
def build_data_table_content(package_ir, export_ir, coverage_model, evidence_list) -> dict
```

Algorithm:
1. Read `export_ir.asset_type_data` (the manifest). If absent or empty:
   - `coverage_model.track("row_manifest", False)`
   - return `{}` (the envelope reports opaque via `NO_EXTRACTOR`/`PARTIAL_PARSE`; the common-layer evidence already records the export index and parse status).
2. Resolve `RowStruct` from `export_ir.properties`:
   - Find the `RowStruct` property (an `ObjectProperty` whose value is a `PackageIndex` referencing an import).
   - Resolve the import through the outer chain (same logic as `semantic/references.py` uses for import `package_path`) to `{class_name, object_name, package_path}`.
   - Nullable: if no `RowStruct` property or unresolvable, `row_struct = None`.
3. `coverage_model.track("row_manifest", True)`
4. `coverage_model.track("row_values", False)` — values not parsed (external struct; see §4.4).
5. Build `rows` list from `asset_type_data["rows"]`: `[{name, payload_size} for r in rows]`.
6. Build `content`:
   ```python
   content = {
       "data_table": {
           "row_count": asset_type_data.get("row_count", len(rows)),
           "row_struct": row_struct,   # may be None (stripped by renderer)
           "rows": rows,
       },
       "coverage": asdict(coverage_model.build()),
       "diagnostics": [_row_values_unresolved_diagnostic(row_struct)],
   }
   ```
7. Return `content`.

The `ROW_VALUES_UNRESOLVED` diagnostic is `info` severity (the parser did nothing wrong; row-value parsing is deferred in this version). The message names the struct's `object_name` and `package_path` so a consumer can locate it. The phrasing "in package '<path>'" is honest for both the external case (path is another package — all three current samples) and a future in-package case (path would be this package); it does not claim the struct is external when it is not. When `row_struct` is `None` (no `RowStruct` property found), the diagnostic instead explains that no row-struct reference was found.

### 4.4 Honest Status Contract

Because `content["coverage"]` is non-empty and reports `row_values` as unavailable, the builder (`builder.py:225-230`) forces `representation = "partial"`. This is correct and honest:
- `parse` stays `complete` — the file parsed fine; only the cross-package struct layout is out of reach.
- `representation` is `partial` — we have the manifest but not the semantic values.

This is the #551 "don't fabricate semantics" contract working as intended: we report what we have (manifest) and honestly mark what we don't (values), rather than omitting the asset or fabricating values.

### 4.5 Known Limitation: Envelope Diagnostic Override

`render.py` *overrides* (does not merge) envelope `diagnostics` with `content["diagnostics"]` (`render.py:46-51`). For the common case (a clean DataTable parse) the envelope diagnostic list is empty, so nothing is lost. For a DataTable that also had package-level parse errors, those envelope diagnostics would not appear in `content["diagnostics"]` (their severity is still reflected in `status.parse`). Merging diagnostics is a cross-domain builder change (belongs to #551 territory) and is out of scope here. The implementation carries a `ponytail:` comment naming this ceiling and the upgrade path.

### 4.6 Schema

**File**: `src/uasset_read/schemas/data_table_semantic.schema.json` (Draft 2020-12)

Self-contained, with locally-defined `$defs` (matching the blueprint/anim/material template — each domain schema is independent). Required top-level fields: `format`, `format_version`, `mode`, `asset_type`, `asset`, `status`, `data_table`. `allOf` rule: standard mode → `evidence` maxItems 0.

Key `$defs`:

```json
"DataTable": {
  "type": "object",
  "required": ["row_count", "rows"],
  "properties": {
    "row_count": {"type": "integer", "minimum": 0},
    "row_struct": {"$ref": "#/$defs/RowStructRef"},
    "rows": {"type": "array", "items": {"$ref": "#/$defs/RowEntry"}}
  }
},
"RowStructRef": {
  "type": "object",
  "required": ["class_name", "object_name"],
  "properties": {
    "class_name": {"type": "string"},
    "object_name": {"type": "string"},
    "package_path": {"type": "string"}
  }
},
"RowEntry": {
  "type": "object",
  "required": ["name", "payload_size"],
  "properties": {
    "name": {"type": "string", "minLength": 1},
    "payload_size": {"type": "integer", "minimum": 0}
  }
}
```

`AssetStatus`, `ReferenceEntry` (relaxed: `items: {type: object}` to allow the envelope's resolved references), `CoverageInfo`, `DiagnosticEntry`, `EvidenceEntry` are defined locally per the domain template. `additionalProperties: false` is applied to `DataTable`, `RowStructRef`, and `RowEntry`; the top-level document allows the envelope fields.

### 4.7 Validator

**File**: `src/uasset_read/semantic/validator.py`

Add `validate_data_table_document(ir) -> list[str]` and register it via `register_domain_validator("uasset_read.data_table_semantic", validate_data_table_document)` (registration call lives in `semantic/data_table/__init__.py`). Add `"uasset_read.data_table_semantic": "1.0.0"` to `_FORMAT_VERSIONS`.

Rules (simpler than blueprint's — no closure/ID checks because there are no graph endpoints):
- `content.data_table` must be present and non-empty.
- `data_table.row_count` must equal `len(data_table.rows)`.
- Each `rows[]` entry must have non-empty `name` and integer `payload_size >= 0`.
- `row_struct` (if present) must have `class_name` and `object_name`.
- Opaque representation must have at least one diagnostic (mirrors the common rule).
- Standard mode must not contain `evidence` (common rule; the domain validator can no-op this since the common validator already checks it).

### 4.8 Wiring

**File**: `src/uasset_read/semantic/__init__.py` — add after the existing domain imports:
```python
import uasset_read.semantic.data_table  # noqa: F401  (registers #557 DataTable extractors)
```

**File**: `src/uasset_read/semantic/render.py` — add to `format_to_schema`:
```python
"uasset_read.data_table_semantic": "data_table_semantic.schema.json",
```

## 5. Files to Change

| File | Change | Type |
|------|--------|------|
| `src/uasset_read/semantic/data_table/__init__.py` | Register extractor + domain validator + format/version | New code |
| `src/uasset_read/semantic/data_table/extractor.py` | `build_data_table_content` + `RowStruct` resolution helper | New code |
| `src/uasset_read/schemas/data_table_semantic.schema.json` | Draft 2020-12 schema | New schema |
| `src/uasset_read/semantic/validator.py` | `validate_data_table_document` + `_FORMAT_VERSIONS` entry | New code |
| `src/uasset_read/semantic/__init__.py` | Import `data_table` subpackage (registration side-effect) | Wiring |
| `src/uasset_read/semantic/render.py` | `format_to_schema` entry for `--schema` | Wiring |

No changes to: `kinds.py` (already maps `DataTable`), `ir_builder.py`, `models/ir.py`, parsers, `parse_data_table.py`.

## 6. Testing Strategy

Reuse the #551/#556 test scaffold. Tests against the three real samples:

| Sample | Verifications |
|--------|---------------|
| `FirstPerson_DT_WeaponList.uasset` | `row_struct.class_name == "UserDefinedStruct"`; `row_struct.package_path` points at the external struct package; manifest row names; `representation == "partial"`; `ROW_VALUES_UNRESOLVED` diagnostic present |
| `ALS_FootstepDataTable.uasset` | `row_struct.class_name == "ScriptStruct"`; native struct path; same status/diagnostic contract |
| `Lyra_DT_SurfaceTypes.uasset` | Same as ALS (ScriptStruct native) |

### 6.1 Schema Conformance
- `jsonschema` validates each sample's standard + debug output against `data_table_semantic.schema.json`.

### 6.2 Manifest Correctness
- `row_count` and row names match the samples' actual rows (regression-checked against `parse_data_table` output).

### 6.3 RowStruct Resolution
- `row_struct.package_path` is non-empty and points at the external struct package.
- `ScriptStruct` (native) and `UserDefinedStruct` (external package) both resolve to a reference.

### 6.4 Honest Status
- `representation == "partial"`.
- `coverage.scopes_unavailable == ["row_values"]`.
- A `ROW_VALUES_UNRESOLVED` diagnostic is present.

### 6.5 Projection Isomorphism
- `project_debug(debug_output) == standard_output` (the #551 contract).

### 6.6 Byte Determinism
- Same input + parser version + configuration → byte-identical output.

### 6.7 Validator Unit Tests
- `validate_data_table_document` rules: row_count mismatch, missing `name`, negative `payload_size`, missing `row_struct.class_name`, opaque-without-diagnostic.

## 7. Acceptance Criteria Mapping

| Issue Criterion (#557) | How Satisfied |
|------------------------|---------------|
| Identify common semantic patterns across UAsset types | Establishes the "manifest domain" pattern (direct-read from `ExportIR.asset_type_data`, no dedicated IR) vs the "graph domain" pattern (dedicated IR + `PackageIR` field). Documented in §3.2 and §4.2. |
| Define Schema/validator for each additional asset type | `data_table_semantic.schema.json` + `validate_data_table_document`. |
| Capture domain-specific properties and relationships | Row manifest (count, names, payload sizes) + resolved `RowStruct` reference. |
| Handle coverage/diagnostics for each asset type consistently | Reuses `CoverageModel`/`CoverageInfo` and `DiagnosticEntry`; `representation="partial"` forced by honest coverage; `ROW_VALUES_UNRESOLVED` info diagnostic. |

## 8. Non-Goals

- **Row value parsing.** Row payloads are not decoded into typed struct values. All three samples have external `RowStruct` (UserDefinedStruct from another package, or ScriptStruct native). Cross-package struct resolution is a separate, larger feature. The schema is designed so a future `values` field can be added per row without breaking the manifest.
- **Retaining raw row payload bytes.** Not emitted (opaque bytes are not "semantic"). The existing handler reads and discards them; the bytes remain re-readable from the file if a future issue adds value parsing.
- **CurveTable.** Sibling structured-table asset (curves, not rows) with its own `parse_curve_table` handler. Tracked as a separate #557 sub-issue; this spec is DataTable-only.
- **Cross-package struct resolution.** Resolving an external `UserDefinedStruct` by loading its source `.uasset` is out of scope for a single-asset parser.
- **Markdown renderer additions.** The semantic JSON contract is the deliverable; a Markdown section can follow the Material section pattern as a follow-up if desired.

## 9. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| `RowStruct` property name/shape varies across UE versions | Resolve defensively: scan `export_ir.properties` for a property named `RowStruct`; if absent, emit `row_struct: null` + a diagnostic. No fabricated reference. |
| `asset_type_data` absent (handler skipped or failed) | Extractor returns `{}` after tracking `row_manifest: False`; the envelope reports opaque/partial with the existing `NO_EXTRACTOR`/`PARTIAL_PARSE` diagnostics. No crash. |
| Envelope diagnostics overridden by `content["diagnostics"]` on partial parses | Documented limitation (§4.5). For the common case (clean parse) no loss. `ponytail:` comment names the ceiling; merge is a #551-tier builder change. |
| Row count safety limit | `parse_data_table` already caps at `_MAX_ROWS = 100000`; the extractor trusts the handler's `parse_status` and propagates `partial` when the cap is hit. |
| Future row-value parsing breaks the schema | Schema's `RowEntry` is `additionalProperties: false` but a future `values` field can be added as an optional property without changing existing fields. |

## 10. UE Source References

| Structure | Source Location |
|-----------|----------------|
| `UDataTable` | `Engine/Source/Runtime/Engine/Classes/Engine/DataTable.h` |
| `UDataTable::Serialize` / `LoadStructData` | `Engine/Source/Runtime/Engine/Private/DataTable.cpp` |
| `FTableRowBase` | `Engine/Source/Runtime/Engine/Classes/Engine/DataTable.h` |
| `UScriptStruct` (native row struct) | `Engine/Source/Runtime/CoreUObject/Public/UObject/ScriptStruct.h` |
| `UserDefinedStruct` | `Engine/Source/Runtime/Engine/Classes/Engine/UserDefinedStruct.h` |
