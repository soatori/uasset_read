"""IR 工具测试 — 合并自 test_hex_view_ir.py 和 test_json_completeness.py。

覆盖：HexView IR、DebugIR、JSON 输出完整性。
"""
import json
from dataclasses import dataclass
from typing import Any

import pytest

from uasset_read.debug.hex_view import HexViewEntry
from uasset_read.models.ir import HexViewEntryIR, DebugIR, PackageIR, PackageHeaderIR
from uasset_read.ir_builder import _build_debug_ir, build_package_ir
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.result import ParseResult


# ---------------------------------------------------------------------------
# HexViewEntryIR
# ---------------------------------------------------------------------------
class TestHexViewEntryIR:
    """HexViewEntryIR 数据类测试。"""

    def test_basic_creation(self):
        """基本创建和字段访问。"""
        entry = HexViewEntryIR(
            key="Magic", type="u32", value=0x9E2A83C1,
            start=0, stop=4, size=4,
        )
        assert entry.key == "Magic"
        assert entry.type == "u32"
        assert entry.value == 0x9E2A83C1
        assert entry.start == 0
        assert entry.stop == 4
        assert entry.size == 4

    def test_optional_fields_none(self):
        """可选字段默认为 None。"""
        entry = HexViewEntryIR(
            key="x", type="u8", value=1, start=0, stop=1, size=1,
        )
        assert entry.field_path is None
        assert entry.semantic_type is None
        assert entry.value_hex is None
        assert entry.value_size is None

    def test_optional_fields_set(self):
        """可选字段可设置。"""
        entry = HexViewEntryIR(
            key="x", type="u8", value=1, start=0, stop=1, size=1,
            field_path="PackageSummary.Magic",
            semantic_type="header",
        )
        assert entry.field_path == "PackageSummary.Magic"
        assert entry.semantic_type == "header"


# ---------------------------------------------------------------------------
# DebugIR
# ---------------------------------------------------------------------------
class TestDebugIR:
    """DebugIR 数据类测试。"""

    def test_default_empty(self):
        """默认空 DebugIR。"""
        debug = DebugIR()
        assert debug.hex_view == []

    def test_with_entries(self):
        """带条目的 DebugIR。"""
        entries = [
            HexViewEntryIR(key="a", type="u8", value=1, start=0, stop=1, size=1),
            HexViewEntryIR(key="b", type="u32", value=2, start=1, stop=5, size=4),
        ]
        debug = DebugIR(hex_view=entries)
        assert len(debug.hex_view) == 2
        assert debug.hex_view[0].key == "a"
        assert debug.hex_view[1].key == "b"


# ---------------------------------------------------------------------------
# _build_debug_ir
# ---------------------------------------------------------------------------
class TestBuildDebugIR:
    """_build_debug_ir 函数测试。"""

    def test_empty_entries_returns_none(self):
        """空条目返回 None。"""
        assert _build_debug_ir([]) is None

    def test_none_entries_returns_none(self):
        """None 输入返回 None。"""
        assert _build_debug_ir(None) is None

    def test_converts_hex_view_entries(self):
        """HexViewEntry 转换为 HexViewEntryIR。"""
        source = [
            HexViewEntry(key="Magic", type="u32", value=0x9E2A83C1, start=0, stop=4),
        ]
        result = _build_debug_ir(source)
        assert result is not None
        assert isinstance(result, DebugIR)
        assert len(result.hex_view) == 1
        assert result.hex_view[0].key == "Magic"
        assert result.hex_view[0].type == "u32"
        assert result.hex_view[0].value == 0x9E2A83C1
        assert result.hex_view[0].start == 0
        assert result.hex_view[0].stop == 4
        assert result.hex_view[0].size == 4

    def test_preserves_field_path_and_semantic_type(self):
        """保留 field_path 和 semantic_type。"""
        source = [
            HexViewEntry(
                key="Version", type="i32", value=100, start=4, stop=8,
                field_path="PackageSummary.Version",
                semantic_type="header",
            ),
        ]
        result = _build_debug_ir(source)
        assert result.hex_view[0].field_path == "PackageSummary.Version"
        assert result.hex_view[0].semantic_type == "header"

    def test_handles_legacy_entries_without_new_fields(self):
        """兼容没有新字段的旧条目。"""
        source = [
            HexViewEntry(key="x", type="u8", value=1, start=0, stop=1),
        ]
        result = _build_debug_ir(source)
        assert result is not None
        assert result.hex_view[0].field_path is None
        assert result.hex_view[0].semantic_type is None

    def test_multiple_entries(self):
        """多个条目转换。"""
        source = [
            HexViewEntry(key="A", type="u8", value=1, start=0, stop=1),
            HexViewEntry(key="B", type="u16", value=2, start=1, stop=3),
            HexViewEntry(key="C", type="u32", value=3, start=3, stop=7),
        ]
        result = _build_debug_ir(source)
        assert len(result.hex_view) == 3


