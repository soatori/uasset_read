"""C++ 对称语义输出测试 — 验证接口、枚举、结构体、委托、复制的 C++ 生成。

覆盖范围：
1. InterfaceIR → UINTERFACE / I 前缀类
2. EnumIR → UENUM enum class
3. StructIR → USTRUCT struct
4. DelegateIR → DECLARE_DYNAMIC_DELEGATE / DECLARE_DYNAMIC_MULTICAST_DELEGATE
5. ReplicationIR → GetLifetimeReplicatedProps + OnRep 函数
"""
import pytest

from uasset_read.blueprint.interface_extractor import InterfaceIR, extract_interfaces
from uasset_read.blueprint.enum_extractor import EnumIR, EnumValueIR, extract_enums
from uasset_read.blueprint.struct_extractor import StructIR, StructFieldIR, extract_structs
from uasset_read.blueprint.delegate_extractor import DelegateIR, extract_delegates
from uasset_read.blueprint.replication_extractor import (
    ReplicatedVarIR,
    ReplicationIR,
    extract_replication,
)
from uasset_read.cpp_gen.formatters import (
    format_cpp_interfaces,
    format_cpp_enums,
    format_cpp_structs,
    format_cpp_delegates,
    format_cpp_replication,
)
from uasset_read.models.blueprint import BlueprintMetadata


class TestInterfaceExtraction:
    """接口提取测试。"""

    def test_extract_interface_from_function(self):
        """从函数的 interface_class 字段提取接口。"""
        from uasset_read.models.blueprint import BlueprintEvent
        event = BlueprintEvent(
            name="TestInterfaceFunc",
            is_interface_event=True,
            interface_class="/Script/MyModule.BPI_MyInterface",
        )
        bp = BlueprintMetadata(is_blueprint=True, functions=[], events=[event])
        interfaces = extract_interfaces(bp)
        assert len(interfaces) == 1
        assert interfaces[0].name == "IBPI_MyInterface"

    def test_extract_interface_already_has_prefix(self):
        """接口名称已有 I 前缀时不重复添加。"""
        from uasset_read.models.blueprint import BlueprintEvent
        event = BlueprintEvent(
            name="TestEvent",
            is_interface_event=True,
            interface_class="/Script/MyModule.IBPI_AlreadyI",
        )
        bp = BlueprintMetadata(is_blueprint=True, functions=[], events=[event])
        interfaces = extract_interfaces(bp)
        assert interfaces[0].name == "IBPI_AlreadyI"

    def test_extract_no_interfaces(self):
        """没有接口时返回空列表。"""
        bp = BlueprintMetadata(is_blueprint=True, functions=[], events=[])
        interfaces = extract_interfaces(bp)
        assert len(interfaces) == 0


class TestEnumExtraction:
    """枚举提取测试。"""

    def test_extract_enum_from_variable(self):
        """从 byte/enum 类型变量提取枚举引用。"""
        from uasset_read.models.blueprint import BlueprintVariable
        from uasset_read.models.core import FEdGraphPinType
        var = BlueprintVariable(
            var_name="MyEnumVar",
            var_type=FEdGraphPinType(pin_category="byte", pin_subcategory="/Script/MyModule.EMyEnum"),
        )
        bp = BlueprintMetadata(is_blueprint=True, variables=[var])
        enums = extract_enums(bp)
        assert len(enums) == 1
        assert enums[0].name == "EMyEnum"

    def test_extract_enum_already_has_prefix(self):
        """枚举名称已有 E 前缀时不重复添加。"""
        from uasset_read.models.blueprint import BlueprintVariable
        from uasset_read.models.core import FEdGraphPinType
        var = BlueprintVariable(
            var_name="MyEnumVar",
            var_type=FEdGraphPinType(pin_category="byte", pin_subcategory="/Script/MyModule.EAlreadyPrefixed"),
        )
        bp = BlueprintMetadata(is_blueprint=True, variables=[var])
        enums = extract_enums(bp)
        assert enums[0].name == "EAlreadyPrefixed"


