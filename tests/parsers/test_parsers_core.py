"""parsers 核心模块测试 — 合并自 test_parsers_coverage / test_parse_uasset_coverage / test_usmap_coverage。

覆盖范围：
- parsers/utils: resolve_name_from_index、make_enum_value、extract_inner_from_tag、read_validated_count
- parsers/custom_properties: handle_custom_property 分派逻辑、register_custom_property 装饰器
- parsers/class_serialization_strategy / class_specific_skip: 策略一致性
- parsers/asset_registry_parser: AssetRegistryData 容错
- parse_uasset: 轻量模式、轻量图提取、字节码提取、后处理
- parsers/usmap: 完整 .usmap/.jmap 解析器测试
"""
from __future__ import annotations

import gzip as gzip_mod
import json
import os
import struct
import tempfile
from dataclasses import dataclass, field
from io import BytesIO
from typing import List, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from uasset_read.constants import LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD
from uasset_read.exceptions import ParseError
from uasset_read.models.result import ParseResult
from uasset_read.parse_uasset import (
    _should_use_lightweight_tolerant_parse,
    _build_lightweight_graphs,
    _build_lightweight_function_graphs,
    _post_process,
)
from uasset_read.parse_post_process import _extract_kismet_decompiled
from uasset_read.parsers.asset_registry_parser import read_asset_registry_data
from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    SerializationStrategy,
    CLASS_STRATEGY_TABLE,
)
from uasset_read.parsers.class_specific_skip import SKIP_CLASS_NAMES
from uasset_read.parsers.custom_properties import (
    CUSTOM_PROPERTY_HANDLERS,
    CustomPropertyContext,
    handle_custom_property,
    register_custom_property,
)
from uasset_read.parsers.utils import (
    extract_inner_from_tag,
    make_enum_value,
    read_validated_count_tolerant,
    resolve_name_from_index,
)
from uasset_read.parsers.usmap import (
    _BytesReader,
    _decompress,
    _jmap_prop_type,
    _parse_property_type,
    UsmapProperty,
    UsmapSchema,
    UsmapData,
    parse_usmap,
    PROPERTY_TYPE_NAMES,
    MAGIC_USMAP,
    MAX_RECURSION_DEPTH,
)


# ============================================================================
# parsers/utils — resolve_name_from_index
# ============================================================================


class TestResolveNameFromIndex:
    """resolve_name_from_index 应正确解析名称索引。"""

    def test_valid_index(self):
        archive = None  # archive 未使用
        name_map = ["foo", "bar", "baz"]
        assert resolve_name_from_index(archive, name_map, 0) == "foo"
        assert resolve_name_from_index(archive, name_map, 2) == "baz"

    def test_negative_index_returns_fallback(self):
        assert resolve_name_from_index(None, ["foo"], -1) == "param_-1"

    def test_out_of_range_returns_fallback(self):
        assert resolve_name_from_index(None, ["foo"], 5) == "param_5"

    def test_custom_fallback_prefix(self):
        assert resolve_name_from_index(None, [], 0, fallback_prefix="name") == "name_0"

    def test_empty_name_map(self):
        assert resolve_name_from_index(None, [], 0) == "param_0"


# ============================================================================
# parsers/utils — make_enum_value
# ============================================================================


class TestMakeEnumValue:
    """make_enum_value 应正确创建枚举值字典。"""

    def test_known_enum_type(self):
        result = make_enum_value("Color", "Red")
        assert result == {"enum_type": "Color", "value_name": "Color::Red"}

    def test_unknown_enum_type_no_prefix(self):
        result = make_enum_value("UnknownEnum", "SomeValue")
        assert result == {"enum_type": "UnknownEnum", "value_name": "SomeValue"}

    def test_empty_enum_type(self):
        result = make_enum_value("", "SomeValue")
        assert result == {"enum_type": "", "value_name": "SomeValue"}


# ============================================================================
# parsers/utils — extract_inner_from_tag
# ============================================================================


class TestExtractInnerFromTag:
    """extract_inner_from_tag 应从 tag type 中提取括号内容。"""

    def test_array_property(self):
        assert extract_inner_from_tag("ArrayProperty(IntProperty)") == "IntProperty"

    def test_no_parentheses(self):
        assert extract_inner_from_tag("IntProperty") is None

    def test_multiple_parentheses(self):
        assert extract_inner_from_tag("MapProperty(StringProperty)(IntProperty)") == "StringProperty)(IntProperty"

    def test_empty_string(self):
        assert extract_inner_from_tag("") is None

    def test_nested_parentheses(self):
        assert extract_inner_from_tag("A(B(C))") == "B(C)"


# ============================================================================
# parsers/utils — read_validated_count_tolerant
# ============================================================================


class TestReadValidatedCount:
    """read_validated_count_tolerant 应正确验证数量值。"""

    def _make_archive(self, data: bytes):
        """创建模拟的 FArchive 对象。"""

        class FakeArchive:
            def __init__(self, d):
                self._data = d
                self._pos = 0

            def tell(self):
                return self._pos

            def read_i32(self):
                val = struct.unpack_from("<i", self._data, self._pos)[0]
                self._pos += 4
                return val

        return FakeArchive(data)

    def test_valid_count(self):
        archive = self._make_archive(struct.pack("<i", 10))
        assert read_validated_count_tolerant(archive, 100, "test") == 10

    def test_negative_count_returns_zero(self):
        archive = self._make_archive(struct.pack("<i", -5))
        assert read_validated_count_tolerant(archive, 100, "test") == 0

    def test_over_max_returns_zero(self):
        archive = self._make_archive(struct.pack("<i", 200))
        assert read_validated_count_tolerant(archive, 100, "test") == 0


# ============================================================================
# custom_properties — CustomPropertyContext
# ============================================================================


class TestCustomPropertyContext:
    """CustomPropertyContext 应正确创建。"""

    def test_create_context(self):
        ctx = CustomPropertyContext(type_id=0xFD, tag=None, archive=None)
        assert ctx.type_id == 0xFD
        assert ctx.tag is None
        assert ctx.archive is None
        assert ctx.name_map is None
        assert ctx.mappings is None
        assert ctx.game is None
        assert ctx.summary is None

    def test_create_context_with_all_fields(self):
        ctx = CustomPropertyContext(
            type_id=0xFE,
            tag="fake_tag",
            archive="fake_archive",
            name_map=["a", "b"],
            mappings={"k": "v"},
            game="TestGame",
            summary="fake_summary",
        )
        assert ctx.type_id == 0xFE
        assert ctx.name_map == ["a", "b"]
        assert ctx.game == "TestGame"


# ============================================================================
# custom_properties — register_custom_property
# ============================================================================


class TestRegisterCustomProperty:
    """register_custom_property 装饰器应正确注册处理器。"""

    def test_decorator_registers_handler(self):
        """装饰器应将处理器添加到 CUSTOM_PROPERTY_HANDLERS。"""
        assert (None, 0xFD) in CUSTOM_PROPERTY_HANDLERS
        assert (None, 0xFE) in CUSTOM_PROPERTY_HANDLERS

    def test_game_specific_handler_registered(self):
        """游戏特定处理器应以游戏名作为 key。"""
        assert ("borderlands4", 0xFD) in CUSTOM_PROPERTY_HANDLERS
        assert ("borderlands4", 0xFE) in CUSTOM_PROPERTY_HANDLERS

    def test_string_type_id_registered(self):
        """字符串类型的 type_id 也应被注册。"""
        assert ("borderlands4", "GbxDefPtrProperty") in CUSTOM_PROPERTY_HANDLERS
        assert ("borderlands4", "GameDataHandleProperty") in CUSTOM_PROPERTY_HANDLERS


# ============================================================================
# custom_properties — handle_custom_property 分派逻辑
# ============================================================================


