---

---
status: in_progress
phase: 51-binary-output-sanitization
source: [51-PLAN.md]
started: "2026-05-16T17:00:00.000Z"
updated: "2026-05-16T18:00:00.000Z"
---

## Current Test

number: 1
name: FString 读取 null 字符检测逻辑
expected: |
  read_fstring() 在检测到 null 字符比例超过 30% 时返回空字符串并记录警告日志
awaiting: testing

## Tests

### 1. FString 读取 null 字符检测逻辑
expected: |
  read_fstring() 在检测到 null 字符比例超过 30% 时返回空字符串并记录警告日志
result: pending

### 2. FText None 类型解析修复
expected: |
  read_ftext_with_history() 对无效 history_type（如 -121）进行保守处理，返回空字符串并记录 debug 日志
result: pending

### 3. _sanitize_string() 单元测试
expected: |
  _sanitize_string() 正确清理字符串中的二进制/null 字符，保留 \n \r \t
result: pending

### 4. pin_tooltip 二进制数据过滤
expected: |
  read_ue_graph_pin() 的 pin_tooltip 读取后检测二进制数据，严重时返回空字符串
result: pending

### 5. JSON 格式化器防御性过滤
expected: |
  format_node_dict() 对 pin dict 中所有字符串字段进行 _sanitize_string() 清理
result: pending

### 6. 现有测试无回归
expected: |
  运行现有测试确保无回归（561 tests），主要功能未受影响
result: pending

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps

<!-- YAML format for plan-phase --gaps consumption -->
- truth: "read_fstring() 检测 null 字符比例并返回空字符串"
  status: gap
  reason: "FString 读取后需要验证 null 字符比例"
  severity: major
  test: 1
  root_cause: "当前 read_fstring() 实现只有 rstrip('\x00')，没有 null 字符比例检测逻辑"
  artifacts:
    - path: "src/uasset_read/archive.py"
      issue: "read_fstring() 需要添加 null_ratio 检测"
  missing:
    - "添加 null_ratio > 0.3 时返回空字符串的逻辑"
    - "添加警告日志记录"
  debug_session: ""

- truth: "read_ftext_with_history() 对无效 history_type 进行保守处理"
  status: gap
  reason: "无效 history_type（如 -121）需要特殊处理"
  severity: major
  test: 2
  root_cause: "read_ftext_with_history() 对 history_type 不在 -1..10 范围内的情况未处理"
  artifacts:
    - path: "src/uasset_read/serializers/graph.py"
      issue: "read_ftext_with_history() 需要添加无效 history_type 检测"
  missing:
    - "添加 history_type 范围检查"
    - "添加 debug 日志记录"
  debug_session: ""

- truth: "JSON 格式化器对 pin 字段进行防御性清理"
  status: gap
  reason: "asdict() 序列化前需要清理字符串字段"
  severity: major
  test: 5
  root_cause: "format_node_dict() 使用 asdict() 直接序列化 pin，绕过了字符串清理"
  artifacts:
    - path: "src/uasset_read/graph/flow_builder.py"
      issue: "format_node_dict() 需要添加 _sanitize_pin_dict() 清理"
  missing:
    - "添加 _sanitize_string() 辅助函数"
    - "添加 _sanitize_pin_dict() 函数"
    - "在 pin 序列化前应用清理"
  debug_session: ""

- truth: "pin_tooltip 二进制数据源头过滤"
  status: gap
  reason: "pin_tooltip 读取后需要检测二进制数据"
  severity: major
  test: 4
  root_cause: "read_ue_graph_pin() 读取 pin_tooltip 后未检测二进制数据"
  artifacts:
    - path: "src/uasset_read/serializers/graph.py"
      issue: "read_ue_graph_pin() 需要添加 pin_tooltip 二进制检测"
  missing:
    - "添加 _contains_binary_data() 辅助函数"
    - "在 pin_tooltip 读取后应用检测"
  debug_session: ""

## Diagnosis

### 当前状态

Phase 51 修复尚未实施。UAT 验证无法进行，因为：
1. `read_fstring()` 只有 `rstrip('\x00')`，无 null_ratio 检测
2. `read_ftext_with_history()` 对无效 history_type 未处理
3. JSON 格式化器未对 pin 字段进行清理
4. `pin_tooltip` 无二进制数据过滤

### 预期修复行动

运行 `/gsd-plan-phase 51 --gaps` 生成修复计划，然后：
- `/gsd-execute-phase 51 --gaps-only` — 执行所有 4 个修复任务
- 运行/tests/test_phase51_binary_sanitization.py 验证
- `/gsd-verify-work 51` — 再次 UAT 验证
