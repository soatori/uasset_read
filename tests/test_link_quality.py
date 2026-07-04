"""link 模块缺陷测试 — 对应 Task #252。

验证以下缺陷场景：
1. _verify_imports 返回值被丢弃 — import 验证错误丢失
2. get_full_name() 循环引用导致 RecursionError
3. _create_export_instances 缺少 serial_offset+serial_size 越界检查
4. _build_dependency_graph 缺少类型校验
5. LinkerParseResult.status 边界情况
"""
import pytest
from unittest.mock import MagicMock, patch

from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.link.result import LinkerParseResult
from uasset_read.serializers.object_resources import PackageIndex, ObjectImport, ObjectExport


# ─────────────────────────────────────────────────────────────────────────────
# Mock helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_linker(
    export_count: int = 2,
    import_count: int = 1,
    file_size: int = 10000,
) -> PackageLinker:
    """构造最小可用的 PackageLinker。"""
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


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: _verify_imports 返回值被丢弃
# ─────────────────────────────────────────────────────────────────────────────

class TestVerifyImportsReturnDiscarded:
    """缺陷: post_load() 调用 _verify_imports() 但丢弃返回值。

    _verify_imports() 返回 List[str] 错误列表，
    但 post_load() 不捕获返回值，导致 import 验证错误丢失。
    """

    def test_verify_imports_returns_errors(self):
        """_verify_imports 本身可以正确检测错误。"""
        linker = _make_linker(export_count=1, import_count=2)
        linker.link()

        # 构造一个 class_index 越界的 import
        imp = linker._import_map[1]
        imp.class_index = PackageIndex(999)  # 不存在的 export

        errors = linker._verify_imports()
        assert isinstance(errors, list)
        assert len(errors) > 0
        assert "class_index 无法解析" in errors[0]

    def test_post_load_preserves_verify_imports_result(self):
        """post_load 保留 _verify_imports 的返回值 — 修复 #250 (M-21)。

        _verify_imports() 的错误列表现在存储在 linker._import_verification_errors 中。
        """
        linker = _make_linker(export_count=1, import_count=2)
        linker.link()

        # 构造一个 class_index 越界的 import
        imp = linker._import_map[1]
        imp.class_index = PackageIndex(999)  # 不存在的 export

        # 手动 preload（mock parser）
        linker._export_objects[0]._preloaded = True

        # 调用 post_load
        linker.post_load()

        # 验证：post_load 后 _verify_imports 的错误被保存
        assert hasattr(linker, '_import_verification_errors')
        assert len(linker._import_verification_errors) > 0, (
            "post_load 应保留 _verify_imports 的错误"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: get_full_name() 循环引用
# ─────────────────────────────────────────────────────────────────────────────

class TestGetFullNameCircularReference:
    """修复 #250 (M-20): get_full_name() 现在检测循环 outer 引用。

    循环引用时返回 '<circular:N>' 而非触发 RecursionError。
    """

    def test_normal_outer_chain(self):
        """正常 outer 链不崩溃。"""
        root = UObjectInstance(
            package_index=1,
            object_name="Root",
            object_class="Package",
            class_package=None,
            outer_index=PackageIndex(0),
            is_import=False,
        )
        child = UObjectInstance(
            package_index=2,
            object_name="Child",
            object_class="Class",
            class_package=None,
            outer_index=PackageIndex(1),
            is_import=False,
            outer=root,
        )
        assert child.get_full_name() == "Root.Child"

    def test_circular_outer_returns_circular_marker(self):
        """循环 outer 引用返回 <circular:N> 而非 RecursionError（修复 #250）。"""
        obj_a = UObjectInstance(
            package_index=1,
            object_name="ObjectA",
            object_class="Class",
            class_package=None,
            outer_index=PackageIndex(2),
            is_import=False,
        )
        obj_b = UObjectInstance(
            package_index=2,
            object_name="ObjectB",
            object_class="Class",
            class_package=None,
            outer_index=PackageIndex(1),
            is_import=False,
        )
        # 构造循环引用
        obj_a.outer = obj_b
        obj_b.outer = obj_a

        # 不再触发 RecursionError，而是返回 <circular:N>
        result = obj_a.get_full_name()
        assert "<circular:" in result

    def test_self_referencing_outer_returns_circular_marker(self):
        """对象的 outer 指向自身时返回 <circular:N>（修复 #250）。"""
        obj = UObjectInstance(
            package_index=1,
            object_name="SelfRef",
            object_class="Class",
            class_package=None,
            outer_index=PackageIndex(1),
            is_import=False,
        )
        obj.outer = obj

        result = obj.get_full_name()
        assert result == "<circular:1>.SelfRef"


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: _create_export_instances 缺少 serial_offset+serial_size 校验
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateExportInstancesOffsetSizeValidation:
    """缺陷: _create_export_instances 只验证 serial_offset 不越界，
    但不验证 serial_offset + serial_size > file_size。

    preload() 有此校验，但早期校验不完整。
    """

    def test_offset_plus_size_exceeds_file_size_not_caught_early(self):
        """serial_offset + serial_size > file_size 在 link 阶段不被拦截。

        只有 serial_offset 单独被验证。
        """
        linker = _make_linker(export_count=0, file_size=1000)

        # 构造一个 offset+size 超出文件的 export
        exp = MagicMock(spec=ObjectExport)
        exp.class_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.object_name = "OverflowExport"
        exp.serial_offset = 800  # 合法
        exp.serial_size = 300  # 800+300=1100 > 1000，超出文件
        linker._export_map = [exp]
        linker._create_export_instances()

        # 实例被创建了（serial_offset=800 在范围内，所以没有被归零）
        assert len(linker._export_objects) == 1
        inst = linker._export_objects[0]
        assert inst.serial_offset == 800
        assert inst.serial_size == 300

        # 缺陷：没有诊断记录（因为只检查了 offset，没检查 offset+size）
        overflow_diag = [
            d for d in linker.diagnostics
            if "serial_size" in d.field or "offset+size" in d.error
        ]
        # 修复后此断言应改为 assert len(overflow_diag) > 0
        assert len(overflow_diag) == 0, (
            "缺陷确认: offset+size 越界在 _create_export_instances 未被检测"
        )

    def test_offset_valid_size_overflow_preload_catches(self):
        """preload() 确实有 offset+size 校验 — 验证 preload 阶段可以拦截。"""
        linker = _make_linker(export_count=1, file_size=1000)
        linker.link()

        # 设置 offset 合法但 offset+size 超出
        linker._export_objects[0].serial_offset = 800
        linker._export_objects[0].serial_size = 300

        linker.preload(0)

        # preload 应记录诊断
        diags = [d for d in linker.diagnostics if d.field == "serial_size"]
        assert len(diags) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: _build_dependency_graph 缺少类型校验
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildDependencyGraphTypeValidation:
    """缺陷: _build_dependency_graph 对 depends_map 元素不做类型校验。

    如果 contains_map 包含非整数元素，PackageIndex(raw_dep) 可能崩溃。
    """

    def test_normal_depends_map(self):
        """正常 depends_map 正确构建依赖图。"""
        linker = _make_linker(export_count=3, import_count=1)
        linker.link()

        # 设置 summary.depends_map
        # depends_map[export_idx] = [FPackageIndex 值列表]
        linker._summary.depends_map = [
            [2, -1],   # export 0 依赖 export 1 和 import 0
            [0],       # export 1 无有效依赖
            [],        # export 2 无依赖
        ]
        # 所有 export 标记为 preloaded
        for inst in linker._export_objects:
            inst._preloaded = True

        linker._build_dependency_graph()

        # export 0 应有 2 个依赖
        assert len(linker._export_objects[0].dependencies) == 2
        # export 1 应无依赖（0 是 null）
        assert len(linker._export_objects[1].dependencies) == 0
        # export 2 应无依赖
        assert len(linker._export_objects[2].dependencies) == 0

    def test_depends_map_with_non_int_element(self):
        """depends_map 包含非整数元素时不应崩溃。"""
        linker = _make_linker(export_count=2, import_count=0)
        linker.link()

        # 构造包含非整数元素的 depends_map
        linker._summary.depends_map = [
            [1, "invalid_string"],  # 非整数元素
            [None],                  # None 元素
        ]
        for inst in linker._export_objects:
            inst._preloaded = True

        # 不应崩溃（容错处理）
        try:
            linker._build_dependency_graph()
        except (TypeError, ValueError):
            pytest.fail(
                "_build_dependency_graph 应容错处理非整数元素，"
                "而非抛出异常"
            )

    def test_depends_map_out_of_bounds_export_index(self):
        """depends_map 包含越界 export index 时应记录诊断。"""
        linker = _make_linker(export_count=2, import_count=0)
        linker.link()

        # depends_map 引用不存在的 export
        linker._summary.depends_map = [
            [100],  # export index 100 不存在
            [],
        ]
        for inst in linker._export_objects:
            inst._preloaded = True

        linker._build_dependency_graph()

        # 应记录诊断
        dep_diag = [d for d in linker.diagnostics if d.field == "DependsMap"]
        assert len(dep_diag) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: LinkerParseResult.status 边界情况
# ─────────────────────────────────────────────────────────────────────────────

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
            summary=MagicMock(),
            name_map=["Test"],
            export_map=[mock_export],
        )
        assert result.status == "success"

    def test_status_partial_with_errors(self):
        """有错误时 status 为 partial。"""
        result = LinkerParseResult(
            summary=MagicMock(),
            name_map=["Test"],
            export_map=[],
            errors=["Some error"],
        )
        assert result.status == "partial"

    def test_status_partial_skipped_export(self):
        """有 skipped export 时 status 为 partial。"""
        mock_export = MagicMock()
        mock_export.parse_status = "skipped"
        result = LinkerParseResult(
            summary=MagicMock(),
            name_map=["Test"],
            export_map=[mock_export],
        )
        assert result.status == "partial"

    def test_status_partial_opaque_export(self):
        """有 opaque export 时 status 为 partial。"""
        mock_export = MagicMock()
        mock_export.parse_status = "opaque"
        result = LinkerParseResult(
            summary=MagicMock(),
            name_map=["Test"],
            export_map=[mock_export],
        )
        assert result.status == "partial"

    def test_status_partial_lightweight_metadata(self):
        """lightweight_tolerant_parse 元数据使 status 为 partial。"""
        result = LinkerParseResult(
            summary=MagicMock(),
            name_map=["Test"],
            export_map=[],
            metadata={"lightweight_tolerant_parse": True},
        )
        assert result.status == "partial"

    def test_status_success_only_summary(self):
        """仅 summary 有数据时，若 export_map 为空则 status 为 success。"""
        result = LinkerParseResult(
            summary=MagicMock(),
            name_map=["Test"],
            export_map=[],
        )
        assert result.status == "success"


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: get_full_name 异常场景
# ─────────────────────────────────────────────────────────────────────────────

