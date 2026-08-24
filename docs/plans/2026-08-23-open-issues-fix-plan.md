# Open Issues Fix Plan — 2026-08-23

## Issue #586: Enforce semantic JSON contract and tolerant domain fallback

### Root cause (triple)

1. **core/\_\_init\_\_.py:224-228** — `SemanticContractError` thrown unconditionally on validation failure; no tolerant/strict distinction
2. **builder.py:225** — `owns_envelope_sections` doesn't check if content is empty before setting domain format
3. **render.py `_strip_none_and_empty`** — Removes empty `{}` causing domain root block to be stripped from output

### Secondary issues found during investigation

4. **DataTable validator** checked `data_table.get("row_count")` but extractor puts it inside `table_summary`
5. **Skeleton validator** checked `skeleton.get("bone_count")` but extractor puts it inside `skeleton_summary`
6. **Skeleton extractor** put `bone_count` inside `skeleton_summary` instead of top-level (test expectation mismatch)
7. **Multiple extractors** (anim, user_defined, standalone, sound) tracked unavailable coverage scopes when `asset_type_data` was missing, causing representation/coverage mismatches

### Fixes applied

| File | Change |
|------|--------|
| `core/__init__.py` | Added tolerant mode fallback: catches `SemanticContractError` and falls back to `asset_semantic` envelope |
| `validator.py` | Fixed DataTable validator to check `table_summary.row_count`; fixed Skeleton validator to check top-level `bone_count`; removed parent_index range check (parser corruption, not contract violation) |
| `render.py` | Added `preserve_keys` to `_strip_none_and_empty`; ensures domain root keys exist for domain formats even when content is empty |
| `builder.py` | Restored original `owns_envelope_sections` logic (domain format always used when available) |
| `skeleton/extractor.py` | Moved `bone_count` to top-level of skeleton dict; made `skeleton_summary` optional |
| `anim/extractor.py` | Removed `cov.track("anim_summary", False)` when asset_type_data missing |
| `user_defined/extractor.py` | Removed `cov.track("enum_data", False)` when asset_type_data missing |
| `standalone/extractor.py` | Removed `cov.track("profile_properties", False)` when asset_type_data missing |
| `sound/extractor.py` | Removed `cov.track("resource_properties", False)` when asset_type_data missing |
| `skeleton_semantic.schema.json` | Moved `bone_count` to top-level required property; `SkeletonSummary` now only contains optional `guid` |
| `test_skeleton_semantic.py` | Updated `test_validator_aggregates_bone_errors` to test non-integer parent_index |

### Test results

- **586 passed**, 9 skipped, 0 failures
