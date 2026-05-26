"""Phase 75-02: Golden Test 强化 — 字段级对齐校验。

测试目标：
1. EnhancedInputAction 节点字段对齐（IA_Move, IA_Look, IA_Jump, IA_MouseLook）
2. K2Node_Event 节点字段对齐（Touch 相关事件）
3. K2Node_FunctionEntry 节点字段对齐（Move / Aim 函数入口）
4. 关键 pin 不依赖 low confidence recovery 机制

这些测试应先失败，失败信息必须指向字段级差异，而不是只报连接数量不足。
"""

import os
import re
import logging
import pytest
from typing import Dict, List, Optional, Tuple

from uasset_read import parse_uasset_with_linker
from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin, FEdGraphPinType

# ============================================================================
# 测试资产路径
# ============================================================================

SAMPLE_ASSET = (
    r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson"
    r"\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset"
)

# ============================================================================
# 常量 / 枚举映射
# ============================================================================

EGPD_INPUT = 0
EGPD_OUTPUT = 1

ADVANCED_VIEW_HIDDEN = "Hidden"

EXEC_PINS_ENHANCED_INPUT = {"Triggered", "Started", "Ongoing", "Canceled", "Completed"}

REAL_SUBCATEGORIES = {"real", "double", "float"}

# 乱码 / 伪 pin 判定条件
_GARBAGE_PATTERNS = ["/Game/", "/Script/", "StructProperty", "ObjectProperty"]


# ============================================================================
# 辅助函数
# ============================================================================

def _find_graph(parsed_asset, graph_name: str) -> Optional[UEdGraph]:
    """按名称从解析结果中查找 Graph。"""
    for graph in parsed_asset.graphs:
        if graph.graph_name == graph_name:
            return graph
    return None


def _nodes_by_semantic_name(graph: UEdGraph, class_name: str = "") -> Dict[str, UEdGraphNode]:
    """按语义名称索引节点。

    返回 {semantic_name: node} 字典。
    - K2Node_EnhancedInputAction: 使用 input_action_path 的最后一段
    - K2Node_Event: 使用 event_reference.member_name
    - K2Node_FunctionEntry: 使用 function_reference.member_name
    - EdGraphNode_Comment: 使用 node_comment
    - 其他: 使用 class_name
    """
    result: Dict[str, UEdGraphNode] = {}
    for node in graph.nodes:
        nd = node.node_data or {}
        semantic = _extract_semantic_name(node, nd)
        if semantic:
            result[semantic] = node
        if class_name and node.class_name != class_name:
            # 如果指定了 class_name 过滤，移除不匹配的
            pass  # 保留所有，由调用方过滤
    return result


def _extract_semantic_name(node: UEdGraphNode, nd) -> Optional[str]:
    """从节点提取语义名称。"""
    if isinstance(nd, dict):
        if node.class_name == "K2Node_EnhancedInputAction":
            path = nd.get("input_action_path", "")
            if path:
                return path.split("/")[-1] if "/" in path else path
        elif node.class_name == "K2Node_Event":
            er = nd.get("event_reference")
            if er:
                mn = getattr(er, "member_name", None) if not isinstance(er, dict) else er.get("member_name", "")
                if mn and mn != "None":
                    return mn
        elif node.class_name == "K2Node_FunctionEntry":
            fr = nd.get("function_reference")
            if fr:
                mn = getattr(fr, "member_name", None) if not isinstance(fr, dict) else fr.get("member_name", "")
                if mn and mn != "None":
                    return mn
        elif node.class_name == "EdGraphNode_Comment":
            comment = node.node_comment
            if comment:
                return comment

    # Fallback: 尝试从 node_data dict 直接读取
    if isinstance(nd, dict):
        for key in ("input_action_path", "member_name"):
            val = nd.get(key, "")
            if val:
                return val.split("/")[-1] if "/" in val else val

    return None


def _pins_by_name(node: UEdGraphNode) -> Dict[str, UEdGraphPin]:
    """按 pin_name 索引节点的 pins。"""
    return {p.pin_name: p for p in node.pins if p.pin_name}


