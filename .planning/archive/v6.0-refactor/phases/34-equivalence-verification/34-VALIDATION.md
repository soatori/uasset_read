---
phase: 34
slug: equivalence-verification
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase 34 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via project dev dependencies) |
| **Config file** | None — uses project root `pytest` defaults |
| **Quick run command** | `python -m pytest tests/test_equivalence.py -v --tb=short` |
| **Full suite command** | `python -m pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~30 seconds (subprocess CLI calls + diff computation) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_equivalence.py -v --tb=short`
- **After every plan wave:** Run `python -m pytest tests/ -v --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green (or documented known diffs)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 34-01-01 | 01 | 1 | 等价-01 | — | JSON Full 输出等价 (合成资产) | automated | `pytest tests/test_equivalence.py::test_json_full_synthetic -x` | ❌ W0 | ⬜ pending |
| 34-01-02 | 01 | 1 | 等价-02 | — | JSON Summary 输出等价 (合成+真实) | automated | `pytest tests/test_equivalence.py::test_json_summary -x` | ❌ W0 | ⬜ pending |
| 34-01-03 | 01 | 1 | 等价-03 | — | Text 输出等价 (合成+真实) | automated | `pytest tests/test_equivalence.py::test_text -x` | ❌ W0 | ⬜ pending |
| 34-01-04 | 01 | 1 | 等价-04 | — | Markdown 输出等价 (合成+真实) | automated | `pytest tests/test_equivalence.py::test_markdown -x` | ❌ W0 | ⬜ pending |
| 34-01-05 | 01 | 1 | 等价-05 | — | 合成资产全部格式验证 | automated | `pytest tests/test_equivalence.py -k synthetic -v` | ❌ W0 | ⬜ pending |
| 34-01-06 | 01 | 1 | 等价-06 | — | 真实资产全部格式验证 | automated | `pytest tests/test_equivalence.py -k real -v` | ❌ W0 | ⬜ pending |
| 34-01-07 | 01 | 1 | 等价-07 | — | VERIFICATION.md 报告生成 | automated | Check file: `.planning/phases/34-equivalence-verification/VERIFICATION.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_equivalence.py` — 核心验证测试文件（包含 DiffRecorder、deep_compare、CLI runner helpers）
- [ ] 基线输出获取机制 — 每次动态生成旧版输出（subprocess 调用旧版 CLI）
- [ ] DiffRecorder 类 — 在测试文件中实现，支持按 severity/category 分组
- [ ] VERIFICATION.md 报告生成函数 — `build_verification_report()` 在测试文件中实现
- [ ] Mermaid 块检测逻辑 — `extract_mermaid_blocks()` 用于 Markdown 格式的结构化对比
- [ ] pytest parametrize fixture — 资产 × 格式笛卡尔积测试矩阵

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 已知差异分类审查 | 等价-01~06 | 需要人工判断差异是"可接受的设计变更"还是"需修复的回归" | 审查 VERIFICATION.md 中的差异清单，标注每项为 ACCEPTED / FIX_NEEDED / INVESTIGATE |
| ObjectProperty 格式决策 | 等价-03 | 设计决策 — 接受简化格式还是回滚旧版 | 审查 CONTEXT.md 或与项目负责人确认 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