class TestStructExtraction:
    """结构体提取测试。"""

    def test_extract_struct_from_variable(self):
        """从 struct 类型变量提取结构体引用。"""
        from uasset_read.models.blueprint import BlueprintVariable
        from uasset_read.models.core import FEdGraphPinType
        var = BlueprintVariable(
            var_name="MyStructVar",
            var_type=FEdGraphPinType(pin_category="struct", pin_subcategory="/Script/MyModule.MyStruct"),
        )
        bp = BlueprintMetadata(is_blueprint=True, variables=[var])
        structs = extract_structs(bp)
        assert len(structs) == 1
        assert structs[0].name == "FMyStruct"

    def test_extract_struct_already_has_prefix(self):
        """结构体名称已有 F 前缀时不重复添加。"""
        from uasset_read.models.blueprint import BlueprintVariable
        from uasset_read.models.core import FEdGraphPinType
        var = BlueprintVariable(
            var_name="MyStructVar",
            var_type=FEdGraphPinType(pin_category="struct", pin_subcategory="/Script/MyModule.FAlreadyPrefixed"),
        )
        bp = BlueprintMetadata(is_blueprint=True, variables=[var])
        structs = extract_structs(bp)
        assert structs[0].name == "FAlreadyPrefixed"


class TestDelegateExtraction:
    """委托提取测试。"""

    def test_extract_delegate_from_function(self):
        """从标记为 delegate 的函数提取委托。"""
        from uasset_read.models.blueprint import BlueprintFunction
        func = BlueprintFunction(
            name="MyDelegate",
            is_delegate=True,
            return_type="void",
            parameters=[],
        )
        bp = BlueprintMetadata(is_blueprint=True, functions=[func], events=[])
        delegates = extract_delegates(bp)
        assert len(delegates) == 1
        assert delegates[0].name == "FMyDelegate"

    def test_extract_multicast_delegate_from_function(self):
        """从标记为 multicast_delegate 的函数提取多播委托。"""
        from uasset_read.models.blueprint import BlueprintFunction
        func = BlueprintFunction(
            name="MyMulticastDelegate",
            is_multicast_delegate=True,
            return_type="void",
            parameters=[],
        )
        bp = BlueprintMetadata(is_blueprint=True, functions=[func], events=[])
        delegates = extract_delegates(bp)
        assert len(delegates) == 1
        assert delegates[0].is_multicast is True

    def test_extract_delegate_with_signature(self):
        """提取带签名的委托。"""
        from uasset_read.models.blueprint import BlueprintFunction, FunctionParameter
        param = FunctionParameter(name="Param1", param_type="int32")
        func = BlueprintFunction(
            name="MySigDelegate",
            is_delegate=True,
            return_type="bool",
            parameters=[param],
        )
        bp = BlueprintMetadata(is_blueprint=True, functions=[func], events=[])
        delegates = extract_delegates(bp)
        assert "bool" in delegates[0].signature
        assert "int32" in delegates[0].signature


class TestReplicationExtraction:
    """复制信息提取测试。"""

    def test_extract_replicated_variable(self):
        """提取标记为 replicated 的变量。"""
        from uasset_read.models.blueprint import BlueprintVariable
        var = BlueprintVariable(
            var_name="Health",
            is_replicated=True,
        )
        bp = BlueprintMetadata(is_blueprint=True, variables=[var])
        replication = extract_replication(bp)
        assert len(replication.replicated_vars) == 1
        assert replication.replicated_vars[0].name == "Health"

    def test_extract_on_rep_function(self):
        """提取 OnRep 函数名。"""
        from uasset_read.models.blueprint import BlueprintVariable
        var = BlueprintVariable(
            var_name="Score",
            is_replicated=True,
            rep_notify_func="OnRep_Score",
        )
        bp = BlueprintMetadata(is_blueprint=True, variables=[var])
        replication = extract_replication(bp)
        assert "OnRep_Score" in replication.on_rep_functions

    def test_extract_no_replication(self):
        """没有复制变量时返回空。"""
        bp = BlueprintMetadata(is_blueprint=True, variables=[])
        replication = extract_replication(bp)
        assert len(replication.replicated_vars) == 0
        assert len(replication.on_rep_functions) == 0


class TestCppInterfaceFormatting:
    """接口 C++ 格式化测试。"""

    def test_format_single_interface(self):
        """格式化单个接口。"""
        iface = InterfaceIR(name="BPI_Test", cpp_type="IBPI_Test")
        output = format_cpp_interfaces([iface])
        assert "UINTERFACE(Blueprintable)" in output
        assert "IBPI_Test" in output
        assert "GENERATED_BODY()" in output

    def test_format_empty_interfaces(self):
        """空列表返回空字符串。"""
        assert format_cpp_interfaces([]) == ""


class TestCppEnumFormatting:
    """枚举 C++ 格式化测试。"""

    def test_format_enum_with_values(self):
        """格式化带值的枚举。"""
        val = EnumValueIR(name="EMyValue_First", value=0)
        enum = EnumIR(name="EMyEnum", cpp_type="EMyEnum", values=[val])
        output = format_cpp_enums([enum])
        assert "UENUM(BlueprintType)" in output
        assert "enum class EMyEnum : uint8" in output
        assert "EMyValue_First" in output

    def test_format_enum_without_values(self):
        """格式化无值的枚举（使用默认值）。"""
        enum = EnumIR(name="EDefault", cpp_type="EDefault")
        output = format_cpp_enums([enum])
        assert "UMETA(DisplayName = \"Default\")" in output

    def test_format_empty_enums(self):
        """空列表返回空字符串。"""
        assert format_cpp_enums([]) == ""