class TestHandleCustomPropertyDispatch:
    """handle_custom_property 应按优先级分派到正确的处理器。"""

    def _make_mock_tag(self, type_name: str = "None", size: int = 0):
        """创建模拟 PropertyTag。"""
        tag = MagicMock()
        tag.type = type_name
        tag.size = size
        return tag

    def _make_mock_archive(self, data: bytes = b""):
        """创建模拟 FArchive。"""
        archive = MagicMock()
        archive.read.return_value = data
        return archive

    def test_no_handler_returns_unhandled_fallback(self):
        """无处理器时应返回 unhandled fallback 结果。"""
        tag = self._make_mock_tag(type_name="UnknownCustomType", size=4)
        archive = self._make_mock_archive(b"\x00\x01\x02\x03")
        result = handle_custom_property(type_id=0xFF, tag=tag, archive=archive)
        assert result is not None
        assert result["kind"] == "custom_property_unhandled"
        assert result["type_id"] == 0xFF
        assert result["property_type"] == "UnknownCustomType"
        assert result["size"] == 4

    def test_no_handler_zero_size(self):
        """无处理器且 size=0 时 raw_data 应为空。"""
        tag = self._make_mock_tag(type_name="SomeType", size=0)
        archive = self._make_mock_archive()
        result = handle_custom_property(type_id=0xFF, tag=tag, archive=archive)
        assert result["raw_data"] == b""

    def test_game_specific_handler_takes_priority(self):
        """游戏特定处理器应优先于通用处理器。"""
        tag = self._make_mock_tag(type_name="GbxDefPtrProperty", size=0)
        archive = self._make_mock_archive()
        archive.read_name.return_value = "TestName"
        archive.read_i32.return_value = 42
        result = handle_custom_property(type_id=0xFD, tag=tag, archive=archive, game="Borderlands4")
        assert result is not None
        assert result.get("kind") == "GbxDefPtrProperty"

    def test_generic_handler_used_when_no_game_match(self):
        """无游戏匹配时应使用通用处理器。"""
        tag = self._make_mock_tag(type_name="SomeType", size=8)
        archive = self._make_mock_archive(b"\x00" * 8)
        result = handle_custom_property(type_id=0xFD, tag=tag, archive=archive, game="SomeUnknownGame")
        assert result is not None
        assert result.get("type_id") == 0xFD
        assert result.get("size") == 8

    def test_tag_type_fallback_lookup(self):
        """当 type_id 无匹配时，应尝试 tag.type 作为 key。"""
        tag = self._make_mock_tag(type_name="GbxDefPtrProperty", size=0)
        archive = self._make_mock_archive()
        archive.read_name.return_value = "FallbackName"
        archive.read_i32.return_value = 99
        result = handle_custom_property(type_id=0xFD, tag=tag, archive=archive, game="Borderlands4")
        assert result is not None
        assert result.get("kind") == "GbxDefPtrProperty"


# ============================================================================
# AssetRegistryData 容错测试
# ============================================================================


class FailingArchive:
    """在 read_fstring 时抛 ParseError 的 mock。"""
    def seek(self, offset):
        pass
    def tell(self):
        return 0
    def total_size(self):
        return 1000
    def read_fstring(self):
        raise ParseError("short read from asset registry")
    def read_i32(self):
        return 1
    def read_i64(self):
        return 0


def test_asset_registry_data_parse_error_returns_partial():
    """ParseError 应被捕获，返回部分结果而非崩溃。"""
    archive = FailingArchive()
    result = read_asset_registry_data(archive, asset_registry_data_offset=100, file_version_ue4=510, is_cooked=True)
    assert result is not None


# ============================================================================
# 统一类策略表测试
# ============================================================================


def test_no_conflict_between_skip_and_opaque():
    """同一个 class 不应同时出现在 skip 和 opaque 策略中。"""
    for class_name in SKIP_CLASS_NAMES:
        strategy = get_serialization_strategy(class_name)
        if strategy == SerializationStrategy.OPAQUE_CLASS_PAYLOAD:
            pytest.fail(
                f"策略冲突: {class_name} 同时在 OPAQUE_CLASS_PAYLOAD 和 SKIP_CLASS_NAMES 中"
            )


def test_skip_classes_derived_from_strategy_table():
    """SKIP_CLASS_NAMES 应从策略表派生，不应有独立名单。"""
    for class_name in SKIP_CLASS_NAMES:
        assert class_name in CLASS_STRATEGY_TABLE, (
            f"{class_name} 在 SKIP_CLASS_NAMES 但不在 CLASS_STRATEGY_TABLE 中"
        )
        strategy = CLASS_STRATEGY_TABLE[class_name]
        assert strategy == SerializationStrategy.SKIP_UNSUPPORTED, (
            f"{class_name} 在 SKIP_CLASS_NAMES 但策略表中为 {strategy}"
        )


def test_niagara_system_not_conflicting():
    """NiagaraSystem 的两层策略应一致。"""
    strategy = get_serialization_strategy("NiagaraSystem")
    assert strategy in (
        SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
        SerializationStrategy.SKIP_UNSUPPORTED,
    ), f"NiagaraSystem 策略不明确: {strategy}"


# ===========================================================================
# 辅助数据类
# ===========================================================================

@dataclass
class MockSummary:
    """模拟 PackageFileSummary。"""
    export_count: int = 0
    package_name: str = "/Game/Test"
    file_version_ue5: int = 0
    total_export_count: int = 0
    total_import_count: int = 0
    package_flags: int = 0
    version: int = 522
    soft_object_paths_count: int = 0
    soft_object_paths_offset: int = 0
    depends_map_count: int = 0
    depends_map_offset: int = 0
    preload_dependency_count: int = 0
    preload_dependency_offset: int = 0


@dataclass
class MockExport:
    """模拟 ObjectExport。"""
    object_name: str = "TestExport"
    class_index: MagicMock = field(default_factory=lambda: MagicMock())
    serial_offset: int = 0
    serial_size: int = 100


@dataclass
class MockImport:
    """模拟 ObjectImport。"""
    object_name: str = "TestImport"
    class_package: str = "/Engine/Core"
    class_name: str = "Object"


# ===========================================================================
# _should_use_lightweight_tolerant_parse 测试
# ===========================================================================

class TestShouldUseLightweightTolerantParse:
    """_should_use_lightweight_tolerant_parse 轻量模式检测单元测试。"""

    def test_force_full_parse_returns_false(self):
        result = ParseResult()
        result.summary = MockSummary(export_count=1000)
        assert _should_use_lightweight_tolerant_parse(result, tolerant=True, force_full_parse=True) is False

    def test_not_tolerant_returns_false(self):
        result = ParseResult()
        result.summary = MockSummary(export_count=1000)
        assert _should_use_lightweight_tolerant_parse(result, tolerant=False, force_full_parse=False) is False

    def test_no_summary_returns_false(self):
        result = ParseResult()
        result.summary = None
        assert _should_use_lightweight_tolerant_parse(result, tolerant=True, force_full_parse=False) is False

    def test_below_threshold_returns_false(self):
        result = ParseResult()
        result.summary = MockSummary(export_count=LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD)
        assert _should_use_lightweight_tolerant_parse(result, tolerant=True, force_full_parse=False) is False

    def test_above_threshold_returns_true(self):
        result = ParseResult()
        result.summary = MockSummary(export_count=LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD + 1)
        assert _should_use_lightweight_tolerant_parse(result, tolerant=True, force_full_parse=False) is True

    def test_custom_threshold(self):
        result = ParseResult()
        result.summary = MockSummary(export_count=50)
        assert _should_use_lightweight_tolerant_parse(result, tolerant=True, lightweight_threshold=100) is False
        assert _should_use_lightweight_tolerant_parse(result, tolerant=True, lightweight_threshold=30) is True


# ===========================================================================
# _build_lightweight_graphs 测试
# ===========================================================================