class TestGetFullNameEdgeCases:
    """get_full_name() 边界情况。"""

    def test_import_with_class_package(self):
        """import 对象使用 class_package 作为前缀。"""
        obj = UObjectInstance(
            package_index=-1,
            object_name="MyObject",
            object_class="Actor",
            class_package="/Script/Engine",
            outer_index=PackageIndex(0),
            is_import=True,
        )
        assert obj.get_full_name() == "/Script/Engine.MyObject"

    def test_export_with_linker_summary(self):
        """export 对象使用 linker.summary.package_name 作为前缀。"""
        linker = _make_linker(export_count=1, import_count=0)
        linker.link()

        obj = linker._export_objects[0]
        full_name = obj.get_full_name()
        # 应该包含 TestPackage（summary.package_name）作为前缀
        assert full_name.startswith("TestPackage.")

    def test_no_outer_no_linker_returns_name(self):
        """无 outer 无 linker 时返回 object_name。"""
        obj = UObjectInstance(
            package_index=1,
            object_name="BareName",
            object_class="Class",
            class_package=None,
            outer_index=PackageIndex(0),
            is_import=False,
        )
        assert obj.get_full_name() == "BareName"

    def test_integer_package_name_lookup(self):
        """package_name 为 int 时从 name_map 查找。"""
        linker = _make_linker(export_count=1, import_count=0)
        linker.link()
        linker.summary.package_name = 0
        linker.name_map = ["ResolvedPackageName"]

        obj = linker._export_objects[0]
        full_name = obj.get_full_name()
        assert full_name.startswith("ResolvedPackageName.")

    def test_integer_package_name_out_of_bounds(self):
        """package_name 为越界 int 时使用 'Unknown'。"""
        linker = _make_linker(export_count=1, import_count=0)
        linker.link()
        linker.summary.package_name = 999
        linker.name_map = ["ValidName"]

        obj = linker._export_objects[0]
        full_name = obj.get_full_name()
        assert full_name.startswith("Unknown.")


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: UObjectInstance.get_class_object / get_template_object
# ─────────────────────────────────────────────────────────────────────────────