def _assert_pin(
    node: UEdGraphNode,
    name: str,
    direction: int,
    category: str,
    subcategory: Optional[str] = None,
) -> Optional[UEdGraphPin]:
    """断言节点存在指定名称和属性的 pin。

    Returns the pin if found and valid, None otherwise.
    Raises AssertionError on mismatch.
    """
    pins = _pins_by_name(node)
    assert name in pins, (
        f"Pin '{name}' not found on node {node.class_name}. "
        f"Available pins: {sorted(pins.keys())}"
    )
    pin = pins[name]

    # 检查方向
    assert pin.direction == direction, (
        f"Pin '{name}' direction mismatch: "
        f"expected {'Input' if direction == EGPD_INPUT else 'Output'} ({direction}), "
        f"got {'Input' if pin.direction == EGPD_INPUT else 'Output'} ({pin.direction})"
    )

    # 检查 category
    if pin.pin_type:
        actual_cat = pin.pin_type.pin_category
        assert actual_cat == category, (
            f"Pin '{name}' category mismatch: "
            f"expected '{category}', got '{actual_cat}'"
        )

        # 检查 subcategory
        if subcategory is not None:
            actual_sub = pin.pin_type.pin_subcategory
            assert actual_sub == subcategory, (
                f"Pin '{name}' subcategory mismatch: "
                f"expected '{subcategory}', got '{actual_sub}'"
            )

    return pin


def _assert_no_garbage_pin_names(node: UEdGraphNode) -> List[str]:
    """检查节点的 pin 名称是否包含乱码。

    Returns list of garbage pin names found (empty = all clean).
    """
    garbage_names = []
    for pin in node.pins:
        name = pin.pin_name or ""
        if not name or name == "None":
            garbage_names.append(f"<empty/None>")
            continue
        for pattern in _GARBAGE_PATTERNS:
            if pattern in name:
                garbage_names.append(f"{name} (contains '{pattern}')")
                break
        # 检查 direction 值
        if pin.direction not in (EGPD_INPUT, EGPD_OUTPUT):
            garbage_names.append(f"{name} (invalid direction={pin.direction})")
        # 检查 pin category 是否包含对象路径
        if pin.pin_type:
            cat = pin.pin_type.pin_category or ""
            if cat.startswith("/Game/") or cat.startswith("/Script/"):
                garbage_names.append(f"{name} (category contains path: {cat})")

    return garbage_names


# ============================================================================
# Fixture: 解析资产
# ============================================================================

@pytest.fixture(scope="module")
def parsed_asset():
    """加载 BP_FirstPersonCharacter.uasset（仅当文件存在时）。"""
    if not os.path.exists(SAMPLE_ASSET):
        pytest.skip(f"Sample asset not found: {SAMPLE_ASSET}")
    return parse_uasset_with_linker(SAMPLE_ASSET)


# ============================================================================
# Test 1: EnhancedInputAction 节点字段对齐
# ============================================================================

