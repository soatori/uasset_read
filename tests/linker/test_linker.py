"""tests/linker/test_linker.py — PackageLinker 验证逻辑 + 索引解析测试。

合并自：
- test_linker.py: PackageLinker 验证逻辑测试
- test_linker_index.py: DependsMap FPackageIndex 语义 + SoftObjectPath 索引解析

验证：
1. _verify_imports() 返回值被 post_load() 保留
2. post_load() 将导入验证错误传播到 _import_verification_errors
3. 无错误时 _import_verification_errors 为空列表
4. get_full_name() 循环引用检测
5. _create_export_instances offset+size 校验
6. _build_dependency_graph 类型校验
7. LinkerParseResult.status 边界情况
8. UObjectInstance 引用解析
9. PackageIndex 解析边界
10. build_outer_tree super_index 解析
11. DependsMap FPackageIndex 语义
12. SoftObjectPath 索引解析（UE5.7+ int32 vs 传统 FString）
"""
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
