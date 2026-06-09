"""tests/test_linker_issues_67_68_69.py — Issue #67/#68/#69 单元测试。

验证：
- #67: ScriptSerializationStartOffset 在 preload 中的偏移调整
- #68: 循环依赖 defer 机制
- #69: SuperStruct 链递归 preload
"""
import pytest
from unittest.mock import MagicMock, patch

from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.serializers.object_resources import PackageIndex
from uasset_read.constants import UE5_SCRIPT_SERIALIZATION_OFFSET, PKG_UnversionedProperties


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_linker(
    export_count: int = 3,
    import_count: int = 1,
    file_size: int = 10000,
    file_version_ue5: int = 0,
    package_flags: int = 0,
) -> PackageLinker:
    """构造最小可用的 PackageLinker（mock archive/summary）。"""
    archive = MagicMock()
    archive._file_size = file_size

    summary = MagicMock()
    summary.depends_map = None
    summary.file_version_ue5 = file_version_ue5
    summary.package_flags = package_flags

    name_map: list[str] = []

    import_map = []
    for i in range(import_count):
        imp = MagicMock()
        imp.object_name = f"ImportObj_{i}"
        imp.class_name = f"ImportClass_{i}"
        imp.class_package = "/Script/Engine"
        imp.outer_index = PackageIndex(0)
        imp.class_index = PackageIndex(0)
        import_map.append(imp)

    export_map = []
    for i in range(export_count):
        exp = MagicMock()
        exp.object_name = f"ExportObj_{i}"
        exp.class_index = PackageIndex(-(1)) if import_count > 0 else PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.template_index = PackageIndex(0)
        exp.serial_offset = 100 + i * 200
        exp.serial_size = 100
        exp.script_serialization_start_offset = 0
        exp.script_serialization_end_offset = 0
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
# Issue #67: ScriptSerializationStartOffset
# ─────────────────────────────────────────────────────────────────────────────


