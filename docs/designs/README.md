# Active Design Documents

This directory contains active targets and issue-specific evidence. Superseded repository-wide designs are physically separated under `archive/`.

## Authoritative Repository-Wide Target

- [`2026-08-26-package-first-uasset-parser-refactor.md`](2026-08-26-package-first-uasset-parser-refactor.md) — the only authoritative target architecture. It is a design baseline, not a claim that the refactor has been implemented.

## Issue-Specific Documents

Files named `issue-*` contain focused evidence, gates, or execution plans. Their status is local to that issue and does not override the repository-wide target. Verify implementation claims in source, tests, real samples, and the live issue state.

## Archive

- [`archive/README.md`](archive/README.md) — superseded output, IR, Semantic 1.x, scope, test-suite, comparison, and Core/Extras designs.

## Rules

1. Source and tests determine current behavior.
2. The authoritative target determines new repository-wide architecture work.
3. New designs must state `Target`, `Current-state`, `Historical`, or `Superseded` near the top.
4. Superseded repository-wide designs move to `archive/`; they do not remain beside active designs.
5. Do not add another repository-wide output architecture without updating the canonical target and this index.
6. Wiki and README pages must distinguish implemented behavior from planned behavior.
