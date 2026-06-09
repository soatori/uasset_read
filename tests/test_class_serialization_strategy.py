"""tests/test_class_serialization_strategy.py — 类序列化策略表测试。"""
import pytest
from uasset_read.parsers.class_serialization_strategy import (
    SerializationStrategy,
    CLASS_STRATEGY_TABLE,
    get_serialization_strategy,
    should_skip_class,
    is_opaque_class,
    is_uclass_derived,
    get_ue_serialize_method,
    get_ue_serialize_fidelity,
    _UCLASS_DERIVED_CLASSES,
    _UCLASS_NATIVE_CLASSES,
)


class TestSerializationStrategy:
    """SerializationStrategy 枚举测试。"""

    def test_enum_values(self):
        """枚举值正确定义。"""
        assert SerializationStrategy.FULL_SERIALIZER.value == "full_serializer"
        assert SerializationStrategy.UCLASS_NATIVE.value == "uclass_native"
        assert SerializationStrategy.TAGGED_PROPERTIES_ONLY.value == "tagged_properties_only"
        assert SerializationStrategy.OPAQUE_CLASS_PAYLOAD.value == "opaque_class_payload"
        assert SerializationStrategy.SKIP_UNSUPPORTED.value == "skip_unsupported"

    def test_enum_is_string(self):
        """枚举继承 str，可直接比较。"""
        assert isinstance(SerializationStrategy.FULL_SERIALIZER, str)
        assert SerializationStrategy.FULL_SERIALIZER == "full_serializer"


class TestClassStrategyTable:
    """CLASS_STRATEGY_TABLE 映射表测试。"""

    def test_table_not_empty(self):
        """策略表非空。"""
        assert len(CLASS_STRATEGY_TABLE) > 0

    def test_uclass_native_classes(self):
        """UClass native 类正确映射。"""
        uclass_native_classes = [
            "BlueprintGeneratedClass",
            "WidgetBlueprintGeneratedClass",
        ]
        for cls in uclass_native_classes:
            assert cls in CLASS_STRATEGY_TABLE, f"{cls} 未在策略表中"
            assert CLASS_STRATEGY_TABLE[cls] == SerializationStrategy.UCLASS_NATIVE, \
                f"{cls} 应为 UCLASS_NATIVE 策略"

    def test_tagged_properties_classes(self):
        """Tagged properties 类正确映射。"""
        tagged_classes = [
            "Function",
            "UserDefinedStruct",
            "UserDefinedEnum",
            "EdGraph",
            "EdGraphNode",
            "K2Node",
        ]
        for cls in tagged_classes:
            assert cls in CLASS_STRATEGY_TABLE, f"{cls} 未在策略表中"
            assert CLASS_STRATEGY_TABLE[cls] == SerializationStrategy.TAGGED_PROPERTIES_ONLY

    def test_opaque_classes(self):
        """Opaque payload 类正确映射。"""
        opaque_classes = [
            "StaticMesh",
            "SkeletalMesh",
            "Texture2D",
            "TextureCube",
            "Material",
            "MaterialInstanceConstant",
            "AnimSequence",
            "AnimMontage",
            "SoundWave",
            "SoundCue",
            "ParticleSystem",
            "NiagaraSystem",
        ]
        for cls in opaque_classes:
            assert cls in CLASS_STRATEGY_TABLE, f"{cls} 未在策略表中"
            assert CLASS_STRATEGY_TABLE[cls] == SerializationStrategy.OPAQUE_CLASS_PAYLOAD

    def test_skip_classes(self):
        """Skip 类正确映射。"""
        skip_classes = [
            "NiagaraGraph",
            "NiagaraScript",
            "NiagaraDataInterface",
        ]
        for cls in skip_classes:
            assert cls in CLASS_STRATEGY_TABLE, f"{cls} 未在策略表中"
            assert CLASS_STRATEGY_TABLE[cls] == SerializationStrategy.SKIP_UNSUPPORTED


class TestGetSerializationStrategy:
    """get_serialization_strategy() 函数测试。"""

    def test_known_tagged_class(self):
        """已知 tagged properties 类返回正确策略。"""
        strategy = get_serialization_strategy("BlueprintGeneratedClass")
        assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY

    def test_known_opaque_class(self):
        """已知 opaque 类返回正确策略。"""
        strategy = get_serialization_strategy("StaticMesh")
        assert strategy == SerializationStrategy.OPAQUE_CLASS_PAYLOAD

    def test_known_skip_class(self):
        """已知 skip 类返回正确策略。"""
        strategy = get_serialization_strategy("NiagaraGraph")
        assert strategy == SerializationStrategy.SKIP_UNSUPPORTED

    def test_unknown_class_defaults_to_tagged(self):
        """未知类默认返回 TAGGED_PROPERTIES_ONLY。"""
        strategy = get_serialization_strategy("UnknownCustomClass")
        assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY

    def test_empty_string(self):
        """空字符串返回默认策略。"""
        strategy = get_serialization_strategy("")
        assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY


class TestShouldSkipClass:
    """should_skip_class() 函数测试。"""

    def test_skip_class_returns_true(self):
        """Skip 类返回 True。"""
        assert should_skip_class("NiagaraGraph") is True
        assert should_skip_class("NiagaraScript") is True
        assert should_skip_class("NiagaraDataInterface") is True

    def test_opaque_class_returns_false(self):
        """Opaque 类返回 False（不是 skip，是 opaque）。"""
        assert should_skip_class("StaticMesh") is False
        assert should_skip_class("Texture2D") is False

    def test_tagged_class_returns_false(self):
        """Tagged properties 类返回 False。"""
        assert should_skip_class("BlueprintGeneratedClass") is False
        assert should_skip_class("Function") is False

    def test_unknown_class_returns_false(self):
        """未知类返回 False（默认尝试解析）。"""
        assert should_skip_class("SomeUnknownClass") is False


class TestIsOpaqueClass:
    """is_opaque_class() 函数测试。"""

    def test_opaque_class_returns_true(self):
        """Opaque 类返回 True。"""
        assert is_opaque_class("StaticMesh") is True
        assert is_opaque_class("SkeletalMesh") is True
        assert is_opaque_class("Texture2D") is True
        assert is_opaque_class("Material") is True
        assert is_opaque_class("AnimSequence") is True

    def test_skip_class_returns_false(self):
        """Skip 类返回 False（不是 opaque，是 skip）。"""
        assert is_opaque_class("NiagaraGraph") is False
        assert is_opaque_class("NiagaraScript") is False

    def test_tagged_class_returns_false(self):
        """Tagged properties 类返回 False。"""
        assert is_opaque_class("BlueprintGeneratedClass") is False
        assert is_opaque_class("Function") is False

    def test_unknown_class_returns_false(self):
        """未知类返回 False。"""
        assert is_opaque_class("SomeUnknownClass") is False


class TestStrategyConsistency:
    """策略一致性测试。"""

    def test_no_overlap_between_categories(self):
        """三个类别无重叠。"""
        tagged = {cls for cls, s in CLASS_STRATEGY_TABLE.items()
                  if s == SerializationStrategy.TAGGED_PROPERTIES_ONLY}
        opaque = {cls for cls, s in CLASS_STRATEGY_TABLE.items()
                  if s == SerializationStrategy.OPAQUE_CLASS_PAYLOAD}
        skip = {cls for cls, s in CLASS_STRATEGY_TABLE.items()
                if s == SerializationStrategy.SKIP_UNSUPPORTED}

        # 无交集
        assert len(tagged & opaque) == 0
        assert len(tagged & skip) == 0
        assert len(opaque & skip) == 0

    def test_all_entries_valid_strategy(self):
        """所有映射值均为有效策略。"""
        valid_strategies = set(SerializationStrategy)
        for cls, strategy in CLASS_STRATEGY_TABLE.items():
            assert strategy in valid_strategies, f"{cls} 映射到无效策略 {strategy}"


