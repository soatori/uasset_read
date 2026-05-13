---
title: "35c-05: cli.py 文件类型检查 + 异常捕获"
plan_id: "35c-05"
phase: "35c"
status: "complete"
tags: [security, cli, error-handling]
requires: []
provides: [HIGH-01-fix, HIGH-03-fix]
affects: [cli.py]
tech-stack:
  added: [is_file-check, try-except-wrapper]
  patterns: [defensive-programming]
key-files:
  created: []
  modified: [src/uasset_read/cli.py]
decisions: []
metrics:
  duration: "5 min"
  completed_date: "2026-05-13"
---

# Phase 35c Plan 05: CLI 安全增强 Summary

修复 cli.py 中两个安全问题，增强错误处理和防御性编程。

## 一句话概述

使用 `is_file()` 替代 `exists()` 防止目录被错误处理，添加 `parse_uasset()` 的防御性异常捕获。

## 修改内容

### Issue 1: 文件类型检查 (HIGH-01)

**问题**: `exists()` 对目录也返回 True，传入目录时 `open()` 会抛出 `IsADirectoryError`。

**修复**:
```python
# 修改前
if not file_path.exists():
    print(f"Error: File not found: {args.file}", file=sys.stderr)
    sys.exit(EXIT_FILE_NOT_FOUND)

# 修改后
if not file_path.is_file():
    if file_path.is_dir():
        print(f"Error: Not a file: {args.file}", file=sys.stderr)
    else:
        print(f"Error: File not found: {args.file}", file=sys.stderr)
    sys.exit(EXIT_FILE_NOT_FOUND)
```

### Issue 2: 异常捕获 (HIGH-03)

**问题**: `parse_uasset()` 调用未被 try-except 包裹，防御性编程要求外层也捕获异常。

**修复**:
```python
# 修改前
result = parse_uasset(args.file, tolerant=tolerant)

# 修改后
try:
    result = parse_uasset(args.file, tolerant=tolerant)
except Exception as e:
    print(f"Error: Unexpected parse failure: {e}", file=sys.stderr)
    sys.exit(EXIT_PARSE_ERROR)
```

## 验收结果

| 测试项 | 结果 | 退出码 |
|--------|------|--------|
| 传入目录 | ✅ "Error: Not a file: src" | 2 |
| 传入不存在文件 | ✅ "Error: File not found: nonexistent.uasset" | 2 |
| 正常文件解析 | ✅ JSON 输出正常 | 0 |

## 测试状态

- 257 passed, 65 skipped, 1 failed
- 失败的测试 (`test_jump_started_flow`) 是之前已存在的问题，与本次修改无关

## Deviations from Plan

无偏离 - 按计划执行。

## Self-Check: PASSED

- ✅ 文件修改: `src/uasset_read/cli.py`
- ✅ 提交: `6bb2545`
- ✅ 所有验收标准通过