---
phase: 8
slug: blueprint-graph-output
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-02
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | none — 项目默认 pytest.ini detection |
| **Quick run command** | `python -m pytest tests/test_output_formatting.py -x -v` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_output_formatting.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green (152 tests)
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | GRAPH-11 | — | N/A (纯数据格式化) | unit | `pytest tests/test_output_formatting.py::test_format_json_full_contains_graphs -v` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | OUT2-01 | — | N/A | unit | `pytest tests/test_output_formatting.py::test_graphs_field_top_level -v` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | GRAPH-12 | T-08-01 | 循环检测阻止 DoS | unit | `pytest tests/test_output_formatting.py::test_execution_flow_cycle_detection -v` | ❌ W0 | ⬜ pending |
| 08-02-02 | 02 | 2 | GRAPH-12 | — | N/A | unit | `pytest tests/test_output_formatting.py::test_format_json_full_contains_execution_flows -v` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 3 | OUT2-03 | — | N/A | unit | `pytest tests/test_output_formatting.py::test_format_text_full_contains_graph_summary -v` | ❌ W0 | ⬜ pending |
| 08-04-01 | 04 | 4 | OUT2-04 | — | N/A | unit | `pytest tests/test_output_formatting.py::test_cli_graph_flag -v` | ❌ W0 | ⬜ pending |
| 08-04-02 | 04 | 4 | OUT2-04 | — | N/A | unit | `pytest tests/test_output_formatting.py::test_cli_graph_json_composable -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_output_formatting.py` — 新增测试文件，覆盖 Phase 8 所有需求
- [ ] 测试 fixture：`sample_graph_with_connections()` — 包含连接的测试图数据
- [ ] 测试 fixture：`sample_graph_with_execution_flow()` — 包含执行流的测试图数据
- [ ] 测试 fixture：`sample_graph_with_cycle()` — 包含循环的测试图数据

*Existing infrastructure covers framework and conftest.py — Wave 0 only adds test file and fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Lyra 资产图输出完整性 | GRAPH-11, GRAPH-12 | 需要真实 .uasset 文件 | 运行 `python uasset_read.py LyraStarterGame/Content/.../*.uasset --json --graph`，检查 graphs 字段 |

*Primary behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending