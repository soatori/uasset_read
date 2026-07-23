# CLAUDE.md

Project conventions for Claude Code in this repository.

## Basic Rules

- All conversations, code comments, error messages, and documentation are in English; keep output professional and concise.
- Project: `uasset_read` is a Python 3.10+ zero-runtime-dependency Unreal `.uasset` parser for unbaked/editor-saved assets (including full Blueprint data).
- Format understanding must reference UE source code (`E:\Develop\lib\UnrealEngine`); no guessing binary formats.
- Use `E:/Develop/...` or double backslashes for Windows paths; test samples are at `E:\Develop\lib\Samples`.
- Temp files, debug logs, and test artifacts go in the project root `temp/` directory.

## Constraints

Full constraints are in `.claude/rules/constraints.md`. Key points: read-only, zero runtime dependencies, no `pip install`.

## Branches and Commits

- `develop` daily development; `master` releases; `wiki/master` Wiki maintenance.
- `master` allows only `src/`, CI, README, `CLAUDE.md`, `pytest.ini`, `run.py`, `tests/`, specified `docs/`, `.claude/rules/`.
- Commit: `<type>: <brief>`, types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `release`.

## Documentation Structure

- `wiki/`: developer guides
- `docs/formats/uasset/`: UE format reference
- `docs/designs/`, `docs/reference/`, `docs/release-notes/`: design, reference, and release docs
- Issue tracker: GitHub Issues (`gh` CLI); see `docs/agents/issue-tracker.md`

## Agent skills

### Issue tracker

Issues live in GitHub Issues, accessed via the `gh` CLI. External PRs are not a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo — one `CONTEXT.md` + `docs/adr/` at the repo root (neither exists yet). See `docs/agents/domain.md`.
