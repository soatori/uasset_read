"""IR 构建器测试 — build_package_ir 从 ParseResult 到 PackageIR 的转换。

合并来源：
  - test_export_dependency.py
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from uasset_read.ir_builder import (
    build_package_ir,
    _build_header,
    _build_imports,
    _build_exports,
    _normalize_guid,
    _extract_pin_guid,
    _safe_str,
    _build_property_ir,
    _build_graph_ir,
    _build_node_ir,
    _build_pin_ir,
    _resolve_package_index,
    _build_linker,
)
from uasset_read.models.ir import (
    PackageIR, ExportIR, PackageHeaderIR, GraphIR, NodeIR, PinIR,
    PropertyIR, LinkerSummaryIR, ExportDependencyIR,
)


def _make_mock_parse_result():
    """创建最小 Mock ParseResult。"""
    result = MagicMock()
    result.summary.package_name = "/Game/Test/BP_Test"
    result.summary.package_class = "BP_Test_C"
    result.summary.package_flags = 0
    result.summary.total_export_count = 1
    result.summary.total_import_count = 1
    result.name_map = ["BP_Test", "SomeName"]
    result.import_map = []
    result.export_map = []
    result.linker = None
    result.blueprint = None
    result.version_container = None
    result.errors = []
    result.warnings = []
    result.is_success = True
    return result


class TestNormalizeGuid:
    def test_valid_guid_with_dashes(self):
        result = _normalize_guid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890")
        assert result == "a1b2c3d4e5f67890abcdef1234567890"

    def test_valid_guid_already_clean(self):
        result = _normalize_guid("a1b2c3d4e5f67890abcdef1234567890")
        assert result == "a1b2c3d4e5f67890abcdef1234567890"

    def test_none_returns_none(self):
        assert _normalize_guid(None) is None

    def test_empty_returns_none(self):
        assert _normalize_guid("") is None

    def test_invalid_length_returns_none(self):
        assert _normalize_guid("abc") is None

    def test_invalid_chars_returns_none(self):
        assert _normalize_guid("ZZZZZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZZZZZZZZZ") is None


class TestSafeStr:
    def test_none_returns_empty(self):
        assert _safe_str(None) == ""

    def test_string_passthrough(self):
        assert _safe_str("hello") == "hello"

    def test_int_converts(self):
        assert _safe_str(42) == "42"


class TestExtractPinGuid:
    def test_dict_with_pin_guid(self):
        ref = {"pin_guid": "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"}
        assert _extract_pin_guid(ref) == "a1b2c3d4e5f67890abcdef1234567890"

    def test_dict_with_pin_id_fallback(self):
        ref = {"pin_id": "A1B2C3D4E5F67890ABCDEF1234567890"}
        assert _extract_pin_guid(ref) == "a1b2c3d4e5f67890abcdef1234567890"

    def test_string_direct(self):
        assert _extract_pin_guid("A1B2C3D4E5F67890ABCDEF1234567890") == "a1b2c3d4e5f67890abcdef1234567890"

    def test_object_with_pin_guid_attr(self):
        obj = MagicMock()
        obj.pin_guid = "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"
        obj.pin_id = None
        assert _extract_pin_guid(obj) == "a1b2c3d4e5f67890abcdef1234567890"

    def test_invalid_dict_returns_none(self):
        assert _extract_pin_guid({"other_key": "value"}) is None


class TestBuildPackageIR:
    def test_build_minimal_result(self):
        result = _make_mock_parse_result()
        ir = build_package_ir(result)
        assert isinstance(ir, PackageIR)
        assert ir.header.package_name == "/Game/Test/BP_Test"
        assert ir.header.package_class == "BP_Test_C"
        assert ir.name_map == ("BP_Test", "SomeName")
        assert ir.exports == []
        assert ir.imports == []
        assert ir.linker is None

    def test_build_with_ue5_version(self):
        result = _make_mock_parse_result()
        mock_vc = MagicMock()
        mock_vc.is_ue5 = True
        mock_vc.get_ue_version_string = None
        result.version_container = mock_vc
        ir = build_package_ir(result)
        assert ir.header.ue_version == "5.x"

    def test_build_with_ue4_version(self):
        result = _make_mock_parse_result()
        mock_vc = MagicMock()
        mock_vc.is_ue5 = False
        mock_vc.get_ue_version_string = None
        result.version_container = mock_vc
        ir = build_package_ir(result)
        assert ir.header.ue_version == "4.x"

    def test_build_with_version_string_method(self):
        result = _make_mock_parse_result()
        mock_vc = MagicMock()
        mock_vc.get_ue_version_string.return_value = "5.3"
        result.version_container = mock_vc
        ir = build_package_ir(result)
        assert ir.header.ue_version == "5.3"

    def test_build_with_no_version_container(self):
        result = _make_mock_parse_result()
        result.version_container = None
        ir = build_package_ir(result)
        assert ir.header.ue_version == "unknown"

    def test_build_with_exports(self):
        result = _make_mock_parse_result()
        mock_export = MagicMock()
        mock_export.object_name = "Default__BP_Test_C"
        mock_export.object_class = "BlueprintGeneratedClass"
        mock_export.serial_size = 100
        mock_export.outer_index = None
        mock_export.super_index = None
        mock_export.properties = []
        mock_export.graphs = []
        mock_export.bulk_data_header = None
        result.export_map = [mock_export]

        ir = build_package_ir(result)
        assert len(ir.exports) == 1
        assert ir.exports[0].object_name == "Default__BP_Test_C"
        assert ir.exports[0].object_class == "BlueprintGeneratedClass"
        assert ir.exports[0].serial_size == 100

    def test_build_with_imports(self):
        result = _make_mock_parse_result()
        mock_import = MagicMock()
        mock_import.class_package = "/Script/Engine"
        mock_import.class_name = "Actor"
        mock_import.object_name = "MyActor"
        result.import_map = [mock_import]

        ir = build_package_ir(result)
        assert len(ir.imports) == 1
        assert ir.imports[0].class_package == "/Script/Engine"
        assert ir.imports[0].class_name == "Actor"
        assert ir.imports[0].object_name == "MyActor"

    def test_build_with_linker(self):
        result = _make_mock_parse_result()
        mock_linker = MagicMock()
        result.linker = mock_linker
        result.import_map = []
        result.export_map = []

        ir = build_package_ir(result)
        assert ir.linker is not None
        assert ir.linker.has_linker is True

    def test_failed_export_is_skipped(self):
        result = _make_mock_parse_result()
        mock_export = MagicMock()
        # 让 outer_index 属性访问时抛异常
        type(mock_export).outer_index = property(
            lambda self: (_ for _ in ()).throw(ValueError("broken"))
        )
        result.export_map = [mock_export]

        ir = build_package_ir(result)
        # 失败 export 被跳过
        assert len(ir.exports) == 0

    def test_linker_summary_has_paths(self):
        result = _make_mock_parse_result()
        mock_linker = MagicMock()
        result.linker = mock_linker

        mock_import = MagicMock()
        mock_import.class_package = "/Script/Engine"
        mock_import.class_name = "Actor"
        mock_import.object_name = "Actor"
        result.import_map = [mock_import]

        mock_export = MagicMock()
        mock_export.object_name = "BP_Test_C"
        mock_export.object_class = "BlueprintGeneratedClass"
        mock_export.serial_size = 0
        mock_export.outer_index = None
        mock_export.super_index = None
        mock_export.properties = []
        mock_export.graphs = []
        mock_export.bulk_data_header = None
        result.export_map = [mock_export]

        ir = build_package_ir(result)
        assert ir.linker is not None
        assert "/Script/Engine.Actor" in ir.linker.import_paths
        assert "BP_Test_C" in ir.linker.export_paths


class TestBuildGraphIR:
    def test_graph_with_guid_normalization(self):
        mock_graph = MagicMock()
        mock_graph.graph_guid = "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"
        mock_graph.graph_name = "EventGraph"
        mock_graph.graph_class = "EdGraph"
        mock_graph.nodes = []
        mock_graph.execution_chains = []

        graph_ir = _build_graph_ir(mock_graph)
        assert isinstance(graph_ir, GraphIR)
        assert graph_ir.graph_guid == "a1b2c3d4e5f67890abcdef1234567890"
        assert graph_ir.graph_name == "EventGraph"
        assert graph_ir.nodes == []

    def test_graph_with_nodes(self):
        mock_graph = MagicMock()
        mock_graph.graph_guid = "a1b2c3d4e5f67890abcdef1234567890"
        mock_graph.graph_name = "EventGraph"
        mock_graph.graph_class = "EdGraph"
        mock_graph.nodes = []
        mock_graph.execution_chains = [["node_a", "node_b"]]

        mock_node = MagicMock()
        mock_node.node_guid = "b1b2c3d4e5f67890abcdef1234567890"
        mock_node.class_name = "K2Node_Event"
        mock_node.node_comment = "My Event"
        mock_node.pins = []
        mock_node.execution_flow = []
        mock_graph.nodes = [mock_node]

        graph_ir = _build_graph_ir(mock_graph)
        assert len(graph_ir.nodes) == 1
        assert graph_ir.nodes[0].node_class == "K2Node_Event"
        assert graph_ir.nodes[0].node_comment == "My Event"
        assert graph_ir.execution_chains == [["node_a", "node_b"]]


class TestBuildNodeIR:
    def test_node_with_pins(self):
        mock_node = MagicMock()
        mock_node.node_guid = "a1b2c3d4e5f67890abcdef1234567890"
        mock_node.class_name = "K2Node_CallFunction"
        mock_node.node_comment = None
        mock_node.execution_flow = []
        mock_node.pins = []

        mock_pin = MagicMock()
        mock_pin.pin_name = "Exec"
        mock_pin.pin_type = "exec"
        mock_pin.linked_to_raw = []
        mock_pin.direction = 1  # Output
        mock_pin.default_value = None
        mock_node.pins = [mock_pin]

        node_ir = _build_node_ir(mock_node)
        assert isinstance(node_ir, NodeIR)
        assert len(node_ir.pins) == 1
        assert node_ir.pins[0].direction == "EGPD_Output"


class TestBuildPinIR:
    def test_pin_input_direction(self):
        mock_pin = MagicMock()
        mock_pin.pin_name = "Target"
        mock_pin.pin_type = MagicMock()
        mock_pin.pin_type.pin_category = "object"
        mock_pin.pin_type.pin_subcategory = ""
        mock_pin.pin_type.pin_subcategory_object_name = "Actor"
        mock_pin.pin_type.container_type = 0
        mock_pin.pin_type.is_reference = False
        mock_pin.pin_type.is_const = False
        mock_pin.pin_type.is_weak_pointer = False
        mock_pin.pin_type.is_uobject_wrapper = False
        mock_pin.pin_type.is_map_key = False
        mock_pin.pin_type.is_map_value = False
        mock_pin.linked_to_raw = []
        mock_pin.direction = 0  # Input
        mock_pin.default_value = None

        pin_ir = _build_pin_ir(mock_pin)
        assert pin_ir.direction == "EGPD_Input"
        assert pin_ir.pin_name == "Target"
        assert pin_ir.pin_category == "object"
        assert pin_ir.pin_subcategory_object_name == "Actor"
        assert pin_ir.container_type == "None"

    def test_pin_linked_to_raw_dicts(self):
        mock_pin = MagicMock()
        mock_pin.pin_name = "Exec"
        mock_pin.pin_type = MagicMock()
        mock_pin.pin_type.pin_category = "exec"
        mock_pin.pin_type.pin_subcategory = ""
        mock_pin.pin_type.pin_subcategory_object_name = None
        mock_pin.pin_type.container_type = 0
        mock_pin.pin_type.is_reference = False
        mock_pin.pin_type.is_const = False
        mock_pin.pin_type.is_weak_pointer = False
        mock_pin.pin_type.is_uobject_wrapper = False
        mock_pin.pin_type.is_map_key = False
        mock_pin.pin_type.is_map_value = False
        mock_pin.linked_to_raw = [
            {"pin_guid": "a1b2c3d4e5f67890abcdef1234567890"},
            {"pin_guid": "b1b2c3d4e5f67890abcdef1234567890"},
        ]
        mock_pin.direction = 0
        mock_pin.default_value = None

        pin_ir = _build_pin_ir(mock_pin)
        assert len(pin_ir.linked_to) == 2
        assert pin_ir.linked_to[0] == "a1b2c3d4e5f67890abcdef1234567890"

    def test_pin_linked_to_raw_strings(self):
        mock_pin = MagicMock()
        mock_pin.pin_name = "Exec"
        mock_pin.pin_type = MagicMock()
        mock_pin.pin_type.pin_category = "exec"
        mock_pin.pin_type.pin_subcategory = ""
        mock_pin.pin_type.pin_subcategory_object_name = None
        mock_pin.pin_type.container_type = 0
        mock_pin.pin_type.is_reference = False
        mock_pin.pin_type.is_const = False
        mock_pin.pin_type.is_weak_pointer = False
        mock_pin.pin_type.is_uobject_wrapper = False
        mock_pin.pin_type.is_map_key = False
        mock_pin.pin_type.is_map_value = False
        mock_pin.linked_to_raw = ["a1b2c3d4e5f67890abcdef1234567890"]
        mock_pin.direction = 0
        mock_pin.default_value = None

        pin_ir = _build_pin_ir(mock_pin)
        assert len(pin_ir.linked_to) == 1

    def test_pin_structured_type_fields(self):
        """测试 FEdGraphPinType 结构化字段正确提取。"""
        mock_pin = MagicMock()
        mock_pin.pin_name = "Value"
        mock_pin.pin_type = MagicMock()
        mock_pin.pin_type.pin_category = "struct"
        mock_pin.pin_type.pin_subcategory = ""
        mock_pin.pin_type.pin_subcategory_object_name = "/Script/Engine.Vector"
        mock_pin.pin_type.container_type = 1  # Array
        mock_pin.pin_type.is_reference = True
        mock_pin.pin_type.is_const = False
        mock_pin.pin_type.is_weak_pointer = False
        mock_pin.pin_type.is_uobject_wrapper = False
        mock_pin.pin_type.is_map_key = False
        mock_pin.pin_type.is_map_value = False
        mock_pin.linked_to_raw = []
        mock_pin.direction = 1  # Output
        mock_pin.default_value = None

        pin_ir = _build_pin_ir(mock_pin)
        assert pin_ir.pin_category == "struct"
        assert pin_ir.pin_subcategory_object_name == "/Script/Engine.Vector"
        assert pin_ir.container_type == "Array"
        assert pin_ir.is_reference is True
        assert pin_ir.is_const is False

    def test_pin_map_container(self):
        """测试 Map 容器类型的 pin 提取。"""
        mock_pin = MagicMock()
        mock_pin.pin_name = "MapPin"
        mock_pin.pin_type = MagicMock()
        mock_pin.pin_type.pin_category = "struct"
        mock_pin.pin_type.pin_subcategory = ""
        mock_pin.pin_type.pin_subcategory_object_name = None
        mock_pin.pin_type.container_type = 3  # Map
        mock_pin.pin_type.is_reference = False
        mock_pin.pin_type.is_const = False
        mock_pin.pin_type.is_weak_pointer = False
        mock_pin.pin_type.is_uobject_wrapper = False
        mock_pin.pin_type.is_map_key = True
        mock_pin.pin_type.is_map_value = False
        mock_pin.linked_to_raw = []
        mock_pin.direction = 0
        mock_pin.default_value = None

        pin_ir = _build_pin_ir(mock_pin)
        assert pin_ir.container_type == "Map"
        assert pin_ir.is_map_key is True
        assert pin_ir.is_map_value is False

    def test_pin_none_pin_type(self):
        """测试 pin_type 为 None 时的降级处理。"""
        mock_pin = MagicMock()
        mock_pin.pin_name = "Broken"
        mock_pin.pin_type = None
        mock_pin.linked_to_raw = []
        mock_pin.direction = 0
        mock_pin.default_value = None

        pin_ir = _build_pin_ir(mock_pin)
        assert pin_ir.pin_category == ""
        assert pin_ir.container_type == "None"
        assert pin_ir.is_reference is False

    def test_pin_backward_compat_string_pin_type(self):
        """测试 pin_type 为字符串时的向后兼容（旧数据）。"""
        mock_pin = MagicMock()
        mock_pin.pin_name = "Legacy"
        mock_pin.pin_type = "Object"
        mock_pin.linked_to_raw = []
        mock_pin.direction = 0
        mock_pin.default_value = None

        pin_ir = _build_pin_ir(mock_pin)
        assert pin_ir.pin_type == "Object"
        assert pin_ir.pin_category == ""


class TestBuildPropertyIR:
    def test_property_ir_basic(self):
        mock_prop = MagicMock()
        mock_prop.name = "DisplayName"
        mock_prop.type = "StrProperty"
        mock_prop.value = "TestValue"
        mock_prop.array_index = 0
        mock_prop.guid = "A1B2C3D4E5F67890ABCDEF1234567890"

        prop_ir = _build_property_ir(mock_prop)
        assert isinstance(prop_ir, PropertyIR)
        assert prop_ir.name == "DisplayName"
        assert prop_ir.type == "StrProperty"
        assert prop_ir.value == "TestValue"
        assert prop_ir.guid == "a1b2c3d4e5f67890abcdef1234567890"


class TestResolvePackageIndex:
    def test_none_linker_returns_none(self):
        result = _make_mock_parse_result()
        result.linker = None
        mock_pkg_index = MagicMock()
        assert _resolve_package_index(result, mock_pkg_index) is None

    def test_none_index_returns_none(self):
        result = _make_mock_parse_result()
        result.linker = MagicMock()
        assert _resolve_package_index(result, None) is None

    def test_resolved_uses_get_full_name(self):
        result = _make_mock_parse_result()
        mock_linker = MagicMock()
        mock_obj = MagicMock()
        mock_obj.get_full_name.return_value = "/Script/Engine.Actor"
        mock_linker.resolve_package_index.return_value = mock_obj
        result.linker = mock_linker

        mock_pkg_index = MagicMock()
        resolved = _resolve_package_index(result, mock_pkg_index)
        assert resolved == "/Script/Engine.Actor"

    def test_exception_returns_none(self):
        result = _make_mock_parse_result()
        mock_linker = MagicMock()
        mock_linker.resolve_package_index.side_effect = ValueError("fail")
        result.linker = mock_linker

        mock_pkg_index = MagicMock()
        assert _resolve_package_index(result, mock_pkg_index) is None


class TestExportIRWithGraphs:
    def test_export_with_graphs_and_nodes(self):
        result = _make_mock_parse_result()

        mock_graph = MagicMock()
        mock_graph.graph_guid = "a1b2c3d4e5f67890abcdef1234567890"
        mock_graph.graph_name = "EventGraph"
        mock_graph.graph_class = "EdGraph"
        mock_graph.execution_chains = []

        mock_node = MagicMock()
        mock_node.node_guid = "b1b2c3d4e5f67890abcdef1234567890"
        mock_node.class_name = "K2Node_Event"
        mock_node.node_comment = None
        mock_node.execution_flow = []
        mock_node.pins = []
        mock_graph.nodes = [mock_node]

        mock_export = MagicMock()
        mock_export.object_name = "BP_Test_C"
        mock_export.object_class = "BlueprintGeneratedClass"
        mock_export.serial_size = 500
        mock_export.outer_index = None
        mock_export.super_index = None
        mock_export.properties = []
        mock_export.graphs = [mock_graph]
        mock_export.bulk_data_header = None
        result.export_map = [mock_export]

        ir = build_package_ir(result)
        assert len(ir.exports) == 1
        assert len(ir.exports[0].graphs) == 1
        assert ir.exports[0].graphs[0].graph_name == "EventGraph"
        assert len(ir.exports[0].graphs[0].nodes) == 1


# ===========================================================================
# IR 数据结构单元测试（原 test_ir_structures.py）
# ===========================================================================

from dataclasses import fields
from uasset_read.models.ir import (
    PackageHeaderIR as PackageHeaderIRStruct,
    PinIR as PinIRStruct,
    NodeIR as NodeIRStruct,
    GraphIR as GraphIRStruct,
    PropertyIR as PropertyIRStruct,
    ExportIR as ExportIRStruct,
    LinkerSummaryIR as LinkerSummaryIRStruct,
    PackageIR as PackageIRStruct,
)


class TestPinIR:
    def test_pin_ir_minimal(self):
        pin = PinIRStruct(pin_name="Exec", pin_type="exec",
                    linked_to=[], direction="EGPD_Output", default_value=None)
        assert pin.pin_name == "Exec"
        assert pin.linked_to == []
        # 新字段默认值
        assert pin.pin_category == ""
        assert pin.container_type == "None"
        assert pin.is_reference is False

    def test_pin_ir_full(self):
        pin = PinIRStruct(
            pin_name="Target", pin_type="Object",
            linked_to=["abc123def456789012345678abcdef01"],
            direction="EGPD_Input", default_value="SomeValue",
            pin_category="object", pin_subcategory="",
            pin_subcategory_object_name="/Script/Engine.Actor",
            container_type="None", is_reference=False,
            is_const=False, is_weak_pointer=False,
            is_uobject_wrapper=False, is_map_key=False, is_map_value=False,
        )
        assert len(pin.linked_to) == 1
        assert pin.default_value == "SomeValue"
        assert pin.pin_category == "object"
        assert pin.pin_subcategory_object_name == "/Script/Engine.Actor"
        assert pin.container_type == "None"

    def test_pin_ir_container_array(self):
        """测试 TArray 容器类型的 PinIR。"""
        pin = PinIRStruct(
            pin_name="ArrayPin", pin_type="Array<int>",
            linked_to=[], direction="EGPD_Input", default_value=None,
            pin_category="int", container_type="Array",
        )
        assert pin.container_type == "Array"
        assert pin.pin_category == "int"

    def test_pin_ir_map_container(self):
        """测试 TMap 容器类型的 PinIR。"""
        pin = PinIRStruct(
            pin_name="MapPin", pin_type="Map",
            linked_to=[], direction="EGPD_Input", default_value=None,
            pin_category="struct", container_type="Map",
            is_map_key=True, is_map_value=False,
        )
        assert pin.container_type == "Map"
        assert pin.is_map_key is True


class TestNodeIR:
    def test_node_ir_minimal(self):
        node = NodeIRStruct(node_guid="0" * 32, node_class="K2Node_Event",
                      node_comment=None, pins=[], execution_flow=[])
        assert node.node_guid == "0" * 32
        assert node.pins == []

    def test_node_ir_with_comment(self):
        node = NodeIRStruct(node_guid="a" * 32, node_class="K2Node_Comment",
                      node_comment="My Note", pins=[], execution_flow=[])
        assert node.node_comment == "My Note"


class TestGraphIR:
    def test_graph_ir_minimal(self):
        g = GraphIRStruct(graph_guid="0" * 32, graph_name="EventGraph",
                    graph_class="EdGraph", nodes=[], execution_chains=[])
        assert g.graph_name == "EventGraph"


class TestPropertyIR:
    def test_property_ir_minimal(self):
        p = PropertyIRStruct(name="Health", type="FloatProperty", value=100.0,
                       array_index=-1, guid=None)
        assert p.name == "Health"
        assert p.value == 100.0


class TestExportIR:
    def test_export_ir_minimal(self):
        e = ExportIRStruct(index=0, object_name="Default__BP_Test_C",
                     object_class="BlueprintGeneratedClass", serial_size=100,
                     outer_index_resolved=None, super_index_resolved=None,
                     parent_class=None, properties=[], graphs=[], bulk_data=None)
        assert e.index == 0
        assert e.graphs == []
        assert e.bulk_data is None


class TestPackageIR:
    def test_package_ir_minimal(self):
        header = PackageHeaderIRStruct(
            package_name="/Game/Test/BP_Test", package_class="BP_Test_C",
            package_flags=0, total_export_count=1, total_import_count=1,
            ue_version="5.x")
        ir = PackageIRStruct(header=header, name_map=["BP_Test"], imports=[],
                       exports=[], linker=None)
        assert ir.header.package_name == "/Game/Test/BP_Test"
        assert len(ir.exports) == 0


class TestLinkerSummaryIR:
    def test_linker_summary_ir(self):
        ls = LinkerSummaryIRStruct(has_linker=True, import_paths=["/Engine/Core"],
                             export_paths=["/Game/Test"])
        assert ls.has_linker is True
        assert len(ls.import_paths) == 1


# ===========================================================================
# ExportDependencyIR 数据结构测试（原 test_export_dependency.py）
# ===========================================================================

def test_export_dependency_ir_basic():
    """测试 ExportDependencyIR 基本创建和字段访问"""
    ir = ExportDependencyIR(
        export_index=0,
        serialization_before_serialization=[1, 2],
        create_before_serialization=[3],
        serialization_before_create=[],
        create_before_create=[4]
    )
    assert ir.export_index == 0
    assert len(ir.serialization_before_serialization) == 2
    assert ir.serialization_before_serialization == [1, 2]
    assert ir.create_before_serialization == [3]
    assert ir.serialization_before_create == []
    assert ir.create_before_create == [4]


def test_export_dependency_ir_empty_dependencies():
    """测试所有依赖列表为空的情况"""
    ir = ExportDependencyIR(
        export_index=5,
        serialization_before_serialization=[],
        create_before_serialization=[],
        serialization_before_create=[],
        create_before_create=[]
    )
    assert ir.export_index == 5
    assert len(ir.serialization_before_serialization) == 0
    assert len(ir.create_before_serialization) == 0
    assert len(ir.serialization_before_create) == 0
    assert len(ir.create_before_create) == 0


def test_export_dependency_ir_multiple_dependencies():
    """测试多个依赖的情况"""
    ir = ExportDependencyIR(
        export_index=10,
        serialization_before_serialization=[0, 1, 2, 3],
        create_before_serialization=[4, 5],
        serialization_before_create=[6, 7, 8],
        create_before_create=[9]
    )
    assert ir.export_index == 10
    assert len(ir.serialization_before_serialization) == 4
    assert len(ir.create_before_serialization) == 2
    assert len(ir.serialization_before_create) == 3
    assert len(ir.create_before_create) == 1
