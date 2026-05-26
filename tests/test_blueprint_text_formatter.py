"""蓝图翻译参考文本格式器测试。"""
from __future__ import annotations

from uasset_read import (
    BlueprintMetadata,
    FEdGraphPinType,
    FMemberReference,
    ParseResult,
    PackageFileSummary,
    UEdGraph,
    UEdGraphNode,
    UEdGraphPin,
    format_blueprint_translation_text,
)


def _pin(
    pin_id: str,
    pin_name: str,
    direction: int,
    category: str,
    subcategory: str = "",
    linked_to: list[str] | None = None,
    default_value: str | None = None,
) -> UEdGraphPin:
    return UEdGraphPin(
        pin_id=pin_id,
        pin_name=pin_name,
        direction=direction,
        pin_type=FEdGraphPinType(
            pin_category=category,
            pin_subcategory=subcategory,
        ),
        linked_to_raw=linked_to or [],
        default_value=default_value,
    )


def test_format_blueprint_translation_text_is_concise() -> None:
    """输出应保留语义和连接，但去掉原始复制文本的大量噪声。"""
    action_trigger = _pin(
        "11111111111111111111111111111111",
        "Triggered",
        1,
        "exec",
        linked_to=["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
    )
    action_x = _pin(
        "22222222222222222222222222222222",
        "ActionValue_X",
        1,
        "real",
        "float",
        linked_to=["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],
        default_value="0.0",
    )
    action_y = _pin(
        "33333333333333333333333333333333",
        "ActionValue_Y",
        1,
        "real",
        "float",
        linked_to=["cccccccccccccccccccccccccccccccc"],
        default_value="0.0",
    )

    move_execute = _pin(
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "execute",
        0,
        "exec",
        linked_to=["11111111111111111111111111111111"],
    )
    move_right = _pin(
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "Right",
        0,
        "real",
        "float",
        linked_to=["22222222222222222222222222222222"],
    )
    move_forward = _pin(
        "cccccccccccccccccccccccccccccccc",
        "Forward",
        0,
        "real",
        "float",
        linked_to=["33333333333333333333333333333333"],
    )
    move_then = _pin(
        "dddddddddddddddddddddddddddddddd",
        "then",
        1,
        "exec",
    )

    graph = UEdGraph(
        graph_name="EventGraph",
        graph_class="UberEdGraph",
        nodes=[
            UEdGraphNode(
                node_guid="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                class_name="K2Node_EnhancedInputAction",
                node_data={
                    "input_action_path": "/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Move.IA_Move'",
                },
                pins=[action_trigger, action_x, action_y],
            ),
            UEdGraphNode(
                node_guid="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                class_name="K2Node_CallFunction",
                node_data={
                    "function_reference": FMemberReference(
                        member_name="DoMove",
                        b_self_context=True,
                    )
                },
                pins=[move_execute, move_right, move_forward, move_then],
            ),
            UEdGraphNode(
                node_guid="dddddddddddddddddddddddddddddddd",
                class_name="EdGraphNode_Comment",
                node_comment="Movement Input",
                pins=[],
            ),
        ],
    )

    result = ParseResult(
        summary=PackageFileSummary(
            tag=0x9E2A83C1,
            legacy_file_version=-9,
            package_name="/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter",
        ),
        blueprint=BlueprintMetadata(
            is_blueprint=True,
            parent_class="/Script/Engine.Character",
        ),
        graphs=[graph],
    )

    text = format_blueprint_translation_text(result)

    assert "Asset: BP_FirstPersonCharacter" in text
    assert "ParentClass: /Script/Engine.Character" in text
    assert "Graph: EventGraph (UberEdGraph)" in text
    assert "- K2Node_EnhancedInputAction_0 [EnhancedInput: IA_Move]" in text
    assert "InputPath: /Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Move.IA_Move'" in text
    assert "out Triggered [exec] | links=K2Node_CallFunction_1.execute" in text
    assert "- K2Node_CallFunction_1 [CallFunction: DoMove]" in text
    assert "Call: DoMove" in text
    assert "in Right [real/float] | links=K2Node_EnhancedInputAction_0.ActionValue_X" in text
    assert "- EdGraphNode_Comment_2 [Comment: Movement Input]" in text
    assert "Note: Movement Input" in text
    assert "Begin Object" not in text
    assert "CustomProperties Pin" not in text
    assert len(text) < 1200