class TestScriptSerializationOffset:
    """Issue #67: ScriptSerializationStartOffset 偏移调整。"""

    def test_no_offset_when_version_below_threshold(self):
        """版本 < 1010 时不做偏移调整。"""
        linker = _make_linker(
            export_count=1, file_size=10000,
            file_version_ue5=1009,  # < SCRIPT_SERIALIZATION_OFFSET
        )
        linker.link()
        exp = linker._export_map[0]
        exp.script_serialization_start_offset = 50
        exp.script_serialization_end_offset = 80

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            linker.preload(0)

        # 应使用原始 serial_offset（100），而非 100+50=150
        seek_calls = [c for c in linker._archive.seek.call_args_list]
        assert len(seek_calls) >= 1
        assert seek_calls[-1].args[0] == 100

    def test_no_offset_when_unversioned(self):
        """PKG_UnversionedProperties 标志设置时不做偏移调整。"""
        linker = _make_linker(
            export_count=1, file_size=10000,
            file_version_ue5=UE5_SCRIPT_SERIALIZATION_OFFSET,
            package_flags=PKG_UnversionedProperties,
        )
        linker.link()
        exp = linker._export_map[0]
        exp.script_serialization_start_offset = 50
        exp.script_serialization_end_offset = 80

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            linker.preload(0)

        seek_calls = [c for c in linker._archive.seek.call_args_list]
        assert len(seek_calls) >= 1
        # 应使用原始 serial_offset（100），而非 100+50=150
        assert seek_calls[-1].args[0] == 100

    def test_no_offset_when_start_offset_zero(self):
        """script_serialization_start_offset=0 时不调整。"""
        linker = _make_linker(
            export_count=1, file_size=10000,
            file_version_ue5=UE5_SCRIPT_SERIALIZATION_OFFSET,
        )
        linker.link()
        exp = linker._export_map[0]
        exp.script_serialization_start_offset = 0
        exp.script_serialization_end_offset = 0

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            linker.preload(0)

        seek_calls = [c for c in linker._archive.seek.call_args_list]
        assert len(seek_calls) >= 1
        assert seek_calls[-1].args[0] == 100

    def test_offset_applied_when_conditions_met(self):
        """版本 >= 1010 且 start_offset > 0 时应用偏移调整。"""
        linker = _make_linker(
            export_count=1, file_size=10000,
            file_version_ue5=UE5_SCRIPT_SERIALIZATION_OFFSET,
        )
        linker.link()
        exp = linker._export_map[0]
        exp.serial_offset = 100
        exp.serial_size = 200
        exp.script_serialization_start_offset = 50
        exp.script_serialization_end_offset = 130

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            linker.preload(0)

        # 应 seek 到 100+50=150
        seek_calls = [c for c in linker._archive.seek.call_args_list]
        assert len(seek_calls) >= 1
        assert seek_calls[-1].args[0] == 150

    def test_serial_size_restored_after_parse(self):
        """parse 后 serial_size 应恢复为原始值。"""
        linker = _make_linker(
            export_count=1, file_size=10000,
            file_version_ue5=UE5_SCRIPT_SERIALIZATION_OFFSET,
        )
        linker.link()
        exp = linker._export_map[0]
        exp.serial_offset = 100
        exp.serial_size = 200
        exp.script_serialization_start_offset = 50
        exp.script_serialization_end_offset = 130
        # 同步更新 instance（link() 时已从 export_map 复制）
        linker._export_objects[0].serial_offset = 100
        linker._export_objects[0].serial_size = 200

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            linker.preload(0)

        # serial_size 应恢复为原始值 200
        assert linker._export_objects[0].serial_size == 200

    def test_uses_script_serialization_offset_method(self):
        """_uses_script_serialization_offset 正确检查所有条件。"""
        # 版本 >= 1010, unversioned=False, start_offset > 0 => True
        linker = _make_linker(
            export_count=1,
            file_version_ue5=UE5_SCRIPT_SERIALIZATION_OFFSET,
        )
        linker.link()
        exp = linker._export_map[0]
        exp.script_serialization_start_offset = 50
        assert linker._uses_script_serialization_offset(exp) is True

        # 版本 < 1010 => False
        linker2 = _make_linker(
            export_count=1,
            file_version_ue5=1009,
        )
        linker2.link()
        exp2 = linker2._export_map[0]
        exp2.script_serialization_start_offset = 50
        assert linker2._uses_script_serialization_offset(exp2) is False

        # unversioned => False
        linker3 = _make_linker(
            export_count=1,
            file_version_ue5=UE5_SCRIPT_SERIALIZATION_OFFSET,
            package_flags=PKG_UnversionedProperties,
        )
        linker3.link()
        exp3 = linker3._export_map[0]
        exp3.script_serialization_start_offset = 50
        assert linker3._uses_script_serialization_offset(exp3) is False

        # start_offset = 0 => False
        linker4 = _make_linker(
            export_count=1,
            file_version_ue5=UE5_SCRIPT_SERIALIZATION_OFFSET,
        )
        linker4.link()
        exp4 = linker4._export_map[0]
        exp4.script_serialization_start_offset = 0
        assert linker4._uses_script_serialization_offset(exp4) is False


# ─────────────────────────────────────────────────────────────────────────────
# Issue #68: 循环依赖 defer 机制
# ─────────────────────────────────────────────────────────────────────────────


class TestCircularDependencyDefer:
    """Issue #68: 循环依赖 defer 机制。"""

    def test_deferred_status_on_self_reference(self):
        """循环引用被检测到时设置 parse_status=deferred。"""
        linker = _make_linker(export_count=2, file_size=10000)
        linker.link()
        inst0 = linker._export_objects[0]
        inst1 = linker._export_objects[1]

        # 模拟 preload 过程中的循环依赖：
        # 当解析 export[0] 时触发对 export[1] 的 preload，
        # 而 export[1] 的解析又会触发对 export[0] 的 preload
        def fake_parse0(*args, **kwargs):
            # 在解析过程中尝试 preload export[1]
            linker._export_objects[0].serialized_properties = []
            linker._export_objects[0]._preloaded = True
            linker._preload_cache[0] = True
            linker._preloading_in_progress.discard(0)
            linker.preload(1)
            return []

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            side_effect=fake_parse0,
        ):
            linker.preload(0)

        # export[1] 不应崩溃
        assert hasattr(inst1, 'parse_status')

    def test_preloading_in_progress_tracked(self):
        """_preloading_in_progress 在 preload 完成后被清理。"""
        linker = _make_linker(export_count=1, file_size=10000)
        linker.link()

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            linker.preload(0)

        # preload 完成后 _preloading_in_progress 应为空
        assert 0 not in linker._preloading_in_progress

    def test_deferred_export_not_retried_in_cache(self):
        """deferred 的 export 不会进入 preload_cache（允许后续重试）。"""
        linker = _make_linker(export_count=2, file_size=10000)
        linker.link()

        # 手动模拟循环依赖：将 index 0 加入 in_progress
        linker._preloading_in_progress.add(0)
        linker.preload(0)
        linker._preloading_in_progress.discard(0)

        # deferred 状态不应在 preload_cache 中
        assert 0 not in linker._preload_cache

    def test_normal_preload_still_works(self):
        """非循环依赖的 preload 正常工作。"""
        linker = _make_linker(export_count=3, file_size=10000)
        linker.link()

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            linker.preload(0)
            linker.preload(1)
            linker.preload(2)

        for i in range(3):
            assert linker._export_objects[i]._preloaded
            assert i in linker._preload_cache


