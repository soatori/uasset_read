# Code Quality Audit Report

**Date:** 2026-05-12
**Branch:** v2.0-dev
**Scope:** Full UAT/VERIFICATION review + source code quality scan
**Test Suite:** 397 passed, 71 skipped, 0 failed

---

## 1. Test Suite Status

| Metric | Value |
|--------|-------|
| Passed | 397 |
| Skipped | 71 |
| Failed | 0 |
| Total source lines | ~7,000 |
| Modules | 14+ (archive, serializers, models, parsers, blueprint, graph, formatters, cli) |

---

## 2. UAT/VERIFICATION Findings

### FINDING-1: execution_flows start_event='Unknown' (Phase 35)

- **Severity:** HIGH
- **Status:** Open issue in Phase 35 UAT Test 3
- **Description:** 部分节点的 execution_flows 有 start_event='Unknown'，连接数据为空
- **File:** `src/uasset_read/graph/flow_builder.py`
- **Root cause:** Pin linked_to_raw 仍为空或部分节点缺乏 pin 连接数据，导致执行流追踪无法从正确的 Event 节点开始
- **Impact:** 用户无法看到完整的执行流链路

### FINDING-2: pin linked_to_raw empty (Phase 22 - unresolved)

- **Severity:** HIGH
- **Status:** Partially resolved but core issue persists
- **Description:** read_pin_array 返回空列表 (array_count=0)，导致所有 pin 的 linked_to_raw 为空，execution_flows 和 data_flows 无法构建
- **File:** `src/uasset_read/serializers/graph.py` (read_pin_array / read_ue_graph_pin)
- **Root cause:** pins_offset 动态扫描可能定位不准确；UE5 序列化格式可能存在版本特定变化
- **Impact:** 连接关系、执行流、数据流全部为空

### FINDING-3: 10 debug/test scripts in repo root (worktree clutter)

- **Severity:** MEDIUM
- **Status:** Present as untracked files
- **Description:** 10 个 debug_*.py / test_*.py 脚本散落在项目根目录，未纳入 .gitignore
- **Files:** debug_linkedto_deep.py, debug_pin_raw.py, debug_pin_trace.py, debug_pin_trace2.py, debug_pin_trace3.py, debug_pins.py, debug_pins2.py, parse_pin_body.py, test_bp_parse.py, test_pin_layouts.py
- **Impact:** 污染工作目录，git status 输出混乱，可能被误提交

### FINDING-4: DEBUG_PIN_PARSING global flag in production code

- **Severity:** LOW
- **Status:** Present
- **Description:** `src/uasset_read/serializers/graph.py:242` 包含 `print()` 调试输出，由全局常量 `DEBUG_PIN_PARSING` 控制
- **File:** `src/uasset_read/serializers/graph.py`
- **Impact:** 生产代码包含调试输出开关（当前为关闭状态），建议改为 logging 模块

### FINDING-5: Phase 22 execution_flows/data_flows still incomplete

- **Severity:** HIGH
- **Status:** Documented but not fixed across subsequent phases
- **Description:** Phase 22 (节点序列化修复) 只解决了节点识别问题，但 execution_flows 和 data_flows 的 pin 连接数据仍然为空。Phase 35 的 UAT 仍标记为 "issue"
- **Impact:** 蓝图图解析的核心价值之一（执行流追踪）不完整

### FINDING-6: 71 skipped tests (no active investigation)

- **Severity:** LOW
- **Status:** Known, categorized in Phase 32 UAT
- **Description:** 71 个测试被跳过，分为 4 类：TODO 待实现 (11), Phase 33 延迟 (12), v6.0 移除功能 (1), 测试资源受限 (2)，其余为其他模块 skip
- **Impact:** 测试覆盖率不完整，但不影响核心功能

---

## 3. Code Quality Scan

| Check | Result | Details |
|-------|--------|---------|
| Bare `except:` clauses | PASS | 0 found |
| `import *` wildcard imports | PASS | 0 found |
| Mutable default args in dataclasses | PASS | 0 found |
| TODO/FIXME/HACK/XXX markers | PASS | 0 found in source |
| print() statements | PASS | 6 in cli.py (appropriate: stderr for errors, stdout for data), 1 debug-gated in graph.py |
| Syntax errors | PASS | py_compile clean |
| Circular imports | PASS | No ImportError on import |

---

## 4. Summary

| Category | Count | Severity |
|----------|-------|----------|
| HIGH - execution_flows start_event='Unknown' | 1 | HIGH |
| HIGH - pin linked_to_raw empty (Phase 22) | 1 | HIGH |
| HIGH - execution_flows/data_flows incomplete (Phase 22→35) | 1 | HIGH |
| MEDIUM - 10 debug scripts in repo root | 1 | MEDIUM |
| LOW - DEBUG_PIN_PARSING print in production | 1 | LOW |
| LOW - 71 skipped tests | 1 | LOW |

**Total findings:** 6
**Auto-fixable:** 1 (FINDING-3: cleanup debug scripts)
**Manual-only:** 5 (require debugging/design decisions for pin connection parsing)

---

## 5. Recommendations

1. **HIGH priority:** Fix pin linked_to_raw parsing (FINDING-2/5) — this is the root cause of execution_flows and data_flows being empty. Requires binary-level analysis of UE5 UEdGraphPin serialization format.
2. **MEDIUM priority:** Clean up 10 debug scripts from repo root — either move to `tools/` directory or add to `.gitignore`.
3. **LOW priority:** Replace `DEBUG_PIN_PARSING` print with Python `logging` module for production-safe debug output.
