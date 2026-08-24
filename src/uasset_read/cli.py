"""CLI 入口模块 — argparse 参数解析 + 委托 core 模块。

核心逻辑与入口分离：core 模块提供纯解析函数，CLI 仅负责参数解析和输出写入。
"""

import json
import logging
import re
import sys
from pathlib import Path

from uasset_read.config import LogConfig
from uasset_read.core import parse_single, parse_batch, list_formats, ParseError
from uasset_read.project_logging import cleanup_project_logs
from uasset_read.constants import (
    EXIT_SUCCESS,
    EXIT_PARSE_ERROR,
    EXIT_FILE_NOT_FOUND,
    EXIT_ARGUMENT_ERROR,
)

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
        "uasset",
        "umap",
        "uexp",
        "ubulk",
        "uptnl",
        "pak",
        "json",
        "txt",
        "bin",
        "dat",
        "log",
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


def create_parser():
    """Create argparse parser for CLI."""
    import argparse
    from uasset_read import __version__

    parser = argparse.ArgumentParser(
        prog="uasset_read",
        description="Parse Unreal Engine .uasset/.umap files and output structured data",
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Path to .uasset/.umap file to parse (or directory in --batch mode)",
    )

    # Mutually exclusive output flags
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "--json", action="store_true", help="Output full JSON structure (default)"
    )
    group.add_argument("--markdown", action="store_true", help="Output Markdown format")

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
    parser.add_argument('--full-parse', action='store_true', default=False,
                        help='Force full parse for large blueprints (skip lightweight mode)')
    parser.add_argument('--hex-view', action='store_true', default=False,
                        help='Enable HexView byte offset tracking (debug)')
    parser.add_argument('--output-level', choices=['standard', 'debug'], default='standard',
                        help='Output level: standard (default, filters UI properties) or debug (full output)')
    parser.add_argument('--log-level', choices=['debug', 'info', 'warning', 'error', 'off'], default=None,
                        help='File log level: debug, info, warning, error, or off')
    parser.add_argument('--log-dir', metavar='DIR', help='Write project logs to DIR instead of ./log')
    parser.add_argument('--log-cleanup', action=argparse.BooleanOptionalAction, default=True,
                        help='Clean old run logs automatically (default: enabled)')
    parser.add_argument('--log-keep-latest', metavar='N', type=int,
                        help='When cleanup is enabled, keep only the newest N complete runs')
    parser.add_argument('--log-max-total-mb', metavar='MB', type=int,
                        help='When --log-cleanup is set, cap total log storage to MB megabytes')
    parser.add_argument('--log-max-bytes', metavar='BYTES', type=int, default=10_000_000,
                        help='Max size per log file in bytes (default: 10MB)')
    parser.add_argument('--log-backup-count', metavar='N', type=int, default=5,
                        help='Number of backup log files to keep (default: 5)')
    parser.add_argument('--log-repeat-limit', metavar='N', type=int, default=5,
                        help='Keep the first N repeated DEBUG messages (0 disables aggregation)')
    parser.add_argument('--log-format', choices=['text', 'json'], default='text',
                        help='Log output format: text (default) or json')

    # Batch and utility flags
    parser.add_argument(
        "--list-formats", action="store_true", help="List all available export formats"
    )
    parser.add_argument(
        "--clean-logs",
        action="store_true",
        help="Dry-run log cleanup plan and exit; never deletes files",
    )
    parser.add_argument("--batch", action="store_true", help="Enable batch mode")
    parser.add_argument(
        "--batch-dir", metavar="DIR", help="Output directory for batch mode"
    )
    parser.add_argument(
        "--list-package-files",
        action="store_true",
        help="List discovered package files",
    )
    parser.add_argument(
        "--diff",
        metavar="FILE2",
        nargs="?",
        const=True,
        default=None,
        help="Diff FILE against FILE2 (JSON comparison)",
    )
    parser.add_argument(
        "--diff-context",
        metavar="N",
        type=int,
        default=3,
        help="Number of context lines around changes in diff (default: 3)",
    )

    return parser


def resolve_format(args) -> str:
    """从 CLI 参数解析导出格式名。"""
    if args.markdown:
        return "markdown"
    if args.json:
        return "json"
    return "json"


def _write_output(output_str: str, output_path: str | None) -> None:
    """Unified output writer."""
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(output_str)
            print(f"Output written to {output_path}", file=sys.stderr)
        except IOError as e:
            _logger.debug("File write error (full): %s", e, exc_info=True)
            print(
                f"Error writing to file: {_sanitize_error_message(e)}", file=sys.stderr
            )
            sys.exit(EXIT_ARGUMENT_ERROR)
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
        print(output_str)


def _log_enabled_from_args(args) -> bool:
    return args.log_level != "off"


def _log_max_total_bytes_from_args(args) -> int | None:
    if args.log_max_total_mb is None:
        return None
    return args.log_max_total_mb * 1_000_000


def _log_config_from_args(args) -> LogConfig:
    level = args.log_level or "debug"
    keep_latest = args.log_keep_latest if args.log_keep_latest is not None else 20
    max_total_bytes = _log_max_total_bytes_from_args(args)
    if max_total_bytes is None:
        max_total_bytes = 500 * 1024 * 1024
    return LogConfig(
        level=level,
        dir=args.log_dir,
        enabled=level != "off",
        keep_latest=keep_latest,
        max_total_bytes=max_total_bytes,
        auto_cleanup=args.log_cleanup,
        max_bytes=args.log_max_bytes,
        backup_count=args.log_backup_count,
        repeat_limit=args.log_repeat_limit,
        format=args.log_format,
    )