class TestBuildLightweightGraphs:
    """_build_lightweight_graphs 轻量图提取单元测试。"""

    def test_empty_export_map(self):
        result = ParseResult()
        result.export_map = []
        result.import_map = []
        assert _build_lightweight_graphs(result) == []

    def test_empty_import_map(self):
        result = ParseResult()
        result.export_map = [MockExport(object_name="Test")]
        result.import_map = []
        assert _build_lightweight_graphs(result) == []

    def test_no_edgraph_exports(self):
        result = ParseResult()
        export = MockExport(object_name="TestComponent")
        result.export_map = [export]
        result.import_map = [MockImport()]
        with patch('uasset_read.serializers.object_resources.get_asset_class', return_value="BlueprintGeneratedClass"):
            assert _build_lightweight_graphs(result) == []

    def test_edgraph_export(self):
        result = ParseResult()
        export = MockExport(object_name="EventGraph")
        result.export_map = [export]
        result.import_map = [MockImport()]
        with patch('uasset_read.serializers.object_resources.get_asset_class', return_value="EdGraph"):
            graphs = _build_lightweight_graphs(result)
            assert len(graphs) == 1
            assert graphs[0].graph_name == "EventGraph"
            assert graphs[0].graph_class == "EdGraph"
            assert graphs[0].nodes == []

    def test_uberedgraph_export(self):
        result = ParseResult()
        export = MockExport(object_name="UberGraphPages")
        result.export_map = [export]
        result.import_map = [MockImport()]
        with patch('uasset_read.serializers.object_resources.get_asset_class', return_value="UberEdGraph"):
            graphs = _build_lightweight_graphs(result)
            assert len(graphs) == 1
            assert graphs[0].graph_name == "UberGraphPages"
            assert graphs[0].graph_class == "UberEdGraph"

    def test_multiple_edgraph_exports(self):
        result = ParseResult()
        export1 = MockExport(object_name="EventGraph")
        export2 = MockExport(object_name="AnimGraph")
        result.export_map = [export1, export2]
        result.import_map = [MockImport()]
        with patch('uasset_read.serializers.object_resources.get_asset_class', return_value="EdGraph"):
            graphs = _build_lightweight_graphs(result)
            assert len(graphs) == 2
            names = {g.graph_name for g in graphs}
            assert "EventGraph" in names
            assert "AnimGraph" in names

    def test_export_without_name(self):
        result = ParseResult()
        export = MockExport(object_name="")
        result.export_map = [export]
        result.import_map = [MockImport()]
        with patch('uasset_read.serializers.object_resources.get_asset_class', return_value="EdGraph"):
            assert _build_lightweight_graphs(result) == []

    def test_mixed_export_types(self):
        result = ParseResult()
        export1 = MockExport(object_name="EventGraph")
        export2 = MockExport(object_name="TestComponent")
        export3 = MockExport(object_name="UberGraphPages")
        result.export_map = [export1, export2, export3]
        result.import_map = [MockImport()]

        def mock_get_class(exp, imp, exps):
            if exp.object_name in ("EventGraph",):
                return "EdGraph"
            if exp.object_name == "UberGraphPages":
                return "UberEdGraph"
            return "BlueprintGeneratedClass"

        with patch('uasset_read.serializers.object_resources.get_asset_class', side_effect=mock_get_class):
            graphs = _build_lightweight_graphs(result)
            assert len(graphs) == 2


# ===========================================================================
# _build_lightweight_function_graphs 测试
# ===========================================================================

class TestBuildLightweightFunctionGraphs:
    """_build_lightweight_function_graphs 轻量函数图提取单元测试。"""

    def test_empty_export_map(self):
        assert _build_lightweight_function_graphs([]) == []

    def test_none_export_map(self):
        assert _build_lightweight_function_graphs(None) == []

    def test_blueprint_class_export(self):
        export = MockExport(object_name="TestBlueprint_C")
        assert _build_lightweight_function_graphs([export]) == []

    def test_default_object_export(self):
        export = MockExport(object_name="Default__TestBlueprint")
        assert _build_lightweight_function_graphs([export]) == []

    def test_event_graph_export(self):
        export = MockExport(object_name="EventGraph")
        assert _build_lightweight_function_graphs([export]) == []

    def test_uber_graph_pages_export(self):
        export = MockExport(object_name="UberGraphPages")
        assert _build_lightweight_function_graphs([export]) == []

    def test_simple_construction_script_export(self):
        export = MockExport(object_name="SimpleConstructionScript")
        assert _build_lightweight_function_graphs([export]) == []

    def test_normal_function_export(self):
        export = MockExport(object_name="MyFunction")
        entries = _build_lightweight_function_graphs([export])
        assert len(entries) == 1
        assert entries[0]["function_name"] == "MyFunction"
        assert entries[0]["graph_source"] == "export_map"
        assert entries[0]["fallback_reason"] == "lightweight_tolerant_parse"

    def test_multiple_function_exports(self):
        exports = [
            MockExport(object_name="Function1"),
            MockExport(object_name="Function2"),
            MockExport(object_name="Function3"),
        ]
        entries = _build_lightweight_function_graphs(exports)
        assert len(entries) == 3

    def test_max_entries_limit(self):
        exports = [MockExport(object_name=f"Function{i}") for i in range(100)]
        entries = _build_lightweight_function_graphs(exports)
        assert len(entries) == 64

    def test_empty_name_export(self):
        export = MockExport(object_name="")
        assert _build_lightweight_function_graphs([export]) == []


# ===========================================================================
# _extract_kismet_decompiled 测试
# ===========================================================================

class TestExtractKismetDecompiled:
    """_extract_kismet_decompiled 字节码提取单元测试。"""

    def test_no_ustruct_exports(self):
        archive = MagicMock()
        summary = MockSummary()
        name_map = ["Test"]
        import_map = []
        export_map = [MockExport(object_name="TestExport")]
        with patch('uasset_read.serializers.object_resources.resolve_class_name', return_value="TestComponent"):
            result = _extract_kismet_decompiled("/Game/Test", archive, summary, name_map, import_map, export_map)
            assert result == []

    def test_ustruct_export_success(self):
        archive = MagicMock()
        summary = MockSummary()
        name_map = ["Test"]
        import_map = []
        export = MockExport(object_name="MyFunction")
        export_map = [export]
        mock_result = MagicMock()
        mock_result.function_name = "MyFunction"
        with patch('uasset_read.serializers.object_resources.resolve_class_name', return_value="UserDefinedEnum"):
            with patch('uasset_read.kismet.bytecode_extractor.USTRUCT_TYPES', {"UserDefinedEnum"}):
                with patch('uasset_read.kismet.pipeline.decompile_single_function', return_value=mock_result):
                    with patch('uasset_read.kismet.bytecode_extractor.reset_bpgc_cache'):
                        result = _extract_kismet_decompiled("/Game/Test", archive, summary, name_map, import_map, export_map)
                        assert len(result) == 1
                        assert result[0].function_name == "MyFunction"

    def test_ustruct_export_failure_tolerant(self):
        archive = MagicMock()
        summary = MockSummary()
        name_map = ["Test"]
        import_map = []
        export = MockExport(object_name="MyFunction")
        export_map = [export]
        with patch('uasset_read.serializers.object_resources.resolve_class_name', return_value="UserDefinedEnum"):
            with patch('uasset_read.kismet.bytecode_extractor.USTRUCT_TYPES', {"UserDefinedEnum"}):
                with patch('uasset_read.kismet.pipeline.decompile_single_function', side_effect=OSError("Test error")):
                    with patch('uasset_read.kismet.bytecode_extractor.reset_bpgc_cache'):
                        result = _extract_kismet_decompiled("/Game/Test", archive, summary, name_map, import_map, export_map)
                        assert result == []

    def test_ustruct_export_returns_none(self):
        archive = MagicMock()
        summary = MockSummary()
        name_map = ["Test"]
        import_map = []
        export = MockExport(object_name="MyFunction")
        export_map = [export]
        with patch('uasset_read.serializers.object_resources.resolve_class_name', return_value="UserDefinedEnum"):
            with patch('uasset_read.kismet.bytecode_extractor.USTRUCT_TYPES', {"UserDefinedEnum"}):
                with patch('uasset_read.kismet.pipeline.decompile_single_function', return_value=None):
                    with patch('uasset_read.kismet.bytecode_extractor.reset_bpgc_cache'):
                        result = _extract_kismet_decompiled("/Game/Test", archive, summary, name_map, import_map, export_map)
                        assert result == []


# ===========================================================================
# _post_process 测试
# ===========================================================================

class TestPostProcess:
    """_post_process 后处理单元测试。"""

    def test_basic_post_process(self):
        archive = MagicMock()
        summary = MockSummary()
        name_map = ["Test"]
        import_map = []
        export_map = []
        result = ParseResult()
        try:
            _post_process("/Game/Test", archive, summary, name_map, import_map, export_map, result, tolerant=True)
            assert True
        except Exception:
            assert False, "_post_process raised an exception in tolerant mode"

    def test_post_process_with_linker(self):
        archive = MagicMock()
        summary = MockSummary()
        name_map = ["Test"]
        import_map = []
        export_map = []
        result = ParseResult()
        linker = MagicMock()
        try:
            _post_process("/Game/Test", archive, summary, name_map, import_map, export_map, result, tolerant=True, linker=linker)
            assert True
        except Exception:
            assert False, "_post_process raised an exception in tolerant mode"


