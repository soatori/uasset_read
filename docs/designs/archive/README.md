# Archived Repository-Wide Designs

> **Archive status:** documents in this directory are historical evidence, not active requirements. They must not guide new implementation when they conflict with the [package-first target architecture](../2026-08-26-package-first-uasset-parser-refactor.md).

Source code and tests determine current behavior. The package-first report is the only repository-wide target design.

## Archived Documents

| Document | Historical purpose | Active replacement |
|---|---|---|
| `2026-06-01-real-asset-test-suite-design.md` | Early real-asset test-suite proposal | Canonical report: Testing Strategy and Acceptance Gates |
| `2026-06-03-development-scope-refined-design.md` | Earlier product scope and constraints | Canonical report: Scope and Decisions |
| `2026-06-03-output-format-ir-design.md` | Early unified IR/renderer proposal | Canonical report: Target Architecture and Output Contract |
| `2026-07-01-external-project-improvements.md` | External-project comparison roadmap | Canonical report: Evidence Inputs and Migration Plan |
| `2026-07-17-ir-renderer-refactor-design.md` | PackageIR/renderer maintenance proposal | Canonical report: PackageDocument migration |
| `2026-08-11-blueprint-semantic-json-design.md` | Blueprint Semantic 1.x design specification | Current source/tests for v0.5.5; canonical report for v2 |
| `2026-08-13-non-blueprint-semantic-design.md` | Semantic JSON 1.x domain expansion | Canonical report: object-scoped Asset Handlers |
| `2026-08-15-blueprint-semantic-json-extension-plan.md` | Blueprint Semantic 1.x implementation plan | Current source/tests for v0.5.5; canonical report for v2 |
| `2026-08-15-material-semantic-json-design.md` | Material Semantic 1.x implementation design | Current source/tests for v0.5.5; canonical report for v2 |
| `2026-08-15-material-semantic-json-plan.md` | Material Semantic 1.x implementation plan | Current source/tests for v0.5.5; canonical report for v2 |
| `2026-08-17-datatable-semantic-json-design.md` | DataTable Semantic 1.x design | Current source/tests for v0.5.5; canonical report for v2 |
| `2026-08-17-remaining-uasset-semantic-design.md` | Remaining Semantic 1.x domain design | Current source/tests for v0.5.5; canonical report for v2 |
| `core-extras-layering.md` | Earlier Core/Extras lazy-import boundary | Canonical report: Asset Handlers and dependency boundaries |
| `output-refactor.md` | Earlier monolithic JSON output proposal | Canonical report: package envelope, views, depth, and pagination |

## Archive Rules

- Preserve content and Git history; add corrections only as archive annotations.
- Do not move an archived document back into `docs/designs/` to revive it. Write a new dated design that updates the canonical architecture instead.
- Issue-specific evidence remains in `docs/designs/` while it supports active work. Closed issue material may be moved into a separate issue archive in a dedicated cleanup.
- Active documentation may link here for history, but acceptance criteria must link to the canonical report or current tests.