def _handle_batch(args) -> None:
    """处理批量导出模式。"""
    import time

    input_dir = Path(args.file)
    if not input_dir.is_dir():
        print(f"Error: Not a directory: {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    output_dir = args.batch_dir or str(input_dir / "output")
    start_time = time.monotonic()

    try:
        result = parse_batch(
            str(input_dir),
            format=resolve_format(args),
            output_dir=output_dir,
            tolerant=not args.strict,
            verbose=args.verbose,
            include_schema=args.schema or args.verbose,

            include_parent_assets=args.include_parent_assets,
            asset_roots=list(args.asset_root or []),
            mappings_path=args.mappings,
            game=args.game,
            force_full_parse=args.full_parse,
            log_config=_log_config_from_args(args),
        )
    except Exception as e:
        _logger.debug("Batch export error (full): %s", e, exc_info=True)
        print(f"Error: {_sanitize_error_message(e)}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    elapsed = time.monotonic() - start_time
    print(
        f"Batch export complete: {result.total} files in {elapsed:.1f}s",
        file=sys.stderr,
    )
    print(f"  Success: {len(result.success)}", file=sys.stderr)
    if result.partial:
        print(f"  Partial: {len(result.partial)}", file=sys.stderr)
        if result.partial_reasons:
            for reason, files in result.partial_reasons.items():
                print(
                    f"    {reason.replace('_', ' ').title()}: {len(files)}",
                    file=sys.stderr,
                )
    if result.skipped:
        print(f"  Skipped: {len(result.skipped)}", file=sys.stderr)
    if result.failed:
        print(f"  Failed: {len(result.failed)}", file=sys.stderr)
        for path, error, details in result.failed:
            _logger.debug("Batch file failed (full): %s — %s\n%s", path, error, details)
            print(
                f"    - {Path(path).name}: {_sanitize_error_message(error)}",
                file=sys.stderr,
            )
        sys.exit(EXIT_PARSE_ERROR)

    sys.exit(EXIT_SUCCESS)


def _handle_clean_logs(args) -> None:
    config = _log_config_from_args(args)
    planned = cleanup_project_logs(
        log_dir=args.log_dir,
        keep_latest=config.keep_latest,
        max_total_bytes=config.max_total_bytes,
        dry_run=True,
    )
    print(f"Would delete {len(planned)} log file(s)")
    for path in planned:
        print(str(path))
    sys.exit(EXIT_SUCCESS)


def _handle_list_package_files(file_path: str, tolerant: bool) -> None:
    """列出发现的 package 文件。"""
    from uasset_read.package import open_package_bundle

    try:
        bundle = open_package_bundle(file_path, tolerant=tolerant)
    except Exception as e:
        _logger.debug("Package discovery error (full): %s", e, exc_info=True)
        print(
            f"Error: Package discovery failed: {_sanitize_error_message(e)}",
            file=sys.stderr,
        )
        sys.exit(EXIT_PARSE_ERROR)
    print(
        json.dumps(
            {
                "package_kind": bundle.package_kind,
                "container": bundle.container,
                "files": bundle.package_files,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
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

    if args.clean_logs:
        _handle_clean_logs(args)

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

    # --diff 模式
    if args.diff is not None:
        from uasset_read.core import diff_single

        if args.diff is True:
            print("Error: --diff requires a second file path", file=sys.stderr)
            sys.exit(EXIT_ARGUMENT_ERROR)
        file2 = Path(args.diff)
        if not file2.is_file():
            print(f"Error: Diff file not found: {args.diff}", file=sys.stderr)
            sys.exit(EXIT_FILE_NOT_FOUND)
        try:
            diff_output = diff_single(
                str(file_path),
                str(file2),
                tolerant=tolerant,
                context_lines=args.diff_context,
                log_config=_log_config_from_args(args),
            )
        except Exception as e:
            _logger.debug("Diff failed (full): %s", e, exc_info=True)
            print(f"Error: Diff failed: {_sanitize_error_message(e)}", file=sys.stderr)
            sys.exit(EXIT_PARSE_ERROR)
        _write_output(diff_output, args.output)
        return

    try:
        output_str = parse_single(
            str(file_path),
            format=fmt,
            tolerant=tolerant,
            verbose=args.verbose,
            include_schema=args.schema or args.verbose,

            include_parent_assets=args.include_parent_assets,
            asset_roots=list(args.asset_root or []),
            mappings_path=args.mappings,
            game=args.game,
            force_full_parse=args.full_parse,
            hex_view=args.hex_view,
            output_level=args.output_level,
            log_config=_log_config_from_args(args),
        )
    except ParseError as e:
        _logger.debug("Parse error (full): %s", e, exc_info=True)
        print(f"Error: {_sanitize_error_message(e)}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)
    except Exception as e:
        _logger.debug("Unexpected parse failure (full): %s", e, exc_info=True)
        print(
            f"Error: Unexpected parse failure: {_sanitize_error_message(e)}",
            file=sys.stderr,
        )
        sys.exit(EXIT_PARSE_ERROR)

    _write_output(output_str, args.output)
    sys.exit(EXIT_SUCCESS)
