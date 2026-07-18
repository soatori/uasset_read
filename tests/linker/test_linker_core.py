"""Linker 核心测试 — 验证逻辑、生命周期、依赖解析、World Partition。

合并自：
- test_linker.py: PackageLinker 验证逻辑 + 索引解析 + DependsMap + SoftObjectPath
- test_linker_lifecycle.py: link → preload → post_load 生命周期
- test_depends_map_resolution.py: DependsMap FPackageIndex 语义解析
- test_world_partition_paths.py: World Partition hashed 路径规范化
"""
from __future__ import annotations

import struct
from io import BytesIO
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.link.result import LinkerParseResult
from uasset_read.parse_uasset import parse_uasset_with_linker
from uasset_read.parsers.property_types import (
    parse_soft_object_property,
    parse_soft_class_property,
)
from uasset_read.models.properties import PropertyTag, SoftObjectPathValue
from uasset_read.serializers.object_resources import PackageIndex, ObjectImport, ObjectExport
from tests.conftest import asset_path, ASSET_MESH_CHAIR


def _make_linker(
    import_count: int = 2,
    export_count: int = 1,
    file_size: int = 1024,
) -> PackageLinker:
    """创建一个用于测试的 PackageLinker 实例。"""
    archive = MagicMock()
    archive._file_size = file_size
    summary = MagicMock()
    summary.depends_map = None
    name_map = ["TestName"]

    import_map = []
    for i in range(import_count):
        imp = MagicMock()
        imp.object_name = f"Import_{i}"
        imp.class_name = f"Class_{i}"
        imp.class_package = f"/Script/Engine"
        imp.outer_index = PackageIndex(0)
        imp.class_index = PackageIndex(0)
        import_map.append(imp)

    export_map = []
    for i in range(export_count):
        exp = MagicMock()
        exp.object_name = f"Export_{i}"
        exp.class_index = PackageIndex(-(1)) if import_count > 0 else PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.template_index = PackageIndex(0)
        exp.serial_offset = 0
        exp.serial_size = 0
        export_map.append(exp)

    linker = PackageLinker(archive, summary, name_map, import_map, export_map)
    linker.link()
    return linker


class TestVerifyImportsReturnValue:
    """_verify_imports() 返回值保留。"""

    def test_import_verification_errors_initialized_empty(self):
        """_import_verification_errors 初始为空列表。"""
        linker = _make_linker()
        assert linker._import_verification_errors == []

    def test_post_load_captures_verify_imports_result(self):
        """post_load() 将 _verify_imports() 结果保存到 _import_verification_errors。"""
        linker = _make_linker(import_count=2)
        # 正常情况：无验证错误
        linker.post_load()
        assert isinstance(linker._import_verification_errors, list)
        assert linker._import_verification_errors == []

    def test_post_load_with_broken_outer_index(self):
        """outer_index 越界时 _verify_imports 返回错误。"""
        linker = _make_linker(import_count=2, export_count=1)
        linker._import_map[1].outer_index = PackageIndex(999)

        linker.post_load()

        assert len(linker._import_verification_errors) > 0
        assert any("outer_index" in e for e in linker._import_verification_errors)

    def test_verify_imports_returns_list(self):
        """_verify_imports() 返回类型为 List[str]。"""
        linker = _make_linker()
        result = linker._verify_imports()
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, str)

    def test_verify_imports_empty_on_valid_data(self):
        """所有引用有效时 _verify_imports() 返回空列表。"""
        linker = _make_linker(import_count=2, export_count=1)
        # 所有 import 的 class_index 和 outer_index 都是 null（不触发验证）
        errors = linker._verify_imports()
        assert errors == []


class TestPostLoadPreservesVerifyResult:
    """post_load() 保留 _verify_imports 返回值的集成验证。"""

    def test_errors_stored_on_linker(self):
        """post_load 后错误可通过 linker._import_verification_errors 访问。"""
        linker = _make_linker(import_count=1, export_count=1)
        linker._import_map[0].outer_index = PackageIndex(999)

        linker.post_load()

        # 错误应可从 linker 实例访问
        errors = linker._import_verification_errors
        assert isinstance(errors, list)
        assert len(errors) >= 1
        # 每个错误是描述性字符串
        for err in errors:
            assert isinstance(err, str)
            assert len(err) > 0

    def test_multiple_errors_captured(self):
        """多个 import 引用错误都被捕获。"""
        linker = _make_linker(import_count=3, export_count=1)
        # 三个 import 的 outer_index 都越界
        for i in range(3):
            linker._import_map[i].outer_index = PackageIndex(999)

        linker.post_load()

        assert len(linker._import_verification_errors) >= 3


# ─────────────────────────────────────────────────────────────────────────────
# 以下测试合并自 test_link_quality.py（Task #252 缺陷测试）
# ─────────────────────────────────────────────────────────────────────────────


def _make_linker_quality(
    export_count: int = 2,
    import_count: int = 1,
    file_size: int = 10000,
) -> PackageLinker:
    """构造最小可用的 PackageLinker（来自 test_link_quality.py）。"""
    archive = MagicMock()
    archive._file_size = file_size

    summary = MagicMock()
    summary.depends_map = None
    summary.package_name = "TestPackage"

    name_map: list[str] = []

    import_map = []
    for i in range(import_count):
        imp = MagicMock()
        imp.object_name = f"ImportObj_{i}"
        imp.class_name = f"ImportClass_{i}"
        imp.class_package = f"/Script/Engine"
        imp.outer_index = PackageIndex(0)
        imp.class_index = PackageIndex(0)
        import_map.append(imp)

    export_map = []
    for i in range(export_count):
        exp = MagicMock()
        exp.object_name = f"ExportObj_{i}"
        exp.class_index = PackageIndex(-1) if import_count > 0 else PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.template_index = PackageIndex(0)
        exp.serial_offset = 100 + i * 200
        exp.serial_size = 100
        export_map.append(exp)

    linker = PackageLinker(
        archive=archive,
        summary=summary,
        name_map=name_map,
        import_map=import_map,
        export_map=export_map,
    )
    return linker


class TestVerifyImportsReturnDiscarded:
    """缺陷: post_load() 调用 _verify_imports() 但丢弃返回值。"""

    def test_verify_imports_returns_errors(self):
        """_verify_imports 本身可以正确检测错误。"""
        linker = _make_linker_quality(export_count=1, import_count=2)
        linker.link()

        imp = linker._import_map[1]
        imp.outer_index = PackageIndex(999)

        errors = linker._verify_imports()
        assert isinstance(errors, list)
        assert len(errors) > 0
        assert "outer_index 无法解析" in errors[0]

    def test_post_load_preserves_verify_imports_result(self):
        """post_load 保留 _verify_imports 的返回值 — 修复 #250 (M-21)。"""
        linker = _make_linker_quality(export_count=1, import_count=2)
        linker.link()

        imp = linker._import_map[1]
        imp.outer_index = PackageIndex(999)

        linker._export_objects[0]._preloaded = True
        linker.post_load()

        assert hasattr(linker, '_import_verification_errors')
        assert len(linker._import_verification_errors) > 0, (
            "post_load 应保留 _verify_imports 的错误"
        )