# ===========================================================================
# ParseResult 边界测试
# ===========================================================================

class TestParseResultEdgeCases:
    """ParseResult 边界情况测试。"""

    def test_parse_result_defaults(self):
        result = ParseResult()
        assert result.summary is None
        assert result.name_map == []
        assert result.export_map == []
        assert result.import_map == []
        assert result.linker is None
        assert result.graphs == []
        assert result.decompiled_functions == []
        assert result.metadata == {}
        assert result.mmap_used is False
        assert result.mmap_warning is None

    def test_parse_result_with_diagnostics(self):
        result = ParseResult()
        diag = MagicMock()
        result.diagnostics = [diag]
        assert len(result.diagnostics) == 1

    def test_parse_result_status_model(self):
        result = ParseResult()
        assert result.status == "failed"
        result.name_map = ["Test"]
        assert result.status == "partial"
        result.errors = ["Test error"]
        assert result.status == "partial"
        result2 = ParseResult()
        result2.is_success = True
        result2.name_map = ["Test"]
        assert result2.status == "success"


# ===========================================================================
# 辅助：构建最小合法 .usmap 二进制（无压缩，version 0）
# ===========================================================================

def _build_minimal_usmap(
    name_table: list[str] | None = None,
    enums: dict[str, dict[int, str]] | None = None,
    schemas: dict[str, UsmapSchema] | None = None,
    version: int = 0,
) -> bytes:
    """构建最小可解析的 .usmap 字节流。"""
    if name_table is None:
        name_table = []
    if enums is None:
        enums = {}
    if schemas is None:
        schemas = {}

    buf = bytearray()
    buf += struct.pack("<H", MAGIC_USMAP)
    buf += struct.pack("<B", version)

    if version >= 1:
        buf += struct.pack("<B", 0)

    payload = bytearray()

    payload += struct.pack("<I", len(name_table))
    for name in name_table:
        name_bytes = name.encode("utf-8")
        payload += struct.pack("<H" if version >= 2 else "<B", len(name_bytes))
        payload += name_bytes

    payload += struct.pack("<I", len(enums))
    for enum_name, values in enums.items():
        enum_name_idx = name_table.index(enum_name) if enum_name in name_table else -1
        payload += struct.pack("<i", enum_name_idx)
        value_count = len(values)
        payload += struct.pack("<H" if version >= 3 else "<B", value_count)
        for val, member in values.items():
            if version >= 4:
                payload += struct.pack("<Q", val)
            member_idx = name_table.index(member) if member in name_table else -1
            payload += struct.pack("<i", member_idx)

    payload += struct.pack("<I", len(schemas))
    for schema in schemas.values():
        schema_name_idx = name_table.index(schema.name) if schema.name in name_table else -1
        payload += struct.pack("<i", schema_name_idx)
        super_idx = name_table.index(schema.super_type) if schema.super_type and schema.super_type in name_table else -1
        payload += struct.pack("<i", super_idx)
        payload += struct.pack("<H", schema.property_count)
        payload += struct.pack("<H", schema.serializable_count)
        for prop in schema.properties.values():
            payload += struct.pack("<H", prop.index)
            payload += struct.pack("<B", prop.array_dim)
            prop_name_idx = name_table.index(prop.name) if prop.name in name_table else -1
            payload += struct.pack("<i", prop_name_idx)
            _write_prop_type(payload, prop)

    decomp_size = len(payload)
    buf += struct.pack("<B", 0)
    buf += struct.pack("<I", decomp_size)
    buf += struct.pack("<I", decomp_size)
    buf += payload

    return bytes(buf)


def _write_prop_type(buf: bytearray, prop: UsmapProperty) -> None:
    """向 buf 追加属性类型的二进制表示。"""
    type_id = _type_name_to_id(prop.type_name)
    buf += struct.pack("<B", type_id)

    if prop.type_name == "EnumProperty":
        inner = prop.inner_type or UsmapProperty(index=0, name="", type_name="ByteProperty")
        _write_prop_type(buf, inner)
        buf += struct.pack("<i", -1)
    elif prop.type_name == "StructProperty":
        buf += struct.pack("<i", -1)
    elif prop.type_name in {"ArrayProperty", "SetProperty", "OptionalProperty"}:
        inner = prop.inner_type or UsmapProperty(index=0, name="", type_name="IntProperty")
        _write_prop_type(buf, inner)
    elif prop.type_name == "MapProperty":
        inner = prop.inner_type or UsmapProperty(index=0, name="", type_name="IntProperty")
        value = prop.value_type or UsmapProperty(index=0, name="", type_name="IntProperty")
        _write_prop_type(buf, inner)
        _write_prop_type(buf, value)


def _type_name_to_id(name: str) -> int:
    for tid, tname in PROPERTY_TYPE_NAMES.items():
        if tname == name:
            return tid
    return 0xFF


# ===========================================================================
# 测试 _parse_property_type（递归类型解析）
# ===========================================================================

class TestParsePropertyType:
    """_parse_property_type 递归解析测试。"""

    @staticmethod
    def _make_reader(type_id: int, extra: bytes = b"") -> _BytesReader:
        return _BytesReader(struct.pack("<B", type_id) + extra)

    def test_simple_int(self):
        reader = self._make_reader(2)
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "IntProperty"
        assert prop.inner_type is None
        assert prop.value_type is None
        assert prop.struct_type is None
        assert prop.enum_name is None

    def test_simple_float(self):
        reader = self._make_reader(3)
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "FloatProperty"

    def test_simple_byte(self):
        reader = self._make_reader(0)
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "ByteProperty"

    def test_simple_bool(self):
        reader = self._make_reader(1)
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "BoolProperty"

    def test_array_property(self):
        reader = self._make_reader(8, struct.pack("<B", 2))
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "ArrayProperty"
        assert prop.inner_type is not None
        assert prop.inner_type.type_name == "IntProperty"

    def test_map_property(self):
        reader = self._make_reader(24, struct.pack("<BB", 2, 3))
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "MapProperty"
        assert prop.inner_type.type_name == "IntProperty"
        assert prop.value_type.type_name == "FloatProperty"

    def test_struct_property_preserves_name(self):
        reader = self._make_reader(9, struct.pack("<i", -1))
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "StructProperty"
        assert prop.struct_type == ""

    def test_struct_property_with_lut_name(self):
        lut = ["FVector"]
        reader = self._make_reader(9, struct.pack("<i", 0))
        prop = _parse_property_type(reader, lut)
        assert prop.struct_type == "FVector"

    def test_enum_property_preserves_name(self):
        reader = self._make_reader(0x1A, struct.pack("<B", 0) + struct.pack("<i", -1))
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "EnumProperty"
        assert prop.inner_type.type_name == "ByteProperty"
        assert prop.enum_name == ""

    def test_enum_property_with_lut_name(self):
        lut = ["EMyEnum"]
        reader = self._make_reader(0x1A, struct.pack("<B", 0) + struct.pack("<i", 0))
        prop = _parse_property_type(reader, lut)
        assert prop.enum_name == "EMyEnum"

    def test_set_property(self):
        reader = self._make_reader(25, struct.pack("<B", 7))
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "SetProperty"
        assert prop.inner_type.type_name == "DoubleProperty"

    def test_optional_property(self):
        reader = self._make_reader(28, struct.pack("<B", 5))
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "OptionalProperty"
        assert prop.inner_type.type_name == "NameProperty"

    def test_unknown_type_custom_fd(self):
        reader = self._make_reader(0xFD)
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "CustomProperty_FD"

    def test_unknown_type_custom_fe(self):
        reader = self._make_reader(0xFE)
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "CustomProperty_FE"

    def test_fully_unknown_type_id(self):
        reader = self._make_reader(0xC0)
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "Unknown"

    def test_nested_array_of_struct(self):
        inner_struct = struct.pack("<B", 9) + struct.pack("<i", -1)
        reader = self._make_reader(8, inner_struct)
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "ArrayProperty"
        assert prop.inner_type.type_name == "StructProperty"
        assert prop.inner_type.struct_type == ""

    def test_nested_map_string_to_array(self):
        inner = struct.pack("<B", 10)
        val_inner = struct.pack("<B", 8) + struct.pack("<B", 2)
        reader = self._make_reader(24, inner + val_inner)
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "MapProperty"
        assert prop.inner_type.type_name == "StrProperty"
        assert prop.value_type.type_name == "ArrayProperty"
        assert prop.value_type.inner_type.type_name == "IntProperty"

    def test_depth_limit_exceeded(self):
        reader = self._make_reader(2)
        with pytest.raises(ParseError, match="递归深度超过上限"):
            _parse_property_type(reader, [], depth=MAX_RECURSION_DEPTH + 1)


