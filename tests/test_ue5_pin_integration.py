"""UE5 Pin Integration Tests - Verify linked_to_raw, execution_flows, data_flows."""
import pytest
from uasset_read import parse_uasset, format_json_full

# Test asset path
TEST_ASSET = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"


@pytest.mark.skipif(not __import__('os').path.exists(TEST_ASSET), reason="Test asset not found")
class TestUE5PinIntegration:
    """Integration tests for UE5 pin connection parsing."""

    def test_asset_parses_successfully(self):
        """BP_FirstPersonCharacter.uasset parses successfully with no errors."""
        result = parse_uasset(TEST_ASSET)
        assert result is not None
        assert result.status is not None
        assert len(result.graphs) > 0

    def test_eventgraph_has_nodes_with_pins(self):
        """EventGraph has nodes with pins (non-zero count)."""
        result = parse_uasset(TEST_ASSET)
        event_graph = None
        for g in result.graphs:
            if g.graph_name == "EventGraph":
                event_graph = g
                break

        assert event_graph is not None, "EventGraph not found"
        assert len(event_graph.nodes) > 0, "EventGraph has no nodes"

        total_pins = sum(len(n.pins) for n in event_graph.nodes)
        assert total_pins > 0, "EventGraph has no pins"

    def test_pins_have_linked_to_raw(self):
        """At least one pin has non-empty linked_to_raw (root fix verification)."""
        result = parse_uasset(TEST_ASSET)
        event_graph = None
        for g in result.graphs:
            if g.graph_name == "EventGraph":
                event_graph = g
                break

        total_pins = 0
        pins_with_links = 0
        for node in event_graph.nodes:
            for pin in node.pins:
                total_pins += 1
                links = getattr(pin, 'linked_to_raw', [])
                if links and len(links) > 0:
                    pins_with_links += 1

        assert total_pins > 0, "No pins found"
        assert pins_with_links > 0, f"None of {total_pins} pins have linked_to_raw entries"

    def test_execution_flows_not_empty(self):
        """execution_flows in EventGraph is non-empty (contains flow paths)."""
        result = parse_uasset(TEST_ASSET)
        json_output = format_json_full(result)

        event_graph = None
        graphs = json_output.get("blueprint", {}).get("graphs", [])
        for g in graphs:
            if g.get("graph_name") == "EventGraph":
                event_graph = g
                break

        assert event_graph is not None, "EventGraph not found in JSON output"
        execution_flows = event_graph.get("execution_flows", [])
        assert len(execution_flows) > 0, "execution_flows is empty"

    def test_data_flows_not_empty(self):
        """data_flows in Move graph is non-empty."""
        result = parse_uasset(TEST_ASSET)
        json_output = format_json_full(result)

        move_graph = None
        graphs = json_output.get("blueprint", {}).get("graphs", [])
        for g in graphs:
            if g.get("graph_name") == "Move":
                move_graph = g
                break

        assert move_graph is not None, "Move graph not found in JSON output"
        data_flows = move_graph.get("data_flows", [])
        assert len(data_flows) > 0, "data_flows is empty in Move graph"

    def test_connections_not_empty(self):
        """connections list has entries (source -> target pin connections)."""
        result = parse_uasset(TEST_ASSET)
        json_output = format_json_full(result)

        event_graph = None
        graphs = json_output.get("blueprint", {}).get("graphs", [])
        for g in graphs:
            if g.get("graph_name") == "EventGraph":
                event_graph = g
                break

        connections = event_graph.get("connections", [])
        assert len(connections) > 0, "connections list is empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