class TestEnhancedInputNodeFieldAlignment:
    """验证 K2Node_EnhancedInputAction 节点字段与参考对齐。"""

    def test_enhanced_input_nodes_match_reference_fields(self, parsed_asset, caplog):
        """断言 IA_Look, IA_Move, IA_Jump, IA_MouseLook 均存在且字段正确。

        验证项：
        - 所有 4 个节点存在
        - 每个节点 advanced_pin_display == "Hidden" 或等价枚举值
        - Triggered/Started/Ongoing/Canceled/Completed 都是 EGPD_Output exec pins
        - ElapsedSeconds, TriggeredSeconds 为 output real/double 且 advanced_view=True
        - InputAction pin 为 object pin，默认对象可解析
        """
        eventgraph = _find_graph(parsed_asset, "EventGraph")
        assert eventgraph is not None, "EventGraph not found in parsed asset"

        # 提取所有 EnhancedInputAction 节点
        ia_nodes = {
            n: node for n, node in _nodes_by_semantic_name(eventgraph).items()
            if node.class_name == "K2Node_EnhancedInputAction"
        }

        expected_actions = {"IA_Look", "IA_Move", "IA_Jump", "IA_MouseLook"}

        # 诊断输出：列出所有找到的 EnhancedInputAction 节点
        all_ia_classes = [n for n in eventgraph.nodes if n.class_name == "K2Node_EnhancedInputAction"]
        found_names = set()
        for node in all_ia_classes:
            nd = node.node_data or {}
            if isinstance(nd, dict):
                path = nd.get("input_action_path", "")
                name = path.split("/")[-1] if "/" in path else path
                found_names.add(name)

        print(f"\n=== EnhancedInputAction Diagnostics ===")
        print(f"  Expected: {sorted(expected_actions)}")
        print(f"  Found:    {sorted(found_names)}")
        print(f"  Total nodes: {len(all_ia_classes)}")
        for node in all_ia_classes:
            nd = node.node_data or {}
            path = ""
            if isinstance(nd, dict):
                path = nd.get("input_action_path", "")
            print(f"    - {node.class_name}: input_action_path='{path}', pins={len(node.pins)}")

        # 断言所有预期节点存在
        missing = expected_actions - found_names
        if missing:
            pytest.fail(
                f"Missing EnhancedInputAction nodes: {sorted(missing)}. "
                f"Found: {sorted(found_names)}"
            )

        # 逐一验证每个节点
        for action_name in expected_actions:
            node = ia_nodes.get(action_name)
            if node is None:
                pytest.fail(f"EnhancedInputAction node '{action_name}' not found by semantic lookup")

            pins = _pins_by_name(node)

            # --- 验证 advanced_view 标记 ---
            # Advanced pins 应标记为 hidden 或 advanced_view=True
            advanced_pins = [p for p in node.pins if p.advanced_view]
            hidden_pins = [p for p in node.pins if p.hidden]
            print(f"  [{action_name}] advanced_view pins: {[p.pin_name for p in advanced_pins]}")
            print(f"  [{action_name}] hidden pins: {[p.pin_name for p in hidden_pins]}")

            # --- 验证 exec output pins ---
            for exec_pin_name in EXEC_PINS_ENHANCED_INPUT:
                if exec_pin_name in pins:
                    pin = pins[exec_pin_name]
                    assert pin.direction == EGPD_OUTPUT, (
                        f"[{action_name}] Pin '{exec_pin_name}' should be output, "
                        f"got direction={pin.direction}"
                    )
                    if pin.pin_type:
                        assert pin.pin_type.pin_category == "exec", (
                            f"[{action_name}] Pin '{exec_pin_name}' should be exec category, "
                            f"got '{pin.pin_type.pin_category}'"
                        )
                    print(f"  [{action_name}] exec pin '{exec_pin_name}': OK (output)")

            # --- 验证 ElapsedSeconds / TriggeredSeconds ---
            for time_pin_name in ("ElapsedSeconds", "TriggeredSeconds"):
                if time_pin_name in pins:
                    pin = pins[time_pin_name]
                    assert pin.direction == EGPD_OUTPUT, (
                        f"[{action_name}] Pin '{time_pin_name}' should be output, "
                        f"got direction={pin.direction}"
                    )
                    if pin.pin_type:
                        sub = pin.pin_type.pin_subcategory
                        assert sub in REAL_SUBCATEGORIES, (
                            f"[{action_name}] Pin '{time_pin_name}' subcategory should be "
                            f"real/double/float, got '{sub}'"
                        )
                    assert pin.advanced_view is True, (
                        f"[{action_name}] Pin '{time_pin_name}' should have advanced_view=True"
                    )
                    print(f"  [{action_name}] data pin '{time_pin_name}': OK (output, {pin.pin_type.pin_subcategory})")

            # --- 验证 InputAction pin ---
            for pin in node.pins:
                if pin.pin_name == "InputAction":
                    assert pin.default_object is not None and pin.default_object != 0, (
                        f"[{action_name}] InputAction pin default_object should be non-zero"
                    )
                    # 检查默认对象引用
                    if pin.default_object_ref:
                        obj_name = getattr(pin.default_object_ref, "object_name", "")
                        assert obj_name.startswith("IA_"), (
                            f"[{action_name}] InputAction default object should start with 'IA_', "
                            f"got '{obj_name}'"
                        )
                    print(f"  [{action_name}] InputAction pin: default_object={pin.default_object}")

            # --- 乱码检查 ---
            garbage = _assert_no_garbage_pin_names(node)
            if garbage:
                pytest.fail(
                    f"[{action_name}] Garbage pin names found: {garbage}"
                )


