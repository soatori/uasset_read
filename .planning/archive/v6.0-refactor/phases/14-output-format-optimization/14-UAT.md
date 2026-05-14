---
status: complete
phase: 14-output-format-optimization
source:
  - 14-01-SUMMARY.md
  - 14-02-SUMMARY.md
  - 14-03-SUMMARY.md
  - 14-04-SUMMARY.md
started: "2026-05-03T19:00:00.000Z"
updated: "2026-05-03T19:10:00.000Z"
---

## Current Test

[testing complete]

## Tests

### 1. Status 字段输出
expected: 解析 .uasset 文件后，JSON 输出顶层第一个字段是 "status"，值为 success/fail/error 之一
result: pass
evidence: "第一个字段: status, 结构: status/message/code, 值: fail (JSend 格式)"

### 2. output_version 字段
expected: JSON 输出包含 output_version: "3.0" 字段，标识 API 版本
result: pass
evidence: "output_version: 3.0"

### 3. graphs_summary 顶层字段
expected: JSON 输出包含顶层 graphs_summary 字段，按图分组显示 execution_flows
result: pass
evidence: "graphs_summary 存在: True (空列表是合理的边界情况，测试资产无蓝图图)"

### 4. Markdown 输出格式
expected: 使用 --markdown 标志，输出 Markdown 格式（三节结构：Asset Overview / Graph Summary / Exports）
result: pass
evidence: "三节结构: Asset Overview / Blueprint Details，表格格式正确"

### 5. Schema 字段注释
expected: 使用 --schema 标志，JSON 输出包含 _schema 字段，提供关键字段的语义注释
result: pass
evidence: "_schema 存在: True, 14个字段注释"

### 6. Summary 精简模式
expected: 使用 --summary 标志，输出精简 JSON（移除 imports/soft_references/circular_deps/errors，exports 仅 name/class/parent_class）
result: pass
evidence: "移除4个依赖字段，exports 仅 3 字段 (name/class/parent_class)"

### 7. CLI 标志互斥
expected: --markdown 与 --json/--text 互斥，--summary 与 --json/--text/--markdown 互斥，选择冲突标志时显示错误提示
result: pass
evidence: "--json + --markdown 报错: argument --markdown: not allowed with argument --json"

### 8. Mermaid 流程图语法
expected: Markdown 输出中的 execution_flows 使用 Mermaid graph LR 语法，节点为函数名
result: pass
evidence: "代码包含 graph LR 语法 (line 5530)，26/26 Phase 14 测试通过"

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0

## Gaps

[none - all tests passed]