# ---------------------------------------------------------------------------
# PackageIR.debug
# ---------------------------------------------------------------------------
class TestPackageIRDebug:
    """PackageIR.debug 字段测试。"""

    def _make_header(self):
        return PackageHeaderIR(
            package_name="Test", package_class="Package",
            package_flags=0, total_export_count=0, total_import_count=0,
            ue_version="5.4",
        )

    def test_default_none(self):
        """默认 debug 为 None。"""
        ir = PackageIR(
            header=self._make_header(),
            name_map=[], imports=[], exports=[], linker=None,
        )
        assert ir.debug is None

    def test_with_debug(self):
        """设置 debug 字段。"""
        debug = DebugIR(hex_view=[
            HexViewEntryIR(key="x", type="u8", value=1, start=0, stop=1, size=1),
        ])
        ir = PackageIR(
            header=self._make_header(),
            name_map=[], imports=[], exports=[], linker=None,
            debug=debug,
        )
        assert ir.debug is not None
        assert len(ir.debug.hex_view) == 1


# ---------------------------------------------------------------------------
# JSON Renderer — debug.hex_view 输出
# ---------------------------------------------------------------------------
class TestJSONRendererHexView:
    """JSON 渲染器 HexView 输出测试。"""

    def _make_ir(self, hex_view_entries=None):
        """构建用于测试的最小 PackageIR。"""
        header = PackageHeaderIR(
            package_name="Test", package_class="Package",
            package_flags=0, total_export_count=0, total_import_count=0,
            ue_version="5.4",
        )
        ir = PackageIR(
            header=header,
            name_map=[], imports=[], exports=[], linker=None,
        )
        if hex_view_entries:
            ir.debug = DebugIR(hex_view=hex_view_entries)
        return ir

    def test_no_debug_when_hex_view_flag_false(self):
        """hex_view=False 时不输出 debug。"""
        ir = self._make_ir([
            HexViewEntryIR(key="x", type="u8", value=1, start=0, stop=1, size=1),
        ])
        renderer = JSONRenderer()
        options = RenderOptions(hex_view=False)
        output = json.loads(renderer.render(ir, options))
        assert "debug" not in output

    def test_debug_output_when_hex_view_flag_true(self):
        """hex_view=True 时输出 debug.hex_view。"""
        ir = self._make_ir([
            HexViewEntryIR(key="Magic", type="u32", value=0x9E2A83C1, start=0, stop=4, size=4),
        ])
        renderer = JSONRenderer()
        options = RenderOptions(hex_view=True)
        output = json.loads(renderer.render(ir, options))
        assert "debug" in output
        assert "hex_view" in output["debug"]
        assert len(output["debug"]["hex_view"]) == 1
        assert output["debug"]["hex_view"][0]["key"] == "Magic"
        assert output["debug"]["hex_view"][0]["type"] == "u32"
        assert output["debug"]["hex_view"][0]["value"] == 0x9E2A83C1
        assert output["debug"]["hex_view"][0]["start"] == 0
        assert output["debug"]["hex_view"][0]["stop"] == 4
        assert output["debug"]["hex_view"][0]["size"] == 4

    def test_debug_output_when_output_level_debug(self):
        """output_level='debug' 时输出 debug.hex_view。"""
        ir = self._make_ir([
            HexViewEntryIR(key="x", type="u8", value=1, start=0, stop=1, size=1),
        ])
        renderer = JSONRenderer()
        options = RenderOptions(output_level="debug")
        output = json.loads(renderer.render(ir, options))
        assert "debug" in output

    def test_no_debug_when_no_entries(self):
        """无条目时不输出 debug。"""
        ir = self._make_ir()  # 无 hex_view_entries
        renderer = JSONRenderer()
        options = RenderOptions(hex_view=True)
        output = json.loads(renderer.render(ir, options))
        assert "debug" not in output

    def test_field_path_in_output(self):
        """field_path 字段正确输出。"""
        ir = self._make_ir([
            HexViewEntryIR(
                key="Version", type="i32", value=100, start=4, stop=8, size=4,
                field_path="PackageSummary.Version",
                semantic_type="header",
            ),
        ])
        renderer = JSONRenderer()
        options = RenderOptions(hex_view=True)
        output = json.loads(renderer.render(ir, options))
        entry = output["debug"]["hex_view"][0]
        assert entry["field_path"] == "PackageSummary.Version"
        assert entry["semantic_type"] == "header"

    def test_bytes_value_serialized_as_hex(self):
        """bytes 值序列化为 value_hex。"""
        ir = self._make_ir([
            HexViewEntryIR(
                key="raw", type="bytes", value=b'\xAB\xCD', start=0, stop=2, size=2,
            ),
        ])
        renderer = JSONRenderer()
        options = RenderOptions(hex_view=True)
        output = json.loads(renderer.render(ir, options))
        entry = output["debug"]["hex_view"][0]
        assert entry["value_hex"] == "abcd"
        assert entry["value_size"] == 2
        assert "value" not in entry


