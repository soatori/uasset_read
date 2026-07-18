"""linker.py 安全修复测试 — Sub 1/4/5，以及 UObjectInstance 测试。

验证：
1. ObjectProperty/WeakObjectProperty 的 int 和 PackageIndex 值都能被正确解析
2. serial_size 负值被检测并标记失败
3. serial_size == 0 检查在偏移校验之后执行
4. UObjectInstance get_full_name() 正常路径、循环引用检测、边界情况
"""
from unittest.mock import MagicMock
import pytest

from uasset_read.serializers.object_resources import PackageIndex, ObjectImport, ObjectExport
from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance


# ---- helpers ----

def _make_linker(
    export_count: int = 0,
    file_size: int = 1024,
) -> PackageLinker:
    archive = MagicMock()
    archive._file_size = file_size
    summary = MagicMock()
    name_map = ["TestName"]
    import_map: list = []
    export_map: list = []
    for i in range(export_count):
        exp = MagicMock(spec=ObjectExport)
        exp.class_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.object_name = 0
        exp.serial_offset = 0
        exp.serial_size = 0
        export_map.append(exp)
    linker = PackageLinker(archive, summary, name_map, import_map, export_map)
    linker.link()
    return linker


# ======================================================================
# Sub 1: _resolve_property_references / _resolve_weak_references
# ======================================================================

class TestResolvePropertyReferences:
    """ObjectProperty 值可以是 int 或 PackageIndex。"""

    def test_int_value_resolved(self):
        """int 值的 ObjectProperty 被正确解析。"""
        linker = _make_linker(export_count=2, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        # export index 2 → PackageIndex(2)
        inst.serialized_properties = [
            {"type": "ObjectProperty", "name": "TestProp", "value": 2}
        ]
        linker._resolve_property_references()
        assert "TestProp" in inst.property_references
        assert inst.property_references["TestProp"] is linker._export_objects[1]

    def test_package_index_value_resolved(self):
        """PackageIndex 值的 ObjectProperty 被正确解析。"""
        linker = _make_linker(export_count=2, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "ObjectProperty", "name": "TestProp", "value": PackageIndex(2)}
        ]
        linker._resolve_property_references()
        assert "TestProp" in inst.property_references
        assert inst.property_references["TestProp"] is linker._export_objects[1]

    def test_null_int_value_not_resolved(self):
        """int 值 0（null）不会被解析。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "ObjectProperty", "name": "NullProp", "value": 0}
        ]
        linker._resolve_property_references()
        assert "NullProp" not in getattr(inst, "property_references", {})

    def test_null_package_index_value_not_resolved(self):
        """PackageIndex(0)（null）不会被解析。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "ObjectProperty", "name": "NullProp", "value": PackageIndex(0)}
        ]
        linker._resolve_property_references()
        assert "NullProp" not in getattr(inst, "property_references", {})

    def test_out_of_bounds_package_index_not_resolved(self):
        """越界 PackageIndex 不会崩溃，只是不解析。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "ObjectProperty", "name": "BadProp", "value": PackageIndex(999)}
        ]
        linker._resolve_property_references()
        assert "BadProp" not in getattr(inst, "property_references", {})

    def test_non_property_dict_skipped(self):
        """非 dict 类型的属性被跳过。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = ["not_a_dict", 42, None]
        linker._resolve_property_references()
        # 不应崩溃
        assert not hasattr(inst, "property_references") or len(inst.property_references) == 0


