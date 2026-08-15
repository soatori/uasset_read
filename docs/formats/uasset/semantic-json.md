# Semantic JSON Format

Common JSON contract for `uasset_read` semantic output. Domain schemas compose via `allOf`/`$ref` with this schema.

## CLI Usage

### Standard Mode (Default)

```bash
python run.py --json file.uasset
```

Produces deterministic JSON output with the default `standard` output level, which filters UI properties and empty fields.

### Debug Mode with Evidence

```bash
python run.py --json --output-level debug file.uasset
```

Preserves all `evidence` entries for debugging. Standard mode strips these entries.

### Include `$schema` URI

```bash
python run.py --json --schema file.uasset
```

Adds the `$schema` field pointing to the JSON Schema at `schemas/semantic.schema.json`.

## Python API

### Standard Output

```python
from uasset_read.core import parse_single

output = parse_single(
    "path/to/file.uasset",
    format="json",
    output_level="standard",
)
```

### Debug Output

```python
from uasset_read.core import parse_single

output = parse_single(
    "path/to/file.uasset",
    format="json",
    output_level="debug",
)
```

## Common Envelope Structure

All semantic JSON documents share this structure:

```json
{
  "format": "uasset_read.asset_semantic",
  "format_version": "1.0",
  "mode": "standard",
  "asset_type": "blueprint",
  "asset": {
    "package": "/Game/Blueprints/BP_Foo",
    "name": "BP_Foo"
  },
  "status": {
    "parse": "complete",
    "representation": "full"
  }
}
```

### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `format` | `const` | Yes | Always `"uasset_read.asset_semantic"` |
| `format_version` | `const` | Yes | Always `"1.0"` |
| `mode` | `string` | Yes | `"standard"` or `"debug"` |
| `asset_type` | `string` | Yes | Normalized type discriminator (see Asset Type Resolution) |
| `asset` | `object` | Yes | Asset metadata (see below) |
| `status` | `object` | Yes | Parse and representation status (see Status Model) |
| `references` | `array` | No | Import/export reference entries |
| `content` | `object` | No | Staging area for domain extension fields (promoted to top-level by renderer) |
| `coverage` | `object` | No | Semantic coverage report |
| `diagnostics` | `array` | No | Deduplicated diagnostic messages |
| `evidence` | `array` | No | Debug-only evidence entries (stripped in standard mode) |

## Asset Object

The `asset` object contains identity metadata:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `package` | `string` | Yes | Package path (e.g., `/Game/Blueprints/BP_Foo`) |
| `name` | `string` | Yes | Object name (e.g., `BP_Foo`) |
| `generated_class` | `string` | No | UE class name when `asset_type` is `"unknown"` |

## Status Model

The `status` object has two independent dimensions:

| Field | Values | Description |
|-------|--------|-------------|
| `parse` | `"complete"`, `"partial"`, `"failed"` | How well the asset was parsed |
| `representation` | `"full"`, `"partial"`, `"opaque"` | How much semantic content is available |

### Status Matrix

| parse | representation | Meaning |
|-------|----------------|---------|
| `complete` | `full` | Fully parsed, full semantic content |
| `complete` | `partial` | Fully parsed but some content unavailable |
| `partial` | `partial` | Partially parsed with partial content |
| `partial` | `opaque` | Partially parsed, content not interpretable |
| `failed` | `opaque` | Parse failed, no semantic content |

**Note:** `representation: "opaque"` also occurs when the asset type is unknown or when a known type has no registered domain extractor.

## Optional Fields

### References

Array of import/export reference entries:

