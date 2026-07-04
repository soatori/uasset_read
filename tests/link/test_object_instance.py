"""tests/link/test_object_instance.py — UObjectInstance 测试。

验证：
1. get_full_name() 正常路径生成完整对象路径
2. get_full_name() 检测循环引用并返回 <circular:N>
3. get_full_name() 处理无 outer、无 linker 边界情况
"""
import pytest
from unittest.mock import MagicMock

from uasset_read.link.object_instance import UObjectInstance
from uasset_read.serializers.object_resources import PackageIndex


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
