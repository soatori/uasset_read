---
phase: 14-output-format-optimization
plan: 03
subsystem: 输出格式
tags: [markdown, schema, mermaid, cli-flags, tdd]
requires:
  - 14-01 (StatusInfo + build_status_info)
  - 14-02 (build_graphs_summary)
provides:
  - format_markdown() 函数（OUT-04）
  - build_schema_info() 函数（OUT-05）
  - CLI --markdown 标志
  - CLI --schema 标志
  - format_json_* include_schema 参数
affects:
  - uasset_read.py (functions: format_markdown, build_schema_info, format_json_full, format_json_summary, create_parser, main)
  - tests/test_output_formatting.py
tech-stack:
  added:
    - format_markdown() Markdown 输出函数
    - build_schema_info() 字段语义注释函数
    - --markdown/--schema CLI 标志
  patterns:
    - Mermaid 流程图语法 (graph LR)
    - Markdown 表格格式
    - include_schema 参数模式
key-files:
  created: []
  modified:
    - uasset_read.py (lines 5050-5076, 5079-5121, 5240-5296, 5400-5530, 5579-5618, 5656-5675, 5833-5845)
    - tests/test_output_formatting.py (lines 1434-1677)
decisions:
  - D-14-10: Markdown 三节结构
  - D-14-11: 表格优先格式
  - D-14-12: Mermaid 流程图 LR 方向
  - D-14-13: _schema 顶层字段
  - D-14-17: --markdown CLI 标志
  - D-14-19: --schema CLI 标志
metrics:
  duration_minutes: 15
  completed_date: "2026-05-03T09:20:00Z"
  task_count: 2
  file_count: 2
  test_count: 12
---

# Phase 14 Plan 03: Markdown 格式 + Schema Summary

## 一句话总结

实现了 Markdown 输出格式和字段语义注释功能，添加 CLI --markdown/--schema 标志，使用 TDD 流程确保正确性。

## 实现详情

### format_markdown() 函数（OUT-04）

添加了新的 `format_markdown()` 函数，实现：

- **三节结构**: Asset Overview / Blueprint Details / Graph Summary / Exports
- **表格优先**: exports 使用 Markdown 表格格式 `| Name | Class | Parent |`
- **Mermaid 流程图**: execution_flows 使用 `graph LR` 方向展示调用链
- **空图处理**: 无 graphs 时显示 "No graphs in this asset"

输出示例：
```markdown
# Asset: TestAsset

## Asset Overview
| Field | Value |
|-------|-------|
| Package | /Game/Test/TestAsset |
| Version | UE 522 |
| Status | success |

## Graph Summary
### EventGraph
```mermaid
graph LR
  EventBeginPlay --> PrintString
```
```

### build_schema_info() 函数（OUT-05）

添加了 `build_schema_info()` 函数，返回字段语义注释字典：

- status: 解析结果状态（success/fail/error）
- output_version: 输出格式 API 版本标识
- parent_class: 蓝图继承的父类名称
- variables: 蓝图变量列表（名称、类型、默认值、元数据）
- graphs_summary: 顶层化的图执行流概览
- execution_flows: 函数调用链路径
- imports/soft_references/circular_deps: 依赖分析字段

### CLI 标志扩展

- **--markdown**: 输出 Markdown 格式（与 --json/--text/--summary 互斥）
- **--schema**: 添加 _schema 字段（可与 --json/--summary 组合）

### format_json_* 函数修改

- `format_json_full(result, include_schema=False)`: 添加可选 _schema 字段
- `format_json_summary(result, include_schema=False)`: 同样支持 _schema

### 测试覆盖

12 个新增测试覆盖：

**TestFormatMarkdown (5 tests)**:
- Asset title 格式 "# Asset: {name}"
- Section 结构验证
- Markdown 表格格式
- Mermaid 流程图语法
- 空 graphs 消息

**TestBuildSchemaInfo (4 tests)**:
- 返回字典类型
- 包含关键字段描述
- format_json_full with include_schema
- format_json_summary with include_schema

**TestCLIMarkdownSchemaFlags (3 tests)**:
- --markdown 标志可用
- --markdown/--json 互斥
- --schema 标志可用

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

验证 git log:
- `test(14-03):` commit exists (RED gate) - commit 371473c
- `feat(14-03):` commit exists after test (GREEN gate) - commit d2650dd

TDD flow followed correctly.

## Known Stubs

None.

## Threat Flags

None - 本 plan 为纯输出格式优化，无安全边界变更。

## Self-Check

### Files Created/Modified

- [x] uasset_read.py - format_markdown + build_schema_info + CLI flags + __all__ exports
- [x] tests/test_output_formatting.py - 12 new tests added

### Commits Exist

- [x] 371473c - test(14-03): add failing tests
- [x] d2650dd - feat(14-03): implement Markdown format and Schema field

### Tests Pass

- [x] 12 new tests pass
- [x] 48 tests pass in test_output_formatting.py
- [x] 275 tests pass in full test suite

## Self-Check: PASSED