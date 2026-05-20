# Phase 61: Kismet 表达式系统 - Plan Review

**Reviewed:** 2026-05-19
**Reviewer:** gsd-plan-checker (initial) + manual fixes

## Initial Verdict: ISSUES FOUND (3 blockers, 2 warnings)

### Blockers Fixed

1. **Missing EX_EndFunctionParms (0x16) and EX_EndParmValue (0x15)** — Added to `functions.py` task. These are critical end markers for `read_expression_array()`.

2. **FArchive constructor incompatibility** — Added Task 4.0: FKismetArchive accepts `data: bytes` + `name: str` + `name_map: list[str]` in constructor. Wraps bytes in `io.BytesIO`, overrides FArchive internal state without modifying `archive.py`.

3. **FFieldPath stub** — Upgraded to full implementation in Task 1.3: `FFieldPath` with `Path: list[str]`, `ResolvedOwner`, and `from_archive(cls, archive, name_map)`.

### Warnings Addressed

4. **NameMap injection** — FKismetArchive constructor now accepts `name_map: list[str]`. Documented in Tasks 1.3, 4.0, 4.1.

5. **Unicode string terminator** — Clarified in Task 4.1: `xfer_string`/`xfer_unicode_string` do NOT consume terminators. Calling expression classes (EX_StringConst, EX_UnicodeStringConst) must skip past null bytes manually. Matches CUE4Parse behavior.

## Final Verdict: PASS

All blockers and warnings have been addressed. Plan is ready for execution.

### Dimensions Summary

| Dimension | Status |
|-----------|--------|
| Requirement Coverage | PASS |
| Task Completeness | PASS |
| Dependency Correctness | PASS |
| Key Links Planned | PASS |
| Scope Sanity | PASS |
| Must-Haves Derivation | PASS |
| Context Compliance | PASS |
| Pattern Compliance | PASS |

---

*Review completed: 2026-05-19*