# ---------------------------------------------------------------------------
# core.py bypass 逻辑
# ---------------------------------------------------------------------------
class TestCoreBypassLogic:
    """core.py hex_view 旁路逻辑测试。"""

    def test_hex_view_text_format_bypasses_ir(self):
        """非 json 格式 + hex_view=True 时返回文本（旁路 IR）。"""
        from unittest.mock import MagicMock, patch
        from uasset_read.core import parse_single

        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.hex_view_entries = [
            HexViewEntry(key="x", type="u8", value=1, start=0, stop=1),
        ]
        mock_result.summary = MagicMock()
        mock_result.summary.uncompressed_size = 1024

        with patch("uasset_read.core.parse_package", return_value=mock_result):
            result = parse_single("fake.uasset", hex_view=True, format="markdown")
            assert isinstance(result, str)
            assert "HexView" in result

    def test_hex_view_json_format_goes_through_ir(self):
        """json 格式 + hex_view=True 时走 IR 管线。"""
        from unittest.mock import patch
        from uasset_read.core import parse_single

        # 构建真实 ParseResult 避免 mock 属性缺失问题
        mock_result = ParseResult()
        mock_result.is_success = True
        mock_result.hex_view_entries = [
            HexViewEntry(key="Magic", type="u32", value=0x9E2A83C1, start=0, stop=4),
        ]

        # json 格式走 linker 路径，需要 mock parse_uasset_with_linker
        with patch("uasset_read.core.parse_uasset_with_linker", return_value=mock_result):
            result = parse_single("fake.uasset", hex_view=True, format="json")
            # JSON 格式走 IR 管线，返回 JSON 字符串
            assert isinstance(result, str)
            output = json.loads(result)
            assert "summary" in output
            assert "debug" in output
            assert output["debug"]["hex_view"][0]["key"] == "Magic"


# ==============================================================================
# 以下来自 test_json_completeness.py
# ==============================================================================

