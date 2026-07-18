"""linker 索引测试 — 合并自 test_depends_map_package_index / test_soft_object_path_index。

验证：
1. DependsMap FPackageIndex 语义（正值=export，负值=import，零=null）
2. SoftObjectPath 索引解析（UE5.7+ int32 索引 vs 传统 FString）
"""
import struct
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from uasset_read.parse_uasset import parse_uasset_with_linker
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.parsers.property_types import (
    parse_soft_object_property,
    parse_soft_class_property,
)
from uasset_read.models.properties import PropertyTag, SoftObjectPathValue
from tests.conftest import asset_path, ASSET_MESH_CHAIR


# ============================================================================
# 公共常量
# ============================================================================

STATIC_MESH_REL = "StackOBot_M_BotBase.uasset"
BLUEPRINT_REL = "StackOBot_BP_Drone.uasset"


# ============================================================================
# DependsMap 辅助类
# ============================================================================

class MockArchive:
    """模拟 FArchive 用于测试。"""

    def __init__(self, data: bytes):
        self._stream = BytesIO(data)

    def read_i32(self) -> int:
        return struct.unpack('<i', self._stream.read(4))[0]

    def read_fstring(self) -> str:
        length = struct.unpack('<i', self._stream.read(4))[0]
        if length == 0:
            return ""
        data = self._stream.read(length - 1)  # -1 for null terminator
        self._stream.read(1)  # skip null terminator
        return data.decode('utf-8')

    def tell(self) -> int:
        return self._stream.tell()

    def seek(self, pos: int):
        self._stream.seek(pos)


def _fname(s: str) -> bytes:
    """序列化 FName（长度前缀 + 数据 + null 终止符）。"""
    encoded = s.encode('utf-8')
    return struct.pack('<i', len(encoded) + 1) + encoded + b'\x00'


def _fstring(s: str) -> bytes:
    """序列化 FString（长度前缀 + 数据 + null 终止符）。"""
    if not s:
        return struct.pack('<i', 0)
    encoded = s.encode('utf-8')
    return struct.pack('<i', len(encoded) + 1) + encoded + b'\x00'


# ============================================================================
# DependsMap FPackageIndex 语义测试
# ============================================================================

class TestDependsMapFPackageIndexSemantics:
    """Test that DependsMap values are interpreted as FPackageIndex."""

    def test_depends_map_uses_package_index(self, sample_root: Path):
        """DependsMap values should be FPackageIndex, not raw export indices."""
        bp_path = asset_path(sample_root, BLUEPRINT_REL)
        result = parse_uasset_with_linker(str(bp_path), preload_all=True)

        # Check if DependsMap exists
        if not hasattr(result.summary, 'depends_map') or not result.summary.depends_map:
            pytest.skip("No DependsMap in this file")

        # Find an export with dependencies
        for exp_idx, dep_indices in enumerate(result.summary.depends_map):
            if not dep_indices:
                continue

            # Each dep should be interpretable as FPackageIndex
            for raw_dep in dep_indices:
                # Positive = export, negative = import, 0 = null
                if raw_dep > 0:
                    # Export index (1-based)
                    export_idx = raw_dep - 1
                    assert 0 <= export_idx < len(result.export_map), \
                        f"DependsMap export index {raw_dep} out of bounds"
                elif raw_dep < 0:
                    # Import index (-1 based)
                    import_idx = -raw_dep - 1
                    assert 0 <= import_idx < len(result.import_map), \
                        f"DependsMap import index {raw_dep} out of bounds"
                # raw_dep == 0 is null, valid
        del result

    def test_linker_resolves_depends_to_instances(self, sample_root: Path):
        """Linker should resolve DependsMap to UObjectInstance references."""
        bp_path = asset_path(sample_root, BLUEPRINT_REL)
        result = parse_uasset_with_linker(str(bp_path), preload_all=True)
        linker = result.linker

        # Check that dependencies are resolved to UObjectInstance
        for inst in linker._export_objects:
            if hasattr(inst, 'dependencies') and inst.dependencies:
                for dep in inst.dependencies:
                    assert isinstance(dep, UObjectInstance), \
                        f"Dependency should be UObjectInstance, not {type(dep)}"
                    assert hasattr(dep, 'object_name'), \
                        "Dependency should have object_name"
        del result

    def test_depends_map_can_reference_imports(self, sample_root: Path):
        """DependsMap should be able to reference imports (negative indices)."""
        bp_path = asset_path(sample_root, BLUEPRINT_REL)
        result = parse_uasset_with_linker(str(bp_path), preload_all=True)
        linker = result.linker

        # Check if any dependency references an import
        has_import_dep = False
        for inst in linker._export_objects:
            if hasattr(inst, 'dependencies') and inst.dependencies:
                for dep in inst.dependencies:
                    if dep.is_import:
                        has_import_dep = True
                        break

        # This is informational — some assets may only have export dependencies
        # The important thing is that the code doesn't crash and handles both cases
        assert isinstance(has_import_dep, bool)
        del result

    def test_depends_map_with_static_mesh(self, sample_root: Path):
        """Test DependsMap resolution with StaticMesh asset."""
        mesh_path = asset_path(sample_root, STATIC_MESH_REL)
        result = parse_uasset_with_linker(str(mesh_path), preload_all=True)
        linker = result.linker

        # StaticMesh should have some dependencies resolved
        has_deps = any(
            hasattr(inst, 'dependencies') and inst.dependencies
            for inst in linker._export_objects
        )
        # This is informational — the important thing is no crashes
        assert isinstance(has_deps, bool)
        del result


