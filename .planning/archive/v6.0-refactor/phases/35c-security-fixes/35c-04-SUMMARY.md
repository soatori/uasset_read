---
title: "35c-04: parse_uasset.py is_success 标志 + 临时存档 tolerant 修复"
plan_id: "35c-04"
phase: "35c"
subsystem: "parse_uasset"
tags: [bugfix, is_success, tolerant, FArchive]
requires: []
provides: [correct-is-success-flag, consistent-tolerant-mode]
affects: [parse_uasset.py]
tech_stack:
  added: []
  patterns: [error-state-tracking, parameter-forwarding]
key_files:
  created: []
  modified: [src/uasset_read/parse_uasset.py]
decisions: []
metrics:
  duration: "2 min"
  completed: "2026-05-13"
  tasks: 1
  files: 1
---

# Phase 35c Plan 04: parse_uasset.py is_success + tolerant 修复

## 一句话总结

修复 `parse_uasset.py` 中 `is_success` 过早设置和临时存档未传递 `tolerant` 参数的问题。

## 任务完成情况

| 任务 | 状态 | 提交 | 文件 |
|------|------|------|------|
| 修复 is_success + tolerant | ✅ 完成 | f8bf746 | src/uasset_read/parse_uasset.py |

## 修改详情

### Issue 1: is_success 过早设置

**问题**: `result.is_success = True` 在属性解析完成后立即设置，但后续还有蓝图提取、图提取、依赖分析等步骤可能追加错误，导致错误情况下 `is_success` 仍为 True。

**修复**:
- 删除 line 76 的 `result.is_success = True`
- 在 try 块末尾（所有解析步骤完成后）添加 `result.is_success = len(result.errors) == 0`

### Issue 2: 临时存档未传递 tolerant

**问题**: 两处临时 `FArchive` 实例未传递 `tolerant` 参数，导致与主存档行为不一致。

**修复**:
- Line 85: `FArchive(path)` → `FArchive(path, tolerant=tolerant)`
- Line 105: `FArchive(path)` → `FArchive(path, tolerant=tolerant)`

## 验收结果

| 验收项 | 结果 |
|--------|------|
| 错误存在时 is_success 为 False | ✅ 通过 |
| 无错误时 is_success 为 True | ✅ 通过 |
| 临时存档使用相同 tolerant 模式 | ✅ 通过 |
| parse_uasset 相关测试 | ✅ 10 passed, 5 skipped |

## 偏差记录

无偏差 - 计划完全按预期执行。

## 预存问题

测试 `test_phase21_verification.py::TestExecutionFlow::test_jump_started_flow` 失败，与本次修改无关（Phase 21 验证测试）。