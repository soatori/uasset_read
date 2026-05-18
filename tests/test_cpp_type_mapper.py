"""
测试 cpp_type_mapper 模块。

覆盖 ue_path_to_cpp_type 和 ue_package_path_to_cpp_class 函数。
"""
import pytest

from uasset_read.cpp_gen import (
    UE_TO_CPP_TYPE_MAP,
    ENGINE_CLASS_PATHS,
    ue_path_to_cpp_type,
    ue_package_path_to_cpp_class,
)


class TestUEToCppTypeMap:
    """测试 UE_TO_CPP_TYPE_MAP 字典内容。"""

    def test_map_contains_core_struct_types(self):
        """核心 ScriptStruct 类型应有映射。"""
        assert "/Script/CoreUObject.Vector" in UE_TO_CPP_TYPE_MAP
        assert UE_TO_CPP_TYPE_MAP["/Script/CoreUObject.Vector"] == "FVector"

        assert "/Script/CoreUObject.Rotator" in UE_TO_CPP_TYPE_MAP
        assert UE_TO_CPP_TYPE_MAP["/Script/CoreUObject.Rotator"] == "FRotator"

        assert "/Script/CoreUObject.Transform" in UE_TO_CPP_TYPE_MAP
        assert UE_TO_CPP_TYPE_MAP["/Script/CoreUObject.Transform"] == "FTransform"

    def test_map_contains_primitive_types(self):
        """基本类型应有映射。"""
        assert UE_TO_CPP_TYPE_MAP["float"] == "float"
        assert UE_TO_CPP_TYPE_MAP["bool"] == "bool"
        assert UE_TO_CPP_TYPE_MAP["int"] == "int32"
        assert UE_TO_CPP_TYPE_MAP["name"] == "FName"
        assert UE_TO_CPP_TYPE_MAP["text"] == "FText"
        assert UE_TO_CPP_TYPE_MAP["string"] == "FString"

    def test_map_contains_engine_class_types(self):
        """Engine 类类型应有映射。"""
        assert "/Script/Engine.SceneComponent" in UE_TO_CPP_TYPE_MAP
        assert UE_TO_CPP_TYPE_MAP["/Script/Engine.SceneComponent"] == "USceneComponent"

        assert "/Script/Engine.Character" in UE_TO_CPP_TYPE_MAP
        assert UE_TO_CPP_TYPE_MAP["/Script/Engine.Character"] == "ACharacter"

    def test_map_has_minimum_coverage(self):
        """映射字典应至少覆盖 15 个条目。"""
        assert len(UE_TO_CPP_TYPE_MAP) >= 15


class TestEngineClassPaths:
    """测试 ENGINE_CLASS_PATHS 字典内容。"""

    def test_map_contains_actor_types(self):
        """Actor 类应有正确的 A 前缀。"""
        assert ENGINE_CLASS_PATHS["/Script/Engine.Actor"] == "AActor"
        assert ENGINE_CLASS_PATHS["/Script/Engine.Pawn"] == "APawn"
        assert ENGINE_CLASS_PATHS["/Script/Engine.Character"] == "ACharacter"

    def test_map_contains_component_types(self):
        """Component 类应有正确的 U 前缀。"""
        assert ENGINE_CLASS_PATHS["/Script/Engine.ActorComponent"] == "UActorComponent"
        assert ENGINE_CLASS_PATHS["/Script/Engine.SceneComponent"] == "USceneComponent"
        assert ENGINE_CLASS_PATHS["/Script/Engine.CameraComponent"] == "UCameraComponent"

    def test_map_has_minimum_coverage(self):
        """映射字典应至少覆盖 10 个条目。"""
        assert len(ENGINE_CLASS_PATHS) >= 10


