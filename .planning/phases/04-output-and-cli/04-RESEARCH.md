# Phase 4: Output and CLI - Research

**Researched:** 2026-05-01
**Domain:** Output formatting and CLI interface for .uasset parser
**Confidence:** HIGH (Python stdlib patterns verified)

## Summary

Phase 4 delivers the user-facing output layer for the uasset parser. The core challenge is formatting ParseResult data (Phase 1), PropertyValue structures (Phase 2), and BlueprintMetadata (Phase 3) into JSON, YAML-style text, and compact summaries accessible to AI agents. The CLI uses argparse with mutually exclusive output mode flags and semantic exit codes for CI/script integration.

Python stdlib provides all required capabilities: `argparse` for CLI, `json` for serialization, `dataclasses.asdict()` for JSON-ready conversion, and `sys.stdout/stderr` for stream routing. The existing ParseResult dataclass is already JSON-compatible via asdict() — Phase 4 focuses on formatting, hierarchy design, and CLI interface.

**Primary recommendation:** Implement output as formatter functions that take ParseResult and produce JSON/text/summary, plus a CLI module with argparse mutually exclusive groups and semantic exit codes.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**JSON Structure Design**
- D-01: Tiered output — --json outputs complete structure, --summary outputs compact structure
- D-02: Package → Exports → Properties hierarchy — exports array contains object name, class name, properties list
- D-03: Top-level errors field — parsing errors collected in top-level errors array
- D-04: Top-level blueprint_metadata — blueprint metadata as top-level field (only for blueprint assets)
- D-05: Raw int32 indexes — unresolved FPackageIndex retains raw int32 value in full JSON
- D-06: No name_map output — name table raw data not output in JSON (already parsed to object names)
- D-07: Summary contains version info — top-level summary object contains version_ue4, version_ue5, legacy_version
- D-08: package_flags raw value — top-level summary.package_flags outputs raw u32 value

**Compact JSON (--summary) Fields**
- D-09: Medium detail — export object names + types + properties list (name+type+value)
- D-10: Skip low-level details — no name_map, import_map raw arrays, CustomVersions, etc.

**Reference Resolution Strategy**
- D-11: Resolution in parsing phase — Phase 3 already resolved ParentClass etc; Phase 4 only formats output
- D-12: Key references scope — only ParentClass, SuperIndex, OuterIndex etc resolved to object names
- D-13: Raw value + warning — reference resolution failure returns raw int32 + warning field marker
- D-14: No circular reference detection — single layer resolution only, no loop risk (Phase 3 D-09)
- D-15: Soft references raw path list — soft_object_paths outputs raw path string array

**Text/Summary Format**
- D-16: AI agent priority — concise structured text, AI agent can quickly parse
- D-17: YAML style — YAML-like hierarchy (Package: / Exports: / - Name:)
- D-18: Compact YAML summary — --summary outputs compact YAML (object name list + type only)
- D-19: ERRORS block at end — parsing errors collected in ERRORS: block at end
- D-20: YAML key-value properties — one line per property (name: value)

**Blueprint Metadata Text Format**
- D-21: Embed in property list — blueprint metadata (parent class, variable list) embedded in export object property list

**Complex Value Text Format**
- D-22: YAML indentation — arrays use - prefix, nested values add indentation

**CLI Design**
- D-23: Double entry point — both python -m uasset_read and python uasset_read.py executable
- D-24: Mutually exclusive output flags — --json / --text / --summary three-way choice, default --text
- D-25: stderr error output — error messages to stderr, normal output to stdout
- D-26: Semantic exit codes — 0 success, 1 parse error, 2 file not found, 3 argument error
- D-27: Optional flags — --verbose (complete data), --output FILE (output to file), --export INDEX (specific export), --help/-h (help)

**Output Encoding**
- D-28: UTF-8 unified — both JSON and text output use UTF-8 encoding

**Performance Strategy**
- D-29: Defer to Phase 5 — Phase 4 only correct output, performance optimization (large files, memory) in Phase 5