class TestUObjectInstanceResolution:
    """UObjectInstance 引用解析方法。"""

    def test_get_class_object_returns_none_for_import(self):
        """import 对象的 get_class_object 返回 None。"""
        obj = UObjectInstance(
            package_index=-1,
            object_name="TestImport",
            object_class="Actor",
            class_package="/Script/Engine",
            outer_index=PackageIndex(0),
            is_import=True,
        )
        assert obj.get_class_object() is None

    def test_get_class_object_resolves_via_linker(self):
        """export 对象的 get_class_object 通过 linker 解析。"""
        linker = _make_linker(export_count=2, import_count=1)
        linker.link()

        # export 0 的 class_index 指向 import 0
        inst = linker._export_objects[0]
        result = inst.get_class_object()
        # 应解析为 import 0 对应的 UObjectInstance
        if result is not None:
            assert result is linker._import_objects[0]

    def test_get_template_object_returns_none_for_import(self):
        """import 对象的 get_template_object 返回 None。"""
        obj = UObjectInstance(
            package_index=-1,
            object_name="TestImport",
            object_class="Actor",
            class_package="/Script/Engine",
            outer_index=PackageIndex(0),
            is_import=True,
        )
        assert obj.get_template_object() is None

    def test_get_template_object_resolves_via_linker(self):
        """export 对象的 get_template_object 通过 linker 解析。"""
        linker = _make_linker(export_count=2, import_count=0)
        linker.link()

        # export 1 的 template_index 指向 export 0
        linker._export_map[1].template_index = PackageIndex(1)
        inst = linker._export_objects[1]
        result = inst.get_template_object()
        assert result is linker._export_objects[0]

    def test_get_children_delegates_to_linker(self):
        """get_children 委托给 linker.get_children。"""
        linker = _make_linker(export_count=3, import_count=0)
        linker.link()

        # export 0 是 root（outer_index=null），export 1 和 2 的 outer 指向 export 0
        linker._export_objects[1].outer = linker._export_objects[0]
        linker._export_objects[2].outer = linker._export_objects[0]

        children = linker._export_objects[0].get_children()
        assert len(children) == 2
        assert linker._export_objects[1] in children
        assert linker._export_objects[2] in children

    def test_ensure_preloaded_triggers_preload(self):
        """ensure_preloaded 触发 linker.preload。"""
        linker = _make_linker(export_count=1, import_count=0)
        linker.link()

        inst = linker._export_objects[0]
        assert not inst._preloaded

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            inst.ensure_preloaded()
            assert inst._preloaded


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: get_children / export_objects / _collect_root_objects
# ─────────────────────────────────────────────────────────────────────────────