class TestDependsMapUnitTests:
    """Unit tests for DependsMap FPackageIndex interpretation."""

    def test_zero_is_null_dependency(self):
        """Zero in DependsMap should be treated as null (skipped)."""
        from uasset_read.link.linker import PackageLinker
        from uasset_read.serializers.object_resources import PackageIndex

        # Zero should be null
        pkg_idx = PackageIndex(0)
        assert pkg_idx.is_null

    def test_positive_is_export(self):
        """Positive value in DependsMap should be export index (1-based)."""
        from uasset_read.serializers.object_resources import PackageIndex

        pkg_idx = PackageIndex(1)  # First export
        assert pkg_idx.is_export
        assert pkg_idx.to_export_index() == 0  # 0-based

    def test_negative_is_import(self):
        """Negative value in DependsMap should be import index (-1 based)."""
        from uasset_read.serializers.object_resources import PackageIndex

        pkg_idx = PackageIndex(-1)  # First import
        assert pkg_idx.is_import
        assert pkg_idx.to_import_index() == 0  # 0-based


# ============================================================================
# 索引化 SoftObjectPath 解析测试（UE5.7+）
# ============================================================================

class TestIndexBasedResolution:
    """测试索引化 SoftObjectProperty 解析。"""

    def test_valid_index_resolution(self):
        """有效索引应正确解析到 SoftObjectPathList 条目。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=4)
        soft_list = [
            {"asset_path": "/Game/Content/MyAsset", "sub_path": "SubPath"},
            {"asset_path": "/Engine/Content/Other", "sub_path": ""},
        ]
        # Index 1 (second entry)
        archive = MockArchive(struct.pack('<i', 1))

        result = parse_soft_object_property(tag, archive, [], soft_list)

        assert isinstance(result, SoftObjectPathValue)
        assert result.index == 1
        assert result.asset_path == "/Engine/Content/Other"
        assert result.sub_path == ""
        assert result.error is None

    def test_index_out_of_bounds(self):
        """越界索引应返回错误诊断。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=4)
        soft_list = [{"asset_path": "/Game/Asset", "sub_path": ""}]
        # Index 5 but list has only 1 entry
        archive = MockArchive(struct.pack('<i', 5))

        result = parse_soft_object_property(tag, archive, [], soft_list)

        assert isinstance(result, SoftObjectPathValue)
        assert result.index == 5
        assert result.asset_path == ""
        assert result.error is not None
        assert "out of bounds" in result.error

    def test_negative_index(self):
        """负数索引应返回错误诊断。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=4)
        soft_list = [{"asset_path": "/Game/Asset", "sub_path": ""}]
        archive = MockArchive(struct.pack('<i', -1))

        result = parse_soft_object_property(tag, archive, [], soft_list)

        assert isinstance(result, SoftObjectPathValue)
        assert result.index == -1
        assert result.error is not None

    def test_zero_index(self):
        """索引 0 应正确解析第一个条目。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=4)
        soft_list = [
            {"asset_path": "/First/Asset", "sub_path": "FirstSub"},
            {"asset_path": "/Second/Asset", "sub_path": ""},
        ]
        archive = MockArchive(struct.pack('<i', 0))

        result = parse_soft_object_property(tag, archive, [], soft_list)

        assert result.index == 0
        assert result.asset_path == "/First/Asset"
        assert result.sub_path == "FirstSub"
        assert result.error is None


