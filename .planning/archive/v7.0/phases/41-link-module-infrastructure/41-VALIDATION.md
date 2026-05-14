---
phase: 41
slug: link-module-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-14
---

# Phase 41 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | none — uses default pytest discovery |
| **Quick run command** | `python -m pytest tests/test_link_*.py -x` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_link_*.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 41-01-01 | 01 | 1 | LINK-06 | T-41-01 | LinkerParseResult default values correct | unit | `python -c "from uasset_read.link.result import LinkerParseResult; r = LinkerParseResult(); assert r.is_success == False"` | ❌ W0 | ⬜ pending |
| 41-01-02 | 01 | 1 | LINK-01 | — | UObjectInstance fields and properties correct | unit | `python -m pytest tests/test_link_object_instance.py -x -v` | ❌ W0 | ⬜ pending |
| 41-01-03 | 01 | 1 | LINK-06 | — | LinkerParseResult all fields exist | unit | `python -m pytest tests/test_link_result.py -x -v` | ❌ W0 | ⬜ pending |
| 41-02-01 | 02 | 2 | LINK-02, LINK-03, LINK-04, LINK-05 | T-41-03/04/05 | resolve_package_index bounds check, preload idempotency | unit | `python -m pytest tests/test_link_linker.py -x -v` | ❌ W0 | ⬜ pending |
| 41-02-02 | 02 | 2 | LINK-02, LINK-03, LINK-04, LINK-05 | — | link/resolve/outer-tree/preload all behaviors | unit | `python -m pytest tests/test_link_linker.py -x -v` | ❌ W0 | ⬜ pending |
| 41-02-03 | 02 | 2 | LINK-07 | — | Existing 373 tests pass 0 regression | regression | `python -m pytest tests/ -v` | ✅ existing | ⬜ pending |
| 41-02-04 | 02 | 2 | LINK-03 | D-03 | Submodule import works, top-level fails | integration | `python -c "from uasset_read.link import PackageLinker, UObjectInstance, LinkerParseResult; print('OK')"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_link_object_instance.py` — stubs for LINK-01 (Wave 1 creates)
- [ ] `tests/test_link_result.py` — stubs for LINK-06 (Wave 1 creates)
- [ ] `tests/test_link_linker.py` — stubs for LINK-02 through LINK-05 (Wave 2 creates)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| UE4/UE5 asset compatibility | v7.0 goal | Requires real .uasset files from different UE versions | Run linker on UE4 and UE5 test assets, verify no crashes |
| parse_uasset() behavior unchanged | LINK-07 | Regression against existing 373 tests | `python -m pytest tests/ -v` — all existing tests pass |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
