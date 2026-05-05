#!/usr/bin/env python3
"""
测试脚本 - 收集Pin解析调试数据
"""
import sys
sys.argv.append('--debug-pin')
sys.argv.append('--debug-ftext')

# 导入uasset_read（这会触发DEBUG_PIN_PARSING的设置）
import uasset_read
from uasset_read import parse_uasset
import json

print(f"DEBUG_PIN_PARSING flag: {uasset_read.DEBUG_PIN_PARSING}")

# 解析测试资产
file_path = r'E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset'
print(f"Parsing: {file_path}")
print("=" * 80)

result = parse_uasset(file_path)

print(f"\nResult attributes: {dir(result)}")
print(f"Has blueprint: {hasattr(result, 'blueprint')}")
if hasattr(result, 'blueprint'):
    print(f"Blueprint: {result.blueprint}")
print(f"Has graphs: {hasattr(result, 'graphs')}")
if hasattr(result, 'graphs'):
    print(f"Graphs: {result.graphs}")
print(f"Errors: {result.errors}")
print(f"Warnings: {result.warnings}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

if hasattr(result, 'graphs') and result.graphs:
    graph = result.graphs[0]
    print(f"Graph: {graph.graph_name}")
    print(f"Total nodes: {len(graph.nodes)}")

    # 统计每个节点的Pin数量
    pin_counts = {}
    for node in graph.nodes:
        pin_count = len(node.pins)
        if pin_count not in pin_counts:
            pin_counts[pin_count] = 0
        pin_counts[pin_count] += 1

    print("\nPin count distribution:")
    for count, num_nodes in sorted(pin_counts.items()):
        print(f"  {count} pins: {num_nodes} nodes")

    # 找出有0个Pin的节点
    zero_pin_nodes = [node for node in graph.nodes if len(node.pins) == 0]
    if zero_pin_nodes:
        print(f"\nNodes with 0 pins ({len(zero_pin_nodes)}):")
        for node in zero_pin_nodes[:10]:  # 只显示前10个
            node_name = node.node_data.get('node_name', 'Unknown') if node.node_data else 'Unknown'
            node_class = node.class_name
            print(f"  - {node_name} ({node_class})")

    # 查找特定节点
    print("\nLooking for specific nodes:")
    ia_jump = None
    jump = None
    stop_jumping = None
    actionvalue_x = None
    actionvalue_y = None

    for node in graph.nodes:
        if "IA_Jump" in node.node_name:
            ia_jump = node
        elif "Jump" in node.node_name and "IA_Jump" not in node.node_name:
            if "Stop" in node.node_name:
                stop_jumping = node
            else:
                jump = node
        elif "ActionValue_X" in node.node_name:
            actionvalue_x = node
        elif "ActionValue_Y" in node.node_name:
            actionvalue_y = node

    if ia_jump:
        print(f"  IA_Jump: {len(ia_jump.pins)} pins")
    if jump:
        print(f"  Jump: {len(jump.pins)} pins")
    if stop_jumping:
        print(f"  StopJumping: {len(stop_jumping.pins)} pins")
    if actionvalue_x:
        print(f"  ActionValue_X: {len(actionvalue_x.pins)} pins")
    if actionvalue_y:
        print(f"  ActionValue_Y: {len(actionvalue_y.pins)} pins")

    # 统计Pin连接数量
    total_links = sum(len(pin.linked_to_raw) for node in graph.nodes for pin in node.pins)
    print(f"\nTotal pin connections: {total_links}")

    # 统计execution_flows和data_flows
    if hasattr(graph, 'execution_flows'):
        print(f"Execution flows: {len(graph.execution_flows)}")
    if hasattr(graph, 'data_flows'):
        print(f"Data flows: {len(graph.data_flows)}")

    # 查找K2Node_CallFunction_3的function_reference
    print("\nLooking for K2Node_CallFunction_3:")
    for node in graph.nodes:
        if node.node_name == "K2Node_CallFunction_3":
            print(f"  Node found, class: {node.class_name}")
            if hasattr(node, 'node_data') and node.node_data:
                print(f"  Node data type: {type(node.node_data)}")
                if hasattr(node.node_data, 'function_reference'):
                    print(f"  Function reference: {node.node_data.function_reference}")
                else:
                    print(f"  No function_reference attribute")
            else:
                print(f"  No node_data")