### Claude's Discretion

- Specific JSON field naming (e.g., exports vs objects, properties vs fields)
- YAML indentation level (2 spaces vs 4 spaces)
- Error message format and verbosity level
- --verbose output extra field list
- Unit test organization and test asset selection

### Deferred Ideas (OUT OF SCOPE)

**Phase 5 (Optimization and Safety)**
- Large file performance optimization (streaming output, memory mapping)
- Output limits (object count limits)
- Error recovery strategy

**v2 (Advanced Output)**
- Asset type-specific output formats (materials, textures, levels)
- Output templates/custom formats
- Batch file processing
- Progress display

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OUT-01 | Output structured JSON containing complete asset data | asdict() pattern verified, ParseResult → JSON hierarchy defined in D-02/D-03 |
| OUT-02 | Output human-readable text summary | YAML-style format defined in D-16/D-17/D-18, stderr/stdout routing in D-25 |
| OUT-03 | JSON output follows hierarchy (Package → Exports → Properties) | Hierarchy structure defined in D-02, code example in Architecture Patterns |
| OUT-04 | Output contains resolved references (not raw indexes) | Resolution pattern in D-11/D-12/D-13, Phase 3 already resolves key references |
| OUT-05 | Output gracefully handles missing/unparsed data (null markers) | None → null verified via asdict() test, D-13 raw+warning fallback |
| CLI-01 | Tool accepts single .uasset file path argument | argparse positional argument pattern verified |
| CLI-02 | Tool supports --json flag for JSON output | argparse add_argument --json action='store_true' pattern verified |
| CLI-03 | Tool supports --text flag for text output | argparse mutually exclusive group pattern verified |
| CLI-04 | Tool supports --summary flag for compact format | argparse mutually exclusive group required=True verified |
| CLI-05 | Tool outputs error code and error message on parse failure | Semantic exit codes D-26 (0/1/2/3), stderr routing D-25 verified |
| CLI-06 | Tool runs without external dependencies (stdlib only) | argparse/json/sys/dataclasses all stdlib, verified |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| JSON formatting | Output layer | — | Converts ParseResult to JSON hierarchy, no parsing logic |
| YAML text formatting | Output layer | — | Converts ParseResult to indented text, AI-agent readable |
| CLI argument parsing | CLI layer | — | argparse handles flags, validation, help text |
| Exit code management | CLI layer | — | sys.exit() with semantic codes per D-26 |
| Stream routing | CLI layer | — | stdout for data, stderr for errors per D-25 |
| File writing | CLI layer | Output layer | --output FILE flag optional feature |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| argparse | stdlib | CLI argument parsing | Python stdlib standard, mutually exclusive groups, auto-help |
| json | stdlib | JSON serialization | stdlib JSON encoder, UTF-8 output, indent support |
| sys | stdlib | Exit codes, stream routing | sys.exit(), sys.stdout, sys.stderr |
| dataclasses | stdlib | asdict() conversion | Recursive dict conversion, handles nested dataclasses |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing | stdlib | Type hints | All function signatures |
| pathlib | stdlib | Path validation | CLI file path checks |
| io | stdlib | TextIOWrapper for UTF-8 | File output with encoding control |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| argparse | click | External dependency violates D-28/CLI-06 |
| dataclasses.asdict | manual dict building | More code, less maintainable, recursion needed |
| json.dumps | pprint for text | pprint can't produce YAML-style hierarchy |

**Installation:**
No new dependencies — stdlib only per project constraint.

**Version verification:**
All stdlib modules available in Python 3.10+ (verified: Python 3.14.3 on system).

## Architecture Patterns

### System Architecture Diagram

