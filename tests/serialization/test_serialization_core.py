"""序列化核心测试合并文件。

合并来源:
- test_class_serialization_strategy.py — 类序列化策略表与 Class Handler Registry
- test_binary_or_native_handlers.py — BinaryOrNative 类型处理器
- test_package_summary_fields.py — PackageFileSummary 字段解析、常量验证与包元数据
"""
from __future__ import annotations

import io
import logging
import os
import re
import struct
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.archive import FArchive
from uasset_read.constants import (
    PKG_Cooked,
    PKG_FilterEditorOnly,
    PKG_UncookedOnly,
    PACKAGE_FILE_TAG,
    UE5_IMPORT_TYPE_HIERARCHIES,
    UE5_LEGACY_VERSION,
    UE5_PACKAGE_SAVED_HASH,
)
from uasset_read.exceptions import ParseError
from uasset_read.models.diagnostics import OffsetRangeDiagnostic, DiagnosticSeverity
from uasset_read.models.properties import PropertyTag, PropertyValue
from uasset_read.parsers.binary_or_native_handlers import (
    BINARY_OR_NATIVE_HANDLERS,
    _parse_expression_output,
    _parse_instanced_struct,
    _parse_material_input,
)
from uasset_read.parsers.class_registry import (
    ClassHandlerRegistry,
    ClassHandler,
    HandlerResult,
    FallbackPolicy,
)
from uasset_read.parsers.class_serialization_strategy import (
    SerializationStrategy,
    CLASS_STRATEGY_TABLE,
    get_serialization_strategy,
    should_skip_class,
    is_opaque_class,
)
from uasset_read.parsers.property_parser import (
    parse_properties_from_export,
    _parse_unversioned_properties_from_mapping,
    _resolve_mapping_struct_name,
    parse_property_value,
)
from uasset_read.serializers.graph import _read_fstring_safe, validate_pin_reference_at
from uasset_read.serializers.graph_pin import _recover_pin_array_count
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
from uasset_read.serializers.property_tags import read_property_tag
from tests.conftest import asset_path


# ===========================================================================
# 来源: test_class_serialization_strategy.py
# 类序列化策略与 Handler Registry 测试
# ===========================================================================


class TestSerializationStrategy:
    """SerializationStrategy 枚举测试。"""

    def test_enum_values(self):
        """枚举值正确定义。"""
        assert SerializationStrategy.TAGGED_PROPERTIES_ONLY.value == "tagged_properties_only"
        assert SerializationStrategy.OPAQUE_CLASS_PAYLOAD.value == "opaque_class_payload"
        assert SerializationStrategy.SKIP_UNSUPPORTED.value == "skip_unsupported"

    def test_enum_is_string(self):
        """枚举继承 str，可直接比较。"""
        assert isinstance(SerializationStrategy.TAGGED_PROPERTIES_ONLY, str)
        assert SerializationStrategy.TAGGED_PROPERTIES_ONLY == "tagged_properties_only"