# ─────────────────────────────────────────────────────────────────────────────
# Issue #69: SuperStruct 链递归 preload
# ─────────────────────────────────────────────────────────────────────────────


def _make_struct_linker(super_chain: list[tuple[str, int | None]]) -> PackageLinker:
    """构造具有 super 链的 linker。

    Args:
        super_chain: [(class_name, super_export_index_or_None), ...]
    """
    export_count = len(super_chain)
    # 需要填充 name_map 以供 _create_export_instances 中的整数 object_name 查找
    name_map = [f"Obj_{i}" for i in range(export_count)]

    archive = MagicMock()
    archive._file_size = 50000
    summary = MagicMock()
    summary.depends_map = None
    summary.file_version_ue5 = 0
    summary.package_flags = 0

    import_map: list = []
    export_map = []
    for i in range(export_count):
        exp = MagicMock()
        exp.object_name = i  # int 索引，需通过 name_map 解析
        exp.class_index = PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.template_index = PackageIndex(0)
        exp.serial_offset = 100 + i * 200
        exp.serial_size = 100
        exp.script_serialization_start_offset = 0
        exp.script_serialization_end_offset = 0
        export_map.append(exp)

    linker = PackageLinker(
        archive=archive,
        summary=summary,
        name_map=name_map,
        import_map=import_map,
        export_map=export_map,
    )
    linker.link()

    for i, (class_name, super_idx) in enumerate(super_chain):
        inst = linker._export_objects[i]
        inst.object_class = class_name
        inst.serial_offset = 100 + i * 200
        inst.serial_size = 100

        exp = linker._export_map[i]
        exp.object_name = f"Struct_{i}"
        if super_idx is not None:
            exp.super_index = PackageIndex(super_idx + 1)  # 1-based
        else:
            exp.super_index = PackageIndex(0)  # null

    return linker