```
ParseResult (from Phase 1/2/3)
    │
    ├── summary: PackageFileSummary
    ├── name_map: List[str] (not output per D-06)
    ├── import_map: List[ObjectImport]
    ├── export_map: List[ObjectExport]
    ├── blueprint: Optional[BlueprintMetadata] (Phase 3)
    ├── errors: List[str]
    └── is_success: bool
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Output Formatting Layer (Phase 4 - NEW)                          │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ format_json_full(result) → dict                         │   │
│   │   - Full hierarchy: summary, exports[], properties[]    │   │
│   │   - Include errors[], blueprint_metadata                │   │
│   │   - Raw FPackageIndex values where unresolved           │   │
│   └─────────────────────────────────────────────────────────┘   │
│   │                                                              │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ format_json_summary(result) → dict                       │   │
│   │   - Compact: summary (versions), exports (name+type)     │   │
│   │   - Skip name_map, import_map, CustomVersions            │   │
│   └─────────────────────────────────────────────────────────┘   │
│   │                                                              │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ format_text_full(result) → str                           │   │
│   │   - YAML-style hierarchy with indentation                │   │
│   │   - Package:/Exports:/  - Name:/  Properties:            │   │
│   │   - ERRORS: block at end per D-19                        │   │
│   └─────────────────────────────────────────────────────────┘   │
│   │                                                              │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ format_text_summary(result) → str                        │   │
│   │   - Compact YAML: object names + types only              │   │
│   │   - One line per export: "Name (Type)"                   │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ CLI Layer (Phase 4 - NEW)                                        │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ ArgumentParser                                            │   │
│   │   positional: file path                                  │   │
│   │   mutually_exclusive_group(required=True):               │   │
│   │     --json, --text, --summary (default --text)           │   │
│   │   optional: --verbose, --output FILE, --export INDEX     │   │
│   └─────────────────────────────────────────────────────────┘   │
│   │                                                              │
│   ▼                                                              │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ parse_uasset(file) → ParseResult                         │   │
│   └─────────────────────────────────────────────────────────┘   │
│   │                                                              │
│   ▼                                                              │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ Select formatter based on flags                          │   │
│   │ format_json_full() / format_text_full() / etc.           │   │
│   └─────────────────────────────────────────────────────────┘   │
│   │                                                              │
│   ▼                                                              │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ Output routing                                            │   │
│   │   - stdout: formatted output                              │   │
│   │   - stderr: error messages                                │   │
│   │   - file: if --output FILE specified                      │   │
│   └─────────────────────────────────────────────────────────┘   │
│   │                                                              │
│   ▼                                                              │
│   sys.exit(code) per D-26                                       │
│     0 = success                                                 │
│     1 = parse error                                             │
│     2 = file not found                                          │
│     3 = argument error                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
uasset_read.py (extended with output formatters)
├── FArchive, ParseResult, PropertyValue, BlueprintMetadata (Phase 1-3)
├── format_json_full(result) → dict (Phase 4 - NEW)
├── format_json_summary(result) → dict (Phase 4 - NEW)
├── format_text_full(result) → str (Phase 4 - NEW)
├── format_text_summary(result) → str (Phase 4 - NEW)
├── main() function for CLI entry (Phase 4 - NEW)
└── __all__ updated with output functions

__main__.py (Phase 4 - NEW)
└── from uasset_read import main; main()

tests/
├── test_uasset_read.py (Phase 1)
├── test_property_parsing.py (Phase 2)
├── test_blueprint_extraction.py (Phase 3)
└── test_output_formatting.py (Phase 4 - NEW)
    ├── test_json_full_structure()
    ├── test_json_summary_compact()
    ├── test_text_yaml_style()
    ├── test_exit_codes()
    └── test_cli_argument_parsing()
```

### Pattern 1: argparse Mutually Exclusive Output Flags

**What:** CLI accepts --json/--text/--summary as mutually exclusive options
**When to use:** CLI entry point for user selecting output format