# ===========================================================================
# 测试 UsmapProperty / UsmapSchema 数据类
# ===========================================================================

class TestUsmapProperty:
    def test_creation_with_all_fields(self):
        inner = UsmapProperty(index=0, name="", type_name="IntProperty")
        value = UsmapProperty(index=0, name="", type_name="FloatProperty")
        prop = UsmapProperty(
            index=42, name="MyProp", type_name="MapProperty",
            struct_type="FVector", inner_type=inner, value_type=value,
            enum_name="EMyEnum", array_dim=3,
        )
        assert prop.index == 42
        assert prop.name == "MyProp"
        assert prop.type_name == "MapProperty"
        assert prop.struct_type == "FVector"
        assert prop.inner_type is inner
        assert prop.value_type is value
        assert prop.enum_name == "EMyEnum"
        assert prop.array_dim == 3

    def test_defaults(self):
        prop = UsmapProperty(index=0, name="X", type_name="FloatProperty")
        assert prop.struct_type is None
        assert prop.inner_type is None
        assert prop.value_type is None
        assert prop.enum_name is None
        assert prop.array_dim == 1


class TestUsmapSchema:
    def test_creation_defaults(self):
        schema = UsmapSchema(name="TestClass")
        assert schema.name == "TestClass"
        assert schema.super_type is None
        assert schema.serializable_count == 0
        assert schema.property_count == 0
        assert schema.properties == {}

    def test_with_properties(self):
        prop = UsmapProperty(index=0, name="Health", type_name="FloatProperty")
        schema = UsmapSchema(
            name="APawn", super_type="AActor",
            serializable_count=1, property_count=5, properties={0: prop},
        )
        assert schema.super_type == "AActor"
        assert len(schema.properties) == 1
        assert schema.properties[0].name == "Health"


# ===========================================================================
# 测试 _jmap_prop_type
# ===========================================================================

class TestJmapPropType:
    def test_simple_property(self):
        result = _jmap_prop_type({"type": "IntProperty"})
        assert result.type_name == "IntProperty"
        assert result.inner_type is None
        assert result.value_type is None
        assert result.struct_type is None
        assert result.enum_name is None

    def test_array_property_with_container(self):
        result = _jmap_prop_type({"type": "ArrayProperty", "container": {"type": "FloatProperty"}})
        assert result.type_name == "ArrayProperty"
        assert result.inner_type.type_name == "FloatProperty"

    def test_array_property_with_inner(self):
        result = _jmap_prop_type({"type": "ArrayProperty", "inner": {"type": "NameProperty"}})
        assert result.inner_type.type_name == "NameProperty"

    def test_array_property_with_key_prop(self):
        result = _jmap_prop_type({"type": "ArrayProperty", "key_prop": {"type": "StrProperty"}})
        assert result.inner_type.type_name == "StrProperty"

    def test_map_property_with_key_and_value(self):
        result = _jmap_prop_type({
            "type": "MapProperty",
            "key_prop": {"type": "NameProperty"},
            "value_prop": {"type": "StrProperty"},
        })
        assert result.type_name == "MapProperty"
        assert result.inner_type.type_name == "NameProperty"
        assert result.value_type.type_name == "StrProperty"

    def test_unknown_type_defaults(self):
        result = _jmap_prop_type({"type": None})
        assert result.type_name == "Unknown"

    def test_struct_type_preserves_name(self):
        result = _jmap_prop_type({"type": "StructProperty", "struct": "Engine.FVector"})
        assert result.struct_type == "FVector"

    def test_struct_type_empty_string(self):
        result = _jmap_prop_type({"type": "StructProperty", "struct": ""})
        assert result.struct_type is None

    def test_enum_type_preserves_name(self):
        result = _jmap_prop_type({"type": "EnumProperty", "enum": "Engine.EMyEnum"})
        assert result.enum_name == "EMyEnum"

    def test_enum_type_empty_string(self):
        result = _jmap_prop_type({"type": "EnumProperty", "enum": ""})
        assert result.enum_name is None

    def test_nested_containers(self):
        result = _jmap_prop_type({
            "type": "ArrayProperty",
            "container": {
                "type": "MapProperty",
                "key_prop": {"type": "IntProperty"},
                "value_prop": {"type": "FloatProperty"},
            },
        })
        assert result.type_name == "ArrayProperty"
        assert result.inner_type.type_name == "MapProperty"
        assert result.inner_type.inner_type.type_name == "IntProperty"
        assert result.inner_type.value_type.type_name == "FloatProperty"

    def test_inner_not_dict_ignored(self):
        result = _jmap_prop_type({"type": "ArrayProperty", "container": "not_a_dict"})
        assert result.inner_type is None

    def test_value_not_dict_ignored(self):
        result = _jmap_prop_type({
            "type": "MapProperty",
            "key_prop": {"type": "IntProperty"},
            "value_prop": "not_a_dict",
        })
        assert result.inner_type is not None
        assert result.value_type is None

    def test_empty_dict(self):
        result = _jmap_prop_type({})
        assert result.type_name == "Unknown"

    def test_deeply_nested_no_recursion_limit(self):
        inner: dict = {"type": "IntProperty"}
        for _ in range(20):
            inner = {"type": "ArrayProperty", "container": inner}
        result = _jmap_prop_type(inner)
        assert result.type_name == "ArrayProperty"
        current = result
        for _ in range(19):
            assert current.inner_type is not None
            assert current.inner_type.type_name == "ArrayProperty"
            current = current.inner_type
        assert current.inner_type.type_name == "IntProperty"


# ===========================================================================
# 测试 UsmapData / parse_usmap
# ===========================================================================

class TestUsmapData:
    def test_parse_usmap_from_bytes(self):
        data = _build_minimal_usmap(name_table=["Foo", "Bar"])
        result = parse_usmap(data)
        assert result.version == 0
        assert result.name_table == ["Foo", "Bar"]
        assert result.enums == {}
        assert result.schemas == {}

    def test_usmap_data_from_stream(self):
        data = _build_minimal_usmap(name_table=["Stream"])
        ud = UsmapData(BytesIO(data))
        assert ud.version == 0
        assert ud.name_table == ["Stream"]

    def test_version_1_with_versioning(self):
        payload = bytearray()
        payload += struct.pack("<I", 1)
        payload += struct.pack("<B", 4)
        payload += b"Test"
        payload += struct.pack("<I", 0)
        payload += struct.pack("<I", 0)

        buf = bytearray(struct.pack("<H", MAGIC_USMAP))
        buf += struct.pack("<B", 1)
        buf += struct.pack("<B", 1)
        buf += struct.pack("<ii", 0, 0)
        buf += struct.pack("<i", 2)
        buf += b"\x00" * 40
        buf += struct.pack("<I", 0)
        buf += struct.pack("<B", 0)
        buf += struct.pack("<I", len(payload))
        buf += struct.pack("<I", len(payload))
        buf += payload

        result = parse_usmap(bytes(buf))
        assert result.version == 1
        assert result.name_table == ["Test"]

    def test_version_1_negative_custom_count(self):
        buf = bytearray(struct.pack("<H", MAGIC_USMAP))
        buf += struct.pack("<B", 1)
        buf += struct.pack("<B", 1)
        buf += struct.pack("<ii", 0, 0)
        buf += struct.pack("<i", -1)
        buf += struct.pack("<I", 0)
        buf += struct.pack("<B", 0)
        buf += struct.pack("<I", 0)
        buf += struct.pack("<I", 0)
        with pytest.raises(ParseError, match="CustomVersion 数量无效"):
            parse_usmap(bytes(buf))

    def test_find_property_in_parent(self):
        child_prop = UsmapProperty(index=0, name="Speed", type_name="FloatProperty")
        parent_prop = UsmapProperty(index=0, name="Health", type_name="FloatProperty")
        child = UsmapSchema(
            name="Derived", super_type="Base",
            serializable_count=1, property_count=1, properties={0: child_prop},
        )
        base = UsmapSchema(
            name="Base", serializable_count=1, property_count=1, properties={0: parent_prop},
        )
        data = _build_minimal_usmap(
            name_table=["Derived", "Base", "Speed", "Health"],
            schemas={"Derived": child, "Base": base},
        )
        ud = UsmapData(data)
        found = ud.find_property("Derived", "Health")
        assert found is not None
        assert found.name == "Health"

    def test_find_property_no_infinite_loop(self):
        prop = UsmapProperty(index=0, name="X", type_name="IntProperty")
        a = UsmapSchema(name="A", super_type="B", serializable_count=1, property_count=1, properties={0: prop})
        b = UsmapSchema(name="B", super_type="A", serializable_count=0, property_count=0, properties={})
        data = _build_minimal_usmap(name_table=["A", "B", "X"], schemas={"A": a, "B": b})
        ud = UsmapData(data)
        assert ud.find_property("A", "Nonexistent") is None

    def test_parse_usmap_returns_usmap_data(self):
        data = _build_minimal_usmap()
        result = parse_usmap(data)
        assert isinstance(result, UsmapData)


