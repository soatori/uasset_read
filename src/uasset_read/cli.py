"""CLI 入口模块 — argparse 参数解析 + 委托 core.py。

核心逻辑与入口分离：core.py 提供纯解析函数，CLI 仅负责参数解析和输出写入。
"""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

from uasset_read.core import parse_single, parse_batch, list_formats, ParseError

# Exit code constants
EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3

_logger = logging.getLogger(__name__)


def _sanitize_error_message(message: str) -> str:
    """清理异常消息中的内部路径，防止信息泄露。

    将绝对路径替换为 basename，保留异常类型和关键信息。
    详细原始消息可通过 DEBUG 级别日志获取。
    """
    def basename(path: str) -> str:
        normalized = path.rstrip("\\/").replace("\\", "/")
        return normalized.rsplit("/", 1)[-1] if "/" in normalized else normalized

    sanitized = str(message)

    # Prefer extension-anchored matches so paths with spaces followed by prose
    # do not consume the following error text.
    path_extensions = (
        "uasset", "umap", "uexp", "ubulk", "uptnl", "pak",
        "json", "txt", "bin", "dat", "log",
    )
    ext_group = "|".join(path_extensions)
    # Fallback patterns for paths without extensions (stop at delimiters)
    _close_delims = r"[\x29\x5d\x22\x27]"  # ) ] " '
    patterns = [
        rf"[A-Za-z]:\\[^:\r\n]*?\.({ext_group})(?::\d+)?",
        rf"\\\\[^:\r\n]*?\.({ext_group})(?::\d+)?",
        rf"/[^:\r\n;,)\]\"']*?\.({ext_group})(?::\d+)?",
        rf"[A-Za-z]:\\[^:\r\n]+?(?=(?::\s|{_close_delims}|$))",
        rf"\\\\[^:\r\n]+?(?=(?::\s|{_close_delims}|$))",
        rf"/(?:[^/:\r\n;,)\]\"']+/)+[^/:\r\n;,)\]\"']+?(?=(?::\s|{_close_delims}|$))",
    ]
    for pattern in patterns:
        sanitized = re.sub(pattern, lambda m: basename(m.group(0)), sanitized)
    return sanitized