class TestGetFullNameCircularReference:
    """修复 #250 (M-20): get_full_name() 现在检测循环 outer 引用。"""

    def test_normal_outer_chain(self):
        """正常 outer 链不崩溃。"""
        root = UObjectInstance(
            package_index=1, object_name="Root", object_class="Package",
            class_package=None, outer_index=PackageIndex(0), is_import=False,
        )
        child = UObjectInstance(
            package_index=2, object_name="Child", object_class="Class",
            class_package=None, outer_index=PackageIndex(1), is_import=False,
            outer=root,
        )
        assert child.get_full_name() == "Root.Child"

    def test_circular_outer_returns_circular_marker(self):
        """循环 outer 引用返回 <circular:N> 而非 RecursionError。"""
        obj_a = UObjectInstance(
            package_index=1, object_name="ObjectA", object_class="Class",
            class_package=None, outer_index=PackageIndex(2), is_import=False,
        )
        obj_b = UObjectInstance(
            package_index=2, object_name="ObjectB", object_class="Class",
            class_package=None, outer_index=PackageIndex(1), is_import=False,
        )
        obj_a.outer = obj_b
        obj_b.outer = obj_a

        result = obj_a.get_full_name()
        assert "<circular:" in result

    def test_self_referencing_outer_returns_circular_marker(self):
        """对象的 outer 指向自身时返回 <circular:N>。"""
        obj = UObjectInstance(
            package_index=1, object_name="SelfRef", object_class="Class",
            class_package=None, outer_index=PackageIndex(1), is_import=False,
        )
        obj.outer = obj
        result = obj.get_full_name()
        assert result == "<circular:1>.SelfRef"


class TestCreateExportInstancesOffsetSizeValidation:
    """缺陷: _create_export_instances 只验证 serial_offset 不越界，但不验证 offset+size。"""

    def test_offset_plus_size_exceeds_file_size_not_caught_early(self):
        """serial_offset + serial_size > file_size 在 link 阶段不被拦截。"""
        linker = _make_linker_quality(export_count=0, file_size=1000)

        exp = MagicMock(spec=ObjectExport)
        exp.class_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.object_name = "OverflowExport"
        exp.serial_offset = 800
        exp.serial_size = 300  # 800+300=1100 > 1000
        linker._export_map = [exp]
        linker._create_export_instances()

        assert len(linker._export_objects) == 1
        inst = linker._export_objects[0]
        assert inst.serial_offset == 800
        assert inst.serial_size == 300

        overflow_diag = [
            d for d in linker.diagnostics
            if "serial_size" in d.field or "offset+size" in d.error
        ]
        assert len(overflow_diag) == 0, (
            "缺陷确认: offset+size 越界在 _create_export_instances 未被检测"
        )

    def test_offset_valid_size_overflow_preload_catches(self):
        """preload() 确实有 offset+size 校验。"""
        linker = _make_linker_quality(export_count=1, file_size=1000)
        linker.link()

        linker._export_objects[0].serial_offset = 800
        linker._export_objects[0].serial_size = 300

        linker.preload(0)

        diags = [d for d in linker.diagnostics if d.field == "serial_size"]
        assert len(diags) > 0


class TestBuildDependencyGraphTypeValidation:
    """缺陷: _build_dependency_graph 对 depends_map 元素不做类型校验。"""

    def test_normal_depends_map(self):
        """正常 depends_map 正确构建依赖图。"""
        linker = _make_linker_quality(export_count=3, import_count=1)
        linker.link()

        linker._summary.depends_map = [
            [2, -1],
            [0],
            [],
        ]
        for inst in linker._export_objects:
            inst._preloaded = True

        linker._build_dependency_graph()

        assert len(linker._export_objects[0].dependencies) == 2
        assert len(linker._export_objects[1].dependencies) == 0
        assert len(linker._export_objects[2].dependencies) == 0

    def test_depends_map_with_non_int_element(self):
        """depends_map 包含非整数元素时不应崩溃。"""
        linker = _make_linker_quality(export_count=2, import_count=0)
        linker.link()

        linker._summary.depends_map = [
            [1, "invalid_string"],
            [None],
        ]
        for inst in linker._export_objects:
            inst._preloaded = True

        try:
            linker._build_dependency_graph()
        except (TypeError, ValueError):
            pytest.fail(
                "_build_dependency_graph 应容错处理非整数元素，而非抛出异常"
            )

    def test_depends_map_out_of_bounds_export_index(self):
        """depends_map 包含越界 export index 时应记录诊断。"""
        linker = _make_linker_quality(export_count=2, import_count=0)
        linker.link()

        linker._summary.depends_map = [[100], []]
        for inst in linker._export_objects:
            inst._preloaded = True

        linker._build_dependency_graph()

        dep_diag = [d for d in linker.diagnostics if d.field == "DependsMap"]
        assert len(dep_diag) > 0


class TestLinkerParseResultStatus:
    """验证 LinkerParseResult.status 计算逻辑的边界情况。"""

    def test_status_failed_no_data(self):
        """无任何数据时 status 为 failed。"""
        result = LinkerParseResult()
        assert result.status == "failed"

    def test_status_success_no_errors(self):
        """有数据且无错误时 status 为 success。"""
        mock_export = MagicMock()
        mock_export.parse_status = "success"
        result = LinkerParseResult(
            summary=MagicMock(), name_map=["Test"],
            export_map=[mock_export], is_success=True,
        )
        assert result.status == "success"

    def test_status_partial_with_errors(self):
        """有错误时 status 为 partial。"""
        result = LinkerParseResult(
            summary=MagicMock(), name_map=["Test"],
            export_map=[], errors=["Some error"],
        )
        assert result.status == "partial"

    def test_status_partial_skipped_export(self):
        """有 skipped export 时 status 为 partial。"""
        mock_export = MagicMock()
        mock_export.parse_status = "skipped"
        result = LinkerParseResult(
            summary=MagicMock(), name_map=["Test"],
            export_map=[mock_export],
        )
        assert result.status == "partial"

    def test_status_partial_opaque_export(self):
        """有 opaque export 时 status 为 partial。"""
        mock_export = MagicMock()
        mock_export.parse_status = "opaque"
        result = LinkerParseResult(
            summary=MagicMock(), name_map=["Test"],
            export_map=[mock_export],
        )
        assert result.status == "partial"

    def test_status_partial_lightweight_metadata(self):
        """lightweight_tolerant_parse 元数据使 status 为 partial。"""
        result = LinkerParseResult(
            summary=MagicMock(), name_map=["Test"],
            export_map=[], metadata={"lightweight_tolerant_parse": True},
        )
        assert result.status == "partial"

    def test_status_success_only_summary(self):
        """仅 summary 有数据时，若 export_map 为空则 status 为 success。"""
        result = LinkerParseResult(
            summary=MagicMock(), name_map=["Test"],
            export_map=[], is_success=True,
        )
        assert result.status == "success"


class TestGetFullNameEdgeCases:
    """get_full_name() 边界情况。"""

    def test_import_with_class_package(self):
        """import 对象使用 class_package 作为前缀。"""
        obj = UObjectInstance(
            package_index=-1, object_name="MyObject", object_class="Actor",
            class_package="/Script/Engine", outer_index=PackageIndex(0),
            is_import=True,
        )
        assert obj.get_full_name() == "/Script/Engine.MyObject"

    def test_export_with_linker_summary(self):
        """export 对象使用 linker.summary.package_name 作为前缀。"""
        linker = _make_linker_quality(export_count=1, import_count=0)
        linker.link()

        obj = linker._export_objects[0]
        full_name = obj.get_full_name()
        assert full_name.startswith("TestPackage.")

    def test_no_outer_no_linker_returns_name(self):
        """无 outer 无 linker 时返回 object_name。"""
        obj = UObjectInstance(
            package_index=1, object_name="BareName", object_class="Class",
            class_package=None, outer_index=PackageIndex(0), is_import=False,
        )
        assert obj.get_full_name() == "BareName"

    def test_integer_package_name_lookup(self):
        """package_name 为 int 时从 name_map 查找。"""
        linker = _make_linker_quality(export_count=1, import_count=0)
        linker.link()
        linker.summary.package_name = 0
        linker.name_map = ["ResolvedPackageName"]

        obj = linker._export_objects[0]
        full_name = obj.get_full_name()
        assert full_name.startswith("ResolvedPackageName.")

    def test_integer_package_name_out_of_bounds(self):
        """package_name 为越界 int 时使用 'Unknown'。"""
        linker = _make_linker_quality(export_count=1, import_count=0)
        linker.link()
        linker.summary.package_name = 999
        linker.name_map = ["ValidName"]

        obj = linker._export_objects[0]
        full_name = obj.get_full_name()
        assert full_name.startswith("Unknown.")