# ===========================================================================
# 测试 _decompress 压缩方法
# ===========================================================================

class TestDecompress:
    def test_no_compression_valid(self):
        payload = b"\x01\x02\x03"
        result = _decompress(payload, method=0, comp_size=3, decomp_size=3)
        assert result == payload

    def test_no_compression_size_mismatch(self):
        with pytest.raises(ParseError, match="大小不一致"):
            _decompress(b"\x01", method=0, comp_size=1, decomp_size=2)

    def test_unsupported_method(self):
        with pytest.raises(ParseError, match="不支持的 Usmap 压缩方式"):
            _decompress(b"", method=99, comp_size=0, decomp_size=0)

    def test_brotli_import_error(self):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "brotli":
                raise ImportError("No module named 'brotli'")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            with pytest.raises(ParseError, match="Brotli"):
                _decompress(b"", method=2, comp_size=0, decomp_size=0)

    def test_zstd_import_error(self):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "zstandard":
                raise ImportError("No module named 'zstandard'")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            with pytest.raises(ParseError, match="ZStandard"):
                _decompress(b"", method=3, comp_size=0, decomp_size=0)

    def test_brotli_decompress(self):
        brotli = pytest.importorskip("brotli")
        original = b"Hello, brotli! " * 100
        compressed = brotli.compress(original)
        result = _decompress(compressed, method=2, comp_size=len(compressed), decomp_size=len(original))
        assert result == original

    def test_zstd_decompress(self):
        zstd = pytest.importorskip("zstandard")
        original = b"Hello, zstd! " * 100
        cctx = zstd.ZstdCompressor()
        compressed = cctx.compress(original)
        result = _decompress(compressed, method=3, comp_size=len(compressed), decomp_size=len(original))
        assert result == original


# ===========================================================================
# 测试 gzip 路径
# ===========================================================================

class TestGzipPaths:
    def test_usmap_gzip_extension_rejected(self, tmp_path):
        data = _build_minimal_usmap(name_table=["GzipTest"])
        path = tmp_path / "test.usmap.gz"
        path.write_bytes(gzip_mod.compress(data))
        with pytest.raises(ParseError, match="不支持的映射文件类型"):
            UsmapData(str(path))

    def test_gzip_compressed_bytes_via_binary_io(self):
        data = _build_minimal_usmap(name_table=["GzipStream"])
        ud = UsmapData(data)
        assert ud.name_table == ["GzipStream"]


# ===========================================================================
# 测试 jmap 加载路径（JSON 映射）
# ===========================================================================

class TestJmapLoading:
    def test_jmap_basic(self, tmp_path):
        jmap_data = {
            "objects": {
                "Engine.MyEnum": {"type": "Enum", "names": [["Value0", 0], ["Value1", 1]]},
                "Engine.MyStruct": {
                    "type": "ScriptStruct",
                    "properties": [
                        {"name": "Health", "type": "FloatProperty"},
                        {"name": "Name", "type": "StrProperty"},
                    ],
                },
                "Engine.MyClass": {
                    "type": "Class",
                    "super_struct": "Engine.Object",
                    "properties": [{"name": "Pos", "type": "StructProperty", "struct": "Engine.FVector"}],
                },
            }
        }
        path = tmp_path / "test.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        assert "MyEnum" in ud.enums
        assert ud.enums["MyEnum"][0] == "Value0"
        assert "MyStruct" in ud.schemas
        assert len(ud.schemas["MyStruct"].properties) == 2
        assert "MyClass" in ud.schemas
        assert ud.schemas["MyClass"].super_type == "Object"

    def test_jmap_with_array_dim(self, tmp_path):
        jmap_data = {
            "objects": {
                "Engine.Foo": {
                    "type": "ScriptStruct",
                    "properties": [{"name": "Arr", "type": "ArrayProperty", "array_dim": 3, "inner": {"type": "IntProperty"}}],
                }
            }
        }
        path = tmp_path / "dim.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        prop = list(ud.schemas["Foo"].properties.values())[0]
        assert prop.array_dim == 3

    def test_jmap_with_map_property(self, tmp_path):
        jmap_data = {
            "objects": {
                "Engine.Bar": {
                    "type": "ScriptStruct",
                    "properties": [{"name": "Data", "type": "MapProperty", "key_prop": {"type": "NameProperty"}, "value_prop": {"type": "FloatProperty"}}],
                }
            }
        }
        path = tmp_path / "map.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        prop = list(ud.schemas["Bar"].properties.values())[0]
        assert prop.type_name == "MapProperty"
        assert prop.inner_type.type_name == "NameProperty"
        assert prop.value_type.type_name == "FloatProperty"

    def test_jmap_non_dict_object_skipped(self, tmp_path):
        jmap_data = {"objects": {"Engine.Valid": {"type": "ScriptStruct", "properties": []}, "Engine.Invalid": "not_a_dict"}}
        path = tmp_path / "skip.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        assert "Valid" in ud.schemas
        assert "Invalid" not in ud.schemas

    def test_jmap_non_dict_property_skipped(self, tmp_path):
        jmap_data = {"objects": {"Engine.Foo": {"type": "ScriptStruct", "properties": ["not_a_dict", {"name": "Real", "type": "IntProperty"}]}}}
        path = tmp_path / "skip_prop.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        assert len(ud.schemas["Foo"].properties) == 1

    def test_jmap_enum_empty_names(self, tmp_path):
        jmap_data = {"objects": {"Engine.EmptyEnum": {"type": "Enum", "names": []}}}
        path = tmp_path / "empty_enum.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        assert ud.enums["EmptyEnum"] == {}

    def test_jmap_gzip(self, tmp_path):
        jmap_data = {"objects": {}}
        path = tmp_path / "test.jmap.gz"
        path.write_bytes(gzip_mod.compress(json.dumps(jmap_data).encode("utf-8")))
        ud = UsmapData(str(path))
        assert ud.version == 0
        assert ud.schemas == {}

    def test_jmap_unknown_type_in_property(self, tmp_path):
        jmap_data = {"objects": {"Engine.Foo": {"type": "ScriptStruct", "properties": [{"name": "Custom", "type": "CustomType"}]}}}
        path = tmp_path / "unknown.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        prop = list(ud.schemas["Foo"].properties.values())[0]
        assert prop.type_name == "CustomType"

    def test_jmap_struct_property_with_full_path(self, tmp_path):
        jmap_data = {"objects": {"Engine.Foo": {"type": "ScriptStruct", "properties": [{"name": "Vec", "type": "StructProperty", "struct": "Core.Math.FVector"}]}}}
        path = tmp_path / "fullpath.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        prop = list(ud.schemas["Foo"].properties.values())[0]
        assert prop.struct_type == "FVector"

    def test_jmap_enum_with_full_path(self, tmp_path):
        jmap_data = {"objects": {"Engine.Foo": {"type": "ScriptStruct", "properties": [{"name": "E", "type": "EnumProperty", "enum": "Engine.ENumType"}]}}}
        path = tmp_path / "enumpath.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        prop = list(ud.schemas["Foo"].properties.values())[0]
        assert prop.enum_name == "ENumType"


