# CLAUDE.md

Claude Code project specification for this repository.

## General Rules

- All code comments, error messages, and documentation must be in English; keep output professional and concise.
- Implement code in the simplest way possible; avoid over-abstraction, redundant wrappers, and unnecessary complexity.
- Project overview: `uasset_read` is a zero-runtime-dependency Unreal `.uasset` parser for Python 3.10+, supporting unbaked/editor-saved assets (including full Blueprint data).
- Windows paths use `E:/Develop/...` or double backslashes; test samples are in `tests/samples/`.

## Code Understanding

- CodeGraph (`.codegraph/`) is the primary tool for code exploration and call-path tracing.

## LLM Wiki Retrieval

Call `llm_wiki_explore` to query the local knowledge base before architectural decisions, format understanding, diagnostics, or technical decisions.

Keywords cover the following areas (by `wiki/` directory structure):

| Area | Keywords |
|------|----------|
| Architecture | `IR`, `FArchive`, `Pipeline`, `ExportTable`, `ImportTable` |
| Core Modules | `Models`, `Parsers`, `Serializers`, `Exceptions` |
| Advanced Features | `Blueprint`, `Kismet`, `Linker`, `Graph`, `UEdGraph`, `UEdGraphNode` |
| Container Systems | `PAK`, `IoStore`, `RawFiles` |
| Output Formats | `JSON`, `Markdown` |
| UE Format Reference | `UProperty`, `UFunction`, `UClass`, `FFieldNode`, `SerializationStrategy` |

## Constraints

See `.claude/rules/constraints.md` for full details. Key points: read-only, zero runtime dependencies, no `pip install`.

## Branches and Commits

- `develop` for daily development; `master` for releases; `wiki/master` for Wiki maintenance.
- `master` only allows: `src/`, CI, README, `CLAUDE.md`, `pytest.ini`, `run.py`, `tests/`, specified `docs/`, `.claude/rules/`.
- Commit format: `<type>: <summary> (#issue)`. Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `release`. Issue number is optional.

## Documentation Structure

- `wiki/`: Developer guides
- `docs/formats/uasset/`: UE format reference
- `docs/designs/`, `docs/reference/`, `docs/release-notes/`: Design, reference, and release documentation
- Issue tracking: GitHub Issues (`gh` CLI); see `docs/agents/issue-tracker.md`