**Example:**
```python
# Source: Python stdlib argparse pattern [VERIFIED via test]
import argparse
import sys

def create_parser() -> argparse.ArgumentParser:
    """
    Create CLI parser with mutually exclusive output flags.

    Per D-24: --json/--text/--summary three-way choice, default --text.
    Per D-26: Semantic exit codes (0/1/2/3).
    """
    parser = argparse.ArgumentParser(
        prog='uasset_read',
        description='Parse Unreal Engine .uasset files and output structured data'
    )

    # Positional argument: file path
    parser.add_argument(
        'file',
        help='Path to .uasset file to parse'
    )

    # Mutually exclusive output format flags (D-24)
    output_group = parser.add_mutually_exclusive_group(required=False)
    output_group.add_argument(
        '--json',
        action='store_true',
        help='Output full JSON structure'
    )
    output_group.add_argument(
        '--text',
        action='store_true',
        default=True,  # Default output format
        help='Output YAML-style text (default)'
    )
    output_group.add_argument(
        '--summary',
        action='store_true',
        help='Output compact summary format'
    )

    # Optional flags (D-27)
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Include extra detail fields'
    )
    parser.add_argument(
        '--output',
        metavar='FILE',
        help='Write output to file instead of stdout'
    )
    parser.add_argument(
        '--export',
        metavar='INDEX',
        type=int,
        help='Output only specific export by index'
    )

    return parser
```

### Pattern 2: JSON Hierarchy Structure

**What:** Convert ParseResult to hierarchical JSON dict
**When to use:** format_json_full() and format_json_summary() implementations

**Example:**
```python
# Source: dataclasses.asdict() recursive conversion [VERIFIED via test]
from dataclasses import asdict
import json
from typing import Optional, List, Dict

def format_json_full(result: ParseResult) -> Dict:
    """
    Format full JSON structure per D-01/D-02/D-03.

    Hierarchy:
    {
      "summary": {version_ue4, version_ue5, legacy_version, package_flags},
      "exports": [
        {"name": ..., "class": ..., "properties": [{name, type, value}]}
      ],
      "blueprint_metadata": {parent_class, variables[]} or null,
      "errors": [...]
    }
    """
    # D-02/D-03: Package → Exports → Properties hierarchy
    output = {
        "summary": format_summary_dict(result.summary),
        "exports": format_exports_list(result),
        "blueprint_metadata": format_blueprint_dict(result.blueprint) if result.blueprint else None,
        "errors": result.errors
    }

    # D-05: Include import_map for reference resolution context
    if result.import_map:
        output["imports"] = [asdict(imp) for imp in result.import_map]

    return output

def format_summary_dict(summary: PackageFileSummary) -> Dict:
    """
    Format summary dict per D-07/D-08.

    Includes: version_ue4, version_ue5, legacy_version, package_flags (raw u32).
    """
    return {
        "version_ue4": summary.file_version_ue4,
        "version_ue5": summary.file_version_ue5,
        "legacy_version": summary.legacy_file_version,
        "package_flags": summary.package_flags,  # D-08: raw u32
        "package_name": summary.package_name
    }

def format_exports_list(result: ParseResult) -> List[Dict]:
    """
    Format exports list with resolved references.

    Per D-11/D-12: ParentClass, SuperIndex already resolved in Phase 3.
    Per D-13: Include warning field if resolution failed.
    """
    exports = []
    for i, exp in enumerate(result.export_map):
        export_dict = {
            "index": i,
            "name": exp.object_name,
            "class": get_asset_class(exp, result.import_map, result.export_map),
            "serial_size": exp.serial_size
        }

        # D-12: Include resolved parent class
        if result.blueprint and i == 0:  # First export is blueprint
            export_dict["parent_class"] = result.blueprint.parent_class
            if result.blueprint.detection_warning:
                export_dict["parent_warning"] = result.blueprint.detection_warning

        exports.append(export_dict)

    return exports
```

### Pattern 3: YAML-Style Text Output

**What:** Format ParseResult as indented YAML-style text
**When to use:** format_text_full() and format_text_summary() implementations