# ===========================================================================
# 测试完整 .usmap 解析（带 schema 和 property）
# ===========================================================================

class TestFullUsmapParsing:
    def test_parse_with_schema_and_properties(self):
        name_table = ["MyClass", "Health"]
        prop = UsmapProperty(index=0, name="Health", type_name="IntProperty")
        schema = UsmapSchema(name="MyClass", serializable_count=1, property_count=1, properties={0: prop})
        data = _build_minimal_usmap(name_table=name_table, schemas={"MyClass": schema})
        result = parse_usmap(data)
        assert "MyClass" in result.schemas
        parsed_prop = result.schemas["MyClass"].properties[0]
        assert parsed_prop.name == "Health"
        assert parsed_prop.type_name == "IntProperty"

    def test_parse_with_enum(self):
        name_table = ["EMyEnum", "ValueA", "ValueB"]
        enums = {"EMyEnum": {0: "ValueA", 1: "ValueB"}}
        data = _build_minimal_usmap(name_table=name_table, enums=enums)
        result = parse_usmap(data)
        assert "EMyEnum" in result.enums
        assert result.enums["EMyEnum"][0] == "ValueA"

    def test_parse_multiple_schemas(self):
        name_table = ["A", "B"]
        schema_a = UsmapSchema(name="A", serializable_count=0, property_count=0)
        schema_b = UsmapSchema(name="B", serializable_count=0, property_count=0)
        data = _build_minimal_usmap(name_table=name_table, schemas={"A": schema_a, "B": schema_b})
        result = parse_usmap(data)
        assert "A" in result.schemas
        assert "B" in result.schemas


# ===========================================================================
# 辅助函数（合并自 test_usmap.py）
# ===========================================================================

def _build_usmap_v0_legacy(
    name_table: list[str] | None = None,
    enums: dict[str, dict[int, str]] | None = None,
    schemas: list[UsmapSchema] | None = None,
) -> bytes:
    """构造一个合成的 v0 .usmap 二进制数据。"""
    if name_table is None:
        name_table = []
    if enums is None:
        enums = {}
    if schemas is None:
        schemas = []

    payload = bytearray()
    payload += struct.pack("<I", len(name_table))
    for name in name_table:
        encoded = name.encode("utf-8")
        payload += struct.pack("<B", len(encoded))
        payload += encoded

    payload += struct.pack("<I", len(enums))
    for enum_name, values in enums.items():
        enum_name_idx = name_table.index(enum_name) if enum_name in name_table else -1
        payload += struct.pack("<i", enum_name_idx)
        payload += struct.pack("<B", len(values))
        for val, member_name in values.items():
            member_idx = name_table.index(member_name) if member_name in name_table else -1
            payload += struct.pack("<i", member_idx)

    payload += struct.pack("<I", len(schemas))
    for schema in schemas:
        name_idx = name_table.index(schema.name) if schema.name in name_table else -1
        super_idx = name_table.index(schema.super_type) if schema.super_type and schema.super_type in name_table else -1
        payload += struct.pack("<i", name_idx)
        payload += struct.pack("<i", super_idx)
        payload += struct.pack("<H", schema.property_count)
        payload += struct.pack("<H", schema.serializable_count)
        sorted_props = sorted(schema.properties.values(), key=lambda p: p.index)
        for prop in sorted_props:
            payload += struct.pack("<H", prop.index)
            payload += struct.pack("<B", prop.array_dim)
            prop_name_idx = name_table.index(prop.name) if prop.name in name_table else -1
            payload += struct.pack("<i", prop_name_idx)
            _write_prop_type_legacy(payload, prop)

    comp_size = len(payload)
    header = bytearray()
    header += struct.pack("<H", MAGIC_USMAP)
    header += struct.pack("<B", 0)
    header += struct.pack("<B", 0)
    header += struct.pack("<I", comp_size)
    header += struct.pack("<I", comp_size)
    header += bytes(payload)
    return bytes(header)


def _write_prop_type_legacy(buf: bytearray, prop: UsmapProperty) -> None:
    type_id = _type_name_to_id(prop.type_name)
    buf += struct.pack("<B", type_id)
    if prop.type_name == "EnumProperty":
        if prop.inner_type:
            _write_prop_type_legacy(buf, prop.inner_type)
        buf += struct.pack("<i", -1)
    elif prop.type_name == "StructProperty":
        buf += struct.pack("<i", -1)
    elif prop.type_name in {"ArrayProperty", "SetProperty", "OptionalProperty"}:
        if prop.inner_type:
            _write_prop_type_legacy(buf, prop.inner_type)
    elif prop.type_name == "MapProperty":
        if prop.inner_type:
            _write_prop_type_legacy(buf, prop.inner_type)
        if prop.value_type:
            _write_prop_type_legacy(buf, prop.value_type)


# ===========================================================================
# Header / NameTable / SchemaTable / EnumTable 解析测试
# ===========================================================================

class TestUsmapHeader:
    def test_valid_magic(self):
        data = _build_usmap_v0_legacy()
        result = parse_usmap(data)
        assert result.version == 0

    def test_invalid_magic_raises(self):
        data = struct.pack("<H", 0x1234) + b"\x00" * 20
        with pytest.raises(ParseError, match="magic"):
            parse_usmap(data)

    def test_truncated_header(self):
        data = struct.pack("<H", MAGIC_USMAP)
        with pytest.raises(ParseError):
            parse_usmap(data)

    def test_version_too_high(self):
        buf = bytearray()
        buf += struct.pack("<H", MAGIC_USMAP)
        buf += struct.pack("<B", 99)
        with pytest.raises(ParseError):
            parse_usmap(bytes(buf))


class TestUsmapNameTable:
    def test_empty_name_table(self):
        data = _build_usmap_v0_legacy(name_table=[])
        result = parse_usmap(data)
        assert result.name_table == []

    def test_single_name(self):
        data = _build_usmap_v0_legacy(name_table=["TestStruct"])
        result = parse_usmap(data)
        assert result.name_table == ["TestStruct"]

    def test_multiple_names(self):
        names = ["A", "BB", "CCC", "DDDD"]
        data = _build_usmap_v0_legacy(name_table=names)
        result = parse_usmap(data)
        assert result.name_table == names

    def test_unicode_name(self):
        data = _build_usmap_v0_legacy(name_table=["Hello", "测试"])
        result = parse_usmap(data)
        assert result.name_table[1] == "测试"


class TestUsmapSchemaTable:
    def test_empty_schemas(self):
        data = _build_usmap_v0_legacy(schemas=[])
        result = parse_usmap(data)
        assert result.schemas == {}

    def test_single_schema_no_properties(self):
        schema = UsmapSchema(name="MyClass", super_type=None, property_count=0, serializable_count=0)
        data = _build_usmap_v0_legacy(name_table=["MyClass"], schemas=[schema])
        result = parse_usmap(data)
        assert "MyClass" in result.schemas
        parsed = result.schemas["MyClass"]
        assert parsed.name == "MyClass"
        assert parsed.super_type is None
        assert parsed.property_count == 0

    def test_schema_with_int_property(self):
        prop = UsmapProperty(index=0, name="Health", type_name="IntProperty", array_dim=1)
        schema = UsmapSchema(name="Character", super_type=None, property_count=1, serializable_count=1, properties={0: prop})
        data = _build_usmap_v0_legacy(name_table=["Character", "Health"], schemas=[schema])
        result = parse_usmap(data)
        parsed = result.schemas["Character"]
        assert len(parsed.properties) == 1
        assert parsed.properties[0].name == "Health"
        assert parsed.properties[0].type_name == "IntProperty"

    def test_schema_with_array_property(self):
        inner = UsmapProperty(index=0, name="", type_name="FloatProperty")
        prop = UsmapProperty(index=0, name="Scores", type_name="ArrayProperty", inner_type=inner, array_dim=1)
        schema = UsmapSchema(name="Player", property_count=1, serializable_count=1, properties={0: prop})
        data = _build_usmap_v0_legacy(name_table=["Player", "Scores"], schemas=[schema])
        result = parse_usmap(data)
        parsed = result.schemas["Player"]
        assert parsed.properties[0].type_name == "ArrayProperty"

    def test_schema_with_super_type(self):
        schema = UsmapSchema(name="Child", super_type="Parent", property_count=0, serializable_count=0)
        data = _build_usmap_v0_legacy(name_table=["Child", "Parent"], schemas=[schema])
        result = parse_usmap(data)
        assert result.schemas["Child"].super_type == "Parent"


