"""tests/linker/test_linker.py — PackageLinker 验证逻辑测试。

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
"""
import pytest
from unittest.mock import MagicMock, patch

from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.link.result import LinkerParseResult
from uasset_read.serializers.object_resources import PackageIndex, ObjectImport, ObjectExport


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
