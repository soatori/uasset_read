---
phase: 22-节点序列化修复
plan: 04
status: partial
completed: 2026-05-05
issues_resolved: 2
issues_remaining: 3
---

# Phase 22 Plan 04 Summary: 修复图判断和类名解析逻辑

## 执行状态

**状态**: Partial - 两处逻辑修复完成，但测试仍有 5 项失败

## 修复成果

### 代码修改

1. **extract_blueprint_graphs 图判断逻辑** (行 2518)
   - 原代码: `if class_name and ("EdGraph" in class_name or "UberEdGraph" in class_name)`
   - 修复为: `if class_name and class_name in ['EdGraph', 'UberEdGraph']`
   - 原因: 子串匹配导致 EdGraphNode_Comment 被误判为图对象
   - 效果: K2Node 数量从 18 增加到 30，与导出表匹配 ✓

2. **resolve_class_name 字段选择** (行 2381-2385)
   - 原代码: `return import_map[import_idx].class_name`
   - 修复为: `return import_map[import_idx].object_name`
   - 原因: class_name 是类型名（如 "Class"），object_name 是对象名（如 "K2Node_InputAction"）
   - 效果: 节点类型识别正确，function_reference.MemberName 测试通过 ✓

### 测试结果

| 测试 | 修复前 | 修复后 | 说明 |
|------|--------|--------|------|
| TEST-01: K2Node 数量 | 18 vs 30 | 30 vs 30 ✓ PASSED | 精确匹配排除 EdGraphNode_Comment |
| TEST-02: execution_flows | FAILED | FAILED | 依赖 pin 连接数据，pins 解析仍有问题 |
| TEST-03: data_flows | FAILED | FAILED | 依赖 pin 连接数据，pins 解析仍有问题 |
| TEST-04: function_reference | SKIPPED | PASSED ✓ | resolve_class_name 修复生效 |

**进展**:
- K2Node 数量正确匹配导出表（30 个）
- 节点类型正确识别（EnhancedInputActionEvent, CallFunction 等）
- function_reference.MemberName 正确提取

## 剩余问题

### ISSUE-07: PinCategory/PinSubCategory 解析值异常

**描述**: Pin 解析数据仍为垃圾值
- PinCategory = `/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter_4294967295`（应为 "exec"）
- PinSubCategory = `/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter_37888`（应为正确类型）

**根因**: archive 在读取 pin_type 时位置错误，导致 FName 索引读取垃圾值
- index = 0（正确应指向 "exec" 等类型名）
- number = 4294967295（接近 MAX_UINT32，明显是垃圾数据）

**影响**: execution_flows 和 data_flows 无法构建，因为：
- linked_to 连接数据为空
- Pin 无法匹配正确的输入/输出关系

**建议**: 需要修复 pins_offset 计算（见 ISSUE-04/05）

### ISSUE-04: EnhancedInputAction 节点 pins 为空

**描述**: K2Node_EnhancedInputAction 节点有 0 个 pins

**根因**: pins_offset 计算的 heuristic_delta 方案对 EnhancedInputAction 类型不准确
- 当前 heuristic: script_serial_size <= 20 → delta = 87
- 但实际 delta 可能因节点类型而异

**建议**: 实现动态扫描方案定位 pins_count pattern

### ISSUE-05: execution_flows/data_flows 为空

**描述**: 大多数 graphs 的 execution_flows 和 data_flows 为空或包含错误数据

**根因**: 上述 pin 解析问题导致连接关系无法正确构建

## 关键发现

### 22-04 计划假设验证

**计划声称**:
- 修复两个根因问题可使 TEST-01~04 全部通过

**实际结果**:
- ✓ TEST-01 通过（K2Node 数量）
- ✗ TEST-02/03 失败（依赖底层 pin 解析）
- ✓ TEST-04 通过（function_reference）

**结论**: 22-04 计划的根因分析不完整。两个逻辑修复解决了高层问题，但 TEST-02/03 依赖的底层 pin 序列化解析仍需修复。

### 修复的两处代码位置确认正确

1. `uasset_read.py:2518` — 精确匹配修复正确，解决了 EdGraphNode_Comment 误判
2. `uasset_read.py:2381-2385` — object_name 修复正确，解决了节点类型识别

## 文件修改

| 文件 | 修改内容 |
|------|---------|
| uasset_read.py:2518 | extract_blueprint_graphs 精确匹配判断 |
| uasset_read.py:2381-2385 | resolve_class_name import 类型返回 object_name |

## 下一步建议

1. 需要新 phase 修复 pins_offset 计算（动态扫描方案）
2. 验证 EnhancedInputAction 节点的完整 pins 解析
3. 修复后重新构建 execution_flows/data_flows

---
*Completed: 2026-05-05 — Phase 22-04 部分完成，逻辑修复正确，底层序列化问题需后续处理*