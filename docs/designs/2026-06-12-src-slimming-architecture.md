# Source Slimming Architecture

## Current Direction

`uasset_read` keeps its parser scope broad but narrows its public output surface.
The core parser still supports direct package files, companion payload files,
Pak, IoStore, linker reconstruction, property parsing, Blueprint extraction,
graph analysis, and Kismet bytecode analysis. Public rendering is limited to
two formats:

- `json`
- `markdown`

This keeps machine-readable output and documentation-oriented output available
while removing duplicated text, summary, and Blueprint-specific renderer
surfaces.

## Target Framework

The current architecture should be understood as four layers:

| Layer | Modules | Responsibility |
|---|---|---|
| Core input and archive | `archive`, `package`, `pak`, `iostore` | Open filesystem packages and supported containers without loading unsafe amounts of data into memory. |
| Parse and link | `parse_uasset`, `serializers`, `parsers`, `link`, `mappings` | Read UE package structures, properties, object resources, mappings, and linker object graphs. |
| Deep analysis | `blueprint`, `graph`, `kismet` | Extract Blueprint metadata, graph flow, and Kismet semantics. These features remain available, but should not require extra public render formats. |
| IR and output | `ir_builder`, `renderers` | Convert parse results into package IR and render only JSON or Markdown. |

Deep analysis modules are retained because they contribute to JSON/Markdown
content and future analysis work. Shrinking should come from clearer module
boundaries, lazy imports, and removing stale adapters rather than deleting
Blueprint, graph, or Kismet behavior.

## Completed Slimming

- Removed obsolete public render formats: `json_summary`, `text`,
  `text_summary`, `blueprint_text`, and `blueprint_ue_text`.
- Kept public render formats to `json` and `markdown`.
- Removed the stale same-name `src/uasset_read/ir_builder.py` file.
- Kept `src/uasset_read/ir_builder/` as the only active IR builder package.
- Removed old renderer modules that only served deleted output formats.

## Remaining Large Files

These files still exceed 1000 lines and are the next structural split targets:

| File | Approximate lines | Preferred split direction |
|---|---:|---|
| `src/uasset_read/kismet/translator.py` | 1158 | Separate type registry, translation orchestration, and expression formatting helpers. |
| `src/uasset_read/serializers/package_summary.py` | 1087 | Keep public entrypoint thin; split UE4/UE5 helpers and validation/read-table helpers. |
| `src/uasset_read/blueprint/variable_extractor.py` | 1056 | Separate variable extraction, metadata extraction, and compatibility helpers. |
| `src/uasset_read/parsers/property_parser.py` | 1017 | Separate export payload context, property dispatch, and unversioned-property handling. |

Files in the 700-900 line range should be reviewed after the four files above:
`iostore/reader.py`, `parse_uasset.py`, `serializers/object_resources.py`,
`graph/flow_builder.py`, `link/linker.py`, and
`parsers/property_types/structs.py`.

## Design Constraints

Source slimming is a structural cleanup, not a parser behavior rewrite. The
implementation should preserve valid inputs and safety behavior while reducing
dead surfaces and oversized files. See
`docs/guides/src-slimming-constraints.md` for the hard constraints that apply
to every follow-up change.