class TestUsmapDataAPI:
    def test_from_bytes(self):
        data = _build_usmap_v0_legacy(name_table=["Test"])
        usmap = UsmapData(data)
        assert usmap.version == 0
        assert usmap.name_table == ["Test"]

    def test_from_path(self, tmp_path):
        data = _build_usmap_v0_legacy(name_table=["FileTest"])
        path = tmp_path / "test.usmap"
        path.write_bytes(data)
        usmap = UsmapData(str(path))
        assert usmap.name_table == ["FileTest"]

    def test_parse_usmap_function(self):
        data = _build_usmap_v0_legacy(name_table=["FuncTest"])
        usmap = parse_usmap(data)
        assert usmap.name_table == ["FuncTest"]

    def test_invalid_file_extension(self, tmp_path):
        path = tmp_path / "test.txt"
        path.write_bytes(b"hello")
        with pytest.raises(ParseError, match="不支持的映射文件类型"):
            UsmapData(str(path))

    def test_get_schema(self):
        schema = UsmapSchema(name="MyStruct", property_count=0)
        data = _build_usmap_v0_legacy(name_table=["MyStruct"], schemas=[schema])
        usmap = UsmapData(data)
        assert usmap.get_schema("MyStruct") is not None
        assert usmap.get_schema("SomePackage.MyStruct") is not None
        assert usmap.get_schema("Nonexistent") is None
        assert usmap.get_schema(None) is None

    def test_find_property(self):
        prop = UsmapProperty(index=0, name="ID", type_name="IntProperty")
        schema = UsmapSchema(name="Entity", property_count=1, serializable_count=1, properties={0: prop})
        data = _build_usmap_v0_legacy(name_table=["Entity", "ID"], schemas=[schema])
        usmap = UsmapData(data)
        found = usmap.find_property("Entity", "ID")
        assert found is not None
        assert found.name == "ID"
        found_upper = usmap.find_property("Entity", "id")
        assert found_upper is not None

    def test_find_property_not_found(self):
        schema = UsmapSchema(name="Empty", property_count=0)
        data = _build_usmap_v0_legacy(name_table=["Empty"], schemas=[schema])
        usmap = UsmapData(data)
        assert usmap.find_property("Empty", "Nonexistent") is None


class TestUsmapEnumTable:
    def test_empty_enums(self):
        data = _build_usmap_v0_legacy(enums={})
        result = parse_usmap(data)
        assert result.enums == {}

    def test_enum_with_values(self):
        names = ["ETestEnum", "Value1", "Value2"]
        enums = {"ETestEnum": {0: "Value1", 1: "Value2"}}
        data = _build_usmap_v0_legacy(name_table=names, enums=enums)
        result = parse_usmap(data)
        assert "ETestEnum" in result.enums
        assert result.enums["ETestEnum"][0] == "Value1"


class TestBytesReader:
    def test_read_u8(self):
        reader = _BytesReader(b"\x42")
        assert reader.u8() == 0x42

    def test_read_u16(self):
        reader = _BytesReader(struct.pack("<H", 12345))
        assert reader.u16() == 12345

    def test_read_u32(self):
        reader = _BytesReader(struct.pack("<I", 0xDEADBEEF))
        assert reader.u32() == 0xDEADBEEF

    def test_read_i32(self):
        reader = _BytesReader(struct.pack("<i", -42))
        assert reader.i32() == -42

    def test_read_u64(self):
        reader = _BytesReader(struct.pack("<Q", 0x123456789ABCDEF0))
        assert reader.u64() == 0x123456789ABCDEF0

    def test_read_overflow(self):
        reader = _BytesReader(b"\x01")
        with pytest.raises(ParseError, match="读取越界"):
            reader.read(2)

    def test_remaining(self):
        reader = _BytesReader(b"\x01\x02\x03")
        assert reader.remaining == 3
        reader.u8()
        assert reader.remaining == 2

    def test_name_lookup(self):
        lut = ["alpha", "beta", "gamma"]
        reader = _BytesReader(struct.pack("<i", 1))
        assert reader.name(lut) == "beta"

    def test_name_none(self):
        lut = ["alpha"]
        reader = _BytesReader(struct.pack("<i", -1))
        assert reader.name(lut) is None

    def test_name_out_of_bounds(self):
        lut = ["alpha"]
        reader = _BytesReader(struct.pack("<i", 5))
        with pytest.raises(ParseError, match="名称索引越界"):
            reader.name(lut)


class TestUsmapIntegration:
    @pytest.fixture
    def sample_usmap(self):
        import os
        base = os.path.join(os.path.dirname(__file__), "..", "..", "external", "UAssetAPI", "UAssetAPI.Tests", "TestAssets", "TestJson")
        path = os.path.join(base, "MotorTown.usmap")
        if os.path.exists(path):
            return path
        pytest.skip("无外部 .usmap 测试样本")

    def test_load_real_usmap(self, sample_usmap):
        usmap = UsmapData(sample_usmap)
        assert usmap.version >= 0
        assert isinstance(usmap.name_table, list)
        assert isinstance(usmap.schemas, dict)

    def test_parse_usmap_function_real(self, sample_usmap):
        usmap = parse_usmap(sample_usmap)
        assert len(usmap.schemas) > 0


# ===========================================================================
# jmap 属性递归深度限制测试
# ===========================================================================

def _make_nested_dict(depth: int) -> dict:
    node = {"type": "StrProperty"}
    for _ in range(depth):
        node = {"type": "ArrayProperty", "container": node}
    return node


class TestJmapRecursionDepth:
    def test_normal_depth_succeeds(self):
        prop = _make_nested_dict(10)
        result = _jmap_prop_type(prop)
        assert result.type_name == "ArrayProperty"

    def test_depth_at_limit_succeeds(self):
        prop = _make_nested_dict(63)
        result = _jmap_prop_type(prop)
        assert result is not None

    def test_depth_exceeding_limit_raises(self):
        prop = _make_nested_dict(65)
        with pytest.raises(ValueError, match="递归深度"):
            _jmap_prop_type(prop)

    def test_depth_tracking_is_correct(self):
        prop = {"type": "ArrayProperty", "container": {"type": "StrProperty"}}
        result = _jmap_prop_type(prop, depth=62)
        assert result is not None
        with pytest.raises(ValueError):
            _jmap_prop_type(prop, depth=64)


# ===========================================================================
# UsmapData budget 测试
# ===========================================================================

class RecordingBudget:
    def __init__(self):
        self.calls = []
    def reserve(self, amount, label=""):
        self.calls.append((amount, label))
    def check(self, amount, label=""):
        pass


def _make_minimal_usmap() -> bytes:
    magic = struct.pack('<H', 0x30C4)
    version = struct.pack('B', 0)
    compression = struct.pack('B', 0)
    name_payload = struct.pack('<I', 1)
    name_payload += struct.pack('B', 4)
    name_payload += b'Test'
    name_payload += struct.pack('<I', 0)
    name_payload += struct.pack('<I', 0)
    decomp_size = len(name_payload)
    comp_size = decomp_size
    return magic + version + compression + struct.pack('<I', comp_size) + struct.pack('<I', decomp_size) + name_payload


def test_usmap_file_read_reserves_budget():
    budget = RecordingBudget()
    data = _make_minimal_usmap()
    with tempfile.NamedTemporaryFile(suffix=".usmap", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        UsmapData(path, budget=budget)
        reserve_calls = [c for c in budget.calls if c[1] == "usmap_file_read"]
        assert len(reserve_calls) == 1
        assert reserve_calls[0][0] == os.path.getsize(path)
    finally:
        os.unlink(path)
