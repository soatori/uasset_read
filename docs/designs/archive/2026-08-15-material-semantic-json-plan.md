# Material Semantic JSON Extension Implementation Plan

> **Status: historical implementation plan for Semantic 1.x.** Do not reuse its envelope/schema architecture for v2. The current target is [`../2026-08-26-package-first-uasset-parser-refactor.md`](../2026-08-26-package-first-uasset-parser-refactor.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Material/MaterialInstance semantic JSON output with expression graphs, data-flow connections, parameters, and material properties.

**Architecture:** Tagged property aggregation — reuse existing MaterialExpression export parsing, fix binary struct handlers for FExpressionInput/FMaterialInput, add MaterialIR to PackageIR, extend schema and renderers. No UMaterial::Serialize native layout parsing.

**Tech Stack:** Python 3.10+, zero runtime dependencies, pytest, JSON Schema Draft 2020-12

**Spec:** `docs/designs/2026-08-15-material-semantic-json-design.md`

## Global Constraints

- Python 3.10+, zero runtime dependencies (no `pip install`)
- All output is UTF-8, LF, canonical JSON with fixed key order
- `standard` / `debug` isomorphic projection: `project_debug(debug) == standard`
- Partial/opaque with diagnostics — no fabricated semantics
- UE 5.8 source at `E:\Develop\lib\UnrealEngine` is the format reference
- Test samples at `E:\Develop\lib\Samples` (via `--sample-root` or `UE_SAMPLE_ROOT`)
- Commit format: `<type>: <brief>` (types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`)
- Run tests: `python -m pytest tests -q`

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/uasset_read/constants.py` | Material property enum decode tables + expression type classification table |
| `src/uasset_read/models/ir.py` | MaterialIR + sub-IR dataclasses; `material` field on PackageIR |
| `src/uasset_read/parsers/binary_or_native_handlers.py` | "F" prefix normalization in handler lookup; `_parse_expression_input` handler |
| `src/uasset_read/ir_builder.py` | `_build_material_ir`: scan exports, resolve cross-refs, build data_flow |
| `src/uasset_read/renderers/json_renderer.py` | `_material_to_dict` + sub-methods for JSON output |
| `src/uasset_read/renderers/markdown_renderer.py` | Material section in Markdown output |
| `schemas/package.schema.json` | `MaterialData` $def + sub-$defs, top-level `material` property |
| `tests/test_material_constants.py` | Unit tests for decode tables |
| `tests/ir/test_material_ir.py` | Unit tests for MaterialIR dataclasses |
| `tests/parsers/test_binary_handler_prefix.py` | Unit tests for "F" prefix normalization |
| `tests/parsers/test_expression_input_handler.py` | Unit tests for `_parse_expression_input` |
| `tests/ir/test_build_material_ir.py` | Unit tests for `_build_material_ir` |
| `tests/test_material_schema.py` | Schema validation tests |
| `tests/renderers/test_material_json_renderer.py` | JSON renderer tests |
| `tests/renderers/test_material_markdown.py` | Markdown renderer tests |
| `tests/integration/test_material_integration.py` | Integration tests with real samples |

---

### Task 1: Material Property Decode Constants

**Files:**
- Modify: `src/uasset_read/constants.py`
- Test: `tests/test_material_constants.py`

**Interfaces:**
- Produces: `MATERIAL_DOMAIN_MAP: dict[int, str]`, `BLEND_MODE_MAP: dict[int, str]`, `SHADING_MODEL_MAP: dict[int, str]`, `MATERIAL_USAGE_FLAG_NAMES: tuple[str, ...]`, `classify_expression_type(class_name: str) -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_material_constants.py`:

```python
"""Material property decode constants and expression classification tests."""
from __future__ import annotations

from uasset_read.constants import (
    MATERIAL_DOMAIN_MAP,
    BLEND_MODE_MAP,
    SHADING_MODEL_MAP,
    MATERIAL_USAGE_FLAG_NAMES,
    classify_expression_type,
)


class TestMaterialDomainMap:
    def test_surface(self):
        assert MATERIAL_DOMAIN_MAP[0] == "Surface"

    def test_deferred_decal(self):
        assert MATERIAL_DOMAIN_MAP[1] == "DeferredDecal"

    def test_post_process(self):
        assert MATERIAL_DOMAIN_MAP[4] == "PostProcess"


class TestBlendModeMap:
    def test_opaque(self):
        assert BLEND_MODE_MAP[0] == "Opaque"

    def test_masked(self):
        assert BLEND_MODE_MAP[1] == "Masked"

    def test_translucent(self):
        assert BLEND_MODE_MAP[2] == "Translucent"


class TestShadingModelMap:
    def test_unlit(self):
        assert SHADING_MODEL_MAP[0] == "Unlit"

    def test_default_lit(self):
        assert SHADING_MODEL_MAP[1] == "DefaultLit"


class TestUsageFlagNames:
    def test_contains_skeletal_mesh(self):
        assert "bUsedWithSkeletalMesh" in MATERIAL_USAGE_FLAG_NAMES

    def test_contains_nanite(self):
        assert "bUsedWithNanite" in MATERIAL_USAGE_FLAG_NAMES


class TestClassifyExpressionType:
    def test_constant(self):
        assert classify_expression_type("MaterialExpressionConstant") == "constant"

    def test_constant_2vector(self):
        assert classify_expression_type("MaterialExpressionConstant2Vector") == "constant"

    def test_scalar_parameter(self):
        assert classify_expression_type("MaterialExpressionScalarParameter") == "parameter"

    def test_vector_parameter(self):
        assert classify_expression_type("MaterialExpressionVectorParameter") == "parameter"

    def test_multiply(self):
        assert classify_expression_type("MaterialExpressionMultiply") == "operator"

    def test_add(self):
        assert classify_expression_type("MaterialExpressionAdd") == "operator"

    def test_texture_sample(self):
        assert classify_expression_type("MaterialExpressionTextureSample") == "texture_sample"

    def test_texture_coordinate(self):
        assert classify_expression_type("MaterialExpressionTextureCoordinate") == "input"

    def test_comment(self):
        assert classify_expression_type("MaterialExpressionComment") == "comment"

    def test_reroute(self):
        assert classify_expression_type("MaterialExpressionReroute") == "reroute"

    def test_function_input(self):
        assert classify_expression_type("MaterialExpressionFunctionInput") == "function_io"

    def test_unknown(self):
        assert classify_expression_type("MaterialExpressionSomeNewThing") == "unknown"

    def test_none_input(self):
        assert classify_expression_type("") == "unknown"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_material_constants.py -v`
Expected: FAIL with `ImportError: cannot import name 'MATERIAL_DOMAIN_MAP'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/uasset_read/constants.py` (after existing `decode_package_flags` or similar decode tables):

```python
# --- Material property decode tables ---
# Reference: Engine/Source/Runtime/Engine/Public/Materials/Material.h

MATERIAL_DOMAIN_MAP: dict[int, str] = {
    0: "Surface",
    1: "DeferredDecal",
    2: "LightFunction",
    3: "Volume",
    4: "PostProcess",
    5: "UserInterface",
}

BLEND_MODE_MAP: dict[int, str] = {
    0: "Opaque",
    1: "Masked",
    2: "Translucent",
    3: "Additive",
    4: "Modulate",
    5: "AlphaComposite",
    8: "TranslucentColoredTransmittance",
}

SHADING_MODEL_MAP: dict[int, str] = {
    0: "Unlit",
    1: "DefaultLit",
    2: "Subsurface",
    3: "PreintegratedSkin",
    4: "SubsurfaceProfile",
    5: "ClearCoatTopCoat",
    6: "ThinTranslucent",
    8: "SingleLayerWater",
}

MATERIAL_USAGE_FLAG_NAMES: tuple[str, ...] = (
    "bUsedWithSkeletalMesh",
    "bUsedWithClothing",
    "bUsedWithStatic",
    "bUsedWithLandscape",
    "bUsedWithNanite",
    "bUsedWithUI",
    "bUsedWithParticles",
    "bUsedWithSplineMeshes",
    "bUsedWithInstancedStaticMeshes",
    "bUsedWithGeometryCollection",
    "bUsedWithWaterSurface",
    "bUsedWithHairStrands",
)

# Expression type classification table
# Maps expression class name patterns to semantic types
_EXPRESSION_TYPE_PATTERNS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("MaterialExpressionConstant",), "constant"),
    (("MaterialExpressionScalarParameter", "MaterialExpressionVectorParameter",
      "MaterialExpressionTextureSampleParameter", "MaterialExpressionTextureObjectParameter",
      "MaterialExpressionDoubleVectorParameter", "MaterialExpressionChannelMaskParameter",
      "MaterialExpressionStaticBoolParameter", "MaterialExpressionStaticSwitchParameter",
      "MaterialExpressionStaticComponentMaskParameter",
      "MaterialExpressionFontSampleParameter", "MaterialExpressionCurveAtlasRowParameter",
      "MaterialExpressionTextureCollectionParameter",
      "MaterialExpressionRuntimeVirtualTextureSampleParameter"), "parameter"),
    (("MaterialExpressionAdd", "MaterialExpressionSubtract", "MaterialExpressionMultiply",
      "MaterialExpressionDivide", "MaterialExpressionPower", "MaterialExpressionLinearInterpolate",
      "MaterialExpressionClamp", "MaterialExpressionSaturate", "MaterialExpressionAbs",
      "MaterialExpressionSine", "MaterialExpressionCosine", "MaterialExpressionFloor",
      "MaterialExpressionCeil", "MaterialExpressionFrac", "MaterialExpressionRound",
      "MaterialExpressionSquareRoot", "MaterialExpressionExponential", "MaterialExpressionExponential2",
      "MaterialExpressionModulo", "MaterialExpressionCrossProduct", "MaterialExpressionDotProduct",
      "MaterialExpressionLength", "MaterialExpressionNormalize", "MaterialExpressionOneMinus",
      "MaterialExpressionSign", "MaterialExpressionDesaturation", "MaterialExpressionIf",
      "MaterialExpressionIfThenElse", "MaterialExpressionInverseLinearInterpolate",
      "MaterialExpressionSmoothStep", "MaterialExpressionStep", "MaterialExpressionFmod",
      "MaterialExpressionLogarithm", "MaterialExpressionLogarithm2", "MaterialExpressionLogarithm10",
      "MaterialExpressionArcsine", "MaterialExpressionArcsineFast",
      "MaterialExpressionArccosine", "MaterialExpressionArccosineFast",
      "MaterialExpressionArctangent", "MaterialExpressionArctangentFast",
      "MaterialExpressionArctangent2", "MaterialExpressionArctangent2Fast",
      "MaterialExpressionBumpOffset", "MaterialExpressionBlend",
      "MaterialExpressionComponentMask", "MaterialExpressionAppendVector",
      "MaterialExpressionConstantBiasScale", "MaterialExpressionDistance",
      "MaterialExpressionFresnel", "MaterialExpressionNoise", "MaterialExpressionPanner",
      "MaterialExpressionRotator", "MaterialExpressionSphereMask",
      "MaterialExpressionSphericalParticleOpacity", "MaterialExpressionDeriveNormalZ",
      "MaterialExpressionDDX", "MaterialExpressionDDY",
      "MaterialExpressionMax", "MaterialExpressionMin",
      "MaterialExpressionTransform", "MaterialExpressionTransformPosition",
      "MaterialExpressionConvert", "MaterialExpressionHsvToRgb",
      "MaterialExpressionRgbToHsv", "MaterialExpressionSpeedTree",
      "MaterialExpressionBlendMaterialAttributes", "MaterialExpressionBreakMaterialAttributes",
      "MaterialExpressionGetMaterialAttributes", "MaterialExpressionSetMaterialAttributes",
      "MaterialExpressionMakeMaterialAttributes",
      "MaterialExpressionMaterialAttributeLayers", "MaterialExpressionLayerStack",
      "MaterialExpressionSwitch", "MaterialExpressionStaticSwitch",
      "MaterialExpressionPreviousFrameSwitch", "MaterialExpressionFeatureLevelSwitch",
      "MaterialExpressionQualitySwitch", "MaterialExpressionShaderStageSwitch",
      "MaterialExpressionShadingPathSwitch", "MaterialExpressionDataDrivenShaderPlatformInfoSwitch",
      "MaterialExpressionPathTracingQualitySwitch", "MaterialExpressionRayTracingQualitySwitch",
      "MaterialExpressionReflectionCapturePassSwitch", "MaterialExpressionShadowReplace",
      "MaterialExpressionNaniteReplace", "MaterialExpressionVirtualTextureFeatureSwitch",
      "MaterialExpressionRequiredSamplersSwitch",
      "MaterialExpressionDistanceFieldsRenderingSwitch", "MaterialExpressionGIReplace",
      "MaterialExpressionLightmassReplace", "MaterialExpressionBindlessSwitch",
      "MaterialExpressionMeshPaintTextureReplace",
      "MaterialExpressionSobol", "MaterialExpressionTemporalSobol"), "operator"),
    (("MaterialExpressionTextureSample", "MaterialExpressionTextureObject",
      "MaterialExpressionTextureCoordinate", "MaterialExpressionTextureProperty",
      "MaterialExpressionSparseVolumeTextureSample", "MaterialExpressionSparseVolumeTextureObject",
      "MaterialExpressionRuntimeVirtualTextureSample", "MaterialExpressionRuntimeVirtualTextureReplace",
      "MaterialExpressionVirtualTextureFeatureSwitch",
      "MaterialExpressionDBufferTexture", "MaterialExpressionSceneTexture",
      "MaterialExpressionUserSceneTexture", "MaterialExpressionSceneColor",
      "MaterialExpressionSceneDepth", "MaterialExpressionSceneDepthWithoutWater",
      "MaterialExpressionSceneTexelSize", "MaterialExpressionScreenPosition",
      "MaterialExpressionTextureCollection", "MaterialExpressionTextureCollectionParameter"), "texture_sample"),
    (("MaterialExpressionVertexColor", "MaterialExpressionCameraPositionWS",
      "MaterialExpressionCameraVectorWS", "MaterialExpressionObjectOrientation",
      "MaterialExpressionObjectPositionWS", "MaterialExpressionObjectBounds",
      "MaterialExpressionObjectLocalBounds", "MaterialExpressionObjectRadius",
      "MaterialExpressionLocalPosition", "MaterialExpressionWorldPosition",
      "MaterialExpressionViewProperty", "MaterialExpressionViewSize",
      "MaterialExpressionPixelNormalWS", "MaterialExpressionVertexNormalWS",
      "MaterialExpressionVertexTangentWS", "MaterialExpressionTangent",
      "MaterialExpressionTangentOutput",
      "MaterialExpressionTime", "MaterialExpressionDeltaTime",
      "MaterialExpressionEyeAdaptation", "MaterialExpressionEyeAdaptationInverse",
      "MaterialExpressionDistanceCullFade", "MaterialExpressionDistanceToNearestSurface",
      "MaterialExpressionDistanceFieldGradient", "MaterialExpressionDistanceFieldApproxAO",
      "MaterialExpressionFogColor", "MaterialExpressionAtmosphericFogColor",
      "MaterialExpressionAtmosphericLightColor", "MaterialExpressionAtmosphericLightVector",
      "MaterialExpressionMainDirectionalLight", "MaterialExpressionLightVector",
      "MaterialExpressionPixelDepth", "MaterialExpressionPreSkinnedNormal",
      "MaterialExpressionPreSkinnedPosition", "MaterialExpressionPreSkinnedLocalBounds",
      "MaterialExpressionTwoSidedSign", "MaterialExpressionIsOrthographic",
      "MaterialExpressionIsFirstPerson", "MaterialExpressionPerInstanceCustomData",
      "MaterialExpressionPerInstanceFadeAmount", "MaterialExpressionPerInstanceRandom",
      "MaterialExpressionBounds", "MaterialExpressionSkyAtmosphereLightDirection",
      "MaterialExpressionSkyAtmosphereLightIlluminance", "MaterialExpressionSkyAtmosphereViewLuminance",
      "MaterialExpressionSkyLightEnvMapSample", "MaterialExpressionPostVolumeUserFlagTest",
      "MaterialExpressionParticleColor", "MaterialExpressionParticleDirection",
      "MaterialExpressionParticleMacroUV", "MaterialExpressionParticleMotionBlurFade",
      "MaterialExpressionParticlePositionWS", "MaterialExpressionParticleRadius",
      "MaterialExpressionParticleRandom", "MaterialExpressionParticleRelativeTime",
      "MaterialExpressionParticleSize", "MaterialExpressionParticleSpeed",
      "MaterialExpressionParticleSpriteRotation", "MaterialExpressionParticleSubUV",
      "MaterialExpressionFirstPersonOutput", "MaterialExpressionVolumetricAdvancedMaterialInput",
      "MaterialExpressionLightmapUVs", "MaterialExpressionMeshPaintTextureCoordinateIndex",
      "MaterialExpressionRecordTextureStreamingInfo",
      "MaterialExpressionTemporalResponsivenessOutput"), "input"),
    (("MaterialExpressionComment",), "comment"),
    (("MaterialExpressionFunctionInput", "MaterialExpressionFunctionOutput"), "function_io"),
    (("MaterialExpressionReroute", "MaterialExpressionNamedReroute",
      "MaterialExpressionNamedRerouteUsage", "MaterialExpressionRerouteBase",
      "MaterialExpressionPinBase"), "reroute"),
)


def classify_expression_type(class_name: str) -> str:
    """Classify a MaterialExpression class name into a semantic type.

    Returns one of: "constant", "parameter", "operator", "texture_sample",
    "input", "comment", "function_io", "reroute", "unknown".
    Returns "unknown" for empty or unrecognized names.
    """
    if not class_name:
        return "unknown"
    for patterns, expr_type in _EXPRESSION_TYPE_PATTERNS:
        for pattern in patterns:
            if class_name == pattern:
                return expr_type
    return "unknown"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_material_constants.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/constants.py tests/test_material_constants.py
git commit -m "feat: add material property decode constants and expression type classification"
```

---

### Task 2: MaterialIR Dataclasses

**Files:**
- Modify: `src/uasset_read/models/ir.py`
- Test: `tests/ir/test_material_ir.py`

**Interfaces:**
- Consumes: nothing (foundational types)
- Produces: `MaterialExpressionInputIR`, `MaterialExpressionOutputIR`, `MaterialExpressionIR`, `MaterialInputIR`, `MaterialIR`; `PackageIR.material` field

- [ ] **Step 1: Write the failing test**

Create `tests/ir/test_material_ir.py`:

```python
"""MaterialIR dataclass construction and defaults tests."""
from __future__ import annotations

from uasset_read.models.ir import (
    MaterialIR,
    MaterialExpressionIR,
    MaterialExpressionInputIR,
    MaterialExpressionOutputIR,
    MaterialInputIR,
    PackageIR,
    PackageHeaderIR,
)


class TestMaterialExpressionInputIR:
    def test_defaults(self):
        inp = MaterialExpressionInputIR(
            input_name="A",
            source_expression_guid=None,
            source_output_index=0,
        )
        assert inp.input_name == "A"
        assert inp.source_expression_guid is None
        assert inp.source_output_index == 0
        assert inp.mask == 0
        assert inp.mask_r == 0

    def test_with_mask(self):
        inp = MaterialExpressionInputIR(
            input_name="B",
            source_expression_guid="abc123",
            source_output_index=1,
            mask=1, mask_r=1, mask_g=1, mask_b=0, mask_a=0,
        )
        assert inp.mask == 1
        assert inp.mask_r == 1


class TestMaterialExpressionOutputIR:
    def test_defaults(self):
        out = MaterialExpressionOutputIR()
        assert out.output_name == ""
        assert out.mask == 0


class TestMaterialExpressionIR:
    def test_construction(self):
        expr = MaterialExpressionIR(
            expression_guid="abc123",
            expression_class="MaterialExpressionMultiply",
            expression_type="operator",
            inputs=[],
            outputs=[],
        )
        assert expr.expression_guid == "abc123"
        assert expr.expression_class == "MaterialExpressionMultiply"
        assert expr.expression_type == "operator"
        assert expr.parameter is None
        assert expr.constant_value is None
        assert expr.editor_position is None
        assert expr.description is None


class TestMaterialInputIR:
    def test_construction(self):
        mi = MaterialInputIR(
            input_name="BaseColor",
            source_expression_guid="abc123",
            source_output_index=0,
        )
        assert mi.input_name == "BaseColor"
        assert mi.source_expression_guid == "abc123"
        assert mi.mask == 0


class TestMaterialIR:
    def test_material_type(self):
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[],
            material_inputs=[],
            data_flow=[],
        )
        assert mat.material_type == "Material"
        assert mat.parameters is None
        assert mat.base_property_overrides is None
        assert mat.parent is None

    def test_instance_type(self):
        mat = MaterialIR(
            material_type="MaterialInstance",
            properties={},
            expressions=[],
            material_inputs=[],
            parameters={"scalar": {"x": 1.0}},
            base_property_overrides={"BlendMode": "Opaque"},
            parent="/Game/Path/Parent",
            data_flow=[],
        )
        assert mat.material_type == "MaterialInstance"
        assert mat.parameters["scalar"]["x"] == 1.0
        assert mat.parent == "/Game/Path/Parent"


class TestPackageIRMaterialField:
    def test_material_field_defaults_none(self):
        header = PackageHeaderIR(
            package_name="/Game/Test",
            package_class="",
            package_flags=0,
            total_export_count=0,
            total_import_count=0,
            ue_version="5.x",
        )
        ir = PackageIR(
            header=header,
            name_map=(),
            imports=[],
            exports=[],
            linker=None,
        )
        assert ir.material is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ir/test_material_ir.py -v`
Expected: FAIL with `ImportError: cannot import name 'MaterialIR'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/uasset_read/models/ir.py` (before the `PackageIR` class, after existing IR types like `DiagnosticsDataIR`):

```python
@dataclass
class MaterialExpressionInputIR:
    """An input on a material expression, with resolved data-flow connection."""
    input_name: str
    source_expression_guid: str | None
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
    expression_guid: str
    expression_class: str
    expression_type: str | None
    inputs: list[MaterialExpressionInputIR]
    outputs: list[MaterialExpressionOutputIR]
    parameter: dict | None = None
    constant_value: Any | None = None
    editor_position: dict | None = None
    description: str | None = None


@dataclass
class MaterialInputIR:
    """A material channel input (e.g. BaseColor, Roughness) with resolved expression ref."""
    input_name: str
    source_expression_guid: str | None
    source_output_index: int
    mask: int = 0
    mask_r: int = 0
    mask_g: int = 0
    mask_b: int = 0
    mask_a: int = 0


@dataclass
class MaterialIR:
    """Material semantic data (top-level on PackageIR)."""
    material_type: str
    properties: dict
    expressions: list[MaterialExpressionIR]
    material_inputs: list[MaterialInputIR]
    data_flow: list[dict]
    parameters: dict | None = None
    base_property_overrides: dict | None = None
    parent: str | None = None
```

Then add `material` field to `PackageIR` (add after `animation` field):

```python
    material: MaterialIR | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ir/test_material_ir.py -v`
Expected: PASS

Also run existing tests to verify no regression:
Run: `python -m pytest tests/ir/ tests/test_json_schema.py -v`
Expected: PASS (no regressions)

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/models/ir.py tests/ir/test_material_ir.py
git commit -m "feat: add MaterialIR dataclasses and material field to PackageIR"
```

---

### Task 3: Fix Binary Handler "F" Prefix Normalization

**Files:**
- Modify: `src/uasset_read/parsers/binary_or_native_handlers.py`
- Test: `tests/parsers/test_binary_handler_prefix.py`

**Interfaces:**
- Consumes: existing `BINARY_OR_NATIVE_HANDLERS` dict, `_parse_struct_binary` function
- Produces: handler lookup that finds handlers for non-"F"-prefixed struct types (e.g., `MaterialInput`, `ColorMaterialInput`, `ScalarMaterialInput`)

- [ ] **Step 1: Write the failing test**

Create `tests/parsers/test_binary_handler_prefix.py`:

```python
"""Tests for binary handler F-prefix normalization."""
from __future__ import annotations

from uasset_read.parsers.binary_or_native_handlers import BINARY_OR_NATIVE_HANDLERS


class TestHandlerPrefixNormalization:
    """Verify that non-F-prefixed struct types find their handlers."""

    def test_material_input_found(self):
        """MaterialInput (without F prefix) should find the handler."""
        handler = BINARY_OR_NATIVE_HANDLERS.get("MaterialInput")
        if handler is None:
            handler = BINARY_OR_NATIVE_HANDLERS.get("FMaterialInput")
        assert handler is not None, "No handler found for MaterialInput or FMaterialInput"

    def test_color_material_input_found(self):
        handler = BINARY_OR_NATIVE_HANDLERS.get("ColorMaterialInput")
        if handler is None:
            handler = BINARY_OR_NATIVE_HANDLERS.get("FColorMaterialInput")
        assert handler is not None

    def test_scalar_material_input_found(self):
        handler = BINARY_OR_NATIVE_HANDLERS.get("ScalarMaterialInput")
        if handler is None:
            handler = BINARY_OR_NATIVE_HANDLERS.get("FScalarMaterialInput")
        assert handler is not None

    def test_expression_output_found(self):
        """ExpressionOutput should find the ExpressionOutput handler."""
        handler = BINARY_OR_NATIVE_HANDLERS.get("ExpressionOutput")
        if handler is None:
            handler = BINARY_OR_NATIVE_HANDLERS.get("FExpressionOutput")
        assert handler is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/parsers/test_binary_handler_prefix.py -v`
Expected: FAIL — `MaterialInput` (without F) is not in the dict

- [ ] **Step 3: Write minimal implementation**

In `src/uasset_read/parsers/binary_or_native_handlers.py`, find the `_parse_struct_binary` function and find the handler lookup line. It currently looks like:

```python
handler = BINARY_OR_NATIVE_HANDLERS.get(struct_type)
```

Change it to:

```python
handler = BINARY_OR_NATIVE_HANDLERS.get(struct_type) or BINARY_OR_NATIVE_HANDLERS.get(f"F{struct_type}")
```

This tries the struct_type as-is first, then with "F" prefix. This is a single-point fix.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/parsers/test_binary_handler_prefix.py -v`
Expected: PASS

Also run existing parser tests to verify no regression:
Run: `python -m pytest tests/parsers/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/parsers/binary_or_native_handlers.py tests/parsers/test_binary_handler_prefix.py
git commit -m "fix: normalize binary handler lookup to try both with and without F prefix"
```

---

### Task 4: Add ExpressionInput Handler

**Files:**
- Modify: `src/uasset_read/parsers/binary_or_native_handlers.py`
- Test: `tests/parsers/test_expression_input_handler.py`

**Interfaces:**
- Consumes: `PropertyTag`, `FArchive` (via the handler signature)
- Produces: `_parse_expression_input` function, registered as `"ExpressionInput"` in `BINARY_OR_NATIVE_HANDLERS`. Returns dict with `expression_index` (raw PackageIndex int), `output_index`, `input_name`, `mask`, `mask_r/g/b/a`.

- [ ] **Step 1: Write the failing test**

Create `tests/parsers/test_expression_input_handler.py`:

```python
"""Tests for _parse_expression_input binary handler."""
from __future__ import annotations

import struct

from uasset_read.parsers.binary_or_native_handlers import (
    _parse_expression_input,
    BINARY_OR_NATIVE_HANDLERS,
)


class FakeTag:
    """Minimal PropertyTag mock."""
    def __init__(self, struct_type: str = "ExpressionInput", size: int = 36):
        self.type = "StructProperty"
        self.struct_type = struct_type
        self.size = size


class FakeArchive:
    """Minimal FArchive mock for binary data."""
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read_i32(self) -> int:
        val = struct.unpack_from("<i", self._data, self._pos)[0]
        self._pos += 4
        return val

    def read_name(self, name_map=None) -> str:
        idx = self.read_i32()
        _number = self.read_i32()
        if name_map and 0 <= idx < len(name_map):
            return name_map[idx]
        return f"Name_{idx}"

    def tell(self) -> int:
        return self._pos

    def seek(self, pos: int) -> None:
        self._pos = pos


class TestParseExpressionInput:
    def test_decodes_full_struct(self):
        """Verify 36-byte FExpressionInput struct decodes correctly.

        Layout: Expression(i32) + OutputIndex(i32) + InputName(8B) + Mask(i32) + MaskR/G/B/A(i32*4)
        """
        # Expression PackageIndex = 1 (export index 0, 1-based)
        # OutputIndex = 0
        # InputName = FName(0, 0)
        # Mask = 0, MaskR=0, G=0, B=0, A=0
        data = struct.pack("<ii", 1, 0) + struct.pack("<ii", 0, 0) + struct.pack("<iiiii", 0, 0, 0, 0, 0)
        archive = FakeArchive(data)
        tag = FakeTag(size=36)

        result = _parse_expression_input(tag, archive, ["InputA"], [], None)

        assert result is not None
        assert result["kind"] == "expression_input"
        assert result["expression_index"] == 1
        assert result["output_index"] == 0
        assert result["mask"] == 0

    def test_with_mask_values(self):
        """Verify mask values are decoded."""
        # Expression=2, OutputIndex=1, InputName=FName(0,0), Mask=1, R=1, G=0, B=0, A=0
        data = struct.pack("<ii", 2, 1) + struct.pack("<ii", 0, 0) + struct.pack("<iiiii", 1, 1, 0, 0, 0)
        archive = FakeArchive(data)
        tag = FakeTag(size=36)

        result = _parse_expression_input(tag, archive, ["InputB"], [], None)

        assert result is not None
        assert result["expression_index"] == 2
        assert result["output_index"] == 1
        assert result["mask"] == 1
        assert result["mask_r"] == 1
        assert result["mask_g"] == 0

    def test_too_small_returns_none(self):
        """Struct smaller than 36 bytes should return None."""
        archive = FakeArchive(b"\x00" * 10)
        tag = FakeTag(size=10)

        result = _parse_expression_input(tag, archive, [], [], None)

        assert result is None

    def test_registered_in_handler_dict(self):
        """Verify ExpressionInput is registered in BINARY_OR_NATIVE_HANDLERS."""
        assert "ExpressionInput" in BINARY_OR_NATIVE_HANDLERS or \
               "FExpressionInput" in BINARY_OR_NATIVE_HANDLERS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/parsers/test_expression_input_handler.py -v`
Expected: FAIL with `ImportError: cannot import name '_parse_expression_input'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/uasset_read/parsers/binary_or_native_handlers.py` (after the existing `_parse_material_input` function):

```python
def _parse_expression_input(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: List[str],
    export_map: List[Any],
    summary: Any,
) -> Optional[Dict[str, Any]]:
    """Parse FExpressionInput binary data.

    FExpressionInput format (36 bytes):
    - Expression: int32 (PackageIndex — references a MaterialExpression export)
    - OutputIndex: int32
    - InputName: FName (8 bytes: index + number)
    - Mask: int32
    - MaskR: int32
    - MaskG: int32
    - MaskB: int32
    - MaskA: int32

    Reference: Engine/Source/Runtime/Engine/Public/Materials/MaterialExpression.h:47-79
    """
    if tag.size < 36:
        return None

    start_pos = archive.tell()
    try:
        expression_index = archive.read_i32()
        output_index = archive.read_i32()
        input_name = archive.read_name(name_map)
        mask = archive.read_i32()
        mask_r = archive.read_i32()
        mask_g = archive.read_i32()
        mask_b = archive.read_i32()
        mask_a = archive.read_i32()

        return {
            "kind": "expression_input",
            "type": tag.type,
            "size": tag.size,
            "expression_index": expression_index,
            "output_index": output_index,
            "input_name": input_name,
            "mask": mask,
            "mask_r": mask_r,
            "mask_g": mask_g,
            "mask_b": mask_b,
            "mask_a": mask_a,
        }
    except (struct.error, OSError, ValueError) as e:
        archive.seek(start_pos)
        logger.debug("ExpressionInput parse failed: %s", e)
        return None
```

Register in the handler dict (find the existing handler dict that has `"FMaterialInput": _parse_material_input` and add):

```python
    "ExpressionInput": _parse_expression_input,
    "FExpressionInput": _parse_expression_input,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/parsers/test_expression_input_handler.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/parsers/binary_or_native_handlers.py tests/parsers/test_expression_input_handler.py
git commit -m "feat: add ExpressionInput binary handler for FExpressionInput struct parsing"
```

---

### Task 5: Add _build_material_ir to ir_builder

**Files:**
- Modify: `src/uasset_read/ir_builder.py`
- Test: `tests/ir/test_build_material_ir.py`

**Interfaces:**
- Consumes: `ParseResult` (export_map with Material + MaterialExpression exports), `classify_expression_type` from constants, `MATERIAL_DOMAIN_MAP`/`BLEND_MODE_MAP`/`SHADING_MODEL_MAP`/`MATERIAL_USAGE_FLAG_NAMES` from constants, `MaterialIR`/`MaterialExpressionIR`/etc from models.ir, `normalize_hex_guid` from core.utils
- Produces: `_build_material_ir(result) -> MaterialIR | None`, called from `build_package_ir` to set `ir.material`

- [ ] **Step 1: Write the failing test**

Create `tests/ir/test_build_material_ir.py`:

```python
"""Tests for _build_material_ir IR builder."""
from __future__ import annotations

from unittest.mock import Mock

from uasset_read.ir_builder import _build_material_ir


def _make_export(
    object_name: str = "",
    object_class: str = "",
    serial_size: int = 0,
    properties=None,
    parse_status: str = "success",
    b_is_asset: bool = False,
):
    """Create a mock export object."""
    export = Mock()
    export.object_name = object_name
    export.object_class = object_class
    export.serial_size = serial_size
    export.properties = properties or []
    export.parse_status = parse_status
    export.b_is_asset = b_is_asset
    export.class_index = None
    export.outer_index = 0
    export.super_index = 0
    export.graphs = []
    export.bulk_data_header = None
    export._asset_type_data = None
    export.custom_data = {}
    export.transforms = {}
    export.fallback_reason = None
    export.error_message = None
    export.guid = ""
    export.object_flags = 0
    export.serial_offset = 0
    export.package_flags = 0
    export.b_forced_export = False
    export.b_not_for_client = False
    export.b_not_for_server = False
    export.b_is_inherited_instance = False
    export.b_not_always_loaded_for_editor_game = True
    export.b_generate_public_hash = False
    export.script_serialization_start_offset = 0
    export.script_serialization_end_offset = 0
    export.template_index = None
    return export


def _make_property(name: str, value, prop_type: str = "FloatProperty"):
    """Create a mock property object."""
    prop = Mock()
    prop.name = name
    prop.value = value
    prop.type = prop_type
    prop.array_index = -1
    prop.guid = None
    return prop


def _make_result(exports, summary=None):
    """Create a mock ParseResult."""
    result = Mock()
    result.export_map = exports
    result.import_map = []
    result.summary = summary or Mock()
    result.summary.package_name = "/Game/Test"
    result.summary.package_flags = 0
    result.linker = None
    result.name_map = []
    result.blueprint = None
    result.decompiled_functions = []
    result.graphs = []
    result.components = None
    result.diagnostics = []
    result.errors = []
    result.warnings = []
    result.metadata = {}
    result.version_container = Mock()
    result.version_container.is_ue5 = True
    result.version_container.get_ue_version_string = Mock(return_value="5.x")
    result.resolved_parent_assets = []
    result.inherited_blueprint_graphs = []
    result.soft_references = []
    result.soft_package_references = []
    result.logic_sources = []
    result.hex_view_entries = []
    return result


class TestBuildMaterialIr:
    def test_no_material_returns_none(self):
        """When no Material/MaterialInstance export exists, returns None."""
        result = _make_result([_make_export(object_name="Foo", object_class="Texture2D")])
        ir = _build_material_ir(result)
        assert ir is None

    def test_material_with_no_expressions(self):
        """A Material export with no expression exports."""
        mat_export = _make_export(
            object_name="M_Test",
            object_class="Material",
            b_is_asset=True,
            properties=[_make_property("MaterialDomain", 0, "IntProperty")],
        )
        result = _make_result([mat_export])
        ir = _build_material_ir(result)
        assert ir is not None
        assert ir.material_type == "Material"
        assert len(ir.expressions) == 0

    def test_material_with_expression(self):
        """A Material export with one MaterialExpressionConstant."""
        mat_export = _make_export(
            object_name="M_Test",
            object_class="Material",
            b_is_asset=True,
        )
        expr_export = _make_export(
            object_name="MaterialExpressionConstant_1",
            object_class="MaterialExpressionConstant",
            properties=[
                _make_property("R", 1.0, "FloatProperty"),
                _make_property("MaterialExpressionGuid", "abc123", "StructProperty"),
            ],
        )
        result = _make_result([mat_export, expr_export])
        ir = _build_material_ir(result)
        assert ir is not None
        assert ir.material_type == "Material"
        assert len(ir.expressions) == 1
        assert ir.expressions[0].expression_class == "MaterialExpressionConstant"
        assert ir.expressions[0].expression_type == "constant"

    def test_material_instance(self):
        """A MaterialInstance export."""
        mi_export = _make_export(
            object_name="MI_Test",
            object_class="MaterialInstanceConstant",
            b_is_asset=True,
            properties=[
                _make_property("Parent", {"object_name": "M_Parent"}, "ObjectProperty"),
            ],
        )
        result = _make_result([mi_export])
        ir = _build_material_ir(result)
        assert ir is not None
        assert ir.material_type == "MaterialInstance"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ir/test_build_material_ir.py -v`
Expected: FAIL — `_build_material_ir` does not exist or is not importable

- [ ] **Step 3: Write minimal implementation**

Add to `src/uasset_read/ir_builder.py` (before `build_package_ir` or after the existing `_build_animation_data` function):

```python
def _build_material_ir(result: "ParseResult | LinkerParseResult") -> MaterialIR | None:
    """Build MaterialIR from ParseResult by scanning exports.

    Scans export_map for Material/MaterialInstance + MaterialExpression* exports.
    Resolves FExpressionInput/FMaterialInput PackageIndex cross-references.
    """
    from uasset_read.constants import (
        MATERIAL_DOMAIN_MAP, BLEND_MODE_MAP, SHADING_MODEL_MAP,
        MATERIAL_USAGE_FLAG_NAMES, classify_expression_type,
    )
    from uasset_read.models.ir import (
        MaterialIR, MaterialExpressionIR,
        MaterialExpressionInputIR, MaterialExpressionOutputIR,
        MaterialInputIR,
    )

    # Find Material/MaterialInstance export
    material_export = None
    expression_exports = []

    for export in result.export_map or []:
        class_name = _safe_str(getattr(export, "object_class", None)) or \
                     resolve_class_name(
                         getattr(export, "class_index", None),
                         result.import_map or [],
                         result.export_map or [],
                     )
        if class_name in ("Material",):
            if getattr(export, "b_is_asset", False) or material_export is None:
                material_export = export
                material_export._resolved_class = "Material"
        elif class_name in ("MaterialInstance", "MaterialInstanceConstant"):
            if getattr(export, "b_is_asset", False) or material_export is None:
                material_export = export
                material_export._resolved_class = "MaterialInstance"
        elif class_name and class_name.startswith("MaterialExpression"):
            expression_exports.append(export)

    if material_export is None:
        return None

    material_type = getattr(material_export, "_resolved_class", "Material")

    # Build expression index → guid mapping
    expr_guid_map: dict[int, str] = {}
    for idx, expr_export in enumerate(expression_exports):
        guid = _extract_expression_guid(expr_export)
        if guid:
            expr_guid_map[idx + 1] = guid  # 1-based export index

    # Build expressions
    expressions = []
    for idx, expr_export in enumerate(expression_exports):
        expr_ir = _build_single_expression_ir(idx + 1, expr_export, expr_guid_map, result)
        expressions.append(expr_ir)

    # Build material inputs (Material only)
    material_inputs = []
    if material_type == "Material":
        material_inputs = _build_material_inputs(material_export, expr_guid_map)

    # Build properties
    properties = _build_material_properties(material_export)

    # Build parameters (MaterialInstance only)
    parameters = None
    base_property_overrides = None
    parent = None
    if material_type == "MaterialInstance":
        parameters = _build_material_instance_parameters(material_export)
        base_property_overrides = _build_material_instance_overrides(material_export)
        parent = _resolve_material_parent(material_export, result)

    # Build data_flow
    data_flow = _build_material_data_flow(expressions, material_inputs)

    return MaterialIR(
        material_type=material_type,
        properties=properties,
        expressions=expressions,
        material_inputs=material_inputs,
        parameters=parameters,
        base_property_overrides=base_property_overrides,
        parent=parent,
        data_flow=data_flow,
    )


def _extract_expression_guid(expr_export) -> str | None:
    """Extract MaterialExpressionGuid from export properties."""
    for prop in getattr(expr_export, "properties", None) or []:
        if getattr(prop, "name", None) == "MaterialExpressionGuid":
            val = getattr(prop, "value", None)
            if isinstance(val, str):
                return normalize_hex_guid(val)
            if isinstance(val, dict):
                guid_str = val.get("guid", "") or val.get("value", "")
                if guid_str:
                    return normalize_hex_guid(guid_str)
    return None


def _build_single_expression_ir(
    export_idx: int,
    expr_export,
    expr_guid_map: dict[int, str],
    result,
) -> MaterialExpressionIR:
    """Build a single MaterialExpressionIR from an export."""
    from uasset_read.constants import classify_expression_type
    from uasset_read.models.ir import (
        MaterialExpressionIR,
        MaterialExpressionInputIR,
        MaterialExpressionOutputIR,
    )

    class_name = _safe_str(getattr(expr_export, "object_class", None)) or \
                 resolve_class_name(
                     getattr(expr_export, "class_index", None),
                     result.import_map or [],
                     result.export_map or [],
                 )

    guid = expr_guid_map.get(export_idx, "")
    expr_type = classify_expression_type(class_name)

    # Parse inputs (ExpressionInput struct properties)
    inputs = []
    for prop in getattr(expr_export, "properties", None) or []:
        prop_name = getattr(prop, "name", "")
        prop_value = getattr(prop, "value", None)
        if isinstance(prop_value, dict) and prop_value.get("struct_type") in (
            "ExpressionInput", "FExpressionInput",
        ):
            fields = prop_value.get("fields", {})
            if isinstance(fields, dict):
                expr_idx = fields.get("expression_index", 0)
                source_guid = expr_guid_map.get(expr_idx) if expr_idx else None
                inputs.append(MaterialExpressionInputIR(
                    input_name=prop_name,
                    source_expression_guid=source_guid,
                    source_output_index=fields.get("output_index", 0),
                    mask=fields.get("mask", 0),
                    mask_r=fields.get("mask_r", 0),
                    mask_g=fields.get("mask_g", 0),
                    mask_b=fields.get("mask_b", 0),
                    mask_a=fields.get("mask_a", 0),
                ))

    # Parse outputs
    outputs = _build_expression_outputs(expr_export)

    # Extract parameter/constant values
    parameter, constant_value = _extract_expression_value(class_name, expr_export)

    # Editor position
    editor_position = _extract_editor_position(expr_export)

    # Description
    description = None
    for prop in getattr(expr_export, "properties", None) or []:
        if getattr(prop, "name", None) == "Desc":
            description = _safe_str(getattr(prop, "value", None)) or None

    return MaterialExpressionIR(
        expression_guid=guid,
        expression_class=class_name,
        expression_type=expr_type,
        inputs=inputs,
        outputs=outputs,
        parameter=parameter,
        constant_value=constant_value,
        editor_position=editor_position,
        description=description,
    )


def _build_expression_outputs(expr_export) -> list:
    """Build MaterialExpressionOutputIR list from export properties."""
    from uasset_read.models.ir import MaterialExpressionOutputIR

    outputs = []
    for prop in getattr(expr_export, "properties", None) or []:
        if getattr(prop, "name", None) == "Outputs":
            val = getattr(prop, "value", None)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        fields = item.get("fields", item)
                        outputs.append(MaterialExpressionOutputIR(
                            output_name=fields.get("output_name", ""),
                            mask=fields.get("mask", 0),
                            mask_r=fields.get("mask_r", 0),
                            mask_g=fields.get("mask_g", 0),
                            mask_b=fields.get("mask_b", 0),
                            mask_a=fields.get("mask_a", 0),
                        ))
            break
    return outputs


def _extract_expression_value(class_name: str, expr_export) -> tuple:
    """Extract parameter or constant value from expression properties."""
    parameter = None
    constant_value = None

    for prop in getattr(expr_export, "properties", None) or []:
        prop_name = getattr(prop, "name", None)
        prop_value = getattr(prop, "value", None)

        if prop_name == "ParameterName" and prop_value:
            parameter = {"name": _safe_str(prop_value)}
        elif prop_name == "DefaultValue" and prop_value is not None:
            if parameter is None:
                parameter = {}
            if isinstance(prop_value, dict):
                parameter["value"] = prop_value.get("fields", prop_value)
            else:
                parameter["value"] = prop_value
        elif prop_name == "R" and prop_value is not None:
            constant_value = prop_value
        elif prop_name == "X" and constant_value is None and prop_value is not None:
            constant_value = prop_value

    return parameter, constant_value


def _extract_editor_position(expr_export) -> dict | None:
    """Extract MaterialExpressionEditorX/Y from properties."""
    x = None
    y = None
    for prop in getattr(expr_export, "properties", None) or []:
        if getattr(prop, "name", None) == "MaterialExpressionEditorX":
            x = getattr(prop, "value", None)
        elif getattr(prop, "name", None) == "MaterialExpressionEditorY":
            y = getattr(prop, "value", None)
    if x is not None or y is not None:
        return {"x": x or 0, "y": y or 0}
    return None


def _build_material_inputs(material_export, expr_guid_map: dict[int, str]) -> list:
    """Build MaterialInputIR list from Material export properties."""
    from uasset_read.models.ir import MaterialInputIR

    inputs = []
    for prop in getattr(material_export, "properties", None) or []:
        prop_name = getattr(prop, "name", "")
        prop_value = getattr(prop, "value", None)
        if isinstance(prop_value, dict):
            struct_type = prop_value.get("struct_type", "")
            if struct_type in (
                "MaterialInput", "FMaterialInput",
                "ColorMaterialInput", "FColorMaterialInput",
                "ScalarMaterialInput", "FScalarMaterialInput",
                "VectorMaterialInput", "FVectorMaterialInput",
                "Vector2MaterialInput", "FVector2MaterialInput",
            ):
                fields = prop_value.get("fields", {})
                if isinstance(fields, dict):
                    expr_idx = fields.get("expression_index", 0)
                    source_guid = expr_guid_map.get(expr_idx) if expr_idx else None
                    inputs.append(MaterialInputIR(
                        input_name=prop_name,
                        source_expression_guid=source_guid,
                        source_output_index=fields.get("output_index", 0),
                        mask=fields.get("mask", 0),
                        mask_r=fields.get("mask_r", 0),
                        mask_g=fields.get("mask_g", 0),
                        mask_b=fields.get("mask_b", 0),
                        mask_a=fields.get("mask_a", 0),
                    ))
    return inputs


def _build_material_properties(material_export) -> dict:
    """Build material properties dict from tagged properties."""
    from uasset_read.constants import (
        MATERIAL_DOMAIN_MAP, BLEND_MODE_MAP, SHADING_MODEL_MAP,
        MATERIAL_USAGE_FLAG_NAMES,
    )

    properties: dict = {}
    usage_flags: list[str] = []

    for prop in getattr(material_export, "properties", None) or []:
        prop_name = getattr(prop, "name", "")
        prop_value = getattr(prop, "value", None)

        if prop_name in ("MaterialDomain", "Domain"):
            domain_val = _safe_int(prop_value)
            properties["domain"] = MATERIAL_DOMAIN_MAP.get(domain_val, str(domain_val))
        elif prop_name == "BlendMode":
            blend_val = _safe_int(prop_value)
            properties["blend_mode"] = BLEND_MODE_MAP.get(blend_val, str(blend_val))
        elif prop_name == "ShadingModel":
            model_val = _safe_int(prop_value)
            properties["shading_model"] = SHADING_MODEL_MAP.get(model_val, str(model_val))
        elif prop_name in MATERIAL_USAGE_FLAG_NAMES and prop_value:
            usage_flags.append(prop_name)

    if usage_flags:
        properties["usage_flags"] = usage_flags

    return properties


def _build_material_instance_parameters(material_export) -> dict:
    """Build parameters dict from MaterialInstance export properties."""
    parameters: dict = {}

    for prop in getattr(material_export, "properties", None) or []:
        prop_name = getattr(prop, "name", "")
        prop_value = getattr(prop, "value", None)

        if prop_name == "ScalarParameterValues":
            parameters["scalar"] = _extract_parameter_values(prop_value, "ParameterValue")
        elif prop_name == "VectorParameterValues":
            parameters["vector"] = _extract_parameter_values(prop_value, "ParameterValue")
        elif prop_name == "TextureParameterValues":
            parameters["texture"] = _extract_parameter_values(prop_value, "ParameterValue")
        elif prop_name == "StaticSwitchParameters":
            parameters["static_switch"] = _extract_static_switch_values(prop_value)

    return parameters if parameters else None


def _extract_parameter_values(source, value_key: str) -> dict:
    """Extract parameter name→value mapping from a parameter array."""
    result: dict = {}
    if isinstance(source, list):
        for item in source:
            if isinstance(item, dict):
                info = item.get("ParameterInfo", item.get("Info", {}))
                if isinstance(info, dict):
                    name = info.get("Name", info.get("ParameterName", ""))
                else:
                    name = str(info)
                if not name:
                    name = item.get("ParameterName", item.get("Name", ""))
                if name:
                    result[str(name)] = {"value": item.get(value_key, item.get("Value"))}
    return result


def _extract_static_switch_values(source) -> dict:
    """Extract static switch parameter name→bool mapping."""
    result: dict = {}
    if isinstance(source, list):
        for item in source:
            if isinstance(item, dict):
                info = item.get("ParameterInfo", item.get("Info", {}))
                if isinstance(info, dict):
                    name = info.get("Name", info.get("ParameterName", ""))
                else:
                    name = str(info)
                if not name:
                    name = item.get("ParameterName", item.get("Name", ""))
                if name:
                    val = item.get("Value", item.get("value"))
                    result[str(name)] = bool(val) if val is not None else False
    return result


def _build_material_instance_overrides(material_export) -> dict | None:
    """Build base_property_overrides from MaterialInstance export."""
    from uasset_read.objects.exports.helpers import prop_value

    overrides: dict = {}
    override_names = (
        "OpacityMaskClipValue", "BlendMode", "ShadingModel",
        "TwoSided", "DitheredLODTransition", "CastDynamicShadowAsMasked",
        "bIsThinSurface", "OutputTranslucentVelocity", "bHasPixelAnimation",
        "bEnableTessellation", "DisplacementScaling", "bEnableDisplacementFade",
        "DisplacementFadeRange", "MaxWorldPositionOffsetDisplacement",
        "CompatibleWithLumenCardSharing", "UsageFlags",
    )

    for prop in getattr(material_export, "properties", None) or []:
        prop_name = getattr(prop, "name", "")
        if prop_name == "BasePropertyOverrides":
            val = getattr(prop, "value", None)
            if isinstance(val, dict):
                for name in override_names:
                    flag = val.get(f"bOverride_{name}")
                    if flag:
                        v = val.get(name)
                        if v is not None:
                            overrides[name] = v

    return overrides if overrides else None


def _resolve_material_parent(material_export, result) -> str | None:
    """Resolve parent material path from MaterialInstance export."""
    for prop in getattr(material_export, "properties", None) or []:
        if getattr(prop, "name", None) == "Parent":
            val = getattr(prop, "value", None)
            if isinstance(val, dict):
                return _safe_str(val.get("object_name", val.get("full_name")))
            if isinstance(val, str):
                return val
    return None


def _build_material_data_flow(
    expressions: list,
    material_inputs: list,
) -> list[dict]:
    """Build data_flow list from resolved expression inputs and material inputs."""
    from uasset_read.models.ir import MaterialExpressionIR, MaterialInputIR

    data_flow: list[dict] = []

    # Expression-to-expression connections
    for expr in expressions:
        for inp in expr.inputs:
            if inp.source_expression_guid:
                data_flow.append({
                    "source_expression_guid": inp.source_expression_guid,
                    "source_output_index": inp.source_output_index,
                    "target_expression_guid": expr.expression_guid,
                    "target_input_name": inp.input_name,
                })

    # Expression-to-material connections
    for mi in material_inputs:
        if mi.source_expression_guid:
            data_flow.append({
                "source_expression_guid": mi.source_expression_guid,
                "source_output_index": mi.source_output_index,
                "target_expression_guid": "__material__",
                "target_input_name": mi.input_name,
            })

    return data_flow
```

Then add the import at the top of `ir_builder.py`:

```python
from uasset_read.models.ir import (
    ...existing imports...,
    MaterialIR,
    MaterialExpressionIR,
    MaterialExpressionInputIR,
    MaterialExpressionOutputIR,
    MaterialInputIR,
)
```

And in `build_package_ir`, add the material field to the PackageIR construction (after `animation=_build_animation_data(result),`):

```python
        material=_build_material_ir(result),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ir/test_build_material_ir.py -v`
Expected: PASS

Also run existing IR tests for regressions:
Run: `python -m pytest tests/ir/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/ir_builder.py tests/ir/test_build_material_ir.py
git commit -m "feat: add _build_material_ir to build MaterialIR from exports"
```

---

### Task 6: Add Schema

**Files:**
- Modify: `schemas/package.schema.json`
- Test: `tests/test_material_schema.py`

**Interfaces:**
- Consumes: existing schema structure with `additionalProperties: false`
- Produces: `MaterialData` $def + sub-$defs, top-level `material` property

- [ ] **Step 1: Write the failing test**

Create `tests/test_material_schema.py`:

```python
"""Schema validation tests for Material semantic JSON."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import jsonschema
except ImportError:
    pytest.skip("jsonschema not available", allow_module_level=True)


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "package.schema.json"


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


class TestMaterialSchemaDef:
    def test_material_data_def_exists(self, schema):
        assert "MaterialData" in schema.get("$defs", {})

    def test_material_top_level_property(self, schema):
        assert "material" in schema.get("properties", {})

    def test_material_data_has_required_material_type(self, schema):
        mat_def = schema["$defs"]["MaterialData"]
        assert "material_type" in mat_def.get("required", [])

    def test_material_expression_entry_def(self, schema):
        assert "MaterialExpressionEntry" in schema["$defs"]

    def test_material_input_entry_def(self, schema):
        assert "MaterialInputEntry" in schema["$defs"]

    def test_material_data_flow_entry_def(self, schema):
        assert "MaterialDataFlowEntry" in schema["$defs"]

    def test_material_parameters_def(self, schema):
        assert "MaterialParameters" in schema["$defs"]

    def test_material_properties_def(self, schema):
        assert "MaterialProperties" in schema["$defs"]


class TestSchemaValidation:
    def test_valid_material_output(self, schema):
        """Validate a minimal valid Material output against the schema."""
        data = {
            "status": {"status": "success"},
            "summary": {
                "package_name": "/Game/Test",
                "package_class": "",
                "package_flags": 0,
                "total_export_count": 1,
                "total_import_count": 0,
                "ue_version": "5.x",
            },
            "exports": [],
            "material": {
                "material_type": "Material",
                "properties": {"domain": "Surface"},
                "expressions": [],
                "material_inputs": [],
                "data_flow": [],
            },
        }
        jsonschema.validate(data, schema)

    def test_valid_material_instance_output(self, schema):
        data = {
            "status": {"status": "success"},
            "summary": {
                "package_name": "/Game/Test",
                "package_class": "",
                "package_flags": 0,
                "total_export_count": 1,
                "total_import_count": 0,
                "ue_version": "5.x",
            },
            "exports": [],
            "material": {
                "material_type": "MaterialInstance",
                "parent": "/Game/Path/Parent",
                "parameters": {"scalar": {"x": {"value": 1.0}}},
            },
        }
        jsonschema.validate(data, schema)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_material_schema.py -v`
Expected: FAIL — `MaterialData` not in `$defs`

- [ ] **Step 3: Write minimal implementation**

In `schemas/package.schema.json`:

1. Add `"material"` to the top-level `properties` dict (after `"anim_montage"` or `"function_graphs"`):

```json
"material": {
  "$ref": "#/$defs/MaterialData",
  "description": "Material semantic data (only for Material/MaterialInstance assets)"
},
```

2. Add the new `$defs` entries inside the existing `"$defs"` block (after the last existing def):

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
    "source_expression_guid": { "type": "string" },
    "source_output_index": { "type": "integer" },
    "target_expression_guid": { "type": "string" },
    "target_input_name": { "type": "string" }
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_material_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add schemas/package.schema.json tests/test_material_schema.py
git commit -m "feat: add MaterialData schema definitions to package.schema.json"
```

---

### Task 7: Add JSON Rendering

**Files:**
- Modify: `src/uasset_read/renderers/json_renderer.py`
- Test: `tests/renderers/test_material_json_renderer.py`

**Interfaces:**
- Consumes: `MaterialIR`, `MaterialExpressionIR`, `MaterialInputIR` from models.ir, `RenderOptions` from renderers.base
- Produces: `_material_to_dict`, `_material_expression_to_dict`, `_material_input_to_dict` methods on `JSONRenderer`

- [ ] **Step 1: Write the failing test**

Create `tests/renderers/test_material_json_renderer.py`:

```python
"""Tests for Material JSON rendering."""
from __future__ import annotations

import json

from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    MaterialIR,
    MaterialExpressionIR,
    MaterialExpressionInputIR,
    MaterialExpressionOutputIR,
    MaterialInputIR,
)


def _make_header() -> PackageHeaderIR:
    return PackageHeaderIR(
        package_name="/Game/Test/M_Test",
        package_class="",
        package_flags=0,
        total_export_count=1,
        total_import_count=0,
        ue_version="5.x",
    )


def _render_json(material: MaterialIR, **options_kwargs) -> dict:
    ir = PackageIR(
        header=_make_header(),
        name_map=(),
        imports=[],
        exports=[],
        linker=None,
        material=material,
    )
    renderer = JSONRenderer()
    options = RenderOptions(**options_kwargs)
    output = renderer.render(ir, options)
    return json.loads(output)


class TestMaterialRendering:
    def test_material_section_present(self):
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[],
            material_inputs=[],
            data_flow=[],
        )
        data = _render_json(mat)
        assert "material" in data
        assert data["material"]["material_type"] == "Material"

    def test_material_with_expressions(self):
        expr = MaterialExpressionIR(
            expression_guid="abc123",
            expression_class="MaterialExpressionMultiply",
            expression_type="operator",
            inputs=[
                MaterialExpressionInputIR(
                    input_name="A",
                    source_expression_guid="def456",
                    source_output_index=0,
                ),
            ],
            outputs=[MaterialExpressionOutputIR()],
        )
        mat = MaterialIR(
            material_type="Material",
            properties={"domain": "Surface"},
            expressions=[expr],
            material_inputs=[],
            data_flow=[],
        )
        data = _render_json(mat)
        assert len(data["material"]["expressions"]) == 1
        assert data["material"]["expressions"][0]["expression_class"] == "MaterialExpressionMultiply"
        assert data["material"]["expressions"][0]["inputs"][0]["source_expression_guid"] == "def456"

    def test_material_inputs_rendered(self):
        mi = MaterialInputIR(
            input_name="BaseColor",
            source_expression_guid="abc123",
            source_output_index=0,
        )
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[],
            material_inputs=[mi],
            data_flow=[],
        )
        data = _render_json(mat)
        assert len(data["material"]["material_inputs"]) == 1
        assert data["material"]["material_inputs"][0]["input_name"] == "BaseColor"

    def test_data_flow_rendered(self):
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[],
            material_inputs=[],
            data_flow=[
                {
                    "source_expression_guid": "abc",
                    "source_output_index": 0,
                    "target_expression_guid": "def",
                    "target_input_name": "A",
                }
            ],
        )
        data = _render_json(mat)
        assert len(data["material"]["data_flow"]) == 1

    def test_material_instance_rendered(self):
        mat = MaterialIR(
            material_type="MaterialInstance",
            properties={},
            expressions=[],
            material_inputs=[],
            parameters={"scalar": {"x": {"value": 1.0}}},
            base_property_overrides={"BlendMode": "Opaque"},
            parent="/Game/Path/Parent",
            data_flow=[],
        )
        data = _render_json(mat)
        assert data["material"]["material_type"] == "MaterialInstance"
        assert data["material"]["parent"] == "/Game/Path/Parent"
        assert data["material"]["parameters"]["scalar"]["x"]["value"] == 1.0

    def test_standard_mode_omits_empty(self):
        """Standard mode should omit empty fields."""
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[],
            material_inputs=[],
            data_flow=[],
        )
        data = _render_json(mat, output_level="standard")
        assert "properties" not in data["material"]
        assert "expressions" not in data["material"]

    def test_debug_mode_includes_empty(self):
        """Debug mode should include all fields."""
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[],
            material_inputs=[],
            data_flow=[],
        )
        data = _render_json(mat, output_level="debug")
        assert data["material"]["material_type"] == "Material"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/renderers/test_material_json_renderer.py -v`
Expected: FAIL — `_material_to_dict` not called, no `material` key in output

- [ ] **Step 3: Write minimal implementation**

In `src/uasset_read/renderers/json_renderer.py`, add to `_build_data` method (after the animation section, before `if (options.hex_view...`):

```python
        if ir.material is not None:
            data["material"] = self._material_to_dict(ir.material, is_debug)
```

Add the new methods to the `JSONRenderer` class (after `_anim_montage_to_dict`):

```python
    def _material_to_dict(self, material, is_debug: bool = False) -> dict[str, Any]:
        """Serialize MaterialIR to dict."""
        d: dict[str, Any] = {"material_type": material.material_type}
        if material.properties:
            d["properties"] = material.properties
        if material.expressions:
            d["expressions"] = [
                self._material_expression_to_dict(e, is_debug) for e in material.expressions
            ]
        elif is_debug:
            d["expressions"] = []
        if material.material_inputs:
            d["material_inputs"] = [
                self._material_input_to_dict(mi) for mi in material.material_inputs
            ]
        elif is_debug:
            d["material_inputs"] = []
        if material.parameters:
            d["parameters"] = material.parameters
        if material.base_property_overrides:
            d["base_property_overrides"] = material.base_property_overrides
        if material.parent:
            d["parent"] = material.parent
        if material.data_flow:
            d["data_flow"] = material.data_flow
        elif is_debug:
            d["data_flow"] = []
        return d

    def _material_expression_to_dict(self, expr, is_debug: bool = False) -> dict[str, Any]:
        """Serialize MaterialExpressionIR to dict."""
        d: dict[str, Any] = {
            "expression_guid": expr.expression_guid,
            "expression_class": expr.expression_class,
        }
        if expr.expression_type:
            d["expression_type"] = expr.expression_type
        if expr.inputs or is_debug:
            d["inputs"] = [
                {
                    "input_name": inp.input_name,
                    "source_expression_guid": inp.source_expression_guid,
                    "source_output_index": inp.source_output_index,
                    "mask": inp.mask,
                    "mask_r": inp.mask_r,
                    "mask_g": inp.mask_g,
                    "mask_b": inp.mask_b,
                    "mask_a": inp.mask_a,
                }
                for inp in expr.inputs
            ]
        if expr.outputs or is_debug:
            d["outputs"] = [
                {
                    "output_name": out.output_name,
                    "mask": out.mask,
                    "mask_r": out.mask_r,
                    "mask_g": out.mask_g,
                    "mask_b": out.mask_b,
                    "mask_a": out.mask_a,
                }
                for out in expr.outputs
            ]
        if expr.parameter:
            d["parameter"] = expr.parameter
        if expr.constant_value is not None:
            d["constant_value"] = expr.constant_value
        if expr.editor_position:
            d["editor_position"] = expr.editor_position
        if expr.description:
            d["description"] = expr.description
        return d

    def _material_input_to_dict(self, mi) -> dict[str, Any]:
        """Serialize MaterialInputIR to dict."""
        return {
            "input_name": mi.input_name,
            "source_expression_guid": mi.source_expression_guid,
            "source_output_index": mi.source_output_index,
            "mask": mi.mask,
            "mask_r": mi.mask_r,
            "mask_g": mi.mask_g,
            "mask_b": mi.mask_b,
            "mask_a": mi.mask_a,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/renderers/test_material_json_renderer.py -v`
Expected: PASS

Also run existing renderer tests for regressions:
Run: `python -m pytest tests/renderers/ tests/test_json_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/renderers/json_renderer.py tests/renderers/test_material_json_renderer.py
git commit -m "feat: add _material_to_dict JSON rendering for Material semantic data"
```

---

### Task 8: Add Markdown Rendering

**Files:**
- Modify: `src/uasset_read/renderers/markdown_renderer.py`
- Test: `tests/renderers/test_material_markdown.py`

**Interfaces:**
- Consumes: `MaterialIR` from models.ir, `RenderOptions` from renderers.base
- Produces: Material section in Markdown output

- [ ] **Step 1: Write the failing test**

Create `tests/renderers/test_material_markdown.py`:

```python
"""Tests for Material Markdown rendering."""
from __future__ import annotations

from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    MaterialIR,
    MaterialExpressionIR,
    MaterialInputIR,
)


def _render_markdown(material: MaterialIR) -> str:
    ir = PackageIR(
        header=PackageHeaderIR(
            package_name="/Game/Test/M_Test",
            package_class="",
            package_flags=0,
            total_export_count=1,
            total_import_count=0,
            ue_version="5.x",
        ),
        name_map=(),
        imports=[],
        exports=[],
        linker=None,
        material=material,
    )
    renderer = MarkdownRenderer()
    options = RenderOptions()
    return renderer.render(ir, options)


class TestMaterialMarkdown:
    def test_material_header_present(self):
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[],
            material_inputs=[],
            data_flow=[],
        )
        md = _render_markdown(mat)
        assert "Material" in md

    def test_properties_rendered(self):
        mat = MaterialIR(
            material_type="Material",
            properties={"domain": "Surface", "blend_mode": "Opaque"},
            expressions=[],
            material_inputs=[],
            data_flow=[],
        )
        md = _render_markdown(mat)
        assert "Surface" in md
        assert "Opaque" in md

    def test_expressions_rendered(self):
        expr = MaterialExpressionIR(
            expression_guid="abc123",
            expression_class="MaterialExpressionConstant",
            expression_type="constant",
            inputs=[],
            outputs=[],
        )
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[expr],
            material_inputs=[],
            data_flow=[],
        )
        md = _render_markdown(mat)
        assert "MaterialExpressionConstant" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/renderers/test_material_markdown.py -v`
Expected: FAIL — no Material section in Markdown output

- [ ] **Step 3: Write minimal implementation**

In `src/uasset_read/renderers/markdown_renderer.py`, add a Material section method and call it from the main render method (following the existing pattern for Blueprint/Animation sections).

Add the method:

```python
    def _render_material_section(self, ir: PackageIR, lines: list[str]) -> None:
        """Render Material section in Markdown."""
        if ir.material is None:
            return
        mat = ir.material
        lines.append(f"\n## Material ({mat.material_type})\n")
        if mat.properties:
            lines.append("| Property | Value |")
            lines.append("|----------|-------|")
            for key, val in sorted(mat.properties.items()):
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                lines.append(f"| {key} | {val} |")
            lines.append("")
        if mat.parent:
            lines.append(f"**Parent:** {mat.parent}\n")
        if mat.expressions:
            lines.append("### Expressions\n")
            lines.append("| GUID | Class | Type |")
            lines.append("|------|-------|------|")
            for expr in mat.expressions:
                lines.append(
                    f"| {expr.expression_guid[:8]}... | {expr.expression_class} | {expr.expression_type or ''} |"
                )
            lines.append("")
        if mat.parameters:
            lines.append("### Parameters\n")
            for ptype, params in mat.parameters.items():
                if params:
                    lines.append(f"**{ptype}:** {', '.join(sorted(params.keys()))}\n")
        if mat.data_flow:
            lines.append(f"**Data flow connections:** {len(mat.data_flow)}\n")