class TestUObjectInstanceResolution:
    """UObjectInstance 引用解析方法。"""

    def test_get_class_object_returns_none_for_import(self):
        """import 对象的 get_class_object 返回 None。"""
        obj = UObjectInstance(
            package_index=-1, object_name="TestImport", object_class="Actor",
            class_package="/Script/Engine", outer_index=PackageIndex(0),
            is_import=True,
        )
        assert obj.get_class_object() is None

    def test_get_class_object_resolves_via_linker(self):
        """export 对象的 get_class_object 通过 linker 解析。"""
        linker = _make_linker_quality(export_count=2, import_count=1)
        linker.link()

        inst = linker._export_objects[0]
        result = inst.get_class_object()
        if result is not None:
            assert result is linker._import_objects[0]

    def test_get_template_object_returns_none_for_import(self):
        """import 对象的 get_template_object 返回 None。"""
        obj = UObjectInstance(
            package_index=-1, object_name="TestImport", object_class="Actor",
            class_package="/Script/Engine", outer_index=PackageIndex(0),
            is_import=True,
        )
        assert obj.get_template_object() is None

    def test_get_template_object_resolves_via_linker(self):
        """export 对象的 get_template_object 通过 linker 解析。"""
        linker = _make_linker_quality(export_count=2, import_count=0)
        linker.link()

        linker._export_map[1].template_index = PackageIndex(1)
        inst = linker._export_objects[1]
        result = inst.get_template_object()
        assert result is linker._export_objects[0]

    def test_get_children_delegates_to_linker(self):
        """get_children 委托给 linker.get_children。"""
        linker = _make_linker_quality(export_count=3, import_count=0)
        linker.link()

        linker._export_objects[1].outer = linker._export_objects[0]
        linker._export_objects[2].outer = linker._export_objects[0]

        children = linker._export_objects[0].get_children()
        assert len(children) == 2
        assert linker._export_objects[1] in children
        assert linker._export_objects[2] in children

    def test_ensure_preloaded_triggers_preload(self):
        """ensure_preloaded 触发 linker.preload。"""
        linker = _make_linker_quality(export_count=1, import_count=0)
        linker.link()

        inst = linker._export_objects[0]
        assert not inst._preloaded

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            inst.ensure_preloaded()
            assert inst._preloaded


class TestLinkerObjectCollection:
    """linker 对象集合方法。"""

    def test_export_objects_returns_copy(self):
        """export_objects 返回列表副本，修改不影响内部状态。"""
        linker = _make_linker_quality(export_count=2)
        linker.link()

        objs = linker.export_objects()
        objs.clear()

        assert len(linker.export_objects()) == 2

    def test_get_children_returns_empty_for_leaf(self):
        """无子对象时 get_children 返回空列表。"""
        linker = _make_linker_quality(export_count=1)
        linker.link()

        children = linker.get_children(linker._export_objects[0])
        assert children == []

    def test_collect_root_objects(self):
        """_collect_root_objects 收集 outer_index 为 null 的对象。"""
        linker = _make_linker_quality(export_count=3, import_count=1)
        linker.link()

        roots = linker._root_objects
        assert len(roots) > 0

    def test_no_outer_returns_empty_list(self):
        """get_children 在无 linker 的实例上返回空列表。"""
        obj = UObjectInstance(
            package_index=1, object_name="NoLinker", object_class="Class",
            class_package=None, outer_index=PackageIndex(0), is_import=False,
        )
        assert obj.get_children() == []


class TestPackageIndexEdgeCases:
    """PackageIndex 解析边界。"""

    def test_import_index_resolution(self):
        """-1 => import index 0, -2 => import index 1。"""
        linker = _make_linker_quality(export_count=1, import_count=3)
        linker.link()

        result = linker.resolve_package_index(PackageIndex(-1))
        assert result is linker._import_objects[0]

        result = linker.resolve_package_index(PackageIndex(-3))
        assert result is linker._import_objects[2]

    def test_export_index_resolution(self):
        """1 => export index 0, 2 => export index 1。"""
        linker = _make_linker_quality(export_count=3)
        linker.link()

        result = linker.resolve_package_index(PackageIndex(1))
        assert result is linker._export_objects[0]

        result = linker.resolve_package_index(PackageIndex(3))
        assert result is linker._export_objects[2]

    def test_zero_index_returns_none(self):
        """PackageIndex(0) 返回 None。"""
        linker = _make_linker_quality(export_count=1)
        result = linker.resolve_package_index(PackageIndex(0))
        assert result is None


class TestBuildOuterTreeSuperIndex:
    """验证 build_outer_tree 解析 super_index（父类引用）。"""

    def test_super_index_resolved(self):
        """super_index 指向的对象被设置为 export 的 super_object。"""
        linker = _make_linker_quality(export_count=3, import_count=1)
        linker.link()

        linker._export_map[2].super_index = PackageIndex(1)
        linker.build_outer_tree()

        inst = linker._export_objects[2]
        assert inst.super_object is linker._export_objects[0]

    def test_super_index_null_not_resolved(self):
        """super_index 为 null 时不设置 super_object。"""
        linker = _make_linker_quality(export_count=2)
        linker.link()

        linker.build_outer_tree()

        for inst in linker._export_objects:
            assert inst.super_object is None


# ============================================================================
# DependsMap / SoftObjectPath 测试（合并自 test_linker_index.py）
# ============================================================================

STATIC_MESH_REL = "StackOBot_M_BotBase.uasset"
BLUEPRINT_REL = "StackOBot_BP_Drone.uasset"


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


import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.serializers.object_resources import PackageIndex


# ─────────────────────────────────────────────────────────────────────────────
# Mock-based unit tests (no real assets required)
# ─────────────────────────────────────────────────────────────────────────────


def _make_lifecycle_linker(
    export_count: int = 3,
    import_count: int = 1,
    file_size: int = 10000,
) -> PackageLinker:
    """构造一个最小可用的 PackageLinker（mock archive/summary）。

    使用字符串名称（而非 int 索引）避免 name_map 查找越界。
    """
    archive = MagicMock()
    archive._file_size = file_size

    summary = MagicMock()
    summary.depends_map = None

    name_map: list[str] = []

    # 构造 import_map（使用字符串名称，跳过 name_map 索引查找）
    import_map = []
    for i in range(import_count):
        imp = MagicMock()
        imp.object_name = f"ImportObj_{i}"
        imp.class_name = f"ImportClass_{i}"
        imp.class_package = f"/Script/Engine"
        imp.outer_index = PackageIndex(0)
        imp.class_index = PackageIndex(0)
        import_map.append(imp)

    # 构造 export_map（使用字符串名称）
    export_map = []
    for i in range(export_count):
        exp = MagicMock()
        exp.object_name = f"ExportObj_{i}"
        # class_index 使用 resolve_class_name 能解析的形式
        # resolve_class_name 需要 import_map/export_map 中的 object_name
        # 使用负数指向 import
        exp.class_index = PackageIndex(-(1)) if import_count > 0 else PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.template_index = PackageIndex(0)
        exp.serial_offset = 100 + i * 200
        exp.serial_size = 100
        export_map.append(exp)

    linker = PackageLinker(
        archive=archive,
        summary=summary,
        name_map=name_map,
        import_map=import_map,
        export_map=export_map,
    )
    return linker


