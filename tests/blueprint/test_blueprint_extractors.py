"""blueprint 组件提取器和变换解析器单元测试。

覆盖范围：
- component_extractor: extract_components 函数签名、空输入、_filter_scalar_properties
- transform_parser: parse_vector_value、parse_rotator_value、parse_scale_value、
  extract_component_transforms、_decode_raw_vector
- models/transforms: format_transform_value、VectorValue/RotatorValue/ScaleValue
"""
from __future__ import annotations

import math
import struct

import pytest

from uasset_read.blueprint.component_extractor import extract_components
from uasset_read.blueprint.transform_parser import (
    _decode_raw_vector,
    _try_extract_struct_value,
    extract_component_transforms,
    parse_rotator_value,
    parse_scale_value,
    parse_vector_value,
)
from uasset_read.models.properties import PropertyValue, StructValue
from uasset_read.models.transforms import (
    RotatorValue,
    ScaleValue,
    VectorValue,
    format_transform_value,
)


# ============================================================================
# ComponentExtractor — 基本接口测试
# ============================================================================


class TestComponentExtractorCallable:
    """extract_components 应可调用。"""

    def test_callable(self):
        assert callable(extract_components)

    def test_empty_export_map_returns_empty_list(self):
        result = extract_components([], [])
        assert result == []

    def test_export_without_properties_skipped(self):
        """无属性的 export 应被跳过。"""

        class FakeExport:
            object_name = "TestComponent"
            class_index = 0
            properties = []

        result = extract_components([FakeExport()], [])
        assert result == []


# ============================================================================
# TransformParser — parse_vector_value
# ============================================================================


class TestParseVectorValue:
    """parse_vector_value 应正确解析 StructValue 到 VectorValue。"""

    def test_basic_vector(self):
        sv = StructValue(
            struct_type="Vector",
            fields={"X": 1.0, "Y": 2.0, "Z": 3.0},
        )
        vec = parse_vector_value(sv)
        assert isinstance(vec, VectorValue)
        assert vec.x == 1.0
        assert vec.y == 2.0
        assert vec.z == 3.0

    def test_zero_vector(self):
        sv = StructValue(struct_type="Vector", fields={})
        vec = parse_vector_value(sv)
        assert vec.x == 0
        assert vec.y == 0
        assert vec.z == 0

    def test_integer_location(self):
        """location 精度：整数应保持整数。"""
        sv = StructValue(
            struct_type="Vector",
            fields={"X": 100.0, "Y": 200.0, "Z": 300.0},
        )
        vec = parse_vector_value(sv, precision_type="location")
        assert vec.x == 100
        assert vec.y == 200
        assert vec.z == 300

    def test_fractional_location(self):
        """location 精度：小数保留 3 位。"""
        sv = StructValue(
            struct_type="Vector",
            fields={"X": 1.12345, "Y": 2.0, "Z": 3.99999},
        )
        vec = parse_vector_value(sv, precision_type="location")
        assert vec.x == pytest.approx(1.123, abs=1e-3)
        assert vec.y == 2
        assert vec.z == pytest.approx(4.0, abs=1e-3)


# ============================================================================
# TransformParser — parse_rotator_value
# ============================================================================


class TestParseRotatorValue:
    """parse_rotator_value 应正确解析 StructValue 到 RotatorValue。"""

    def test_basic_rotator(self):
        sv = StructValue(
            struct_type="Rotator",
            fields={"Roll": 1.0, "Pitch": 2.0, "Yaw": 3.0},
        )
        rot = parse_rotator_value(sv)
        assert isinstance(rot, RotatorValue)
        assert rot.roll == 1.0
        assert rot.pitch == 2.0
        assert rot.yaw == 3.0
        assert rot.unit == "degrees"

    def test_zero_rotator(self):
        sv = StructValue(struct_type="Rotator", fields={})
        rot = parse_rotator_value(sv)
        assert rot.roll == 0
        assert rot.pitch == 0
        assert rot.yaw == 0


# ============================================================================
# TransformParser — parse_scale_value
# ============================================================================


class TestParseScaleValue:
    """parse_scale_value 应正确解析 StructValue 到 ScaleValue。"""

    def test_basic_scale(self):
        sv = StructValue(
            struct_type="Vector",
            fields={"X": 1.5, "Y": 2.5, "Z": 3.5},
        )
        s = parse_scale_value(sv)
        assert isinstance(s, ScaleValue)
        assert s.x == pytest.approx(1.5)
        assert s.y == pytest.approx(2.5)
        assert s.z == pytest.approx(3.5)

    def test_scale_precision(self):
        """scale 精度：保留 4 位小数。"""
        sv = StructValue(
            struct_type="Vector",
            fields={"X": 1.123456789, "Y": 0.0, "Z": 0.0},
        )
        s = parse_scale_value(sv)
        assert s.x == pytest.approx(1.1235, abs=1e-4)


# ============================================================================
# TransformParser — extract_component_transforms
# ============================================================================


