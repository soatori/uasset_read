---
phase: 35e
slug: pin-offset-debug
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-13
---

# Phase 35e — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/test_ue5_pin_offset_verification.py -v --tb=short` |
| **Full suite command** | `python -m pytest tests/ --tb=short -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_ue5_pin_offset_verification.py -v --tb=short` (once created in Plan 04)
- **After every plan wave:** Run `python -m pytest tests/ --tb=short -q`
- **Before `/gsd-verify-work`:** Full suite must be green

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 35e-01-01 | 01 | 1 | 35e-REQ-01 | T-35e-01 | N/A (diagnostic tool) | syntax | `python -c "import ast; ast.parse(open('tools/binary_trace_pin.py').read()); print('Syntax OK')"` | ✅ | ⬜ pending |
| 35e-01-02 | 01 | 1 | 35e-REQ-02 | T-35e-01 | N/A (diagnostic tool) | syntax | `python -c "import ast; ast.parse(open('tools/binary_trace_pin.py').read()); print('Syntax OK')"` | ✅ | ⬜ pending |
| 35e-02-01 | 02 | 2 | 35e-REQ-03 | — | N/A | syntax | `python -c "import ast; ast.parse(open('src/uasset_read/constants.py').read()); print('Constants OK')"` | ✅ | ⬜ pending |
| 35e-02-02 | 02 | 2 | 35e-REQ-03 | T-35e-03 | 1-byte read only | syntax | `python -c "import ast; ast.parse(open('src/uasset_read/serializers/graph.py').read()); print('graph.py Syntax OK')"` | ✅ | ⬜ pending |
| 35e-02-03 | 02 | 2 | 35e-REQ-03 | T-35e-02 | try/except tolerant | syntax + import | `python -c "import sys; sys.path.insert(0,'src'); from uasset_read.serializers.graph import read_ue_graph_pin; print('Import OK')"` | ✅ | ⬜ pending |
| 35e-03-01 | 03 | 3 | 35e-REQ-03 | T-35e-04 | 1-byte read only | syntax | `python -c "import ast; ast.parse(open('src/uasset_read/serializers/graph.py').read()); print('graph.py Syntax OK')"` | ✅ | ⬜ pending |
| 35e-03-02 | 03 | 3 | 35e-REQ-04 | T-35e-04 | N/A (diagnostic) | manual | `python tools/binary_trace_pin.py --asset <asset> --node-export-idx 40 --pin-index 0` | ❌ (Plan 01) | ⬜ pending |
| 35e-04-01 | 04 | 4 | 35e-REQ-04 | T-35e-05 | N/A (test only) | pytest | `python -m pytest tests/test_ue5_pin_offset_verification.py -v --tb=short` | ❌ (this task) | ⬜ pending |
| 35e-04-02 | 04 | 4 | 35e-REQ-04 | T-35e-05 | N/A (test only) | pytest | `python -m pytest tests/ --tb=short -q` | ❌ (Plan 01) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No additional test framework setup needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| linked_to_raw non-empty (Plan 03 Task 2) | 35e-REQ-04 | Requires working binary trace tool + runtime diagnostics | Run `python tools/binary_trace_pin.py --asset "..."` --node-export-idx 40 --pin-index 0 and verify DefaultTextValue flags/history_type/body are traced, then run the linked_to_raw diagnostic python -c one-liner from Plan 03 Task 2 action |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