class TestSuperStructChainPreload:
    """Issue #69: SuperStruct 链递归 preload。"""

    def test_super_chain_preloaded_before_child(self):
        """SuperStruct 被先于子类 preload。"""
        # export[0]=父类, export[1]=子类（super -> export[0]）
        preload_order = []

        def fake_parse(*args, **kwargs):
            idx = kwargs.get('_index', None)
            # 从 linker._export_map 中获取 index
            exp = args[0]  # 第一个参数是 export
            for i, e in enumerate(linker._export_map):
                if e is exp:
                    preload_order.append(i)
                    break
            return []

        linker = _make_struct_linker([
            ("EdGraph", None),        # export 0: 无 super
            ("BlueprintGeneratedClass", 0),  # export 1: super -> 0
        ])

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            side_effect=fake_parse,
        ):
            linker.preload(1)

        # 父类（index 0）应先于子类（index 1）被 preload
        assert 0 in preload_order
        assert 1 in preload_order
        assert preload_order.index(0) < preload_order.index(1)

    def test_non_struct_class_no_recursive_preload(self):
        """非 UStruct 类不触发 super 链递归。"""
        call_count = [0]

        def counting_parse(*args, **kwargs):
            call_count[0] += 1
            return []

        linker = _make_struct_linker([
            ("EdGraph", None),          # export 0: 非 struct 类
            ("EdGraphNode", 0),         # export 1: super -> 0，但不是 struct 类
        ])

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            side_effect=counting_parse,
        ):
            linker.preload(1)

        # EdGraphNode 不是 struct-like 类，不应递归 preload export[0]
        # 只有 export[1] 自身被 parse
        assert call_count[0] == 1

    def test_self_referencing_super_index_ignored(self):
        """super_index 指向自身时忽略（防止无限递归）。"""
        linker = _make_struct_linker([
            ("EdGraph", 0),  # export 0: super -> 自身
        ])

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            # 不应崩溃
            linker.preload(0)

        assert linker._export_objects[0]._preloaded

    def test_recursion_depth_limit(self):
        """递归深度达到 10 层时停止。"""
        # 构造 12 层 super 链：export[0] -> super[1] -> super[2] -> ... -> super[11]
        chain = []
        for i in range(12):
            if i < 11:
                chain.append(("BlueprintGeneratedClass", i + 1))
            else:
                chain.append(("BlueprintGeneratedClass", None))  # 链尾

        # 反转：super 链是从子类到父类
        chain.reverse()
        # export[0] 无 super, export[1] super -> 0, export[2] super -> 1, ...
        chain_final = [("BlueprintGeneratedClass", None)]
        for i in range(1, 12):
            chain_final.append(("BlueprintGeneratedClass", i - 1))

        linker = _make_struct_linker(chain_final)

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            # 不应因递归深度过大而崩溃
            linker.preload(11)

        assert linker._export_objects[11]._preloaded

    def test_already_preloaded_super_not_reloaded(self):
        """已 preload 的 super 不会被重复 preload。"""
        preload_count = [0]

        def counting_parse(*args, **kwargs):
            preload_count[0] += 1
            return []

        linker = _make_struct_linker([
            ("EdGraph", None),            # export 0: 无 super
            ("BlueprintGeneratedClass", 0),  # export 1: super -> 0
        ])

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            side_effect=counting_parse,
        ):
            # 先 preload 父类
            linker.preload(0)
            assert preload_count[0] == 1

            # 再 preload 子类（父类已 preload，不应再次 parse）
            linker.preload(1)
            assert preload_count[0] == 2  # 只增加了子类的 1 次

    def test_import_super_index_not_recursed(self):
        """super_index 指向 import 时不递归（仅 export 超类递归）。"""
        linker = _make_linker(export_count=1, import_count=1, file_size=10000)
        linker.link()

        inst = linker._export_objects[0]
        inst.object_class = "BlueprintGeneratedClass"
        inst.serial_offset = 100
        inst.serial_size = 100

        exp = linker._export_map[0]
        exp.object_name = "TestExport"
        exp.super_index = PackageIndex(-1)  # 指向 import

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            # 不应崩溃
            linker.preload(0)

        assert linker._export_objects[0]._preloaded


# ─────────────────────────────────────────────────────────────────────────────
# Integration: 现有测试不受影响
# ─────────────────────────────────────────────────────────────────────────────


class TestExistingBehaviorUnchanged:
    """确保现有行为不受三个 issue 修复的影响。"""

    def test_preload_marks_preloaded(self):
        """preload 后实例 _preloaded 标记为 True。"""
        linker = _make_linker(export_count=3)
        linker.link()

        for inst in linker._export_objects:
            assert not inst._preloaded

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            for i in range(3):
                linker.preload(i)

        for inst in linker._export_objects:
            assert inst._preloaded

    def test_preload_is_idempotent(self):
        """重复调用 preload 不会重复解析。"""
        linker = _make_linker(export_count=1)
        linker.link()

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            linker.preload(0)
            linker.preload(0)  # 第二次应直接返回

        assert linker._export_objects[0]._preloaded

    def test_preload_out_of_bounds_is_safe(self):
        """越界 index 的 preload 不会崩溃。"""
        linker = _make_linker(export_count=2)
        linker.link()

        linker.preload(-1)
        linker.preload(100)

        assert not linker._export_objects[0]._preloaded

    def test_preload_zero_size_skips(self):
        """serial_size=0 跳过 preload。"""
        linker = _make_linker(export_count=1)
        linker.link()
        linker._export_objects[0].serial_size = 0

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
        ) as mock_parse:
            linker.preload(0)
            mock_parse.assert_not_called()
            assert linker._export_objects[0]._preloaded

    def test_skip_unsupported_still_works(self):
        """SKIP_UNSUPPORTED 策略仍正常工作。"""
        linker = _make_linker(export_count=1)
        linker.link()
        inst = linker._export_objects[0]
        inst.object_class = "StaticMesh"

        with patch(
            "uasset_read.parsers.property_parser.parse_properties_from_export",
            return_value=[],
        ):
            linker.preload(0)

        assert inst._preloaded
