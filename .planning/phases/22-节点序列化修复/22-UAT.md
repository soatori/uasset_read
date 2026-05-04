---
status: testing
phase: 22-节点序列化修复
source: [22-01-SUMMARY.md, 22-02-SUMMARY.md, 22-03-SUMMARY.md]
started: 2026-05-05T00:00:00Z
updated: 2026-05-05T12:45:00Z
---

## Current Test

[testing complete]

## Tests

### 1. K2Node 解析数量
expected: 运行 `python -m pytest tests/test_phase21_verification.py::TestNodeCount::test_node_count_matches_exports`，测试应该通过，表示解析的 K2Node 数量匹配导出表数量（30个）。
result: issue
reported: "解析的 K2Node 数量是 18，导出表有 30 个，缺少 12 个节点"
severity: major

### 2. Jump 执行流程
expected: 运行 `python -m pytest tests/test_phase21_verification.py::TestExecutionFlow`，所有测试应该通过，表示 execution_flows 包含 IA_Jump → Jump → StopJumping 链路。
result: issue
reported: "execution_flows 为空，未找到 IA_Jump → Jump → StopJumping 执行流程（3个测试全部失败）"
severity: major

### 3. ActionValue 数据流
expected: 运行 `python -m pytest tests/test_phase21_verification.py::TestDataFlow`，所有测试应该通过，表示 data_flows 包含 ActionValue_X/Y 连接。
result: issue
reported: "data_flows 存在但缺少 ActionValue_X → Right 和 ActionValue_Y → Forward 连接（2个测试失败）"
severity: major

### 4. function_reference 提取
expected: 运行 `python -m pytest tests/test_phase21_verification.py::TestNodeProperties::test_function_reference_member_name`，测试应该通过，表示 CallFunction 节点的 function_reference.MemberName 正确提取（如 "Jump"）。
result: issue
reported: "测试被跳过（SKIPPED），未找到对应的 CallFunction 节点"
severity: major

## Summary

total: 4
passed: 0
issues: 4
pending: 0
skipped: 0

## Gaps

- truth: "K2Node 解析数量应匹配导出表数量（30个）"
  status: failed
  reason: "User reported: 解析的 K2Node 数量是 18，导出表有 30 个，缺少 12 个节点"
  severity: major
  test: 1
  artifacts: []
  missing: []
- truth: "execution_flows 应包含 IA_Jump → Jump → StopJumping 执行链路"
  status: failed
  reason: "User reported: execution_flows 为空，未找到 IA_Jump → Jump → StopJumping 执行流程（3个测试全部失败）"
  severity: major
  test: 2
  artifacts: []
  missing: []
- truth: "data_flows 应包含 ActionValue_X/Y 连接"
  status: failed
  reason: "User reported: data_flows 存在但缺少 ActionValue_X → Right 和 ActionValue_Y → Forward 连接（2个测试失败）"
  severity: major
  test: 3
  artifacts: []
  missing: []
- truth: "CallFunction 节点的 function_reference.MemberName 应正确提取"
  status: failed
  reason: "User reported: 测试被跳过（SKIPPED），未找到对应的 CallFunction 节点"
  severity: major
  test: 4
  artifacts: []
  missing: []