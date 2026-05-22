"""Token 用量对比测试 — format_graphs_json vs to_n2c_json。"""
import pytest

from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin, FEdGraphPinType


def _make_mixed_graph():
    """Create a 10+ node graph with mixed node types for token comparison."""
    graph = UEdGraph(graph_name="EventGraph", graph_class="EdGraph")

    # 1. Event node
    event = UEdGraphNode(
        node_guid="guid-event-0",
        class_name="K2Node_Event",
        node_pos_x=-400,
        node_pos_y=0,
        node_comment="Entry point",
    )
    event.node_data = type('MockData', (), {
        'event_reference': type('MockER', (), {
            'member_name': 'ReceiveBeginPlay',
            'member_parent': 'Actor',
        })(),
    })()
    event.pins.append(UEdGraphPin(
        pin_id="guid-event-0-out", pin_name="then", direction=1,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    graph.nodes.append(event)

    # 2. CallFunction: PrintString
    cf1 = UEdGraphNode(
        node_guid="guid-cf1",
        class_name="K2Node_CallFunction",
        node_pos_x=-200,
        node_pos_y=0,
    )
    cf1.node_data = type('MockData', (), {
        'function_reference': type('MockFR', (), {
            'member_name': 'PrintString',
            'member_parent': 'KismetSystemLibrary',
        })(),
    })()
    cf1.pins.append(UEdGraphPin(
        pin_id="guid-cf1-exec-in", pin_name="execute", direction=0,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    cf1.pins.append(UEdGraphPin(
        pin_id="guid-cf1-exec-out", pin_name="then", direction=1,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    cf1.pins.append(UEdGraphPin(
        pin_id="guid-cf1-in", pin_name="InString", direction=0,
        pin_type=FEdGraphPinType(pin_category="string"),
    ))
    graph.nodes.append(cf1)

    # 3. Branch (IfThenElse)
    branch = UEdGraphNode(
        node_guid="guid-branch",
        class_name="K2Node_IfThenElse",
        node_pos_x=0,
        node_pos_y=0,
    )
    branch.pins.append(UEdGraphPin(
        pin_id="guid-branch-exec-in", pin_name="execute", direction=0,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    branch.pins.append(UEdGraphPin(
        pin_id="guid-branch-cond", pin_name="Condition", direction=0,
        pin_type=FEdGraphPinType(pin_category="bool"),
    ))
    branch.pins.append(UEdGraphPin(
        pin_id="guid-branch-true", pin_name="True", direction=1,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    branch.pins.append(UEdGraphPin(
        pin_id="guid-branch-false", pin_name="False", direction=1,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    graph.nodes.append(branch)

    # 4. Knot (should be excluded in N2C)
    knot = UEdGraphNode(
        node_guid="guid-knot",
        class_name="K2Node_Knot",
        node_pos_x=100,
        node_pos_y=0,
    )
    knot.pins.append(UEdGraphPin(
        pin_id="guid-knot-in", pin_name="InputPin", direction=0,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    knot.pins.append(UEdGraphPin(
        pin_id="guid-knot-out", pin_name="OutputPin", direction=1,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    graph.nodes.append(knot)

    # 5. VariableGet
    varget = UEdGraphNode(
        node_guid="guid-varget",
        class_name="K2Node_VariableGet",
        node_pos_x=-200,
        node_pos_y=200,
    )
    varget.node_data = type('MockData', (), {
        'variable_reference': type('MockVR', (), {
            'member_name': 'MyVariable',
            'member_parent': None,
        })(),
    })()
    varget.pins.append(UEdGraphPin(
        pin_id="guid-varget-out", pin_name="MyVariable", direction=1,
        pin_type=FEdGraphPinType(pin_category="int"),
    ))
    graph.nodes.append(varget)

    # 6-11. More CallFunction nodes
    for i in range(6):
        cf = UEdGraphNode(
            node_guid=f"guid-cf-extra-{i}",
            class_name="K2Node_CallFunction",
            node_pos_x=200 + i * 200,
            node_pos_y=0,
        )
        cf.node_data = type('MockData', (), {
            'function_reference': type('MockFR', (), {
                'member_name': f'Function{i}',
                'member_parent': 'SomeClass',
            })(),
        })()
        cf.pins.append(UEdGraphPin(
            pin_id=f"guid-cf-extra-{i}-exec-in", pin_name="execute", direction=0,
            pin_type=FEdGraphPinType(pin_category="exec"),
        ))
        cf.pins.append(UEdGraphPin(
            pin_id=f"guid-cf-extra-{i}-exec-out", pin_name="then", direction=1,
            pin_type=FEdGraphPinType(pin_category="exec"),
        ))
        graph.nodes.append(cf)

    # Wire exec from event to cf1
    event.pins[0].linked_to_raw = [{"pin_id": "guid-cf1-exec-in", "pin_guid": "guid-cf1-exec-in"}]

    return graph


class TestTokenReduction:
    """Token 用量对比测试。"""

    def test_estimate_token_count_empty(self):
        """Empty dict returns 0 or very small value."""
        from uasset_read.n2c import _estimate_token_count
        result = _estimate_token_count({})
        assert result <= 1  # Empty JSON "{}" -> 1 token max

    def test_estimate_token_count_proportional(self):
        """Token count is proportional to JSON string length."""
        from uasset_read.n2c import _estimate_token_count
        small = {"a": 1}
        large = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
        assert _estimate_token_count(large) > _estimate_token_count(small)

    def test_n2c_reduces_tokens_by_40_percent(self):
        """N2C format uses at least 40% fewer tokens than existing format."""
        from uasset_read.graph import format_graphs_json
        from uasset_read.n2c import to_n2c_json, _estimate_token_count

        graph = _make_mixed_graph()

        # Generate existing format output
        existing_output = format_graphs_json([graph])
        existing_tokens = _estimate_token_count({"graphs": existing_output})

        # Generate N2C format output
        n2c_output = to_n2c_json(graphs=[graph])
        n2c_tokens = _estimate_token_count(n2c_output)

        # Calculate savings
        savings = (existing_tokens - n2c_tokens) / existing_tokens * 100

        # Assert at least 40% reduction
        assert savings >= 40, (
            f"N2C token reduction {savings:.1f}% < 40% threshold. "
            f"Existing: {existing_tokens} tokens, N2C: {n2c_tokens} tokens"
        )

    def test_token_comparison_details(self):
        """Print detailed token comparison data."""
        from uasset_read.graph import format_graphs_json
        from uasset_read.n2c import to_n2c_json, _estimate_token_count

        graph = _make_mixed_graph()

        existing_output = format_graphs_json([graph])
        existing_tokens = _estimate_token_count({"graphs": existing_output})

        n2c_output = to_n2c_json(graphs=[graph])
        n2c_tokens = _estimate_token_count(n2c_output)

        savings = (existing_tokens - n2c_tokens) / existing_tokens * 100

        print(f"\nToken Comparison:")
        print(f"  Existing format: {existing_tokens} tokens")
        print(f"  N2C format:      {n2c_tokens} tokens")
        print(f"  Savings:         {savings:.1f}%")
        # This is informational, always passes
        assert True
