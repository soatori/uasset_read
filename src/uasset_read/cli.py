"""CLI 入口模块 — argparse 参数解析、格式路由、错误处理。

等价迁移 uasset_read_legacy.py §7814-7938。
Phase 33 Plan 02: 入口与测试适配。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from uasset_read.parse_uasset import parse_uasset
from uasset_read.formatters import (
    format_json_full,
    format_json_summary,
    format_text_full,
    format_markdown,
    format_graphs_json,
)

# Exit code constants (D-26)
EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3


def create_parser() -> argparse.ArgumentParser:
    """
    Create argparse parser for CLI (CLI-01 to CLI-04).

    Per D-23: Double entry point support
    Per D-24: Mutually exclusive --json/--text/--summary/--markdown flags
    Per D-27: Optional flags: --verbose, --output FILE, --export INDEX
    D-14-17: --markdown flag (OUT-04)
    D-14-19: --schema flag (OUT-05)

    Returns:
        argparse.ArgumentParser: Configured parser
    """
    parser = argparse.ArgumentParser(
        prog='uasset_read',
        description='Parse Unreal Engine .uasset files and output structured data'
    )

    # Positional: file path (CLI-01)
    parser.add_argument('file', help='Path to .uasset file to parse')

    # Mutually exclusive output flags (D-24, D-14-17)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--json', action='store_true', help='Output full JSON structure')
    group.add_argument('--text', action='store_true', help='Output YAML-style text (default)')
    group.add_argument('--summary', action='store_true', help='Output compact summary format')
    group.add_argument('--markdown', action='store_true', help='Output Markdown format (D-14-17)')

    # Optional flags (D-27, D-14-19)
    parser.add_argument('--verbose', action='store_true', help='Include extra detail fields')
    parser.add_argument('--output', metavar='FILE', help='Write output to file instead of stdout')
    parser.add_argument('--export', metavar='INDEX', type=int, help='Output only specific export by index')
    parser.add_argument('--graph', action='store_true', help='Include blueprint graph data in output')
    parser.add_argument('--schema', action='store_true', help='Include field semantic annotations (_schema) (D-14-19)')
    parser.add_argument('--tolerant', action='store_true', default=True, help='Enable tolerant mode for UE5 serialization (default: on)')
    parser.add_argument('--strict', action='store_true', help='Disable tolerant mode: throw ParseError on serialization issues')

    return parser


def main():
    """
    Main CLI entry point (CLI-05).

    Per D-23: Double entry point (also __main__.py)
    Per D-25: stdout for data, stderr for errors
    Per D-26: Exit codes 0/1/2/3
    Per D-28: UTF-8 encoding for file output

    Exit codes:
    - 0: Success
    - 1: Parse error
    - 2: File not found
    - 3: Argument error
    """
    parser = create_parser()

    try:
        args = parser.parse_args()
    except SystemExit as e:
        # argparse exits on error, map to EXIT_ARGUMENT_ERROR
        sys.exit(EXIT_ARGUMENT_ERROR)

    # D-26: file not found check
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    # Parse the file
    tolerant = not args.strict
    result = parse_uasset(args.file, tolerant=tolerant)

    # D-26: parse error handling
    if not result.is_success:
        print("Parse errors:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    # Phase 8: --graph flag handling (D-08-12/13)
    # 优先级：--graph 检查在最前
    if args.graph:
        # D-08-13: --graph + --json/--verbose = full output with graphs
        if args.json or args.verbose:
            include_schema = args.schema or args.verbose
            output_str = json.dumps(format_json_full(result, include_schema), indent=2, ensure_ascii=False)
        elif args.text:
            # --graph --text = text output with Graphs section
            output_str = format_text_full(result)
        else:
            # D-08-13: --graph alone = only graphs in JSON format
            output_str = json.dumps({"graphs": format_graphs_json(result.graphs)},
                                    indent=2, ensure_ascii=False)
    elif args.markdown:
        # D-14-17: --markdown 标志输出 Markdown 格式
        output_str = format_markdown(result)
    elif args.json:
        include_schema = args.schema or args.verbose
        output_str = json.dumps(format_json_full(result, include_schema), indent=2, ensure_ascii=False)
    elif args.summary:
        include_schema = args.schema or args.verbose
        output_str = json.dumps(format_json_summary(result, include_schema), indent=2, ensure_ascii=False)
    else:
        # Default: --text or no flag
        output_str = format_text_full(result)

    # D-25/D-28: Output routing with UTF-8
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_str)
            print(f"Output written to {args.output}", file=sys.stderr)
        except IOError as e:
            print(f"Error writing to file: {e}", file=sys.stderr)
            sys.exit(EXIT_ARGUMENT_ERROR)
    else:
        # stdout for data (D-25)
        print(output_str)

    sys.exit(EXIT_SUCCESS)
