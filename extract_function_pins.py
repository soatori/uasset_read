#!/usr/bin/env python
"""extract_function_pins.py — Extract function pin/parameter info from .uasset files.

Standalone entry point for quick function signature inspection.
Reuses the existing parse pipeline; no new core logic.

Usage:
    python extract_function_pins.py path/to/file.uasset
    python extract_function_pins.py path/to/file.uasset --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Inject src/ into Python path (same pattern as run.py)
_src_dir = Path(__file__).resolve().parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))


def create_parser() -> argparse.ArgumentParser:
    """Create argparse parser for the script."""
    parser = argparse.ArgumentParser(
        prog="extract_function_pins",
        description="Extract function parameter/pin information from .uasset Blueprint files.",
    )
    parser.add_argument("file", help="Path to .uasset file to parse")
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output machine-readable JSON instead of human-readable text",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Write output to file instead of stdout",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Disable tolerant mode (default: tolerant)",
    )
    return parser


def extract_function_pins(file_path: str, tolerant: bool = True) -> list[dict]:
    """Extract function pin/parameter info from a .uasset file.

    Parses the asset and returns Blueprint function data with parameters.

    Args:
        file_path: Path to .uasset file
        tolerant: Enable tolerant parsing mode (default: True)

    Returns:
        List of dicts, each with keys: function_name, return_type, parameters.
        Each parameter has keys: name, type, is_input, is_output.
    """
    from uasset_read import parse_package

    result = parse_package(file_path, tolerant=tolerant)

    if not result.is_success or not result.blueprint or not result.blueprint.is_blueprint:
        return []

    entries: list[dict] = []
    for func in result.blueprint.functions:
        params = [
            {
                "name": p.name,
                "type": p.param_type,
                "is_input": p.is_input,
                "is_output": p.is_output,
            }
            for p in func.parameters
        ]
        entries.append({
            "function_name": func.name,
            "return_type": func.return_type or "void",
            "parameters": params,
        })
    return entries


def format_text(entries: list[dict]) -> str:
    """Format function pin data as human-readable text.

    Output format per function:
        ReturnType FunctionName(Type1 Param1, Type2 Param2)
            <- Type1 Param1        (input)
            -> Type2 Param2        (output)

    Args:
        entries: List of function dicts from extract_function_pins()

    Returns:
        Formatted text string
    """
    if not entries:
        return "No functions found.\n"

    lines: list[str] = []
    for entry in entries:
        func_name = entry.get("function_name", "Unknown")
        return_type = entry.get("return_type", "") or "void"
        parameters = entry.get("parameters", [])

        param_parts = []
        for p in parameters:
            p_type = p.get("type", "")
            p_name = p.get("name", "")
            if p_type and p_name:
                param_parts.append(f"{p_type} {p_name}")
            elif p_name:
                param_parts.append(p_name)

        sig_params = ", ".join(param_parts)
        suffix = ""
        fallback = entry.get("fallback_reason")
        if fallback:
            suffix = f"  [{fallback}]"
        lines.append(f"{return_type} {func_name}({sig_params}){suffix}")

        for p in parameters:
            p_type = p.get("type", "")
            p_name = p.get("name", "")
            is_input = p.get("is_input", False)
            is_output = p.get("is_output", False)
            arrow = "<-" if is_input else "->"
            type_prefix = f"{p_type} " if p_type else ""
            lines.append(f"    {arrow} {type_prefix}{p_name}")

        lines.append("")  # blank line between functions

    return "\n".join(lines)


def format_json(entries: list[dict]) -> str:
    """Format function pin data as JSON.

    Args:
        entries: List of function dicts from extract_function_pins()

    Returns:
        JSON string (indented, UTF-8)
    """
    output = []
    for entry in entries:
        func = {
            "function_name": entry.get("function_name", "Unknown"),
            "return_type": entry.get("return_type", ""),
            "parameters": [],
        }
        for p in entry.get("parameters", []):
            func["parameters"].append({
                "name": p.get("name", ""),
                "type": p.get("type", ""),
                "is_input": p.get("is_input", False),
                "is_output": p.get("is_output", False),
            })
        output.append(func)
    return json.dumps(output, indent=2, ensure_ascii=False)


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.is_file():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        return 1

    try:
        entries = extract_function_pins(str(file_path), tolerant=not args.strict)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json_output:
        output = format_json(entries)
    else:
        output = format_text(entries)

    if args.output:
        try:
            Path(args.output).write_text(output, encoding="utf-8")
        except IOError as e:
            print(f"Error writing to file: {e}", file=sys.stderr)
            return 1
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
        print(output, end="")

    return 0


if __name__ == "__main__":
    sys.exit(main())