class TestCppStructFormatting:
    """结构体 C++ 格式化测试。"""

    def test_format_struct_with_fields(self):
        """格式化带字段的结构体。"""
        field = StructFieldIR(name="MyField", cpp_type="float", default_value="1.0f")
        struct = StructIR(name="FMyStruct", cpp_type="FMyStruct", fields=[field])
        output = format_cpp_structs([struct])
        assert "USTRUCT(BlueprintType)" in output
        assert "struct FMyStruct" in output
        assert "UPROPERTY(BlueprintReadWrite, EditAnywhere)" in output
        assert "float MyField = 1.0f;" in output

    def test_format_struct_without_fields(self):
        """格式化无字段的结构体。"""
        struct = StructIR(name="FEmpty", cpp_type="FEmpty")
        output = format_cpp_structs([struct])
        assert "// Add fields here" in output

    def test_format_empty_structs(self):
        """空列表返回空字符串。"""
        assert format_cpp_structs([]) == ""


class TestCppDelegateFormatting:
    """委托 C++ 格式化测试。"""

    def test_format_dynamic_delegate(self):
        """格式化动态委托。"""
        delegate = DelegateIR(name="FMyDelegate", cpp_type="FMyDelegate", signature="void(int32)")
        output = format_cpp_delegates([delegate])
        assert "DECLARE_DYNAMIC_DELEGATE" in output
        assert "FMyDelegate" in output

    def test_format_multicast_delegate(self):
        """格式化多播委托。"""
        delegate = DelegateIR(name="FMyMulticast", cpp_type="FMyMulticast", is_multicast=True)
        output = format_cpp_delegates([delegate])
        assert "DECLARE_DYNAMIC_MULTICAST_DELEGATE(FMyMulticast)" in output

    def test_format_empty_delegates(self):
        """空列表返回空字符串。"""
        assert format_cpp_delegates([]) == ""


class TestCppReplicationFormatting:
    """复制 C++ 格式化测试。"""

    def test_format_replication_with_vars(self):
        """格式化带复制变量的声明。"""
        var = ReplicatedVarIR(name="Health", cpp_type="float")
        replication = ReplicationIR(replicated_vars=[var])
        output = format_cpp_replication(replication)
        assert "GetLifetimeReplicatedProps" in output
        assert "Health" in output

    def test_format_replication_with_on_rep(self):
        """格式化带 OnRep 函数的声明。"""
        replication = ReplicationIR(on_rep_functions=["OnRep_Score"])
        output = format_cpp_replication(replication)
        assert "UFUNCTION()" in output
        assert "OnRep_Score" in output

    def test_format_empty_replication(self):
        """空复制返回空字符串。"""
        empty = ReplicationIR()
        assert format_cpp_replication(empty) == ""


class TestIntegration:
    """集成测试 — 完整流程。"""

    def test_full_blueprint_to_cpp(self):
        """测试完整的蓝图元数据到 C++ 输出流程。"""
        from uasset_read.models.blueprint import BlueprintVariable, BlueprintFunction
        from uasset_read.models.core import FEdGraphPinType

        # 创建包含多种元素的 BlueprintMetadata
        var = BlueprintVariable(
            var_name="ReplicatedVar",
            var_type=FEdGraphPinType(pin_category="float"),
            is_replicated=True,
            rep_notify_func="OnRep_ReplicatedVar",
        )
        func = BlueprintFunction(
            name="MyDelegate",
            is_delegate=True,
            return_type="void",
            parameters=[],
        )
        bp = BlueprintMetadata(
            is_blueprint=True,
            variables=[var],
            functions=[func],
            events=[],
        )

        # 提取并格式化
        interfaces = extract_interfaces(bp)
        enums = extract_enums(bp)
        structs = extract_structs(bp)
        delegates = extract_delegates(bp)
        replication = extract_replication(bp)

        # 验证提取结果
        assert len(delegates) == 1
        assert len(replication.replicated_vars) == 1

        # 验证格式化输出
        delegate_output = format_cpp_delegates(delegates)
        assert "DECLARE_DYNAMIC_DELEGATE" in delegate_output

        replication_output = format_cpp_replication(replication)
        assert "GetLifetimeReplicatedProps" in replication_output
