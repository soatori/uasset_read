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
        """构建宏内部执行流（简化版）。

        这里复用 flow_builder 的追踪逻辑，传入宏图的节点。
        注意：需要将 internal_nodes 适配为 UEdGraphNode 列表。
        """
        # TODO: 后续接入 flow_builder 的追踪逻辑
        return []

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