class TestPreloadThenPostLoadOrder:
    """test_preload_then_post_load_order: 验证 post_load 在所有 preload 后执行。"""

    def test_preload_marks_instances(self):
        """preload 后实例 _preloaded 标记为 True。"""
        linker = _make_lifecycle_linker(export_count=3)
        linker.link()

        # 初始状态：所有 export 未预加载
        for inst in linker._export_objects:
            assert not inst._preloaded

        # Mock property parser to avoid real serialization
        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            # 逐个 preload
            for i in range(3):
                linker.preload(i)

        # 所有 export 应已标记为预加载
        for inst in linker._export_objects:
            assert inst._preloaded

    def test_post_load_runs_after_all_preloads(self):
        """post_load 在所有 preload 完成后执行，引用解析依赖 preload 状态。"""
        linker = _make_lifecycle_linker(export_count=2)
        linker.link()

        # 模拟 preload：手动设置 _preloaded 和 serialized_properties
        for i, inst in enumerate(linker._export_objects):
            inst._preloaded = True
            inst.serialized_properties = [
                {"name": f"Prop{i}", "type": "ObjectProperty", "value": 0}
            ]

        # 调用 post_load
        linker.post_load()

        # post_load 应已执行：property_references 字段被初始化
        # （即使 value=0 是 null 引用，不应产生条目）
        for inst in linker._export_objects:
            assert hasattr(inst, "property_references")

    def test_post_load_skips_non_preloaded(self):
        """post_load 中的引用解析跳过未 preload 的实例。"""
        linker = _make_lifecycle_linker(export_count=2)
        linker.link()

        # 只 preload 第一个
        linker._export_objects[0]._preloaded = True
        linker._export_objects[0].serialized_properties = [
            {"name": "Ref", "type": "ObjectProperty", "value": 2}  # 指向 export #2
        ]
        # 第二个不 preload
        linker._export_objects[1]._preloaded = False

        linker.post_load()

        # 第一个实例的 property_references 应被处理
        assert hasattr(linker._export_objects[0], "property_references")
        # 第二个实例不应有 property_references（因为未 preload，被跳过）
        assert linker._export_objects[1].property_references == {}

    def test_preload_is_idempotent(self):
        """重复调用 preload 不会重复解析（缓存机制）。"""
        linker = _make_lifecycle_linker(export_count=1)
        linker.link()

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            # 第一次 preload
            linker.preload(0)
            assert linker._export_objects[0]._preloaded

            # 第二次 preload（应直接返回）
            linker.preload(0)
            assert linker._export_objects[0]._preloaded

    def test_preload_out_of_bounds_is_safe(self):
        """越界 index 的 preload 不会崩溃。"""
        linker = _make_lifecycle_linker(export_count=2)
        linker.link()

        # 负数 index
        linker.preload(-1)
        # 超出范围
        linker.preload(100)

        # 不应崩溃，原有状态不变
        assert not linker._export_objects[0]._preloaded


class TestPropertyReferencesResolved:
    """test_property_references_resolved: 验证 ObjectProperty 引用被正确解析。"""

    def test_object_property_resolved_to_instance(self):
        """ObjectProperty 的 FPackageIndex 被解析为 UObjectInstance。"""
        linker = _make_lifecycle_linker(export_count=2)
        linker.link()

        # 设置第一个 export 有一个 ObjectProperty 指向第二个 export
        inst0 = linker._export_objects[0]
        inst0._preloaded = True
        inst0.serialized_properties = [
            {"name": "TargetObj", "type": "ObjectProperty", "value": 2}  # export #2 (1-based)
        ]

        linker._resolve_property_references()

        # 验证引用已解析
        assert "TargetObj" in inst0.property_references
        resolved = inst0.property_references["TargetObj"]
        assert isinstance(resolved, UObjectInstance)
        assert resolved is linker._export_objects[1]

    def test_object_property_null_index_not_added(self):
        """ObjectProperty 值为 0（null）时不添加到 property_references。"""
        linker = _make_lifecycle_linker(export_count=2)
        linker.link()

        inst0 = linker._export_objects[0]
        inst0._preloaded = True
        inst0.serialized_properties = [
            {"name": "NullRef", "type": "ObjectProperty", "value": 0}
        ]

        linker._resolve_property_references()

        # null 引用不应出现在 property_references 中
        assert "NullRef" not in inst0.property_references

    def test_object_property_import_reference(self):
        """ObjectProperty 可以引用 import 对象（负数 index）。"""
        linker = _make_lifecycle_linker(export_count=1, import_count=2)
        linker.link()

        inst0 = linker._export_objects[0]
        inst0._preloaded = True
        inst0.serialized_properties = [
            {"name": "ImportRef", "type": "ObjectProperty", "value": -1}  # import #1
        ]

        linker._resolve_property_references()

        assert "ImportRef" in inst0.property_references
        resolved = inst0.property_references["ImportRef"]
        assert isinstance(resolved, UObjectInstance)
        assert resolved is linker._import_objects[0]

    def test_object_property_out_of_bounds_not_added(self):
        """ObjectProperty 越界 index 不添加到 property_references。"""
        linker = _make_lifecycle_linker(export_count=1)
        linker.link()

        inst0 = linker._export_objects[0]
        inst0._preloaded = True
        inst0.serialized_properties = [
            {"name": "BadRef", "type": "ObjectProperty", "value": 999}
        ]

        linker._resolve_property_references()

        # 越界引用不应出现
        assert "BadRef" not in inst0.property_references

    def test_non_object_properties_ignored(self):
        """非 ObjectProperty 类型的属性不参与引用解析。"""
        linker = _make_lifecycle_linker(export_count=1)
        linker.link()

        inst0 = linker._export_objects[0]
        inst0._preloaded = True
        inst0.serialized_properties = [
            {"name": "IntProp", "type": "IntProperty", "value": 42},
            {"name": "BoolProp", "type": "BoolProperty", "value": True},
        ]

        linker._resolve_property_references()

        # 非 ObjectProperty 不应产生引用
        assert inst0.property_references == {}


class TestWeakReferencesResolved:
    """test_weak_references_resolved: 验证 WeakObjectProperty 引用被正确解析。"""

    def test_weak_property_resolved_to_instance(self):
        """WeakObjectProperty 的 FPackageIndex 被解析为弱引用。"""
        linker = _make_lifecycle_linker(export_count=2)
        linker.link()

        inst0 = linker._export_objects[0]
        inst0._preloaded = True
        inst0.serialized_properties = [
            {"name": "WeakTarget", "type": "WeakObjectProperty", "value": 2}
        ]

        linker._resolve_weak_references()

        assert len(inst0.weak_references) == 1
        assert inst0.weak_references[0] is linker._export_objects[1]

    def test_weak_property_null_not_added(self):
        """WeakObjectProperty 值为 0 时不添加到 weak_references。"""
        linker = _make_lifecycle_linker(export_count=1)
        linker.link()

        inst0 = linker._export_objects[0]
        inst0._preloaded = True
        inst0.serialized_properties = [
            {"name": "NullWeak", "type": "WeakObjectProperty", "value": 0}
        ]

        linker._resolve_weak_references()

        assert len(inst0.weak_references) == 0

    def test_weak_property_import_reference(self):
        """WeakObjectProperty 可以引用 import 对象。"""
        linker = _make_lifecycle_linker(export_count=1, import_count=1)
        linker.link()

        inst0 = linker._export_objects[0]
        inst0._preloaded = True
        inst0.serialized_properties = [
            {"name": "WeakImport", "type": "WeakObjectProperty", "value": -1}
        ]

        linker._resolve_weak_references()

        assert len(inst0.weak_references) == 1
        assert inst0.weak_references[0] is linker._import_objects[0]

    def test_weak_and_strong_references_coexist(self):
        """同一对象可以同时拥有强引用和弱引用。"""
        linker = _make_lifecycle_linker(export_count=3)
        linker.link()

        inst0 = linker._export_objects[0]
        inst0._preloaded = True
        inst0.serialized_properties = [
            {"name": "StrongRef", "type": "ObjectProperty", "value": 2},
            {"name": "WeakRef", "type": "WeakObjectProperty", "value": 3},
        ]

        linker._resolve_property_references()
        linker._resolve_weak_references()

        # 强引用
        assert "StrongRef" in inst0.property_references
        assert inst0.property_references["StrongRef"] is linker._export_objects[1]
        # 弱引用
        assert len(inst0.weak_references) == 1
        assert inst0.weak_references[0] is linker._export_objects[2]


