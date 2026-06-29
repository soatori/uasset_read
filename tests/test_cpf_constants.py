"""CPF_* 常量与 UE ObjectMacros.h 对齐测试。"""
import pytest
from uasset_read.constants import (
    CPF_Edit, CPF_ConstParm, CPF_BlueprintVisible, CPF_ExportObject,
    CPF_BlueprintReadOnly, CPF_Net, CPF_EditFixedSize, CPF_Parm,
    CPF_OutParm, CPF_ZeroConstructor, CPF_ReturnParm, CPF_DisableEditOnTemplate,
    CPF_NonNullable, CPF_Transient, CPF_Config, CPF_RequiredParm,
    CPF_DisableEditOnInstance, CPF_EditConst, CPF_GlobalConfig,
    CPF_InstancedReference, CPF_DuplicateTransient, CPF_SaveGame,
    CPF_NoClear, CPF_Virtual, CPF_ReferenceParm, CPF_BlueprintAssignable,
    CPF_Deprecated, CPF_IsPlainOldData, CPF_RepSkip, CPF_RepNotify,
    CPF_Interp, CPF_NonTransactional, CPF_EditorOnly, CPF_NoDestructor,
    CPF_AutoWeak, CPF_ContainsInstancedReference, CPF_AssetRegistrySearchable,
    CPF_SimpleDisplay, CPF_AdvancedDisplay, CPF_Protected,
    CPF_BlueprintCallable, CPF_BlueprintAuthorityOnly, CPF_TextExportTransient,
    CPF_NonPIEDuplicateTransient, CPF_ExposeOnSpawn, CPF_PersistentInstance,
    CPF_UObjectWrapper, CPF_HasGetValueTypeHash, CPF_NativeAccessSpecifierPublic,
    CPF_NativeAccessSpecifierProtected, CPF_NativeAccessSpecifierPrivate,
    CPF_SkipSerialization, CPF_TObjectPtr, CPF_AllowSelfReference,
    CPF_ExperimentalOverridableLogic, CPF_ExperimentalAlwaysOverriden,
    CPF_ExperimentalNeverOverriden, CPF_ForcePostConstructLink,
)