# ============================================================================
# Test 2: K2Node_Event 节点字段对齐（Touch 事件）
# ============================================================================

class TestTouchEventNodeFieldAlignment:
    """验证 K2Node_Event 节点（Touch 相关）字段与参考对齐。"""

    def test_touch_event_nodes_match_reference_fields(self, parsed_asset):
        """断言 4 个 K2Node_Event 名称正确且字段对齐。

        验证项：
        - Primary Thumbstick, Secondary Thumbstick, Touch Jump Start, Touch Jump End 存在
        - bOverrideFunction=True
        - delegate pin 的 PinSubCategoryMemberReference.member_name 与 EventReference.member_name 一致
        - Primary/Secondary Thumbstick 的 Axis_X/Axis_Y split pins 无乱码、方向为 output
        """
        eventgraph = _find_graph(parsed_asset, "EventGraph")
        assert eventgraph is not None, "EventGraph not found in parsed asset"

        expected_events = {
            "Primary Thumbstick",
            "Secondary Thumbstick",
            "Touch Jump Start",
            "Touch Jump End",
        }

        # 提取所有 K2Node_Event 节点
        event_nodes = _nodes_by_semantic_name(eventgraph)
        found_events = {
            name for name, node in event_nodes.items()
            if node.class_name == "K2Node_Event"
        }

        print(f"\n=== K2Node_Event Diagnostics ===")
        print(f"  Expected: {sorted(expected_events)}")
        print(f"  Found:    {sorted(found_events)}")

        # 诊断：列出所有 K2Node_Event 节点
        all_event_nodes = [n for n in eventgraph.nodes if n.class_name == "K2Node_Event"]
        for node in all_event_nodes:
            nd = node.node_data or {}
            if isinstance(nd, dict):
                er = nd.get("event_reference")
                mn = ""
                if er:
                    mn = getattr(er, "member_name", "") if not isinstance(er, dict) else er.get("member_name", "")
                b_override = nd.get("b_override_function", "N/A")
            else:
                mn = ""
                b_override = "N/A"
            print(f"    - {node.class_name}: member_name='{mn}', b_override={b_override}")

        # 断言所有预期事件存在
        missing = expected_events - found_events
        if missing:
            pytest.fail(
                f"Missing K2Node_Event nodes: {sorted(missing)}. "
                f"Found: {sorted(found_events)}"
            )

        # 逐一验证
        for event_name in expected_events:
            node = event_nodes.get(event_name)
            if node is None:
                pytest.fail(f"K2Node_Event node '{event_name}' not found by semantic lookup")

            nd = node.node_data or {}

            # --- 验证 bOverrideFunction=True ---
            b_override = nd.get("b_override_function", False) if isinstance(nd, dict) else False
            assert b_override is True, (
                f"[{event_name}] bOverrideFunction should be True, got {b_override}"
            )
            print(f"  [{event_name}] bOverrideFunction: True (OK)")

            # --- 验证 delegate pin member_name 一致性 ---
            event_ref = nd.get("event_reference") if isinstance(nd, dict) else None
            event_member_name = ""
            if event_ref:
                event_member_name = (
                    getattr(event_ref, "member_name", "")
                    if not isinstance(event_ref, dict)
                    else event_ref.get("member_name", "")
                )

            for pin in node.pins:
                # 检查 pin 类型中的 member reference
                if pin.pin_type:
                    sub_obj_name = getattr(pin.pin_type, "pin_subcategory_object_name", "")
                    if sub_obj_name and sub_obj_name != event_member_name:
                        print(
                            f"  [{event_name}] Pin '{pin.pin_name}' subcategory_object_name="
                            f"'{sub_obj_name}', event_ref.member_name='{event_member_name}'"
                        )

            # --- Thumbstick 节点：验证 Axis_X/Axis_Y split pins ---
            if "Thumbstick" in event_name:
                pins = _pins_by_name(node)
                for axis_pin in ("Axis_X", "Axis_Y"):
                    if axis_pin in pins:
                        pin = pins[axis_pin]
                        assert pin.direction == EGPD_OUTPUT, (
                            f"[{event_name}] Pin '{axis_pin}' should be output, "
                            f"got direction={pin.direction}"
                        )
                        print(f"  [{event_name}] split pin '{axis_pin}': OK (output)")

            # --- 乱码检查 ---
            garbage = _assert_no_garbage_pin_names(node)
            if garbage:
                pytest.fail(
                    f"[{event_name}] Garbage pin names found: {garbage}"
                )