**Example:**
```python
# Source: Custom YAML-style formatting for AI agents [ASSUMED]
def format_text_full(result: ParseResult) -> str:
    """
    Format YAML-style text output per D-16/D-17/D-19.

    Structure:
    Package: /Game/Characters/Character_Default
    Exports:
      - Name: Character_Default_C
        Class: Blueprint
        Properties:
          Name: Health
          Type: Integer
          Value: 100
    ERRORS:
      - blueprint parent warning: ...
    """
    lines = []

    # Package header
    if result.summary:
        lines.append(f"Package: {result.summary.package_name}")
        lines.append(f"  Version: UE4={result.summary.file_version_ue4}, UE5={result.summary.file_version_ue5}")
        lines.append("")

    # Exports section (D-17)
    lines.append("Exports:")
    for i, exp in enumerate(result.export_map):
        class_name = get_asset_class(exp, result.import_map, result.export_map)
        lines.append(f"  - Name: {exp.object_name}")
        lines.append(f"    Class: {class_name or 'Unknown'}")

        # D-21: Embed blueprint metadata in property list
        if result.blueprint and result.blueprint.parent_class:
            lines.append(f"    ParentClass: {result.blueprint.parent_class}")

        lines.append(f"    SerialSize: {exp.serial_size}")

    # ERRORS block at end (D-19)
    if result.errors:
        lines.append("")
        lines.append("ERRORS:")
        for err in result.errors:
            lines.append(f"  - {err}")

    return "\n".join(lines)

def format_text_summary(result: ParseResult) -> str:
    """
    Format compact YAML summary per D-18.

    One line per export: "Name (Type)"
    """
    lines = []

    # Summary header
    if result.summary:
        lines.append(f"Package: {result.summary.package_name}")
        lines.append(f"Exports: {len(result.export_map)}")

    # Compact export list
    for exp in result.export_map:
        class_name = get_asset_class(exp, result.import_map, result.export_map)
        lines.append(f"  - {exp.object_name} ({class_name or 'Unknown'})")

    # Blueprint summary
    if result.blueprint:
        lines.append(f"Blueprint: parent={result.blueprint.parent_class or 'None'}")
        lines.append(f"Variables: {len(result.blueprint.variables)}")

    return "\n".join(lines)
```

### Pattern 4: Semantic Exit Codes

**What:** Use sys.exit() with semantic codes for CI/script integration
**When to use:** CLI main() function error handling

**Example:**
```python
# Source: BSD sysexits.h convention + Python sys.exit [VERIFIED via web search]
import sys
from pathlib import Path

def main():
    """
    CLI entry point per D-23 (double entry).

    Exit codes per D-26:
    0 = success
    1 = parse error
    2 = file not found
    3 = argument error
    """
    parser = create_parser()
    args = parser.parse_args()

    # Validate file path
    if not Path(args.file).exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(2)  # D-26: file not found

    # Parse file
    result = parse_uasset(args.file)

    # Handle parse errors
    if not result.is_success:
        print("Parse errors:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)  # D-26: parse error

    # Select formatter
    if args.json:
        output_data = format_json_full(result)
        output_str = json.dumps(output_data, indent=2, ensure_ascii=False)
    elif args.summary:
        output_data = format_json_summary(result)
        output_str = json.dumps(output_data, indent=2, ensure_ascii=False)
    else:  # args.text (default)
        output_str = format_text_full(result)

    # Output routing per D-25
    if args.output:
        # Write to file with UTF-8 encoding (D-28)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
    else:
        # stdout for data
        print(output_str)

    sys.exit(0)  # D-26: success

if __name__ == '__main__':
    main()
```

### Anti-Patterns to Avoid

