# Non-Blueprint Semantic JSON Output Design

Date: 2026-08-13

Status: Design approved, pending implementation

Issue: #552

## 1. Goal

Define the semantic content model for non-Blueprint UAsset types, establishing the common `asset_semantic` envelope as the single output format for all non-Blueprint asset families. This design covers three asset families: `graph`, `structured`, and `resource`.

## 2. Scope

This design covers:

- Common envelope usage for non-Blueprint assets (envelope itself unchanged)
- Per-domain content model definitions (skeleton, not full implementation)
- Namespace collision protection
- Cross-asset reference deduplication via stable IDs
- Coverage and diagnostics per domain
- Size/loss limits for large native payloads
- Test fixtures and acceptance assertions
- Documentation structure

This design does NOT cover:

- Changing Blueprint Semantic JSON v1 (#551)
- Implementing full domain extractors (#554–#557 implement per-domain)
- Adding new JSON Schema domain sub-schemas
- Splitting output files or adding a third output mode

## 3. Architecture

### 3.1 Layer Model

```
┌─────────────────────────────────────────────────┐
│  SemanticIR  (envelope — existing, unchanged)    │
│  format, format_version, mode, asset_type,      │
│  asset, status, references, coverage,           │
│  diagnostics, evidence                          │
├─────────────────────────────────────────────────┤
│  content  (domain layer — dispatched by asset_type) │
│  ┌───────────┬──────────────┬──────────────┐    │
│  │  graph    │  structured  │  resource    │    │
│  │ extractor │  extractor   │  extractor   │    │
│  └───────────┴──────────────┴──────────────┘    │
├─────────────────────────────────────────────────┤
│  Validation layer (Python — dispatched by asset_type) │
│  envelope validation (existing) + domain validation (new) │
└─────────────────────────────────────────────────┘
```

### 3.2 Key Decisions

1. **Renderer unchanged** — `render_semantic_json()` continues merging `content` to top-level JSON via `raw.update(content)`.
2. **Extractor interface unchanged** — `extractor(export, coverage, evidence_list) -> dict`.
3. **Validator extended** — `validate_semantic_document()` adds `_DOMAIN_VALIDATORS` registry, dispatched by `asset_type`.
4. **Documentation constraint** — each asset family has its own doc in `docs/formats/uasset/`, defining required fields, optional fields, and value domains.
5. **Schema unchanged** — `semantic.schema.json` keeps `additionalProperties: true`. Domain content validation is handled by Python validators, not JSON Schema.

### 3.3 Asset Family Classification

Maps to `kinds.py` `resolve_asset_type()`:

| Family | asset_type values | Current extractor |
|--------|-------------------|-------------------|
| graph | `material`, `sound_cue`, `niagara_system`, `niagara_emitter`, `niagara_script` | `graph_domain.py` |
| structured | `static_mesh`, `skeletal_mesh`, `skeleton`, `anim_sequence`, `anim_montage`, `data_table`, `curve_table` | `structured_domain.py` |
| resource | `texture`, `sound_wave` | `resource_domain.py` |

Blueprint types (`blueprint`, `anim_blueprint`) use the separate `blueprint_semantic` format and are out of scope.

## 4. Namespace Collision Protection

### 4.1 Problem

`render_semantic_json()` merges `content` to top-level via `raw.update(content)`. Domain fields appear at the same level as envelope fields. If an extractor emits a key like `format` or `status`, it silently overwrites the envelope.

### 4.2 Solution

Collision guard in `render_semantic_json()` before `raw.update(content)`:

```python
ENVELOPE_KEYS: frozenset[str] = frozenset({
    "format", "format_version", "mode", "asset_type",
    "asset", "status", "references", "coverage",
    "diagnostics", "evidence", "$schema",
})

def render_semantic_json(ir: SemanticIR, ...) -> str:
    raw = asdict(ir)
    content = raw.pop("content", {}) or {}
    collisions = ENVELOPE_KEYS & set(content.keys())
    if collisions:
        raise ValueError(
            f"Domain content collides with envelope keys: {sorted(collisions)}"
        )
    raw.update(content)
    ...
```

### 4.3 Rules

- `ENVELOPE_KEYS` is a `frozenset`, aligned with schema `required` fields.
- Extractor documentation explicitly lists forbidden key names.
- Test coverage: construct extractor returning `{"format": "bad"}`, assert `ValueError`.

## 5. Domain Content Models

### 5.1 Graph Domain (Material / SoundCue / Niagara)

Target content structure (implemented incrementally by #554–#557):

```json
{
    "graph_metadata": {
        "class_name": "Material",
        "object_name": "M_Wood",
        "serial_size": 12345
    },
    "nodes": [
        {
            "id": "n0",
            "kind": "texture_sample",
            "label": "TextureSample",
            "inputs": {
                "UV": {"type": "vector2"}
            },
            "outputs": {
                "RGB": {"type": "vector3"},
                "A": {"type": "float"}
            },
            "refs": [{"target": 0, "role": "texture_asset"}]
        }
    ],
    "edges": [
        {
            "from": {"node": "n0", "pin": "RGB"},
            "to": {"node": "n1", "pin": "BaseColor"}
        }
    ],
    "asset_type_data": {}
}
```

Design principles:

- Nodes use local stable `id` (not full paths).
- `refs` use reference table index (e.g., `0`), not inline package paths.
- Edges express only confirmed connections, no speculation.
- `asset_type_data` preserved as compatibility layer; new fields replace it incrementally.
- Domain-specific edge semantics: material data flow, audio signal flow, Niagara parameter/simulation flow.

### 5.2 Structured Domain (StaticMesh / Skeleton / DataTable)

```json
{
    "class_name": "StaticMesh",
    "object_name": "SM_Chair",
    "serial_size": 45678,
    "summary": {
        "vertex_count": 1200,
        "triangle_count": 800,
        "lod_count": 3,
        "bounds": {"min": [0, 0, 0], "max": [100, 100, 50]},
        "materials": [{"slot": "Body", "ref": 0}]
    },
    "reference_skeleton": {},
    "row_count": 50
}
```

Design principles:

- `summary` contains business-level fields, not raw arrays.
- `reference_skeleton` and `row_count` are existing passthrough fields.
- `materials[].ref` uses reference table index.

### 5.3 Resource Domain (Texture2D / SoundWave)

```json
{
    "class_name": "Texture2D",
    "object_name": "T_Wood_D",
    "serial_size": 204800,
    "properties": {
        "SizeX": 1024,
        "SizeY": 1024,
        "Format": "PF_DXT5",
        "NumMips": 10
    },
    "bulk_summary": {
        "total_bytes": 1048576,
        "compressed_bytes": 524288,
        "chunk_count": 1
    },
    "asset_type_data": {}
}
```

Design principles:

- `properties` filtered to resource-relevant keys (existing `_RESOURCE_PROPERTY_KEYS`).
- `bulk_summary` provides bounded summary, never raw pixel/sample data.
- `asset_type_data` preserved as compatibility layer.

## 6. Cross-Asset Reference Deduplication

### 6.1 Reference Table

The envelope `references` array is already deduplicated by `collect_references()`. Each import/export appears exactly once, keyed by `(kind, class_name, object_name, package_path)`.

### 6.2 Domain-Level References

Domain content uses **index references** into the envelope `references` array:

```json
// Envelope — reference table (existing)
"references": [
    {"index": 0, "kind": "import", "class_name": "Texture2D", "object_name": "T_Wood_D", "package_path": "/Game/Textures/T_Wood_D"},
    {"index": 1, "kind": "import", "class_name": "Material", "object_name": "M_Wood", "package_path": "/Game/Materials/M_Wood"}
]

// Domain — uses index
"nodes": [
    {
        "id": "n0",
        "refs": [{"target": 0, "role": "texture_asset"}]
    }
]
```

### 6.3 Rules

1. Domain `refs[].target` must be a valid index into the envelope `references` array.
2. Domain content must NOT contain inline package paths (enforce index usage).
3. Missing references (e.g., empty `package_path`) retain the entry and produce a `MISSING_REFERENCE` diagnostic.
4. Cycle-safe: the reference table is a flat array; cycles are impossible.

### 6.4 Validator Rule

The validator must check all `refs[].target` across all domain content structures:

```python
def _collect_all_refs(content: dict) -> list[tuple[str, int]]:
    """Collect all (context_id, target_index) pairs from domain content."""
    refs = []
    # Graph domain: nodes[].refs
    for node in content.get("nodes", []):
        for ref in node.get("refs", []):
            refs.append((f"node:{node.get('id', '?')}", ref.get("target", -1)))
    # Structured domain: summary.materials[].ref
    for mat in content.get("summary", {}).get("materials", []):
        refs.append((f"material:{mat.get('slot', '?')}", mat.get("ref", -1)))
    # Resource domain: refs at top level (if present)
    for ref in content.get("refs", []):
        refs.append(("resource", ref.get("target", -1)))
    return refs

def _validate_refs_indices(content: dict, references: list) -> list[str]:
    """Check that all domain refs[].target are valid reference indices."""
    errors = []
    max_idx = len(references) - 1
    for context, idx in _collect_all_refs(content):
        if not isinstance(idx, int) or idx < 0 or idx > max_idx:
            errors.append(f"Invalid reference index {idx} in {context}")
    return errors
```

## 7. Coverage and Diagnostics

### 7.1 Coverage States

| State | Meaning | When used |
|-------|---------|-----------|
| `partial` | Some fields available | Extractor parsed only some expected fields |
| `unavailable` | Completely unavailable | Native payload cannot be parsed (opaque class) |
| `truncated` | Bounded truncation | Large data truncated (e.g., DataTable row limit) |

### 7.2 Per-Domain Coverage Scopes

**Graph domain:**
- `graph_metadata` — always available
- `asset_type_data` — available if present
- `graphs` — available if present
- (Future: `nodes`, `edges`, `control_flow`, `data_flow`)

**Structured domain:**
- `structured_metadata` — always available
- `asset_type_data` — available if present
- `skeleton_data` — only for skeleton/anim types
- `row_data` — only for DataTable/CurveTable
- (Future: `summary`)

**Resource domain:**
- `resource_metadata` — always available
- `resource_properties` — available if present
- `asset_type_data` — available if present
- (Future: `bulk_summary`)

### 7.3 Coverage Expression

```json
// All scopes complete — coverage omitted
{}

// Some scopes unavailable
"coverage": {
    "scopes_expected": 4,
    "scopes_available": 3,
    "scopes_unavailable": ["skeleton_data"],
    "notes": "Skeleton reference not present in export"
}
```

Rules:

- Coverage omission = all applicable scopes complete.
- Field applicable + coverage non-complete + field missing = `unknown`.
- Field applicable + coverage complete + field missing = naturally empty or nonexistent.
- JSON `null` = confirmed runtime `null` only.

### 7.4 Diagnostics

- Domain extractors produce diagnostics with domain prefixes: `GRAPH_*`, `STRUCT_*`, `RESOURCE_*`.
- Common diagnostics (e.g., `MISSING_REFERENCE`, `UNKNOWN_TYPE`) have no prefix.
- Diagnostic buffer self-truncation must mark `diagnostics` scope as `truncated`.

## 8. Size and Loss Limits

### 8.1 Prohibited in Standard Output

| Data type | Standard | Debug | Limit method |
|-----------|----------|-------|-------------|
| Vertex/index arrays | ❌ | Bounded summary | `vertex_count` + hash |
| Weights/skin binding | ❌ | Bounded summary | `bone_count` + hash |
| Texture pixels | ❌ | Bounded summary | `dimensions` + `format` + hash |
| Audio samples | ❌ | Bounded summary | `duration` + `sample_rate` + hash |
| DataTable rows | ❌ | Bounded summary | `row_count` + hash |
| Node coordinates | ❌ | ✅ Allowed | debug evidence only |
| Raw GUIDs | ❌ | ✅ Allowed | debug evidence only |

### 8.2 Bounded Summary Format

`$bounded` is a value-level wrapper used wherever a domain field would otherwise contain a large payload. It replaces the raw value, not the containing object.

```json
{
    "$bounded": {
        "type": "array",
        "count": 12000,
        "original_bytes": 48000,
        "sha256": "a1b2c3...",
        "preview": []
    }
}
```

Example usage in domain content:

```json
{
    "row_data": {
        "$bounded": {
            "type": "array",
            "count": 5000,
            "original_bytes": 200000,
            "sha256": "...",
            "preview": []
        }
    }
}
```

Rules:

- `$bounded` must produce corresponding `truncated` coverage and stable diagnostic.
- `preview` max 10 elements; excess omitted.
- `sha256` computed over complete original data for cross-version consistency.
- Graph, Node, Pin, control flow, data flow must NOT be truncated solely for standard output length.

### 8.3 Safety Limit Triggers

When parser safety limits (recursion depth, node count cap) trigger:

- Produce `truncated` coverage.
- Delete all dangling references to trimmed objects.
- Produce `LIMIT_TRIGGERED` diagnostic.

## 9. Test Fixtures and Acceptance

### 9.1 Test Layers

| Layer | Purpose | Status |
|-------|---------|--------|
| Schema compliance | Envelope structure correct | ✅ Existing |
| Semantic validation | ID uniqueness, ref closure, edge direction | ✅ Existing |
| Projection invariant | `project_debug(debug) == standard` | ✅ Existing |
| Domain extractors | Per-domain content fields correct | ❌ All skipped |
| Domain validators | Per-domain content rules | ❌ Not implemented |
| Collision guard | Envelope keys not overwritten | ❌ Not implemented |
| Reference dedup | Domain uses index refs | ❌ Not implemented |
| Size limits | `$bounded` summary correct | ❌ Not implemented |

### 9.2 New Tests

**Domain extractor tests (unskip + extend):**
- `test_graph_extractor_material` — Material produces expected keys
- `test_structured_extractor_static_mesh` — StaticMesh produces expected keys
- `test_resource_extractor_texture` — Texture2D produces expected keys

**Domain validator tests:**
- `test_graph_validator_rejects_missing_metadata`
- `test_structured_validator_accepts_valid_content`
- `test_resource_validator_rejects_negative_serial_size`

**Collision guard test:**
- `test_content_collision_raises` — extractor returning `{"format": "bad"}` raises `ValueError`

**Reference index validation test:**
- `test_domain_refs_use_valid_indices` — `refs[].target` must be valid index

### 9.3 Real Asset Fixtures

| Family | Fixture asset | Source |
|--------|--------------|--------|
| graph | `M_Wood_Walnut.uasset` (Material) | StarterContent |
| graph | `Starter_Background_Cue.uasset` (SoundCue) | StarterContent |
| structured | `SM_Chair.uasset` (StaticMesh) | StarterContent |
| structured | `SK_Mannequin.uasset` (Skeleton) | Mannequin |
| resource | `T_Wood_D.uasset` (Texture2D) | StarterContent |

Acceptance assertions:

- Each fixture passes `validate_semantic_document()` with zero errors.
- Each fixture `status.parse` is not `failed`.
- Each fixture coverage/content fields match expected snapshot.
- Standard output contains no `$bounded` (normal parsing should not trigger truncation).

## 10. Documentation Structure

### 10.1 File Layout

```
docs/formats/uasset/
├── semantic-json.md          # Common envelope doc (existing)
├── graph-domain.md           # Graph domain content model
├── structured-domain.md      # Structured domain content model
└── resource-domain.md        # Resource domain content model
```

### 10.2 Per-Domain Doc Template

Each domain doc covers:

1. **Applicable asset types** — which `asset_type` values activate this domain
2. **Required fields** — field path, type, description
3. **Optional fields** — field path, type, description
4. **Reference rules** — how domain uses reference table indices
5. **Coverage scopes** — scope name, applicable condition, description
6. **Diagnostic codes** — code, severity, description
7. **Size limits** — which data uses `$bounded`, debug evidence limits
8. **Example output** — complete JSON example for a representative asset

### 10.3 Design Spec

This design document lives at:

```
docs/superpowers/specs/2026-08-13-non-blueprint-semantic-design.md
```

## 11. Implementation Boundaries

### 11.1 What This Issue Defines

- Architecture decisions (sections 3–4)
- Content model skeletons (section 5)
- Reference dedup rules (section 6)
- Coverage/diagnostics model (section 7)
- Size/loss limits (section 8)
- Test and documentation structure (sections 9–10)

### 11.2 What Subsequent Issues Implement

- #554 — Blueprint domain extractor (uses `blueprint_semantic`, not this envelope)
- #555 — Animation Blueprint domain extractor
- #556 — Material node domain extractor (graph family)
- #557 — Other UAsset asset extractors (structured + resource families)

### 11.3 One-Shot Replacement Rule

When an asset family is accepted for implementation:

- Remove its superseded output path, schema/tests, examples, and documentation together.
- Do not design or retain a legacy output adapter, dual-write path, compatibility flag, or old-schema fallback.

## 12. Constraints

- **Zero runtime dependencies** — no `jsonschema` or other third-party packages in production.
- **Read-only** — parse only; no modification or writing.
- **Unbaked/editor-saved assets only** — cooked assets have graph data stripped.
- **Standard output never enumerates** vertices, indices, skin weights, texture pixels, or audio samples.
- **Unknown/unsupported classes** must report `opaque` or limited coverage, not fabricated semantics.
- **Deterministic output** — same input, parser version, and configuration produce byte-identical output.
