"""蓝图图流构建 — 执行流、数据流、连接映射。

等价迁移 uasset_read.py L6478-6620, L6546-6607, L6836-7114。
Phase 31: 蓝图图解析模块。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Set, Any

from uasset_read.constants import (
    START_EVENT_TYPES, CONTROL_FLOW_NODES, BRANCH_TYPE_MAP,
    FORMAT_CONFIG, GRAPH_TYPE_MAP, DATA_BOUNDARY_NODES,
)
from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin
from uasset_read.models.node_types import (
    K2NodeCallFunction, K2NodeEvent, K2NodeKnot,
    EdGraphNodeComment, K2NodeEnhancedInputAction
)

# N2C Processor Registry integration (Phase 69)
from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.definitions import N2CNodeDefinition
from uasset_read.n2c.processor_registry import N2CProcessorRegistry
from uasset_read.n2c.compat import definition_to_node_dict, definition_to_trace_node_info
from uasset_read.n2c.type_registry import N2CNodeTypeRegistry


def _ensure_registry():
    """确保 Processor Registry 已初始化（幂等，conftest-reset-safe）。"""
    from uasset_read.n2c.processors import register_all_processors
    registry = N2CProcessorRegistry.get_instance()
    if not registry._processors or registry._fallback is None:
        register_all_processors()


# ============================================================================
# 辅助函数
# ============================================================================

def _sanitize_string(value: str) -> str:
    """清理字符串中的二进制/null 字符，确保 JSON 安全输出。
    
    保留 \n \r \t 等常用控制字符，移除 null 和其他控制字符。
    """
    if not value:
        return value
    # 移除 null 字符
    value = value.replace('\x00', '')
    # 移除其他控制字符（保留 \n \r \t）
    value = ''.join(c for c in value if c >= ' ' or c in '\n\r\t')
    return value


def _sanitize_pin_dict(pin_dict: dict) -> dict:
    """清理 pin dict 中所有字符串字段。"""
    sanitized = {}
    for key, val in pin_dict.items():
        if isinstance(val, str):
            sanitized[key] = _sanitize_string(val)
        elif isinstance(val, (list, dict)):
            sanitized[key] = _sanitize_recursive(val)
        else:
            sanitized[key] = val
    return sanitized


def _sanitize_recursive(obj):
    """递归清理列表/字典中的字符串。"""
    if isinstance(obj, str):
        return _sanitize_string(obj)
    elif isinstance(obj, list):
        return [_sanitize_recursive(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _sanitize_recursive(v) for k, v in obj.items()}
    return obj


def _derive_node_name(node: UEdGraphNode, idx: int) -> str:
    """从节点派生用户友好的节点名（D-19-02）。

    策略：使用 f"{class_name}_{idx}" 格式，避免同名节点冲突。
    """
    return f"{node.class_name}_{idx}"


def _resolve_node_type(class_name: str) -> N2CNodeType:
    """使用 N2CNodeTypeRegistry 解析节点类型（Phase 68）。"""
    return N2CNodeTypeRegistry.get_instance().resolve(class_name)


def format_pin_ref(
    node_guid: str,
    pin_name: str,
    node_name_lookup: Dict[str, str],
    mode: str = "name"
) -> Dict:
    """格式化 Pin 引用（D-19-02, D-19-05）。

    Args:
        node_guid: 节点 GUID
        pin_name: Pin 名称
        node_name_lookup: node_guid → node_name 查找表
        mode: "name" 或 "guid" 模式（默认 name）

    Returns:
        Dict: 格式化后的 Pin 引用对象
    """
    if mode == "name":
        if node_guid in node_name_lookup:
            return {
                "node": node_name_lookup[node_guid],
                "pin": pin_name
            }
        else:
            return {
                "node_guid": node_guid,
                "pin": pin_name,
                "warning": "node_name lookup failed"
            }
    else:
        return {
            "node_guid": node_guid,
            "pin_name": pin_name
        }


def format_node_dict(node: UEdGraphNode, idx: int) -> Dict:
    """格式化单个节点为 OUT-01 规范 JSON 结构（Phase 31 等价迁移）。

    Per D-20-01: node_name 使用 _derive_node_name() 派生
    Per D-20-02: 字段名规范化（node_type, position:{x,y})
    Per D-20-03: function_reference/event_reference 提升到顶层

    Args:
        node: UEdGraphNode 节点对象
        idx: 节点在图中的索引

    Returns:
        Dict: OUT-01 规范节点结构
    """
    from dataclasses import asdict

    # Phase 69: ensure registry initialized (conftest-reset-safe)
    _ensure_registry()

    # D-20-01: 派生 node_name
    node_name = _derive_node_name(node, idx)

    # D-20-02: 字段名规范化
    result = {
        "node_name": node_name,
        "node_type": node.class_name,
        "node_guid": node.node_guid,
        "position": {"x": node.node_pos_x, "y": node.node_pos_y},
        "node_comment": node.node_comment,
        "pins": [_sanitize_pin_dict(asdict(pin)) for pin in node.pins]  # 添加字符串清理
    }

    # Phase 69: 使用 Processor Registry 替代 if/elif 链
    node_type = _resolve_node_type(node.class_name)
    definition = N2CNodeDefinition(
        node_id=node.node_guid or f"no-guid-{idx}",
        node_type=node_type,
        position=(node.node_pos_x, node.node_pos_y),
        comment=node.node_comment or "",
    )
    N2CProcessorRegistry.get_instance().process_node(node, node_type, definition)

    # 通过 compat 层转换回 OUT-01 格式
    compat_result = definition_to_node_dict(
        definition,
        node_name=node_name,
        node_guid=node.node_guid or "",
        original_class_name=node.class_name,
        pins=result["pins"],
    )
    # 合并 position/node_comment（compat 可能移除了 None 值）
    if "node_comment" not in compat_result and node.node_comment:
        compat_result["node_comment"] = node.node_comment

    result = compat_result

    # Phase 49: CallFunction 节点提取结构化 parameters
    if node.class_name == "K2Node_CallFunction":
        from uasset_read.formatters.json_formatter import _extract_call_function_parameters
        result["parameters"] = _extract_call_function_parameters(node)

    return result


def _get_start_event_name(node: UEdGraphNode) -> str:
    """获取起点节点的事件名称（D-19-11）。

    支持4种起点类型：
    - K2Node_Event: event_reference.member_name（dict或dataclass）
    - K2Node_EnhancedInputAction: input_action_path或class_name
    - K2Node_VariableSet: "VariableSet"
    - K2Node_CustomEvent: "CustomEvent"

    Fallback: 如果无法提取具体名称，返回 node.class_name 而非 "Unknown"。
    """
    nd = node.node_data

    if node.class_name == "K2Node_Event":
        if not nd:
            return node.class_name
        # node_data is a dict from read_k2node_event(), or a K2NodeEvent dataclass
        if isinstance(nd, dict):
            er = nd.get("event_reference")
        else:
            er = getattr(nd, 'event_reference', None)

        if er is None:
            return node.class_name

        # er is FMemberReference object
        if hasattr(er, 'member_name'):
            mn = er.member_name
        elif isinstance(er, dict):
            mn = er.get("member_name")
        else:
            mn = None

        if not mn or mn == "None":
            return node.class_name

        # member_name can be a path like "/Game/.../BP_X_37120"
        if '/' in mn:
            return f"Event.{mn.split('/')[-1]}"
        return f"Event.{mn}"

    elif node.class_name == "K2Node_EnhancedInputAction":
        if nd:
            if isinstance(nd, dict):
                path = nd.get("input_action_path", "")
            else:
                path = getattr(nd, 'input_action_path', "")
            if path:
                return f"InputAction.{path.split('/')[-1] if '/' in path else path}"
        return f"InputAction.{node.class_name}"
    elif node.class_name == "K2Node_VariableSet":
        return "VariableSet"
    elif node.class_name == "K2Node_CustomEvent":
        return "CustomEvent"
    elif node.class_name == "K2Node_FunctionEntry":
        if not nd:
            return node.class_name
        if isinstance(nd, dict):
            fr = nd.get("function_reference")
        else:
            fr = getattr(nd, 'function_reference', None)
        if fr:
            mn = getattr(fr, 'member_name', None) if not isinstance(fr, dict) else fr.get("member_name")
            if mn and mn != "None":
                if '/' in mn:
                    return f"FunctionEntry.{mn.split('/')[-1]}"
                return f"FunctionEntry.{mn}"
        return node.class_name

    return node.class_name


def is_function_graph(graph: UEdGraph) -> bool:
    """判断图是否为函数图（非事件图）。

    组合判断（D-01）：
    1. 含 K2Node_FunctionEntry → Function Graph
    2. 含 K2Node_Event → EventGraph
    3. Fallback: graph_name 模式
    """
    node_types = {n.class_name for n in graph.nodes}
    if "K2Node_FunctionEntry" in node_types:
        return True
    if "K2Node_Event" in node_types:
        return False
    return graph.graph_name.lower() != "eventgraph"


def is_boundary_node(node: UEdGraphNode, pin_name: str) -> bool:
    """判断是否为数据流边界节点（Phase 54）。

    Args:
        node: 目标节点
        pin_name: pin 名称（用于 self 检测）

    Returns:
        bool: True=边界（停止追踪），False=继续追踪
    """
    if node.class_name in DATA_BOUNDARY_NODES:
        return True
    # Self 引用（包括 self 和 Target 别名）
    pin_lower = pin_name.lower()
    if pin_lower == "self" or pin_lower == "target":
        return True
    return False


def _resolve_knot_chain(
    pin_guid: str,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    max_depth: int = 20
) -> Tuple[str, bool]:
    """递归穿透 Knot 链直到到达非 Knot 节点（Phase 54）。

    用于反向数据流追踪：从目标 pin 开始，穿透 Knot 链找到数据源。

    Args:
        pin_guid: 起始 pin GUID（通常是连接到 Knot OutputPin 的目标 pin）
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表
        max_depth: 最大穿透深度（防止无限循环）

    Returns:
        Tuple[str, bool]: (terminal_pin_guid, success)
        - success=True: 找到非 Knot 终端节点
        - success=False: 链断裂或循环检测
    """
    visited: Set[str] = set()
    current_pin_guid = pin_guid

    for _ in range(max_depth):
        if current_pin_guid in visited:
            return (current_pin_guid, False)  # 循环检测

        visited.add(current_pin_guid)

        # Get target node
        target_node_guid, _ = pin_lookup.get(current_pin_guid, (None, None))
        if not target_node_guid:
            return (current_pin_guid, False)  # Pin 不存在

        target_node = node_lookup.get(target_node_guid)
        if not target_node:
            return (current_pin_guid, False)  # Node 不存在

        # Check if Knot
        if target_node.class_name != "K2Node_Knot":
            return (current_pin_guid, True)  # 到达非 Knot 节点

        # Knot: Find InputPin and follow its linked_to_raw backwards
        for pin in target_node.pins:
            if pin.pin_name == "InputPin" and pin.direction == 0:  # Input
                # InputPin 的 linked_to_raw 是上一个 pin（数据来源）
                for linked_ref in (pin.linked_to_raw or []):
                    next_pin_guid = linked_ref.get("pin_guid") if isinstance(linked_ref, dict) else linked_ref
                    current_pin_guid = next_pin_guid
                    break
                break

    return (current_pin_guid, False)  # 超过深度限制


def _trace_data_source(
    pin: UEdGraphPin,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    node_name_lookup: Dict[str, str] = {}
) -> Optional[Dict]:
    """追踪单个参数的数据来源（Phase 54）。

    用于反向数据流追踪：从 CallFunction input pin 开始，穿透 Knot 链，
    找到数据源节点（FunctionEntry 参数、Pure 函数 ReturnValue、self 引用等）。

    Args:
        pin: 目标 pin（通常是 CallFunction input pin）
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表
        node_name_lookup: node_guid → node_name 查找表

    Returns:
        Optional[Dict]: 数据来源标注，或 None（默认值/无连接）
        {
            "data_sources": [
                {
                    "source_type": "pure_function" | "function_parameter" | "self_reference" | "boundary" | "default_value" | "knot_chain_broken" | "pin_not_found" | "node_not_found",
                    "node": str,  # 可选，节点名称
                    "pin": str,   # 可选，pin 名称
                    "function_name": str,  # 可选，函数名（Pure 函数）
                    "value": str  # 可选，默认值
                }
            ]
        }
    """
    # 检查是否有连接
    if not pin.linked_to_raw:
        # 默认值
        if pin.default_value is not None and pin.default_value != "":
            return {"data_sources": [{"source_type": "default_value", "value": pin.default_value}]}
        return None  # 无数据源

    # 遍历连接（可能有多个，但通常只有一个）
    sources: List[Dict] = []
    for linked_ref in pin.linked_to_raw:
        target_pin_guid = linked_ref.get("pin_guid") if isinstance(linked_ref, dict) else linked_ref

        # Knot 穿透
        terminal_pin_guid, success = _resolve_knot_chain(target_pin_guid, pin_lookup, node_lookup)
        if not success:
            sources.append({"source_type": "knot_chain_broken", "pin_guid": terminal_pin_guid})
            continue

        # 获取终端节点
        terminal_node_guid, terminal_pin_name = pin_lookup.get(terminal_pin_guid, (None, None))
        if not terminal_node_guid:
            sources.append({"source_type": "pin_not_found", "pin_guid": terminal_pin_guid})
            continue

        terminal_node = node_lookup.get(terminal_node_guid)
        if not terminal_node:
            sources.append({"source_type": "node_not_found", "node_guid": terminal_node_guid})
            continue

        # 边界检测
        if is_boundary_node(terminal_node, terminal_pin_name):
            # FunctionEntry 参数或 self
            if terminal_node.class_name == "K2Node_FunctionEntry":
                node_name = node_name_lookup.get(terminal_node_guid, terminal_node_guid)
                sources.append({
                    "source_type": "function_parameter",
                    "node": node_name,
                    "pin": terminal_pin_name
                })
            elif terminal_pin_name.lower() == "self" or terminal_pin_name.lower() == "target":
                sources.append({"source_type": "self_reference"})
            else:
                # 其他边界（如 VariableSet）
                node_name = node_name_lookup.get(terminal_node_guid, terminal_node_guid)
                sources.append({
                    "source_type": "boundary",
                    "node": node_name,
                    "pin": terminal_pin_name
                })
        else:
            # 非边界：通常是 Pure 函数输出
            if terminal_node.class_name == "K2Node_CallFunction":
                # 检查是否为 Pure（无 exec pin）
                has_exec_pin = any(p.pin_type and p.pin_type.pin_category == "exec" for p in terminal_node.pins)
                node_name = node_name_lookup.get(terminal_node_guid, terminal_node_guid)

                # 获取函数名
                func_name = None
                nd = terminal_node.node_data
                if nd:
                    fr = nd.get("function_reference") if isinstance(nd, dict) else getattr(nd, 'function_reference', None)
                    if fr:
                        func_name = getattr(fr, 'member_name', None)

                sources.append({
                    "source_type": "pure_function" if not has_exec_pin else "function_output",
                    "node": node_name,
                    "function_name": func_name,
                    "pin": terminal_pin_name
                })

    return {"data_sources": sources} if sources else None


def _find_next_exec_node(
    node: UEdGraphNode,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode]
) -> Optional[UEdGraphNode]:
    """查找 exec output pin 连接的下一个节点。

    Args:
        node: 当前节点
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表

    Returns:
        Optional[UEdGraphNode]: 下一个节点，或 None
    """
    for pin in node.pins:
        if pin.direction == 1:  # Output
            if pin.pin_type and pin.pin_type.pin_category == "exec":
                for linked_pin_id in (pin.linked_to_raw or []):
                    target_pin_guid = linked_pin_id.get("pin_guid") if isinstance(linked_pin_id, dict) else linked_pin_id
                    if target_pin_guid in pin_lookup:
                        target_node_guid, _ = pin_lookup[target_pin_guid]
                        return node_lookup.get(target_node_guid)
    return None


def _trace_execution_from_event(
    start_node: UEdGraphNode,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    node_name_lookup: Dict[str, str] = {}
) -> List[Dict]:
    """追踪单条执行流（D-08-07~11, D-19-13~14, Phase 54）。

    Args:
        start_node: K2Node_Event 起点（或其他START_EVENT_TYPES起点）
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表
        node_name_lookup: node_guid → node_name 查找表（Phase 54 新增）

    Returns:
        List[Dict]: 节点信息序列
    """
    visited: Set[str] = set()
    flow: List[Dict] = []
    current_node = start_node

    while current_node:
        # LOW-07: 处理 node_guid 为 None 的情况
        current_guid = current_node.node_guid
        if current_guid is None:
            # node_guid 缺失时仍记录节点但跳过循环检测
            flow.append({
                "node_type": current_node.class_name,
                "warning": "missing node_guid"
            })
            current_node = _find_next_exec_node(current_node, pin_lookup, node_lookup)
            continue

        if current_guid in visited:
            flow.append({
                "node_guid": current_guid,
                "node_type": current_node.class_name,
                "cycle_detected": True
            })
            break

        visited.add(current_guid)

        node_info = {
            "node_guid": current_guid,
            "node_type": current_node.class_name,
        }

        # Phase 69: 使用 Processor Registry 调度语义提取
        node_type = _resolve_node_type(current_node.class_name)
        definition = N2CNodeDefinition(
            node_id=current_guid,
            node_type=node_type,
            position=(current_node.node_pos_x, current_node.node_pos_y),
            comment=current_node.node_comment or "",
        )
        N2CProcessorRegistry.get_instance().process_node(current_node, node_type, definition)

        # 通过 compat 层映射回 node_info
        semantic_info = definition_to_trace_node_info(
            definition, current_guid, current_node.class_name
        )
        # 合并 semantic 字段（不覆盖已有字段）
        for k, v in semantic_info.items():
            if k not in node_info:
                node_info[k] = v

        # --- 保留：CallFunction 的 parameters 提取（数据流追踪，非语义提取）---
        if current_node.class_name == "K2Node_CallFunction":
            from uasset_read.formatters.json_formatter import _extract_call_function_parameters
            node_info["parameters"] = _extract_call_function_parameters(
                current_node, pin_lookup, node_lookup, node_name_lookup
            )

        # Phase 53: mark pure functions with "pure": true in flow
        has_exec_pin = any(pin.pin_type and pin.pin_type.pin_category == "exec" for pin in current_node.pins)
        if not has_exec_pin:
            node_info["pure"] = True

            # Phase 54: Pure 函数 data_providers 标注（正向追踪）
            data_providers: List[Dict] = []
            for pin in current_node.pins:
                if pin.direction == 1 and pin.pin_type and pin.pin_type.pin_category != "exec":
                    # 找到 output pin 的连接目标
                    for linked_ref in (pin.linked_to_raw or []):
                        target_pin_guid = linked_ref.get("pin_guid") if isinstance(linked_ref, dict) else linked_ref
                        if target_pin_guid in pin_lookup:
                            target_node_guid, target_pin_name = pin_lookup[target_pin_guid]
                            target_node_name = node_name_lookup.get(target_node_guid, target_node_guid)
                            data_providers.append({
                                "output_pin": pin.pin_name,
                                "target_node": target_node_name,
                                "target_pin": target_pin_name
                            })

            if data_providers:
                node_info["data_providers"] = data_providers

        elif current_node.node_data and hasattr(current_node.node_data, 'b_defaults_to_pure') and current_node.node_data.b_defaults_to_pure:
            node_info["pure"] = True

        # 控制流节点终止执行（stopped_at 已由 compat 层设置）
        if current_node.class_name in CONTROL_FLOW_NODES:
            # 确保 branch_type 设置正确（如果 Processor 未覆盖）
            if "branch_type" not in node_info:
                branch_type = BRANCH_TYPE_MAP.get(current_node.class_name, "unknown")
                node_info["branch_type"] = branch_type
            if "stopped_at" not in node_info:
                node_info["stopped_at"] = "control_flow_node"
            flow.append(node_info)
            break

        flow.append(node_info)
        current_node = _find_next_exec_node(current_node, pin_lookup, node_lookup)

    return flow


def _trace_execution_from_pin(
    start_node: UEdGraphNode,
    start_pin: UEdGraphPin,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    node_name_lookup: Dict[str, str] = {}
) -> List[Dict]:
    """从特定Pin开始追踪执行流（D-19-12, Phase 54）。

    用于EnhancedInputAction多触发时机追踪。
    Phase 54: 增加 node_name_lookup 参数传递。
    """
    for linked_pin_id in (start_pin.linked_to_raw or []):
        target_pin_guid = linked_pin_id.get("pin_guid") if isinstance(linked_pin_id, dict) else linked_pin_id
        if target_pin_guid in pin_lookup:
            target_node_guid, _ = pin_lookup[target_pin_guid]
            next_node = node_lookup.get(target_node_guid)
            if next_node:
                return _trace_execution_from_event(next_node, pin_lookup, node_lookup, node_name_lookup)

    return []


# ============================================================================
# 主函数
# ============================================================================

def build_connections_map(graph: UEdGraph) -> Tuple[List[Dict], List[str]]:
    """构建引脚连接映射（D-08-01~06, LINK-01, D-19-01~05）。

    将 linked_to_raw（PinId GUID hex）转换为用户友好的节点引用格式。

    Args:
        graph: UEdGraph 对象

    Returns:
        Tuple[List[Dict], List[str]]: (connections 列表, warnings 列表)
    """
    node_name_lookup: Dict[str, str] = {}
    for idx, node in enumerate(graph.nodes):
        node_name_lookup[node.node_guid] = _derive_node_name(node, idx)

    pin_lookup: Dict[str, Tuple[str, str]] = {}
    for node in graph.nodes:
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

    mode = FORMAT_CONFIG["pin_reference_mode"]
    connections: List[Dict] = []
    warnings: List[str] = []

    for node in graph.nodes:
        for pin in node.pins:
            if pin.direction == 1:  # Output
                for linked_pin_ref in (pin.linked_to_raw or []):
                    target_pin_guid = linked_pin_ref.get("pin_guid") if isinstance(linked_pin_ref, dict) else linked_pin_ref

                    if target_pin_guid in pin_lookup:
                        target_node_guid, target_pin_name = pin_lookup[target_pin_guid]
                        connections.append({
                            "from": format_pin_ref(node.node_guid, pin.pin_name, node_name_lookup, mode),
                            "to": format_pin_ref(target_node_guid, target_pin_name, node_name_lookup, mode)
                        })
                    else:
                        warnings.append(f"PinId {target_pin_guid} not found in graph")
                        connections.append({
                            "from": format_pin_ref(node.node_guid, pin.pin_name, node_name_lookup, mode),
                            "to": {"raw_pin_id": target_pin_guid},
                            "warning": "target pin not found"
                        })

    return connections, warnings


def build_execution_flows(graph: UEdGraph) -> List[Dict]:
    """构建执行流路径（D-08-07~11, D-19-10~12, Phase 54）。

    从 START_EVENT_TYPES 节点开始，沿 exec pin 连接追踪到 CallFunction 链路。
    Phase 54: 增强 CallFunction 数据标注（data_source + data_providers）。

    Args:
        graph: UEdGraph 对象

    Returns:
        List[Dict]: execution_flows 数组
    """
    # Phase 69: ensure registry initialized
    _ensure_registry()

    pin_lookup: Dict[str, Tuple[str, str]] = {}
    node_lookup: Dict[str, UEdGraphNode] = {}
    node_name_lookup: Dict[str, str] = {}  # Phase 54: 新增

    for node in graph.nodes:
        node_lookup[node.node_guid] = node
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

    # Phase 54: 构建 node_name_lookup
    for idx, node in enumerate(graph.nodes):
        node_name_lookup[node.node_guid] = _derive_node_name(node, idx)

    execution_flows: List[Dict] = []
    start_nodes = [n for n in graph.nodes if n.class_name in START_EVENT_TYPES]

    for start_node in start_nodes:
        if start_node.class_name == "K2Node_EnhancedInputAction":
            for pin in start_node.pins:
                if pin.direction == 1 and pin.pin_type and pin.pin_type.pin_category == "exec":
                    flow = _trace_execution_from_pin(start_node, pin, pin_lookup, node_lookup, node_name_lookup)
                    execution_flows.append({
                        "start_event": f"{start_node.class_name}.{pin.pin_name}",
                        "nodes": flow
                    })
        else:
            flow = _trace_execution_from_event(start_node, pin_lookup, node_lookup, node_name_lookup)
            start_event_name = _get_start_event_name(start_node)
            execution_flows.append({
                "start_event": start_event_name,
                "nodes": flow
            })

    return execution_flows


def build_data_flows(graph: UEdGraph, mode: str = "name") -> List[Dict]:
    """构建数据流图（D-19-06~09, LINK-03）。

    从非exec pins提取数据传递关系，构建data_flows数组。

    Args:
        graph: UEdGraph对象
        mode: 输出格式模式（"name"或"guid"，默认"name"）

    Returns:
        List[Dict]: data_flows数组
    """
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    for node in graph.nodes:
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

    node_name_lookup: Dict[str, str] = {}
    for idx, node in enumerate(graph.nodes):
        node_name_lookup[node.node_guid] = _derive_node_name(node, idx)

    data_flows: List[Dict] = []

    for node in graph.nodes:
        for pin in node.pins:
            if pin.direction == 1 and pin.pin_type and pin.pin_type.pin_category != "exec":
                for linked_pin_ref in (pin.linked_to_raw or []):
                    target_pin_guid = linked_pin_ref.get("pin_guid") if isinstance(linked_pin_ref, dict) else linked_pin_ref
                    if target_pin_guid in pin_lookup:
                        target_node_guid, target_pin_name = pin_lookup[target_pin_guid]
                        data_flows.append({
                            "source": format_pin_ref(node.node_guid, pin.pin_name, node_name_lookup, mode),
                            "target": format_pin_ref(target_node_guid, target_pin_name, node_name_lookup, mode)
                        })

    return data_flows


def build_graphs_summary(graphs: List[UEdGraph]) -> List[Dict]:
    """构建所有图的摘要（OUT-03, D-19-09, Phase 71）。

    Args:
        graphs: List[UEdGraph] 图列表

    Returns:
        List[Dict]: graphs_summary 数组
    """
    from .chain_builder import build_execution_chains

    summaries: List[Dict] = []

    for graph in graphs:
        # 图类型映射
        graph_type = GRAPH_TYPE_MAP.get(graph.graph_class, graph.graph_class)

        # 执行流构建（用于 chain_builder）
        execution_flows = build_execution_flows(graph)

        # 执行流链式表达（Phase 71）
        execution_chains = build_execution_chains(graph, execution_flows)

        # 连接映射构建
        connections, warnings = build_connections_map(graph)

        # 数据流构建（D-19-09）
        data_flows = build_data_flows(graph)

        # 过滤空 chain（无实际连接的 flow）
        non_empty_chains = [c for c in execution_chains if c.get("chains")]

        summaries.append({
            "graph_name": graph.graph_name,
            "graph_type": graph_type,
            "node_count": len(graph.nodes),
            "schema": graph.schema,
            "execution_chains": non_empty_chains,  # Phase 71: 链式表达替代 execution_flows
            "connections": connections,
            "data_flows": data_flows,  # D-19-09: 数据流与执行流独立分离
            "warnings": warnings if warnings else None,
        })

    return summaries


def format_graphs_json(graphs: List[UEdGraph]) -> List[Dict]:
    """格式化蓝图图数据为 JSON 输出（GRAPH-11, GRAPH-12, OUT-02, OUT-04, Phase 71）。

    等价迁移 uasset_read_legacy.py L6685-6735。

    Per D-08-03: connections 放在 graph 层级
    Per D-08-09: execution_flows 数组（Phase 71: 改为 execution_chains）
    Per D-19-09: data_flows 数组（LINK-03）
    Per D-20-07: graph_type 语义化映射（EdGraph→event, UberEdGraph→uber）
    Per OUT-01: nodes 使用 format_node_dict 格式化
    Per Phase 71: execution_chains 链式表达替代 execution_flows

    Args:
        graphs: List[UEdGraph] from ParseResult.graphs

    Returns:
        List[Dict]: 每个 graph 的 JSON 表示
    """
    from .chain_builder import build_execution_chains

    formatted = []
    for graph in graphs:
        # 图类型映射
        graph_type = GRAPH_TYPE_MAP.get(graph.graph_class, graph.graph_class)

        # 构建连接映射
        connections, warnings = build_connections_map(graph)

        # 构建执行流
        execution_flows = build_execution_flows(graph)

        # 构建执行流链式表达（Phase 71）
        execution_chains = build_execution_chains(graph, execution_flows)

        # 构建数据流
        data_flows = build_data_flows(graph)

        graph_dict = {
            "graph_name": graph.graph_name,
            "graph_type": graph_type,
            "node_count": len(graph.nodes),  # D-14-04: 顶层 graphs_summary 使用 node_count
            "nodes": [format_node_dict(node, idx) for idx, node in enumerate(graph.nodes)],  # OUT-01: 完整节点列表
            "connections": connections,
            "execution_chains": execution_chains,  # Phase 71: 链式表达替代 execution_flows
            "data_flows": data_flows,
        }

        # D-08-04: 添加 warnings（如果有）
        if warnings:
            graph_dict["warnings"] = warnings

        # 可选字段
        if graph.graph_guid:
            graph_dict["graph_guid"] = graph.graph_guid
        if graph.schema:
            graph_dict["schema"] = graph.schema

        formatted.append(graph_dict)

    return formatted


def _extract_signature_from_pins(fe_node: UEdGraphNode) -> Dict[str, Any]:
    """从 FunctionEntry 节点的 Pins 提取签名（GAP-07）。

    当 blueprint_functions 查找失败时，使用 Pin 信息作为 fallback。

    Args:
        fe_node: K2Node_FunctionEntry 节点

    Returns:
        Dict: 包含 return_type 和 parameters 的签名字典
    """
    from uasset_read.parsers.property_types import format_variable_type

    return_type = ""
    parameters: List[Dict] = []

    for pin in fe_node.pins:
        # 跳过 exec pin
        if pin.pin_type and pin.pin_type.pin_category == "exec":
            continue

        # 输出 Pin → 返回值（Direction=1, pin_name == "ReturnValue"）
        if pin.direction == 1 and pin.pin_name and "return" in pin.pin_name.lower():
            # 提取返回值类型
            if pin.pin_type:
                # 使用 format_variable_type 格式化类型
                return_type = format_variable_type(pin.pin_type)
                # 如果格式化后为空或 "bool" 等基本类型，尝试使用 pin_subcategory
                if not return_type or return_type.lower() in ("bool", "int", "float", "string", "name", "text", "uobject"):
                    sub_cat = getattr(pin.pin_type, 'pin_subcategory', '') or getattr(pin.pin_type, 'pin_sub_category', '') or ''
                    if sub_cat and sub_cat.lower() != "none":
                        return_type = sub_cat

        # 输入 Pin → 参数（Direction=0）
        elif pin.direction == 0:
            pin_name = pin.pin_name or ""
            # 跳过 self/Target（self 引用）
            if pin_name.lower() in ("self", "target", "worldcontext"):
                continue

            # 提取参数类型
            param_type = ""
            if pin.pin_type:
                param_type = format_variable_type(pin.pin_type)
                sub_cat = getattr(pin.pin_type, 'pin_subcategory', '') or getattr(pin.pin_type, 'pin_sub_category', '') or ''
                if sub_cat and sub_cat.lower() != "none":
                    param_type = sub_cat

            parameters.append({
                "name": pin_name,
                "type": param_type,
                "direction": "input"
            })

    return {
        "return_type": return_type,
        "parameters": parameters
    }


def build_function_graphs(
    graphs: List[UEdGraph],
    blueprint_functions: Optional[List] = None,
) -> List[Dict]:
    """构建顶层 function_graphs 数组（Phase 55）。

    每个 FunctionEntry 节点对应一个条目，包含签名、执行流和数据流内嵌标注。

    Args:
        graphs: UEdGraph 列表
        blueprint_functions: BlueprintFunction 列表（用于签名提取）

    Returns:
        List[Dict]: function_graphs 数组
    """
    if not graphs:
        return []

    # 构建 blueprint_functions 查找字典
    func_lookup: Dict[str, Any] = {}
    if blueprint_functions:
        for func in blueprint_functions:
            name = getattr(func, 'name', None)
            if name:
                func_lookup[name] = func

    function_graphs: List[Dict] = []

    for graph in graphs:
        # 构建 pin_lookup 和 node_lookup
        pin_lookup: Dict[str, Tuple[str, str]] = {}
        node_lookup: Dict[str, UEdGraphNode] = {}
        node_name_lookup: Dict[str, str] = {}

        for idx, node in enumerate(graph.nodes):
            node_lookup[node.node_guid] = node
            node_name_lookup[node.node_guid] = _derive_node_name(node, idx)
            for pin in node.pins:
                pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

        # 收集所有 FunctionEntry 节点
        function_entries = [n for n in graph.nodes if n.class_name == "K2Node_FunctionEntry"]

        for fe_node in function_entries:
            # 提取 function_name
            function_name = None
            nd = fe_node.node_data
            if nd:
                fr = nd.get("function_reference") if isinstance(nd, dict) else getattr(nd, 'function_reference', None)
                if fr:
                    raw_name = getattr(fr, 'member_name', None)
                    if raw_name and raw_name != "None":
                        # 处理路径形式 "/Game/.../FunctionName"
                        if '/' in raw_name:
                            function_name = raw_name.split('/')[-1]
                        else:
                            function_name = raw_name

            if not function_name:
                function_name = "Unknown"

            # 查找 blueprint_functions 获取签名
            signature: Dict[str, Any] = {"return_type": "", "parameters": []}
            func_meta = func_lookup.get(function_name)
            if func_meta:
                return_type = getattr(func_meta, 'return_type', '') or ''
                signature["return_type"] = return_type

                # 提取参数
                params = getattr(func_meta, 'parameters', []) or []
                formatted_params: List[Dict] = []
                for p in params:
                    p_name = getattr(p, 'name', '') or ''
                    p_type = getattr(p, 'param_type', '') or ''
                    is_input = getattr(p, 'is_input', True)
                    formatted_params.append({
                        "name": p_name,
                        "type": p_type,
                        "direction": "input" if is_input else "output"
                    })
                signature["parameters"] = formatted_params
            else:
                # GAP-07: 如果 blueprint_functions 查找失败，使用 Pin-based 提取作为 fallback
                signature = _extract_signature_from_pins(fe_node)

            # 构建执行流
            execution_flows = _trace_execution_from_event(
                fe_node, pin_lookup, node_lookup, node_name_lookup
            )

            # 过滤空执行流
            if not execution_flows:
                continue

            # 对每个执行流节点计算 data_providers 和 data_sources
            # 构建数据流字典用于反向查找
            data_flows = build_data_flows(graph, mode="name")

            # 创建辅助函数：从 data_flows 中提取节点的数据流标注
            def _annotate_node_with_data_flow(
                node_guid: str,
                node_type: str,
                node_pins: List[UEdGraphPin],
                d_flows: List[Dict],
                n_name_lookup: Dict[str, str],
                p_lookup: Dict[str, Tuple[str, str]],
                n_lookup: Dict[str, UEdGraphNode]
            ) -> Dict[str, List[Dict]]:
                """从 data_flows 中提取节点的 data_providers 和 data_sources 标注。"""
                node_name = n_name_lookup.get(node_guid, node_guid)
                providers: List[Dict] = []
                sources: List[Dict] = []

                # 遍历节点的 pins
                for pin in node_pins:
                    if pin.pin_type and pin.pin_type.pin_category == "exec":
                        continue

                    # Input pin → data_sources（反向追踪）
                    if pin.direction == 0:
                        # 使用 _trace_data_source 进行反向追踪
                        data_source = _trace_data_source(
                            pin, p_lookup, n_lookup, n_name_lookup
                        )
                        if data_source:
                            sources.append({
                                "input_pin": pin.pin_name,
                                "data_source": data_source
                            })

                    # Output pin → data_providers（正向追踪）
                    elif pin.direction == 1:
                        # 找到 output pin 的连接目标
                        for linked_ref in (pin.linked_to_raw or []):
                            target_pin_guid = linked_ref.get("pin_guid") if isinstance(linked_ref, dict) else linked_ref
                            if target_pin_guid in p_lookup:
                                target_node_guid, target_pin_name = p_lookup[target_pin_guid]
                                target_node_name = n_name_lookup.get(target_node_guid, target_node_guid)
                                providers.append({
                                    "output_pin": pin.pin_name,
                                    "target_node": target_node_name,
                                    "target_pin": target_pin_name
                                })

                return {"data_providers": providers, "data_sources": sources}

            # 遍历执行流节点，添加数据流标注
            annotated_nodes: List[Dict] = []
            for node_info in execution_flows:
                node_guid = node_info.get("node_guid")
                node_type = node_info.get("node_type", "")

                # 获取原始节点对象
                original_node = node_lookup.get(node_guid)

                if original_node:
                    annotation = _annotate_node_with_data_flow(
                        node_guid,
                        node_type,
                        original_node.pins,
                        data_flows,
                        node_name_lookup,
                        pin_lookup,
                        node_lookup
                    )

                    # 合并标注到节点信息（仅在非空时添加）
                    if annotation.get("data_providers"):
                        node_info["data_providers"] = annotation["data_providers"]
                    if annotation.get("data_sources"):
                        node_info["data_sources"] = annotation["data_sources"]

                annotated_nodes.append(node_info)

            # 构建条目
            entry: Dict = {
                "function_name": function_name,
                "graph_source": graph.graph_name,
                "entry_node_guid": fe_node.node_guid,
                "signature": signature,
                "execution_flows": [{
                    "start_event": f"FunctionEntry.{function_name}",
                    "nodes": annotated_nodes
                }]
            }

            function_graphs.append(entry)

    return function_graphs