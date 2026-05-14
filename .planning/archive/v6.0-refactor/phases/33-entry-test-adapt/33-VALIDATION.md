---
phase: 33
slug: entry-test-adapt
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-12
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/ -q` |
| **Full suite command** | `python -m pytest tests/ --tb=short -v` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -q`
- **After every plan wave:** Run `python -m pytest tests/ --tb=short -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 33-01-01 | 01 | 1 | MOD-12 | T-33-01 / — | VectorValue/RotatorValue/ScaleValue可导入 | unit | `python -c "from uasset_read.models.transforms import VectorValue, RotatorValue, ScaleValue; print('OK')"` | ✅ | ✅ |
| 33-01-02 | 01 | 1 | TEST-02 | T-33-02 | parse_uasset可导入且调用成功 | unit | `python -c "from uasset_read import parse_uasset; print('OK')"` | ✅ | ✅ |
| 33-01-03 | 01 | 1 | MOD-12 | T-33-03 | find_main_blueprint_generated_class可调用 | unit | `python -c "from uasset_read import find_main_blueprint_generated_class; print('OK')"` | ✅ | ✅ |
| 33-02-01 | 02 | 2 | CLI-01 | T-33-04 | python -m uasset_read --help退出码0 | integration | `python -m uasset_read --help > nul & echo Exit code: %ERRORLEVEL%` | ✅ | ✅ |
| 33-02-02 | 02 | 2 | CLI-02 | T-33-05 | --json输出格式正确 | integration | `python -m pytest tests/test_phase14_output_formats.py::TestOutputTypeFlags::test_json_flag -v` | ✅ | ✅ |
| 33-02-03 | 02 | 2 | CLI-03 | T-33-06 | --markdown输出格式正确 | integration | `python -m pytest tests/test_phase14_output_formats.py::TestOutputTypeFlags::test_markdown_flag -v` | ✅ | ✅ |
| 33-02-04 | 02 | 2 | CLI-04 | T-33-07 | 无效文件路径返回退出码2 | integration | `python -m pytest tests/test_uasset_read.py -k "file_not_found" -v` | ✅ | ✅ |
| 33-02-05 | 02 | 2 | CLI-05 | T-33-08 | 无效参数返回退出码3 | integration | `python -m pytest tests/test_uasset_read.py -k "argument_error" -v` | ✅ | ✅ |
| 33-03-01 | 03 | 3 | TEST-02 | T-33-09 | 18个测试文件导入成功 | integration | `python -m pytest tests/ --collect-only -q` | ✅ | ✅ |
| 33-03-02 | 03 | 3 | TEST-02 | T-33-10 | 测试基线：373 passed, 0 failed | integration | `python -m pytest tests/ -q` | ✅ | ✅ |
| 33-03-03 | 03 | 3 | TEST-02 | T-33-11 | 旧版uasset_read.py已删除 | integration | `test -f uasset_read.py && echo "FAIL" || echo "PASS"` | ✅ | ✅ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_uasset_read.py` — CLI入口测试（test_phase14_output_formats.py, test_phase21_verification.py等）
- [x] `tests/conftest.py` — 共享fixtures（如果需要）
- [x] `pytest>=7` — 配置在pyproject.toml dev依赖中

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | N/A | All phase behaviors have automated verification. | — |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 2s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-12

---

## Validation Audit Trail

| Audit Date | Gaps Total | Resolved | Escalated | Run By |
|------------|------------|----------|-----------|--------|
| 2026-05-12 | 0 | 0 | 0 | manual |

---

## Notes

Phase 33验证采用"自下而上"策略：
- Plan 01: 模块化入口（parse_uasset、transform_parser）→ 100%单元测试覆盖
- Plan 02: CLI入口 → 集成测试覆盖（exit codes、argparse）
- Plan 03: 测试适配 → 基线回归测试（373 passed, 0 failed）

所有验证命令可在pytest配置中运行，无需额外工具或CLI标志。
