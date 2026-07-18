"""Blueprint 变量与 Pin 测试（blueprint/variables）。

合并自：
- test_variable_extractor.py — VariableExtractor 缺陷修复（标志位、类型映射、组件检测）
- test_pin_guid_filtering.py — PinReference GUID 格式统一
- test_pin_recovery.py — Pin 连接关系恢复、FText 安全网、滑动恢复
"""
from __future__ import annotations

import struct
import pytest
from unittest.mock import MagicMock, patch, PropertyMock, call

from uasset_read.constants import (
    CPF_Edit, CPF_EditConst, CPF_BlueprintVisible, CPF_BlueprintReadOnly,
    CPF_Transient, CPF_InstancedReference, CPF_Net, CPF_SaveGame,
    CPF_BlueprintAssignable, CPF_RepNotify, CPF_Protected, CPF_ExposeOnSpawn,
    CPF_Config, CPF_Deprecated, CPF_BlueprintCallable, CPF_Interp,
    MAX_FTEXT_CONSUMPTION,
)
from uasset_read.models.properties import StructValue, PropertyValue
from uasset_read.models.core import FEdGraphPinType
from uasset_read.blueprint.variable_extractor import (
    _is_internal_engine_property,
    _map_property_flags,
    _extract_pin_type_from_property,
    _extract_blueprint_variable_descriptions,
    _map_pin_category_to_cpp_type,
    extract_blueprint_variables,
    parse_property_flags_to_labels,
)
from uasset_read.graph.flow_builder import _pin_ref_guid, _is_valid_pin_guid
from uasset_read.serializers.graph_pin import (
    read_ue_graph_pin,
    read_pin_reference,
    _recover_pin_array_count,
    _try_recover_to_subpins,
)



# === VariableExtractor 缺陷修复测试 ===

class TestFlagsToLabelsEditConst:

    """parse_property_flags_to_labels 在 CPF_EditConst 时应输出 'EditConst' 而非 'EditAnywhere'。"""

    def test_edit_only_generates_editanywhere(self):
        """仅 CPF_Edit → EditAnywhere。"""
        labels = parse_property_flags_to_labels(CPF_Edit)
        assert "EditAnywhere" in labels
        assert "EditConst" not in labels

    def test_edit_and_editconst_generates_editconst(self):
        """CPF_Edit | CPF_EditConst → EditConst（不是 EditAnywhere）。"""
        labels = parse_property_flags_to_labels(CPF_Edit | CPF_EditConst)
        assert "EditConst" in labels, (
            "CPF_Edit | CPF_EditConst 应生成 'EditConst' 标签，"
            f"实际得到: {labels}"
        )
        # EditAnywhere 和 EditConst 不应同时出现
        assert "EditAnywhere" not in labels, (
            "EditConst 模式下不应同时出现 'EditAnywhere' 标签"
        )

    def test_parse_property_flags_labels_consistent(self):
        """parse_property_flags_to_labels 已正确处理 EditConst，
        应在 EditConst 模式下输出正确标签。"""
        flags = CPF_Edit | CPF_EditConst
        parse_labels = parse_property_flags_to_labels(flags)
        flag_labels = parse_property_flags_to_labels(flags)
        # 两者都应包含 EditConst
        assert "EditConst" in parse_labels, "parse 侧已验证 EditConst"
        assert "EditConst" in flag_labels, (
            "parse_property_flags_to_labels 应包含 EditConst 标签"
        )


# ===========================================================================
# Defect 2: _map_property_flags 语义混淆
# ===========================================================================

class TestMapPropertyFlagsSemantics:
    """_map_property_flags 中 is_edit_anywhere 和 is_edit_instance_only
    不应映射到相同的标志位。"""

    def test_edit_alone_sets_edit_anywhere(self):
        """CPF_Edit（无 EditConst）→ is_edit_anywhere=True, is_edit_instance_only=True。"""
        result = _map_property_flags(CPF_Edit)
        assert result["is_edit_anywhere"] is True

    def test_edit_with_editconst_differentiates(self):
        """CPF_Edit | CPF_EditConst 时 is_edit_anywhere 和 is_edit_instance_only
        应产生不同结果。"""
        result = _map_property_flags(CPF_Edit | CPF_EditConst)
        # 当前代码两者都使用 flags & CPF_Edit，语义相同
        # 修复后，is_edit_instance_only 应与 is_edit_anywhere 区分
        assert result["is_edit_anywhere"] is True, "Edit 标志应设置 is_edit_anywhere"
        assert result["is_edit_instance_only"] is False, (
            "EditConst 模式下 is_edit_instance_only 应为 False（不可在实例编辑）"
        )

    def test_editconst_alone(self):
        """仅 CPF_EditConst（无 CPF_Edit）→ is_edit_anywhere=False, is_edit_instance_only=False。
        CPF_EditConst 语义为"仅默认值可编辑"，无 CPF_Edit 时两者都应为 False。"""
        result = _map_property_flags(CPF_EditConst)
        assert result["is_edit_anywhere"] is False, (
            "CPF_EditConst 单独设置时，无 CPF_Edit 位，is_edit_anywhere 应为 False"
        )
        assert result["is_edit_instance_only"] is False, (
            "CPF_EditConst 单独设置时，is_edit_instance_only 应为 False"
        )

    def test_no_edit_flags(self):
        """无 CPF_Edit → 两者都为 False。"""
        result = _map_property_flags(0)
        assert result["is_edit_anywhere"] is False
        assert result["is_edit_instance_only"] is False

    def test_blueprint_readable_and_readonly_exclusive(self):
        """CPF_BlueprintVisible | CPF_BlueprintReadOnly 时
        is_blueprint_readable=True, is_blueprint_read_only=True。"""
        result = _map_property_flags(CPF_BlueprintVisible | CPF_BlueprintReadOnly)
        assert result["is_blueprint_readable"] is True
        assert result["is_blueprint_read_only"] is True


# ===========================================================================
# Defect 3: _extract_pin_type_from_property 非 dict UInt32Property
# ===========================================================================

