# Test Script Rules

These rules govern new and migrated tests; existing tests are not auto-deleted or bulk-migrated.

## File Placement

| Scenario | Location | Rule |
|----------|----------|------|
| Modify existing test | `tests/{module}/test_*.py` | Prefer reusing and merging existing tests |
| Formal test | `tests/{module}/test_{feature}.py` | Only keep tests with long-term maintenance value |
| Core benchmarks | `tests/core/` | Minimal regression set only, max 5 files |
| Quick/temp tests | `temp/test_{purpose}.py` | One-off verification, local debugging; not part of formal suite |

## Quantity & Cleanup Requirements

- Total formal `test_*.py` files under `tests/` must not exceed **20**; at the limit, merge duplicates, delete outdated tests, or migrate low-value tests first.
- Core benchmarks must not exceed **5**; cover only main parsing path, critical safety boundaries, and most important user-visible output; module details must not bypass limits via this directory.
- Total test cases (`test_*` functions) under `tests/` must not exceed **100**; at the limit, merge same-scenario cases, delete low-value tests, or migrate to `temp/`.
- Same module, same input type, same output target, or same boundary class: prefer merging into existing scripts; no duplicate files without clear isolation need.
- Special or new features may only get a standalone test file when they have independent boundaries, independent I/O, or independent regression value.
- Before creating a new file, evaluate existing scripts: check for duplicate coverage, mergeable cases, outdated cases, and misclassification; state the reason for reuse, merge, migration, deletion, or new creation.
- When cleaning tests, ensure behavioral coverage does not decrease: merge cases and keep key regression assertions first, then delete duplicate/broken scripts; category changes require同步 updates to paths, imports, and commands.
- `temp/` tests should be deleted, archived as documentation evidence, or promoted to formal tests at task end; they must not become a second long-term test suite.
- New formal test commits must list the module, core quota usage, current total, and post-addition total; over-limit proposals must not be merged.
- Test directories mirror `src/uasset_read/` by functional module; name files `test_{feature}.py`, functions `test_{scenario}_{expected}()`.
