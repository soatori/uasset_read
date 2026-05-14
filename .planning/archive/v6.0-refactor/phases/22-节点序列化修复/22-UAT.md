---
status: partial
phase: 22-节点序列化修复
source: [22-01-SUMMARY.md, 22-02-SUMMARY.md, 22-03-SUMMARY.md, 22-04-SUMMARY.md]
started: 2026-05-05T00:00:00Z
updated: 2026-05-05T15:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. K2Node 解析数量
expected: 运行 `python -m pytest tests/test_phase21_verification.py::TestNodeCount::test_node_count_matches_exports`，测试应该通过，表示解析的 K2Node 数量匹配导出表数量（30个）。
result: passed
reported: "K2Node 数量匹配：解析 30 个，导出表 30 个"
severity: none
fixed_by: "22-04: extract_blueprint_graphs 精确匹配修复"

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
passed: 2
issues: 2
pending: 0
skipped: 0

## Gaps

- truth: "K2Node 解析数量应匹配导出表数量（30个）"
  status: resolved
  reason: "Fixed by 22-04: extract_blueprint_graphs exact match"
  severity: none
  test: 1
  root_cause: "extract_blueprint_graphs() 使用子串匹配 \"EdGraph\" in class_name，导致 EdGraphNode_Comment 被误判为图"
  artifacts:
    - path: "uasset_read.py:2518"
      issue: "图判断逻辑使用子串匹配而非精确匹配"
  missing:
    - "改为精确匹配：class_name in ['EdGraph', 'UberEdGraph']"
  debug_session: .planning/debug/k2node-count-match.md
  fixed_by: "22-04"

- truth: "execution_flows 应包含 IA_Jump → Jump → StopJumping 执行链路"
  status: failed
  reason: "User reported: execution_flows 为空，未找到 IA_Jump → Jump → StopJumping 执行流程（3个测试全部失败）"
  severity: major
  test: 2
  root_cause: "resolve_class_name 使用错误字段（class_name 而非 object_name），导致 K2Node 被识别为 Class 类型"
  artifacts:
    - path: "uasset_read.py:2363-2392"
      issue: "resolve_class_name 对 import 类型返回 class_name 字段"
  missing:
    - "对 import 类型使用 object_name 字段"
  debug_session: .planning/debug/execution-flows-empty.md

- truth: "data_flows 应包含 ActionValue_X/Y 连接"
  status: failed
  reason: "User reported: data_flows 存在但缺少 ActionValue_X → Right 和 ActionValue_Y → Forward 连接（2个测试失败）"
  severity: major
  test: 3
  root_cause: "同上 - resolve_class_name 错误导致节点类型识别失败"
  artifacts:
    - path: "uasset_read.py:2363-2392"
      issue: "resolve_class_name 对 import 类型返回 class_name 字段"
  missing:
    - "对 import 类型使用 object_name 字段"
  debug_session: .planning/debug/data-flows-missing-links.md

- truth: "CallFunction 节点的 function_reference.MemberName 应正确提取"
  status: resolved
  reason: "Fixed by 22-04: resolve_class_name returns object_name for import types"
  severity: none
  test: 4
  root_cause: "resolve_class_name 返回 class_name 而非 object_name"
  artifacts:
    - path: "uasset_read.py:2385"
      issue: "resolve_class_name 返回 class_name 而非 object_name"
  missing:
    - "修改为返回 object_name 字段"
  debug_session: .planning/debug/function-reference-missing.md
  fixed_by: "22-04"