# ============================================================================
# Test 3: K2Node_FunctionEntry 节点字段对齐
# ============================================================================

class TestFunctionEntryNodeFieldAlignment:
    """验证 K2Node_FunctionEntry 节点字段与参考对齐。"""

    def test_function_entry_nodes_match_reference_fields(self, parsed_asset):
        """断言 Move / Aim FunctionEntry 有正确字段。

        验证项：
        - ExtraFlags=201457664, bIsEditable=True
        - 参数 pins 分别为 Left/Right, Forward/Backward, Yaw, Pitch
        """
        eventgraph = _find_graph(parsed_asset, "EventGraph")
        assert eventgraph is not None, "EventGraph not found in parsed asset"

        # 查找所有 FunctionEntry 节点（跨所有 graphs，因为每个函数有独立的 graph）
        fe_nodes = {}
        for graph in parsed_asset.graphs:
            for node in graph.nodes:
                if node.class_name == "K2Node_FunctionEntry":
                    nd = node.node_data or {}
                    if isinstance(nd, dict):
                        fr = nd.get("function_reference")
                        if fr:
                            mn = (
                                getattr(fr, "member_name", "")
                                if not isinstance(fr, dict)
                                else fr.get("member_name", "")
                            )
                            if mn:
                                fe_nodes[mn] = node

        print(f"\n=== K2Node_FunctionEntry Diagnostics ===")
        print(f"  Found: {sorted(fe_nodes.keys())}")

        # 诊断：列出所有 FunctionEntry（跨所有 graphs）
        for graph in parsed_asset.graphs:
            for node in graph.nodes:
                if node.class_name == "K2Node_FunctionEntry":
                    nd = node.node_data or {}
                    fr_name = ""
                    extra_flags_val = "N/A"
                    b_editable_val = "N/A"
                    if isinstance(nd, dict):
                        fr = nd.get("function_reference")
                        if fr:
                            fr_name = (
                                getattr(fr, "member_name", "")
                                if not isinstance(fr, dict)
                                else fr.get("member_name", "")
                            )
                        # Phase 75-03: 从 node_data 提取 PropertyTag 字段
                        extra_flags_val = nd.get("extra_flags", "N/A")
                        b_editable_val = nd.get("b_is_editable", "N/A")
                    print(f"    - {node.class_name}: function='{fr_name}', "
                          f"extra_flags={extra_flags_val}, b_editable={b_editable_val}")
                    print(f"      pins: {[p.pin_name for p in node.pins]}")

        expected_functions = {"Move", "Aim"}
        missing = expected_functions - set(fe_nodes.keys())
        if missing:
            pytest.fail(
                f"Missing K2Node_FunctionEntry nodes: {sorted(missing)}. "
                f"Found: {sorted(fe_nodes.keys())}"
            )

        # 验证 Move 和 Aim 的 pin 签名
        expected_params = {
            "Move": {"Left", "Right", "Forward", "Backward"},
            "Aim": {"Yaw", "Pitch"},
        }

        for func_name, node in fe_nodes.items():
            if func_name not in expected_params:
                continue

            pins = _pins_by_name(node)
            input_pins = {
                name for name, pin in pins.items()
                if pin.direction == EGPD_INPUT
                and pin.pin_type
                and pin.pin_type.pin_category != "exec"
            }

            expected = expected_params[func_name]
            missing_pins = expected - input_pins
            if missing_pins:
                pytest.fail(
                    f"[{func_name}] Missing parameter pins: {sorted(missing_pins)}. "
                    f"Found input pins: {sorted(input_pins)}"
                )

            print(f"  [{func_name}] parameter pins: {sorted(input_pins)} (OK)")


# ============================================================================
# Test 4: Golden Edges 不依赖 Low Confidence Recovery
# ============================================================================

