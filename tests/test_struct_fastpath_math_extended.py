"""测试扩展数学类型 Struct fast-path"""
import pytest


def test_int_vector2_size():
    """测试 IntVector2 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("IntVector2") == 8


def test_int_vector4_size():
    """测试 IntVector4 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("IntVector4") == 16


def test_uint_vector_size():
    """测试 UintVector 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("UintVector") == 12


def test_uint_vector2_size():
    """测试 UintVector2 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("UintVector2") == 8


def test_uint_vector4_size():
    """测试 UintVector4 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("UintVector4") == 16


def test_int64_vector2_size():
    """测试 Int64Vector2 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Int64Vector2") == 16


def test_int64_vector_size():
    """测试 Int64Vector 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Int64Vector") == 24


def test_int64_vector4_size():
    """测试 Int64Vector4 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Int64Vector4") == 32


def test_uint64_vector2_size():
    """测试 UInt64Vector2 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("UInt64Vector2") == 16


def test_uint64_vector_size():
    """测试 UInt64Vector 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("UInt64Vector") == 24


def test_uint64_vector4_size():
    """测试 UInt64Vector4 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("UInt64Vector4") == 32


def test_deprecate_slate_vector2d_size():
    """测试 DeprecateSlateVector2D 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("DeprecateSlateVector2D") == 16


def test_vector_double_size():
    """测试 VectorDouble 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("VectorDouble") == 24


def test_timespan_size():
    """测试 Timespan 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Timespan") == 8


def test_datetime_size():
    """测试 DateTime 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("DateTime") == 8


def test_frame_number_size():
    """测试 FrameNumber 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("FrameNumber") == 4


def test_two_vectors_size():
    """测试 TwoVectors 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("TwoVectors") == 24


def test_matrix_size():
    """测试 Matrix 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Matrix") == 64

