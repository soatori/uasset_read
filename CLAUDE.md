# CLAUDE.md

Claude Code project specification for this repository. Repository-wide rules live in `AGENTS.md`; this file adds Claude-specific navigation.

## General Rules

- Code, comments, and error messages use English. Documentation follows the language of the document; repository-wide design reports may be Chinese when requested. Agent summaries and user replies may be Chinese.
- Implement code in the simplest way possible; avoid over-abstraction, redundant wrappers, and unnecessary complexity.
- Current overview: v0.6.0-dev is a Python 3.10+ read-only parser whose default path is the package-first v2 document (`parse_package_document` / `python -m uasset_read`). Strongest path: classic editor-saved packages and Blueprint decode.
- Target overview: remaining deferred gaps are Zen body extract, full `SchemaProvider`, Pak product path — see `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` and `docs/designs/2026-09-13-deferred-capability-bundling.md`. Do not describe deferred gaps as implemented.
- Windows paths use `E:/Develop/...` or double backslashes; test samples are in `tests/samples/`.

## Code Understanding

- CodeGraph (`.codegraph/`) is the primary tool for code exploration and call-path tracing. Source and tests override prose descriptions of current behavior.

## Constraints

See `AGENTS.md` and `.claude/rules/constraints.md`. Key points: package-first architecture, source-backed binary decisions, bounded reads, cross-platform Python, structured diagnostics, and a read-only first v2 milestone.

## Branches and Commits

- `develop` for daily development; `master` for releases; `wiki/master` for Wiki maintenance.
- `master` only allows: `src/`, CI, README, `CLAUDE.md`, `pytest.ini`, `run.py`, `tests/`, specified `docs/`, `.claude/rules/`.
- Commit format: `<type>: <summary> (#issue)`. Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `release`. Issue number is optional.

## Documentation Structure

- `wiki/`: Developer guides (separate git repo; keep in sync with `src/`)
- `docs/formats/uasset/`: UE format reference
- `docs/designs/`, `docs/reference/`, `docs/release-notes/`: Design, reference, and release documentation
- `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`: authoritative target architecture
- `docs/designs/README.md`: status of active designs; executed plans live under `docs/designs/archive/`
- Issue tracking: GitHub Issues (`gh` CLI); see `docs/agents/issue-tracker.md`
