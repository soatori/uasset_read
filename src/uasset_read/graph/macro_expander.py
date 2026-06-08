"""蓝图宏展开引擎 — 递归展开 MacroInstance，循环检测，引脚映射，标准宏定义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class MacroExpansionContext:
    """宏展开的上下文信息。"""
    macro_name: str
    macro_guid: str
    macro_graph_ref: Dict[str, Any]
    blueprint_ref: Optional[str] = None


class MacroCycleError(Exception):
    """宏循环检测异常。"""
    def __init__(self, cycle_path: List[MacroExpansionContext]):
        self.cycle_path = cycle_path
        names = [ctx.macro_name for ctx in cycle_path]
        message = f"宏循环检测: {' -> '.join(names)} -> {names[0]}"
        super().__init__(message)


@dataclass
class MacroExpansion:
    """宏展开结果。"""
    context: MacroExpansionContext
    expanded_nodes: List[Dict[str, Any]] = field(default_factory=list)
    pin_mapping: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    entry_tunnels: List[Dict[str, Any]] = field(default_factory=list)
    exit_tunnels: List[Dict[str, Any]] = field(default_factory=list)
    internal_flows: List[Dict[str, Any]] = field(default_factory=list)
    nested_expansions: List["MacroExpansion"] = field(default_factory=list)
    unresolved: bool = False


# ──────────────────────────────────────────────────────
# 标准宏定义（内置于引擎，不在用户资产中）
# ──────────────────────────────────────────────────────

STANDARD_MACROS: Dict[str, Dict[str, Any]] = {
    "ForLoop": {
        "inputs": ["Entry", "LastIndex", "FirstIndex", "Increment"],
        "outputs": ["Loop Body", "Completed", "Loop Counter"],
        "is_loop": True,
        "is_standard": True,
    },
    "ForLoopWithBreak": {
        "inputs": ["Entry", "LastIndex", "FirstIndex", "Increment", "Break"],
        "outputs": ["Loop Body", "Completed", "Loop Counter"],
        "is_loop": True,
        "is_standard": True,
    },
    "WhileLoop": {
        "inputs": ["Entry", "Condition"],
        "outputs": ["Loop Body", "Completed"],
        "is_loop": True,
        "is_standard": True,
    },
    "Gate": {
        "inputs": ["Enter", "Open", "Close", "Toggle"],
        "outputs": ["Exit"],
        "is_loop": False,
        "is_standard": True,
    },
    "Do N": {
        "inputs": ["Enter", "N"],
        "outputs": ["Exit", "Completed"],
        "is_loop": False,
        "is_standard": True,
    },
    "DoOnce": {
        "inputs": ["Enter", "Reset"],
        "outputs": ["Exit"],
        "is_loop": False,
        "is_standard": True,
    },
    "IsValid": {
        "inputs": ["Input"],
        "outputs": ["Valid", "Invalid"],
        "is_loop": False,
        "is_standard": True,
    },
    "FlipFlop": {
        "inputs": ["A"],
        "outputs": ["A", "B", "IsA"],
        "is_loop": False,
        "is_standard": True,
    },
    "ForEachLoop": {
        "inputs": ["Entry", "Array"],
        "outputs": ["Loop Body", "Completed", "Array Element", "Array Index"],
        "is_loop": True,
        "is_standard": True,
    },
    "ForEachLoopWithBreak": {
        "inputs": ["Entry", "Array", "Break"],
        "outputs": ["Loop Body", "Completed", "Array Element", "Array Index"],
        "is_loop": True,
        "is_standard": True,
    },
    "Branch": {
        "inputs": ["Condition"],
        "outputs": ["True", "False"],
        "is_loop": False,
        "is_standard": True,
    },
    "Delay": {
        "inputs": ["Duration"],
        "outputs": ["Completed"],
        "is_loop": False,
        "is_standard": True,
    },
    "RetriggerableDelay": {
        "inputs": ["Duration"],
        "outputs": ["Completed"],
        "is_loop": False,
        "is_standard": True,
    },
    "Select": {
        "inputs": ["Index", "A", "B"],
        "outputs": ["ReturnValue"],
        "is_loop": False,
        "is_standard": True,
    },
    "SwitchOnInt": {
        "inputs": ["Value"],
        "outputs": ["0", "1", "2", "3", "4", "Default"],
        "is_loop": False,
        "is_standard": True,
    },
}


# ──────────────────────────────────────────────────────
# 标准宏 → C++ 控制流映射
# ──────────────────────────────────────────────────────

STANDARD_MACRO_CPP_MAPPING: Dict[str, Dict[str, Any]] = {
    "ForLoop": {
        "cpp_statement": "for",
        "cpp_template": "for (int {LoopCounter} = {FirstIndex}; {LoopCounter} <= {LastIndex}; {LoopCounter} += {Increment})",
        "loop_body_pin": "Loop Body",
        "completed_pin": "Completed",
    },
    "ForLoopWithBreak": {
        "cpp_statement": "for",
        "cpp_template": "for (int {LoopCounter} = {FirstIndex}; {LoopCounter} <= {LastIndex}; {LoopCounter} += {Increment}) /* break */",
        "loop_body_pin": "Loop Body",
        "completed_pin": "Completed",
    },
    "WhileLoop": {
        "cpp_statement": "while",
        "cpp_template": "while ({Condition})",
        "loop_body_pin": "Loop Body",
        "completed_pin": "Completed",
    },
    "ForEachLoop": {
        "cpp_statement": "for_each",
        "cpp_template": "for (auto& {ArrayElement} : {Array})",
        "loop_body_pin": "Loop Body",
        "completed_pin": "Completed",
    },
    "ForEachLoopWithBreak": {
        "cpp_statement": "for_each",
        "cpp_template": "for (auto& {ArrayElement} : {Array}) /* break */",
        "loop_body_pin": "Loop Body",
        "completed_pin": "Completed",
    },
    "Gate": {
        "cpp_statement": "gate",
        "cpp_template": "// Gate: open/close control flow",
    },
    "Do N": {
        "cpp_statement": "for",
        "cpp_template": "for (int _counter = 0; _counter < {N}; _counter++)",
    },
    "DoOnce": {
        "cpp_statement": "do_once",
        "cpp_template": "/* DoOnce: executes once until reset */",
    },
    "IsValid": {
        "cpp_statement": "if",
        "cpp_template": "if (IsValid({Input}))",
    },
    "FlipFlop": {
        "cpp_statement": "flipflop",
        "cpp_template": "/* FlipFlop: alternates between A and B */",
    },
    "Branch": {
        "cpp_statement": "if",
        "cpp_template": "if ({Condition})",
    },
    "Delay": {
        "cpp_statement": "delay",
        "cpp_template": "/* Latent: Delay({Duration}) */",
    },
    "RetriggerableDelay": {
        "cpp_statement": "delay",
        "cpp_template": "/* Latent: RetriggerableDelay({Duration}) */",
    },
    "Select": {
        "cpp_statement": "ternary",
        "cpp_template": "auto {ReturnValue} = {Index} ? {A} : {B};",
    },
    "SwitchOnInt": {
        "cpp_statement": "switch",
        "cpp_template": "switch ({Value}) { /* cases */ }",
    },
}


class MacroExpander:
    """宏展开器。"""

    def __init__(self, asset_context: Dict[str, Any]):
        self.asset_context = asset_context
        self.visited_guids: Set[str] = set()
        self.expansion_stack: List[MacroExpansionContext] = []

    def expand_macro_instance(self, instance_node: Dict[str, Any]) -> MacroExpansion:
        """展开单个宏实例。

        Args:
            instance_node: 包含 macro_graph_reference 的节点字典

        Returns:
            MacroExpansion 展开结果

        Raises:
            MacroCycleError: 检测到宏循环时抛出
        """
        macro_ref = instance_node.get("macro_graph_reference", {})
        graph_guid = macro_ref.get("graph_guid", "")
        graph_name = macro_ref.get("graph_name", "")

        # 检查标准宏（不需要展开内部节点）
        if graph_name in STANDARD_MACROS:
            return self._create_standard_expansion(graph_name, macro_ref)

        # 循环检测
        if graph_guid and graph_guid in self.visited_guids:
            raise MacroCycleError(self.expansion_stack.copy() + [
                MacroExpansionContext(
                    macro_name=graph_name,
                    macro_guid=graph_guid,
                    macro_graph_ref=macro_ref,
                )
            ])

        # 查找宏图
        macro_graph = self._find_macro_graph(macro_ref)
        if macro_graph is None:
            return self._create_unresolved_expansion(instance_node, macro_ref)

        # 标记已访问
        if graph_guid:
            self.visited_guids.add(graph_guid)

        ctx = MacroExpansionContext(
            macro_name=graph_name,
            macro_guid=graph_guid,
            macro_graph_ref=macro_ref,
        )
        self.expansion_stack.append(ctx)

        try:
            expansion = self._expand_graph(macro_graph, ctx)
            return expansion
        finally:
            self.expansion_stack.pop()
            if graph_guid:
                self.visited_guids.discard(graph_guid)

    def _find_macro_graph(self, macro_ref: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """在资产中查找宏图。

        按优先级查找：
        1. 当前资产的 graphs 列表（按 GUID 匹配）
        2. 当前资产的 graphs 列表（按名称匹配）
        3. resolved_parent_assets 中的 graphs（跨蓝图引用）
        """
        graph_guid = macro_ref.get("graph_guid")
        graph_name = macro_ref.get("graph_name")

        # 1. 在当前资产的所有 Graph 中查找
        for graph in self.asset_context.get("graphs", []):
            if graph.get("guid") == graph_guid:
                return graph
            if graph.get("name") == graph_name:
                return graph

        # 2. 在 resolved_parent_assets 中查找（跨蓝图引用）
        for parent_asset in self.asset_context.get("resolved_parent_assets", []):
            for graph in parent_asset.get("graphs", []):
                if graph.get("guid") == graph_guid:
                    return graph

        return None

    def _expand_graph(self, macro_graph: Dict[str, Any], ctx: MacroExpansionContext) -> MacroExpansion:
        """展开宏图内部节点。

        处理流程：
        1. 分离 Tunnel 节点和普通节点
        2. 从 Tunnel 构建引脚映射
        3. 递归展开嵌套 MacroInstance
        4. 构建内部执行流
        """
        nodes = macro_graph.get("nodes", [])

        entry_tunnels: List[Dict[str, Any]] = []
        exit_tunnels: List[Dict[str, Any]] = []
        internal_nodes: List[Dict[str, Any]] = []

        for node in nodes:
            if node.get("node_type") == "K2Node_Tunnel":
                # 只处理精确的 UK2Node_Tunnel（排除子类）
                if node.get("exact_class") == "UK2Node_Tunnel":
                    if node.get("b_can_have_outputs"):
                        exit_tunnels.append(node)
                    if node.get("b_can_have_inputs"):
                        entry_tunnels.append(node)
                    continue
            internal_nodes.append(node)

        # 构建引脚映射
        pin_mapping = self._build_pin_mapping(entry_tunnels, exit_tunnels)

        # 递归展开嵌套宏
        nested_expansions: List[MacroExpansion] = []
        for node in internal_nodes:
            if node.get("node_type") == "K2Node_MacroInstance":
                nested = self.expand_macro_instance(node)
                nested_expansions.append(nested)

        # 构建内部执行流
        internal_flows = self._build_internal_flows(entry_tunnels, internal_nodes, exit_tunnels)

        return MacroExpansion(
            context=ctx,
            expanded_nodes=internal_nodes,
            pin_mapping=pin_mapping,
            entry_tunnels=entry_tunnels,
            exit_tunnels=exit_tunnels,
            internal_flows=internal_flows,
            nested_expansions=nested_expansions,
        )

    def _build_pin_mapping(
        self,
        entry_tunnels: List[Dict[str, Any]],
        exit_tunnels: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """构建 Tunnel 引脚到 Instance 引脚的映射。

        规则：
        - 方向取反：Tunnel 的 Output -> Instance 的 Input
        - 只处理顶层引脚（parent_pin 为 None）
        """
        mapping: Dict[str, Dict[str, Any]] = {}
        for tunnel in entry_tunnels + exit_tunnels:
            for pin in tunnel.get("pins", []):
                if pin.get("parent_pin") is None:
                    direction = pin.get("direction", "")
                    # 方向取反
                    instance_dir = "EGPD_Input" if direction == "EGPD_Output" else "EGPD_Output"
                    mapping[pin["pin_name"]] = {
                        "instance_direction": instance_dir,
                        "pin_type": pin.get("pin_type", {}),
                        "default_value": pin.get("default_value", ""),
                        "tunnel_type": "entry" if tunnel in entry_tunnels else "exit",
                    }
        return mapping

    def _build_internal_flows(
        self,
        entry_tunnels: List[Dict[str, Any]],
        internal_nodes: List[Dict[str, Any]],
        exit_tunnels: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """构建宏内部执行流。

        从 entry_tunnels 的 exec output pin 出发，通过 linked_to_raw
        找到连接的内部节点入口，然后沿 exec output pin 追踪执行链。

        Returns:
            List of flow dicts，每个包含:
            - "entry_tunnel": 入口 Tunnel 引脚名
            - "nodes": 按执行顺序排列的内部节点列表
        """
        if not entry_tunnels or not internal_nodes:
            return []

        # 构建内部节点的 pin_id → (node_guid, pin_name) 查找表
        pin_lookup: Dict[str, Tuple[str, str]] = {}
        node_by_guid: Dict[str, Dict[str, Any]] = {}
        for node in internal_nodes:
            guid = node.get("node_guid", "")
            if guid:
                node_by_guid[guid] = node
            for pin in node.get("pins", []):
                pid = pin.get("pin_id", "")
                if pid:
                    pin_lookup[pid] = (guid, pin.get("pin_name", ""))

        # 收集 exit tunnel 的 exec input pin_id 用于终止检测
        # 同时记录所有 exit tunnel 的 node_guid，避免误判内部节点
        exit_pin_ids: Set[str] = set()
        exit_node_guids: Set[str] = set()
        for tunnel in exit_tunnels:
            tunnel_guid = tunnel.get("node_guid", "")
            if tunnel_guid:
                exit_node_guids.add(tunnel_guid)
            for pin in tunnel.get("pins", []):
                if pin.get("direction") == 0:  # input pin
                    pid = pin.get("pin_id", "")
                    if pid:
                        exit_pin_ids.add(pid)

        flows: List[Dict[str, Any]] = []

        for entry in entry_tunnels:
            # 找 entry tunnel 的 exec output pin (direction=1)
            for pin in entry.get("pins", []):
                if pin.get("direction") != 1:
                    continue
                pt = pin.get("pin_type", {})
                if pt.get("pin_category") != "exec":
                    continue

                pin_name = pin.get("pin_name", "")
                start_pid = pin.get("pin_id", "")

                # 通过 linked_to_raw 找到连接的第一个内部节点
                first_node = None
                for linked_ref in (pin.get("linked_to_raw") or []):
                    if isinstance(linked_ref, str):
                        target_pid = linked_ref
                    elif isinstance(linked_ref, dict):
                        target_pid = linked_ref.get("pin_id", "")
                    else:
                        continue
                    if target_pid in pin_lookup:
                        target_guid, _ = pin_lookup[target_pid]
                        first_node = node_by_guid.get(target_guid)
                        if first_node:
                            break

                if first_node is None:
                    continue

                # BFS 追踪 exec 链
                flow_nodes: List[Dict[str, Any]] = []
                visited: Set[str] = set()
                # 待处理的 exec output pin 引用列表
                pending_refs: List[str] = []

                # 从第一个内部节点开始
                first_guid = first_node.get("node_guid", "")
                if first_guid:
                    visited.add(first_guid)
                    flow_nodes.append(first_node)
                    # 收集该节点的 exec output pin 的 linked_to_raw
                    for out_pin in first_node.get("pins", []):
                        if out_pin.get("direction") != 1:
                            continue
                        out_pt = out_pin.get("pin_type", {})
                        if out_pt.get("pin_category") != "exec":
                            continue
                        for ref in (out_pin.get("linked_to_raw") or []):
                            if isinstance(ref, str):
                                pending_refs.append(ref)
                            elif isinstance(ref, dict):
                                ref_id = ref.get("pin_id", "")
                                if ref_id:
                                    pending_refs.append(ref_id)

                while pending_refs:
                    next_refs: List[str] = []
                    for ref_pid in pending_refs:
                        if ref_pid in exit_pin_ids:
                            continue
                        if ref_pid not in pin_lookup:
                            continue
                        target_guid, _ = pin_lookup[ref_pid]
                        if not target_guid or target_guid in visited:
                            continue
                        # 到达 exit tunnel 节点时终止
                        if target_guid in exit_node_guids:
                            continue
                        visited.add(target_guid)

                        node = node_by_guid.get(target_guid)
                        if node is None:
                            continue
                        flow_nodes.append(node)

                        # 收集该节点的 exec output pin 的 linked_to_raw
                        for out_pin in node.get("pins", []):
                            if out_pin.get("direction") != 1:
                                continue
                            out_pt = out_pin.get("pin_type", {})
                            if out_pt.get("pin_category") != "exec":
                                continue
                            for ref in (out_pin.get("linked_to_raw") or []):
                                if isinstance(ref, str):
                                    if ref not in visited:
                                        next_refs.append(ref)
                                elif isinstance(ref, dict):
                                    ref_id = ref.get("pin_id", "")
                                    if ref_id and ref_id not in visited:
                                        next_refs.append(ref_id)

                    pending_refs = next_refs
                    if len(visited) > 200:
                        break

                if flow_nodes:
                    flows.append({
                        "entry_tunnel": pin_name,
                        "nodes": flow_nodes,
                    })

        return flows

    def _create_standard_expansion(
        self,
        macro_name: str,
        macro_ref: Dict[str, Any],
    ) -> MacroExpansion:
        """为标准宏创建展开结果（不展开内部节点）。"""
        info = STANDARD_MACROS[macro_name]
        return MacroExpansion(
            context=MacroExpansionContext(
                macro_name=macro_name,
                macro_guid="",
                macro_graph_ref=macro_ref,
            ),
            pin_mapping={
                name: {"instance_direction": "EGPD_Input", "is_standard": True}
                for name in info["inputs"]
            },
            expanded_nodes=[],
            internal_flows=[],
        )

    def _create_unresolved_expansion(
        self,
        instance_node: Dict[str, Any],
        macro_ref: Dict[str, Any],
    ) -> MacroExpansion:
        """创建未解析的展开结果（宏图找不到）。"""
        return MacroExpansion(
            context=MacroExpansionContext(
                macro_name=macro_ref.get("graph_name", "Unknown"),
                macro_guid=macro_ref.get("graph_guid", ""),
                macro_graph_ref=macro_ref,
            ),
            unresolved=True,
        )