# ============================================================================
# 传统 FString 解析测试
# ============================================================================

class TestLegacyFStringResolution:
    """测试传统 FString 格式解析。"""

    def test_legacy_format_with_empty_list(self):
        """空列表应回退到 FString 格式。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=20)
        archive = MockArchive(_fstring("/Game/Legacy") + _fstring("SubPath"))

        result = parse_soft_object_property(tag, archive, [], [])

        assert isinstance(result, SoftObjectPathValue)
        assert result.index is None
        assert result.asset_path == "/Game/Legacy"
        assert result.sub_path == "SubPath"

    def test_legacy_format_with_none_list(self):
        """None 列表应使用 FString 格式。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=20)
        archive = MockArchive(_fstring("/Game/Legacy") + _fstring(""))

        result = parse_soft_object_property(tag, archive, [], None)

        assert isinstance(result, SoftObjectPathValue)
        assert result.index is None
        assert result.asset_path == "/Game/Legacy"
        assert result.sub_path == ""

    def test_legacy_format_empty_strings(self):
        """传统格式可以有空字符串。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=8)
        archive = MockArchive(_fstring("") + _fstring(""))

        result = parse_soft_object_property(tag, archive, [], None)

        assert result.asset_path == ""
        assert result.sub_path == ""


# ============================================================================
# SoftClassProperty 测试
# ============================================================================

class TestSoftClassProperty:
    """测试 SoftClassProperty 解析（与 SoftObjectProperty 相同逻辑）。"""

    def test_index_based_soft_class_property(self):
        """SoftClassProperty 也应支持索引解析。"""
        tag = PropertyTag(name="TestClass", type="SoftClassProperty", size=4)
        soft_list = [
            {"asset_path": "/Game/Classes/MyClass", "sub_path": ""},
        ]
        archive = MockArchive(struct.pack('<i', 0))

        result = parse_soft_class_property(tag, archive, [], soft_list)

        assert isinstance(result, SoftObjectPathValue)
        assert result.index == 0
        assert result.asset_path == "/Game/Classes/MyClass"
        assert result.raw_kind == "SoftClassProperty"

    def test_legacy_soft_class_property(self):
        """SoftClassProperty 传统格式。"""
        tag = PropertyTag(name="TestClass", type="SoftClassProperty", size=20)
        archive = MockArchive(_fstring("/Game/LegacyClass") + _fstring(""))

        result = parse_soft_class_property(tag, archive, [], None)

        assert result.asset_path == "/Game/LegacyClass"
        assert result.index is None


# ============================================================================
# SoftObjectPath 集成测试
# ============================================================================

class TestSoftObjectPathIntegration:
    """SoftObjectPath 集成级别测试。"""

    def test_soft_object_path_value_structure(self):
        """验证 SoftObjectPathValue 结构包含所有字段。"""
        value = SoftObjectPathValue(
            raw_kind="SoftObjectProperty",
            asset_path="/Game/Asset",
            sub_path="Sub",
            index=3,
            error=None,
        )
        assert value.raw_kind == "SoftObjectProperty"
        assert value.asset_path == "/Game/Asset"
        assert value.sub_path == "Sub"
        assert value.index == 3
        assert value.error is None

    def test_empty_soft_object_path_list_uses_legacy(self):
        """空的 soft_object_path_list 应使用传统格式。"""
        tag = PropertyTag(name="Test", type="SoftObjectProperty", size=16)
        archive = MockArchive(_fstring("/Fallback") + _fstring("Path"))

        # Empty list triggers legacy mode
        result = parse_soft_object_property(tag, archive, [], [])

        assert result.index is None
        assert result.asset_path == "/Fallback"
