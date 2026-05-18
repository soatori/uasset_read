"""
测试 cpp_uproperty_mapper 模块。

覆盖 cpf_flags_to_uproperty_marks 函数。
"""
import pytest

from uasset_read.constants import (
    CPF_Edit,
    CPF_BlueprintVisible,
    CPF_BlueprintReadOnly,
    CPF_BlueprintReadWrite,
    CPF_EditAnywhere,
    CPF_EditInstanceOnly,
    CPF_InstancedReference,
    CPF_BlueprintAssignable,
    CPF_BlueprintCallable,
    CPF_Replicated,
    CPF_Net,
    CPF_Transient,
    CPF_DuplicateTransient,
    CPF_Config,
    CPF_SaveGame,
    CPF_NoClear,
    CPF_ExposeOnSpawn,
    CPF_Interp,
    CPF_RepNotify,
    CPF_ReferenceOnly,
    CPF_Deprecated,
    CPF_AdvancedDisplay,
    CPF_Protected,
)

from uasset_read.cpp_gen import cpf_flags_to_uproperty_marks, CPF_TO_UPROPERTY_MAP


class TestCPFToUPROPERTYMap:
    """测试 CPF_TO_UPROPERTY_MAP 映射规则。"""

    def test_map_not_empty(self):
        """映射规则列表不应为空。"""
        assert len(CPF_TO_UPROPERTY_MAP) > 0

    def test_map_contains_edit_anywhere(self):
        """应包含 EditAnywhere 映射。"""
        assert CPF_EditAnywhere in [rule[0] for rule in CPF_TO_UPROPERTY_MAP]


