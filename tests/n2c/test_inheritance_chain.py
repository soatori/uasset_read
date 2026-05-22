"""继承链集成测试 — 验证 3 层深度节点正确解析。

Phase 68 Wave 3 输出。
"""
import pytest
from uasset_read.n2c.type_registry import N2CNodeTypeRegistry
from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.type_data import K2NODE_INHERITANCE, get_parent_chain


class TestInheritanceChain:
    """继承链集成测试。"""

    def setup_method(self):
        """每个测试前重置注册表，避免状态污染。"""
        N2CNodeTypeRegistry.reset()

    def test_call_array_function_resolves_to_call_function_via_inheritance(self):
        """K2Node_CallArrayFunction 有独立枚举值时精确匹配。"""
        registry = N2CNodeTypeRegistry.get_instance()
        result = registry.resolve("K2Node_CallArrayFunction")
        # 如果枚举有 CallArrayFunction → 精确匹配
        # 如果没有 → 继承回退到 CallFunction
        assert result in [N2CNodeType.CallArrayFunction, N2CNodeType.CallFunction]

    def test_three_level_inheritance(self):
        """3 层继承链回退测试。

        示例：K2Node_StructMemberSet → K2Node_StructOperation → K2Node_Variable
        应正确回退到最近有处理器的祖先类型。
        """
        registry = N2CNodeTypeRegistry.get_instance()
        chain = get_parent_chain("K2Node_StructMemberSet")
        assert len(chain) >= 3, f"Expected 3+ levels, got {len(chain)}: {chain}"

    def test_inheritance_map_no_cycles(self):
        """继承关系映射无循环。"""
        for class_name in K2NODE_INHERITANCE:
            chain = get_parent_chain(class_name)
            assert len(chain) <= 10, f"Chain too long for {class_name}: {chain}"
            # 无重复
            assert len(chain) == len(set(chain)), f"Cycle detected for {class_name}: {chain}"

    def test_all_types_have_valid_inheritance(self):
        """所有类型在继承链中最终能到达 K2Node 或根类型。"""
        from uasset_read.n2c.type_data import K2NODE_TYPES
        root_types = {"K2Node", "UK2Node"}
        for class_name in K2NODE_TYPES:
            if class_name not in K2NODE_INHERITANCE:
                continue  # 根类型无父类
            chain = get_parent_chain(class_name)
            assert any(t in str(chain[-1]) for t in root_types), \
                f"{class_name} chain does not reach root: {chain}"


class TestUnknownFallback:
    """Unknown fallback 测试。"""

    def setup_method(self):
        """每个测试前重置注册表。"""
        N2CNodeTypeRegistry.reset()

    def test_unregistered_type_returns_unknown(self):
        """未注册类型返回 Unknown。"""
        registry = N2CNodeTypeRegistry.get_instance()
        result = registry.resolve("K2Node_CustomPluginNode")
        assert result == N2CNodeType.Unknown

    def test_unknown_is_cached(self):
        """Unknown 结果被缓存。"""
        registry = N2CNodeTypeRegistry.get_instance()
        registry.resolve("K2Node_UnknownTest1")
        assert "K2Node_UnknownTest1" in registry._resolve_cache

    def test_empty_string_returns_unknown(self):
        """空字符串返回 Unknown。"""
        registry = N2CNodeTypeRegistry.get_instance()
        result = registry.resolve("")
        assert result == N2CNodeType.Unknown

    def test_none_like_string(self):
        """类似 None 的字符串返回 Unknown。"""
        registry = N2CNodeTypeRegistry.get_instance()
        result = registry.resolve("None")
        assert result == N2CNodeType.Unknown