class TestCPFConstantsAlignment:
    """CPF_* 常量与 UE ObjectMacros.h 逐位对齐。"""

    def test_cpf_edit(self):
        assert CPF_Edit == 0x01

    def test_cpf_const_parm(self):
        assert CPF_ConstParm == 0x02

    def test_cpf_blueprint_visible(self):
        assert CPF_BlueprintVisible == 0x04

    def test_cpf_export_object(self):
        assert CPF_ExportObject == 0x08

    def test_cpf_blueprint_read_only(self):
        assert CPF_BlueprintReadOnly == 0x10

    def test_cpf_net(self):
        assert CPF_Net == 0x20

    def test_cpf_edit_fixed_size(self):
        assert CPF_EditFixedSize == 0x40

    def test_cpf_parm(self):
        assert CPF_Parm == 0x80

    def test_cpf_out_parm(self):
        assert CPF_OutParm == 0x100

    def test_cpf_zero_constructor(self):
        assert CPF_ZeroConstructor == 0x200

    def test_cpf_return_parm(self):
        assert CPF_ReturnParm == 0x400

    def test_cpf_disable_edit_on_template(self):
        assert CPF_DisableEditOnTemplate == 0x800

    def test_cpf_non_nullable(self):
        assert CPF_NonNullable == 0x1000

    def test_cpf_transient(self):
        assert CPF_Transient == 0x2000

    def test_cpf_config(self):
        assert CPF_Config == 0x4000

    def test_cpf_required_parm(self):
        assert CPF_RequiredParm == 0x8000

    def test_cpf_disable_edit_on_instance(self):
        assert CPF_DisableEditOnInstance == 0x10000

    def test_cpf_edit_const(self):
        assert CPF_EditConst == 0x20000

    def test_cpf_global_config(self):
        assert CPF_GlobalConfig == 0x40000

    def test_cpf_instanced_reference(self):
        assert CPF_InstancedReference == 0x80000

    def test_cpf_duplicate_transient(self):
        assert CPF_DuplicateTransient == 0x200000

    def test_cpf_save_game(self):
        assert CPF_SaveGame == 0x1000000

    def test_cpf_no_clear(self):
        assert CPF_NoClear == 0x2000000

    def test_cpf_virtual(self):
        assert CPF_Virtual == 0x4000000

    def test_cpf_reference_parm(self):
        assert CPF_ReferenceParm == 0x8000000

    def test_cpf_blueprint_assignable(self):
        assert CPF_BlueprintAssignable == 0x10000000

    def test_cpf_deprecated(self):
        assert CPF_Deprecated == 0x20000000

    def test_cpf_is_plain_old_data(self):
        assert CPF_IsPlainOldData == 0x40000000

    def test_cpf_rep_skip(self):
        assert CPF_RepSkip == 0x80000000

    def test_cpf_rep_notify(self):
        assert CPF_RepNotify == 0x100000000

    def test_cpf_interp(self):
        assert CPF_Interp == 0x200000000

    def test_cpf_non_transactional(self):
        assert CPF_NonTransactional == 0x400000000

    def test_cpf_editor_only(self):
        assert CPF_EditorOnly == 0x800000000

    def test_cpf_no_destructor(self):
        assert CPF_NoDestructor == 0x1000000000

    def test_cpf_auto_weak(self):
        assert CPF_AutoWeak == 0x4000000000

    def test_cpf_contains_instanced_reference(self):
        assert CPF_ContainsInstancedReference == 0x8000000000

    def test_cpf_asset_registry_searchable(self):
        assert CPF_AssetRegistrySearchable == 0x10000000000

    def test_cpf_simple_display(self):
        assert CPF_SimpleDisplay == 0x20000000000

    def test_cpf_advanced_display(self):
        assert CPF_AdvancedDisplay == 0x40000000000

    def test_cpf_protected(self):
        assert CPF_Protected == 0x80000000000

    def test_cpf_blueprint_callable(self):
        assert CPF_BlueprintCallable == 0x100000000000

    def test_cpf_blueprint_authority_only(self):
        assert CPF_BlueprintAuthorityOnly == 0x200000000000

    def test_cpf_text_export_transient(self):
        assert CPF_TextExportTransient == 0x400000000000

    def test_cpf_non_pie_duplicate_transient(self):
        assert CPF_NonPIEDuplicateTransient == 0x800000000000

    def test_cpf_expose_on_spawn(self):
        assert CPF_ExposeOnSpawn == 0x1000000000000

    def test_cpf_persistent_instance(self):
        assert CPF_PersistentInstance == 0x2000000000000

    def test_cpf_uobject_wrapper(self):
        assert CPF_UObjectWrapper == 0x4000000000000

    def test_cpf_has_value_type_hash(self):
        assert CPF_HasGetValueTypeHash == 0x8000000000000

    def test_cpf_native_access_specifier_public(self):
        assert CPF_NativeAccessSpecifierPublic == 0x10000000000000

    def test_cpf_native_access_specifier_protected(self):
        assert CPF_NativeAccessSpecifierProtected == 0x20000000000000

    def test_cpf_native_access_specifier_private(self):
        assert CPF_NativeAccessSpecifierPrivate == 0x40000000000000

    def test_cpf_skip_serialization(self):
        assert CPF_SkipSerialization == 0x80000000000000

    def test_cpf_tobject_ptr(self):
        assert CPF_TObjectPtr == 0x100000000000000

    def test_cpf_allow_self_reference(self):
        assert CPF_AllowSelfReference == 0x1000000000000000

    def test_cpf_experimental_overridable_logic(self):
        assert CPF_ExperimentalOverridableLogic == 0x0200000000000000

    def test_cpf_experimental_always_overriden(self):
        assert CPF_ExperimentalAlwaysOverriden == 0x0400000000000000

    def test_cpf_experimental_never_overriden(self):
        assert CPF_ExperimentalNeverOverriden == 0x0800000000000000

    def test_cpf_force_post_construct_link(self):
        assert CPF_ForcePostConstructLink == 0x2000000000000000

    def test_no_nonexistent_flags(self):
        """验证不存在的标志位已被移除。"""
        import uasset_read.constants as c
        removed = [
            'CPF_BlueprintPure', 'CPF_BlueprintCompilerGenerated',
            'CPF_NetSerialize', 'CPF_RepRetry', 'CPF_Constructed',
            'CPF_NaturalizePropertyIndex', 'CPF_Required',
            'CPF_ReferencePersisted',
        ]
        for name in removed:
            assert not hasattr(c, name), f"{name} 不应存在于 constants 中"

    def test_all_flags_are_power_of_two(self):
        """所有 CPF_* 常量必须是 2 的幂（位掩码）。"""
        import uasset_read.constants as c
        flags = [v for k, v in vars(c).items() if k.startswith('CPF_') and isinstance(v, int)]
        for flag in flags:
            assert flag > 0 and (flag & (flag - 1)) == 0, f"CPF_* 值 {flag:#x} 不是 2 的幂"

    def test_no_duplicate_values(self):
        """CPF_* 常量值不得重复。"""
        import uasset_read.constants as c
        flags = [v for k, v in vars(c).items() if k.startswith('CPF_') and isinstance(v, int)]
        assert len(flags) == len(set(flags)), "存在重复的 CPF_* 值"
