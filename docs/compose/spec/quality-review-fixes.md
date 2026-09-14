---
feature: quality-review-fixes
status: designed
updated: 2026-09-15
branch: fix/quality-review-i1-i4
commits: ea163122..  # filled at delivery
---

# Quality Review Fixes (I1–I4)

## Report

## [S1] Problem

Independent code review of the parser quality system found four Important issues that dilute the “unexpected = CI signal” goal and under-document the contract:

1. **I1** — `classify_trailing_reason` maps `Texture2D` and `BlendSpace` (and other ordinary residue classes) to `unexpected`, so two of five baseline seeds pin noise as “expected unexpected.”
2. **I2** — `FirstPerson_DT_WeaponList` baseline entry has empty `max_by_code_reason` (zero diagnostics today) and cannot regress-detect TABLE_* or general growth except via `forbidden_codes`.
3. **I3** — `_assert_quality_baseline` only checks pre-known `(code, reason)` pairs; a new code or new reason bucket on a seed is invisible.
4. **I4** — changelog documents `reason` but not the schema addition of optional `fallback`.

## [S2] Design

### S2.1 Classifier tables (I1)

Extend `classify_trailing_reason` with a **minimal + evidence-based** set, using sample-sweep and fixture evidence (ordinary ok assets with trailing, not true corruptions):

| Class pattern | reason | Rationale |
|---------------|--------|-----------|
| `Texture2D`, `Texture`, `TextureCube`, `Texture2DArray`, `TextureRenderTarget*` | `bulk_expected` | bulk mip/payload not embedded as properties |
| `BlendSpace`, `BlendSpace1D`, `BlendSpace2D` | `known_unimplemented` | trailing sample data / axes not specialized |
| `AnimSequence`, `AnimMontage`, `AnimComposite` | `known_unimplemented` | short fixed tails; body not specialized |
| `Material`, `MaterialInstance*`, `MaterialFunction` | `known_unimplemented` | expression graph / instance params not deeply decoded |

Rules:

- Keep bulk-before-prefix ordering; add Texture* into `_BULK_CLASSES` (or prefix list checked first).
- Do **not** classify MetaData/Blueprint/K2/Niagara/Skeleton/PhysicsAsset — already correct.
- After table change, **regenerate** `tests/samples/quality_baseline.json` via `tools/gen_quality_baseline.py`.
- Update classifier unit tests for the new mappings.

### S2.2 DT seed zero-diag pin (I2)

Keep `FirstPerson_DT_WeaponList` as a seed. Add explicit pin that the sample must remain clean:

```json
"FirstPerson_DT_WeaponList.uasset": {
  "depth": "asset",
  "forbidden_codes": ["EXPORT_PROPERTY_PARSE_FAILED", "HANDLER_FAILURE"],
  "forbid_unlisted": true,
  "max_total_diagnostics": 0,
  "max_by_code_reason": {}
}
```

Gate behavior:

- If any diagnostic is emitted when `max_total_diagnostics` is present and is 0, fail.
- Alternatively: `forbid_unlisted: true` alone already fails any diagnostic if the sample’s `max_by_code_reason` is empty (all pairs unlisted). Prefer **both** for readability: zero pin is explicit; forbid_unlisted is the general rule.

### S2.3 Allowlist semantics for unlisted pairs (I3)

In `_assert_quality_baseline`:

- Default: **fail** on any `(code, reason)` not listed in `max_by_code_reason` when the sample entry has `"forbid_unlisted": true` (new field).
- For entries without the field: keep current ceiling-only behavior for backward compatibility within this feature (existing seeds without the flag stay ceiling-only until regenerated with the flag).
- Generator: set `"forbid_unlisted": true` on **all five** seeds so the new semantics are the default for this baseline file.
- Failure message must name the unexpected `(code, reason)` and suggest regenerating or classifying.

### S2.4 Changelog honesty (I4)

Extend the Unreleased Improvements bullet:

- optional `reason` taxonomy as today
- **and** optional `fallback` on PackageDocument diagnostics (schema additive)
- note that merge path surfaces both when archive recovery diagnostics are lifted

### Out of Scope (restated)

- Niagara / BP deep-parser fixes
- Changing `format_version`
- Process-global logging
- Removing `remaining` parameter (keep signature)

## [S3] Out of Scope

- Classifier expansion beyond S2.1 tables
- New top-level API for quality reports
- CI job scanning external `E:\Develop\lib\Samples`
- `TABLE_ROW_COUNT_INVALID` / `fstring_length_exceeds_limit` classification (remain unclassified)
- Worktree creation (environment blocks `git worktree`; work on branch `fix/quality-review-i1-i4` from `ea163122`)

## Tasks

- [ ] T1: Extend `classify_trailing_reason` tables + unit tests — acceptance: `Texture2D`→`bulk_expected`, `BlendSpace`→`known_unimplemented`, `AnimSequence`→`known_unimplemented`, `Material`→`known_unimplemented`; existing MetaData/Niagara/Skeleton mappings unchanged (covers: S2.1)
- [ ] T2: Regenerate `quality_baseline.json` after T1 — acceptance: GridChecker no longer pins Texture2D as `unexpected`; BS seed reason is `known_unimplemented`; file committed with generator output (covers: S2.1; depends: T1)
- [ ] T3: Baseline gate allowlist + zero-diag pin — acceptance: `_assert_quality_baseline` fails on unlisted `(code,reason)` when `forbid_unlisted`; DT seed has `max_total_diagnostics: 0` and `forbid_unlisted: true`; unit/integration tests cover fail and pass paths (covers: S2.2, S2.3; depends: T2)
- [ ] T4: Generator sets `forbid_unlisted` on all seeds — acceptance: regenerated baseline JSON includes `"forbid_unlisted": true` for every seed (covers: S2.3; depends: T3)
- [ ] T5: Changelog documents `fallback` + reason — acceptance: Unreleased bullet mentions both keys; commit docs-only (covers: S2.4)