class TestExtractPinTypeUInt32:
    """UInt32Property 等类型在非 dict 值路径中应正确映射。"""

    def test_uint32_property_non_dict(self):
        """UInt32Property 非 dict 值应映射到 pin_category='uint32'。"""
        prop = PropertyValue(name="Health", type="UInt32Property", value=42)
        result = _extract_pin_type_from_property(prop)
        assert result.pin_category == "uint32", (
            f"UInt32Property 应映射到 'uint32'，实际得到: {result.pin_category}"
        )

    def test_uint32_property_dict_with_no_pin_category(self):
        """UInt32Property dict 值（无 pin_category）应通过 _PROPERTY_TYPE_TO_PIN_CATEGORY 映射。"""
        prop = PropertyValue(
            name="Count",
            type="UInt32Property",
            value={"some_field": 100},
        )
        result = _extract_pin_type_from_property(prop)
        assert result.pin_category == "uint32"

    def test_soft_object_property_non_dict(self):
        """SoftObjectProperty 非 dict 值应映射到 pin_category='soft_object'。"""
        prop = PropertyValue(name="AssetRef", type="SoftObjectProperty", value="None")
        result = _extract_pin_type_from_property(prop)
        assert result.pin_category == "soft_object"


# ===========================================================================
# Defect 4: _extract_blueprint_variable_descriptions 缺失组件检测
# ===========================================================================

class TestExtractVariableDescriptionsComponent:
    """_extract_blueprint_variable_descriptions 应检测组件变量。"""

    def test_component_variable_in_new_variables(self):
        """NewVariables 中含 'Component' 的 ObjectProperty 应标记 is_component。"""
        component_sv = StructValue(
            struct_type="BPVariableDescription",
            fields={
                "VarName": "MySceneComp",
                "VarType": {
                    "PinCategory": "ObjectProperty",
                    "PinSubcategory": "/Script/Engine.SceneComponent",
                    "ContainerType": 0,
                },
                "Category": "Component",
                "PropertyFlags": 0,
                "MetaDataArray": [],
            },
        )
        variables = _extract_blueprint_variable_descriptions([component_sv])
        assert len(variables) == 1
        assert variables[0].is_component is True, (
            "VarType pin_subcategory 含 'SceneComponent' 的变量应标记 is_component=True"
        )

    def test_non_component_variable(self):
        """非组件变量 is_component 应为 False。"""
        var_sv = StructValue(
            struct_type="BPVariableDescription",
            fields={
                "VarName": "Health",
                "VarType": {
                    "PinCategory": "float",
                    "PinSubcategory": "",
                    "ContainerType": 0,
                },
                "Category": "Default",
                "PropertyFlags": 0,
                "MetaDataArray": [],
            },
        )
        variables = _extract_blueprint_variable_descriptions([var_sv])
        assert len(variables) == 1
        assert variables[0].is_component is False


# ===========================================================================
# Defect 5: extract_blueprint_variables CPF_InstancedReference 组件检测
# ===========================================================================

class TestExtractBlueprintVariablesComponent:
    """extract_blueprint_variables 应同时通过名称和 CPF_InstancedReference
    检测组件变量。"""

    def test_instanced_reference_flag_marks_component(self):
        """ObjectProperty + CPF_InstancedReference 应标记 is_component=True。"""
        prop = PropertyValue(
            name="MyComponent",
            type="ObjectProperty",
            value={
                "object_class": "UActorComponent",
                "property_flags": CPF_InstancedReference,
            },
        )
        variables = extract_blueprint_variables([prop])
        assert len(variables) == 1
        assert variables[0].is_component is True, (
            "CPF_InstancedReference 标志应触发 is_component=True"
        )

    def test_name_based_component_detection(self):
        """ObjectProperty 含 'Component' 子类名应标记 is_component。"""
        prop = PropertyValue(
            name="CameraComp",
            type="ObjectProperty",
            value={
                "object_class": "UCameraComponent",
                "property_flags": 0,
            },
        )
        variables = extract_blueprint_variables([prop])
        assert len(variables) == 1
        assert variables[0].is_component is True


# ===========================================================================
# 辅助函数测试
# ===========================================================================

class TestMapPinCategoryToCppType:
    """_map_pin_category_to_cpp_type 映射验证。"""

    def test_known_types(self):
        assert _map_pin_category_to_cpp_type("real") == "float"
        assert _map_pin_category_to_cpp_type("double") == "double"
        assert _map_pin_category_to_cpp_type("int") == "int32"
        assert _map_pin_category_to_cpp_type("int64") == "int64"
        assert _map_pin_category_to_cpp_type("byte") == "uint8"
        assert _map_pin_category_to_cpp_type("bool") == "bool"
        assert _map_pin_category_to_cpp_type("string") == "FString"
        assert _map_pin_category_to_cpp_type("name") == "FName"
        assert _map_pin_category_to_cpp_type("text") == "FText"

    def test_struct_types(self):
        assert _map_pin_category_to_cpp_type("struct") == "FStruct"
        assert _map_pin_category_to_cpp_type("vector") == "FVector"
        assert _map_pin_category_to_cpp_type("rotator") == "FRotator"
        assert _map_pin_category_to_cpp_type("transform") == "FTransform"
        assert _map_pin_category_to_cpp_type("vector2d") == "FVector2D"
        assert _map_pin_category_to_cpp_type("linearcolor") == "FLinearColor"

    def test_object_types(self):
        assert _map_pin_category_to_cpp_type("object") == "UObject*"
        assert _map_pin_category_to_cpp_type("class") == "UClass*"
        assert _map_pin_category_to_cpp_type("widget") == "UWidget*"

    def test_case_insensitive(self):
        """大小写不敏感匹配。"""
        assert _map_pin_category_to_cpp_type("Real") == "float"
        assert _map_pin_category_to_cpp_type("VECTOR") == "FVector"
        assert _map_pin_category_to_cpp_type("Boolean") == "bool"

    def test_script_path_passthrough(self):
        """以 /Script/ 开头的路径应直接返回。"""
        path = "/Script/Engine.Actor"
        assert _map_pin_category_to_cpp_type(path) == path

    def test_unknown_returns_raw(self):
        """未知类型名应返回原始字符串。"""
        assert _map_pin_category_to_cpp_type("CustomType") == "CustomType"

    def test_whitespace_stripped(self):
        """前后空白应被剥离。"""
        assert _map_pin_category_to_cpp_type("  vector  ") == "FVector"


