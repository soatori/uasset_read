---
phase: 33
plan: 02
type: execute
subsystem: entry-test-adapt
tags: [cli, entry-point, argparse]
dependency:
  requires: ["Phase 33 Plan 01"]
  provides: ["CLI entry point (cli.py)", "python -m entry (__main__.py)", "version 6.0.0"]
  affects: ["src/uasset_read/cli.py", "src/uasset_read/__main__.py", "pyproject.toml"]
tech-stack:
  added: [cli.py, __main__.py]
  patterns: [argparse, mutually-exclusive-group, error-handling, exit-codes]
key-files:
  created:
    - src/uasset_read/cli.py
    - src/uasset_read/__main__.py
  modified:
    - pyproject.toml
decisions:
  - "CLI entry point follows exact equivalence migration from uasset_read_legacy.py §7814-7938"
  - "Exit codes: 0=success, 1=parse_error, 2=file_not_found, 3=argument_error (D-26)"
  - "stdout for data, stderr for errors (D-25)"
metrics:
  duration: "~5min"
  completed: "2026-05-12T01:00:00Z"
---

# Phase 33 Plan 02: CLI 入口与测试适配 Summary

**One-liner:** 创建 CLI 入口模块（cli.py + __main__.py），实现 argparse 参数解析、格式路由、退出码管理，版本号升级至 6.0.0。

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | 创建 cli.py 实现 CLI 入口 | f7969fd | cli.py |
| 2 | 创建 __main__.py + 更新 pyproject.toml + 版本 | d66e5fb | __main__.py, pyproject.toml |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None — all functions are fully implemented with real logic.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: input_validation | cli.py | --export INDEX 通过 argparse type=int 自动验证非整数值 |
| threat_flag: error_handling | cli.py | IOError 捕获写入错误，输出到 stderr 并退出 EXIT_ARGUMENT_ERROR (T-33-07) |
| threat_flag: path_safety | cli.py | 仅执行只读操作，不写入用户提供的文件路径（T-33-05） |
