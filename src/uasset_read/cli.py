"""CLI 入口模块 — argparse 参数解析、格式路由、错误处理。

等价迁移 uasset_read_legacy.py §7814-7938。
Phase 33 Plan 02: 入口与测试适配。
Phase Export: 重构为使用统一导出系统（保持向后兼容）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from uasset_read.parse_uasset import parse_uasset, parse_uasset_with_linker

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
    Phase Export: --n2c, --validate, --list-formats, --batch, --batch-dir

    Returns:
        argparse.ArgumentParser: Configured parser
    """
    parser = argparse.ArgumentParser(
        prog='uasset_read',
        description='Parse Unreal Engine .uasset files and output structured data'
    )

    # Positional: file path (CLI-01) or directory (batch mode)
    parser.add_argument('file', nargs='?', default=None,
                        help='Path to .uasset file to parse (or directory in --batch mode)')

    # Mutually exclusive output flags (D-24, D-14-17)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--json', action='store_true', help='Output full JSON structure')
    group.add_argument('--text', action='store_true', help='Output YAML-style text (default)')
    group.add_argument('--summary', action='store_true', help='Output compact summary format')
    group.add_argument('--markdown', action='store_true', help='Output Markdown format (D-14-17)')
    group.add_argument('--blueprint-text', action='store_true', help='Output compact blueprint translation reference text')
    group.add_argument('--blueprint-ue-text', action='store_true', help='Output UE-style Begin Object blueprint text')
    group.add_argument('--cpp-skeleton', action='store_true',
                       help='Output C++ class skeleton (.h header) instead of JSON (requires blueprint)')
    # Phase Export: new formats
    group.add_argument('--n2c', action='store_true', help='Output N2C intermediate format JSON')

    # Optional flags (D-27, D-14-19)
    parser.add_argument('--verbose', action='store_true', help='Include extra detail fields')
    parser.add_argument('--output', metavar='FILE', help='Write output to file instead of stdout')
    parser.add_argument('--export', metavar='INDEX', type=int, help='Output only specific export by index')
    parser.add_argument('--graph', action='store_true', help='Include blueprint graph data in output')
    parser.add_argument('--schema', action='store_true', help='Include field semantic annotations (_schema) (D-14-19)')
    parser.add_argument('--function-graphs', action='store_true',
                        help='Include top-level function_graphs array in JSON output (output_version 5.0) (Phase 55)')
    parser.add_argument('--asset-root', action='append', default=[],
                        help='Root directory to search for parent .uasset files (can be repeated)')
    parser.add_argument('--include-parent-assets', action='store_true',
                        help='Resolve and parse parent Blueprint assets when available')
    parser.add_argument('--tolerant', action='store_true', default=True, help='Enable tolerant mode for UE5 serialization (default: on)')
    parser.add_argument('--strict', action='store_true', help='Disable tolerant mode: throw ParseError on serialization issues')

    # Phase Export: new flags
    parser.add_argument('--validate', action='store_true',
                        help='Validate output against schema (for N2C format)')
    parser.add_argument('--list-formats', action='store_true',
                        help='List all available export formats and exit')
    parser.add_argument('--batch', action='store_true',
                        help='Enable batch mode: treat positional arg as directory of .uasset files')
    parser.add_argument('--batch-dir', metavar='DIR',
                        help='Output directory for batch mode (default: ./output)')

    return parser


def resolve_format(args) -> str:
    """从 CLI 参数解析导出格式名。"""
    if args.n2c:
        return "n2c"
    if args.cpp_skeleton:
        return "cpp_skeleton"
    if args.blueprint_text:
        return "blueprint_text"
    if args.blueprint_ue_text:
        return "blueprint_ue_text"
    if args.markdown:
        return "markdown"
    if args.summary:
        return "json_summary"
    if args.json:
        return "json"
    if args.text:
        return "text"
    # Default
    return "text"


