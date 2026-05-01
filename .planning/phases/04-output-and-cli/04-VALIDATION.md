---
phase: 4
slug: output-and-cli
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-01
---

# Phase 4 — Output and CLI Validation Strategy

Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing from Phase 1/2/3) |
| **Config file** | none — pytest auto-discovery |
| **Quick run command** | `python -m pytest tests/test_output_formatting.py -v` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_output_formatting.py -v`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-00-01 | 00 | 0 | OUT-01~CLI-06 | — | Test scaffolding stubs | unit | `pytest tests/test_output_formatting.py --collect-only` | ✅ W0 | ✅ planned |
| 04-01-01 | 01 | 1 | OUT-01 | — | JSON full structure | unit | `pytest tests/test_output_formatting.py::test_json_full_structure -x` | ✅ W0 | ✅ planned |
| 04-01-02 | 01 | 1 | OUT-03 | — | JSON hierarchy Package→Exports→Properties | unit | `pytest tests/test_output_formatting.py::test_json_hierarchy -x` | ✅ W0 | ✅ planned |
| 04-01-03 | 01 | 1 | OUT-04 | — | Resolved references in output | unit | `pytest tests/test_output_formatting.py::test_references_resolved -x` | ✅ W0 | ✅ planned |
| 04-01-04 | 01 | 1 | OUT-05 | — | Null markers for missing data | unit | `pytest tests/test_output_formatting.py::test_null_handling -x` | ✅ W0 | ✅ planned |
| 04-02-01 | 02 | 2 | CLI-01 | — | argparse validates file path | unit | `pytest tests/test_output_formatting.py::test_cli_file_arg -x` | ✅ W0 | ✅ planned |
| 04-02-02 | 02 | 2 | CLI-02 | — | --json flag works | unit | `pytest tests/test_output_formatting.py::test_cli_json_flag -x` | ✅ W0 | ✅ planned |
| 04-02-03 | 02 | 2 | CLI-03 | — | --text flag works | unit | `pytest tests/test_output_formatting.py::test_cli_text_flag -x` | ✅ W0 | ✅ planned |
| 04-02-04 | 02 | 2 | CLI-04 | — | --summary flag works | unit | `pytest tests/test_output_formatting.py::test_cli_summary_flag -x` | ✅ W0 | ✅ planned |
| 04-02-05 | 02 | 2 | CLI-05 | — | Semantic exit codes 0/1/2/3 | unit | `pytest tests/test_output_formatting.py::test_exit_codes -x` | ✅ W0 | ✅ planned |
| 04-03-01 | 03 | 2 | CLI-06 | — | stdlib only, no external deps | integration | `pytest tests/test_output_formatting.py::test_no_external_deps -x` | ✅ W0 | ✅ planned |

*Status: ✅ planned · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_output_formatting.py` — stubs for OUT-01 to OUT-05, CLI-01 to CLI-06
- [x] Mock ParseResult fixtures for output testing
- [x] CLI integration tests with subprocess exit code verification

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Human-readable text format readability | OUT-02 | Subjective assessment | Run CLI with --text on sample .uasset, verify AI agent can parse |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned — ready for execution
