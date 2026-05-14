---
status: complete
phase: 28a-test-baseline-fix
source: [uasset_read.py, tests/test_property_parsing.py, tests/test_output_formatting.py]
started: "2026-05-11T17:35:00Z"
completed: "2026-05-11T17:45:00Z"
updated: "2026-05-12"
---

## 当前测试

[测试已完成]

## 测试用例

### 1. UE5 NodePosX/NodePosY/NodeGuid 从 PropertyTags 提取
expected: 解析 UE5 蓝图资产时，NodePosX/NodePosY/NodeGuid/NodeComment 从 PropertyTags 中正确提取，节点位置信息出现在输出 JSON 的 graphs 字段中
result: pass

### 2. 空执行流过滤（EnhancedInputAction Started/Ongoing）
expected: 解析包含 EnhancedInputAction 触发器的蓝图时，空 flow（Started/Ongoing 无 CallFunction 连接）应被过滤，output JSON 中不出现空 function_name 的执行流条目
result: pass

### 3. FPropertyTypeName 格式解析（FName 8 bytes + InnerCount 4 bytes）
expected: 运行 `python -m pytest tests/test_property_parsing.py -v` 全部通过，FPropertyTypeName 测试数据格式为 FName(8 bytes) + InnerCount(4 bytes)，不再是 FString 格式。12 个相关测试 pass
result: pass

### 4. linked_to_raw 输出格式修复（output pins 为 dict {'pin_guid': str}）
expected: 运行 `python -m pytest tests/test_output_formatting.py -v` 中 linked_to_raw 相关测试通过，output pins 的 linked_to_raw 格式为 dict {'pin_guid': str} 而非简单字符串列表
result: pass

### 5. 测试基线整体验证
expected: `python -m pytest tests/ --tb=no -q` 显示 411 passed, 47 skipped，0 failures。无回归
result: pass

## 摘要

总数: 5
通过: 5
问题: 0
待处理: 0
跳过: 0
阻塞: 0

## 差距

[无]
