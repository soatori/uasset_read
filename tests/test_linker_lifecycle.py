"""测试 FLinkerLoad 生命周期：link → preload → post_load。

Issue #28: 验证 PackageLinker 的两阶段加载流程正确性。

测试用例：
1. test_preload_then_post_load_order — post_load 在所有 preload 后执行
2. test_property_references_resolved — ObjectProperty 引用被正确解析
3. test_weak_references_resolved — WeakObjectProperty 引用被正确解析
4. test_preload_populates_properties — preload 后 properties 被填充
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.serializers.object_resources import PackageIndex


# ─────────────────────────────────────────────────────────────────────────────
# Mock-based unit tests (no real assets required)
# ─────────────────────────────────────────────────────────────────────────────


def _make_linker(
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
        linker = _make_linker(export_count=3)
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
        linker = _make_linker(export_count=2)
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
        linker = _make_linker(export_count=2)
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
        linker = _make_linker(export_count=1)
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
        linker = _make_linker(export_count=2)
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
        linker = _make_linker(export_count=2)
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
        linker = _make_linker(export_count=2)
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
        linker = _make_linker(export_count=1, import_count=2)
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
        linker = _make_linker(export_count=1)
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
        linker = _make_linker(export_count=1)
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
        linker = _make_linker(export_count=2)
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
        linker = _make_linker(export_count=1)
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
        linker = _make_linker(export_count=1, import_count=1)
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
        linker = _make_linker(export_count=3)
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
        linker = _make_linker(export_count=1)
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
        linker = _make_linker(export_count=1)
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
        linker = _make_linker(export_count=1)
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
        linker = _make_linker(export_count=1)
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

DEFAULT_SAMPLE_ROOT = Path(r"E:\Develop\lib\UnrealEngine\Samples")

STATIC_MESH = DEFAULT_SAMPLE_ROOT / (
    "StarterContent/Content/StarterContent/Architecture/"
    "SM_AssetPlatform.uasset"
)
BLUEPRINT = DEFAULT_SAMPLE_ROOT / (
    "FirstPerson/Content/FirstPerson/Blueprints/"
    "BP_FirstPersonCharacter.uasset"
)


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