class TestResolveWeakReferences:
    """WeakObjectProperty 值可以是 int 或 PackageIndex。"""

    def _make_linker_with_import(self) -> PackageLinker:
        """创建带 1 个 import 和 2 个 export 的 linker。"""
        archive = MagicMock()
        archive._file_size = 1024
        summary = MagicMock()
        name_map = ["TestName"]
        imp = MagicMock(spec=ObjectImport)
        imp.class_package = 0
        imp.class_name = 0
        imp.outer_index = PackageIndex(0)
        imp.object_name = 0
        export_map = []
        for i in range(2):
            exp = MagicMock(spec=ObjectExport)
            exp.class_index = PackageIndex(0)
            exp.super_index = PackageIndex(0)
            exp.outer_index = PackageIndex(0)
            exp.object_name = 0
            exp.serial_offset = 0
            exp.serial_size = 0
            export_map.append(exp)
        linker = PackageLinker(archive, summary, name_map, [imp], export_map)
        linker.link()
        return linker

    def test_int_value_resolved(self):
        """int 值的 WeakObjectProperty 被正确解析。"""
        linker = self._make_linker_with_import()
        inst = linker._export_objects[0]
        inst._preloaded = True
        # import index 0 → PackageIndex(-1)
        inst.serialized_properties = [
            {"type": "WeakObjectProperty", "name": "WeakProp", "value": -1}
        ]
        linker._resolve_weak_references()
        assert len(inst.weak_references) == 1
        assert inst.weak_references[0] is linker._import_objects[0]

    def test_package_index_value_resolved(self):
        """PackageIndex 值的 WeakObjectProperty 被正确解析。"""
        linker = self._make_linker_with_import()
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "WeakObjectProperty", "name": "WeakProp", "value": PackageIndex(-1)}
        ]
        linker._resolve_weak_references()
        assert len(inst.weak_references) == 1
        assert inst.weak_references[0] is linker._import_objects[0]

    def test_null_int_value_not_resolved(self):
        """int 值 0（null）不会被添加到 weak_references。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "WeakObjectProperty", "name": "NullWeak", "value": 0}
        ]
        linker._resolve_weak_references()
        assert len(inst.weak_references) == 0

    def test_null_package_index_value_not_resolved(self):
        """PackageIndex(0)（null）不会被添加到 weak_references。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "WeakObjectProperty", "name": "NullWeak", "value": PackageIndex(0)}
        ]
        linker._resolve_weak_references()
        assert len(inst.weak_references) == 0

    def test_out_of_bounds_package_index_not_resolved(self):
        """越界 PackageIndex 不会崩溃。"""
        linker = _make_linker(export_count=1, file_size=1024)
        inst = linker._export_objects[0]
        inst._preloaded = True
        inst.serialized_properties = [
            {"type": "WeakObjectProperty", "name": "BadWeak", "value": PackageIndex(999)}
        ]
        linker._resolve_weak_references()
        assert len(inst.weak_references) == 0


# ======================================================================
# Sub 4: serial_size 负值检查
# ======================================================================

class TestPreloadNegativeSerialSize:
    """serial_size 为负数时应被检测并标记失败。"""

    def test_negative_serial_size_recorded_diagnostic(self):
        """serial_size=-100 产生诊断，不崩溃，不进入 parse。"""
        linker = _make_linker(export_count=1, file_size=1024)
        linker._export_objects[0].serial_offset = 100
        linker._export_objects[0].serial_size = -100
        linker.preload(0)
        assert linker._export_objects[0]._preloaded is True
        diags = [d for d in linker.diagnostics if d.source == "preload"]
        assert len(diags) >= 1

    def test_negative_serial_size_no_parse(self):
        """serial_size 为负数时不应进入 parse_properties_from_export。"""
        linker = _make_linker(export_count=1, file_size=1024)
        linker._export_objects[0].serial_offset = 100
        linker._export_objects[0].serial_size = -1
        linker.preload(0)
        assert linker._export_objects[0]._preloaded is True
        # serialized_properties 应为空（未进入 parse）
        assert len(linker._export_objects[0].serialized_properties) == 0


# ======================================================================
# Sub 5: serial_size == 0 检查顺序
# ======================================================================

class TestPreloadZeroSizeCheckOrder:
    """serial_size == 0 检查应在偏移校验之后执行。"""

    def test_zero_size_with_invalid_offset_still_records_diagnostic(self):
        """serial_size=0 但 serial_offset 无效时，应先记录偏移诊断。"""
        linker = _make_linker(export_count=1, file_size=1024)
        linker._export_objects[0].serial_offset = -1
        linker._export_objects[0].serial_size = 0
        linker.preload(0)
        assert linker._export_objects[0]._preloaded is True
        # 应记录 serial_offset 越界诊断（即使 serial_size=0）
        diags = [d for d in linker.diagnostics if d.source == "preload"]
        assert len(diags) >= 1

    def test_zero_size_with_out_of_range_offset_records_diagnostic(self):
        """serial_size=0 但 serial_offset 超出文件范围时，应先记录偏移诊断。"""
        linker = _make_linker(export_count=1, file_size=1024)
        linker._export_objects[0].serial_offset = 2000  # > file_size
        linker._export_objects[0].serial_size = 0
        linker.preload(0)
        assert linker._export_objects[0]._preloaded is True
        diags = [d for d in linker.diagnostics if d.source == "preload"]
        assert len(diags) >= 1


# ======================================================================
# UObjectInstance 测试（合并自 test_object_instance.py）
# ======================================================================

def _make_instance(
    name: str = "TestObj",
    package_index: int = 1,
    is_import: bool = False,
    outer: "UObjectInstance | None" = None,
    linker=None,
    class_package: str | None = None,
) -> UObjectInstance:
    """创建一个用于测试的 UObjectInstance。"""
    return UObjectInstance(
        package_index=package_index,
        object_name=name,
        object_class="TestClass",
        class_package=class_package,
        outer_index=PackageIndex(0),
        is_import=is_import,
        outer=outer,
        linker=linker,
    )


