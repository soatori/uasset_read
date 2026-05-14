---
phase: 19
slug: 连接关系重建
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-04
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | none — 直接运行 |
| **Quick run command** | `python -m pytest tests/test_output_formatting.py -x` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_output_formatting.py -x`
- **After every plan wave:** Run `python -m pytest tests/test_output_formatting.py -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | LINK-01 | — | N/A | unit | `pytest tests/test_output_formatting.py::test_format_config_* -x` | ❌ W0 | ⬜ pending |
| 19-01-02 | 01 | 1 | LINK-01 | — | N/A | unit | `pytest tests/test_output_formatting.py::test_format_pin_ref_* -x` | ❌ W0 | ⬜ pending |
| 19-01-03 | 01 | 1 | LINK-01 | — | N/A | unit | `pytest tests/test_output_formatting.py::test_build_connections_map_* -x` | ✅ | ⬜ pending |
| 19-02-01 | 02 | 1 | LINK-02 | — | N/A | unit | `pytest tests/test_output_formatting.py::test_start_event_types_* -x` | ❌ W0 | ⬜ pending |
| 19-02-02 | 02 | 1 | LINK-02 | — | N/A | unit | `pytest tests/test_output_formatting.py::test_build_execution_flows_* -x` | ✅ | ⬜ pending |
| 19-02-03 | 02 | 1 | LINK-02 | — | N/A | unit | `pytest tests/test_output_formatting.py::test_trace_execution_* -x` | ✅ | ⬜ pending |
| 19-03-01 | 03 | 2 | LINK-03 | — | N/A | unit | `pytest tests/test_output_formatting.py::test_build_data_flows_* -x` | ❌ W0 | ⬜ pending |
| 19-03-02 | 03 | 2 | LINK-03 | — | N/A | unit | `pytest tests/test_output_formatting.py::test_format_graphs_json_* -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_output_formatting.py::test_format_config_*` — LINK-01格式配置测试
- [ ] `tests/test_output_formatting.py::test_format_pin_ref_*` — LINK-01 Pin引用格式测试
- [ ] `tests/test_output_formatting.py::test_start_event_types_*` — LINK-02起点类型测试
- [ ] `tests/test_output_formatting.py::test_build_data_flows_*` — LINK-03数据流构建测试
- [ ] `tests/test_output_formatting.py::test_data_flows_excludes_exec_*` — LINK-03 exec过滤测试
- [ ] `tests/test_output_formatting.py::test_control_flow_branch_type_*` — D-19-14 branch_type测试

*Existing infrastructure covers most phase requirements. Wave 0 adds 6 new tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 测试资产验证（Jump执行流程） | TEST-02 | 需解析BP_FirstPersonCharacter.uasset验证IA_Jump节点结构 | 1. 解析测试资产 2. 检查execution_flows包含IA_Jump → Jump → StopJumping链路 3. 验证各触发时机独立追踪 |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---

*Phase 19: 连接关系重建 — Validation Strategy*
*Created: 2026-05-04*