"""CLI entry module — argparse parsing + output writing.

Parsing is delegated to the v2 package-document API; the CLI holds no
parse logic and the v1 pipeline is no longer reachable from here.
"""

import json
import logging
import re
import sys
from pathlib import Path

from uasset_read.config import LogConfig
from uasset_read.project_logging import cleanup_project_logs
from uasset_read.constants import (
    EXIT_SUCCESS,
    EXIT_PARSE_ERROR,
    EXIT_FILE_NOT_FOUND,
    EXIT_ARGUMENT_ERROR,
)

_logger = logging.getLogger(__name__)


def _sanitize_error_message(message: object) -> str:
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

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Path to .uasset/.umap file to parse",
    )

    # v2 projection controls
    parser.add_argument(
        "--depth",
        choices=["package", "object", "asset", "decode"],
        default="asset",
        help="Projection depth: package (headers only), object (properties), asset (semantic), decode (full)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of objects to include in output",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=None,
        help="Maximum output size in bytes (truncates objects to fit)",
    )

    # Optional flags
    parser.add_argument("--output", metavar="FILE", help="Write output to file instead of stdout")
    parser.add_argument("--mappings", metavar="FILE", help="Load .usmap/.jmap type mappings")
    parser.add_argument("--game", metavar="NAME", help="Enable game-specific property readers")
    parser.add_argument("--tolerant", action="store_true", default=True, help="Enable tolerant mode (default)")
    parser.add_argument("--strict", action="store_true", help="Disable tolerant mode")
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "off"],
        default=None,
        help="File log level: debug, info, warning, error, or off",
    )
    parser.add_argument("--log-dir", metavar="DIR", help="Write project logs to DIR instead of ./log")
    parser.add_argument(
        "--log-cleanup",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Clean old run logs automatically (default: enabled)",
    )
    parser.add_argument(
        "--log-keep-latest", metavar="N", type=int, help="When cleanup is enabled, keep only the newest N complete runs"
    )
    parser.add_argument(
        "--log-max-total-mb",
        metavar="MB",
        type=int,
        help="When --log-cleanup is set, cap total log storage to MB megabytes",
    )
    parser.add_argument(
        "--log-max-bytes",
        metavar="BYTES",
        type=int,
        default=10_000_000,
        help="Max size per log file in bytes (default: 10MB)",
    )
    parser.add_argument(
        "--log-backup-count", metavar="N", type=int, default=5, help="Number of backup log files to keep (default: 5)"
    )
    parser.add_argument(
        "--log-format", choices=["text", "json"], default="text", help="Log output format: text (default) or json"
    )

    # Utility flags
    parser.add_argument(
        "--clean-logs",
        action="store_true",
        help="Dry-run log cleanup plan and exit; never deletes files",
    )
    parser.add_argument(
        "--list-package-files",
        action="store_true",
        help="List discovered package files",
    )

    return parser


def _write_output(output_str: str, output_path: str | None) -> None:
    """Unified output writer."""
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(output_str)
            print(f"Output written to {output_path}", file=sys.stderr)
        except IOError as e:
            _logger.debug("File write error (full): %s", e, exc_info=True)
            print(f"Error writing to file: {_sanitize_error_message(e)}", file=sys.stderr)
            sys.exit(EXIT_ARGUMENT_ERROR)
    else:
        try:
            stdout = sys.stdout
            if hasattr(stdout, "reconfigure"):
                stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pass
        print(output_str)


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
        format=args.log_format,
    )


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

    # v1 pipeline removal: retired flags get an explicit unsupported message
    # instead of argparse's generic unrecognized-argument error (Gate B).
    retired = {"--legacy-json", "--markdown", "--list-formats", "--diff", "--batch"}
    hit = next((flag for flag in sys.argv if flag in retired), None)
    if hit is not None:
        parser.error(
            f"{hit} was removed together with the v1 pipeline; the v2 document output (--depth) is the only parse path"
        )

    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code == 0:
            sys.exit(EXIT_SUCCESS)
        sys.exit(EXIT_ARGUMENT_ERROR)

    if args.clean_logs:
        _handle_clean_logs(args)

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

    tolerant = not args.strict

    # --list-package-files
    if args.list_package_files:
        _handle_list_package_files(args.file, tolerant)
        return

    # PackageDocument v2 (the only parse path).
    try:
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.projection import project_document

        doc = parse_package_document(
            str(file_path),
            tolerant=tolerant,
            mappings_path=args.mappings,
            game=args.game,
            depth=args.depth,
        )
        projected = project_document(
            doc,
            depth=args.depth,
            limit=args.limit,
            max_bytes=args.max_bytes,
        )
        # Budget mode must serialize exactly like projection's byte measure
        # (compact separators); otherwise indent inflation breaks the cap.
        if args.max_bytes is None:
            output_str = json.dumps(projected, ensure_ascii=False, indent=2)
        else:
            output_str = json.dumps(projected, ensure_ascii=False, separators=(",", ":"))
    except Exception as e:
        _logger.debug("V2 parse error (full): %s", e, exc_info=True)
        print(f"Error: {_sanitize_error_message(e)}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    _write_output(output_str, args.output)
    sys.exit(EXIT_SUCCESS)