"""JSON 输出完整性测试 — 验证变量、实现关联、父资产字段完整输出。"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from uasset_read.ir_builder import build_package_ir, _bind_implementations
from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    BlueprintIR,
    BlueprintFunctionIR,
    BlueprintEventIR,
    DecompiledFunctionIR,
    ExportIR,
    PropertyIR,
    ExecutionChainIR,
    VariableIR,
)
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.base import RenderOptions


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------

def _make_header() -> PackageHeaderIR:
    return PackageHeaderIR(
        package_name="/Game/Test/BP_Test",
        package_class="BP_Test_C",
        package_flags=0,
        total_export_count=1,
        total_import_count=1,
        ue_version="5.3",
    )


def _make_minimal_ir(**kwargs) -> PackageIR:
    """构造最小 PackageIR。"""
    defaults = dict(
        header=_make_header(),
        name_map=["BP_Test"],
        imports=[],
        exports=[],
        linker=None,
    )
    defaults.update(kwargs)
    return PackageIR(**defaults)


def _make_mock_blueprint_variable(
    name="Health",
    category="float",
    guid="A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
    default_value="100.0",
    is_replicated=False,
    is_edit_anywhere=True,
    metadata=None,
    flags_labels=None,
):
    """构造 Mock BlueprintVariable。"""
    var = MagicMock()
    var.var_name = name
    var.category = category
    var.var_guid = guid
    var.default_value = default_value
    var.property_flags = 0x00000001  # CPF_Edit
    var.replication_condition = 0
    var.rep_notify_func = ""
    var.friendly_name = name
    var.metadata = metadata or {}
    var.flags_labels = flags_labels or []
    var.edit_condition = ""
    var.is_component = False
    var.is_edit_anywhere = is_edit_anywhere
    var.is_visible_anywhere = False
    var.is_blueprint_read_only = False
    var.is_transient = False
    var.is_replicated = is_replicated
    var.is_rep_notify = False
    var.is_expose_on_spawn = False
    var.is_save_game = False
    # FEdGraphPinType
    pin_type = MagicMock()
    pin_type.pin_category = category
    pin_type.pin_subcategory = ""
    pin_type.pin_subcategory_object_name = None
    pin_type.container_type = 0
    var.var_type = pin_type
    return var


def _make_mock_parse_result_with_variables(variables=None):
    """构造带变量的 mock ParseResult。"""
    result = MagicMock()
    result.summary.package_name = "/Game/Test/BP_Test"
    result.summary.package_class = "BP_Test_C"
    result.summary.package_flags = 0
    result.summary.total_export_count = 1
    result.summary.total_import_count = 1
    result.name_map = ["BP_Test"]
    result.import_map = []
    result.export_map = []
    result.linker = None
    result.version_container = None
    result.errors = []
    result.warnings = []
    result.is_success = True
    result.diagnostics = []
    result.graphs = []
    result.components = []
    result.decompiled_functions = []
    result.resolved_parent_assets = []
    result.inherited_blueprint_graphs = []
    result.logic_sources = []
    result.metadata = {}
    # Blueprint
    bp = MagicMock()
    bp.parent_class = "/Script/Engine.Character"
    bp.functions = []
    bp.events = []
    bp.variables = variables or []
    result.blueprint = bp
    return result


def _render_json(ir: PackageIR, include_function_graphs=False) -> dict:
    """渲染 IR 为 JSON 字典。"""
    renderer = JSONRenderer()
    options = RenderOptions(include_function_graphs=include_function_graphs)
    output = renderer.render(ir, options)
    return json.loads(output)


# ===========================================================================
# 变量输出测试
# ===========================================================================

class TestVariableOutput:
    """验证变量完整输出到 JSON。"""

    def test_variables_in_top_level_json(self):
        """顶层 JSON 应包含 variables 数组。"""
        variables = [
            VariableIR(name="Health", type="float", default_value="100.0", kind="user", guid="a1b2c3d4e5f67890abcdef1234567890"),
            VariableIR(name="Damage", type="int32", default_value="10", kind="user"),
        ]
        ir = _make_minimal_ir(variables=variables)
        data = _render_json(ir)
        assert "variables" in data
        assert len(data["variables"]) == 2
        assert data["variables"][0]["name"] == "Health"
        assert data["variables"][0]["type"] == "float"
        assert data["variables"][0]["default_value"] == "100.0"
        assert data["variables"][0]["guid"] == "a1b2c3d4e5f67890abcdef1234567890"

    def test_variable_full_metadata(self):
        """变量应包含完整元数据字段。"""
        variables = [
            VariableIR(
                name="bIsAlive",
                type="bool",
                default_value="true",
                kind="user",
                guid="a1b2c3d4e5f67890abcdef1234567890",
                category="bool",
                property_flags=0x00000001,
                metadata={"ToolTip": "Is the actor alive"},
                flags_labels=["EditAnywhere"],
                is_edit_anywhere=True,
                is_replicated=True,
            ),
        ]
        ir = _make_minimal_ir(variables=variables)
        data = _render_json(ir)
        var = data["variables"][0]
        assert var["guid"] == "a1b2c3d4e5f67890abcdef1234567890"
        assert var["category"] == "bool"
        assert var["property_flags"] == 0x00000001
        assert var["metadata"] == {"ToolTip": "Is the actor alive"}
        assert var["flags_labels"] == ["EditAnywhere"]
        assert var["is_edit_anywhere"] is True
        assert var["is_replicated"] is True

    def test_variable_bool_flags_omitted_when_false(self):
        """布尔标志为 False 时不应出现在 JSON 中。"""
        variables = [
            VariableIR(name="X", type="float", default_value=None, kind="user"),
        ]
        ir = _make_minimal_ir(variables=variables)
        data = _render_json(ir)
        var = data["variables"][0]
        assert "is_edit_anywhere" not in var
        assert "is_replicated" not in var
        assert "is_transient" not in var

    def test_variable_empty_list_not_in_json(self):
        """空变量列表不应输出 variables 字段。"""
        ir = _make_minimal_ir(variables=[])
        data = _render_json(ir)
        assert "variables" not in data

    def test_variable_ir_builder_from_mock(self):
        """ir_builder 应从 BlueprintVariable 正确构建 VariableIR。"""
        var = _make_mock_blueprint_variable(
            name="MaxHealth",
            category="float",
            guid="A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
            default_value="200.0",
            metadata={"Category": "Stats"},
            flags_labels=["EditAnywhere", "BlueprintReadWrite"],
        )
        result = _make_mock_parse_result_with_variables([var])
        ir = build_package_ir(result)
        assert len(ir.variables) == 1
        v = ir.variables[0]
        assert v.name == "MaxHealth"
        assert v.type == "float"
        assert v.default_value == "200.0"
        assert v.guid == "a1b2c3d4e5f67890abcdef1234567890"
        assert v.metadata == {"Category": "Stats"}
        assert v.flags_labels == ["EditAnywhere", "BlueprintReadWrite"]

    def test_metadata_variables_skipped(self):
        """元数据变量（如 BlueprintType）应被跳过。"""
        from uasset_read.constants import BLUEPRINT_METADATA_KEYS
        meta_var = _make_mock_blueprint_variable(name=list(BLUEPRINT_METADATA_KEYS)[0])
        user_var = _make_mock_blueprint_variable(name="Health")
        result = _make_mock_parse_result_with_variables([meta_var, user_var])
        ir = build_package_ir(result)
        assert len(ir.variables) == 1
        assert ir.variables[0].name == "Health"


# ===========================================================================
# 函数/事件实现关联测试
# ===========================================================================

class TestImplementationBinding:
    """验证函数/事件与 decompiled_functions 和 function_graphs 的关联。"""

    def _make_blueprint_ir(self, functions=None, events=None):
        return BlueprintIR(
            parent_class="/Script/Engine.Character",
            functions=functions or [],
            events=events or [],
            components=[],
        )

    def test_exact_function_name_match(self):
        """精确函数名匹配 → implementation_status == 'decompiled'。"""
        func = BlueprintFunctionIR(name="Fire", return_type="void", parameters=[])
        bp = self._make_blueprint_ir(functions=[func])
        decompiled = [
            DecompiledFunctionIR(name="Fire", signature="void Fire()", cpp_code="void Fire() {}", parameters=[], return_type="void"),
        ]
        _bind_implementations(bp, decompiled, [])
        assert func.implementation_status == "decompiled"
        assert func.implementation is not None
        assert func.implementation["name"] == "Fire"
        assert func.implementation["cpp_code"] == "void Fire() {}"

    def test_event_alias_match(self):
        """事件别名匹配（ReceiveBeginPlay → BeginPlay）→ decompiled。"""
        evt = BlueprintEventIR(name="ReceiveBeginPlay", event_type="Event", parameters=[])
        bp = self._make_blueprint_ir(events=[evt])
        decompiled = [
            DecompiledFunctionIR(name="BeginPlay", signature="void BeginPlay()", cpp_code="void BeginPlay() {}", parameters=[], return_type="void"),
        ]
        _bind_implementations(bp, decompiled, [])
        assert evt.implementation_status == "decompiled"
        assert evt.implementation["name"] == "BeginPlay"

    def test_graph_only_match(self):
        """function_graphs 匹配但无 decompiled → implementation_status == 'graph_only'。"""
        func = BlueprintFunctionIR(name="UpdateUI", return_type="void", parameters=[])
        bp = self._make_blueprint_ir(functions=[func])
        graphs = [
            {"function_name": "UpdateUI", "graph_source": "UpdateUI", "entry_node_guid": "abc123"},
        ]
        _bind_implementations(bp, [], graphs)
        assert func.implementation_status == "graph_only"
        assert func.function_graph is not None
        assert func.function_graph["function_name"] == "UpdateUI"

    def test_missing_implementation(self):
        """无匹配 → implementation_status == 'missing'。"""
        func = BlueprintFunctionIR(name="Unmapped", return_type="void", parameters=[])
        bp = self._make_blueprint_ir(functions=[func])
        _bind_implementations(bp, [], [])
        assert func.implementation_status == "missing"
        assert func.implementation is None
        assert func.function_graph is None

    def test_decompiled_takes_priority_over_graph(self):
        """decompiled 优先于 function_graphs。"""
        func = BlueprintFunctionIR(name="Fire", return_type="void", parameters=[])
        bp = self._make_blueprint_ir(functions=[func])
        decompiled = [
            DecompiledFunctionIR(name="Fire", signature="void Fire()", cpp_code="void Fire() {}", parameters=[], return_type="void"),
        ]
        graphs = [
            {"function_name": "Fire", "graph_source": "Fire", "entry_node_guid": "abc123"},
        ]
        _bind_implementations(bp, decompiled, graphs)
        assert func.implementation_status == "decompiled"
        assert func.function_graph is None

    def test_implementation_in_json_output(self):
        """实现关联应出现在 JSON 输出中。"""
        func = BlueprintFunctionIR(name="Fire", return_type="void", parameters=[])
        func.implementation = {"name": "Fire", "signature": "void Fire()", "cpp_code": "void Fire() {}", "parameters": [], "return_type": "void"}
        func.implementation_status = "decompiled"
        bp = BlueprintIR(parent_class=None, functions=[func], events=[], components=[])
        ir = _make_minimal_ir(blueprint=bp)
        data = _render_json(ir)
        f = data["blueprint"]["functions"][0]
        assert f["implementation_status"] == "decompiled"
        assert f["implementation"]["cpp_code"] == "void Fire() {}"

    def test_event_implementation_in_json_output(self):
        """事件实现关联应出现在 JSON 输出中。"""
        evt = BlueprintEventIR(name="ReceiveBeginPlay", event_type="Event", parameters=[])
        evt.implementation = {"name": "BeginPlay", "signature": "void BeginPlay()", "cpp_code": "void BeginPlay() {}", "parameters": [], "return_type": "void"}
        evt.implementation_status = "decompiled"
        bp = BlueprintIR(parent_class=None, functions=[], events=[evt], components=[])
        ir = _make_minimal_ir(blueprint=bp)
        data = _render_json(ir)
        e = data["blueprint"]["events"][0]
        assert e["implementation_status"] == "decompiled"
        assert e["implementation"]["name"] == "BeginPlay"


# ===========================================================================
# 函数/事件完整元数据测试
# ===========================================================================

class TestFunctionEventMetadata:
    """验证函数/事件 flags 和 metadata 完整输出。"""

    def test_function_flags_in_json(self):
        """函数 flags 应出现在 JSON 中。"""
        func = BlueprintFunctionIR(
            name="GetHealth", return_type="float", parameters=[],
            function_flags=0x00000400,  # FUNC_BlueprintPure
            is_pure=True,
            is_const=True,
            access_specifier="Public",
            meta_data={"Category": "Health"},
        )
        bp = BlueprintIR(parent_class=None, functions=[func], events=[], components=[])
        ir = _make_minimal_ir(blueprint=bp)
        data = _render_json(ir)
        f = data["blueprint"]["functions"][0]
        assert f["function_flags"] == 0x00000400
        assert f["is_pure"] is True
        assert f["is_const"] is True
        assert f["meta_data"] == {"Category": "Health"}

    def test_event_override_fields_in_json(self):
        """事件 override 字段应出现在 JSON 中。"""
        evt = BlueprintEventIR(
            name="ReceiveBeginPlay", event_type="Event", parameters=[],
            is_override=True,
            override_parent_class="/Script/Engine.Actor",
            override_parent_event="ReceiveBeginPlay",
            is_interface_event=False,
        )
        bp = BlueprintIR(parent_class=None, functions=[], events=[evt], components=[])
        ir = _make_minimal_ir(blueprint=bp)
        data = _render_json(ir)
        e = data["blueprint"]["events"][0]
        assert e["is_override"] is True
        assert e["override_parent_class"] == "/Script/Engine.Actor"

    def test_function_false_flags_omitted(self):
        """函数布尔标志为 False 时不应出现在 JSON 中。"""
        func = BlueprintFunctionIR(name="F", return_type="void", parameters=[])
        bp = BlueprintIR(parent_class=None, functions=[func], events=[], components=[])
        ir = _make_minimal_ir(blueprint=bp)
        data = _render_json(ir)
        f = data["blueprint"]["functions"][0]
        assert "is_pure" not in f
        assert "is_static" not in f
        assert "is_net" not in f


# ===========================================================================
# 父资产字段测试
# ===========================================================================

class TestParentAssetFields:
    """验证父资产字段完整输出。"""

    def test_parent_assets_in_ir(self):
        """PackageIR 应包含父资产字段。"""
        ir = _make_minimal_ir(
            resolved_parent_assets=[{"class": "ParentBP", "path": "/Game/ParentBP.uasset", "status": "parsed"}],
            logic_sources=[{"source": "current_asset", "asset": "/Game/Test/BP_Test.uasset"}],
            inherited_blueprint_graphs=[{"graph_name": "EventGraph", "nodes": []}],
        )
        assert len(ir.resolved_parent_assets) == 1
        assert ir.resolved_parent_assets[0]["class"] == "ParentBP"
        assert len(ir.logic_sources) == 1
        assert len(ir.inherited_blueprint_graphs) == 1

    def test_parent_assets_in_json(self):
        """父资产字段应出现在 JSON 输出中。"""
        ir = _make_minimal_ir(
            resolved_parent_assets=[{"class": "ParentBP", "path": "/Game/ParentBP.uasset", "status": "parsed"}],
            logic_sources=[{"source": "current_asset", "asset": "/Game/Test/BP_Test.uasset"}],
            inherited_blueprint_graphs=[{"graph_name": "EventGraph", "nodes": []}],
        )
        data = _render_json(ir)
        assert "resolved_parent_assets" in data
        assert len(data["resolved_parent_assets"]) == 1
        assert data["resolved_parent_assets"][0]["class"] == "ParentBP"
        assert "logic_sources" in data
        assert "inherited_blueprint_graphs" in data

    def test_parent_assets_empty_not_in_json(self):
        """空父资产字段不应出现在 JSON 中。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "resolved_parent_assets" not in data
        assert "logic_sources" not in data
        assert "inherited_blueprint_graphs" not in data