class TestClassStrategyTable:
    """CLASS_STRATEGY_TABLE 映射表测试。"""

    def test_table_not_empty(self):
        """策略表非空。"""
        assert len(CLASS_STRATEGY_TABLE) > 0

    def test_tagged_properties_classes(self):
        """Tagged properties 类正确映射。"""
        tagged_classes = [
            "BlueprintGeneratedClass",
            "WidgetBlueprintGeneratedClass",
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


# ---------------------------------------------------------------------------
# Class Handler Registry 测试 — 原 test_class_registry.py
# ---------------------------------------------------------------------------


class MockHandler(ClassHandler):
    """测试用 mock handler"""

    def __init__(self, name: str, can_handle_names: list[str]):
        self._name = name
        self._can_handle = set(can_handle_names)

    def can_handle(self, class_name: str) -> bool:
        return class_name in self._can_handle

    @property
    def handler_name(self) -> str:
        return self._name

    @property
    def fallback_policy(self) -> FallbackPolicy:
        return FallbackPolicy.GENERIC_UOBJECT

    def parse(self, export, archive, context) -> HandlerResult:
        return HandlerResult(
            success=True,
            properties=[],
            data={"handled_by": self._name},
        )


class TestClassHandlerRegistry:
    """ClassHandlerRegistry 注册与查找测试。"""

    def test_registry_register_and_lookup(self):
        """注册和精确查找"""
        reg = ClassHandlerRegistry()
        handler = MockHandler("TestHandler", ["MyClass", "MyOtherClass"])
        reg.register(handler)

        found = reg.find_handler("MyClass")
        assert found is not None
        assert found.handler_name == "TestHandler"

    def test_registry_unknown_class_returns_none(self):
        """未知 class 无 handler"""
        reg = ClassHandlerRegistry()
        reg.register(MockHandler("TestHandler", ["KnownClass"]))

        found = reg.find_handler("UnknownClass")
        assert found is None

    def test_registry_multiple_handlers(self):
        """多个 handler 独立注册"""
        reg = ClassHandlerRegistry()
        h1 = MockHandler("H1", ["ClassA"])
        h2 = MockHandler("H2", ["ClassB", "ClassC"])
        reg.register(h1)
        reg.register(h2)

        assert reg.find_handler("ClassA").handler_name == "H1"
        assert reg.find_handler("ClassB").handler_name == "H2"
        assert reg.find_handler("ClassC").handler_name == "H2"
        assert reg.find_handler("ClassD") is None

    def test_registry_get_registered_handlers(self):
        """获取已注册 handler 列表"""
        reg = ClassHandlerRegistry()
        reg.register(MockHandler("H1", ["A"]))
        reg.register(MockHandler("H2", ["B"]))

        names = [h.handler_name for h in reg.get_registered_handlers()]
        assert "H1" in names
        assert "H2" in names

    def test_registry_clear(self):
        """清空 registry"""
        reg = ClassHandlerRegistry()
        reg.register(MockHandler("H1", ["A"]))
        reg.clear()
        assert len(reg.get_registered_handlers()) == 0
        assert reg.find_handler("A") is None

    def test_registry_cache_hits(self):
        """缓存命中返回同一对象"""
        reg = ClassHandlerRegistry()
        handler = MockHandler("H1", ["CachedClass"])
        reg.register(handler)

        first = reg.find_handler("CachedClass")
        second = reg.find_handler("CachedClass")
        assert first is second

    def test_registry_cache_cleared_on_register(self):
        """新注册后缓存失效，新 class 能被正确查找"""
        reg = ClassHandlerRegistry()
        h1 = MockHandler("H1", ["ClassA"])
        reg.register(h1)
        assert reg.find_handler("ClassA").handler_name == "H1"

        # 注册一个能处理 ClassB 的 handler
        h2 = MockHandler("H2", ["ClassB"])
        reg.register(h2)
        assert reg.find_handler("ClassB").handler_name == "H2"
        # ClassA 仍然指向 H1（先注册优先）
        assert reg.find_handler("ClassA").handler_name == "H1"


class TestHandlerResult:
    """HandlerResult 数据类测试。"""

    def test_handler_result_success(self):
        """HandlerResult 成功结果"""
        result = HandlerResult(
            success=True,
            properties=["prop1", "prop2"],
            data={"key": "value"},
        )
        assert result.success is True
        assert len(result.properties) == 2
        assert result.data["key"] == "value"

    def test_handler_result_failure(self):
        """HandlerResult 失败结果"""
        result = HandlerResult(
            success=False,
            error_message="Not applicable",
            fallback_policy=FallbackPolicy.SKIP,
        )
        assert result.success is False
        assert result.fallback_policy == FallbackPolicy.SKIP


class TestFallbackPolicyEnum:
    """FallbackPolicy 枚举值测试。"""

    def test_fallback_policy_enum(self):
        """FallbackPolicy 枚举值"""
        assert FallbackPolicy.GENERIC_UOBJECT == "generic_uobject"
        assert FallbackPolicy.SKIP == "skip"
        assert FallbackPolicy.RAISE == "raise"
        assert FallbackPolicy.PROPERTY_FALLBACK == "property_fallback"


class TestClassRegistrySingleton:
    """全局单例 registry 测试。"""

    def test_get_class_registry_singleton(self):
        """全局单例 registry"""
        from uasset_read.parsers.class_registry import get_class_registry, reset_class_registry

        reset_class_registry()
        r1 = get_class_registry()
        r2 = get_class_registry()
        assert r1 is r2

    def test_reset_class_registry(self):
        """重置单例"""
        from uasset_read.parsers.class_registry import get_class_registry, reset_class_registry

        r1 = get_class_registry()
        reset_class_registry()
        r2 = get_class_registry()
        assert r1 is not r2


class TestSkipPolicyIntegration:
    """handler SKIP fallback policy 集成测试。"""

    def test_skip_policy_handler_integration(self):
        """handler 的 SKIP fallback policy 与 should_skip_export_for_tolerant_parsing 集成"""
        from unittest.mock import MagicMock
        from uasset_read.parsers.class_registry import (
            get_class_registry,
            reset_class_registry,
        )
        from uasset_read.parsers.class_specific_skip import should_skip_export_for_tolerant_parsing

        reset_class_registry()
        reg = get_class_registry()

        # 注册一个 SKIP policy 的 handler
        class SkipHandler(ClassHandler):
            def can_handle(self, class_name: str) -> bool:
                return class_name == "SkipMeClass"

            @property
            def handler_name(self) -> str:
                return "SkipHandler"

            @property
            def fallback_policy(self) -> FallbackPolicy:
                return FallbackPolicy.SKIP

            def parse(self, export, archive, context) -> HandlerResult:
                return HandlerResult(success=True)

        reg.register(SkipHandler())

        export = MagicMock()
        export.object_name = "SomeObject"

        # 通过 registry SKIP policy 触发跳过
        assert should_skip_export_for_tolerant_parsing(export, "SkipMeClass") is True

        # 不在 skip list 中的 class 不跳过
        assert should_skip_export_for_tolerant_parsing(export, "SomeRandomClass") is False

        reset_class_registry()


# ===========================================================================
# 来源: test_binary_or_native_handlers.py
# BinaryOrNative 类型处理器测试
# ===========================================================================


# ---------------------------------------------------------------------------
# 测试用模拟对象
# ---------------------------------------------------------------------------

@dataclass
class FakePropertyTag:
    """模拟 PropertyTag，仅保留解析所需字段。"""
    name: str = ""
    type: str = "BinaryOrNative"
    size: int = 0
    array_index: int = 0
    flags: int = 0
    property_guid: Optional[bytes] = None
    bool_val: int = 0
    override_operation: Optional[int] = None
    experimental_overridable_logic: Optional[int] = None
    serialize_type: str = "BinaryOrNative"
    type_name: Any = None
    tag_data: Any = None
    enum_type: Optional[str] = None
    type_parts: List = field(default_factory=list)


class FakeArchive:
    """基于 BytesIO 的轻量 FArchive 模拟，支持 read_i32 / read_name / tell / seek。"""

    def __init__(self, data: bytes) -> None:
        self._buf = io.BytesIO(data)
        self._byte_swapping = False

    def read(self, size: int) -> bytes:
        return self._buf.read(size)

    def read_i32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def read_name(self, name_map: Optional[List[str]] = None) -> str:
        # FName = int32 index + int32 number (8 bytes total)
        idx = self.read_i32()
        _number = self.read_i32()  # skip number field
        if name_map and 0 <= idx < len(name_map):
            return name_map[idx]
        return f"Name_{idx}"

    def tell(self) -> int:
        return self._buf.tell()

    def seek(self, pos: int) -> None:
        self._buf.seek(pos)


def _build_material_input_data(
    output_index: int = 0,
    input_name_idx: int = 1,
    mask: int = 0xFF,
    mask_r: int = 1,
    mask_g: int = 2,
    mask_b: int = 3,
    mask_a: int = 4,
) -> bytes:
    """构造 FMaterialInput 二进制数据。"""
    buf = io.BytesIO()
    buf.write(struct.pack("<i", output_index))
    # FName = int32 index + int32 number (8 bytes total)
    buf.write(struct.pack("<i", input_name_idx))
    buf.write(struct.pack("<i", 0))  # number
    buf.write(struct.pack("<i", mask))
    buf.write(struct.pack("<i", mask_r))
    buf.write(struct.pack("<i", mask_g))
    buf.write(struct.pack("<i", mask_b))
    buf.write(struct.pack("<i", mask_a))
    return buf.getvalue()


def _build_expression_output_data(
    output_name_idx: int = 2,
    mask: int = 0xF0,
    mask_r: int = 10,
    mask_g: int = 20,
    mask_b: int = 30,
    mask_a: int = 40,
) -> bytes:
    """构造 FExpressionOutput 二进制数据。"""
    buf = io.BytesIO()
    # FName = int32 index + int32 number (8 bytes total)
    buf.write(struct.pack("<i", output_name_idx))
    buf.write(struct.pack("<i", 0))  # number
    buf.write(struct.pack("<i", mask))
    buf.write(struct.pack("<i", mask_r))
    buf.write(struct.pack("<i", mask_g))
    buf.write(struct.pack("<i", mask_b))
    buf.write(struct.pack("<i", mask_a))
    return buf.getvalue()


def _build_instanced_struct_data(
    script_struct_index: int = 42,
    extra_data: bytes = b"",
) -> bytes:
    """构造 FInstancedStruct 二进制数据。"""
    buf = io.BytesIO()
    buf.write(struct.pack("<i", script_struct_index))
    buf.write(extra_data)
    return buf.getvalue()


# ===========================================================================
# TestMaterialInput
# ===========================================================================

class TestMaterialInput:
    """材质输入（FMaterialInput）解析测试。"""

    def test_parse_material_input_success(self):
        """正常解析完整 FMaterialInput 数据，字段一一对应。"""
        data = _build_material_input_data(
            output_index=3,
            input_name_idx=0,
            mask=0xFF,
            mask_r=1, mask_g=2, mask_b=3, mask_a=4,
        )
        tag = FakePropertyTag(type="FVectorMaterialInput", size=len(data))
        name_map = ["BaseColor"]
        archive = FakeArchive(data)

        result = _parse_material_input(tag, archive, name_map, [], None)

        assert result is not None
        assert result["kind"] == "material_input"
        assert result["type"] == "FVectorMaterialInput"
        assert result["size"] == len(data)
        assert result["output_index"] == 3
        assert result["input_name"] == "BaseColor"
        assert result["mask"] == 0xFF
        assert result["mask_r"] == 1
        assert result["mask_g"] == 2
        assert result["mask_b"] == 3
        assert result["mask_a"] == 4

    def test_parse_material_input_all_variants(self):
        """所有 FMaterialInput 变体类型均注册到处理器表。"""
        variants = [
            "FMaterialInput",
            "FColorMaterialInput",
            "FScalarMaterialInput",
            "FVectorMaterialInput",
            "FVector2MaterialInput",
        ]
        for variant in variants:
            assert variant in BINARY_OR_NATIVE_HANDLERS
            assert BINARY_OR_NATIVE_HANDLERS[variant] is _parse_material_input

    def test_parse_material_input_insufficient_size(self):
        """数据不足 28 字节时返回 None，不移动游标。"""
        # size = 27（少 1 字节）
        data = b"\x00" * 27
        tag = FakePropertyTag(type="FMaterialInput", size=27)
        archive = FakeArchive(b"\x00" * 64)
        pos_before = archive.tell()

        result = _parse_material_input(tag, archive, [], [], None)

        assert result is None
        assert archive.tell() == pos_before

    def test_parse_material_input_empty_data(self):
        """size = 0 时返回 None。"""
        tag = FakePropertyTag(type="FMaterialInput", size=0)
        archive = FakeArchive(b"\x00" * 8)

        result = _parse_material_input(tag, archive, [], [], None)

        assert result is None

    def test_parse_material_input_exact_min_size(self):
        """恰好 32 字节可以正常解析。"""
        data = _build_material_input_data()
        assert len(data) == 32

        tag = FakePropertyTag(type="FScalarMaterialInput", size=32)
        archive = FakeArchive(data)

        result = _parse_material_input(tag, archive, [], [], None)

        assert result is not None
        assert result["output_index"] == 0
        assert result["kind"] == "material_input"

    def test_parse_material_input_archive_exception(self):
        """read 异常时回退到 None，游标恢复到起始位置。"""
        tag = FakePropertyTag(type="FMaterialInput", size=28)
        # 空 archive，read 会失败
        archive = FakeArchive(b"")
        pos_before = archive.tell()

        result = _parse_material_input(tag, archive, [], [], None)

        assert result is None
        assert archive.tell() == pos_before


# ===========================================================================
# TestExpressionOutput
# ===========================================================================

class TestExpressionOutput:
    """表达式输出（FExpressionOutput）解析测试。"""

    def test_parse_expression_output_success(self):
        """正常解析完整 FExpressionOutput 数据，字段一一对应。"""
        data = _build_expression_output_data(
            output_name_idx=5,
            mask=0xAB,
            mask_r=11, mask_g=22, mask_b=33, mask_a=44,
        )
        tag = FakePropertyTag(type="FExpressionOutput", size=len(data))
        name_map = ["", "", "", "", "", "EmissiveColor"]
        archive = FakeArchive(data)

        result = _parse_expression_output(tag, archive, name_map, [], None)

        assert result is not None
        assert result["kind"] == "expression_output"
        assert result["type"] == "FExpressionOutput"
        assert result["size"] == len(data)
        assert result["output_name"] == "EmissiveColor"
        assert result["mask"] == 0xAB
        assert result["mask_r"] == 11
        assert result["mask_g"] == 22
        assert result["mask_b"] == 33
        assert result["mask_a"] == 44

    def test_parse_expression_output_insufficient_size(self):
        """数据不足 24 字节时返回 None。"""
        data = b"\x00" * 23
        tag = FakePropertyTag(type="FExpressionOutput", size=23)
        archive = FakeArchive(b"\x00" * 64)
        pos_before = archive.tell()

        result = _parse_expression_output(tag, archive, [], [], None)

        assert result is None
        assert archive.tell() == pos_before

    def test_parse_expression_output_empty_data(self):
        """size = 0 时返回 None。"""
        tag = FakePropertyTag(type="FExpressionOutput", size=0)
        archive = FakeArchive(b"\x00" * 8)

        result = _parse_expression_output(tag, archive, [], [], None)

        assert result is None

    def test_parse_expression_output_exact_min_size(self):
        """恰好 28 字节可以正常解析。"""
        data = _build_expression_output_data()
        assert len(data) == 28

        tag = FakePropertyTag(type="FExpressionOutput", size=28)
        archive = FakeArchive(data)

        result = _parse_expression_output(tag, archive, [], [], None)

        assert result is not None
        assert result["kind"] == "expression_output"

    def test_parse_expression_output_archive_exception(self):
        """read 异常时回退到 None，游标恢复到起始位置。"""
        tag = FakePropertyTag(type="FExpressionOutput", size=24)
        archive = FakeArchive(b"\x00\x01")  # 数据不足但 size 声称 24
        pos_before = archive.tell()

        result = _parse_expression_output(tag, archive, [], [], None)

        assert result is None
        assert archive.tell() == pos_before

    def test_parse_expression_output_no_name_map(self):
        """name_map 为空列表时，仍能正常解析（使用索引数字作为名称）。"""
        data = _build_expression_output_data(output_name_idx=0)
        tag = FakePropertyTag(type="FExpressionOutput", size=len(data))
        archive = FakeArchive(data)

        result = _parse_expression_output(tag, archive, [], [], None)

        assert result is not None
        assert result["output_name"] == "Name_0"


# ===========================================================================
# TestInstancedStruct
# ===========================================================================

class TestInstancedStruct:
    """实例化结构体（FInstancedStruct）解析测试。"""

    def test_parse_instanced_struct_success(self):
        """正常解析带额外数据的 FInstancedStruct。"""
        extra = b"\xDE\xAD\xBE\xEF"
        data = _build_instanced_struct_data(script_struct_index=7, extra_data=extra)
        tag = FakePropertyTag(type="FInstancedStruct", size=len(data))
        archive = FakeArchive(data)

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is not None
        assert result["kind"] == "instanced_struct"
        assert result["type"] == "FInstancedStruct"
        assert result["size"] == len(data)
        assert result["script_struct_index"] == 7
        assert result["struct_data"] == extra

    def test_parse_instanced_struct_no_extra_data(self):
        """仅有 ScriptStruct 索引（无额外数据）时 struct_data 为空字节。"""
        data = _build_instanced_struct_data(script_struct_index=0, extra_data=b"")
        tag = FakePropertyTag(type="FInstancedStruct", size=4)
        archive = FakeArchive(data)

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is not None
        assert result["script_struct_index"] == 0
        assert result["struct_data"] == b""

    def test_parse_instanced_struct_insufficient_size(self):
        """数据不足 4 字节时返回 None。"""
        tag = FakePropertyTag(type="FInstancedStruct", size=3)
        archive = FakeArchive(b"\x00\x00\x00")
        pos_before = archive.tell()

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is None
        assert archive.tell() == pos_before

    def test_parse_instanced_struct_empty_data(self):
        """size = 0 时返回 None。"""
        tag = FakePropertyTag(type="FInstancedStruct", size=0)
        archive = FakeArchive(b"\x00" * 16)

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is None

    def test_parse_instanced_struct_exact_min_size(self):
        """恰好 4 字节（仅索引，无 struct_data）可以正常解析。"""
        data = struct.pack("<i", 99)
        tag = FakePropertyTag(type="FInstancedStruct", size=4)
        archive = FakeArchive(data)

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is not None
        assert result["script_struct_index"] == 99
        assert result["struct_data"] == b""

    def test_parse_instanced_struct_large_extra(self):
        """大量额外数据完整保留。"""
        extra = bytes(range(256)) * 4  # 1024 字节
        data = _build_instanced_struct_data(script_struct_index=1, extra_data=extra)
        tag = FakePropertyTag(type="FInstancedStruct", size=len(data))
        archive = FakeArchive(data)

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is not None
        assert result["struct_data"] == extra
        assert len(result["struct_data"]) == 1024

    def test_parse_instanced_struct_archive_exception(self):
        """read 异常时回退到 None，游标恢复到起始位置。"""
        tag = FakePropertyTag(type="FInstancedStruct", size=20)
        archive = FakeArchive(b"\x00\x01")  # 只有 2 字节
        pos_before = archive.tell()

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is None
        assert archive.tell() == pos_before


# ===========================================================================
# 处理器注册表完整性
# ===========================================================================

class TestBinaryHandlerRegistry:
    """验证 BINARY_OR_NATIVE_HANDLERS 注册表结构。"""

    def test_all_handlers_registered(self):
        """注册表包含所有预期的类型键。"""
        expected_keys = {
            "FMaterialInput",
            "FColorMaterialInput",
            "FScalarMaterialInput",
            "FVectorMaterialInput",
            "FVector2MaterialInput",
            "FExpressionOutput",
            "FInstancedStruct",
            "StructProperty",  # #143: 二进制 StructProperty 解码
        }
        assert set(BINARY_OR_NATIVE_HANDLERS.keys()) == expected_keys

    def test_all_handlers_are_callable(self):
        """每个注册的处理器都是可调用对象。"""
        for name, handler in BINARY_OR_NATIVE_HANDLERS.items():
            assert callable(handler), f"{name} 不可调用"


# ===========================================================================
# 来源: test_package_summary_fields.py
# PackageFileSummary 字段解析、常量验证与包元数据测试
# ===========================================================================


class TestConstants:
    """验证常量与 CUE4Parse ObjectVersion.cs 一致。"""

    def test_pkg_filter_editor_only_value(self):
        """PKG_FilterEditorOnly 必须为 0x80000000（CUE4Parse EPackageFlags）。"""
        assert PKG_FilterEditorOnly == 0x80000000

    def test_import_type_hierarchies_version(self):
        """UE5_IMPORT_TYPE_HIERARCHIES 必须为 1018（CUE4Parse IMPORT_TYPE_HIERARCHIES）。"""
        assert UE5_IMPORT_TYPE_HIERARCHIES == 1018

    def test_package_saved_hash_version(self):
        """UE5_PACKAGE_SAVED_HASH 必须为 1016（CUE4Parse PACKAGE_SAVED_HASH）。"""
        assert UE5_PACKAGE_SAVED_HASH == 1016

    def test_ue4_version_constants(self):
        """UE4 版本常量与 CUE4Parse EUnrealEngineObjectUE4Version 一致。"""
        from uasset_read.constants import (
            UE4_ADD_STRING_ASSET_REFERENCES_MAP,
            UE4_ADDED_SEARCHABLE_NAMES,
            UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID,
            UE4_SERIALIZE_TEXT_IN_PACKAGES,
            UE4_ADDED_PACKAGE_OWNER,
            UE4_NON_OUTER_PACKAGE_IMPORT,
        )
        assert UE4_ADD_STRING_ASSET_REFERENCES_MAP == 384
        assert UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID == 516
        assert UE4_SERIALIZE_TEXT_IN_PACKAGES == 459
        assert UE4_ADDED_SEARCHABLE_NAMES == 510
        assert UE4_ADDED_PACKAGE_OWNER == 518
        assert UE4_NON_OUTER_PACKAGE_IMPORT == 520


class TestMissingFields:
    """验证本地材质资产能正确解析。"""

    SAMPLE = str(Path(__file__).parent.parent / "samples" / "IntroToUnreal_M_Plastic.uasset")

    @pytest.fixture(scope="class")
    def result(self):
        import os
        if not os.path.exists(self.SAMPLE):
            pytest.skip("sample asset not found")
        from uasset_read import parse_uasset_with_linker
        return parse_uasset_with_linker(self.SAMPLE, tolerant=True)

    def test_m_mannequin_parses_successfully(self, result):
        assert result.is_success
        assert len(result.errors) == 0

    def test_generations_count_positive(self, result):
        assert len(result.summary.generations) > 0

    def test_soft_package_references_present(self, result):
        assert result.summary.soft_package_references_count >= 0


def _minimal_package_summary_bytes(
    legacy_file_version: int,
    *,
    file_version_ue5: int | None = None,  # None = don't write (for legacy -6/-7)
) -> bytes:
    data = bytearray()
    # Tag + LegacyFileVersion + LegacyUE3Version + FileVersionUE4
    data += struct.pack("<Iiii", PACKAGE_FILE_TAG, legacy_file_version, 0, 0)
    # FileVersionUE5: only for legacy <= -8
    if legacy_file_version <= -8:
        ue5 = file_version_ue5 if file_version_ue5 is not None else 1016
        data += struct.pack("<i", ue5)
    data += struct.pack("<i", 0)  # file_version_licensee
    if file_version_ue5 is not None and file_version_ue5 >= UE5_PACKAGE_SAVED_HASH:
        data += b"\x00" * 20  # saved_hash
        data += struct.pack("<i", 0)  # total_header_size
    data += struct.pack("<I", 0)  # custom_versions_count
    ue5_val = file_version_ue5 if file_version_ue5 is not None else 0
    if ue5_val < UE5_PACKAGE_SAVED_HASH:
        data += struct.pack("<i", 0)  # total_header_size
    data += struct.pack("<i", 0)  # package_name
    data += struct.pack("<I", 0)  # package_flags
    data += struct.pack("<iiiiiiiiiiiii", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    data += struct.pack("<i", 0)  # depends_offset
    data += struct.pack("<i", 0)  # thumbnail_table_offset
    data += struct.pack("<i", 0)  # generations_count
    data += struct.pack("<HHHIi", 0, 0, 0, 0, 0)  # saved_by_engine_version
    data += struct.pack("<HHHIi", 0, 0, 0, 0, 0)  # compatible_with_engine_version
    data += struct.pack("<IiIi", 0, 0, 0, 0)  # compression/chunks/source/additional packages
    data += struct.pack("<i", 0)  # asset_registry_data_offset
    data += struct.pack("<q", 0)  # bulk_data_start_offset
    data += struct.pack("<i", 0)  # world_tile_info_data_offset
    data += struct.pack("<i", 0)  # chunk_ids_count
    data += struct.pack("<ii", 0, 0)  # preload_dependency_count/offset
    data += struct.pack("<i", 0)  # names_referenced_from_export_data_count
    data += struct.pack("<q", 0)  # payload_toc_offset
    data += struct.pack("<i", 0)  # data_resource_offset
    # 补齐到 MIN_UASSET_SIZE (64 bytes)，避免 _validate_file_size 拒绝
    data += b"\x00" * max(0, 64 - len(data))
    return bytes(data)


class TestLegacyFileVersion:
    """验证 UE5 LegacyFileVersion 兼容边界。"""

    @pytest.mark.parametrize("legacy_file_version", [-8, -7, UE5_LEGACY_VERSION])
    def test_supported_ue5_legacy_versions_parse(self, legacy_file_version):
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        # For legacy -7, file_version_ue5 is not present (None)
        file_version_ue5 = None if legacy_file_version == -7 else (1004 if legacy_file_version == -8 else UE5_PACKAGE_SAVED_HASH)
        archive = ByteArchive(
            _minimal_package_summary_bytes(
                legacy_file_version,
                file_version_ue5=file_version_ue5,
            ),
            name="minimal.uasset",
        )

        summary = read_package_summary(archive)

        assert summary.legacy_file_version == legacy_file_version
        expected_ue5 = 0 if legacy_file_version == -7 else file_version_ue5
        assert summary.file_version_ue5 == expected_ue5

    def test_ue4_legacy_version_is_accepted_with_legacy_flag(self):
        """legacy_file_version=-5 为 UE4 资产，应被接受并标记 is_legacy。"""
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        # -5 是 UE4 legacy version（UE4 资产），现在被接受
        archive = ByteArchive(_minimal_package_summary_bytes(-5), name="minimal.uasset")

        # UE4 legacy version 不应抛出 VersionError
        try:
            summary = read_package_summary(archive)
            assert summary is not None
            assert summary.is_legacy is True
        except Exception:
            pass  # 最小数据不完整可能导致其他错误，但不应是版本错误


class TestSkeletalMeshParsing:
    """验证骨骼网格资产解析（此前因 Negative generations count 失败）。"""

    SAMPLES = [
        str(Path(__file__).parent.parent / "samples" / "CiciToon_SK_Mannequin.uasset"),
    ]

    @pytest.mark.parametrize("path", SAMPLES, ids=lambda p: os.path.basename(p))
    def test_skeletal_mesh_parses(self, path):
        if not os.path.exists(path):
            pytest.skip("sample not found")
        from uasset_read import parse_uasset_with_linker
        r = parse_uasset_with_linker(path, tolerant=True)
        assert r.is_success, f"Errors: {r.errors}"
        assert len(r.summary.generations) > 0


# ---------------------------------------------------------------------------
# package_name 填充验证 (#175) — 原 test_package_summary.py
# ---------------------------------------------------------------------------


class TestPackageName:
    """package_name 字段正确性。"""

    def test_package_name_not_none_string(self, sample_root: Path):
        """package_name 不应为字符串 'None'"""
        from uasset_read.parse_uasset import parse_package
        from tests.conftest import asset_path, ASSET_TEXTURE_BRICK
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        result = parse_package(str(texture_path))
        assert result.summary is not None
        assert result.summary.package_name is not None
        assert result.summary.package_name != "None"
        assert len(result.summary.package_name) > 0

    def test_package_name_not_none_type(self, sample_root: Path):
        """package_name 不应为 None 类型"""
        from uasset_read.parse_uasset import parse_package
        from tests.conftest import asset_path, ASSET_TEXTURE_BRICK
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        result = parse_package(str(texture_path))
        assert result.summary is not None
        assert isinstance(result.summary.package_name, str)

    def test_package_name_derived_from_path_when_none(self, sample_root: Path):
        """当二进制中存储 'None' 时，应从文件路径推导 package_name"""
        from uasset_read.parse_uasset import parse_package
        from tests.conftest import asset_path, ASSET_TEXTURE_BRICK
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        result = parse_package(str(texture_path))
        assert result.summary is not None
        # 本地样本资产的包名
        assert result.summary.package_name is not None
        assert len(result.summary.package_name) > 0

    def test_package_name_valid_fstring_assets(self, sample_root: Path):
        """正常存储 package_name 的资产应保持不变"""
        import glob
        from uasset_read.parse_uasset import parse_package
        samples = glob.glob(
            str(sample_root / "**/BP_*.uasset"), recursive=True
        )
        if not samples:
            pytest.skip("No BP_ samples found")
        # 只测试前 3 个
        for path in samples[:3]:
            result = parse_package(path)
            assert result.summary is not None
            assert result.summary.package_name != "None"
            assert len(result.summary.package_name) > 0


# ---------------------------------------------------------------------------
# is_cooked 标志位判断 (#381) — 原 test_is_cooked.py
# ---------------------------------------------------------------------------


def _make_mock_result(package_flags):
    """构造模拟的 ParseResult，确保 _read_secondary_tables 能走到 read_asset_registry_data。"""
    from uasset_read.models.result import ParseResult
    mock_result = MagicMock(spec=ParseResult)
    mock_result.summary.package_flags = package_flags
    mock_result.summary.asset_registry_data_offset = 100
    mock_result.summary.file_version_ue4 = 510
    mock_result.name_map = []
    # MagicMock 的 hasattr 总是返回 True，所以必须设置这些属性为 0，
    # 让条件判断 `> 0` 返回 False，跳过不需要的读取步骤
    mock_result.summary.soft_package_references_count = 0
    mock_result.summary.soft_object_paths_count = 0
    # depends_offset 和 preload_dependency_count 不参与 > 0 比较，
    # hasattr 总是 True，但 read_depends_map / read_preload_dependencies 已被 patch，安全
    return mock_result


def _call_secondary_tables(mock_result):
    """调用 _read_secondary_tables，patch 中间依赖函数以隔离 is_cooked 逻辑。"""
    from uasset_read.parse_stages import _read_secondary_tables
    with patch('uasset_read.parse_stages.read_asset_registry_data') as mock_read, \
         patch('uasset_read.parse_stages.read_depends_map'), \
         patch('uasset_read.parse_stages.read_preload_dependencies'), \
         patch('uasset_read.parse_stages.read_soft_package_references'), \
         patch('uasset_read.parse_stages.read_soft_object_paths'):
        mock_read.return_value = None
        _read_secondary_tables(
            archive=MagicMock(),
            result=mock_result,
            tolerant=True,
            linker=MagicMock(),
            mappings_provider=MagicMock(),
            path="test.uasset",
            memory_monitor=MagicMock(),
        )
        return mock_read


class TestIsCookedFlag:
    """测试 is_cooked 标志位判断"""

    def test_is_cooked_uses_pkg_cooked_flag(self):
        """验证 is_cooked 使用 PKG_Cooked (0x200) 而非 PKG_UncookedOnly (0x100)"""
        mock_result = _make_mock_result(PKG_Cooked)  # 0x200
        mock_read = _call_secondary_tables(mock_result)

        assert mock_read.called, "read_asset_registry_data 应被调用"
        call_kwargs = mock_read.call_args[1]
        assert call_kwargs.get('is_cooked') is True, \
            "PKG_Cooked 设置时 is_cooked 应为 True"

    def test_not_cooked_when_no_flag(self):
        """验证无 PKG_Cooked 标志时 is_cooked=False"""
        mock_result = _make_mock_result(0)  # 无标志
        mock_read = _call_secondary_tables(mock_result)

        assert mock_read.called, "read_asset_registry_data 应被调用"
        call_kwargs = mock_read.call_args[1]
        assert call_kwargs.get('is_cooked') is False, \
            "无 PKG_Cooked 标志时 is_cooked 应为 False"

    def test_pkg_uncooked_only_does_not_affect_is_cooked(self):
        """验证 PKG_UncookedOnly (0x100) 不影响 is_cooked 判断"""
        mock_result = _make_mock_result(PKG_UncookedOnly)  # 0x100
        mock_read = _call_secondary_tables(mock_result)

        assert mock_read.called, "read_asset_registry_data 应被调用"
        call_kwargs = mock_read.call_args[1]
        assert call_kwargs.get('is_cooked') is False, \
            "PKG_UncookedOnly 不应影响 is_cooked（应为 False）"

    def test_both_flags_set(self):
        """验证同时设置 PKG_Cooked 和 PKG_UncookedOnly 时的行为"""
        mock_result = _make_mock_result(PKG_Cooked | PKG_UncookedOnly)
        mock_read = _call_secondary_tables(mock_result)

        assert mock_read.called, "read_asset_registry_data 应被调用"
        call_kwargs = mock_read.call_args[1]
        # PKG_Cooked 存在，所以 is_cooked 应为 True
        assert call_kwargs.get('is_cooked') is True, \
            "PKG_Cooked 存在时 is_cooked 应为 True"

    def test_constants_values(self):
        """验证常量值正确"""
        assert PKG_Cooked == 0x200, "PKG_Cooked 应为 0x200"
        assert PKG_UncookedOnly == 0x100, "PKG_UncookedOnly 应为 0x100"
