"""flow_extractor 测试 — extract_chains / extract_data_flow_map / _detect_cycle."""
import pytest

from uasset_read.n2c.id_mapper import N2CIdMapper
from uasset_read.n2c.flow_extractor import extract_chains, extract_data_flow_map, _detect_cycle


class TestDetectCycle:
    """_detect_cycle DFS 环检测测试。"""

    def test_simple_cycle(self):
        """A->B->A is a cycle."""
        adj = {"A": ["B"], "B": ["A"]}
        assert _detect_cycle(adj) is True

    def test_no_cycle(self):
        """A->B->C is not a cycle."""
        adj = {"A": ["B"], "B": ["C"]}
        assert _detect_cycle(adj) is False

    def test_self_cycle(self):
        """A->A is a cycle."""
        adj = {"A": ["A"]}
        assert _detect_cycle(adj) is True

    def test_empty(self):
        """Empty graph has no cycle."""
        assert _detect_cycle({}) is False

    def test_diamond_no_cycle(self):
        """Diamond shape without back edge: A->B, A->C, B->D, C->D."""
        adj = {"A": ["B", "C"], "B": ["D"], "C": ["D"]}
        assert _detect_cycle(adj) is False

    def test_three_node_cycle(self):
        """A->B->C->A is a cycle."""
        adj = {"A": ["B"], "B": ["C"], "C": ["A"]}
        assert _detect_cycle(adj) is True


class TestExtractChains:
    """extract_chains 测试。"""

    def _make_mapper(self):
        """Create a mapper with test GUIDs."""
        mapper = N2CIdMapper()
        mapper.register("guid-event")
        mapper.register("guid-call")
        mapper.register("guid-call2")
        return mapper

    def test_linear_chain(self):
        """Linear flow returns 'N1->N2'."""
        mapper = self._make_mapper()
        flows = [{
            "start_event": "Event.ReceiveBeginPlay",
            "nodes": [
                {"node_guid": "guid-event", "node_type": "K2Node_Event"},
                {"node_guid": "guid-call", "node_type": "K2Node_CallFunction", "function_name": "PrintString"},
            ]
        }]
        chains = extract_chains(flows, mapper, {})
        assert "N1->N2" in chains

    def test_skips_missing_guid(self):
        """Nodes with missing node_guid are skipped."""
        mapper = self._make_mapper()
        flows = [{
            "start_event": "Event.ReceiveBeginPlay",
            "nodes": [
                {"node_guid": "guid-event", "node_type": "K2Node_Event"},
                {"node_type": "K2Node_CallFunction", "warning": "missing node_guid"},
                {"node_guid": "guid-call", "node_type": "K2Node_CallFunction"},
            ]
        }]
        chains = extract_chains(flows, mapper, {})
        # Should have a chain with N1 (event) but not the missing-guid node
        assert any("N1" in c for c in chains)

    def test_branch_terminates_chain(self):
        """ControlFlow node (stopped_at) terminates chain."""
        mapper = self._make_mapper()
        flows = [{
            "start_event": "Event.ReceiveBeginPlay",
            "nodes": [
                {"node_guid": "guid-event", "node_type": "K2Node_Event"},
                {"node_guid": "guid-call", "node_type": "K2Node_IfThenElse",
                 "branch_type": "Branch", "stopped_at": "control_flow_node"},
            ]
        }]
        chains = extract_chains(flows, mapper, {})
        # Chain should end at the Branch node
        assert len(chains) >= 1

    def test_cycle_fallback_to_pairs(self):
        """Cyclic flow falls back to pair format."""
        mapper = self._make_mapper()
        mapper.register("guid-cycle")
        flows = [{
            "start_event": "Event.ReceiveBeginPlay",
            "nodes": [
                {"node_guid": "guid-event", "node_type": "K2Node_Event"},
                {"node_guid": "guid-call", "node_type": "K2Node_CallFunction"},
                {"node_guid": "guid-event", "node_type": "K2Node_Event", "cycle_detected": True},
            ]
        }]
        result = extract_chains(flows, mapper, {})
        # Should contain _format: pairs
        assert any(isinstance(r, dict) and r.get("_format") == "pairs" for r in result)

    def test_longer_chain(self):
        """N1->N2->N3 chain."""
        mapper = self._make_mapper()
        mapper.register("guid-call3")
        flows = [{
            "start_event": "Event.ReceiveBeginPlay",
            "nodes": [
                {"node_guid": "guid-event", "node_type": "K2Node_Event"},
                {"node_guid": "guid-call", "node_type": "K2Node_CallFunction"},
                {"node_guid": "guid-call2", "node_type": "K2Node_CallFunction"},
            ]
        }]
        chains = extract_chains(flows, mapper, {})
        assert "N1->N2->N3" in chains


class TestExtractDataFlowMap:
    """extract_data_flow_map 测试。"""

    def _make_test_data(self):
        """Create test data for data flow mapping."""
        mapper = N2CIdMapper()
        mapper.register("guid-event")
        mapper.register("guid-call")
        name_to_guid = {
            "K2Node_Event_0": "guid-event",
            "K2Node_CallFunction_1": "guid-call",
        }
        pin_map = {
            ("guid-event", "ReturnValue"): 0,
            ("guid-call", "InString"): 1,
        }
        data_flows = [{
            "source": {"node": "K2Node_Event_0", "pin": "ReturnValue"},
            "target": {"node": "K2Node_CallFunction_1", "pin": "InString"},
        }]
        return data_flows, mapper, name_to_guid, pin_map

    def test_compact_format(self):
        """Returns {'N1.P0': 'N2.P1'} compact format."""
        data_flows, mapper, name_to_guid, pin_map = self._make_test_data()
        result = extract_data_flow_map(data_flows, mapper, name_to_guid, pin_map)
        assert "N1.P0" in result
        assert result["N1.P0"] == "N2.P1"

    def test_skips_missing_lookup(self):
        """Skips entries where source node not in name_to_guid."""
        mapper = N2CIdMapper()
        data_flows = [{
            "source": {"node": "UnknownNode", "pin": "ReturnValue"},
            "target": {"node": "K2Node_CallFunction_1", "pin": "InString"},
        }]
        result = extract_data_flow_map(data_flows, mapper, {}, {})
        assert result == {}

    def test_empty_input(self):
        """Empty data_flows returns empty dict."""
        mapper = N2CIdMapper()
        result = extract_data_flow_map([], mapper, {}, {})
        assert result == {}

    def test_multiple_flows(self):
        """Multiple data flows are all mapped."""
        mapper = N2CIdMapper()
        mapper.register("guid-a")
        mapper.register("guid-b")
        mapper.register("guid-c")
        name_to_guid = {
            "NodeA_0": "guid-a",
            "NodeB_1": "guid-b",
            "NodeC_2": "guid-c",
        }
        pin_map = {
            ("guid-a", "Out"): 0,
            ("guid-b", "In"): 0,
            ("guid-b", "Out"): 1,
            ("guid-c", "In"): 0,
        }
        data_flows = [
            {
                "source": {"node": "NodeA_0", "pin": "Out"},
                "target": {"node": "NodeB_1", "pin": "In"},
            },
            {
                "source": {"node": "NodeB_1", "pin": "Out"},
                "target": {"node": "NodeC_2", "pin": "In"},
            },
        ]
        result = extract_data_flow_map(data_flows, mapper, name_to_guid, pin_map)
        assert "N1.P0" in result
        assert result["N1.P0"] == "N2.P0"
        assert "N2.P1" in result
        assert result["N2.P1"] == "N3.P0"
