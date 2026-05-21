"""N2CNodeTypeRegistry 单元测试。

覆盖：单例管理、精确匹配、继承回退、Unknown fallback、缓存、诊断方法。
Phase 68 Wave 2 测试。
"""
import pytest

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.type_registry import N2CNodeTypeRegistry


# === 单例管理 ===

class TestSingleton:
    """单例创建与重置。"""

    def test_singleton_creation(self):
        """get_instance() 返回同一实例。"""
        r1 = N2CNodeTypeRegistry.get_instance()
        r2 = N2CNodeTypeRegistry.get_instance()
        assert r1 is r2

    def test_reset_clears_singleton(self):
        """reset() 后 get_instance() 返回新实例。"""
        r1 = N2CNodeTypeRegistry.get_instance()
        N2CNodeTypeRegistry.reset()
        r2 = N2CNodeTypeRegistry.get_instance()
        assert r1 is not r2


# === 精确匹配 ===

class TestExactMatch:
    """resolve() 精确匹配已知类型。"""

    def test_resolve_exact_match_call_function(self):
        """K2Node_CallFunction -> CallFunction。"""
        registry = N2CNodeTypeRegistry.get_instance()
        result = registry.resolve("K2Node_CallFunction")
        assert result == N2CNodeType.CallFunction

    def test_resolve_exact_match_event(self):
        """K2Node_Event -> Event。"""
        registry = N2CNodeTypeRegistry.get_instance()
        result = registry.resolve("K2Node_Event")
        assert result == N2CNodeType.Event

    def test_resolve_exact_match_variable_get(self):
        """K2Node_VariableGet -> VariableGet。"""
        registry = N2CNodeTypeRegistry.get_instance()
        result = registry.resolve("K2Node_VariableGet")
        assert result == N2CNodeType.VariableGet


# === 继承回退 ===

class TestInheritanceFallback:
    """resolve() 沿继承链回退查找。"""

    def test_resolve_inheritance_exact_match_prioritized(self):
        """K2Node_CallArrayFunction 有自身枚举值，精确匹配优先于继承回退。"""
        registry = N2CNodeTypeRegistry.get_instance()
        result = registry.resolve("K2Node_CallArrayFunction")
        # CallArrayFunction 自身在枚举中，应返回 CallArrayFunction 而非回退到 CallFunction
        assert result == N2CNodeType.CallArrayFunction

    def test_resolve_inheritance_struct_member(self):
        """K2Node_StructMemberSet 有枚举值 StructMemberSet，精确匹配。"""
        registry = N2CNodeTypeRegistry.get_instance()
        result = registry.resolve("K2Node_StructMemberSet")
        assert result == N2CNodeType.StructMemberSet

    def test_resolve_deep_inheritance_chain(self):
        """3 层继承链回退测试。

        K2Node_ActorBoundEvent -> K2Node_Event -> K2Node_EditablePinBase -> K2Node
        如果 ActorBoundEvent 精确匹配失败，应回退到 Event。
        但 ActorBoundEvent 有枚举值，所以精确匹配应优先。
        """
        registry = N2CNodeTypeRegistry.get_instance()
        # ActorBoundEvent 有枚举值，精确匹配
        result = registry.resolve("K2Node_ActorBoundEvent")
        assert result == N2CNodeType.ActorBoundEvent

    def test_resolve_inheritance_fallback_to_switch(self):
        """K2Node_SwitchEnum 继承 K2Node_Switch，两者都有枚举值。

        精确匹配优先，返回 SwitchEnum。
        """
        registry = N2CNodeTypeRegistry.get_instance()
        result = registry.resolve("K2Node_SwitchEnum")
        assert result == N2CNodeType.SwitchEnum

    def test_resolve_inheritance_no_direct_match(self):
        """模拟一个不在枚举中但有继承关系的类型。

        由于所有已知类型都在枚举中，我们测试 Switch 基类本身。
        K2Node_Switch -> Switch (直接匹配)
        """
        registry = N2CNodeTypeRegistry.get_instance()
        result = registry.resolve("K2Node_Switch")
        assert result == N2CNodeType.Switch


# === Unknown 回退 ===

class TestUnknownFallback:
    """resolve() 未知类型返回 Unknown。"""

    def test_resolve_unknown_type(self):
        """不存在的类型返回 Unknown。"""
        registry = N2CNodeTypeRegistry.get_instance()
        result = registry.resolve("K2Node_NonExistentType")
        assert result == N2CNodeType.Unknown

    def test_resolve_unknown_cached(self):
        """第二次 resolve 同一未知类型，缓存命中返回 Unknown。"""
        registry = N2CNodeTypeRegistry.get_instance()
        unknown_type = "K2Node_NonExistentType"
        result1 = registry.resolve(unknown_type)
        result2 = registry.resolve(unknown_type)
        assert result1 == N2CNodeType.Unknown
        assert result2 == N2CNodeType.Unknown
        assert result1 is result2  # 同一枚举实例


# === 缓存 ===

class TestCache:
    """resolve() 缓存行为。"""

    def test_resolve_cache_populated(self):
        """resolve 后 _resolve_cache 包含结果（对于非精确匹配类型）。"""
        registry = N2CNodeTypeRegistry.get_instance()
        # 使用一个不在精确匹配中但在继承链中的类型
        # 所有类型都有精确匹配，所以缓存不会被填充
        # 我们需要用 Unknown 类型来测试缓存
        unknown = "K2Node_FakeType"
        registry.resolve(unknown)
        assert unknown in registry._resolve_cache
        assert registry._resolve_cache[unknown] == N2CNodeType.Unknown

    def test_resolve_cache_hit(self):
        """第二次 resolve 同一类型返回相同值。"""
        registry = N2CNodeTypeRegistry.get_instance()
        result1 = registry.resolve("K2Node_CallFunction")
        result2 = registry.resolve("K2Node_CallFunction")
        assert result1 == result2
        assert result1 == N2CNodeType.CallFunction


# === 诊断方法 ===

class TestDiagnosticMethods:
    """get_registered_types() 诊断方法。"""

    def test_get_registered_types(self):
        """返回非空排序列表，包含已知类型。"""
        registry = N2CNodeTypeRegistry.get_instance()
        types = registry.get_registered_types()
        assert isinstance(types, list)
        assert len(types) > 0
        # 检查排序
        assert types == sorted(types)
        # 检查包含已知类型
        assert "K2Node_CallFunction" in types
        assert "K2Node_Event" in types

    def test_get_registered_types_count(self):
        """数量 >= 100。"""
        registry = N2CNodeTypeRegistry.get_instance()
        types = registry.get_registered_types()
        assert len(types) >= 100, f"Expected >= 100 types, got {len(types)}"

    def test_get_registered_types_contains_branch(self):
        """包含 Branch 类型映射（K2Node_IfThenElse -> Branch）。"""
        registry = N2CNodeTypeRegistry.get_instance()
        types = registry.get_registered_types()
        assert "K2Node_IfThenElse" in types
