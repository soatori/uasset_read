# Source Slimming Constraints

## Non-Negotiable Inputs

Do not remove support for any currently valid input class:

- Direct `.uasset` and `.umap` package files.
- Companion package payloads such as `.uexp`, `.ubulk`, and `.uptnl`.
- Pak-backed package access.
- IoStore-backed package access.
- Type mappings through `.usmap` and `.jmap`.
- Parent asset discovery when explicitly requested.

Removing public output formats does not imply removing the parser or analysis
data that can feed JSON or Markdown.

## Safety Constraints

Any source slimming or large-file split must preserve these behaviors:

- Large-file limits through `--max-file-size`.
- Batch memory threshold handling through `--max-memory`.
- Batch garbage-collection cadence through `--batch-size`.
- Lightweight parsing fallback for high export counts.
- Pak short-read validation for compressed and uncompressed reads.
- IoStore short-read validation for compressed blocks and uncompressed
  partitions.
- `tolerant` and `strict` mode semantics.
- Partial/opaque/fallback diagnostics for unsupported or unknown payloads.

Changes that increase peak memory usage for large assets or containers are not
acceptable, even if tests still pass on small fixtures.

## Output Constraints

The only public renderer formats are:

- `json`
- `markdown`

Do not reintroduce `json_summary`, `text`, `text_summary`, `blueprint_text`, or
`blueprint_ue_text` as public CLI or `list_formats()` outputs unless a new
design explicitly reverses the slimming decision.

Deep Blueprint, graph, and Kismet analysis may remain available through JSON,
Markdown, and direct submodule APIs. They should not require dedicated public
render formats.

## Refactor Rules

- Prefer moving code behind clearer module boundaries before changing parsing
  semantics.
- Keep binary parsing behavior anchored to Unreal Engine serialization
  semantics.
- Keep container paths separate during review and testing; do not conflate Pak,
  IoStore, filesystem packages, compressed reads, and uncompressed reads.
- Keep public root imports narrow. Prefer submodule imports for advanced
  analysis code.
- Preserve import paths that are still documented as active API.
- Mark obsolete plans as superseded instead of deleting historical context.

## Required Verification

Every slimming change should run:

```bash
python run.py --help
python run.py --list-formats
python -m pytest tests -q
python -m compileall -q src tests
```

For changes touching Pak, IoStore, archive, package, property parsing, graph
execution, or linker boundaries, also run the narrow tests that cover that
specific path before the full suite.
