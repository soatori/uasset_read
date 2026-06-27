"""测试 StructProperty LWC（Large World Coordinates）版本感知尺寸查询和解析。

覆盖：
- get_struct_size() 基础功能
- get_struct_size() LWC 版本感知（UE4 / UE5 pre-LWC / UE5 LWC）
- get_struct_size() 显式精度变体（Vector3d / Vector3f 等）
- parse_struct_property() Quat/Plane/Sphere LWC 快速路径
"""
from __future__ import annotations

import struct
from io import BytesIO
from pathlib import Path

import pytest

from uasset_read.archive import FArchive
from uasset_read.models.properties import PropertyTag, StructValue
from uasset_read.parsers.property_types import get_struct_size, parse_struct_property
from uasset_read.versioning import VersionContainer


# ============================================================================
# 辅助函数
# ============================================================================

def _archive(tmp_path: Path, data: bytes) -> FArchive:
    """创建测试用 FArchive。"""
    path = tmp_path / "data.bin"
    path.write_bytes(data)
    return FArchive(str(path), tolerant=False)


def _make_vc(ue5_version: int = 0, ue4_version: int = 0) -> VersionContainer:
    """创建测试用 VersionContainer。"""
    return VersionContainer(
        file_version_ue5=ue5_version,
        file_version_ue4=ue4_version,
    )


# ============================================================================
# get_struct_size — 基础功能
# ============================================================================

class TestGetStructSizeBasic:
    """get_struct_size 基础查询（无 version_container）。"""

    def test_known_non_lwc_type(self):
        """非 LWC 类型返回固定大小。"""
        assert get_struct_size("Color") == 4
        assert get_struct_size("Guid") == 16
        assert get_struct_size("IntPoint") == 8
        assert get_struct_size("LinearColor") == 16

    def test_unknown_type_returns_none(self):
        """未知类型返回 None。"""
        assert get_struct_size("UnknownStruct") is None
        assert get_struct_size("CustomFoo") is None

    def test_no_version_container_uses_float_size(self):
        """无 version_container 时，LWC 基础类型返回 float 大小。"""
        assert get_struct_size("Vector") == 12
        assert get_struct_size("Rotator") == 12
        assert get_struct_size("Vector2D") == 8
        assert get_struct_size("Vector4") == 16
        assert get_struct_size("Quat") == 16
        assert get_struct_size("Plane") == 16
        assert get_struct_size("Sphere") == 16


# ============================================================================
# get_struct_size — LWC 版本感知
# ============================================================================

class TestGetStructSizeLWC:
    """get_struct_size LWC 版本感知。"""

    def test_ue4_returns_float_size(self):
        """UE4 版本返回 float 大小。"""
        vc = _make_vc(ue4_version=516)
        assert get_struct_size("Vector", vc) == 12
        assert get_struct_size("Quat", vc) == 16

    def test_ue5_pre_lwc_returns_float_size(self):
        """UE5 pre-LWC (file_version_ue5 < 1004) 返回 float 大小。"""
        vc = _make_vc(ue5_version=1000)
        assert get_struct_size("Vector", vc) == 12
        assert get_struct_size("Rotator", vc) == 12
        assert get_struct_size("Vector2D", vc) == 8
        assert get_struct_size("Vector4", vc) == 16
        assert get_struct_size("Quat", vc) == 16
        assert get_struct_size("Plane", vc) == 16
        assert get_struct_size("Sphere", vc) == 16

    def test_ue5_lwc_returns_double_size(self):
        """UE5 LWC (file_version_ue5 >= 1004) 返回 double 大小。"""
        vc = _make_vc(ue5_version=1004)
        assert get_struct_size("Vector", vc) == 24
        assert get_struct_size("Rotator", vc) == 24
        assert get_struct_size("Vector2D", vc) == 16
        assert get_struct_size("Vector4", vc) == 32
        assert get_struct_size("Quat", vc) == 32
        assert get_struct_size("Plane", vc) == 32
        assert get_struct_size("Sphere", vc) == 32

    def test_ue5_lwc_higher_version(self):
        """UE5 LWC 更高版本也返回 double 大小。"""
        vc = _make_vc(ue5_version=1012)
        assert get_struct_size("Vector", vc) == 24
        assert get_struct_size("Quat", vc) == 32

    def test_non_lwc_type_unaffected_by_version(self):
        """非 LWC 类型不受版本影响。"""
        vc_lwc = _make_vc(ue5_version=1004)
        assert get_struct_size("Color", vc_lwc) == 4
        assert get_struct_size("Guid", vc_lwc) == 16
        assert get_struct_size("LinearColor", vc_lwc) == 16
        assert get_struct_size("IntPoint", vc_lwc) == 8


# ============================================================================
# get_struct_size — 显式精度变体
# ============================================================================

class TestGetStructSizeExplicitTypes:
    """显式精度变体类型（Vector3d, Vector3f 等）。"""

    def test_double_variants_always_return_double_size(self):
        """显式双精度变体始终返回 double 大小，不看版本。"""
        # 无版本
        assert get_struct_size("Vector3d") == 24
        assert get_struct_size("Vector4d") == 32
        assert get_struct_size("Rotator3d") == 24
        assert get_struct_size("Quat4d") == 32
        assert get_struct_size("Plane4d") == 32
        assert get_struct_size("Sphere3d") == 32

        # UE4 版本
        vc_ue4 = _make_vc(ue4_version=516)
        assert get_struct_size("Vector3d", vc_ue4) == 24
        assert get_struct_size("Quat4d", vc_ue4) == 32

        # UE5 LWC 版本
        vc_lwc = _make_vc(ue5_version=1004)
        assert get_struct_size("Vector3d", vc_lwc) == 24
        assert get_struct_size("Quat4d", vc_lwc) == 32

    def test_float_variants_always_return_float_size(self):
        """显式单精度变体始终返回 float 大小，不看版本。"""
        # 无版本
        assert get_struct_size("Vector3f") == 12
        assert get_struct_size("Vector4f") == 16
        assert get_struct_size("Rotator3f") == 12
        assert get_struct_size("Quat4f") == 16
        assert get_struct_size("Plane4f") == 16
        assert get_struct_size("Sphere3f") == 16
        assert get_struct_size("Vector2f") == 8

        # UE5 LWC 版本
        vc_lwc = _make_vc(ue5_version=1004)
        assert get_struct_size("Vector3f", vc_lwc) == 12
        assert get_struct_size("Quat4f", vc_lwc) == 16


# ============================================================================
# parse_struct_property — Quat/Plane/Sphere LWC 快速路径
# ============================================================================