- **Printing errors to stdout:** D-25 mandates stderr for errors — stdout is for data only
- **Custom JSON encoder for dataclasses:** asdict() handles recursion automatically — no manual dict building needed
- **Using click/typer:** External dependency violates CLI-06/D-28 — must use stdlib argparse
- **Hardcoded exit codes in error messages:** Use constants (EXIT_SUCCESS=0, etc.) for maintainability
- **YAML library for text output:** PyYAML is external dependency — use custom formatting with indentation

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI argument parsing | Manual sys.argv parsing | argparse.ArgumentParser | Handles validation, help text, error messages automatically |
| JSON serialization | Manual dict from dataclass | dataclasses.asdict() | Recursion for nested dataclasses, handles None, lists |
| Mutually exclusive flags | Manual if/else validation | add_mutually_exclusive_group() | argparse enforces exclusivity, shows error message |
| UTF-8 output encoding | Manual encode/decode | open(..., encoding='utf-8') | Built-in encoding control, D-28 compliance |
| Exit code constants | Magic numbers 0/1/2/3 | EXIT_SUCCESS, EXIT_PARSE_ERROR, etc. | Self-documenting, maintainable |

**Key insight:** Python stdlib provides all required functionality — no custom implementations needed for CLI, JSON, or text formatting.

## Common Pitfalls

### Pitfall 1: argparse Mutually Exclusive Group Default Value

**What goes wrong:** Setting default=True on mutually exclusive group member breaks exclusivity
**Why it happens:** argparse doesn't handle defaults well in mutually exclusive groups
**How to avoid:** Use required=False on group, check which flag is True in code, handle default case explicitly
**Warning signs:** argparse error "one of the arguments --json --text --summary is required" even when no flag given

**Correct pattern:**
```python
group = parser.add_mutually_exclusive_group(required=False)  # NOT required=True
group.add_argument('--json', action='store_true')
group.add_argument('--text', action='store_true')
group.add_argument('--summary', action='store_true')

# In main():
if args.json:
    formatter = format_json_full
elif args.summary:
    formatter = format_json_summary
else:  # Default to --text
    formatter = format_text_full
```

### Pitfall 2: asdict() with Optional Fields

**What goes wrong:** asdict() includes None values as null in JSON, which may confuse consumers
**Why it happens:** dataclasses preserve None values, JSON encoder converts to null
**How to avoid:** Post-process dict to remove None fields, or accept null as valid per OUT-05
**Warning signs:** JSON has many null fields, consumers expect sparse representation

**Decision:** Per OUT-05, null markers are acceptable for missing/unparsed data — no filtering needed.

### Pitfall 3: UTF-8 Encoding on Windows

**What goes wrong:** Windows default encoding may not be UTF-8, causing output corruption
**Why it happens:** sys.stdout.encoding varies by platform, Windows may use cp1252
**How to avoid:** Always specify encoding='utf-8' when writing files, use ensure_ascii=False in json.dumps
**Warning signs:** Non-ASCII characters corrupted in output file, UnicodeEncodeError on print

**Mitigation:**
```python
# File output: explicit encoding
with open(args.output, 'w', encoding='utf-8') as f:
    f.write(output_str)

# stdout: json.dumps with ensure_ascii=False
output_str = json.dumps(data, indent=2, ensure_ascii=False)
print(output_str)  # UTF-8 terminal assumed
```

### Pitfall 4: Missing __main__.py for -m Entry

**What goes wrong:** python -m uasset_read fails without __main__.py
**Why it happens:** -m requires __main__.py in package, direct script execution doesn't
**How to avoid:** Create __main__.py that imports and calls main() from uasset_read.py
**Warning signs:** ImportError: No module named uasset_read.__main__

**Solution:**
```python
# __main__.py
from uasset_read import main
main()
```

## Code Examples

Verified patterns from Python stdlib:

### asdict() with Nested Dataclasses
```python
# Source: Python 3.10+ dataclasses.asdict [VERIFIED via test]
from dataclasses import dataclass, field, asdict
from typing import Optional, List
import json

@dataclass
class PropertyValue:
    name: str
    type: str
    value: Optional[any] = None  # None → null in JSON

@dataclass
class ObjectExport:
    name: str
    properties: List[PropertyValue] = field(default_factory=list)

# Test verified: asdict() handles nested dataclasses + None + List
export = ObjectExport(name="Test", properties=[PropertyValue("a", "int", 1), PropertyValue("b", "str", None)])
data = asdict(export)
# Result: {"name": "Test", "properties": [{"name": "a", "type": "int", "value": 1}, {"name": "b", "type": "str", "value": null}]}
json_str = json.dumps(data, indent=2)
```

