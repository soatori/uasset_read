"""Graph 序列化模块 — 蓝图图二进制序列化器。

拆分后的子模块：
- _common.py: 共享工具函数（GUID、FText、线程状态等）
- pin_types.py: FEdGraphPinType 读取
- members.py: FMemberReference 读取
- pins.py: Pin 引用、数组、UEdGraphPin 读取
- k2_nodes.py: K2Node 类型读取器
- nodes.py: UEdGraphNode 读取与节点工厂
- graph.py: UEdGraph 容器读取
"""
from __future__ import annotations

# Re-export all public functions for backward compatibility
from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
from uasset_read.serializers.graph.members import read_fmember_reference
from uasset_read.serializers.graph.pins import read_ue_graph_pin, read_pin_reference, read_pin_array
from uasset_read.serializers.graph._common import (
    get_pin_trace_events,
    reset_pin_trace_events,
    _recover_pin_array_count,
    _try_recover_to_subpins,
    _read_guid,
)
from uasset_read.serializers.graph.nodes import read_ue_graph_node, create_node_from_archive
from uasset_read.serializers.graph.graph import read_ue_graph

# Also re-export K2Node readers for tests and models that import them directly
from uasset_read.serializers.graph.k2_nodes import (
    read_k2node_call_function,
    read_k2node_event,
    read_k2node_knot,
    read_edgraph_node_comment,
    read_k2node_enhanced_input,
    read_k2node_functionentry,
    read_k2node_message,
    read_k2node_call_delegate,
    read_k2node_call_array_function,
    read_k2node_call_parent_function,
    read_k2node_function_result,
    read_k2node_create_widget,
    read_k2node_add_delegate,
    read_k2node_macro_instance,
    read_k2node_assign_delegate,
    read_k2node_get_data_table_row,
    read_k2node_load_asset,
    read_k2node_spawn_actor_from_class,
)

__all__ = [
    # Main orchestration
    'read_ue_graph', 'read_ue_graph_node', 'read_ue_graph_pin',
    'read_ed_graph_pin_type', 'read_fmember_reference',
    'create_node_from_archive',
    # Pin readers
    'read_pin_reference',
    'read_pin_array',
    # K2Node readers
    'read_k2node_call_function',
    'read_k2node_event',
    'read_k2node_knot',
    'read_edgraph_node_comment',
    'read_k2node_enhanced_input',
    'read_k2node_functionentry',
    'read_k2node_message',
    'read_k2node_call_delegate',
    'read_k2node_call_array_function',
    'read_k2node_call_parent_function',
    'read_k2node_function_result',
    'read_k2node_create_widget',
    'read_k2node_add_delegate',
    'read_k2node_macro_instance',
    'read_k2node_assign_delegate',
    'read_k2node_get_data_table_row',
    'read_k2node_load_asset',
    'read_k2node_spawn_actor_from_class',
    # Pin trace diagnostics
    'get_pin_trace_events',
    'reset_pin_trace_events',
]
