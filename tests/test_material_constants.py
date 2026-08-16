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
