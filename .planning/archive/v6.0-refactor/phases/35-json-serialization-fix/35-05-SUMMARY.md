---
phase: "35"
plan: "05"
subsystem: "serializers, models, tests"
tags: ["bugfix", "api-enhancement", "circular-deps", "parse-result"]
dependency_graph:
  requires: []
  provides:
    - "detect_circular_deps 不再误报引擎包自引用"
    - "ParseResult.status property 可直接访问"
  affects:
    - "tests/test_dependency_analysis.py"
tech_stack:
  added: []
  patterns: ["property delegation", "lazy import to avoid circular dependency"]
key_files:
  created: []
  modified:
    - "src/uasset_read/serializers/object_resources.py"
    - "src/uasset_read/models/result.py"
    - "tests/test_dependency_analysis.py"
decisions:
  - "detect_circular_deps 改为返回空列表而非保留部分功能 — 理由：原算法完全不是循环检测，产生误报比不检测更差"
  - "ParseResult.status 使用 property + 延迟导入 — 理由：避免 result.py 与 helpers.py 之间的循环导入"
metrics:
  duration: "~5min"
  completed: "2026-05-12"
  tests: "397 passed, 71 skipped, 0 failed"
---

# Phase 35 Plan 05: 修复 P3 轻微 Bug Summary

**一句话:** 修复循环依赖检测误报（包自引用）和 ParseResult 缺少 status 属性的 API 不一致问题。

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | 修复 detect_circular_deps 误报 | `f60cbd4` | `serializers/object_resources.py` |
| 2 | 为 ParseResult 添加 status 属性 | `35f604e` | `models/result.py` |
| - | 更新测试匹配新行为 | `6b8f4cf` | `tests/test_dependency_analysis.py` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 测试文件期望旧的误报行为**
- **Found during:** Task 1 verification (full test suite)
- **Issue:** 3 个测试 (`test_detect_circular_deps_high_density_dependency`, `test_detect_circular_deps_format`, `test_detect_circular_deps_multiple_packages`) 期望旧的 `[pkg, pkg]` 误报输出
- **Fix:** 更新测试断言为 `result == []`，文档说明新行为更安全
- **Files modified:** `tests/test_dependency_analysis.py`
- **Commit:** `6b8f4cf`

## Key Decisions

1. **detect_circular_deps 直接返回空列表** — 原算法只是统计包出现次数，完全不是循环依赖检测。产生误报比不检测更差。真正的循环检测需要构建有向图 + DFS/Tarjan 算法，超出 P3 bug 修复范围。

2. **ParseResult.status 使用 property + 延迟导入** — 在 property 内部 `from uasset_read.formatters.helpers import build_status_info` 避免模块级循环导入（result.py 被 helpers.py 导入，helpers.py 又需要导入 result.py 的 ParseResult）。

## Verification

- 397 passed, 71 skipped, 0 failed
- `detect_circular_deps` 对包含多个 `/Script/Engine` 条目的 import_map 返回 `[]`
- `ParseResult().status` 正确映射三种状态：success / fail / error

## Threat Flags

无新增威胁表面。

## Self-Check

- [x] `src/uasset_read/serializers/object_resources.py` — detect_circular_deps 修改存在
- [x] `src/uasset_read/models/result.py` — status property 存在
- [x] `tests/test_dependency_analysis.py` — 3 个测试已更新
- [x] Commits `f60cbd4`, `35f604e`, `6b8f4cf` 存在于 git log
- [x] 全部测试通过

## Self-Check: PASSED