def _write_output(output_str: str, output_path: str | None) -> None:
    """统一输出写入。"""
    if output_path:
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(output_str)
            print(f"Output written to {output_path}", file=sys.stderr)
        except IOError as e:
            print(f"Error writing to file: {e}", file=sys.stderr)
            sys.exit(EXIT_ARGUMENT_ERROR)
    else:
        # stdout for data (D-25)
        print(output_str)


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
        # argparse exits with 0 on --help, preserve that
        if e.code == 0:
            sys.exit(EXIT_SUCCESS)
        sys.exit(EXIT_ARGUMENT_ERROR)

    # --list-formats: 列出所有格式并退出
    if args.list_formats:
        from uasset_read.exporter import ExporterRegistry
        formats = ExporterRegistry.list_formats()
        print("Available export formats:")
        for fmt in formats:
            print(f"  --{fmt.replace('_', '-')}")
        sys.exit(EXIT_SUCCESS)

    # Batch mode
    if args.batch:
        _handle_batch(args)
        return

    # Validate positional arg
    if args.file is None:
        print("Error: file argument is required (or use --batch for directory mode)", file=sys.stderr)
        sys.exit(EXIT_ARGUMENT_ERROR)

    # D-26 + HIGH-01: file not found check + verify it's a file, not a directory
    file_path = Path(args.file)
    if not file_path.is_file():
        if file_path.is_dir():
            print(f"Error: Not a file: {args.file}", file=sys.stderr)
        else:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    # Resolve format
    fmt = resolve_format(args)
    tolerant = not args.strict

    # 部分格式需要 parse_uasset_with_linker 以输出可读对象路径
    if fmt in {"cpp_skeleton", "blueprint_ue_text", "json", "json_summary"}:
        try:
            linker_result = parse_uasset_with_linker(
                args.file,
                tolerant=tolerant,
                include_parent_assets=args.include_parent_assets,
                asset_roots=args.asset_root,
            )
        except Exception as e:
            print(f"Error: Unexpected parse failure: {e}", file=sys.stderr)
            sys.exit(EXIT_PARSE_ERROR)

        if not linker_result.is_success:
            print("Parse errors:", file=sys.stderr)
            for err in linker_result.errors:
                print(f"  - {err}", file=sys.stderr)
            sys.exit(EXIT_PARSE_ERROR)

        # Verify blueprint exists only for formats that require blueprint metadata.
        if fmt == "cpp_skeleton" and (linker_result.blueprint is None or not linker_result.blueprint.is_blueprint):
            print("Error: --cpp-skeleton requires a blueprint file", file=sys.stderr)
            sys.exit(EXIT_PARSE_ERROR)

        # Use exporter
        from uasset_read.exporter import ExporterRegistry, ExportOptions
        options = ExportOptions(
            format=fmt,
            output_path=args.output,
        )
        try:
            exporter = ExporterRegistry.get(fmt)
            output_str = exporter.export(linker_result, options)
        except ValueError as e:
            if fmt == "cpp_skeleton":
                print(f"Error: C++ skeleton extraction failed: {e}", file=sys.stderr)
            else:
                print(f"Error: Blueprint UE text export failed: {e}", file=sys.stderr)
            sys.exit(EXIT_PARSE_ERROR)

        _write_output(output_str, args.output)
        sys.exit(EXIT_SUCCESS)

    # Standard parse
    try:
        result = parse_uasset(
            args.file,
            tolerant=tolerant,
            include_parent_assets=args.include_parent_assets,
            asset_roots=args.asset_root,
        )
    except Exception as e:
        print(f"Error: Unexpected parse failure: {e}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    # D-26: parse error handling
    if not result.is_success:
        print("Parse errors:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    # Phase 8: --graph flag handling (D-08-12/13)
    # --graph 有特殊逻辑，不经过统一导出器
    if args.graph:
        _handle_graph_mode(args, result)
        sys.exit(EXIT_SUCCESS)

    # Use unified export system
    from uasset_read.exporter import ExporterRegistry, ExportOptions, ExportValidationError

    options = ExportOptions(
        format=fmt,
        include_schema=args.schema or args.verbose,
        include_function_graphs=args.function_graphs,
        verbose=args.verbose,
        output_path=args.output,
        validate_output=args.validate,
    )

    try:
        exporter = ExporterRegistry.get(fmt)
        output_str = exporter.export(result, options)
    except ExportValidationError as e:
        print(f"Error: Output validation failed: {e}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)
    except ValueError as e:
        print(f"Error: Export failed: {e}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    _write_output(output_str, args.output)
    sys.exit(EXIT_SUCCESS)


def _handle_graph_mode(args, result):
    """处理 --graph 标志的特殊逻辑（向后兼容）。"""
    from uasset_read.formatters import format_json_full, format_text_full
    from uasset_read.graph import format_graphs_json

    # Phase 55: --function-graphs 隐含 --json
    if args.function_graphs and not (args.json or args.text or args.summary or args.markdown or args.blueprint_text or args.blueprint_ue_text):
        args.json = True

    if args.json or args.verbose:
        include_schema = args.schema or args.verbose
        include_function_graphs = args.function_graphs
        data = format_json_full(result, include_schema, include_function_graphs)
        output_str = json.dumps(data, indent=2, ensure_ascii=False)
    elif args.text:
        output_str = format_text_full(result)
    else:
        # --graph alone = only graphs in JSON format
        output_str = json.dumps({"graphs": format_graphs_json(result.graphs)},
                                indent=2, ensure_ascii=False)

    _write_output(output_str, args.output)


def _handle_batch(args):
    """处理批量导出模式。"""
    from uasset_read.exporter import ExportOptions, BatchExporter, ExporterRegistry, ExportValidationError

    # Resolve input directory
    if args.file is None:
        print("Error: directory argument is required in --batch mode", file=sys.stderr)
        sys.exit(EXIT_ARGUMENT_ERROR)

    input_dir = Path(args.file)
    if not input_dir.is_dir():
        print(f"Error: Not a directory: {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    # Collect .uasset files
    uasset_files = sorted(input_dir.glob("*.uasset"))
    if not uasset_files:
        print(f"Error: No .uasset files found in {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    # Resolve output directory
    output_dir = args.batch_dir or str(input_dir / "output")

    # Resolve format
    fmt = resolve_format(args)

    options = ExportOptions(
        format=fmt,
        include_schema=args.schema or args.verbose,
        include_function_graphs=args.function_graphs,
        verbose=args.verbose,
        validate_output=args.validate,
        output_dir=output_dir,
    )

    batch_exporter = BatchExporter(output_dir, options)
    file_paths = [str(f) for f in uasset_files]
    batch_result = batch_exporter.export_files(file_paths)

    # Report
    print(f"Batch export complete: {batch_result.total} files", file=sys.stderr)
    print(f"  Success: {len(batch_result.success)}", file=sys.stderr)
    if batch_result.skipped:
        print(f"  Skipped: {len(batch_result.skipped)}", file=sys.stderr)
        for path, reason in batch_result.skipped:
            print(f"    - {Path(path).name}: {reason}", file=sys.stderr)
    if batch_result.failed:
        print(f"  Failed: {len(batch_result.failed)}", file=sys.stderr)
        for path, error in batch_result.failed:
            print(f"    - {Path(path).name}: {error}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    sys.exit(EXIT_SUCCESS)