class TestGetFullName:
    """get_full_name() 正常路径。"""

    def test_root_object_no_outer(self):
        """无 outer 的对象返回 object_name。"""
        inst = _make_instance(name="MyObject")
        assert inst.get_full_name() == "MyObject"

    def test_single_outer(self):
        """单层 outer 返回 Outer.Name。"""
        outer = _make_instance(name="Package")
        inner = _make_instance(name="MyObject", outer=outer)
        assert inner.get_full_name() == "Package.MyObject"

    def test_nested_outer(self):
        """多层 outer 返回完整路径。"""
        root = _make_instance(name="Root")
        mid = _make_instance(name="Mid", outer=root)
        leaf = _make_instance(name="Leaf", outer=mid)
        assert leaf.get_full_name() == "Root.Mid.Leaf"

    def test_import_with_class_package(self):
        """Import 对象使用 class_package 作为前缀。"""
        inst = _make_instance(
            name="EngineClass",
            is_import=True,
            class_package="/Script/Engine",
        )
        assert inst.get_full_name() == "/Script/Engine.EngineClass"

    def test_with_linker_summary(self):
        """有 linker.summary 时使用 package_name 作为前缀。"""
        linker = MagicMock()
        linker.summary = MagicMock()
        linker.summary.package_name = "/Game/MyPackage"
        inst = _make_instance(name="Asset", linker=linker)
        assert inst.get_full_name() == "/Game/MyPackage.Asset"

    def test_with_linker_summary_int_index(self):
        """linker.summary.package_name 为 int 索引时从 name_map 解析。"""
        linker = MagicMock()
        linker.summary = MagicMock()
        linker.summary.package_name = 0
        linker.name_map = ["ResolvedPackageName"]
        inst = _make_instance(name="Asset", linker=linker)
        assert inst.get_full_name() == "ResolvedPackageName.Asset"


class TestGetFullNameCircularDetection:
    """get_full_name() 循环引用检测。"""

    def test_self_referencing_outer(self):
        """对象 outer 指向自身时返回 <circular:N> 而非无限递归。"""
        inst = _make_instance(name="Cyclic")
        inst.outer = inst
        result = inst.get_full_name()
        assert result == "<circular:1>.Cyclic"

    def test_two_node_cycle(self):
        """A.outer=B, B.outer=A 的双向循环。"""
        a = _make_instance(name="A")
        b = _make_instance(name="B")
        a.outer = b
        b.outer = a
        # 从 A 开始：A -> B -> A(cycle)
        result_a = a.get_full_name()
        assert result_a == "<circular:2>.B.A"
        # 从 B 开始：B -> A -> B(cycle)
        result_b = b.get_full_name()
        assert result_b == "<circular:2>.A.B"

    def test_three_node_cycle(self):
        """A -> B -> C -> A 的三向循环。"""
        a = _make_instance(name="A")
        b = _make_instance(name="B")
        c = _make_instance(name="C")
        a.outer = b
        b.outer = c
        c.outer = a
        result = a.get_full_name()
        assert result == "<circular:3>.C.B.A"

    def test_long_chain_with_cycle_at_end(self):
        """正常链末尾出现循环时不崩溃。"""
        root = _make_instance(name="Root")
        mid = _make_instance(name="Mid", outer=root)
        leaf = _make_instance(name="Leaf", outer=mid)
        # Mid outer 指向 Leaf，形成 Mid -> Leaf -> Mid 循环（Root 不参与）
        mid.outer = leaf
        result = leaf.get_full_name()
        assert "<circular:" in result
        # Leaf -> Mid -> Leaf(cycle): "<circular:2>.Mid.Leaf"
        assert result == "<circular:2>.Mid.Leaf"

    def test_no_false_positive_on_normal_chain(self):
        """正常链不触发循环检测。"""
        a = _make_instance(name="A")
        b = _make_instance(name="B", outer=a)
        c = _make_instance(name="C", outer=b)
        d = _make_instance(name="D", outer=c)
        assert d.get_full_name() == "A.B.C.D"

    def test_large_cycle_does_not_crash(self):
        """50 节点循环不崩溃（性能验证）。"""
        nodes = [_make_instance(name=f"N{i}") for i in range(50)]
        for i in range(49):
            nodes[i].outer = nodes[i + 1]
        nodes[49].outer = nodes[0]  # 闭合循环
        result = nodes[0].get_full_name()
        assert "<circular:" in result
