"""
Node type-specific data classes — K2Node subclasses inherit UEdGraphNode.

The classes defined here are serialization models of the UE binary format,
used by the serializers layer to construct instances when reading data from
the archive. Serialization logic is in serializers/graph.py.

Per D-04: Node inheritance structure, subclasses access base fields via super().
Per D-05: class_name field is used for match/case type dispatch.
"""

from dataclasses import dataclass, field

from .core import UEdGraphNode, FMemberReference


@dataclass
class K2NodeCallFunction(UEdGraphNode):
    """K2Node_CallFunction function call node."""
    function_reference: FMemberReference | None = None
    b_defaults_to_pure: bool = False


@dataclass
class K2NodeEvent(UEdGraphNode):
    """K2Node_Event event node."""
    event_reference: FMemberReference | None = None
    b_override_function: bool = False


@dataclass
class K2NodeKnot(UEdGraphNode):
    """K2Node_Knot reroute node, no additional fields."""


@dataclass
class EdGraphNodeComment(UEdGraphNode):
    """EdGraphNode_Comment comment node."""
    comment_color: tuple[float, float, float, float] = (0.05, 0.05, 0.05, 1.0)
    node_width: int = 0
    node_height: int = 0
    font_size: int = 14


@dataclass
class K2NodeEnhancedInputAction(UEdGraphNode):
    """K2Node_EnhancedInputAction input action node."""
    input_action_path: str = ""
    trigger_events: dict[str, str] = field(default_factory=dict)


@dataclass
class K2NodeFunctionEntry(UEdGraphNode):
    """K2Node_FunctionEntry function entry node."""
    function_reference: FMemberReference | None = None
    extra_flags: int = 0
    b_is_editable: bool = False
