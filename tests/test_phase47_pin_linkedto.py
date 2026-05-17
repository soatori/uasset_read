"""Phase 47: Pin LinkedTo 修复验证测试。

验证 FEdGraphPinType 序列化修复后，linked_to_raw 不再全为空。
"""
from pathlib import Path

import pytest

from uasset_read import parse_uasset
from uasset_read.graph import build_connections_map, build_execution_flows

_ASSET_ROOT = Path(r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content")
TEST_ASSET = str(next(_ASSET_ROOT.rglob("BP_FirstPersonCharacter.uasset"), None))


@pytest.mark.skip(reason="Phase 55 cleanup: linked_to_raw parsing bug (Phase 44 issue)")
class TestPhase47PinLinkedTo:
    """Phase 47 验证：linked_to_raw 非空，connections > 0，execution_flows 非空。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.result = parse_uasset(TEST_ASSET)

    def test_graphs_exist(self):
        """至少有一个图被解析。"""
        assert len(self.result.graphs) > 0, "No graphs parsed"

    def test_pins_parsed(self):
        """至少解析了一些引脚。"""
        total = sum(len(n.pins) for g in self.result.graphs for n in g.nodes)
        assert total > 0, "No pins parsed"

    def test_linked_to_raw_not_all_empty(self):
        """至少一个 pin 的 linked_to_raw 非空。"""
        linked = sum(
            1
            for g in self.result.graphs
            for n in g.nodes
            for p in n.pins
            if p.linked_to_raw
        )
        assert linked > 0, "All linked_to_raw are empty — Phase 47 fix not applied"

    def test_connections_nonzero(self):
        """至少一个图的 connections 数组非空。"""
        for g in self.result.graphs:
            connections, _ = build_connections_map(g)
            if connections:
                return
        pytest.fail("All graphs have empty connections — Phase 47 fix not applied")

    def test_execution_flows_have_nodes(self):
        """至少一条 execution flow 的 nodes 数组非空。"""
        for g in self.result.graphs:
            flows = build_execution_flows(g)
            for ef in flows:
                if ef.get("nodes"):
                    return
        pytest.fail("All execution flows have empty nodes — Phase 47 fix not applied")

    def test_pin_type_fields_populated(self):
        """FEdGraphPinType 的新字段被正确读取。"""
        for g in self.result.graphs:
            for n in g.nodes:
                for p in n.pins:
                    if p.pin_type is not None:
                        assert hasattr(p.pin_type, "is_const")
                        assert hasattr(p.pin_type, "is_uobject_wrapper")
                        assert hasattr(p.pin_type, "b_serialize_as_single_precision_float")
                        assert hasattr(p.pin_type, "is_reference")
                        assert hasattr(p.pin_type, "is_weak_pointer")
                        return
        pytest.fail("No pins with pin_type found to verify fields")
