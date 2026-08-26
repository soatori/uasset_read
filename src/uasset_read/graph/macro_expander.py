"""Blueprint macro expansion engine — recursive MacroInstance expansion, cycle detection, pin mapping, standard macro definitions."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class MacroExpansionContext:
    """Macro expansion context information."""

    macro_name: str
    macro_guid: str
    macro_graph_ref: Dict[str, Any]
    blueprint_ref: Optional[str] = None


@dataclass
class MacroExpansion:
    """Macro expansion result."""

    context: MacroExpansionContext
    expanded_nodes: List[Dict[str, Any]] = field(default_factory=list)
    pin_mapping: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    entry_tunnels: List[Dict[str, Any]] = field(default_factory=list)
    exit_tunnels: List[Dict[str, Any]] = field(default_factory=list)
    internal_flows: List[Dict[str, Any]] = field(default_factory=list)
    nested_expansions: List["MacroExpansion"] = field(default_factory=list)
    unresolved: bool = False


# ──────────────────────────────────────────────────────
# Standard macro definitions (built into the engine, not in user assets)
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
# Standard macro -> C++ control flow mapping
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
    """Macro expander."""

    def __init__(self, asset_context: Dict[str, Any]):
        self.asset_context = asset_context
        self.visited_guids: Set[str] = set()
        self.expansion_stack: List[MacroExpansionContext] = []

    def expand_macro_instance(self, instance_node: Dict[str, Any]) -> MacroExpansion:
        """Expand a single macro instance.

        Args:
            instance_node: node dictionary containing macro_graph_reference

        Returns:
            MacroExpansion expansion result

        Raises:
            ValueError: raised when a macro cycle is detected
        """
        macro_ref = instance_node.get("macro_graph_reference", {})
        graph_guid = macro_ref.get("graph_guid", "")
        graph_name = macro_ref.get("graph_name", "")

        # Prioritize user-defined macro graphs (user-defined takes precedence over standard macros when names match)
        # If the asset contains a graph with the same name, expand the user-defined version
        macro_graph = self._find_macro_graph(macro_ref)
        if macro_graph is not None:
            # User-defined macro takes priority, expand normally
            pass
        elif graph_name in STANDARD_MACROS:
            # Only use standard macro expansion when no same-name graph exists
            return self._create_standard_expansion(graph_name, macro_ref)

        # Cycle detection
        if graph_guid and graph_guid in self.visited_guids:
            raise ValueError(
                "Macro cycle detected: "
                + " -> ".join(ctx.macro_name for ctx in self.expansion_stack)
                + " -> "
                + graph_name
            )

        # Find macro graph
        macro_graph = self._find_macro_graph(macro_ref)
        if macro_graph is None:
            return self._create_unresolved_expansion(instance_node, macro_ref)

        # Mark as visited
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
        """Find macro graph in the asset.

        Search priority:
        1. Current asset's graphs list (exact GUID match, skip empty GUID)
        2. Current asset's graphs list (exact name match, skip empty name)
        3. Current asset's graphs list (case-insensitive name match -- GUID fallback)
        4. graphs in resolved_parent_assets (cross-blueprint references)
        """
        graph_guid = macro_ref.get("graph_guid") or ""
        graph_name = macro_ref.get("graph_name") or ""

        all_graphs = self.asset_context.get("graphs", [])

        # 1. GUID exact match (skip empty/None GUID to avoid false matches)
        if graph_guid:
            for graph in all_graphs:
                if graph.get("guid") == graph_guid:
                    return graph

        # 2. Name exact match (skip empty name)
        if graph_name:
            for graph in all_graphs:
                if graph.get("name") == graph_name:
                    return graph

        # 3. Case-insensitive name match (fallback when GUID fails)
        if graph_name:
            name_lower = graph_name.lower()
            for graph in all_graphs:
                gname = graph.get("name") or ""
                if gname.lower() == name_lower:
                    return graph

        # 4. Search in resolved_parent_assets (cross-blueprint references)
        for parent_asset in self.asset_context.get("resolved_parent_assets", []):
            for graph in parent_asset.get("graphs", []):
                if graph_guid and graph.get("guid") == graph_guid:
                    return graph
                if graph_name and graph.get("name") == graph_name:
                    return graph

        return None

    def _expand_graph(self, macro_graph: Dict[str, Any], ctx: MacroExpansionContext) -> MacroExpansion:
        """Expand internal nodes of a macro graph.

        Processing flow:
        1. Separate Tunnel nodes and regular nodes
        2. Build pin mapping from Tunnels
        3. Recursively expand nested MacroInstance
        4. Build internal execution flow
        """
        nodes = macro_graph.get("nodes", [])

        entry_tunnels: List[Dict[str, Any]] = []
        exit_tunnels: List[Dict[str, Any]] = []
        internal_nodes: List[Dict[str, Any]] = []

        for node in nodes:
            if node.get("node_type") == "K2Node_Tunnel":
                # Only process exact UK2Node_Tunnel (exclude subclasses)
                if node.get("exact_class") == "UK2Node_Tunnel":
                    if node.get("b_can_have_outputs"):
                        exit_tunnels.append(node)
                    if node.get("b_can_have_inputs"):
                        entry_tunnels.append(node)
                    continue
            internal_nodes.append(node)

        # Build pin mapping
        pin_mapping = self._build_pin_mapping(entry_tunnels, exit_tunnels)

        # Recursively expand nested macros
        nested_expansions: List[MacroExpansion] = []
        for node in internal_nodes:
            if node.get("node_type") == "K2Node_MacroInstance":
                nested = self.expand_macro_instance(node)
                nested_expansions.append(nested)

        # Build internal execution flow
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
        """Build mapping from Tunnel pins to Instance pins.

        Rules:
        - Direction reversal: Tunnel's Output -> Instance's Input
        - Only process top-level pins (parent_pin is None)
        """
        mapping: Dict[str, Dict[str, Any]] = {}
        for tunnel in entry_tunnels + exit_tunnels:
            for pin in tunnel.get("pins", []):
                if pin.get("parent_pin") is None:
                    direction = pin.get("direction", "")
                    # Direction reversal (compatible with int and str)
                    if self._is_output_direction(direction):
                        instance_dir = "EGPD_Input"
                    else:
                        instance_dir = "EGPD_Output"
                    mapping[pin["pin_name"]] = {
                        "instance_direction": instance_dir,
                        "pin_type": pin.get("pin_type", {}),
                        "default_value": pin.get("default_value", ""),
                        "tunnel_type": "entry" if tunnel in entry_tunnels else "exit",
                    }
        return mapping

    @staticmethod
    def _is_output_direction(direction) -> bool:
        """Determine if direction is output (compatible with int 1 and str "EGPD_Output")."""
        return direction == 1 or direction == "EGPD_Output"

    @staticmethod
    def _is_input_direction(direction) -> bool:
        """Determine if direction is input (compatible with int 0 and str "EGPD_Input")."""
        return direction == 0 or direction == "EGPD_Input"

    def _build_internal_flows(
        self,
        entry_tunnels: List[Dict[str, Any]],
        internal_nodes: List[Dict[str, Any]],
        exit_tunnels: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build internal execution flow within a macro.

        Starting from entry_tunnels' exec output pins, finds connected internal node entries
        via linked_to_raw, then traces the execution chain along exec output pins.

        Returns:
            List of flow dicts, each containing:
            - "entry_tunnel": entry Tunnel pin name
            - "nodes": list of internal nodes in execution order
        """
        if not entry_tunnels or not internal_nodes:
            return []

        # Build pin_id -> (node_guid, pin_name) lookup table for internal nodes
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

        # Collect exit tunnel exec input pin_ids for termination detection
        # Also record all exit tunnel node_guids to avoid misclassifying internal nodes
        exit_pin_ids: Set[str] = set()
        exit_node_guids: Set[str] = set()
        for tunnel in exit_tunnels:
            tunnel_guid = tunnel.get("node_guid", "")
            if tunnel_guid:
                exit_node_guids.add(tunnel_guid)
            for pin in tunnel.get("pins", []):
                if self._is_input_direction(pin.get("direction")):  # input pin
                    pid = pin.get("pin_id", "")
                    if pid:
                        exit_pin_ids.add(pid)

        flows: List[Dict[str, Any]] = []

        for entry in entry_tunnels:
            # Find entry tunnel's exec output pin (direction=1)
            for pin in entry.get("pins", []):
                if not self._is_output_direction(pin.get("direction")):
                    continue
                pt = pin.get("pin_type", {})
                if pt.get("pin_category") != "exec":
                    continue

                pin_name = pin.get("pin_name", "")
                # Find the first connected internal node via linked_to_raw
                first_node = None
                for linked_ref in pin.get("linked_to_raw") or []:
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

                # BFS trace exec chain
                flow_nodes: List[Dict[str, Any]] = []
                visited: Set[str] = set()
                # Pending exec output pin reference list
                pending_refs: List[str] = []

                # Start from the first internal node
                first_guid = first_node.get("node_guid", "")
                if first_guid:
                    visited.add(first_guid)
                    flow_nodes.append(first_node)
                    # Collect linked_to_raw of this node's exec output pin
                    for out_pin in first_node.get("pins", []):
                        if not self._is_output_direction(out_pin.get("direction")):
                            continue
                        out_pt = out_pin.get("pin_type", {})
                        if out_pt.get("pin_category") != "exec":
                            continue
                        for ref in out_pin.get("linked_to_raw") or []:
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
                        # Terminate when reaching exit tunnel node
                        if target_guid in exit_node_guids:
                            continue
                        visited.add(target_guid)

                        node = node_by_guid.get(target_guid)
                        if node is None:
                            continue
                        flow_nodes.append(node)

                        # Collect linked_to_raw of this node's exec output pin
                        for out_pin in node.get("pins", []):
                            if not self._is_output_direction(out_pin.get("direction")):
                                continue
                            out_pt = out_pin.get("pin_type", {})
                            if out_pt.get("pin_category") != "exec":
                                continue
                            for ref in out_pin.get("linked_to_raw") or []:
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
                    flows.append(
                        {
                            "entry_tunnel": pin_name,
                            "nodes": flow_nodes,
                        }
                    )

        return flows

    def _create_standard_expansion(
        self,
        macro_name: str,
        macro_ref: Dict[str, Any],
    ) -> MacroExpansion:
        """Create expansion result for standard macros (does not expand internal nodes)."""
        info = STANDARD_MACROS[macro_name]
        pin_mapping: Dict[str, Dict[str, Any]] = {}
        # Input pins
        for name in info["inputs"]:
            pin_mapping[name] = {"instance_direction": "EGPD_Input", "is_standard": True}
        # Output pins
        for name in info["outputs"]:
            pin_mapping[name] = {"instance_direction": "EGPD_Output", "is_standard": True}
        return MacroExpansion(
            context=MacroExpansionContext(
                macro_name=macro_name,
                macro_guid="",
                macro_graph_ref=macro_ref,
            ),
            pin_mapping=pin_mapping,
            expanded_nodes=[],
            internal_flows=[],
        )

    def _create_unresolved_expansion(
        self,
        instance_node: Dict[str, Any],
        macro_ref: Dict[str, Any],
    ) -> MacroExpansion:
        """Create unresolved expansion result (macro graph not found)."""
        return MacroExpansion(
            context=MacroExpansionContext(
                macro_name=macro_ref.get("graph_name", "Unknown"),
                macro_guid=macro_ref.get("graph_guid", ""),
                macro_graph_ref=macro_ref,
            ),
            unresolved=True,
        )