class TestLinkerIntegration:
    """linker.preload() 集成测试。"""

    def _create_mock_export_instance(self, class_name: str, serial_size: int = 100):
        """创建 mock export instance。"""
        from unittest.mock import MagicMock
        inst = MagicMock()
        inst.object_class = class_name
        inst.object_name = "TestObject"
        inst.serial_size = serial_size
        inst.serial_offset = 0
        inst._preloaded = False
        return inst

    def test_linker_preload_marks_skip_class_as_skipped(self):
        """SKIP_UNSUPPORTED 类在 preload 中被标记为 skipped。"""
        from uasset_read.parsers.class_serialization_strategy import (
            should_skip_class,
            is_opaque_class,
        )
        # NiagaraGraph 是 SKIP_UNSUPPORTED
        assert should_skip_class("NiagaraGraph") is True
        assert is_opaque_class("NiagaraGraph") is False

    def test_linker_preload_marks_opaque_class_as_opaque(self):
        """OPAQUE_CLASS_PAYLOAD 类在 preload 中被标记为 opaque。"""
        from uasset_read.parsers.class_serialization_strategy import (
            should_skip_class,
            is_opaque_class,
        )
        # StaticMesh 是 OPAQUE_CLASS_PAYLOAD
        assert should_skip_class("StaticMesh") is False
        assert is_opaque_class("StaticMesh") is True

    def test_linker_preload_continues_for_tagged_class(self):
        """TAGGED_PROPERTIES_ONLY 类在 preload 中继续正常解析。"""
        from uasset_read.parsers.class_serialization_strategy import (
            get_serialization_strategy,
            SerializationStrategy,
        )
        # BlueprintGeneratedClass 是 TAGGED_PROPERTIES_ONLY
        strategy = get_serialization_strategy("BlueprintGeneratedClass")
        assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY

    def test_linker_preload_defaults_for_unknown_class(self):
        """未知 class 默认使用 TAGGED_PROPERTIES_ONLY 策略。"""
        from uasset_read.parsers.class_serialization_strategy import (
            get_serialization_strategy,
            SerializationStrategy,
        )
        strategy = get_serialization_strategy("SomeUnknownClass")
        assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY


class TestIsUclassDerived:
    """is_uclass_derived() 函数测试 — SerializationControlExtensions 条件。

    UE 源码 Class.cpp:1624-1627: const bool bIsUClass = IsA<UClass>();
    只有 UClass 派生类在 UStruct::SerializeTaggedProperties() 中
    读取 SerializationControlExtensions header。
    """

    def test_uclass_derived_returns_true(self):
        """UClass 派生类返回 True。"""
        assert is_uclass_derived("BlueprintGeneratedClass") is True
        assert is_uclass_derived("WidgetBlueprintGeneratedClass") is True
        assert is_uclass_derived("Class") is True

    def test_non_uclass_returns_false(self):
        """非 UClass 类返回 False。"""
        # UStruct 子类 — 有 tagged properties 但不是 UClass
        assert is_uclass_derived("Function") is False
        assert is_uclass_derived("UserDefinedStruct") is False
        assert is_uclass_derived("UserDefinedEnum") is False
        assert is_uclass_derived("EdGraph") is False
        assert is_uclass_derived("EdGraphNode") is False
        assert is_uclass_derived("K2Node") is False

    def test_opaque_class_returns_false(self):
        """Opaque 类返回 False。"""
        assert is_uclass_derived("StaticMesh") is False
        assert is_uclass_derived("Texture2D") is False
        assert is_uclass_derived("Material") is False

    def test_skip_class_returns_false(self):
        """Skip 类返回 False。"""
        assert is_uclass_derived("NiagaraGraph") is False
        assert is_uclass_derived("NiagaraScript") is False

    def test_unknown_class_returns_false(self):
        """未知类返回 False（保守策略，不消费字节）。"""
        assert is_uclass_derived("SomeUnknownClass") is False
        assert is_uclass_derived("CustomUClass") is False

    def test_none_returns_false(self):
        """None 输入返回 False（class name 无法解析时的降级处理）。"""
        assert is_uclass_derived(None) is False

    def test_empty_string_returns_false(self):
        """空字符串返回 False。"""
        assert is_uclass_derived("") is False


class TestUclassDerivedSetConsistency:
    """UCLASS_DERIVED_CLASSES 集合一致性测试。"""

    def test_uclass_set_not_empty(self):
        """UCLASS_DERIVED_CLASSES 非空。"""
        assert len(_UCLASS_DERIVED_CLASSES) > 0

    def test_uclass_set_no_overlap_with_opaque(self):
        """UCLASS_DERIVED_CLASSES 与 opaque 类无重叠。"""
        # UCLASS_DERIVED_CLASSES 包含策略表中的类，但 opaque 类不应出现在其中
        for cls in _UCLASS_DERIVED_CLASSES:
            assert not is_opaque_class(cls), f"{cls} 不应同时在 UCLASS_DERIVED 和 opaque 中"

    def test_all_tagged_uclass_derived_are_in_uclass_set(self):
        """Tagged properties 中的 UClass 派生类在 UCLASS_DERIVED_CLASSES 中。"""
        # BlueprintGeneratedClass 和 WidgetBlueprintGeneratedClass 是 UClass 派生类
        assert "BlueprintGeneratedClass" in _UCLASS_DERIVED_CLASSES
        assert "WidgetBlueprintGeneratedClass" in _UCLASS_DERIVED_CLASSES