class TestUePathToCppType:
    """测试 ue_path_to_cpp_type 函数。"""

    # ---- 引用格式解析 ----

    def test_scriptstruct_quoted_format(self):
        """ScriptStruct 引用格式应正确解析。"""
        result = ue_path_to_cpp_type("ScriptStruct'CoreUObject.Vector'")
        assert result == "FVector"

    def test_class_quoted_format(self):
        """Class 引用格式应正确解析。"""
        result = ue_path_to_cpp_type("Class'Engine.SceneComponent'")
        assert result == "USceneComponent"

    def test_quoted_format_with_full_path(self):
        """带完整路径的引用格式应正确解析。"""
        result = ue_path_to_cpp_type("ScriptStruct'/Script/CoreUObject.Vector'")
        assert result == "FVector"

    # ---- 路径格式解析 ----

    def test_full_script_path(self):
        """完整 Script 路径应正确解析。"""
        result = ue_path_to_cpp_type("/Script/CoreUObject.Vector")
        assert result == "FVector"

        result = ue_path_to_cpp_type("/Script/CoreUObject.Rotator")
        assert result == "FRotator"

        result = ue_path_to_cpp_type("/Script/CoreUObject.Transform")
        assert result == "FTransform"

    def test_engine_class_path(self):
        """Engine 类路径应正确解析。"""
        result = ue_path_to_cpp_type("/Script/Engine.Character")
        assert result == "ACharacter"

        result = ue_path_to_cpp_type("/Script/Engine.SceneComponent")
        assert result == "USceneComponent"

    # ---- 基本类型解析 ----

    def test_primitive_float(self):
        """float 类型应返回 float。"""
        result = ue_path_to_cpp_type("float")
        assert result == "float"

    def test_primitive_bool(self):
        """bool 类型应返回 bool。"""
        result = ue_path_to_cpp_type("bool")
        assert result == "bool"

    def test_primitive_int(self):
        """int 类型应返回 int32。"""
        result = ue_path_to_cpp_type("int")
        assert result == "int32"

    def test_primitive_name(self):
        """name 类型应返回 FName。"""
        result = ue_path_to_cpp_type("name")
        assert result == "FName"

    def test_primitive_text(self):
        """text 类型应返回 FText。"""
        result = ue_path_to_cpp_type("text")
        assert result == "FText"

    def test_primitive_string(self):
        """string 类型应返回 FString。"""
        result = ue_path_to_cpp_type("string")
        assert result == "FString"

    # ---- 小写类型名解析 ----

    def test_lowercase_vector(self):
        """小写 vector 应转换为 FVector。"""
        result = ue_path_to_cpp_type("vector")
        assert result == "FVector"

    def test_lowercase_rotator(self):
        """小写 rotator 应转换为 FRotator。"""
        result = ue_path_to_cpp_type("rotator")
        assert result == "FRotator"

    # ---- 未知类型回退 ----

    def test_unknown_type_returns_as_is(self):
        """未知类型应返回原值。"""
        result = ue_path_to_cpp_type("UnknownType")
        assert result == "UnknownType"

    def test_unknown_path_returns_heuristic(self):
        """未知路径应应用启发式前缀。"""
        # Actor 后缀 → A 前缀
        result = ue_path_to_cpp_type("/Script/Engine.MyCustomActor")
        assert result == "AMyCustomActor"

        # Component 后缀 → U 前缀
        result = ue_path_to_cpp_type("/Script/Engine.MyCustomComponent")
        assert result == "UMyCustomComponent"

    def test_empty_string_returns_empty(self):
        """空字符串应返回空字符串。"""
        result = ue_path_to_cpp_type("")
        assert result == ""

    # ---- 综合测试 ----

    def test_plan_requirement_scriptstruct_vector(self):
        """Phase 56-01 行为测试：ScriptStruct'CoreUObject.Vector' → FVector。"""
        result = ue_path_to_cpp_type("ScriptStruct'CoreUObject.Vector'")
        assert result == "FVector"

    def test_plan_requirement_float(self):
        """Phase 56-01 行为测试：float → float。"""
        result = ue_path_to_cpp_type("float")
        assert result == "float"


class TestUePackagePathToCppClass:
    """测试 ue_package_path_to_cpp_class 函数。"""

    def test_actor_class(self):
        """Actor 类路径应返回 A 前缀类名。"""
        result = ue_package_path_to_cpp_class("/Script/Engine.Character")
        assert result == "ACharacter"

    def test_pawn_class(self):
        """Pawn 类路径应返回 APawn。"""
        result = ue_package_path_to_cpp_class("/Script/Engine.Pawn")
        assert result == "APawn"

    def test_component_class(self):
        """Component 类路径应返回 U 前缀类名。"""
        result = ue_package_path_to_cpp_class("/Script/Engine.SceneComponent")
        assert result == "USceneComponent"

    def test_game_mode_class(self):
        """GameMode 类路径应返回 AGameModeBase。"""
        result = ue_package_path_to_cpp_class("/Script/Engine.GameModeBase")
        assert result == "AGameModeBase"

    def test_unknown_actor_path(self):
        """未知 Actor 路径应应用启发式 A 前缀。"""
        result = ue_package_path_to_cpp_class("/Script/Engine.MyCustomActor")
        assert result == "AMyCustomActor"

    def test_unknown_component_path(self):
        """未知 Component 路径应应用启发式 U 前缀。"""
        result = ue_package_path_to_cpp_class("/Script/Engine.MyComponent")
        assert result == "UMyComponent"

    def test_unknown_default_path(self):
        """未知路径（非 Actor/Component）应应用默认 U 前缀。"""
        result = ue_package_path_to_cpp_class("/Script/Engine.SomeObject")
        assert result == "USomeObject"

    def test_empty_string_returns_empty(self):
        """空字符串应返回空字符串。"""
        result = ue_package_path_to_cpp_class("")
        assert result == ""

    # ---- 综合测试 ----

    def test_plan_requirement_engine_character(self):
        """Phase 56-01 行为测试：/Script/Engine.Character → ACharacter。"""
        result = ue_package_path_to_cpp_class("/Script/Engine.Character")
        assert result == "ACharacter"


class TestHeuristicPrefix:
    """测试启发式前缀判断。"""

    def test_actor_suffix_gets_a_prefix(self):
        """Actor 后缀应获得 A 前缀。"""
        assert ue_path_to_cpp_type("/Script/Engine.TestActor") == "ATestActor"
        assert ue_path_to_cpp_type("/Script/Engine.MyPawn") == "AMyPawn"
        assert ue_path_to_cpp_type("/Script/Engine.CustomCharacter") == "ACustomCharacter"

    def test_component_suffix_gets_u_prefix(self):
        """Component 后缀应获得 U 前缀。"""
        assert ue_path_to_cpp_type("/Script/Engine.TestComponent") == "UTestComponent"
        assert ue_path_to_cpp_type("/Script/Engine.MySceneComponent") == "UMySceneComponent"

    def test_unknown_without_suffix_gets_u_prefix(self):
        """无已知后缀的未知类型应获得默认 U 前缀。"""
        result = ue_path_to_cpp_type("/Script/Engine.SomeClass")
        assert result == "USomeClass"