def create_parser() -> argparse.ArgumentParser:
    """Create argparse parser for CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        prog='uasset_read',
        description='Parse Unreal Engine .uasset/.umap files and output structured data'
    )

    parser.add_argument('file', nargs='?', default=None,
                        help='Path to .uasset/.umap file to parse (or directory in --batch mode)')

    # Mutually exclusive output flags
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--json', action='store_true', help='Output full JSON structure')
    group.add_argument('--markdown', action='store_true', help='Output Markdown format')

    # Optional flags
    parser.add_argument('--verbose', action='store_true', help='Include extra detail fields')
    parser.add_argument('--output', metavar='FILE', help='Write output to file instead of stdout')
    parser.add_argument('--export', metavar='INDEX', type=int, help='Output only specific export by index')
    parser.add_argument('--schema', action='store_true', help='Include field semantic annotations')
    parser.add_argument('--function-graphs', action='store_true', help='Include function_graphs array')
    parser.add_argument('--asset-root', action='append', default=[],
                        help='Root directory to search for parent .uasset files')
    parser.add_argument('--include-parent-assets', action='store_true',
                        help='Resolve and parse parent Blueprint assets')
    parser.add_argument('--mappings', metavar='FILE', help='Load .usmap/.jmap type mappings')
    parser.add_argument('--game', metavar='NAME', help='Enable game-specific property readers')
    parser.add_argument('--tolerant', action='store_true', default=True, help='Enable tolerant mode (default)')
    parser.add_argument('--strict', action='store_true', help='Disable tolerant mode')

    # Batch and utility flags
    parser.add_argument('--list-formats', action='store_true', help='List all available export formats')
    parser.add_argument('--batch', action='store_true', help='Enable batch mode')
    parser.add_argument('--batch-dir', metavar='DIR', help='Output directory for batch mode')
    parser.add_argument('--list-package-files', action='store_true', help='List discovered package files')

    return parser


def resolve_format(args) -> str:
    """从 CLI 参数解析导出格式名。"""
    if args.markdown:
        return "markdown"
    return "json"


def _write_output(output_str: str, output_path: str | None) -> None:
    """统一输出写入。"""
    if output_path:
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(output_str)
            print(f"Output written to {output_path}", file=sys.stderr)
        except IOError as e:
            _logger.debug("File write error (full): %s", e, exc_info=True)
            print(f"Error writing to file: {_sanitize_error_message(e)}", file=sys.stderr)
            sys.exit(EXIT_ARGUMENT_ERROR)
    else:
        print(output_str)


def _handle_batch(args) -> None:
    """处理批量导出模式。"""
    input_dir = Path(args.file)
    if not input_dir.is_dir():
        print(f"Error: Not a directory: {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    output_dir = args.batch_dir or str(input_dir / "output")

    try:
        result = parse_batch(
            str(input_dir),
            format=resolve_format(args),
            output_dir=output_dir,
            tolerant=not args.strict,
            verbose=args.verbose,
            include_schema=args.schema or args.verbose,
            include_function_graphs=args.function_graphs,
            include_parent_assets=args.include_parent_assets,
            asset_roots=list(args.asset_root or []),
            mappings_path=args.mappings,
            game=args.game,
        )
    except Exception as e:
        _logger.debug("Batch export error (full): %s", e, exc_info=True)
        print(f"Error: {_sanitize_error_message(e)}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    print(f"Batch export complete: {result.total} files", file=sys.stderr)
    print(f"  Success: {len(result.success)}", file=sys.stderr)
    if result.skipped:
        print(f"  Skipped: {len(result.skipped)}", file=sys.stderr)
    if result.failed:
        print(f"  Failed: {len(result.failed)}", file=sys.stderr)
        for path, error in result.failed:
            _logger.debug("Batch file failed (full): %s — %s", path, error)
            print(f"    - {Path(path).name}: {_sanitize_error_message(error)}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    sys.exit(EXIT_SUCCESS)


def _handle_list_package_files(file_path: str, tolerant: bool) -> None:
    """列出发现的 package 文件。"""
    from uasset_read.package import open_package_bundle
    try:
        bundle = open_package_bundle(file_path, tolerant=tolerant)
    except Exception as e:
        _logger.debug("Package discovery error (full): %s", e, exc_info=True)
        print(f"Error: Package discovery failed: {_sanitize_error_message(e)}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)
    print(json.dumps({
        "package_kind": bundle.package_kind,
        "container": bundle.container,
        "files": bundle.package_files,
    }, indent=2, ensure_ascii=False))
    sys.exit(EXIT_SUCCESS)


def main():
    """Main CLI entry point."""
    parser = create_parser()

    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code == 0:
            sys.exit(EXIT_SUCCESS)
        sys.exit(EXIT_ARGUMENT_ERROR)

    # --list-formats
    if args.list_formats:
        formats = list_formats()
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
        print("Error: file argument is required", file=sys.stderr)
        sys.exit(EXIT_ARGUMENT_ERROR)

    file_path = Path(args.file)
    if not file_path.is_file():
        if file_path.is_dir():
            print(f"Error: Not a file: {args.file}", file=sys.stderr)
        else:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    fmt = resolve_format(args)
    tolerant = not args.strict

    # --list-package-files
    if args.list_package_files:
        _handle_list_package_files(args.file, tolerant)
        return

    try:
        output_str = parse_single(
            str(file_path),
            format=fmt,
            tolerant=tolerant,
            verbose=args.verbose,
            include_schema=args.schema or args.verbose,
            include_function_graphs=args.function_graphs,
            include_parent_assets=args.include_parent_assets,
            asset_roots=list(args.asset_root or []),
            mappings_path=args.mappings,
            game=args.game,
        )
    except ParseError as e:
        _logger.debug("Parse error (full): %s", e, exc_info=True)
        print(f"Error: {_sanitize_error_message(e)}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)
    except Exception as e:
        _logger.debug("Unexpected parse failure (full): %s", e, exc_info=True)
        print(f"Error: Unexpected parse failure: {_sanitize_error_message(e)}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    _write_output(output_str, args.output)
    sys.exit(EXIT_SUCCESS)