class TestExtractPinTypeEdgeCases:
    """_extract_pin_type_from_property 边界情况。"""

    def test_enum_property_non_dict(self):
        """EnumProperty 非 dict 值应返回 pin_category=byte, pin_subcategory=enum。"""
        prop = PropertyValue(name="State", type="EnumProperty", value="Active")
        result = _extract_pin_type_from_property(prop)
        assert result.pin_category == "byte"
        assert result.pin_subcategory == "enum"

    def test_dict_struct_with_pin_category_override(self):
        """StructProperty dict 含 PinCategory 时应直接使用。"""
        prop = PropertyValue(
            name="Custom",
            type="StructProperty",
            value={"PinCategory": "rotator", "PinSubcategory": ""},
        )
        result = _extract_pin_type_from_property(prop)
        assert result.pin_category == "rotator"

    def test_non_dict_non_typed_value(self):
        """无 type 属性的 prop应回退到 unknown。"""
        prop = PropertyValue(name="Weird", type="NonexistentType", value=42)
        result = _extract_pin_type_from_property(prop)
        # NonexistentType 不在 type_mapping 也不在 _PROPERTY_TYPE_TO_PIN_CATEGORY
        assert result.pin_category == "NonexistentType"

    def test_dict_with_container_type(self):
        """dict 值含 container_type 时应正确传递。"""
        prop = PropertyValue(
            name="Items",
            type="ArrayProperty",
            value={"pin_category": "int", "container_type": 1},
        )
        result = _extract_pin_type_from_property(prop)
        assert result.pin_category == "int"
        assert result.container_type == 1


class TestExtractBlueprintVariableDescriptions:
    """_extract_blueprint_variable_descriptions 基本功能。"""

    def test_empty_list(self):
        """空列表返回空结果。"""
        assert _extract_blueprint_variable_descriptions([]) == []

    def test_item_without_var_name_skipped(self):
        """无 VarName 的条目应被跳过。"""
        sv = StructValue(
            struct_type="BPVariableDescription",
            fields={"Category": "Default"},
        )
        assert _extract_blueprint_variable_descriptions([sv]) == []

    def test_basic_float_variable(self):
        """基本 Float 变量提取。"""
        sv = StructValue(
            struct_type="BPVariableDescription",
            fields={
                "VarName": "Speed",
                "VarType": {
                    "PinCategory": "float",
                    "PinSubcategory": "",
                    "ContainerType": 0,
                },
                "PropertyFlags": CPF_Edit | CPF_BlueprintVisible,
                "MetaDataArray": [],
            },
        )
        variables = _extract_blueprint_variable_descriptions([sv])
        assert len(variables) == 1
        v = variables[0]
        assert v.var_name == "Speed"
        assert v.var_type.pin_category == "float"
        assert v.is_edit_anywhere is True
        assert v.is_blueprint_readable is True


class TestExtractBlueprintVariables:
    """extract_blueprint_variables 功能测试。"""

    def test_empty_properties(self):
        """空属性列表返回空变量列表。"""
        assert extract_blueprint_variables([]) == []

    def test_new_variables_property(self):
        """NewVariables 属性应被展开为变量列表。"""
        var_sv = StructValue(
            struct_type="BPVariableDescription",
            fields={
                "VarName": "Counter",
                "VarType": {"PinCategory": "int", "PinSubcategory": ""},
                "PropertyFlags": 0,
                "MetaDataArray": [],
            },
        )
        prop = PropertyValue(name="NewVariables", type="ArrayProperty", value=[var_sv])
        variables = extract_blueprint_variables([prop])
        assert len(variables) == 1
        assert variables[0].var_name == "Counter"

    def test_metadata_property_names_skipped(self):
        """蓝图元数据属性名应被跳过。"""
        prop = PropertyValue(name="ParentClass", type="ObjectProperty", value={})
        assert extract_blueprint_variables([prop]) == []

    def test_direct_property_extraction(self):
        """直接属性应被提取为变量。"""
        prop = PropertyValue(
            name="Score",
            type="IntProperty",
            value={"property_flags": CPF_BlueprintVisible},
        )
        variables = extract_blueprint_variables([prop])
        assert len(variables) == 1
        assert variables[0].var_name == "Score"
        assert variables[0].var_type.pin_category == "int"


class TestParsePropertyFlagsToLabels:
    """parse_property_flags_to_labels 完整标志位覆盖。"""

    def test_empty_flags(self):
        """空标志返回空列表。"""
        assert parse_property_flags_to_labels(0) == []

    def test_edit_only(self):
        labels = parse_property_flags_to_labels(CPF_Edit)
        assert labels == ["EditAnywhere"]

    def test_edit_const(self):
        labels = parse_property_flags_to_labels(CPF_Edit | CPF_EditConst)
        assert labels == ["EditConst"]

    def test_blueprint_read_write(self):
        labels = parse_property_flags_to_labels(CPF_BlueprintVisible)
        assert "BlueprintReadWrite" in labels

    def test_blueprint_read_only(self):
        labels = parse_property_flags_to_labels(CPF_BlueprintVisible | CPF_BlueprintReadOnly)
        assert "BlueprintReadOnly" in labels

    def test_multiple_flags(self):
        flags = CPF_Edit | CPF_BlueprintVisible | CPF_Transient | CPF_Net
        labels = parse_property_flags_to_labels(flags)
        assert "EditAnywhere" in labels
        assert "BlueprintReadWrite" in labels
        assert "Transient" in labels
        assert "Net" in labels
        assert "Replicated" in labels

    def test_instanced_reference(self):
        labels = parse_property_flags_to_labels(CPF_InstancedReference)
        assert "InstancedReference" in labels

    def test_protected(self):
        labels = parse_property_flags_to_labels(CPF_Protected)
        assert "Protected" in labels

    def test_expose_on_spawn(self):
        labels = parse_property_flags_to_labels(CPF_ExposeOnSpawn)
        assert "ExposeOnSpawn" in labels

    def test_deprecated(self):
        labels = parse_property_flags_to_labels(CPF_Deprecated)
        assert "Deprecated" in labels

    def test_blueprint_callable(self):
        labels = parse_property_flags_to_labels(CPF_BlueprintCallable)
        assert "BlueprintCallable" in labels

    def test_rep_notify(self):
        labels = parse_property_flags_to_labels(CPF_RepNotify)
        assert "RepNotify" in labels

    def test_interp(self):
        labels = parse_property_flags_to_labels(CPF_Interp)
        assert "Interp" in labels

    def test_save_game(self):
        labels = parse_property_flags_to_labels(CPF_SaveGame)
        assert "SaveGame" in labels

    def test_config(self):
        labels = parse_property_flags_to_labels(CPF_Config)
        assert "Config" in labels



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