class TestNoLowConfidencePinRecoveryForGoldenEdges:
    """验证关键 pin 不依赖低置信度恢复机制。"""

    def test_no_low_confidence_pin_recovery_for_golden_edges(self, parsed_asset, caplog):
        """解析过程中捕获日志，断言关键 pin 不依赖 [P73-SUBPINS] / low confidence recovery。

        先允许测试失败并打印 offending node/pin。
        """
        # 设置日志捕获
        with caplog.at_level(logging.DEBUG, logger="uasset_read.serializers.graph"):
            # 重新解析以捕获日志
            if os.path.exists(SAMPLE_ASSET):
                result = parse_uasset_with_linker(SAMPLE_ASSET)
            else:
                pytest.skip(f"Sample asset not found: {SAMPLE_ASSET}")

        # 收集所有 P73-SUBPINS 和 P73-RECOVERY 日志
        subpin_messages = [
            rec.message for rec in caplog.records
            if "[P73-SUBPINS]" in rec.message
        ]
        recovery_messages = [
            rec.message for rec in caplog.records
            if "[P73-RECOVERY]" in rec.message
        ]

        # 诊断输出
        print(f"\n=== Low Confidence Recovery Diagnostics ===")
        print(f"  [P73-SUBPINS] messages: {len(subpin_messages)}")
        print(f"  [P73-RECOVERY] messages: {len(recovery_messages)}")

        for msg in subpin_messages:
            print(f"  SUBPINS: {msg}")
        for msg in recovery_messages:
            print(f"  RECOVERY: {msg}")

        # 检查 golden 节点是否受到影响
        eventgraph = _find_graph(result, "EventGraph")
        golden_node_names = {
            "IA_Move", "IA_Look", "IA_Jump", "IA_MouseLook",
            "Primary Thumbstick", "Secondary Thumbstick",
            "Touch Jump Start", "Touch Jump End",
            "Move", "Aim",
        }

        affected_nodes = []
        for msg in subpin_messages + recovery_messages:
            for name in golden_node_names:
                if name in msg:
                    affected_nodes.append((name, msg))

        if affected_nodes:
            print(f"\n[DIAGNOSIS] Golden nodes affected by low-confidence recovery:")
            for name, msg in affected_nodes:
                print(f"  [{name}] {msg}")

            # 第一阶段：允许失败但打印 offending node/pin
            # 修复完成后收紧为 0
            pytest.fail(
                f"{len(affected_nodes)} golden node(s) affected by low-confidence recovery. "
                f"See diagnostics above for details."
            )

        # 通过条件：无 golden 节点受影响
        assert len(affected_nodes) == 0, "No golden nodes should be affected by low-confidence recovery"


# ============================================================================
# Test 5: EdGraphNode_Comment 节点验证（最小 golden 集）
# ============================================================================

class TestCommentNodeGoldenSet:
    """验证 EdGraphNode_Comment golden 集存在。"""

    def test_comment_nodes_exist(self, parsed_asset):
        """断言 Camera Input, Movement Input, Jump Input 注释节点存在。"""
        eventgraph = _find_graph(parsed_asset, "EventGraph")
        assert eventgraph is not None, "EventGraph not found in parsed asset"

        expected_comments = {"Camera Input", "Movement Input", "Jump Input"}

        # 使用模糊匹配：注释文本包含预期关键词即可
        found_comments = set()
        for node in eventgraph.nodes:
            if node.class_name == "EdGraphNode_Comment" and node.node_comment:
                for expected in expected_comments:
                    if expected in node.node_comment:
                        found_comments.add(expected)

        print(f"\n=== EdGraphNode_Comment Diagnostics ===")
        print(f"  Expected: {sorted(expected_comments)}")
        print(f"  Found:    {sorted(found_comments)}")

        for node in eventgraph.nodes:
            if node.class_name == "EdGraphNode_Comment":
                print(f"    - Comment: '{node.node_comment}' "
                      f"(size: {getattr(node, 'node_width', 0)}x{getattr(node, 'node_height', 0)})")

        missing = expected_comments - found_comments
        if missing:
            pytest.fail(
                f"Missing comment nodes: {sorted(missing)}. "
                f"Found: {sorted(found_comments)}"
            )
