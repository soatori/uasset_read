#!/usr/bin/env python3
"""
测试脚本 - 查看FText的详细信息
"""
import sys
sys.argv.append('--debug-pin')
sys.argv.append('--debug-ftext')

import uasset_read
from uasset_read import parse_uasset

# 解析测试资产
file_path = r'E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset'
print(f"Parsing: {file_path}")
print("=" * 80)

result = parse_uasset(file_path)

# 查找K2Node_CallFunction_12节点
if result.graphs and result.graphs[0].nodes:
    for node in result.graphs[0].nodes:
        if 'K2Node_CallFunction_12' in str(node.node_data) if node.node_data else False:
            print(f"Found K2Node_CallFunction_12")
            print(f"  Pins: {len(node.pins)}")
            for i, pin in enumerate(node.pins):
                print(f"  Pin #{i}: {pin.pin_name}, PinToolTip length: {len(pin.pin_tooltip)}")
                if i == 0:  # 只显示第一个Pin的tooltip
                    print(f"    PinToolTip: {pin.pin_tooltip[:100]}")