# Material Semantic JSON Extension Design

> **Status: implemented current-state history for v0.5.5; future target superseded.** Verify implementation claims in source/tests. New architecture work follows [`../2026-08-26-package-first-uasset-parser-refactor.md`](../2026-08-26-package-first-uasset-parser-refactor.md), where material semantics are attached to an object inside a package document.

> Issue: [#556](https://github.com/soatori/uasset_read/issues/556)
> Builds on: [#551](https://github.com/soatori/uasset_read/issues/551) (common infrastructure — CLOSED)
> Date: 2026-08-15
> Status: Implemented on `dev-0.5.5`
> Anchor: Unreal Engine 5.8.0

This document records the accepted design and its pre-implementation baseline.
The implementation now lives in `semantic/material/`, `ir_builder.py`, the
material schema/validator, and the corresponding core and semantic tests.

## 1. Goal

Define semantic JSON output for Material (`UMaterial`) and MaterialInstance (`UMaterialInstance`) assets, building on the common infrastructure established by #551.

The Material semantic JSON must:
- Capture material expressions (nodes) with typed inputs/outputs and semantic descriptions
- Resolve data-flow connections between expressions
- Capture material properties (domain, blend mode, shading model, usage flags)
- Capture MaterialInstance parameters (scalar/vector/texture/static switch)
- Output diagnostics for compile errors and opaque/partial data — no fabricated semantics

## 2. Background

### 2.1 Common Infrastructure (#551)

#551 established:
- `PackageIR` as the unified IR with domain-specific top-level fields (`blueprint`, `animation`)
- `standard` / `debug` isomorphic projection: `project_debug(debug) == standard`
- Schema Draft 2020-12 with `package.schema.json`, `additionalProperties: false`
- Partial/opaque with diagnostics — no data loss, no fabricated semantics
- JSON renderer with conditional domain sections (`_blueprint_to_dict`, `_anim_*_to_dict`)

### 2.2 Pre-Implementation Material Parsing State

The following table is retained as the historical baseline that motivated the
implementation; it does not describe the current repository state.

| Layer | What exists | Gap |
|-------|-------------|-----|
| Object model (`objects/exports/material.py`) | `UMaterial` (domain, blend_mode, expressions list via tagged properties), `UMaterialInstance` (parent, scalar/vector/texture/static_switch params, base_property_overrides) | No semantic IR, no data-flow resolution |
| Asset type parsers (`parsers/asset_types/material*.py`) | Opaque stubs (`make_opaque_stub`) — metadata only, not parsing `UMaterial::Serialize` native layout | FMaterialInput structs decode as opaque; FExpressionInput cross-refs not resolved |
| Binary handlers (`parsers/binary_or_native_handlers.py`) | `_parse_material_input` (FMaterialInput), `_parse_expression_output` (FExpressionOutput) | Handlers registered with "F"-prefixed names; actual struct types in file lack "F" prefix; no handler for `ExpressionInput` |
| Graph parser (`graph/parser.py`) | `MaterialGraph` in `EDGRAPH_CLASS_NAMES` — would be picked up if present | No material-specific graph semantics |
| IR / Renderer | `PackageIR` has `blueprint`, `animation`; JSON renderer has domain `_to_dict` methods | No `MaterialIR`, no `material` field, no schema section, no renderer method |
| Schema (`schemas/package.schema.json`) | Blueprint/Anim sections, `additionalProperties: false` | No `MaterialData` $def, no top-level `material` property |

### 2.3 Sibling Issues

#554 (Blueprint semantic JSON), #555 (AnimBlueprint semantic JSON), and #556 are
implemented on `dev-0.5.5`. The shared graph-domain patterns established by
these issues are now used by their respective semantic extractors.

## 3. Approach Decision: Tagged Property Aggregation

### 3.1 Options Considered

| Aspect | Approach A: Tagged Property Aggregation | Approach B: Full Native Serialization |
|--------|----------------------------------------|---------------------------------------|
| MaterialExpression properties | Already parsed via tagged properties (separate exports) | Same — expressions are separate exports, not in native layout |
| Data-flow connections (FExpressionInput) | Present as binary struct data (36B), needs handler fix | Same data, no additional source |
| Material channel inputs (FMaterialInput) | Present as binary struct data (44B), needs handler fix | Same data |
| Material properties (BlendMode, Domain, etc.) | Tagged properties | Same |
| MaterialInstance parameters | Already extracted by UMaterialInstance object model | Same |
| Shader compilation data (shader maps) | Not available (opaque) | Would parse `SerializeInlineShaderMaps` — complex, version-dependent, typically empty in editor-saved assets |
| Complexity | Small: fix 2 binary handler registrations + add MaterialIR + schema + renderer | High: implement full `UMaterial::Serialize` native layout parser |
| Risk | Low — extends existing patterns | High — version-dependent, explicitly avoided by current parsers |

### 3.2 Decision: Approach A

**Approach A (Tagged Property Aggregation)** is selected because:

1. **MaterialExpression objects are separate exports** already parsed via tagged properties — no native serialization needed.
2. **Data-flow connection data is present** as `FExpressionInput` binary structs (36 bytes: Expression PackageIndex + OutputIndex + InputName + Mask) — currently opaque only because no handler is registered for `ExpressionInput` struct type.
3. **Material channel inputs** (`FMaterialInput` / `ColorMaterialInput` / `ScalarMaterialInput`) are present as binary structs (44 bytes) — currently opaque only because handlers are registered with "F"-prefixed names that don't match the actual struct types.
4. **`UMaterial::Serialize` native layout** (Approach B) mainly adds shader map data via `SerializeInlineShaderMaps`, which is: (a) complex and version-dependent, (b) typically empty/minimal in editor-saved (unbaked) assets (our target), (c) not required by the acceptance criteria.
5. **Ponytail principle**: simplest solution that covers the acceptance criteria. Approach B adds significant complexity for marginal gain.

### 3.3 Implementation Checklist

The following design steps have been delivered through the current semantic
pipeline; filenames below are retained as the original implementation plan.

1. Fix binary handler registration for `ExpressionInput` and `MaterialInput` variants (without "F" prefix)
2. Add `MaterialIR` + sub-IR dataclasses to `models/ir.py`
3. Add `_build_material_ir` to `ir_builder.py`
4. Add `material` field to `PackageIR`
5. Add `MaterialData` $def to `package.schema.json`
6. Add `_material_to_dict` to `json_renderer.py`

All changes extend existing patterns — no new parsing infrastructure.

## 4. Design

### 4.1 MaterialIR Architecture

New IR types in `models/ir.py`, following the `BlueprintIR` / `AnimationDataIR` pattern:

```
PackageIR
├── material: MaterialIR | None          ← NEW
├── blueprint: BlueprintIR | None       (existing)
└── animation: AnimationDataIR | None   (existing)
```

#### MaterialIR

```python
@dataclass
class MaterialIR:
    """Material semantic data (top-level on PackageIR)."""
    material_type: str                    # "Material" | "MaterialInstance"
    properties: dict                      # domain, blend_mode, shading_model, usage_flags decoded
    expressions: list[MaterialExpressionIR]
    material_inputs: list[MaterialInputIR]    # Channel inputs — Material only
    parameters: dict | None                  # scalar/vector/texture/static_switch — Instance only
    base_property_overrides: dict | None     # Instance only
    parent: str | None                        # Parent material path — Instance only
    data_flow: list[dict]                     # Resolved connections
```

#### MaterialExpressionIR

```python
@dataclass
class MaterialExpressionInputIR:
    """An input on a material expression, with resolved data-flow connection."""
    input_name: str
    source_expression_guid: str | None   # Resolved from FExpressionInput.Expression PackageIndex
    source_output_index: int
    mask: int = 0
    mask_r: int = 0
    mask_g: int = 0
    mask_b: int = 0
    mask_a: int = 0

@dataclass
class MaterialExpressionOutputIR:
    """An output on a material expression."""
    output_name: str = ""
    mask: int = 0
    mask_r: int = 0
    mask_g: int = 0
    mask_b: int = 0
    mask_a: int = 0

@dataclass
class MaterialExpressionIR:
    """A single material expression (node in the material graph)."""
    expression_guid: str                  # MaterialExpressionGuid (32-char hex)
    expression_class: str                 # e.g. "MaterialExpressionMultiply"
    expression_type: str | None           # Semantic: "constant"|"parameter"|"operator"|"texture_sample"|"input"|"comment"
    inputs: list[MaterialExpressionInputIR]
    outputs: list[MaterialExpressionOutputIR]
    parameter: dict | None               # {name, value} for parameter expressions
    constant_value: Any | None            # For constant expressions
    editor_position: dict | None         # {"x": int, "y": int}
    description: str | None
```

#### MaterialInputIR

```python
@dataclass
class MaterialInputIR:
    """A material channel input (e.g. BaseColor, Roughness) with resolved expression ref."""
    input_name: str                       # e.g. "BaseColor", "Roughness", "EmissiveColor"
    source_expression_guid: str | None    # Resolved from FMaterialInput.Expression PackageIndex
    source_output_index: int
    mask: int = 0
    mask_r: int = 0
    mask_g: int = 0
    mask_b: int = 0
    mask_a: int = 0
```

### 4.2 Binary Handler Fixes

**File**: `src/uasset_read/parsers/binary_or_native_handlers.py`

#### Problem

Binary handlers are registered with "F"-prefixed struct type names, but the actual `struct_type` in the file data does NOT have the "F" prefix:

| Handler registered as | Actual struct_type in file | Match? |
|------------------------|---------------------------|--------|
| `FMaterialInput` | `MaterialInput` | No |
| `FColorMaterialInput` | `ColorMaterialInput` | No |
| `FScalarMaterialInput` | `ScalarMaterialInput` | No |
| `FVectorMaterialInput` | `VectorMaterialInput` | No |
| `FVector2MaterialInput` | `Vector2MaterialInput` | No |
| *(no handler)* | `ExpressionInput` | No |

#### Fix 1: Normalize "F" prefix in handler lookup

The chosen approach: normalize the lookup in `_parse_struct_binary` to try both `struct_type` and `f"F{struct_type}"` when looking up handlers. This is a single-point fix that handles all current and future cases without duplicating handler entries.

In `binary_or_native_handlers.py`, the handler dict keeps its existing "F"-prefixed keys. The lookup in `_parse_struct_binary` changes from:

```python
handler = BINARY_OR_NATIVE_HANDLERS.get(struct_type)
```

to:

```python
handler = BINARY_OR_NATIVE_HANDLERS.get(struct_type) or BINARY_OR_NATIVE_HANDLERS.get(f"F{struct_type}")
```

#### Fix 2: Add `ExpressionInput` handler

New function `_parse_expression_input` in `binary_or_native_handlers.py`:

```python
def _parse_expression_input(tag, archive, name_map, export_map, summary):
    """Parse FExpressionInput binary data.

    FExpressionInput format (36 bytes):
    - Expression: int32 (PackageIndex — references a MaterialExpression export)
    - OutputIndex: int32
    - InputName: FName (8 bytes)
    - Mask: int32
    - MaskR: int32
    - MaskG: int32
    - MaskB: int32
    - MaskA: int32
    """
    # ... decode 36 bytes, return dict with Expression PackageIndex
```

Register: `"ExpressionInput": _parse_expression_input`

**UE Source Reference**: `Engine/Source/Runtime/Engine/Public/Materials/MaterialExpression.h:47-79` (FExpressionInput struct)

### 4.3 Data Flow Resolution

In `_build_material_ir` (`ir_builder.py`):

```
1. Scan export_map:
   a. Find Material/MaterialInstance export (the one with b_is_asset=True or object_class matching)
   b. Collect all MaterialExpression* exports

2. Build expression_index → expression_guid mapping:
   - For each MaterialExpression export, extract MaterialExpressionGuid from tagged properties
   - Map: {export_index: expression_guid}

3. For each MaterialExpression export:
   a. Extract MaterialExpressionGuid, expression_class, editor position, description
   b. Classify expression_type from expression_class (see 4.4)
   c. For each ExpressionInput struct property (A, B, etc.):
      - Decode via the new _parse_expression_input handler
      - Resolve Expression PackageIndex → expression_guid via mapping from step 2
   d. Extract Outputs array (already parsed by _parse_expression_output handler)
   e. Extract parameter/constant values from tagged properties

4. For Material channel inputs (Material export only):
   a. For each FMaterialInput struct property (BaseColor, Roughness, etc.):
      - Decode via the fixed _parse_material_input handler
      - Resolve Expression PackageIndex → expression_guid

5. For MaterialInstance parameters:
   a. Reuse existing UMaterialInstance object model data
      (scalar_parameters, vector_parameters, texture_parameters, static_switch_parameters)

6. Build data_flow list:
   - For each resolved ExpressionInput: {source_expression_guid, source_output_index, target_expression_guid, target_input_name}
   - For each resolved MaterialInput: {source_expression_guid, source_output_index, target_expression_guid: "__material__", target_input_name}
   - The literal "__material__" indicates the connection target is the Material itself (channel input), not another expression. This keeps the MaterialDataFlowEntry schema uniform.
```

**PackageIndex resolution** reuses existing infrastructure in `serializers/object_resources.py` (`resolve_class_name`, `PackageIndex`).

### 4.4 Expression Type Classification

Expression type is inferred from the expression class name using prefix matching:

| Class name pattern | expression_type |
|--------------------|----------------|
| `MaterialExpressionConstant*` | `"constant"` |
| `MaterialExpression*Parameter*` | `"parameter"` |
| `MaterialExpressionAdd`, `*Subtract`, `*Multiply`, `*Divide`, `*Power`, `*Lerp`, `*Clamp`, `*Saturate`, `*Abs`, `*Sine`, `*Cosine`, `*Floor`, `*Ceil`, `*Frac`, etc. | `"operator"` |
| `MaterialExpressionTexture*` | `"texture_sample"` |
| `MaterialExpressionTextureCoordinate`, `*VertexColor`, `*CameraPositionWS`, `*ObjectPositionWS`, `*Time`, `*ViewProperty`, etc. | `"input"` |
| `MaterialExpressionComment` | `"comment"` |
| `MaterialExpressionFunctionInput`, `*FunctionOutput` | `"function_io"` |
| `MaterialExpressionReroute`, `*NamedReroute` | `"reroute"` |
| Other | `"unknown"` |

This is a best-effort heuristic classification. Unknown expressions get `"unknown"` — no fabricated semantics.

### 4.5 Material Properties Decoding

Material property enums are stored as integers in tagged properties. Decode to human-readable strings:

| Property | Enum | Values |
|----------|------|--------|
| `MaterialDomain` / `Domain` | EMaterialDomain | `0=Surface`, `1=DeferredDecal`, `2=LightFunction`, `3=Volume`, `4=PostProcess`, `5=UserInterface` |
| `BlendMode` | EBlendMode | `0=Opaque`, `1=Masked`, `2=Translucent`, `3=Additive`, `4=Modulate`, `5=AlphaComposite`, `8=TranslucentColoredTransmittance` |
| `ShadingModel` | EMaterialShadingModel | `0=Unlit`, `1=DefaultLit`, `2=Subsurface`, `3=PreintegratedSkin`, `4=SubsurfaceProfile`, `5=ClearCoatTopCoat`, `6=ThinTranslucent`, `8=SingleLayerWater` |

Usage flags are boolean properties starting with `bUsedWith`:
- `bUsedWithSkeletalMesh`, `bUsedWithClothing`, `bUsedWithStatic`, `bUsedWithLandscape`, `bUsedWithNanite`, `bUsedWithUI`, `bUsedWithParticles`, etc.

Decode tables will be added to `constants.py` (following the `decode_package_flags` pattern).

**UE Source Reference**: `Engine/Source/Runtime/Engine/Public/Materials/Material.h` (EMaterialDomain, EBlendMode, EMaterialShadingModel enums)

### 4.6 Schema

**File**: `schemas/package.schema.json`

Add `material` to top-level properties:
```json
"material": {
  "$ref": "#/$defs/MaterialData",
  "description": "材质语义数据（仅 Material/MaterialInstance 资产存在）"
}
```

New `$defs`:

```json
"MaterialData": {
  "type": "object",
  "required": ["material_type"],
  "properties": {
    "material_type": { "enum": ["Material", "MaterialInstance"] },
    "properties": { "$ref": "#/$defs/MaterialProperties" },
    "expressions": { "type": "array", "items": { "$ref": "#/$defs/MaterialExpressionEntry" } },
    "material_inputs": { "type": "array", "items": { "$ref": "#/$defs/MaterialInputEntry" } },
    "parameters": { "$ref": "#/$defs/MaterialParameters" },
    "base_property_overrides": { "type": "object" },
    "parent": { "type": ["string", "null"] },
    "data_flow": { "type": "array", "items": { "$ref": "#/$defs/MaterialDataFlowEntry" } }
  }
},
"MaterialProperties": {
  "type": "object",
  "properties": {
    "domain": { "type": "string" },
    "blend_mode": { "type": "string" },
    "shading_model": { "type": "string" },
    "usage_flags": { "type": "array", "items": { "type": "string" } }
  }
},
"MaterialExpressionEntry": {
  "type": "object",
  "required": ["expression_guid", "expression_class"],
  "properties": {
    "expression_guid": { "type": "string" },
    "expression_class": { "type": "string" },
    "expression_type": { "type": ["string", "null"] },
    "inputs": { "type": "array", "items": { "type": "object" } },
    "outputs": { "type": "array", "items": { "type": "object" } },
    "parameter": { "type": ["object", "null"] },
    "constant_value": { },
    "editor_position": { "type": ["object", "null"] },
    "description": { "type": ["string", "null"] }
  }
},
"MaterialInputEntry": {
  "type": "object",
  "required": ["input_name"],
  "properties": {
    "input_name": { "type": "string" },
    "source_expression_guid": { "type": ["string", "null"] },
    "source_output_index": { "type": "integer" },
    "mask": { "type": "integer" },
    "mask_r": { "type": "integer" },
    "mask_g": { "type": "integer" },
    "mask_b": { "type": "integer" },
    "mask_a": { "type": "integer" }
  }
},
"MaterialParameters": {
  "type": "object",
  "properties": {
    "scalar": { "type": "object" },
    "vector": { "type": "object" },
    "texture": { "type": "object" },
    "static_switch": { "type": "object" }
  }
},
"MaterialDataFlowEntry": {
  "type": "object",
  "required": ["source_expression_guid", "source_output_index", "target_expression_guid", "target_input_name"],
  "properties": {
    "source_expression_guid": { "type": "string", "description": "Source expression GUID, or \"__material__\" if the source is a material channel input" },
    "source_output_index": { "type": "integer" },
    "target_expression_guid": { "type": "string", "description": "Target expression GUID, or \"__material__\" if the target is the Material itself" },
    "target_input_name": { "type": "string" }
  }
}
```

### 4.7 Rendering

**File**: `src/uasset_read/renderers/json_renderer.py`

Add `_material_to_dict` method following the `_blueprint_to_dict` pattern:

```python
def _material_to_dict(self, material) -> dict[str, Any]:
    d: dict[str, Any] = {"material_type": material.material_type}
    if material.properties:
        d["properties"] = material.properties
    if material.expressions:
        d["expressions"] = [self._material_expression_to_dict(e) for e in material.expressions]
    if material.material_inputs:
        d["material_inputs"] = [self._material_input_to_dict(i) for i in material.material_inputs]
    if material.parameters:
        d["parameters"] = material.parameters
    if material.base_property_overrides:
        d["base_property_overrides"] = material.base_property_overrides
    if material.parent:
        d["parent"] = material.parent
    if material.data_flow:
        d["data_flow"] = material.data_flow
    return d
```

In `_build_data`:
```python
if ir.material is not None:
    data["material"] = self._material_to_dict(ir.material)
```

**Standard/debug projection**: In standard mode, omit null/empty fields and opaque `parse_status`. In debug mode, include all fields including raw struct data. This follows the existing `is_debug` pattern used throughout the renderer.

### 4.8 Markdown Renderer

**File**: `src/uasset_read/renderers/markdown_renderer.py`

Add a Material section to the Markdown output, following the existing Blueprint/Animation section pattern. The section should include:
- Material type and properties summary
- Expression table (guid, class, type, parameter)
- Data-flow connections (if any)
- Parameters (for MaterialInstance)

## 5. Files to Change

| File | Change | Type |
|------|--------|------|
| `src/uasset_read/models/ir.py` | Add `MaterialIR`, `MaterialExpressionIR`, `MaterialExpressionInputIR`, `MaterialExpressionOutputIR`, `MaterialInputIR`; add `material` field to `PackageIR` | New code |
| `src/uasset_read/ir_builder.py` | Add `_build_material_ir`, call from `build_package_ir` | New code |
| `src/uasset_read/parsers/binary_or_native_handlers.py` | Add `_parse_expression_input`; fix handler registration (normalize "F" prefix) | Fix |
| `src/uasset_read/constants.py` | Add `MATERIAL_DOMAIN_MAP`, `BLEND_MODE_MAP`, `SHADING_MODEL_MAP`, `MATERIAL_USAGE_FLAG_NAMES` | New constants |
| `src/uasset_read/renderers/json_renderer.py` | Add `_material_to_dict`, `_material_expression_to_dict`, `_material_input_to_dict`; call from `_build_data` | New code |
| `src/uasset_read/renderers/markdown_renderer.py` | Add Material section | New code |
| `schemas/package.schema.json` | Add `material` top-level property; add `MaterialData` and sub-$defs | Schema |

## 6. Testing Strategy

### 6.1 Unit Tests

- **Binary handler tests**: Test `_parse_expression_input` with mock binary data; test `_parse_material_input` with both "F"-prefixed and non-prefixed struct types
- **IR builder tests**: Test `_build_material_ir` with mock ParseResult containing Material + MaterialExpression exports; verify cross-reference resolution
- **Expression classification tests**: Verify `expression_type` classification for all known MaterialExpression subclasses

### 6.2 Integration Tests

Use real samples from `E:\Develop\lib\Samples`:

| Sample | Type | Verifications |
|--------|------|---------------|
| `M_AnimMan_Default.uasset` | Material (simple: 2 expressions) | Material properties, expressions (Constant, VectorParameter), material_inputs (BaseColor, Roughness), data_flow |
| `M_GridLevel_Background.uasset` | Material (operator: 3 expressions) | ExpressionInput resolution (Multiply A→VectorParameter, B→ScalarParameter), data_flow connections |
| `MI_Neon_White.uasset` | MaterialInstance | Parent, parameters (scalar/vector/texture/static_switch), base_property_overrides |
| `MI_Template_BaseGray_Metal_Animated.uasset` | MaterialInstance | Same as above, different parameter set |

### 6.3 Schema Validation Tests

- Validate all sample outputs against `package.schema.json` using `jsonschema` library
- Verify `additionalProperties: false` is not violated by material data

### 6.4 Standard/Debug Projection Tests

- Verify `project_debug(debug) == standard` contract for material section
- In standard mode: no null/empty fields, no opaque parse_status
- In debug mode: all fields present

## 7. Acceptance Criteria Mapping

| Issue Criterion | How Satisfied |
|-----------------|---------------|
| Draft Material Schema based on/derived from Schema/validator | `MaterialData` $def in `package.schema.json`; schema validation tests |
| Material Expression graphs have typed inputs/outputs and semantic descriptions | `MaterialExpressionIR` with `inputs` (typed via `MaterialExpressionInputIR`), `outputs` (via `MaterialExpressionOutputIR`), `expression_type` semantic classification |
| Shader compilation information and material properties are captured | Material properties: `properties` dict with decoded domain/blend_mode/shading_model/usage_flags. Shader compilation: opaque with diagnostics (honest — not available in editor-saved assets, not fabricated) |
| Material JSON covers all material nodes and their data flow connections | `expressions` list covers all MaterialExpression exports; `data_flow` list covers all resolved ExpressionInput/MaterialInput connections |

## 8. Non-Goals

- **Parse `UMaterial::Serialize` native layout**: Shader maps, inline shader resources, and native serialization are NOT parsed. These are complex, version-dependent, and typically empty in editor-saved (unbaked) assets.
- **Shader decompilation or HLSL output**: Not in scope.
- **Material graph rendering**: The graph is represented as JSON data structures, not visual graph rendering.
- **Material function parsing**: MaterialFunction assets are not in scope for this issue.
- **Cooked material support**: Cooked assets have no editor data (expressions stripped). The parser will output opaque with diagnostics, consistent with #551's partial/opaque contract.

## 9. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Binary handler "F" prefix normalization breaks other struct types | Use a try-both approach: lookup `struct_type` first, then `f"F{struct_type}"` — only affects handler lookup, not struct parsing |
| ExpressionInput PackageIndex references an import (not export) | Handle gracefully: if PackageIndex is negative (import), resolve to import path; if zero or unresolved, output `source_expression_guid: null` with diagnostic |
| MaterialExpression subclass properties not fully extracted | The tagged property parser handles all UPROPERTY fields. Subclass-specific properties (e.g., `R` on Constant, `DefaultValue` on VectorParameter) are already parsed; the IR builder extracts them into `constant_value` / `parameter` fields. |
| Expression type classification misses new UE 5.8 expression types | Unknown expressions get `"unknown"` type — no fabricated semantics. Classification table is extensible. |
| Large material assets with many expressions | Follow the existing graph complexity guard pattern (see `_build_function_graphs_safe` in `ir_builder.py`): skip or summarize if expression count exceeds a threshold (e.g., 900). |

## 10. UE Source References

All format understanding is grounded in UE 5.8 source at `E:\Develop\lib\UnrealEngine`:

| Structure | Source Location |
|-----------|----------------|
| `FExpressionInput` | `Engine/Source/Runtime/Engine/Public/Materials/MaterialExpression.h:47-79` |
| `FExpressionOutput` | `Engine/Source/Runtime/Engine/Public/Materials/MaterialExpression.h:93-112` |
| `FMaterialExpressionCollection` | `Engine/Source/Runtime/Engine/Public/Materials/MaterialExpression.h:124-149` |
| `UMaterialExpression` | `Engine/Source/Runtime/Engine/Public/Materials/MaterialExpression.h:151-` |
| `UMaterial::Serialize` | `Engine/Source/Runtime/Engine/Private/Materials/Material.cpp:2981` |
| `UMaterialInstance` | `Engine/Source/Runtime/Engine/Public/Materials/MaterialInstance.h` |
| `FScalarParameterValue`, `FVectorParameterValue`, `FTextureParameterValue` | `Engine/Source/Runtime/Engine/Public/Materials/MaterialInstance.h:62-276` |
| `FMaterialInstanceBasePropertyOverrides` | `Engine/Source/Runtime/Engine/Public/Materials/MaterialInstanceBasePropertyOverrides.h` |
| EMaterialDomain, EBlendMode, EMaterialShadingModel | `Engine/Source/Runtime/Engine/Public/Materials/Material.h` |