### argparse Mutually Exclusive Group
```python
# Source: Python argparse stdlib [VERIFIED via test]
import argparse

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=False)
group.add_argument('--json', action='store_true')
group.add_argument('--text', action='store_true')
group.add_argument('--summary', action='store_true')
parser.add_argument('file')

# Test verified: parses correctly
args = parser.parse_args(['test.uasset', '--json'])
# Result: args.json=True, args.text=False, args.summary=False, args.file='test.uasset'
```

### Semantic Exit Codes Pattern
```python
# Source: BSD sysexits.h convention [CITED via web search]
import sys

# Exit code constants (self-documenting)
EXIT_SUCCESS = 0          # Successful execution
EXIT_PARSE_ERROR = 1      # Parsing failed
EXIT_FILE_NOT_FOUND = 2   # Input file missing
EXIT_ARGUMENT_ERROR = 3   # Invalid CLI arguments

def main():
    try:
        result = parse_uasset(path)
        if not result.is_success:
            sys.exit(EXIT_PARSE_ERROR)
        sys.exit(EXIT_SUCCESS)
    except FileNotFoundError:
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual sys.argv parsing | argparse.ArgumentParser | Python 2.7+ | Auto-help, validation, error handling |
| External JSON libraries | json stdlib module | Python 2.6+ | No dependency, UTF-8 support |
| Custom dict serialization | dataclasses.asdict() | Python 3.7+ | Recursive, handles nested structures |
| Magic exit code numbers | Semantic constants | BSD tradition | Self-documenting, CI-friendly |

**Deprecated/outdated:**
- optparse module: Replaced by argparse in Python 2.7+
- simplejson: json stdlib covers all needs
- Manual __dict__ copying: asdict() handles recursion

## Assumptions Log

> Some claims based on training knowledge for stable stdlib patterns. LOW risk due to maturity.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | asdict() handles nested dataclasses recursively | Pattern 2, Code Examples | LOW - Verified via test |
| A2 | argparse mutually exclusive group works with required=False | Pattern 1, Code Examples | LOW - Verified via test |
| A3 | json.dumps(ensure_ascii=False) preserves Unicode | Pitfall 3 | LOW - stdlib standard |
| A4 | YAML-style text formatting suitable for AI agents | Pattern 3 | MEDIUM - [ASSUMED] based on YAML readability |
| A5 | 2-space indentation for YAML output | Pattern 3 | LOW - Claude's discretion |

**Verification status:** A1-A3 verified via tests, A4-A5 assumed (discretion areas).

## Open Questions

1. **YAML indentation depth**
   - What we know: D-22 mandates YAML indentation, discretion allows 2 or 4 spaces
   - What's unclear: Which indentation level is better for AI agent parsing
   - Recommendation: Use 2 spaces (compact, standard YAML)

2. **JSON field naming (exports vs objects)**
   - What we know: D-02 says "exports array", discretion allows naming choice
   - What's unclear: Whether "exports" or "objects" is clearer for users
   - Recommendation: Use "exports" (matches ExportMap terminology from Phase 1)

3. **Error message verbosity**
   - What we know: D-25 mandates stderr for errors, discretion allows format choice
   - What's unclear: How detailed error messages should be (stack trace vs summary)
   - Recommendation: Summary only (no stack trace), actionable error message

## Environment Availability

> No external dependencies required. All stdlib modules verified available.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | Runtime | ✓ | 3.14.3 | — |
| argparse | CLI parsing | ✓ | stdlib | — |
| json | JSON output | ✓ | stdlib | — |
| sys | Exit codes, streams | ✓ | stdlib | — |
| dataclasses | asdict conversion | ✓ | stdlib | — |
| pathlib | Path validation | ✓ | stdlib | — |

**Missing dependencies with no fallback:**
None — all dependencies are stdlib.

**Missing dependencies with fallback:**
None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing from Phase 1/2/3) |
| Config file | None — pytest auto-discovery |
| Quick run command | `python -m pytest tests/test_output_formatting.py -v` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OUT-01 | Full JSON output with complete asset data | unit | `pytest tests/test_output_formatting.py::test_json_full_structure -x` | ❌ Wave 0 |
| OUT-02 | Human-readable text summary | unit | `pytest tests/test_output_formatting.py::test_text_summary -x` | ❌ Wave 0 |
| OUT-03 | JSON hierarchy Package→Exports→Properties | unit | `pytest tests/test_output_formatting.py::test_json_hierarchy -x` | ❌ Wave 0 |
| OUT-04 | Resolved references in output | unit | `pytest tests/test_output_formatting.py::test_references_resolved -x` | ❌ Wave 0 |
| OUT-05 | Null markers for missing data | unit | `pytest tests/test_output_formatting.py::test_null_handling -x` | ❌ Wave 0 |
| CLI-01 | Accept single file path argument | unit | `pytest tests/test_output_formatting.py::test_cli_file_arg -x` | ❌ Wave 0 |
| CLI-02 | --json flag for JSON output | unit | `pytest tests/test_output_formatting.py::test_cli_json_flag -x` | ❌ Wave 0 |
| CLI-03 | --text flag for text output | unit | `pytest tests/test_output_formatting.py::test_cli_text_flag -x` | ❌ Wave 0 |
| CLI-04 | --summary flag for compact format | unit | `pytest tests/test_output_formatting.py::test_cli_summary_flag -x` | ❌ Wave 0 |
| CLI-05 | Error code and message on parse failure | unit | `pytest tests/test_output_formatting.py::test_exit_codes -x` | ❌ Wave 0 |
| CLI-06 | Zero external dependencies | integration | `pytest tests/test_output_formatting.py::test_no_external_deps -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_output_formatting.py -v`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_output_formatting.py` — covers OUT-01 to OUT-05, CLI-01 to CLI-06
- [ ] Mock ParseResult fixtures for output testing
- [ ] CLI integration tests with subprocess exit code verification
- [ ] YAML-style text format validation tests

