"""IR 数据结构单元测试。"""
import pytest
from dataclasses import fields
from uasset_read.models.ir import (
    PackageHeaderIR,
    PinIR,
    NodeIR,
    GraphIR,
    PropertyIR,
    ExportIR,
    LinkerSummaryIR,
    PackageIR,
)


class TestPinIR:
    def test_pin_ir_minimal(self):
        pin = PinIR(pin_name="Exec", pin_type="exec", pin_type_value=None,
                    linked_to=[], direction="EGPD_Output", default_value=None)
        assert pin.pin_name == "Exec"
        assert pin.linked_to == []

    def test_pin_ir_full(self):
        pin = PinIR(pin_name="Target", pin_type="Object", pin_type_value="Actor",
                    linked_to=["abc123def456789012345678abcdef01"], direction="EGPD_Input",
                    default_value="SomeValue")
        assert len(pin.linked_to) == 1
        assert pin.default_value == "SomeValue"


class TestNodeIR:
    def test_node_ir_minimal(self):
        node = NodeIR(node_guid="0" * 32, node_class="K2Node_Event",
                      node_comment=None, pins=[], execution_flow=[])
        assert node.node_guid == "0" * 32
        assert node.pins == []

    def test_node_ir_with_comment(self):
        node = NodeIR(node_guid="a" * 32, node_class="K2Node_Comment",
                      node_comment="My Note", pins=[], execution_flow=[])
        assert node.node_comment == "My Note"


class TestGraphIR:
    def test_graph_ir_minimal(self):
        g = GraphIR(graph_guid="0" * 32, graph_name="EventGraph",
                    graph_class="EdGraph", nodes=[], execution_chains=[])
        assert g.graph_name == "EventGraph"


class TestPropertyIR:
    def test_property_ir_minimal(self):
        p = PropertyIR(name="Health", type="FloatProperty", value=100.0,
                       array_index=-1, guid=None)
        assert p.name == "Health"
        assert p.value == 100.0


class TestExportIR:
    def test_export_ir_minimal(self):
        e = ExportIR(index=0, object_name="Default__BP_Test_C",
                     object_class="BlueprintGeneratedClass", serial_size=100,
                     outer_index_resolved=None, super_index_resolved=None,
                     parent_class=None, properties=[], graphs=[], bulk_data=None)
        assert e.index == 0
        assert e.graphs == []
        assert e.bulk_data is None


class TestPackageIR:
    def test_package_ir_minimal(self):
        header = PackageHeaderIR(
            package_name="/Game/Test/BP_Test", package_class="BP_Test_C",
            package_flags=0, total_export_count=1, total_import_count=1,
            ue_version="5.x")
        ir = PackageIR(header=header, name_map=["BP_Test"], imports=[],
                       exports=[], linker=None)
        assert ir.header.package_name == "/Game/Test/BP_Test"
        assert len(ir.exports) == 0


class TestLinkerSummaryIR:
    def test_linker_summary_ir(self):
        ls = LinkerSummaryIR(has_linker=True, import_paths=["/Engine/Core"],
                             export_paths=["/Game/Test"])
        assert ls.has_linker is True
        assert len(ls.import_paths) == 1