# ===========================================================================
# IR 构建器集成测试
# ===========================================================================

class TestIRBuilderIntegration:
    """验证 ir_builder 从 mock ParseResult 正确构建完整 IR。"""

    def test_full_build_with_blueprint(self):
        """完整构建：变量 + 函数 + 事件 + 实现关联。"""
        from uasset_read.models.blueprint import (
            BlueprintFunction,
            BlueprintMetadata,
            BlueprintVariable,
        )
        from uasset_read.models.core import FEdGraphPinType

        var = BlueprintVariable(
            var_name="Speed",
            var_type=FEdGraphPinType(pin_category="float"),
            category="float",
            var_guid="A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
            default_value="600.0",
            friendly_name="Speed",
            is_edit_anywhere=True,
        )
        func = BlueprintFunction(
            name="Fire",
            return_type="void",
            is_blueprint_callable=True,
        )

        from uasset_read.models.result import ParseResult

        result = ParseResult(
            summary=SimpleNamespace(
                package_name="/Game/Test/BP_Test",
                package_class="BP_Test_C",
                package_flags=0,
                export_count=1,
                import_count=1,
                saved_hash=b"",
                depends_map=[],
                asset_registry_data_offset=0,
            ),
            name_map=["BP_Test"],
            is_success=True,
        )

        result.blueprint = BlueprintMetadata(
            is_blueprint=True,
            parent_class="/Script/Engine.Character",
            functions=[func],
            variables=[var],
        )

        ir = build_package_ir(result)

        # 验证变量
        assert len(ir.variables) == 1
        assert ir.variables[0].name == "Speed"
        assert ir.variables[0].type == "float"
        assert ir.variables[0].default_value == "600.0"
        assert ir.variables[0].guid == "a1b2c3d4e5f67890abcdef1234567890"

        # 验证函数
        assert ir.blueprint is not None
        assert len(ir.blueprint.functions) == 1
        assert ir.blueprint.functions[0].name == "Fire"
        assert ir.blueprint.functions[0].is_blueprint_callable is True

        # 验证 JSON 输出
        data = _render_json(ir)
        assert "variables" in data
        assert data["variables"][0]["name"] == "Speed"
        assert "blueprint" in data
        assert data["blueprint"]["functions"][0]["implementation_status"] == "missing"


