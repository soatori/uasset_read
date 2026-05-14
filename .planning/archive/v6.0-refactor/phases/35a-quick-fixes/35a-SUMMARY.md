---
phase: 35a-quick-fixes
name: 快速修复（UAT 收尾项）
status: complete
completed: 2026-05-13T00:45:00Z
tasks_completed: 3
tasks_total: 3
---

# Phase 35a Summary: 快速修复（UAT 收尾项）

## Objective

修复 AUDIT-REPORT.md 中的可自动清理项和 Phase 35 UAT 遗留小问题。

## Tasks Completed

### 35a-01: start_event fallback 改善

**File:** `src/uasset_read/graph/flow_builder.py`

**Change:** `_get_start_event_name()` 函数中的所有 `"Unknown"` 返回分支改为返回 `node.class_name` 作为 fallback。

**Before:**
- 当 node_data 为空时返回 `"Unknown"`
- 当 event_reference 为空时返回 `"Unknown"`
- 当 member_name 为空时返回 `"Unknown"`
- 默认 fallback 返回 `"Unknown"`

**After:**
- 所有 fallback 分支返回 `node.class_name`（如 `"K2Node_Event"`）

**Verification:** `grep -rn "return \"Unknown\"" src/uasset_read/graph/flow_builder.py` 无匹配。

### 35a-02: 清理 debug/test 脚本

**Files Moved:**
- `debug_linkedto_deep.py`, `debug_pin_raw.py`, `debug_pin_trace.py`, `debug_pin_trace2.py`, `debug_pin_trace3.py`, `debug_pins.py`, `debug_pins2.py`, `parse_pin_body.py`
- `test_bp_parse.py`, `test_pin_layouts.py`

**Target:** `tools/` 目录

**.gitignore Added:**
```
# Debug/scratch scripts (not part of test suite)
tools/debug_*.py
tools/test_*.py
tools/parse_*.py
```

**Verification:** `git status` 不再显示这些文件为 untracked。

### 35a-03: DEBUG_PIN_PARSING print → logging 迁移

**Files Modified:**
- `src/uasset_read/serializers/graph.py`: 添加 `import logging` + `logger = logging.getLogger(__name__)`, 替换 `if DEBUG_PIN_PARSING: print(...)` 为 `logger.debug(...)`
- `src/uasset_read/constants.py`: 移除 `import os` 和 `DEBUG_PIN_PARSING` 常量定义

**Verification:** `grep -rn "DEBUG_PIN_PARSING" src/` 无匹配。

## Test Results

```
python -m pytest tests/ -q --tb=short
397 passed, 71 skipped, 0 failed in 5.47s
```

## Key Files Created

| File | Purpose |
|------|---------|
| `tools/*.py` | 调试脚本归档（已 gitignore） |

## Key Files Modified

| File | Change |
|------|--------|
| `src/uasset_read/graph/flow_builder.py` | `_get_start_event_name()` fallback 改善 |
| `src/uasset_read/serializers/graph.py` | DEBUG_PIN_PARSING → logging |
| `src/uasset_read/constants.py` | 移除 DEBUG_PIN_PARSING 常量 |
| `.gitignore` | 添加 tools/ 排除规则 |

## Deviations

None - all tasks executed per plan.

## Notes

- Phase 35a 仅处理快速修复项，linked_to_raw 根因问题属于 Phase 35b
- BP_FirstPersonCharacter 的 graphs 数据为空，需要 Phase 35b 调试 pin 连接解析

## Next Steps

Phase 35b: Pin 连接深度调试与修复 (linked_to_raw 根因修复)