class TestStructPropertyLWCFastPath:
    """验证 Quat/Plane/Sphere 的 LWC 双精度快速路径。"""

    def test_quat_f32_fast_path(self, tmp_path):
        """Quat 标准 float 精度快速路径。"""
        data = struct.pack("<ffff", 1.0, 2.0, 3.0, 4.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestQuat", type="StructProperty", size=16, struct_type="Quat")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Quat"
        assert abs(result.fields["X"] - 1.0) < 1e-6
        assert abs(result.fields["Y"] - 2.0) < 1e-6
        assert abs(result.fields["Z"] - 3.0) < 1e-6
        assert abs(result.fields["W"] - 4.0) < 1e-6

    def test_quat_f64_lwc_fast_path(self, tmp_path):
        """Quat LWC double 精度快速路径（tag.size=32）。"""
        data = struct.pack("<dddd", 1.5, 2.5, 3.5, 4.5)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestQuat", type="StructProperty", size=32, struct_type="Quat")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Quat"
        assert abs(result.fields["X"] - 1.5) < 1e-10
        assert abs(result.fields["Y"] - 2.5) < 1e-10
        assert abs(result.fields["Z"] - 3.5) < 1e-10
        assert abs(result.fields["W"] - 4.5) < 1e-10

    def test_plane_f32_fast_path(self, tmp_path):
        """Plane 标准 float 精度快速路径。"""
        data = struct.pack("<ffff", 0.0, 1.0, 0.0, -5.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestPlane", type="StructProperty", size=16, struct_type="Plane")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Plane"
        assert abs(result.fields["X"] - 0.0) < 1e-6
        assert abs(result.fields["W"] - (-5.0)) < 1e-6

    def test_plane_f64_lwc_fast_path(self, tmp_path):
        """Plane LWC double 精度快速路径（tag.size=32）。"""
        data = struct.pack("<dddd", 0.0, 1.0, 0.0, -5.5)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestPlane", type="StructProperty", size=32, struct_type="Plane")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Plane"
        assert abs(result.fields["X"] - 0.0) < 1e-10
        assert abs(result.fields["W"] - (-5.5)) < 1e-10

    def test_sphere_f32_fast_path(self, tmp_path):
        """Sphere 标准 float 精度快速路径。"""
        data = struct.pack("<ffff", 10.0, 20.0, 30.0, 5.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestSphere", type="StructProperty", size=16, struct_type="Sphere")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Sphere"
        assert abs(result.fields["Center"]["X"] - 10.0) < 1e-6
        assert abs(result.fields["W"] - 5.0) < 1e-6

    def test_sphere_f64_lwc_fast_path(self, tmp_path):
        """Sphere LWC double 精度快速路径（tag.size=32）。"""
        data = struct.pack("<dddd", 10.5, 20.5, 30.5, 5.5)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestSphere", type="StructProperty", size=32, struct_type="Sphere")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Sphere"
        assert abs(result.fields["Center"]["X"] - 10.5) < 1e-10
        assert abs(result.fields["W"] - 5.5) < 1e-10


# ============================================================================
# parse_struct_property — 版本感知尺寸验证
# ============================================================================

class TestStructPropertyVersionAwareValidation:
    """验证 parse_struct_property 的版本感知尺寸验证。"""

    def test_vector_f32_accepted_without_version(self, tmp_path):
        """Vector 12 字节（float）在无 summary 时被接受。"""
        data = struct.pack("<fff", 1.0, 2.0, 3.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="Pos", type="StructProperty", size=12, struct_type="Vector")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Vector"
        assert abs(result.fields["X"] - 1.0) < 1e-6

    def test_vector_f64_accepted_without_version(self, tmp_path):
        """Vector 24 字节（double）在无 summary 时通过预检查（属于 LWC 可变大小）。"""
        data = struct.pack("<ddd", 1.5, 2.5, 3.5)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="Pos", type="StructProperty", size=24, struct_type="Vector")
        # 无 summary 时，get_struct_size 返回 12（float），但 tag.size=24 不匹配
        # 预检查会 warning 并 fallback 到 generic path
        result = parse_struct_property(tag, archive, [], [], summary=None)
        # 应该返回 StructValue（fallback 到 generic path，无数据则 opaque）
        assert isinstance(result, StructValue)

    def test_vector_f32_size_mismatch_with_lwc_version(self, tmp_path):
        """Vector 12 字节在 UE5 LWC 版本下与预期 24 不匹配，fallback。"""
        data = struct.pack("<fff", 1.0, 2.0, 3.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="Pos", type="StructProperty", size=12, struct_type="Vector")

        # 创建一个具有 UE5 LWC 版本的 summary
        class MockSummary:
            file_version_ue5 = 1004
            file_version_ue4 = 0
            custom_versions = []

        result = parse_struct_property(tag, archive, [], [], summary=MockSummary())
        # 12 != 24 (LWC expected)，fallback 到 generic path
        assert isinstance(result, StructValue)