class TestWildcardTypeMapping:
    """验证通配符 Pin category 正确映射。"""

    def test_wildcard_without_leading_space(self):
        """'wildcard'（无前导空格）应映射到 'Wildcard'。"""
        result = _map_pin_category_to_cpp_type("wildcard")
        assert result == "Wildcard"

    def test_wildcard_with_leading_space(self):
        """' wildcard'（有前导空格）也应映射到 'Wildcard'。"""
        result = _map_pin_category_to_cpp_type(" wildcard")
        assert result == "Wildcard"

    def test_exec_maps_to_void(self):
        """'exec' 映射到 'void'。"""
        result = _map_pin_category_to_cpp_type("exec")
        assert result == "void"

    def test_object_types_still_work(self):
        """对象类型映射不受影响。"""
        result = _map_pin_category_to_cpp_type("object")
        assert result == "UObject*"

# === Pin GUID 格式统一测试 ===

class TestPinGuidFormat:

    """验证 PinReference GUID 与 pin_id 格式兼容。"""

    def test_pin_ref_guid_from_dict_with_dashes(self):
        """PinReference dict 返回归一化后的 GUID（无 dash，小写）。"""
        ref = {"pin_guid": "A1B2C3D4-E5F6-7890-ABCD-EF1234567890", "owning_node": "TestNode"}
        result = _pin_ref_guid(ref)
        assert result == "a1b2c3d4e5f67890abcdef1234567890"

    def test_pin_ref_guid_from_dict_without_dashes(self):
        """纯 hex GUID 应归一化为小写。"""
        ref = {"pin_guid": "a1b2c3d4e5f67890abcdef1234567890"}
        result = _pin_ref_guid(ref)
        assert result == "a1b2c3d4e5f67890abcdef1234567890"

    def test_pin_ref_guid_from_string(self):
        """字符串输入应归一化为小写。"""
        result = _pin_ref_guid("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        assert result == "a1b2c3d4e5f67890abcdef1234567890"

    def test_pin_ref_guid_returns_none_for_empty(self):
        """空值返回 None。"""
        assert _pin_ref_guid({}) is None
        assert _pin_ref_guid("") is None
        assert _pin_ref_guid(None) is None

    def test_is_valid_pin_guid_accepts_32_char_hex(self):
        """接受 32 字符 hex GUID。"""
        assert _is_valid_pin_guid("A1B2C3D4E5F67890ABCDEF1234567890") is True

    def test_is_valid_pin_guid_accepts_36_char_dashed(self):
        """接受 36 字符带 dash GUID。"""
        assert _is_valid_pin_guid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890") is True

    def test_is_valid_pin_guid_accepts_lowercase_hex(self):
        """接受小写 hex GUID。"""
        assert _is_valid_pin_guid("a1b2c3d4e5f67890abcdef1234567890") is True

    def test_is_valid_pin_guid_accepts_zero_guid(self):
        """接受全零 GUID（ParentPin 空引用）。"""
        assert _is_valid_pin_guid("0" * 32) is True

    def test_is_valid_pin_guid_accepts_pin_prefix(self):
        """接受 pin- 前缀（测试 fixture）。"""
        assert _is_valid_pin_guid("pin-test-123") is True

    def test_is_valid_pin_guid_rejects_invalid(self):
        """拒绝非 hex 字符。"""
        assert _is_valid_pin_guid("not-a-valid-guid!!") is False
        assert _is_valid_pin_guid("") is False
        assert _is_valid_pin_guid(None) is False
        assert _is_valid_pin_guid("XYZ") is False

    def test_pin_ref_guid_normalized_matches_pin_lookup(self):
        """端到端测试：PinReference GUID 归一化后应匹配 pin_id。"""
        ref_guid = "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"
        pin_id = "a1b2c3d4e5f67890abcdef1234567890"
        normalized = _pin_ref_guid(ref_guid)
        assert normalized == pin_id
        assert _is_valid_pin_guid(normalized) is True


# === Pin 恢复机制测试 ===

class _TrackingArchive:

    """位置追踪 mock archive，自动管理 tell()/seek() 状态。"""

    def __init__(self, read_increment=4, file_size=1024 * 1024):
        self._pos = 0
        self._read_increment = read_increment
        self._seek_calls = []
        self._file_size = file_size

    def total_size(self):
        return self._file_size

    def _record_diagnostic(self, **kwargs):
        """记录诊断信息（mock，不做实际操作）。"""
        pass

    def tell(self):
        return self._pos

    def seek(self, pos, *args, **kwargs):
        self._seek_calls.append(pos)
        self._pos = pos

    def advance(self, n):
        """手动推进位置 n 字节。"""
        self._pos += n

    def read_i32(self, key=""):
        self._pos += 4
        return 0

    def read_u8(self, key=""):
        self._pos += 1
        return 1  # EGPD_Output

    def read_bytes(self, n, key=""):
        self._pos += n
        return b'\x00' * n

    def read(self, n=None):
        if n is None:
            n = 1
        self._pos += n
        return b'\x00' * n

    def read_name(self, name_map, key=""):
        self._pos += 8  # u32 index + u32 number
        return name_map[0] if name_map else "TestPin"

    @property
    def seek_calls(self):
        return list(self._seek_calls)


def _make_ftext_side_effect(consumed_values):
    """构造 _read_ftext_value 的 side_effect，自动推进 archive 位置。

    consumed_values: 每次调用的消耗字节数列表。
    返回 (value, flags, history_type, consumed) 元组。
    """
    call_count = [0]

    def side_effect(archive, tolerant=True):
        idx = call_count[0]
        consumed = consumed_values[idx]
        call_count[0] += 1
        # 推进 archive 位置以模拟真实消耗
        archive.advance(consumed)
        return (f"Value{idx}", 0, -1, consumed)

    return side_effect


def _make_pin_args():
    """构造 read_ue_graph_pin 的标准参数。"""
    name_map = ["TestPin"]
    summary = MagicMock()
    summary.name_map = name_map
    export_map = []
    import_map = []
    return name_map, summary, export_map, import_map


# FText 头部大小：flags(i32, 4B) + history_type(u8, 1B) = 5 字节
_FTEXT_HEADER_SIZE = 5


class TestFTextSafetyNet:
    """FText 解析安全网测试。"""

    @patch("uasset_read.serializers.graph_pin.read_pin_array", return_value=[])
    @patch("uasset_read.serializers.graph_pin.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph_pin._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph_pin._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph_pin.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph_pin._read_ftext_value")
    @pytest.mark.parametrize("large_consumption", [15000, 20000, 50000],
                             ids=["15KB", "20KB", "50KB"])
    def test_ftext_safety_net_triggers_on_large_consumption(
        self, mock_ftext, mock_pin_type, mock_fstring,
        mock_guid, mock_pin_ref, mock_pin_array,
        large_consumption,
    ):
        """验证 PinFriendlyName FText 消耗超过阈值时触发安全网，值被设为 None。"""
        assert large_consumption > MAX_FTEXT_CONSUMPTION

        archive = _TrackingArchive()
        archive.advance(20)  # OwningNode(4) + PinId(16)

        # 模拟两次 FText 调用都消耗超大值
        mock_ftext.side_effect = _make_ftext_side_effect(
            [large_consumption, large_consumption]
        )
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # 安全网应将 pin_friendly_name 设为 None
        assert result.pin_friendly_name is None
        # 安全网触发后应有 seek 回退调用
        assert len(archive.seek_calls) > 0
        # seek 回退目标应小于大消耗后的位置，证明 seek 确实回退了
        post_consumption_pos = 20 + 4 + 16 + 8 + large_consumption  # header + read ops + ftext
        assert archive.seek_calls[0] < post_consumption_pos, (
            f"安全网 seek 目标 {archive.seek_calls[0]} 应小于消耗后位置 {post_consumption_pos}"
        )
        # seek 目标应为 ftext_start_pos + 5（跳过 5 字节 FText 头部）
        # ftext_start_pos = OwningNode(4) + PinId(16) + PinName(8) = 28 加上 mock advance(20)
        # 注意：实际 ftext_start_pos 由函数内部决定，seek 应跳过头部
        assert archive.seek_calls[0] > 20, (
            f"seek 目标应大于 OwningNode+PinId 的起始位置 20"
        )

    @patch("uasset_read.serializers.graph_pin.read_pin_array", return_value=[])
    @patch("uasset_read.serializers.graph_pin.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph_pin._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph_pin._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph_pin.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph_pin._read_ftext_value")
    def test_ftext_safety_net_allows_normal_consumption(
        self, mock_ftext, mock_pin_type, mock_fstring,
        mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证 FText 安全网允许正常消耗通过，值被保留。"""
        normal_consumption = 100

        archive = _TrackingArchive()
        archive.advance(20)

        # 模拟 FText 正常消耗
        mock_ftext.side_effect = _make_ftext_side_effect(
            [normal_consumption, normal_consumption]
        )
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # 正常消耗: pin_friendly_name 应保留原值 (不是 None)
        assert result.pin_friendly_name is not None
        # 正常路径不应有 FText 安全网 seek 回退调用
        # （LinkedTo/SubPins 的 probe seek 不计入）
        # FText 安全网 seek 会 seek 到 ftext_start_pos + 5 (小于 100)
        safety_net_seeks = [s for s in archive.seek_calls if s < 100]
        assert len(safety_net_seeks) == 0

    @patch("uasset_read.serializers.graph_pin.read_pin_array", return_value=[])
    @patch("uasset_read.serializers.graph_pin.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph_pin._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph_pin._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph_pin.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph_pin._read_ftext_value")
    def test_ftext_safety_net_default_text_value(
        self, mock_ftext, mock_pin_type, mock_fstring,
        mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证 DefaultTextValue 的 FText 安全网在消耗超过 10KB 时触发。"""
        friendly_name_consumed = 50
        default_text_consumed = 15000  # 超过 10KB

        archive = _TrackingArchive()
        archive.advance(20)

        # PinFriendlyName 正常, DefaultTextValue 超大
        mock_ftext.side_effect = _make_ftext_side_effect(
            [friendly_name_consumed, default_text_consumed]
        )
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # PinFriendlyName 正常通过
        assert result.pin_friendly_name is not None
        # DefaultTextValue 安全网触发: 设为 None
        assert result.default_text_value is None

    @patch("uasset_read.serializers.graph_pin.read_pin_array", return_value=[])
    @patch("uasset_read.serializers.graph_pin.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph_pin._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph_pin._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph_pin.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph_pin._read_ftext_value")
    def test_ftext_exception_seeks_back_to_start(
        self, mock_ftext, mock_pin_type, mock_fstring,
        mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证 FText 解析抛异常时 archive seek 回到解析前位置 +5（跳过头部）。"""
        archive = _TrackingArchive()
        archive.advance(20)

        # 第一次调用 (PinFriendlyName) 抛异常
        # 第二次调用 (DefaultTextValue) 正常
        def exception_then_normal(archive, tolerant=True):
            if not hasattr(exception_then_normal, '_called'):
                exception_then_normal._called = True
                raise struct.error("FText parse error")
            archive.advance(10)
            return ("DefaultText", 0, -1, 10)

        mock_ftext.side_effect = exception_then_normal
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # 异常处理: PinFriendlyName 应为 None (显式赋值)
        assert result.pin_friendly_name is None
        # 异常分支也调用了 seek，目标为 ftext_start_pos + 5
        assert len(archive.seek_calls) > 0
        # 异常时未消耗任何字节（异常立即抛出），seek 目标应在初始位置之后
        assert archive.seek_calls[0] > 20, (
            f"异常 seek 目标应大于 OwningNode+PinId 起始位置 20, "
            f"实际为 {archive.seek_calls[0]}"
        )

    @patch("uasset_read.serializers.graph_pin.read_pin_array", return_value=[])
    @patch("uasset_read.serializers.graph_pin.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph_pin._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph_pin._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph_pin.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph_pin._read_ftext_value")
    def test_ftext_safety_net_trace_mode(
        self, mock_ftext, mock_pin_type, mock_fstring,
        mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证安全网触发时 trace_mode=True 正确执行且不崩溃。"""
        large_consumption = 15000
        normal_consumption = 50

        archive = _TrackingArchive()
        archive.advance(20)

        mock_ftext.side_effect = _make_ftext_side_effect(
            [large_consumption, normal_consumption]
        )
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        # trace_mode=True 不应导致异常或改变安全网行为
        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=True,
        )

        # 安全网触发: pin_friendly_name 应为 None（与 trace_mode=False 行为一致）
        assert result.pin_friendly_name is None
        # seek 回退仍然发生
        assert len(archive.seek_calls) > 0


class TestPinReferenceGUID:
    """PinReference GUID 格式统一测试。"""

    @pytest.mark.parametrize("raw_guid,expected", [
        ("a1b2c3d4-e5f6-7890-abcd-ef1234567890", "a1b2c3d4e5f67890abcdef1234567890"),
        ("01020304-0506-0708-090a-0b0c0d0e0f10", "0102030405060708090a0b0c0d0e0f10"),
        ("00000000-0000-0000-0000-000000000000", "0" * 32),
    ], ids=["dashed-upper", "dashed-lower", "zero-guid"])
    def test_read_pin_reference_normalizes_guid(self, raw_guid, expected):
        """验证 read_pin_reference 将各种 GUID 格式归一化为 32 字符小写 hex。"""
        fake_archive = MagicMock()
        fake_archive.read_i32.side_effect = [0, 1]

        export_map = [MagicMock(object_name="TestNode")]
        import_map = []

        with patch("uasset_read.serializers.graph_pin._read_guid", return_value=raw_guid):
            result = read_pin_reference(fake_archive, [], export_map, import_map)

        assert result is not None
        assert result["pin_guid"] == expected
        assert len(result["pin_guid"]) == 32
        assert "-" not in result["pin_guid"]

    def test_read_pin_reference_null_pointer_returns_none(self):
        """验证 b_null_ptr != 0 时返回 None（仅消耗 4 字节）。"""
        fake_archive = MagicMock()
        fake_archive.read_i32.side_effect = [1]  # b_null_ptr = 1 (非零)

        result = read_pin_reference(fake_archive, [], [], [])

        assert result is None
        # 仅调用一次 read_i32（读 b_null_ptr），不应再读更多
        assert fake_archive.read_i32.call_count == 1

    def test_read_pin_reference_negative_owning_node_uses_import_map(self):
        """验证 owning_node_index 为负数时从 import_map 解析节点名。"""
        fake_archive = MagicMock()
        # b_null=0, owning_node=-1（负索引 → import_map[0]）
        fake_archive.read_i32.side_effect = [0, -1]

        export_map = []
        import_map = [MagicMock(object_name="ImportedClass")]

        with patch("uasset_read.serializers.graph_pin._read_guid",
                    return_value="a1b2c3d4-e5f6-7890-abcd-ef1234567890"):
            result = read_pin_reference(fake_archive, [], export_map, import_map)

        assert result is not None
        assert result["owning_node"] == "ImportedClass"

    def test_read_pin_reference_out_of_bounds_export_index(self):
        """验证 owning_node_index 超出 export_map 范围时 owning_node 为 None。"""
        fake_archive = MagicMock()
        # b_null=0, owning_node=10（远超 export_map 长度 1）
        fake_archive.read_i32.side_effect = [0, 10]

        export_map = [MagicMock(object_name="OnlyNode")]
        import_map = []

        with patch("uasset_read.serializers.graph_pin._read_guid",
                    return_value="a1b2c3d4-e5f6-7890-abcd-ef1234567890"):
            result = read_pin_reference(fake_archive, [], export_map, import_map)

        assert result is not None
        assert result["owning_node"] is None

    def test_read_pin_reference_out_of_bounds_import_index(self):
        """验证负索引超出 import_map 范围时 owning_node 为 None。"""
        fake_archive = MagicMock()
        # b_null=0, owning_node=-10（远超 import_map 长度 1）
        fake_archive.read_i32.side_effect = [0, -10]

        export_map = []
        import_map = [MagicMock(object_name="OnlyImport")]

        with patch("uasset_read.serializers.graph_pin._read_guid",
                    return_value="a1b2c3d4-e5f6-7890-abcd-ef1234567890"):
            result = read_pin_reference(fake_archive, [], export_map, import_map)

        assert result is not None
        assert result["owning_node"] is None

    def test_read_pin_reference_zero_owning_node(self):
        """验证 owning_node_index 为 0 时 owning_node 为 None（既非正也非负）。"""
        fake_archive = MagicMock()
        fake_archive.read_i32.side_effect = [0, 0]

        export_map = [MagicMock(object_name="Node")]
        import_map = [MagicMock(object_name="Import")]

        with patch("uasset_read.serializers.graph_pin._read_guid",
                    return_value="a1b2c3d4-e5f6-7890-abcd-ef1234567890"):
            result = read_pin_reference(fake_archive, [], export_map, import_map)

        assert result is not None
        assert result["owning_node"] is None


class TestLinkedToRecovery:
    """LinkedTo 恢复机制测试。"""

    @patch("uasset_read.serializers.graph_pin.read_pin_array")
    @patch("uasset_read.serializers.graph_pin.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph_pin._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph_pin._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph_pin.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph_pin._read_ftext_value")
    @patch("uasset_read.serializers.graph_pin._try_recover_to_subpins")
    @patch("uasset_read.serializers.graph_pin.logger")
    def test_recover_to_subpins_result_is_used(
        self, mock_logger, mock_recover, mock_ftext, mock_pin_type, mock_fstring,
        mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证 _try_recover_to_subpins 返回值被正确使用。"""
        mock_pin_array.side_effect = struct.error("LinkedTo parse error")
        mock_recover.return_value = {
            "recovered_pos": 100,
            "count": 2,
            "recovery_type": "subpins_resync",
            "reason": "b_null!=0 null reference",
        }

        archive = _TrackingArchive()
        archive.advance(20)  # OwningNode(4) + PinId(16)

        mock_ftext.side_effect = _make_ftext_side_effect([50, 50])
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # _try_recover_to_subpins 应被调用一次
        mock_recover.assert_called_once()
        # 验证返回值被正确获取（info 日志应包含 recovery 信息）
        recovery_result = mock_recover.return_value
        assert recovery_result is not None
        assert recovery_result["recovery_type"] == "subpins_resync"
        assert recovery_result["recovered_pos"] == 100
        # 验证 logger.info 被调用且包含恢复信息
        mock_logger.info.assert_called_once()
        info_args = mock_logger.info.call_args[0]
        assert "SubPins resynced" in info_args[0]
        assert info_args[1] == 100  # recovered_pos
        assert info_args[2] == "subpins_resync"  # recovery_type

    @patch("uasset_read.serializers.graph_pin.read_pin_array")
    @patch("uasset_read.serializers.graph_pin.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph_pin._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph_pin._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph_pin.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph_pin._read_ftext_value")
    @patch("uasset_read.serializers.graph_pin._try_recover_to_subpins")
    @patch("uasset_read.serializers.graph_pin.logger")
    def test_linkedto_failure_log_dedup_with_pin_name(
        self, mock_logger, mock_recover, mock_ftext, mock_pin_type, mock_fstring,
        mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证失败日志去重包含 pin_name。"""
        mock_pin_array.side_effect = struct.error("test error")
        mock_recover.return_value = None

        archive = _TrackingArchive()
        archive.advance(20)

        mock_ftext.side_effect = _make_ftext_side_effect([50, 50])
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        # 使用 patch 清除线程局部状态
        with patch("uasset_read.serializers.graph_pin._get_thread_local") as mock_tls:
            tls_obj = MagicMock()
            tls_obj.linkedto_failure_seen = set()
            mock_tls.return_value = tls_obj

            # 第一次调用：pin_name="TestPin" — 应添加到 seen 集合
            read_ue_graph_pin(
                archive, name_map, summary, export_map, import_map,
                trace_mode=False,
            )
            # 验证三元组 key 被添加（包含 pin_name）
            assert len(tls_obj.linkedto_failure_seen) == 1
            added_key = next(iter(tls_obj.linkedto_failure_seen))
            assert len(added_key) == 3, "failure_key 应为三元组 (offset, exc_type, pin_name)"
            assert added_key[2] == "TestPin", f"第三元素应为 pin_name，实际为 {added_key[2]}"
            # 验证第一次调用时 logger.error 被调用（非去重路径）
            mock_logger.error.assert_called_once()
            error_args = mock_logger.error.call_args[0]
            assert "LinkedTo read failed at pos" in error_args[0]

    @patch("uasset_read.serializers.graph_pin.read_pin_array")
    @patch("uasset_read.serializers.graph_pin.read_pin_reference", return_value=None)
    @patch("uasset_read.serializers.graph_pin._read_guid", return_value="00000000-0000-0000-0000-000000000000")
    @patch("uasset_read.serializers.graph_pin._read_fstring_safe", return_value="")
    @patch("uasset_read.serializers.graph_pin.read_ed_graph_pin_type")
    @patch("uasset_read.serializers.graph_pin._read_ftext_value")
    @patch("uasset_read.serializers.graph_pin._try_recover_to_subpins")
    @patch("uasset_read.serializers.graph_pin._get_thread_local")
    @patch("uasset_read.serializers.graph_pin.logger")
    def test_recovery_result_none_skips_info_log(
        self, mock_logger, mock_tls, mock_recover, mock_ftext, mock_pin_type, mock_fstring,
        mock_guid, mock_pin_ref, mock_pin_array,
    ):
        """验证 _try_recover_to_subpins 返回 None 时不输出 info 日志。"""
        mock_pin_array.side_effect = struct.error("LinkedTo parse error")
        mock_recover.return_value = None  # 恢复失败

        # 提供干净的线程局部状态，确保 logger.error 不被去重跳过
        tls_obj = MagicMock()
        tls_obj.linkedto_failure_seen = set()
        mock_tls.return_value = tls_obj

        archive = _TrackingArchive()
        archive.advance(20)

        mock_ftext.side_effect = _make_ftext_side_effect([50, 50])
        mock_pin_type.return_value = MagicMock()
        name_map, summary, export_map, import_map = _make_pin_args()

        result = read_ue_graph_pin(
            archive, name_map, summary, export_map, import_map,
            trace_mode=False,
        )

        # _try_recover_to_subpins 仍应被调用
        mock_recover.assert_called_once()
        # recovery_result 为 None 时不应调用 logger.info
        mock_logger.info.assert_not_called()
        # logger.error 应被调用（异常路径，首次未去重）
        mock_logger.error.assert_called_once()


class _ByteArchive:
    """基于字节缓冲区的 mock archive，支持真实数据读取。"""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0
        self._file_size = len(data)
        self._byte_swapping = False

    def tell(self):
        return self._pos

    def seek(self, pos, *args, **kwargs):
        self._pos = pos

    def read(self, n=None):
        if n is None:
            n = 1
        start = self._pos
        end = min(start + n, len(self._data))
        self._pos = end
        return self._data[start:end]


class TestSlidingRecovery:
    """滑动恢复机制测试。"""

    def test_dynamic_scan_window_based_on_bad_count(self):
        """验证 scan_window 根据 bad_count 动态调整。

        策略：在 error_pos - 30 处放置一个合法 count=1，
        - bad_count=5 (窗口 16): 搜索范围 [184, 216], target@170 不在范围内 -> None
        - bad_count=150 (窗口 64): 搜索范围 [136, 264], target@170 在范围内 -> 找到

        缓冲区填充 0xFF 以避免误匹配（0xFF 解析为 -1，超出 0..20 范围）。
        """
        error_pos = 200
        # 在 error_pos - 30 处放置 count=1 (little-endian)
        target_offset = error_pos - 30  # 170
        buf_size = 512
        buf = bytearray(b'\xff' * buf_size)
        struct.pack_into('<i', buf, target_offset, 1)

        archive = _ByteArchive(bytes(buf))
        export_map = []

        # bad_count=5 -> scan_window stays 16, range [184, 216], target@170 不在范围内
        archive.seek(error_pos)
        result_small = _recover_pin_array_count(
            archive, error_pos, bad_count=5,
            export_map=export_map, scan_window=16,
        )
        assert result_small is None, (
            f"bad_count=5 时窗口应为 16，不应找到 offset={target_offset} 处的 count"
        )

        # bad_count=150 -> scan_window becomes 64, range [136, 264], target@170 在范围内
        archive.seek(error_pos)
        result_large = _recover_pin_array_count(
            archive, error_pos, bad_count=150,
            export_map=export_map, scan_window=16,
        )
        assert result_large is not None, (
            f"bad_count=150 时窗口应为 64，应能找到 offset={target_offset} 处的 count"
        )
        assert result_large["count"] == 1

    def test_dynamic_scan_window_medium_bad_count(self):
        """验证 bad_count 在 (20, 100] 范围时窗口为 32。

        在 error_pos - 25 处放置 count=1，
        - bad_count=5 (窗口 16): range [184, 216], target@175 不在范围内 -> None
        - bad_count=30 (窗口 32): range [168, 232], target@175 在范围内 -> 找到
        """
        error_pos = 200
        target_offset = error_pos - 25  # 175
        buf_size = 512
        buf = bytearray(b'\xff' * buf_size)
        struct.pack_into('<i', buf, target_offset, 1)

        archive = _ByteArchive(bytes(buf))
        export_map = []

        # bad_count=5 -> window=16, range [184, 216], target@175 不在范围内
        archive.seek(error_pos)
        result_none = _recover_pin_array_count(
            archive, error_pos, bad_count=5,
            export_map=export_map, scan_window=16,
        )
        assert result_none is None, (
            f"bad_count=5 时窗口应为 16，不应找到 offset={target_offset} 处的 count"
        )

        # bad_count=30 -> scan_window becomes 32, range [168, 232], target@175 在范围内
        archive.seek(error_pos)
        result = _recover_pin_array_count(
            archive, error_pos, bad_count=30,
            export_map=export_map, scan_window=16,
        )
        assert result is not None, (
            f"bad_count=30 时窗口应为 32，应能找到 offset={target_offset} 处的 count"
        )
        assert result["count"] == 1

    def test_high_confidence_recovery_validated(self):
        """验证高置信度恢复的所有 ref 都通过验证。

        在 error_pos 处放置合法 count=2 + 两个合法 PinReference 结构，
        使用 scan_window=64 确保窗口足够覆盖所有数据。
        """
        error_pos = 100
        buf_size = 300
        buf = bytearray(b'\xff' * buf_size)

        # 在 error_pos 处放置 count=2
        struct.pack_into('<i', buf, error_pos, 2)

        export_map = [MagicMock(object_name="Node0")]

        # PinRef 1: b_null=0, owning_node=0, guid=non-zero
        ref1_offset = error_pos + 4  # 104
        struct.pack_into('<i', buf, ref1_offset, 0)      # b_null = 0
        struct.pack_into('<i', buf, ref1_offset + 4, 0)  # owning_node = 0
        for i in range(16):
            buf[ref1_offset + 8 + i] = 0x01

        # PinRef 2: b_null=0, owning_node=0, guid=non-zero
        ref2_offset = ref1_offset + 24  # 128
        struct.pack_into('<i', buf, ref2_offset, 0)      # b_null = 0
        struct.pack_into('<i', buf, ref2_offset + 4, 0)  # owning_node = 0
        for i in range(16):
            buf[ref2_offset + 8 + i] = 0x02

        archive = _ByteArchive(bytes(buf))

        # 使用 scan_window=64 确保窗口覆盖 count + 2 个 PinRef (52 字节)
        archive.seek(error_pos)
        result = _recover_pin_array_count(
            archive, error_pos, bad_count=5,
            export_map=export_map, scan_window=64,
        )

        assert result is not None, "恢复应成功"
        assert result["confidence"] == "high", (
            f"两个 ref 都验证通过时置信度应为 high，实际为 {result['confidence']}"
        )
        assert result["count"] == 2

    def test_low_confidence_count_zero_without_structure(self):
        """验证 count=0 且后续无结构时置信度为 low。"""
        error_pos = 100
        buf_size = 200
        buf = bytearray(b'\xff' * buf_size)

        # 在 error_pos 处放置 count=0，后面不放合法结构（0xFF 作为垃圾数据）
        struct.pack_into('<i', buf, error_pos, 0)

        archive = _ByteArchive(bytes(buf))
        export_map = []

        archive.seek(error_pos)
        result = _recover_pin_array_count(
            archive, error_pos, bad_count=5,
            export_map=export_map, scan_window=16,
        )

        assert result is not None, "恢复应成功（兜底）"
        assert result["confidence"] == "low", (
            f"count=0 且无后续结构时置信度应为 low，实际为 {result['confidence']}"
        )
        assert result["count"] == 0
