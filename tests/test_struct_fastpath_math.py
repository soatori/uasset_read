"""测试数学类型 Struct fast-path"""
import pytest


def test_vector2f_size():
    """测试 Vector2f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Vector2f") == 8


def test_vector3f_size():
    """测试 Vector3f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Vector3f") == 12


def test_vector3d_size():
    """测试 Vector3d 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Vector3d") == 24


def test_vector4f_size():
    """测试 Vector4f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Vector4f") == 16


def test_vector4d_size():
    """测试 Vector4d 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Vector4d") == 32


def test_rotator3f_size():
    """测试 Rotator3f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Rotator3f") == 12


def test_rotator3d_size():
    """测试 Rotator3d 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Rotator3d") == 24


def test_quat4f_size():
    """测试 Quat4f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Quat4f") == 16


def test_quat4d_size():
    """测试 Quat4d 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Quat4d") == 32


def test_plane4f_size():
    """测试 Plane4f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Plane4f") == 16


def test_plane4d_size():
    """测试 Plane4d 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Plane4d") == 32


def test_sphere3f_size():
    """测试 Sphere3f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Sphere3f") == 16


def test_sphere3d_size():
    """测试 Sphere3d 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Sphere3d") == 32


def test_box2f_size():
    """测试 Box2f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Box2f") == 16


def test_box3f_size():
    """测试 Box3f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Box3f") == 24


def test_matrix44f_size():
    """测试 Matrix44f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Matrix44f") == 64


def test_transform3f_size():
    """测试 Transform3f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Transform3f") == 48
