"""Phase 35d-02: 蓝图变量提取修正测试。

CR-11: is_replicated 使用 CPF_Replicated (0x00100000) 而非 CPF_Net (0x00000020)
LOW-04: BlueprintVariable 移除冗余 meta_data 字段
HIGH-10: _extract_pin_type_from_property 添加 hasattr 保护
"""
import pytest
from unittest.mock import MagicMock

from uasset_read.blueprint.variable_extractor import _map_property_flags, _extract_pin_type_from_property
from uasset_read.constants import CPF_Net, CPF_Replicated
from uasset_read.models.core import FEdGraphPinType


# ============================================================================
# Task 1: CR-11 — is_replicated 标志映射修正
# ============================================================================

class TestIsReplicatedFlagMapping:
    """验证 is_replicated 使用 CPF_Replicated 而非 CPF_Net。"""

    def test_is_replicated_uses_cpf_replicated_not_cpf_net(self):
        """flags = CPF_Replicated (0x00100000) → is_replicated=True, is_net=False"""
        result = _map_property_flags(CPF_Replicated)
        assert result["is_replicated"] is True, "CPF_Replicated → is_replicated=True"
        assert result["is_net"] is False, "CPF_Replicated 不影响 is_net"

    def test_is_net_uses_cpf_net_not_cpf_replicated(self):
        """flags = CPF_Net (0x00000020) → is_net=True, is_replicated=False"""
        result = _map_property_flags(CPF_Net)
        assert result["is_net"] is True, "CPF_Net → is_net=True"
        assert result["is_replicated"] is False, "CPF_Net 不影响 is_replicated"

    def test_both_flags_set(self):
        """flags = CPF_Net | CPF_Replicated → is_net=True, is_replicated=True"""
        result = _map_property_flags(CPF_Net | CPF_Replicated)
        assert result["is_net"] is True
        assert result["is_replicated"] is True

    def test_no_flags(self):
        """flags = 0 → is_net=False, is_replicated=False"""
        result = _map_property_flags(0)
        assert result["is_net"] is False
        assert result["is_replicated"] is False


# ============================================================================
# Task 3: HIGH-10 — _extract_pin_type_from_property hasattr 保护
# ============================================================================

class TestExtractPinTypeHasattrGuard:
    """验证 _extract_pin_type_from_property 不会因缺少 type 属性崩溃。"""

    def test_extract_pin_type_with_type_attribute(self):
        """prop 有 type 属性 → 正常返回映射的 FEdGraphPinType"""
        prop = MagicMock()
        prop.value = "IntProperty"
        prop.type = "IntProperty"
        result = _extract_pin_type_from_property(prop)
        assert isinstance(result, FEdGraphPinType)
        assert result.pin_category == "int"

    def test_extract_pin_type_without_type_attribute(self):
        """prop 无 type 属性 → 返回 unknown (无 AttributeError)"""
        prop = MagicMock(spec=[])  # 禁止自动创建属性
        prop.value = "SomeTypeString"
        # prop 没有 type 属性
        result = _extract_pin_type_from_property(prop)
        assert isinstance(result, FEdGraphPinType)
        assert result.pin_category == "unknown"

    def test_extract_pin_type_with_none_type(self):
        """prop 有 type=None → 不崩溃，返回 pin_category=None"""
        prop = MagicMock()
        prop.value = "SomeTypeString"
        prop.type = None
        result = _extract_pin_type_from_property(prop)
        assert isinstance(result, FEdGraphPinType)
        assert result.pin_category is None
