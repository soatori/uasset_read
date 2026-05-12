# Phase 35a Plan: 快速修复（UAT 收尾项）

**Phase:** 35a
**Milestone:** v6.0 模块化重构
**Goal:** 修复 AUDIT-REPORT.md 中的可自动清理项和 Phase 35 UAT 遗留小问题

## Context

Phase 35a 是 Phase 35 的后续收尾，处理 3 个不需要深入二进制调试的小问题：
- execution_flows 的 start_event 显示 "Unknown"（改善 fallback，非根因修复）
- 10 个 debug/test 脚本散落在根目录
- DEBUG_PIN_PARSING print 改为 logging 模块

根因问题（pin linked_to_raw empty）属于 Phase 35b，不在此阶段处理。

## Tasks

### 35a-01: start_event fallback 改善

**File:** `src/uasset_read/graph/flow_builder.py`
**Function:** `_get_start_event_name()` (line 128-181)

**Problem:** 当节点 class_name 不在已知类型列表中，或 node_data 为空时，返回 `"Unknown"`。导致 execution_flows 输出中 start_event 显示为 "Unknown"。

**Fix:** 在所有 `"Unknown"` 返回分支中，改为返回 `node.class_name` 作为 fallback。具体改动：

1. Line 141: `return "Unknown"` → `return node.class_name` (K2Node_Event, nd is None)
2. Line 149: `return "Unknown"` → `return node.class_name` (K2Node_Event, er is None)
3. Line 160: `return "Unknown"` → `return node.class_name` (K2Node_Event, member_name is empty)
4. Line 181: `return "Unknown"` → `return node.class_name` (default fallback for unknown types)

**验证:** 对 BP_FirstPersonCharacter 执行 `uasset-read --json`，execution_flows 中不再出现 `"start_event": "Unknown"`。

### 35a-02: 清理 debug/test 脚本

**Files:** `debug_*.py` (8 files), `test_*.py` (2 files in root)
**Target:** 移至 `tools/` 目录 + `.gitignore` 排除

**Problem:** 10 个调试脚本散落在项目根目录，污染 `git status`，可能被误提交。

**Fix:**
1. 创建 `tools/` 目录
2. 移动以下文件到 `tools/`:
   - `debug_linkedto_deep.py`, `debug_pin_raw.py`, `debug_pin_trace.py`, `debug_pin_trace2.py`, `debug_pin_trace3.py`, `debug_pins.py`, `debug_pins2.py`, `parse_pin_body.py`
   - `test_bp_parse.py`, `test_pin_layouts.py`
3. 在 `.gitignore` 末尾追加:
   ```
   # Debug/scratch scripts (not part of test suite)
   tools/debug_*.py
   tools/test_*.py
   tools/parse_*.py
   ```

**验证:** `git status` 不再显示这些文件为 untracked。

### 35a-03: DEBUG_PIN_PARSING print → logging 迁移

**File:** `src/uasset_read/serializers/graph.py`
**Constant:** `src/uasset_read/constants.py` line 147

**Problem:** `DEBUG_PIN_PARSING` 全局常量控制 `print()` 调试输出，生产代码包含调试开关。

**Fix in `graph.py`:**
1. 添加 `import logging` 到文件顶部
2. 在模块顶部添加: `logger = logging.getLogger(__name__)`
3. 将 line 241-242 的 `if DEBUG_PIN_PARSING: print(...)` 替换为:
   ```python
   logger.debug("FText tolerant mode: history_type=%s, error=%s", history_type, e)
   ```
4. 移除 `DEBUG_PIN_PARSING` 的 import（line 21）

**Fix in `constants.py`:**
1. 移除 line 147: `DEBUG_PIN_PARSING = os.environ.get("UASSET_DEBUG_PINS", "0") == "1"`
2. 如果 `os` import 不再被其他地方使用，也移除 `import os`

**验证:** `grep -rn "DEBUG_PIN_PARSING" src/` 无匹配。`grep -rn "print(" src/uasset_read/serializers/graph.py` 无匹配（cli.py 中的 print 除外）。

## Dependencies

- 35a-01 独立，无依赖
- 35a-02 独立，无依赖
- 35a-03 独立，无依赖

三个任务可并行执行（不同文件）。

## Execution Order

1. 35a-02 (文件移动，最简单)
2. 35a-03 (logging 迁移，影响最小)
3. 35a-01 (行为变更，需要验证)

## Verification

1. `python -m pytest tests/ -v` — 397+ passed, 0 failed
2. `uasset-read E:/Develop/lib/UnrealEngine/Samples/FirstPerson/BP_FirstPersonCharacter.uasset --json` — start_event 非 "Unknown"
3. `git status` — 无 debug_*.py / test_*.py 散落
4. `grep -rn "DEBUG_PIN_PARSING" src/` — 无匹配
