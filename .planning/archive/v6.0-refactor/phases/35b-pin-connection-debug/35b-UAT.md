---
status: testing
phase: 35b-pin-connection-debug
source: 35b-PLAN.md, 35b-CONTEXT.md
started: 2026-05-13T00:00:00Z
updated: 2026-05-13T00:00:00Z
---

## Current Test

number: 3
name: Test 3: Data Flows 构建
expected: |
  Move 图的 data_flows 应该包含数据传递关系：
  
  1. 包含 ActionValue_X/Y 的数据连接
  2. data_flows 是非空列表
  3. 每个 flow 条目包含 source_pin, target_pin, value_type 等字段
awaiting: user response

## Tests

### 1. Pin 连接数据解析
expected: |
  解析 BP_FirstPersonCharacter.uasset 后，pin.linked_to_raw 应该是非空的，包含连接引用数据。
  
  具体验证点：
  1. EventGraph 中至少有一个节点的输出 pin 有 linked_to_raw 条目
  2. linked_to_raw 包含 "owning_node" 和 "pin_guid" 字段
  3. 至少有一个 pin 的 linked_to_raw 长度 > 0
result: pass

### 2. Execution Flows 构建
expected: |
  EventGraph 的 execution_flows 应该包含完整的执行链路：
  
  1. 包含 IA_Jump → Jump → StopJumping 的执行链路
  2. execution_flows 是非空列表
  3. 每个 flow 条目包含 source_node, target_node, pin_name 等字段
result: pass

### 3. Data Flows 构建
expected: |
  Move 图的 data_flows 应该包含数据传递关系：
  
  1. 包含 ActionValue_X/Y 的数据连接
  2. data_flows 是非空列表
  3. 每个 flow 条目包含 source_pin, target_pin, value_type 等字段
result: pending

### 4. UE5 序列化修复验证
expected: |
  UE5 bool 序列化修复应该正确应用：
  
  1. read_bool_ue5() 消耗 exactly 1 字节
  2. read_ed_graph_pin_type() 对 UE5 使用 1 字节 bool
  3. FText b_has_culture 对 UE5 使用 1 字节
  4. 二进制偏移没有 drift (所有字段位置正确)
result: pending

### 5. 集成测试：LinkedTo 数组
expected: |
  LinkedTo 数组应该正确读取：
  
  1. pins_offset 动态扫描定位准确
  2. array_count 对于有连接的 pin > 0
  3. LinkedTo 数组元素正确解析
result: pending

### 6. 回归测试：全部测试通过
expected: |
  运行完整测试套件：
  
  1. pytest tests/ 返回 397+ passed, 0 failed
  2. 之前 Phase 22 跳过的测试现在应该通过
  3. 无新引入的失败测试
result: pending

## Summary

total: 6
passed: 2
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps

[none yet]
