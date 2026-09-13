# Ponytail Byte-Swap & Thin Wrappers Residual

> **ARCHIVED (2026-09-26):** Executed closeout / plan-of-record. Historical evidence only — do not re-execute. Binding contracts and the canonical target remain under [`docs/designs/`](../README.md).


> **Status:** current (executed 2026-09-13). Follow-up to the 2026-09-13 whole-repo
> ponytail re-audit residual scan. **Do not re-execute.**
>
> **Scope:** pure subtraction. Little-endian parse output unchanged. BE packages
> remain rejected at `PACKAGE_FILE_TAG_SWAPPED`.
>
> **Execution record:** Tasks 1–9 `9efa5efa`…`c7e13567`; baseline **231 passed**.
> Size baseline tightened to src files=**69** lines=**18459**.

**Goal:** Remove never-enabled byte-swap machinery, dead `FMemberReference`,
thin wrappers (`load_usmap`, `parse_guard`), and always-default budget knobs.

**Plan of record:** `docs/superpowers/plans/2026-09-13-ponytail-byteswap-thin-wrappers.md`

## Do-not-reexecute

- 2026-09-08 whole-repo waves
- 2026-09-12 residual cuts
- 2026-09-14 residual plan (landed on this branch lineage)

## Execution commits

| Task | SHA | Summary |
| --- | --- | --- |
| 1 | `9efa5efa` | collapse archive byte-swap path to little-endian only |
| 2 | `626b8460` | delete unused `FMemberReference` model after Wave A |
| 3 | `65c7623d` | drop unused `ResourceBudget` knobs and `MemoryLimitExceeded` fields |
| 4 | `4245c5ab` | call `UsmapParser` directly; drop `load_usmap` wrapper |
| 5 | `fa599375` | fold `safe_parse` into `binary_or_native_handlers`; drop `parse_guard` module |
| 6 | `a6ff8cea` | share projection `json_byte_size` in agent_tools budgets |
| 7 | `5c4d1090` | map Kismet bytecode status to confidence with one dict |
| 8 | `355ee80f` | drop never-registered `None`-key custom property lookups |
| 9 | `c7e13567` | inline `UE5_LEGACY_VERSION`; tighten size baseline after residual wave |

Task 5 already lowered `min_files` 70→69. Task 9 re-measured and tightened
`max_lines` 18560→18459 (files stayed 69). One README Data Models table row was
corrected in the docs commit: removed the deleted `FMemberReference` name
(deferred minor from Task 2 review).

## Residual risk

- BE cooked packages: still `VersionError` (intentional; no fixtures). Removing
  the byte-swap path does **not** enable big-endian parse.
- `PackageBundle` path properties kept (payload extraction tests).
