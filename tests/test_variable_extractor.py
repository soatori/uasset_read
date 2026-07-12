"""VariableExtractor 缺陷修复测试。

覆盖场景：
1. parse_property_flags_to_labels: EditConst 标签生成缺陷
2. _map_property_flags: is_edit_anywhere / is_edit_instance_only 语义混淆
3. _extract_pin_type_from_property: UInt32Property 非 dict 值类型映射
4. _extract_blueprint_variable_descriptions: 组件变量缺失 is_component 标记
5. extract_blueprint_variables: CPF_InstancedReference 未参与组件检测
6. _map_pin_category_to_cpp_type: 未知类型回退
7. parse_property_flags_to_labels: 完整标志位覆盖
"""
import pytest
from unittest.mock import MagicMock

from uasset_read.models.properties import StructValue, PropertyValue
from uasset_read.models.core import FEdGraphPinType
from uasset_read.constants import (
    CPF_Edit, CPF_EditConst, CPF_BlueprintVisible, CPF_BlueprintReadOnly,
    CPF_Transient, CPF_InstancedReference, CPF_Net, CPF_SaveGame,
    CPF_BlueprintAssignable, CPF_RepNotify, CPF_Protected, CPF_ExposeOnSpawn,
    CPF_Config, CPF_Deprecated, CPF_BlueprintCallable, CPF_Interp,
)
from uasset_read.blueprint.variable_extractor import (
    _map_property_flags,
    _extract_pin_type_from_property,
    _extract_blueprint_variable_descriptions,
    _map_pin_category_to_cpp_type,
    extract_blueprint_variables,
    parse_property_flags_to_labels,
)


# ===========================================================================
# Defect 1: parse_property_flags_to_labels 缺少 EditConst 标签
# ===========================================================================

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