```json
{
  "references": [
    {
      "index": 0,
      "kind": "import",
      "class_name": "Texture2D",
      "object_name": "T_MyTexture",
      "package_path": "/Game/Textures/T_MyTexture"
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `index` | `integer` | Yes | Import/export table index |
| `kind` | `"import"` or `"export"` | Yes | Reference type |
| `class_name` | `string` | Yes | UE class name |
| `object_name` | `string` | Yes | Object name |
| `package_path` | `string` | No | Package path (for imports) |

**Note:** Reference closure filtering is not yet implemented. Currently, all import and export references are included regardless of reachability from the primary asset. This will be addressed when domain extensions (#554-#557) define which references are semantically reachable.

### Coverage

Reports semantic coverage (scopes expected vs. available):

```json
{
  "coverage": {
    "scopes_expected": 5,
    "scopes_available": 3,
    "scopes_unavailable": ["editor_only_properties", "deprecated_data"],
    "notes": ""
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `scopes_expected` | `integer` | Yes | Total number of semantic scopes expected |
| `scopes_available` | `integer` | Yes | Number of scopes with available content |
| `scopes_unavailable` | `array[string]` | No | Names of unavailable scopes |
| `notes` | `string` | No | Additional notes |

### Diagnostics

Array of deduplicated diagnostic messages:

```json
{
  "diagnostics": [
    {
      "severity": "warning",
      "code": "PARTIAL_PARSE",
      "message": "Asset 'BP_Foo' was only partially parsed"
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `severity` | `"error"`, `"warning"`, `"info"` | Yes | Diagnostic severity |
| `code` | `string` | Yes | Unique diagnostic code |
| `message` | `string` | Yes | Human-readable message |

**Note:** Diagnostics are deduplicated and bounded to a maximum of 100 entries. The validator requires that assets with `representation: "opaque"` must have at least one diagnostic.

### Evidence (Debug Only)

Debug-only evidence entries. Stripped in standard mode:

```json
{
  "evidence": [
    {
      "key": "asset_class",
      "value": "BlueprintGeneratedClass"
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key` | `string` | Yes | Evidence key |
| `value` | `any` | No | Evidence value |

## Asset Type Resolution

UE class names are mapped to normalized type strings:

| UE Class | Normalized Type |
|----------|-----------------|
| `Material` | `material` |
| `MaterialInstance` | `material` |
| `MaterialInstanceConstant` | `material` |
| `MaterialInstanceDynamic` | `material` |
| `Texture2D` | `texture` |
| `TextureCube` | `texture` |
| `StaticMesh` | `static_mesh` |
| `SkeletalMesh` | `skeletal_mesh` |
| `Skeleton` | `skeleton` |
| `AnimSequence` | `anim_sequence` |
| `AnimMontage` | `anim_montage` |
| `DataTable` | `data_table` |
| `CurveTable` | `curve_table` |
| `SoundCue` | `sound_cue` |
| `SoundWave` | `sound_wave` |
| `NiagaraSystem` | `niagara_system` |
| `NiagaraEmitter` | `niagara_emitter` |
| `NiagaraScript` | `niagara_script` |
| `BlueprintGeneratedClass` | `blueprint` |
| `AnimBlueprintGeneratedClass` | `anim_blueprint` |

### Unknown Types

Unknown UE classes emit:
- `asset_type: "unknown"`
- `asset.generated_class` with the original UE class name
- `evidence` entry with `key: "asset_class"` and the raw class name

### Unregistered Asset Opaque Behavior

Assets with known types but no registered domain extractor are emitted with `representation: "opaque"`. The builder adds an `info` diagnostic with code `NO_EXTRACTOR`. This ensures semantic coverage honesty: without an extractor, the asset's domain content cannot be interpreted.

## Standard/Debug Projection

The projection is idempotent: `project_semantic(ir, ir.mode)` returns equivalent IR.

- **Standard mode**: Strips all `evidence` entries (debug-only extension fields are not yet implemented)
- **Debug mode**: Preserves all `evidence` entries for debugging

```python
from uasset_read.semantic.projection import project_semantic

# Standard projection
standard = project_semantic(debug_ir, "standard")
assert standard.evidence == ()

# Debug passthrough
debug = project_semantic(standard_ir, "debug")
assert debug.evidence == original_evidence
```

## Extension Points

Domain schemas compose via `allOf`/`$ref` with the common schema. The top-level object uses `additionalProperties: true` to allow domain fields.

### Extension Registry

Register domain extractors for UE class names:

```python
from uasset_read.semantic.extensions import register_extension

def my_extractor(export_ir, semantic_ir):
    # Add domain-specific content to semantic_ir.content
    return semantic_ir

register_extension("MyCustomClass", my_extractor)
```

### Reference Scope (#551)

`references` currently contains the **full import and export tables** of the
package, sorted deterministically by `(kind, index)`. The table is complete
but **not filtered**: reachable-reference closure (only objects semantically
reachable from the primary asset) requires domain-extractor reachability data
and is formally deferred to #554–#557.

Until then, consumers must not interpret `references` as the primary asset's
dependency closure. This scope is pinned by
`tests/core/test_semantic_determinism.py::TestReferenceScopePinned`.

## Determinism Guarantees

Output is byte-identical across processes and `PYTHONHASHSEED` values:

- **UTF-8 encoding** with `ensure_ascii=False`
- **LF line endings** (no `\r\n`)
- **Fixed key ordering** via `canonical_sort()`
- **`allow_nan=False`** in JSON encoding
- **Deterministic sort** for all dict keys using predefined orderings
- **Total array ordering** — no array order depends on input order:
  `diagnostics` by `(severity, code, message)`, `references` by
  `(kind, index, class_name, object_name, package_path)`, `evidence` by
  `(key, canonical value)`

### Canonical Key Order

Top-level keys are ordered:
1. `format`
2. `format_version`
3. `mode`
4. `asset_type`
5. `asset`
6. `status`
7. `references`
8. `content`
9. `coverage`
10. `diagnostics`
11. `evidence`

Sub-objects follow their own canonical orderings.

## JSON Schema

The full Draft 2020-12 schema is implemented at
`src/uasset_read/schemas/semantic.schema.json` and packaged inside the wheel
(`importlib.resources` path `uasset_read/schemas/semantic.schema.json`). Load
it from either a source checkout or an installed package with:

```python
from uasset_read.schema_loader import load_semantic_schema

schema = load_semantic_schema()
```

Behavior and limits:

- `render_semantic_json(ir, include_schema=True)` emits the schema URI as `$schema`;
  by default (`include_schema=False`) no `$schema` key is emitted.
- The schema enforces both modes: in `standard` mode `evidence` must be an empty
  array (the projection strips it); `debug` mode may carry evidence entries.
- `asset.package` and `asset.name` are required non-empty strings — opaque
  fallback documents derive a non-empty package when the header has none.
- Domain-extension fields (#554–#557) are permitted via top-level
  `additionalProperties: true` and are not yet schema-described.
- `EvidenceEntry.value` is intentionally untyped (free-form debug evidence).

## See Also

- [Package Summary](package-summary.md)
- [Import/Export Tables](import-export-tables.md)
- [Blueprint Format](assets/blueprint.md)