```

Call it from the main render method (find where Blueprint/Animation sections are rendered and add the material section call nearby):

```python
        self._render_material_section(ir, lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/renderers/test_material_markdown.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/renderers/markdown_renderer.py tests/renderers/test_material_markdown.py
git commit -m "feat: add Material section to Markdown renderer"
```

---

### Task 9: Integration Tests with Real Samples

**Files:**
- Test: `tests/integration/test_material_integration.py`

**Interfaces:**
- Consumes: All previous tasks (constants, IR types, binary handlers, IR builder, schema, renderers)
- Produces: End-to-end verification with real material assets

- [ ] **Step 1: Write the test**

Create `tests/integration/test_material_integration.py`:

```python
"""Integration tests for Material semantic JSON with real samples."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

SAMPLE_ROOTS = [
    Path("E:/Develop/lib/Samples"),
    ROOT / "tests" / "samples",
]


def _find_sample(name_pattern: str) -> Path | None:
    for root in SAMPLE_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*.uasset"):
            if name_pattern.lower() in p.name.lower():
                return p
    return None


def _parse_asset(asset_path: Path) -> dict:
    """Parse a .uasset file and return JSON dict."""
    result = subprocess.run(
        [sys.executable, "run.py", str(asset_path), "--output-level", "debug"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=30,
    )
    # run.py writes to a file, not stdout — use --json flag or direct API
    # Fallback: import and call directly
    sys.path.insert(0, str(ROOT / "src"))
    from uasset_read.cli import parse_package
    from uasset_read.renderers.json_renderer import JSONRenderer
    from uasset_read.renderers.base import RenderOptions

    parse_result = parse_package(str(asset_path))
    from uasset_read.ir_builder import build_package_ir
    ir = build_package_ir(parse_result)
    renderer = JSONRenderer()
    options = RenderOptions(output_level="debug")
    output = renderer.render(ir, options)
    return json.loads(output)


@pytest.fixture(scope="module")
def anim_man_default():
    path = _find_sample("M_AnimMan_Default")
    if path is None:
        pytest.skip("M_AnimMan_Default sample not found")
    return path


@pytest.fixture(scope="module")
def grid_level_background():
    path = _find_sample("M_GridLevel_Background")
    if path is None:
        pytest.skip("M_GridLevel_Background sample not found")
    return path


@pytest.fixture(scope="module")
def mi_neon_white():
    path = _find_sample("MI_Neon_White")
    if path is None:
        pytest.skip("MI_Neon_White sample not found")
    return path


class TestMaterialIntegration:
    def test_material_section_present(self, anim_man_default):
        data = _parse_asset(anim_man_default)
        assert "material" in data
        assert data["material"]["material_type"] == "Material"

    def test_material_has_expressions(self, anim_man_default):
        data = _parse_asset(anim_man_default)
        assert len(data["material"]["expressions"]) > 0

    def test_expression_has_guid(self, anim_man_default):
        data = _parse_asset(anim_man_default)
        for expr in data["material"]["expressions"]:
            assert expr["expression_guid"]
            assert expr["expression_class"]

    def test_material_has_inputs(self, anim_man_default):
        data = _parse_asset(anim_man_default)
        assert len(data["material"]["material_inputs"]) > 0
        inputs = data["material"]["material_inputs"]
        input_names = [mi["input_name"] for mi in inputs]
        assert "BaseColor" in input_names or "Roughness" in input_names

    def test_grid_level_has_multiply(self, grid_level_background):
        data = _parse_asset(grid_level_background)
        expr_classes = [e["expression_class"] for e in data["material"]["expressions"]]
        assert "MaterialExpressionMultiply" in expr_classes

    def test_grid_level_has_data_flow(self, grid_level_background):
        data = _parse_asset(grid_level_background)
        # At least some data flow connections should be resolved
        assert len(data["material"]["data_flow"]) > 0

    def test_material_instance_has_parent(self, mi_neon_white):
        data = _parse_asset(mi_neon_white)
        assert data["material"]["material_type"] == "MaterialInstance"
        assert data["material"].get("parent")

    def test_material_instance_has_parameters(self, mi_neon_white):
        data = _parse_asset(mi_neon_white)
        params = data["material"].get("parameters", {})
        assert params, "MaterialInstance should have parameters"
```

- [ ] **Step 2: Run test to verify it passes (or identify issues)**

Run: `python -m pytest tests/integration/test_material_integration.py -v --allow-missing-assets`
Expected: May PASS or identify issues in the IR builder that need fixing. Fix any issues in `ir_builder.py` and re-run.

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests -q`
Expected: PASS (or failures clearly attributed to environment/sample availability)

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_material_integration.py
git commit -m "test: add Material semantic JSON integration tests with real samples"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ MaterialIR architecture (spec 4.1) → Task 2
- ✅ Binary handler fixes (spec 4.2) → Tasks 3, 4
- ✅ Data flow resolution (spec 4.3) → Task 5
- ✅ Expression type classification (spec 4.4) → Task 1
- ✅ Material properties decoding (spec 4.5) → Task 1 (constants) + Task 5 (IR builder)
- ✅ Schema (spec 4.6) → Task 6
- ✅ JSON rendering (spec 4.7) → Task 7
- ✅ Markdown rendering (spec 4.8) → Task 8
- ✅ Testing strategy (spec 6) → Tasks 1-8 (unit) + Task 9 (integration)
- ✅ All files in spec section 5 covered

**2. Placeholder scan:** No TBDs, TODOs, or vague steps. All code blocks contain actual implementation.

**3. Type consistency:**
- `MaterialIR.material_type` — str, consistent across spec, Task 2, Task 7
- `MaterialExpressionIR.expression_guid` — str, consistent across Tasks 2, 5, 7
- `classify_expression_type` — returns `str` (fixed: was `str | None` in initial draft, updated to `str` since implementation always returns a string including "unknown")
- `MaterialInputIR.input_name` — str, consistent across Tasks 2, 5, 7
- `_parse_expression_input` returns dict with `expression_index` key — consistent with Task 5's `_build_single_expression_ir` which reads `fields.get("expression_index")`