class TestExtractComponentTransforms:
    """extract_component_transforms 应从属性列表中提取变换。"""

    def test_empty_properties(self):
        result = extract_component_transforms([])
        # 空属性列表返回空字典（无变换可提取）
        assert result == {}

    def test_extracts_location(self):
        props = [
            PropertyValue(
                name="RelativeLocation",
                type="StructProperty",
                value=StructValue(
                    struct_type="Vector",
                    fields={"X": 10.0, "Y": 20.0, "Z": 30.0},
                ),
            ),
        ]
        result = extract_component_transforms(props)
        assert isinstance(result["relative_location"], VectorValue)
        assert result["relative_location"].x == 10.0

    def test_extracts_rotation(self):
        props = [
            PropertyValue(
                name="RelativeRotation",
                type="StructProperty",
                value=StructValue(
                    struct_type="Rotator",
                    fields={"Roll": 0.0, "Pitch": 45.0, "Yaw": 90.0},
                ),
            ),
        ]
        result = extract_component_transforms(props)
        assert isinstance(result["relative_rotation"], RotatorValue)
        assert result["relative_rotation"].yaw == 90.0

    def test_extracts_scale(self):
        props = [
            PropertyValue(
                name="RelativeScale3D",
                type="StructProperty",
                value=StructValue(
                    struct_type="Vector",
                    fields={"X": 2.0, "Y": 2.0, "Z": 2.0},
                ),
            ),
        ]
        result = extract_component_transforms(props)
        assert isinstance(result["relative_scale"], ScaleValue)
        assert result["relative_scale"].x == 2.0

    def test_skips_non_transform_properties(self):
        props = [
            PropertyValue(name="SomeOtherProp", type="FloatProperty", value=1.0),
        ]
        result = extract_component_transforms(props)
        # 非变换属性被跳过，返回空字典
        assert result == {}


# ============================================================================
# TransformParser — _decode_raw_vector
# ============================================================================


class TestDecodeRawVector:
    """_decode_raw_vector 应从 bytes 解码向量。"""

    def test_float32_12_bytes(self):
        raw = struct.pack("<fff", 1.0, 2.0, 3.0)
        vec = _decode_raw_vector(raw)
        assert vec is not None
        assert vec.x == 1.0
        assert vec.y == 2.0
        assert vec.z == 3.0

    def test_float64_24_bytes(self):
        raw = struct.pack("<ddd", 1.5, 2.5, 3.5)
        vec = _decode_raw_vector(raw)
        assert vec is not None
        assert vec.x == 1.5
        assert vec.y == 2.5
        assert vec.z == 3.5

    def test_empty_returns_none(self):
        assert _decode_raw_vector(b"") is None

    def test_invalid_size_returns_none(self):
        assert _decode_raw_vector(b"\x00\x01") is None


# ============================================================================
# TransformParser — _try_extract_struct_value
# ============================================================================


class TestTryExtractStructValue:
    """_try_extract_struct_value 应从不同格式中提取字段字典。"""

    def test_struct_value(self):
        sv = StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})
        result = _try_extract_struct_value(sv)
        assert result == {"X": 1.0, "Y": 2.0, "Z": 3.0}

    def test_binary_or_native_property_dict(self):
        raw = struct.pack("<fff", 1.0, 2.0, 3.0)
        d = {"kind": "binary_or_native_property", "raw_data": raw}
        result = _try_extract_struct_value(d)
        assert result is not None
        assert result["X"] == 1.0

    def test_struct_binary_decoded_dict(self):
        d = {"kind": "struct_binary_decoded", "fields": {"X": 1.0, "Y": 2.0}}
        result = _try_extract_struct_value(d)
        assert result == {"X": 1.0, "Y": 2.0}

    def test_unknown_dict_returns_none(self):
        result = _try_extract_struct_value({"kind": "unknown"})
        assert result is None

    def test_none_returns_none(self):
        result = _try_extract_struct_value(None)
        assert result is None


# ============================================================================
# models/transforms — format_transform_value
# ============================================================================


class TestFormatTransformValue:
    """format_transform_value 应按类型应用精度。"""

    def test_location_integer(self):
        assert format_transform_value(100.0, "location") == 100

    def test_location_fractional(self):
        assert format_transform_value(1.12345, "location") == pytest.approx(1.123, abs=1e-3)

    def test_rotation(self):
        assert format_transform_value(1.123456789, "rotation") == pytest.approx(1.123, abs=1e-3)

    def test_scale(self):
        assert format_transform_value(1.123456789, "scale") == pytest.approx(1.1235, abs=1e-4)

    def test_unknown_type_passthrough(self):
        assert format_transform_value(42.0, "unknown") == 42.0

    def test_nan_passthrough(self):
        result = format_transform_value(float("nan"), "location")
        assert math.isnan(result)

    def test_inf_passthrough(self):
        result = format_transform_value(float("inf"), "location")
        assert math.isinf(result)


# ============================================================================
# models/transforms — 数据类
# ============================================================================


class TestTransformDataclasses:
    """VectorValue/RotatorValue/ScaleValue 应正确创建。"""

    def test_vector_value(self):
        v = VectorValue(x=1.0, y=2.0, z=3.0)
        assert v.x == 1.0
        assert v.property_type == "StructProperty"

    def test_rotator_value(self):
        r = RotatorValue(roll=1.0, pitch=2.0, yaw=3.0)
        assert r.unit == "degrees"
        assert r.property_type == "StructProperty"

    def test_scale_value(self):
        s = ScaleValue(x=1.0, y=2.0, z=3.0)
        assert s.property_type == "StructProperty"