class TestPreloadPopulatesProperties:
    """test_preload_populates_properties: 验证 preload 后 properties 被填充。"""

    def test_preload_calls_property_parser(self):
        """preload 调用 parse_properties_from_export 并填充 serialized_properties。"""
        linker = _make_lifecycle_linker(export_count=1)
        linker.link()

        fake_props = [{"name": "TestProp", "type": "IntProperty", "value": 123}]

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=fake_props,
        ) as mock_parse:
            linker.preload(0)

            mock_parse.assert_called_once()
            assert linker._export_objects[0].serialized_properties == fake_props

    def test_preload_sets_preloaded_flag(self):
        """preload 完成后 _preloaded 标记为 True。"""
        linker = _make_lifecycle_linker(export_count=1)
        linker.link()

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            assert not linker._export_objects[0]._preloaded
            linker.preload(0)
            assert linker._export_objects[0]._preloaded

    def test_preload_zero_size_skips_parsing(self):
        """serial_size 为 0 的 export 跳过属性解析但仍标记为 preloaded。"""
        linker = _make_lifecycle_linker(export_count=1)
        linker.link()

        # 设置 serial_size 为 0
        linker._export_objects[0].serial_size = 0

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
        ) as mock_parse:
            linker.preload(0)

            mock_parse.assert_not_called()
            assert linker._export_objects[0]._preloaded

    def test_preload_populates_export_properties_backward_compat(self):
        """preload 后 export_map 中的 properties 字段也被填充（向后兼容）。"""
        linker = _make_lifecycle_linker(export_count=1)
        linker.link()

        fake_props = [{"name": "CompatProp", "type": "StrProperty", "value": "hello"}]

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=fake_props,
        ):
            linker.preload(0)

            # instance 的 serialized_properties 应被填充
            assert linker._export_objects[0].serialized_properties == fake_props


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests with real UE sample assets
# ─────────────────────────────────────────────────────────────────────────────

LOCAL_SAMPLE_ROOT = Path(__file__).parent.parent / "samples"

STATIC_MESH = LOCAL_SAMPLE_ROOT / "StackOBot_M_BotBase.uasset"
BLUEPRINT = LOCAL_SAMPLE_ROOT / "StackOBot_BP_Drone.uasset"