class TestLinkerObjectCollection:
    """linker 对象集合方法。"""

    def test_export_objects_returns_copy(self):
        """export_objects 返回列表副本，修改不影响内部状态。"""
        linker = _make_linker(export_count=2)
        linker.link()

        objs = linker.export_objects()
        objs.clear()

        assert len(linker.export_objects()) == 2

    def test_get_children_returns_empty_for_leaf(self):
        """无子对象时 get_children 返回空列表。"""
        linker = _make_linker(export_count=1)
        linker.link()

        children = linker.get_children(linker._export_objects[0])
        assert children == []

    def test_collect_root_objects(self):
        """_collect_root_objects 收集 outer_index 为 null 的对象。"""
        linker = _make_linker(export_count=3, import_count=1)
        linker.link()

        # 所有对象 outer_index 都是 null（默认值）
        roots = linker._root_objects
        assert len(roots) > 0

    def test_no_outer_returns_empty_list(self):
        """get_children 在无 linker 的实例上返回空列表。"""
        obj = UObjectInstance(
            package_index=1,
            object_name="NoLinker",
            object_class="Class",
            class_package=None,
            outer_index=PackageIndex(0),
            is_import=False,
        )
        assert obj.get_children() == []


# ─────────────────────────────────────────────────────────────────────────────
# Test 9: package index import 边界
# ─────────────────────────────────────────────────────────────────────────────

class TestPackageIndexEdgeCases:
    """PackageIndex 解析边界。"""

    def test_import_index_resolution(self):
        """-1 => import index 0, -2 => import index 1。"""
        linker = _make_linker(export_count=1, import_count=3)
        linker.link()

        # -1 应解析为 import_objects[0]
        result = linker.resolve_package_index(PackageIndex(-1))
        assert result is linker._import_objects[0]

        # -3 应解析为 import_objects[2]
        result = linker.resolve_package_index(PackageIndex(-3))
        assert result is linker._import_objects[2]

    def test_export_index_resolution(self):
        """1 => export index 0, 2 => export index 1。"""
        linker = _make_linker(export_count=3)
        linker.link()

        result = linker.resolve_package_index(PackageIndex(1))
        assert result is linker._export_objects[0]

        result = linker.resolve_package_index(PackageIndex(3))
        assert result is linker._export_objects[2]

    def test_zero_index_returns_none(self):
        """PackageIndex(0) 返回 None。"""
        linker = _make_linker(export_count=1)
        result = linker.resolve_package_index(PackageIndex(0))
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Test 10: build_outer_tree super_index
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildOuterTreeSuperIndex:
    """验证 build_outer_tree 解析 super_index（父类引用）。"""

    def test_super_index_resolved(self):
        """super_index 指向的对象被设置为 export 的 super_object。"""
        linker = _make_linker(export_count=3, import_count=1)
        linker.link()

        # export 2 的 super_index 指向 export 0
        linker._export_map[2].super_index = PackageIndex(1)

        linker.build_outer_tree()

        inst = linker._export_objects[2]
        assert inst.super_object is linker._export_objects[0]

    def test_super_index_null_not_resolved(self):
        """super_index 为 null 时不设置 super_object。"""
        linker = _make_linker(export_count=2)
        linker.link()

        linker.build_outer_tree()

        for inst in linker._export_objects:
            assert inst.super_object is None