# ===========================================================================
# errors 字段测试
# ===========================================================================

class TestOutputVersionAndErrors:
    """验证 JSON 输出不包含 output_version，errors 字段正确。"""

    def test_json_no_output_version(self):
        """JSON 完整输出不应包含 output_version。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "output_version" not in data

    def test_json_has_errors_when_present(self):
        """有错误时 JSON 应包含 errors 数组。"""
        ir = _make_minimal_ir(errors=["Parse failed at offset 0x100"])
        data = _render_json(ir)
        assert "errors" in data
        assert data["errors"] == ["Parse failed at offset 0x100"]

    def test_json_no_errors_when_empty(self):
        """无错误时 JSON 不应包含 errors 字段。"""
        ir = _make_minimal_ir(errors=[])
        data = _render_json(ir)
        assert "errors" not in data

    def test_components_in_blueprint(self):
        """组件应通过 blueprint.components 输出。"""
        bp = BlueprintIR(
            parent_class="/Script/Engine.Character",
            functions=[],
            events=[],
            components=[{"name": "Mesh", "class": "SkeletalMeshComponent", "properties": {}, "transforms": {}}],
        )
        ir = _make_minimal_ir(blueprint=bp)
        data = _render_json(ir)
        assert "blueprint" in data
        assert data["blueprint"]["components"] == [{"name": "Mesh", "class": "SkeletalMeshComponent", "properties": {}, "transforms": {}}]


# ===========================================================================
# 格式契约测试 — 所有格式处理同一 IR 不崩溃
# ===========================================================================

class TestFormatFieldContracts:
    """验证所有注册格式都能处理完整 PackageIR 而不崩溃。"""

    def _make_full_ir(self) -> PackageIR:
        """构造包含所有字段的 PackageIR。"""
        diag = MagicMock()
        diag.to_dict.return_value = {"kind": "test", "offset": 0}
        return PackageIR(
            header=_make_header(),
            name_map=["Test"],
            imports=[{"class_package": "Engine", "class_name": "Actor", "object_name": "Actor"}],
            exports=[ExportIR(
                index=0, object_name="Test", object_class="Blueprint",
                serial_size=100, outer_index_resolved=None, super_index_resolved=None,
                parent_class=None,
                properties=[PropertyIR(name="X", type="float", value="1.0", array_index=0, guid=None)],
                graphs=[], bulk_data=None,
            )],
            linker=None,
            blueprint=BlueprintIR(
                parent_class="/Script/Engine.Character",
                functions=[BlueprintFunctionIR(name="F", return_type="void", parameters=[], is_pure=True)],
                events=[BlueprintEventIR(name="E", event_type="Event", parameters=[], is_override=True)],
                components=[{"name": "M", "class": "C", "properties": {}, "transforms": {}}],
            ),
            decompiled_functions=[DecompiledFunctionIR(name="F", signature="void F()", cpp_code="void F(){}", parameters=[], return_type="void")],
            execution_chains=[ExecutionChainIR(event="BeginPlay", chain=["F"])],
            variables=[VariableIR(name="Health", type="float", default_value="100.0", kind="user", is_edit_anywhere=True)],
            diagnostics=[diag],
            function_graphs=[{"function_name": "F", "graph_source": "F"}],
            resolved_parent_assets=[{"class": "P", "path": "/P"}],
            inherited_blueprint_graphs=[{"graph_name": "G"}],
            logic_sources=[{"source": "s"}],
            errors=["test error"],
            status="partial",
            status_message="test error",
            status_code="PARSE_ERROR",
        )

    @pytest.mark.parametrize("format_name", [
        "json", "markdown",
    ])
    def test_format_handles_full_ir(self, format_name):
        """所有格式应能处理包含所有字段的 PackageIR 而不崩溃。"""
        from uasset_read.renderers import get_renderer
        ir = self._make_full_ir()
        renderer = get_renderer(format_name)
        options = RenderOptions()
        output = renderer.render(ir, options)
        assert isinstance(output, str)
        assert len(output) > 0