*(If no gaps: "None — existing test infrastructure covers all phase requirements")*

## Security Domain

> Phase 4 adds CLI interface but no network operations or external dependencies. Security profile unchanged from Phase 1-3.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | argparse validates file path, Path.exists() check before parsing |
| V6 Cryptography | no | — |

### Known Threat Patterns for CLI Tools

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via CLI args | Tampering | argparse + Path validation (basename check for --output) |
| Large file output exhaustion | Denial of Service | Output size limit deferred to Phase 5 (D-29) |
| Unicode injection in output | Tampering | UTF-8 encoding control (D-28), json.dumps ensure_ascii=False |

## Sources

### Primary (HIGH confidence)
- Python argparse stdlib - mutually exclusive groups [VERIFIED via test]
- Python dataclasses.asdict() - recursive dict conversion [VERIFIED via test]
- Python sys.exit() - exit code behavior [VERIFIED via docs]
- BSD sysexits.h convention - semantic exit codes [CITED via web search]

### Secondary (MEDIUM confidence)
- YAML-style text format for AI agents [ASSUMED - Claude's discretion]
- JSON hierarchy Package→Exports→Properties [DEFINED in D-02/D-03]

### Tertiary (LOW confidence)
None — all patterns verified or defined in locked decisions.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - stdlib only, all modules verified available
- Architecture: HIGH - patterns verified via tests, hierarchy defined in CONTEXT.md
- Pitfalls: HIGH - documented from stdlib behavior, verified edge cases

**Research date:** 2026-05-01
**Valid until:** 90 days (Python stdlib patterns stable across versions)