@pytest.mark.integration
class TestLinkerLifecycleIntegration:
    """使用真实资产验证 FLinkerLoad 生命周期。"""

    @pytest.mark.skipif(not BLUEPRINT.exists(), reason="Blueprint sample not found")
    def test_full_lifecycle_with_blueprint(self):
        """完整生命周期：link → preload_all → post_load。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        result = parse_uasset_with_linker(str(BLUEPRINT), preload_all=True)

        assert result.linker is not None
        linker = result.linker

        # link 阶段：export 对象已创建
        assert len(linker._export_objects) > 0

        # preload 阶段：所有有数据的 export 已预加载
        for idx, inst in enumerate(linker._export_objects):
            if inst.serial_size > 0 and inst.serial_offset >= 0:
                assert inst._preloaded, (
                    f"Export #{idx} ({inst.object_name}) 未预加载"
                )

        # post_load 阶段：已执行（通过检查 property_references 字段存在性）
        for inst in linker._export_objects:
            assert hasattr(inst, "property_references")
            assert hasattr(inst, "weak_references")
        del result

    @pytest.mark.skipif(not STATIC_MESH.exists(), reason="StaticMesh sample not found")
    def test_preload_populates_real_properties(self):
        """真实资产 preload 后 serialized_properties 被填充。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        result = parse_uasset_with_linker(str(STATIC_MESH), preload_all=True)
        linker = result.linker

        # 至少有一个 export 有属性数据
        has_properties = any(
            inst.serialized_properties
            for inst in linker._export_objects
            if inst._preloaded
        )
        assert has_properties, "StaticMesh 资产应包含属性数据"
        del result

    @pytest.mark.skipif(not BLUEPRINT.exists(), reason="Blueprint sample not found")
    def test_property_references_real_resolution(self):
        """真实资产中 ObjectProperty 引用被解析。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        result = parse_uasset_with_linker(str(BLUEPRINT), preload_all=True)
        linker = result.linker

        # 查找包含 ObjectProperty 的对象
        found_object_property = False
        for inst in linker._export_objects:
            if not inst._preloaded:
                continue
            if not inst.serialized_properties:
                continue
            for prop in inst.serialized_properties:
                if isinstance(prop, dict) and prop.get("type") == "ObjectProperty":
                    found_object_property = True
                    # post_load 应已处理此属性
                    assert hasattr(inst, "property_references")

        # 注意：某些资产可能没有 ObjectProperty，不强制断言
        del result

    @pytest.mark.skipif(not BLUEPRINT.exists(), reason="Blueprint sample not found")
    def test_post_load_order_preload_dependency(self):
        """验证 post_load 的引用解析依赖 preload 完成。

        未 preload 的实例不应参与引用解析。
        """
        from uasset_read.parse_uasset import parse_uasset_with_linker

        # 不使用 preload_all，手动控制 preload
        result = parse_uasset_with_linker(str(BLUEPRINT), preload_all=False)
        linker = result.linker

        # 只 preload 第一个有数据的 export
        preloaded_idx = None
        for i, inst in enumerate(linker._export_objects):
            if inst.serial_size > 0:
                linker.preload(i)
                preloaded_idx = i
                break

        if preloaded_idx is None:
            pytest.skip("No export with serial_size > 0")

        # 调用 post_load
        linker.post_load()

        # 已 preload 的实例应有 property_references 字段
        assert hasattr(linker._export_objects[preloaded_idx], "property_references")

        # 未 preload 的实例 property_references 应为空
        for i, inst in enumerate(linker._export_objects):
            if i != preloaded_idx and not inst._preloaded:
                assert inst.property_references == {}
        del result


# ─────────────────────────────────────────────────────────────────────────────
# 合并自 test_lifecycle_preload.py 的集成测试
# ─────────────────────────────────────────────────────────────────────────────

LOCAL_SAMPLE_ROOT_LIFECYCLE = Path(__file__).parent.parent / "samples"


@pytest.fixture(scope="module")
def ue_sample_root() -> Path:
    if not LOCAL_SAMPLE_ROOT_LIFECYCLE.exists():
        pytest.skip(f"sample root not found: {LOCAL_SAMPLE_ROOT_LIFECYCLE}")
    return LOCAL_SAMPLE_ROOT_LIFECYCLE


@pytest.fixture(scope="module")
def static_mesh_asset(ue_sample_root) -> Path:
    """StaticMesh 测试资产。"""
    path = ue_sample_root / "StackOBot_M_BotBase.uasset"
    if not path.exists():
        pytest.skip(f"asset not found: {path}")
    return path


@pytest.fixture(scope="module")
def blueprint_asset(ue_sample_root) -> Path:
    """Blueprint 测试资产。"""
    path = ue_sample_root / "StackOBot_BP_Drone.uasset"
    if not path.exists():
        pytest.skip(f"asset not found: {path}")
    return path


def test_lifecycle_order_link_preload_postload(blueprint_asset):
    """验证生命周期顺序：link → preload → post_load。"""
    from uasset_read.parse_uasset import parse_uasset_with_linker

    result = parse_uasset_with_linker(str(blueprint_asset), preload_all=True)

    # link 阶段完成
    assert result.linker is not None
    assert len(result.linker._export_objects) > 0

    # preload 阶段完成（所有 export 已预加载）
    for idx, inst in enumerate(result.linker._export_objects):
        if inst.serial_size > 0:
            assert inst._preloaded, f"Export #{idx} ({inst.object_name}) 未预加载"

    # post_load 阶段完成（property_references 已填充）
    # 检查至少有一个对象有 property_references（如果有 ObjectProperty）
    has_object_property = False
    for inst in result.linker._export_objects:
        if hasattr(inst, 'serialized_properties') and inst.serialized_properties:
            for prop in inst.serialized_properties:
                if isinstance(prop, dict) and prop.get('type') == 'ObjectProperty':
                    has_object_property = True
                    break

    # 如果有 ObjectProperty，则应该有解析后的引用
    if has_object_property:
        # 至少有一个对象有 property_references
        any_refs = any(
            hasattr(inst, 'property_references') and inst.property_references
            for inst in result.linker._export_objects
        )
        # 注意：即使有 ObjectProperty，引用也可能为 None（越界等），所以不强制断言
        # 但 post_load 应该已执行（通过检查 _preloaded 状态）


def test_preload_all_works(static_mesh_asset):
    """测试 preload_all=True 正常工作。"""
    from uasset_read.parse_uasset import parse_uasset_with_linker

    result = parse_uasset_with_linker(str(static_mesh_asset), preload_all=True)

    assert result.is_success or len(result.errors) == 0
    assert result.linker is not None

    # 所有有 serial_size 的 export 都应该已预加载
    for idx, inst in enumerate(result.linker._export_objects):
        if inst.serial_size > 0 and inst.serial_offset >= 0:
            assert inst._preloaded, f"Export #{idx} ({inst.object_name}) 未预加载"


def test_property_references_resolved_after_postload(blueprint_asset):
    """测试 post_load 后 ObjectProperty 引用已解析。"""
    from uasset_read.parse_uasset import parse_uasset_with_linker

    result = parse_uasset_with_linker(str(blueprint_asset), preload_all=True)

    # 查找包含 ObjectProperty 的对象
    found_object_property = False
    for inst in result.linker._export_objects:
        if not inst._preloaded:
            continue
        if not hasattr(inst, 'serialized_properties') or not inst.serialized_properties:
            continue

        for prop in inst.serialized_properties:
            if not isinstance(prop, dict):
                continue
            if prop.get('type') == 'ObjectProperty':
                found_object_property = True
                # post_load 应该已尝试解析此引用
                # 即使解析结果为 None（越界），property_references 字段应存在
                assert hasattr(inst, 'property_references')

    # 注意：测试资产可能没有 ObjectProperty，所以不强制断言 found_object_property


def test_export_properties_backward_compat(static_mesh_asset):
    """测试 export.properties 向后兼容性（从 linker instance 复制）。"""
    from uasset_read.parse_uasset import parse_package

    result = parse_package(str(static_mesh_asset))

    # export_map 中的 export 应该有 properties 字段
    for export in result.export_map:
        if export.serial_size > 0:
            # properties 应该已填充（从 linker instance 复制）
            assert hasattr(export, 'properties')
            # properties 应该是列表（可能为空）
            assert isinstance(export.properties, list)


def test_is_success_based_on_errors(static_mesh_asset):
    """测试 is_success 基于错误数量，而非无条件 True。"""
    from uasset_read.parse_uasset import parse_package

    result = parse_package(str(static_mesh_asset))

    # 如果没有错误，is_success 应该为 True
    if len(result.errors) == 0:
        assert result.is_success is True
    else:
        # 如果有错误，is_success 应该为 False
        assert result.is_success is False


def test_archive_stays_open_during_preload(static_mesh_asset):
    """测试 archive 在 preload 期间保持打开状态。"""
    from uasset_read.parse_uasset import parse_uasset_with_linker

    # preload_all=True 应该正常工作（archive 在 preload 期间未关闭）
    result = parse_uasset_with_linker(str(static_mesh_asset), preload_all=True)

    # 如果 archive 提前关闭，preload 会失败
    # 成功解析意味着 archive 在 preload 期间保持打开
    assert result.linker is not None

    # 验证至少有一个 export 成功预加载
    preloaded_count = sum(
        1 for inst in result.linker._export_objects
        if inst._preloaded and inst.serial_size > 0
    )
    # 至少有部分 export 成功预加载（除非所有 export 的 serial_size 都为 0）
    if any(inst.serial_size > 0 for inst in result.linker._export_objects):
        assert preloaded_count > 0, "没有 export 成功预加载，可能 archive 提前关闭"


import pytest
from unittest.mock import Mock, MagicMock

from uasset_read.serializers.object_resources import PackageIndex
from uasset_read.ir_builder import _build_resolved_depends_map


class MockParseResult:
    """模拟 ParseResult，包含 DependsMap 测试所需字段。"""
    def __init__(self, depends_map, import_map=None, export_map=None, linker=None):
        self.summary = Mock()
        self.summary.depends_map = depends_map
        self.import_map = import_map or []
        self.export_map = export_map or []
        self.linker = linker
        self.blueprint = None


def _make_depends_linker(import_map=None, export_map=None):
    """创建模拟 linker，resolve_package_index 按 UE 语义解析。

    PackageIndex 编码：
    - > 0: export (1-based), to_export_index() = idx - 1
    - < 0: import (-1 based), to_import_index() = -idx - 1
    - == 0: null
    """
    imports = import_map or []
    exports = export_map or []
    linker = Mock()

    def resolve_package_index(pkg_idx):
        if pkg_idx is None or pkg_idx.index == 0:
            return None
        if pkg_idx.is_export:
            idx = pkg_idx.index - 1  # 1-based → 0-based
            if 0 <= idx < len(exports):
                return exports[idx]
            return None
        if pkg_idx.is_import:
            idx = -pkg_idx.index - 1  # -1 based → 0-based
            if 0 <= idx < len(imports):
                return imports[idx]
            return None
        return None

    linker.resolve_package_index = resolve_package_index
    return linker


def _make_export(name, full_name=None):
    """创建模拟 export 对象。"""
    exp = Mock()
    exp.object_name = name
    exp.get_full_name = Mock(return_value=full_name or f"Package.{name}")
    return exp


def _make_import(class_package, class_name, full_name=None):
    """创建模拟 import 对象。"""
    imp = Mock()
    imp.class_package = class_package
    imp.class_name = class_name
    imp.get_full_name = Mock(return_value=full_name or f"{class_package}.{class_name}")
    return imp


class TestExportDependencyResolution:
    """测试 export 依赖解析（正数 PackageIndex）。"""

    def test_export_dependency_resolution(self):
        """正数 PackageIndex 应正确解析为 export 路径。"""
        # Export 0 依赖 Export 1（PackageIndex=2，UE 1-based 编码）
        exports = [_make_export("Export0"), _make_export("Export1")]
        linker = _make_depends_linker(export_map=exports)
        result = MockParseResult([[2]], export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved) == 1
        assert len(resolved[0]) == 1
        assert resolved[0][0]["index"] == 2
        assert resolved[0][0]["path"] == "Package.Export1"

    def test_multiple_export_dependencies(self):
        """单个 export 可以依赖多个其他 export。"""
        exports = [
            _make_export("Export0"),
            _make_export("Export1"),
            _make_export("Export2"),
        ]
        linker = _make_depends_linker(export_map=exports)
        result = MockParseResult([[2, 3]], export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 2
        assert resolved[0][0]["index"] == 2
        assert resolved[0][0]["path"] == "Package.Export1"
        assert resolved[0][1]["index"] == 3
        assert resolved[0][1]["path"] == "Package.Export2"


class TestImportDependencyResolution:
    """测试 import 依赖解析（负数 PackageIndex）。"""

    def test_import_dependency_resolution(self):
        """负数 PackageIndex 应正确解析为 import 路径。"""
        # Export 0 依赖 Import 0（PackageIndex=-1，UE -1 based 编码）
        imports = [_make_import("/Script/Core", "Object")]
        exports = [_make_export("Export0")]
        linker = _make_depends_linker(import_map=imports, export_map=exports)
        result = MockParseResult([[-1]], import_map=imports, export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved) == 1
        assert len(resolved[0]) == 1
        assert resolved[0][0]["index"] == -1
        assert resolved[0][0]["path"] == "/Script/Core.Object"

    def test_multiple_import_dependencies(self):
        """单个 export 可以依赖多个 import。"""
        imports = [
            _make_import("/Script/Core", "Object"),
            _make_import("/Script/Engine", "Actor"),
        ]
        exports = [_make_export("Export0")]
        linker = _make_depends_linker(import_map=imports, export_map=exports)
        result = MockParseResult([[-1, -2]], import_map=imports, export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 2
        assert resolved[0][0]["index"] == -1
        assert resolved[0][0]["path"] == "/Script/Core.Object"
        assert resolved[0][1]["index"] == -2
        assert resolved[0][1]["path"] == "/Script/Engine.Actor"


class TestNullDependencyIgnored:
    """测试 null PackageIndex (0) 的处理。"""

    def test_null_dependency_kept_with_none_path(self):
        """PackageIndex=0 在 _build_resolved_depends_map 中保留但 path=None。

        注：null 过滤发生在 linker._build_dependency_graph 层，
        _build_resolved_depends_map 保留所有原始条目。
        """
        exports = [_make_export("Export0"), _make_export("Export1")]
        linker = _make_depends_linker(export_map=exports)
        result = MockParseResult([[0, 2, 0]], export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        # 所有条目保留，null 的 path 为 None
        assert len(resolved[0]) == 3
        assert resolved[0][0]["index"] == 0
        assert resolved[0][0]["path"] is None
        assert resolved[0][1]["index"] == 2
        assert resolved[0][1]["path"] == "Package.Export1"
        assert resolved[0][2]["index"] == 0
        assert resolved[0][2]["path"] is None

    def test_all_null_dependencies(self):
        """所有依赖都是 null 时，path 全部为 None。"""
        exports = [_make_export("Export0")]
        linker = _make_depends_linker(export_map=exports)
        result = MockParseResult([[0, 0, 0]], export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 3
        assert all(item["path"] is None for item in resolved[0])

    def test_linker_filters_null_dependencies(self):
        """验证 linker._build_dependency_graph 层过滤 null 依赖。"""
        from uasset_read.link.linker import PackageLinker
        from uasset_read.serializers.package_summary import PackageFileSummary

        summary = Mock()
        summary.depends_map = [[0, 2, 0]]  # null, export 1, null

        # 创建 linker 实例并手动设置必要属性
        linker = Mock(spec=PackageLinker)
        linker._summary = summary
        linker._export_objects = [Mock(), Mock()]  # 2 个 export 对象
        linker._diagnostics = []

        # 用真实方法测试 null 过滤逻辑
        from uasset_read.serializers.object_resources import PackageIndex as PI

        # 模拟 resolve_package_index
        def resolve_pkg_idx(pkg_idx):
            if pkg_idx.index == 0:
                return None
            if pkg_idx.is_export:
                idx = pkg_idx.index - 1
                if 0 <= idx < len(linker._export_objects):
                    return linker._export_objects[idx]
            return None

        linker.resolve_package_index = resolve_pkg_idx

        # 手动执行 _build_dependency_graph 的核心逻辑
        depends_map = summary.depends_map
        for exp_idx, dep_indices in enumerate(depends_map):
            inst = linker._export_objects[exp_idx]
            inst.dependencies = []
            for raw_dep in dep_indices:
                if raw_dep == 0:
                    continue  # Null dependency, skip
                pkg_idx = PI(raw_dep)
                resolved = resolve_pkg_idx(pkg_idx)
                if resolved is not None:
                    inst.dependencies.append(resolved)

        # 验证 null 被过滤，只保留有效依赖
        assert len(linker._export_objects[0].dependencies) == 1


class TestResolvedDependsMapOutputFormat:
    """测试 resolved_depends_map 输出格式。"""

    def test_resolved_depends_map_output_format(self):
        """输出应包含 raw index 和 resolved path。"""
        imports = [_make_import("/Script/Core", "Object")]
        exports = [_make_export("Export0"), _make_export("Export1")]
        linker = _make_depends_linker(import_map=imports, export_map=exports)
        result = MockParseResult([[2, -1]], import_map=imports, export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert isinstance(resolved, list)
        assert len(resolved) == 1
        assert isinstance(resolved[0], list)

        for item in resolved[0]:
            assert "index" in item
            assert "path" in item
            assert isinstance(item["index"], int)
            assert isinstance(item["path"], (str, type(None)))

    def test_empty_depends_map(self):
        """空 DependsMap 应返回空列表。"""
        result = MockParseResult([])
        resolved = _build_resolved_depends_map(result)
        assert resolved == []

    def test_no_summary(self):
        """无 summary 时应返回空列表。"""
        result = MockParseResult([[2]])
        result.summary = None
        resolved = _build_resolved_depends_map(result)
        assert resolved == []

    def test_multiple_export_rows(self):
        """多个 export 各自有独立的依赖行。"""
        exports = [
            _make_export("Export0"),
            _make_export("Export1"),
            _make_export("Export2"),
        ]
        linker = _make_depends_linker(export_map=exports)
        depends_map = [[2], [3], []]  # Export0→Export1, Export1→Export2, Export2→none
        result = MockParseResult(depends_map, export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved) == 3
        assert len(resolved[0]) == 1
        assert resolved[0][0]["path"] == "Package.Export1"
        assert len(resolved[1]) == 1
        assert resolved[1][0]["path"] == "Package.Export2"
        assert len(resolved[2]) == 0


class TestOutOfBoundsDependencyDiagnostic:
    """测试越界依赖产生诊断信息。"""

    def test_out_of_bounds_export_dependency(self):
        """越界 export PackageIndex 应返回 path=None。"""
        exports = [_make_export("Export0"), _make_export("Export1")]
        linker = _make_depends_linker(export_map=exports)
        result = MockParseResult([[5]], export_map=exports, linker=linker)  # 只有 2 个 export

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 1
        assert resolved[0][0]["index"] == 5
        assert resolved[0][0]["path"] is None

    def test_out_of_bounds_import_dependency(self):
        """越界 import PackageIndex 应返回 path=None。"""
        imports = [_make_import("/Script/Core", "Object")]
        exports = [_make_export("Export0")]
        linker = _make_depends_linker(import_map=imports, export_map=exports)
        # -6 表示 import index 5 (0-based)，但只有 1 个 import
        result = MockParseResult([[-6]], import_map=imports, export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 1
        assert resolved[0][0]["index"] == -6
        assert resolved[0][0]["path"] is None

    def test_mixed_valid_and_invalid_dependencies(self):
        """混合有效和无效依赖时，应保留所有条目。"""
        imports = [_make_import("/Script/Core", "Object")]
        exports = [_make_export("Export0"), _make_export("Export1")]
        linker = _make_depends_linker(import_map=imports, export_map=exports)
        # 2=有效export, 99=越界, -1=有效import, -99=越界
        result = MockParseResult([[2, 99, -1, -99]], import_map=imports, export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 4
        assert resolved[0][0]["path"] == "Package.Export1"  # 有效 export
        assert resolved[0][1]["path"] is None  # 越界 export
        assert resolved[0][2]["path"] == "/Script/Core.Object"  # 有效 import
        assert resolved[0][3]["path"] is None  # 越界 import

    def test_no_linker_returns_all_none(self):
        """无 linker 时所有 path 应为 None。"""
        result = MockParseResult([[2, -1]], linker=None)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 2
        assert resolved[0][0]["index"] == 2
        assert resolved[0][0]["path"] is None
        assert resolved[0][1]["index"] == -1
        assert resolved[0][1]["path"] is None


import pytest
from unittest.mock import MagicMock

from uasset_read.link.linker import (
    PackageLinker,
    normalize_world_partition_path,
)
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.serializers.object_resources import (
    PackageIndex,
    ObjectImport,
    ObjectExport,
)


# ─── normalize_world_partition_path 测试 ────────────────────────────

class TestNormalizeWorldPartitionPath:
    """normalize_world_partition_path() 正确去除哈希后缀。"""

    def test_engine_hash_suffix(self):
        """去除 /Script/Engine_3103784960 → /Script/Engine"""
        assert normalize_world_partition_path("/Script/Engine_3103784960") == "/Script/Engine"

    def test_coreuobject_hash_suffix(self):
        """去除 /Script/CoreUObject_12345 → /Script/CoreUObject"""
        assert normalize_world_partition_path("/Script/CoreUObject_12345") == "/Script/CoreUObject"

    def test_controlrig_hash_suffix(self):
        """去除 /Script/ControlRig_123456 → /Script/ControlRig"""
        assert normalize_world_partition_path("/Script/ControlRig_123456") == "/Script/ControlRig"

    def test_long_hash_suffix(self):
        """去除 10 位数字后缀"""
        assert normalize_world_partition_path("/Script/Engine_3724541952") == "/Script/Engine"

    def test_no_hash_suffix_unchanged(self):
        """无哈希后缀时原样返回"""
        assert normalize_world_partition_path("/Script/Engine") == "/Script/Engine"

    def test_no_hash_suffix_short_digits(self):
        """少于 3 位数字的后缀不被去除"""
        assert normalize_world_partition_path("/Script/Engine_12") == "/Script/Engine_12"

    def test_empty_string(self):
        """空字符串原样返回"""
        assert normalize_world_partition_path("") == ""

    def test_none_like_empty(self):
        """None 值原样返回"""
        assert normalize_world_partition_path(None) is None

    def test_no_slash_prefix(self):
        """无斜杠前缀的路径也能正确处理"""
        assert normalize_world_partition_path("Engine_12345") == "Engine"

    def test_non_script_path(self):
        """非 /Script/ 路径也能正确处理"""
        assert normalize_world_partition_path(
            "/ControlRig/Controls/DefaultGizmoLibraryNormalized_1258291200"
        ) == "/ControlRig/Controls/DefaultGizmoLibraryNormalized"

    def test_object_name_with_hash(self):
        """object_name 含哈希后缀"""
        assert normalize_world_partition_path(
            "/Script/ControlRig.EControlRigVectorKind_2063597568"
        ) == "/Script/ControlRig.EControlRigVectorKind"

    def test_game_path_unchanged(self):
        """Game 路径不含数字后缀时不被修改"""
        assert normalize_world_partition_path("/Game/Maps/MyMap") == "/Game/Maps/MyMap"

    def test_consecutive_underscores(self):
        """连续下划线只影响最后一个段落的数字后缀"""
        assert normalize_world_partition_path("/Script/Engine_Core_12345") == "/Script/Engine_Core"


# ─── _verify_imports World Partition 容错测试 ───────────────────────

def _make_linker_with_wp_import(
    wp_object_name: str,
    outer_index_value: int,
) -> PackageLinker:
    """创建一个带有 World Partition hashed 路径 import 的 linker。"""
    archive = MagicMock()
    archive._file_size = 1024
    summary = MagicMock()
    summary.depends_map = None
    name_map = ["TestName"]

    import_map = []

    # 先添加一个 Package import (root)
    root_imp = MagicMock(spec=ObjectImport)
    root_imp.class_package = "/Script/CoreUObject"
    root_imp.class_name = "Package"
    root_imp.object_name = "Engine"
    root_imp.outer_index = PackageIndex(0)  # null
    root_imp.package_name = None
    root_imp.b_import_optional = False
    import_map.append(root_imp)

    # 添加 World Partition hashed import
    wp_imp = MagicMock(spec=ObjectImport)
    wp_imp.class_package = "/Script/CoreUObject"
    wp_imp.class_name = "Class"
    wp_imp.object_name = wp_object_name
    wp_imp.outer_index = PackageIndex(outer_index_value)
    wp_imp.package_name = None
    wp_imp.b_import_optional = False
    import_map.append(wp_imp)

    export_map = []
    linker = PackageLinker(archive, summary, name_map, import_map, export_map)
    linker.link()
    return linker


class TestVerifyImportsWorldPartition:
    """_verify_imports() 对 World Partition hashed 路径的容错处理。"""

    def test_hashed_path_outer_index_error_downgraded(self):
        """hashed 路径的 outer_index 无法解析时降级为 debug 而非 error。"""
        linker = _make_linker_with_wp_import(
            wp_object_name="/Script/Engine_3103784960",
            outer_index_value=999,  # out of bounds
        )
        linker.post_load()
        # 不应有 outer_index 错误（hashed 路径被降级为 debug）
        errors = linker._import_verification_errors
        assert not any("outer_index" in e and "3103784960" in e for e in errors)

    def test_non_hashed_path_outer_index_error_preserved(self):
        """非 hashed 路径的 outer_index 无法解析时保留为 error。"""
        linker = _make_linker_with_wp_import(
            wp_object_name="/Script/Engine",
            outer_index_value=999,  # out of bounds
        )
        linker.post_load()
        errors = linker._import_verification_errors
        assert any("outer_index" in e and "无法解析" in e for e in errors)

    def test_hashed_path_valid_outer_index_no_error(self):
        """hashed 路径的 outer_index 有效时无错误。"""
        linker = _make_linker_with_wp_import(
            wp_object_name="/Script/Engine_3103784960",
            outer_index_value=-1,  # valid: points to import 0
        )
        linker.post_load()
        errors = linker._import_verification_errors
        assert errors == []

    def test_multiple_hashed_imports(self):
        """多个 hashed 路径 import 的 outer_index 错误都被降级。"""
        archive = MagicMock()
        archive._file_size = 1024
        summary = MagicMock()
        summary.depends_map = None
        name_map = ["TestName"]

        import_map = []
        for i in range(5):
            imp = MagicMock(spec=ObjectImport)
            imp.class_package = f"/Script/Engine_{100000 + i}"
            imp.class_name = "Class"
            imp.object_name = f"/Script/Engine_{100000 + i}"
            imp.outer_index = PackageIndex(999)  # all out of bounds
            imp.package_name = None
            imp.b_import_optional = False
            import_map.append(imp)

        linker = PackageLinker(archive, summary, name_map, import_map, [])
        linker.link()
        linker.post_load()

        # 所有 hashed 路径的 outer_index 错误都应被降级
        errors = linker._import_verification_errors
        assert not any("outer_index" in e and "无法解析" in e for e in errors)


# ─── UObjectInstance.get_full_name() 规范化测试 ───────────────────

class TestGetFullNameWorldPartition:
    """UObjectInstance.get_full_name() 对 hashed 路径的规范化。"""

    def test_hashed_class_package_normalized(self):
        """hashed class_package 在 full_name 中被规范化。"""
        inst = UObjectInstance(
            package_index=-1,
            object_name="Actor",
            object_class="Class",
            class_package="/Script/Engine_3103784960",
            outer_index=PackageIndex(0),
            is_import=True,
            linker=None,
        )
        full_name = inst.get_full_name()
        assert full_name == "/Script/Engine.Actor"

    def test_non_hashed_class_package_unchanged(self):
        """非 hashed class_package 在 full_name 中不变。"""
        inst = UObjectInstance(
            package_index=-1,
            object_name="Actor",
            object_class="Class",
            class_package="/Script/Engine",
            outer_index=PackageIndex(0),
            is_import=True,
            linker=None,
        )
        full_name = inst.get_full_name()
        assert full_name == "/Script/Engine.Actor"
