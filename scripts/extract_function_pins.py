"""Standalone script to extract function parameter/pin information from .uasset files.

Usage:
    python extract_function_pins.py path/to/file.uasset           # human-readable
    python extract_function_pins.py path/to/file.uasset --json    # machine-readable

All underlying APIs are in uasset_read; this is a convenience entry point.
"""

import argparse
import json
import sys
from pathlib import Path

# Inject src/ into Python path so it can be called directly from the project root
_src_dir = Path(__file__).resolve().parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from uasset_read.pipeline.core import parse_uasset_with_linker


def extract_pins(file_path: str) -> list[dict]:
    """Extract function pin/parameter info from a .uasset file.

    Returns a list of dicts with keys: function_name, return_type, parameters.
    """
    result = parse_uasset_with_linker(file_path, include_parent_assets=False)

    functions: list[dict] = []
    blueprint = getattr(result, "blueprint", None)
    if blueprint is None:
        return functions

    for func in blueprint.functions:
        params = []
        for p in func.parameters:
            params.append({
                "name": p.name,
                "type": p.param_type,
                "is_input": p.is_input,
                "is_output": p.is_output,
            })
        functions.append({
            "function_name": func.name,
            "return_type": func.return_type or "void",
            "parameters": params,
        })

    return functions


def format_human(functions: list[dict]) -> str:
    """Format function list as human-readable text."""
    lines: list[str] = []
    for func in functions:
        inputs = [p for p in func["parameters"] if p["is_input"]]
        outputs = [p for p in func["parameters"] if p["is_output"]]

        param_parts = []
        for p in inputs:
            param_parts.append(f"{p['type']} {p['name']}")
        param_str = ", ".join(param_parts)

        lines.append(f"{func['return_type']} {func['function_name']}({param_str})")

        for p in inputs:
            lines.append(f"    <- {p['type']} {p['name']}")
        for p in outputs:
            lines.append(f"    -> {p['type']} {p['name']}")

        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract function pin/parameter information from .uasset files",
    )
    parser.add_argument("file", help="Path to .uasset file")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="Output as JSON (default: human-readable)")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    try:
        functions = extract_pins(str(path))
    except Exception as e:
        print(f"Error parsing {args.file}: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json_output:
        print(json.dumps(functions, indent=2, ensure_ascii=False))
    else:
        if not functions:
            print(f"No functions found in {args.file}")
        else:
            print(format_human(functions))


if __name__ == "__main__":
    main()