class TestCpfFlagsToUpropertyMarks:
    """测试 cpf_flags_to_uproperty_marks 函数。"""

    # ---- Phase 56-01 行为测试（来自 PLAN 行为块）----

    def test_plan_combined_edit_blueprint_visible(self):
        """Phase 56-01 行为测试 1: CPF_Edit | CPF_BlueprintVisible → ['EditAnywhere', 'BlueprintReadWrite']"""
        result = cpf_flags_to_uproperty_marks(CPF_Edit | CPF_BlueprintVisible)
        assert "EditAnywhere" in result
        assert "BlueprintReadWrite" in result

    def test_plan_instanced_reference(self):
        """Phase 56-01 行为测试 2: CPF_InstancedReference → ['Instanced']"""
        result = cpf_flags_to_uproperty_marks(CPF_InstancedReference)
        assert result == ["Instanced"]

    def test_plan_blueprint_read_only(self):
        """Phase 56-01 行为测试 3: CPF_BlueprintReadOnly → ['BlueprintReadOnly']"""
        result = cpf_flags_to_uproperty_marks(CPF_BlueprintReadOnly)
        assert result == ["BlueprintReadOnly"]

    def test_plan_empty_flags(self):
        """Phase 56-01 行为测试 4: 0 → []"""
        result = cpf_flags_to_uproperty_marks(0)
        assert result == []

    def test_plan_combined_three_flags(self):
        """Phase 56-01 行为测试 5: CPF_Edit | CPF_BlueprintVisible | CPF_InstancedReference → ['EditAnywhere', 'BlueprintReadWrite', 'Instanced']"""
        result = cpf_flags_to_uproperty_marks(
            CPF_Edit | CPF_BlueprintVisible | CPF_InstancedReference
        )
        assert "EditAnywhere" in result
        assert "BlueprintReadWrite" in result
        assert "Instanced" in result

    def test_plan_net_replicated(self):
        """Phase 56-01 行为测试 6: CPF_Net | CPF_Replicated → ['Replicated']"""
        result = cpf_flags_to_uproperty_marks(CPF_Net | CPF_Replicated)
        assert "Replicated" in result
        # CPF_Net 不应单独出现，因为 CPF_Replicated 隐含它
        assert "Net" not in result

    def test_plan_transient(self):
        """Phase 56-01 行为测试 7: CPF_Transient → ['Transient']"""
        result = cpf_flags_to_uproperty_marks(CPF_Transient)
        assert result == ["Transient"]

    # ---- 单标志测试 ----

    def test_edit_anywhere_single(self):
        """单独 CPF_EditAnywhere 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_EditAnywhere)
        assert "EditAnywhere" in result

    def test_edit_instance_only_single(self):
        """单独 CPF_EditInstanceOnly 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_EditInstanceOnly)
        assert "EditInstanceOnly" in result

    def test_blueprint_assignable_single(self):
        """单独 CPF_BlueprintAssignable 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_BlueprintAssignable)
        assert "BlueprintAssignable" in result

    def test_blueprint_callable_single(self):
        """单独 CPF_BlueprintCallable 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_BlueprintCallable)
        assert "BlueprintCallable" in result

    def test_save_game_single(self):
        """单独 CPF_SaveGame 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_SaveGame)
        assert "SaveGame" in result

    def test_no_clear_single(self):
        """单独 CPF_NoClear 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_NoClear)
        assert "NoClear" in result

    def test_expose_on_spawn_single(self):
        """单独 CPF_ExposeOnSpawn 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_ExposeOnSpawn)
        assert "ExposeOnSpawn" in result

    def test_interp_single(self):
        """单独 CPF_Interp 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_Interp)
        assert "Interp" in result

    def test_rep_notify_single(self):
        """单独 CPF_RepNotify 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_RepNotify)
        assert "RepNotify" in result

    def test_reference_only_single(self):
        """单独 CPF_ReferenceOnly 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_ReferenceOnly)
        assert "ReferenceOnly" in result

    def test_deprecated_single(self):
        """单独 CPF_Deprecated 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_Deprecated)
        assert "Deprecated" in result

    def test_advanced_display_single(self):
        """单独 CPF_AdvancedDisplay 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_AdvancedDisplay)
        assert "AdvancedDisplay" in result

    def test_protected_single(self):
        """单独 CPF_Protected 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_Protected)
        assert "Protected" in result

    # ---- CPF_Net 特殊处理测试 ----

    def test_net_without_replicated(self):
        """CPF_Net 单独出现时应返回 Net。"""
        result = cpf_flags_to_uproperty_marks(CPF_Net)
        assert "Net" in result

    def test_net_with_replicated_excludes_net(self):
        """CPF_Net | CPF_Replicated 应只返回 Replicated，不返回 Net。"""
        result = cpf_flags_to_uproperty_marks(CPF_Net | CPF_Replicated)
        assert "Replicated" in result
        assert "Net" not in result

    # ---- 组合标志测试 ----

    def test_edit_anywhere_with_read_write(self):
        """EditAnywhere + BlueprintReadWrite 组合。"""
        result = cpf_flags_to_uproperty_marks(CPF_EditAnywhere | CPF_BlueprintReadWrite)
        assert "EditAnywhere" in result
        assert "BlueprintReadWrite" in result

    def test_multiple_flags_no_duplicates(self):
        """多个标志组合不应产生重复标记。"""
        result = cpf_flags_to_uproperty_marks(
            CPF_Edit | CPF_BlueprintVisible | CPF_Transient | CPF_SaveGame
        )
        assert result.count("EditAnywhere") <= 1
        assert result.count("BlueprintReadWrite") <= 1
        assert result.count("Transient") <= 1
        assert result.count("SaveGame") <= 1

    def test_all_common_flags(self):
        """常见标志组合测试。"""
        result = cpf_flags_to_uproperty_marks(
            CPF_Edit | CPF_BlueprintVisible | CPF_ExposeOnSpawn | CPF_Transient
        )
        assert "EditAnywhere" in result
        assert "BlueprintReadWrite" in result
        assert "ExposeOnSpawn" in result
        assert "Transient" in result

    # ---- 组件默认标记测试 ----

    def test_component_defaults_visible_anywhere(self):
        """组件无编辑标志时应添加 VisibleAnywhere。"""
        result = cpf_flags_to_uproperty_marks(0, is_component=True)
        assert "VisibleAnywhere" in result

    def test_component_defaults_blueprint_read_only(self):
        """组件无蓝图访问标志时应添加 BlueprintReadOnly。"""
        result = cpf_flags_to_uproperty_marks(0, is_component=True)
        assert "BlueprintReadOnly" in result

    def test_component_with_edit_anywhere_no_visible(self):
        """组件有 EditAnywhere 时不添加 VisibleAnywhere。"""
        result = cpf_flags_to_uproperty_marks(CPF_EditAnywhere, is_component=True)
        assert "VisibleAnywhere" not in result
        assert "EditAnywhere" in result

    def test_component_with_blueprint_read_write_no_read_only(self):
        """组件有 BlueprintReadWrite 时不添加 BlueprintReadOnly。"""
        result = cpf_flags_to_uproperty_marks(CPF_BlueprintReadWrite, is_component=True)
        assert "BlueprintReadOnly" not in result
        assert "BlueprintReadWrite" in result

    def test_component_with_instanced_reference(self):
        """组件有 Instanced 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_InstancedReference, is_component=True)
        assert "Instanced" in result

    # ---- 边界条件测试 ----

    def test_negative_flags_returns_empty(self):
        """负数标志应返回空列表。"""
        result = cpf_flags_to_uproperty_marks(-1)
        assert result == []

    def test_large_flags_value(self):
        """大数值标志（64位边界）应正常处理。"""
        # 测试接近 64 位边界的值
        result = cpf_flags_to_uproperty_marks(0xFFFFFFFFFFFFFFFF)
        # 应该有一些标记返回，不应崩溃
        assert isinstance(result, list)

    def test_duplicate_transient_flag(self):
        """CPF_DuplicateTransient 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_DuplicateTransient)
        assert "DuplicateTransient" in result

    def test_config_flag(self):
        """CPF_Config 标志。"""
        result = cpf_flags_to_uproperty_marks(CPF_Config)
        assert "Config" in result


class TestCpfFlagsOrderPreservation:
    """测试 CPF 标志顺序保持。"""

    def test_order_matters_for_combined_check(self):
        """组合检查应该先于单标志检查。"""
        # CPF_Edit | CPF_BlueprintVisible 组合应返回 EditAnywhere + BlueprintReadWrite
        # 而不是分开返回 CPF_EditAnywhere + CPF_BlueprintReadWrite
        result = cpf_flags_to_uproperty_marks(CPF_Edit | CPF_BlueprintVisible)

        # 应包含两个标记
        assert "EditAnywhere" in result
        assert "BlueprintReadWrite" in result


class TestInvalidInput:
    """测试无效输入处理。"""

    def test_none_input(self):
        """None 输入应引发 TypeError。"""
        with pytest.raises(TypeError):
            cpf_flags_to_uproperty_marks(None)  # type: ignore

    def test_string_input(self):
        """字符串输入应引发 TypeError。"""
        with pytest.raises(TypeError):
            cpf_flags_to_uproperty_marks("invalid")  # type: ignore

    def test_float_input(self):
        """浮点数输入应引发 TypeError 或被转换为整数。"""
        with pytest.raises(TypeError):
            cpf_flags_to_uproperty_marks(1.5)  # type: ignore