"""variable_extractor.py 单元测试"""

from uasset_read.constants import CPF_Edit, CPF_EditConst
from uasset_read.blueprint.variable_extractor import _map_property_flags, _is_internal_engine_property


class TestMapPropertyFlags:
    """_map_property_flags 对 CPF_Edit / CPF_EditConst 的处理。"""

    def test_edit_only_sets_is_edit_instance_only(self):
        """仅设 CPF_Edit 时 is_edit_instance_only 为 True。"""
        flags = CPF_Edit
        result = _map_property_flags(flags)
        assert result["is_edit_anywhere"] is True
        assert result["is_edit_instance_only"] is True

    def test_edit_and_editconst_clears_is_edit_instance_only(self):
        """CPF_Edit | CPF_EditConst 时 is_edit_instance_only 为 False。"""
        flags = CPF_Edit | CPF_EditConst
        result = _map_property_flags(flags)
        assert result["is_edit_anywhere"] is True
        assert result["is_edit_instance_only"] is False

    def test_no_edit_flags(self):
        """无 CPF_Edit 标志时两个 edit 字段均为 False。"""
        flags = 0
        result = _map_property_flags(flags)
        assert result["is_edit_anywhere"] is False
        assert result["is_edit_instance_only"] is False

    def test_editconst_alone(self):
        """仅有 CPF_EditConst（无 CPF_Edit）时两个 edit 字段均为 False。"""
        flags = CPF_EditConst
        result = _map_property_flags(flags)
        assert result["is_edit_anywhere"] is False
        assert result["is_edit_instance_only"] is False

    def test_other_flags_not_affected(self):
        """其他标志不受影响。"""
        flags = CPF_Edit | CPF_EditConst
        result = _map_property_flags(flags)
        assert result["is_blueprint_readable"] is False
        assert result["is_transient"] is False


class TestIsInternalEngineProperty:
    """_is_internal_engine_property 不误过滤合法蓝图变量。"""

    def test_legitimate_blueprint_variables_not_filtered(self):
        """合法蓝图变量不应被过滤。"""
        # bIsPlayer, bHasWeapon 等合法蓝图布尔变量
        legitimate_vars = [
            "bIsPlayer", "bHasWeapon", "bCanJump", "bShouldAttack",
            "bEnableSprint", "bForceReload", "bDeferDamage", "bDisableAI",
            "bAllowMovement", "bDisplayHUD", "bCreateParticle", "bLoadAsset",
            # Cached/Selected/Original 前缀的合法变量
            "CachedHealth", "CachedDamage", "SelectedTarget", "SelectedWeapon",
            "OriginalPosition", "OriginalRotation",
            # 其他合法变量
            "PlayerScore", "EnemyCount", "IsAlive", "HasAmmo",
        ]
        for var_name in legitimate_vars:
            result = _is_internal_engine_property(var_name)
            assert result is False, f"{var_name} should not be filtered as internal"

    def test_internal_engine_properties_filtered(self):
        """内部引擎属性应被过滤。"""
        internal_vars = [
            "bBeingCompiled", "bCompiled", "bRegenerating",
            "BlueprintGeneratedClass", "SelectedNodes", "bAllowRenaming",
            "bAllowMultipleOutputs", "bAllowMultipleInputs",
            "bIsRegenerating", "bIsRegeneratingClass",
            "bIsIncrementalCompile", "bIsRegeneratingOnLoad",
        ]
        for var_name in internal_vars:
            result = _is_internal_engine_property(var_name)
            assert result is True, f"{var_name} should be filtered as internal"
