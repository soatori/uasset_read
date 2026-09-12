"""CLI entry module — argparse parsing + output writing.

Parsing is delegated to the v2 package-document API; the CLI holds no
parse logic and the v1 pipeline is no longer reachable from here.
"""

import json
import logging
import re
import sys
from pathlib import Path

# CLI exit codes — this module is their only consumer.
EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3

_logger = logging.getLogger(__name__)


def _sanitize_error_message(message: object) -> str:
    """Reduce path-like tokens in a CLI error to their basenames.

    Full messages stay available at DEBUG; the terminal only needs the
    offending filename, not the developer's directory layout.
    """
    return re.sub(
        r"(?:[A-Za-z]:)?(?:[/\\][^\s:;\"']+)+",
        lambda m: Path(m.group(0).rstrip("\\/")).name or m.group(0),
        str(message),
    )


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
    parser.add_argument("--mappings", metavar="FILE", help="Load .usmap type mappings")
    parser.add_argument("--game", metavar="NAME", help="Enable game-specific property readers")
    parser.add_argument("--strict", action="store_true", help="Disable tolerant mode")

    # Batch mode
    parser.add_argument(
        "--batch",
        nargs="?",
        const=".",
        default=None,
        metavar="DIR",
        help="Batch parse: process all .uasset files in DIR (default: current directory)",
    )
    parser.add_argument(
        "--batch-format",
        choices=["jsonl", "json"],
        default="jsonl",
        help="Batch output format: jsonl (one JSON per line, default) or json (array)",
    )

    # Utility flags
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


def _parse_and_project(file_path: Path, args) -> dict:
    """Parse one package and project it under the CLI's depth/limit/budget flags.

    Shared by single-file and batch modes so both stay in lockstep.
    """
    from uasset_read.package import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(
        str(file_path),
        tolerant=not args.strict,
        mappings_path=args.mappings,
        game=args.game,
        depth=args.depth,
    )
    return project_document(doc, depth=args.depth, limit=args.limit, max_bytes=args.max_bytes)


def _handle_batch(args) -> None:
    """Handle batch mode: parse all .uasset files in a directory."""
    batch_dir = Path(args.batch)
    if not batch_dir.is_dir():
        print(f"Error: Not a directory: {args.batch}", file=sys.stderr)
        sys.exit(EXIT_ARGUMENT_ERROR)

    # Collect all .uasset files
    uasset_files = sorted(batch_dir.rglob("*.uasset"))
    if not uasset_files:
        print(f"Error: No .uasset files found in {args.batch}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    results = []
    errors = []
    total = len(uasset_files)

    for i, file_path in enumerate(uasset_files, 1):
        print(f"[{i}/{total}] {file_path.name}", file=sys.stderr)
        try:
            projected = _parse_and_project(file_path, args)
            # Add source file info
            projected["_source_file"] = str(file_path)
            results.append(projected)
        except Exception as e:
            _logger.debug("Batch parse error for %s: %s", file_path, e, exc_info=True)
            error_entry = {
                "_source_file": str(file_path),
                "_error": True,
                "_error_message": _sanitize_error_message(e),
            }
            errors.append(error_entry)
            results.append(error_entry)

    # Output
    output = {
        "format": "uasset_read.batch",
        "format_version": "1.0",
        "total": total,
        "succeeded": total - len(errors),
        "failed": len(errors),
        "results": results,
    }
    if errors:
        output["errors"] = errors

    if args.batch_format == "jsonl":
        # JSONL: one JSON per line
        lines = []
        for r in results:
            lines.append(json.dumps(r, ensure_ascii=False, separators=(",", ":")))
        output_str = "\n".join(lines)
    else:
        # JSON array
        output_str = json.dumps(output, ensure_ascii=False, indent=2)

    _write_output(output_str, args.output)


def _handle_list_package_files(file_path: str) -> None:
    """List the discovered package files (main + present sidecars)."""
    from uasset_read.package import open_package_bundle

    try:
        bundle = open_package_bundle(file_path)
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
                "files": bundle.files,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    sys.exit(EXIT_SUCCESS)


def main():
    """Main CLI entry point."""
    parser = create_parser()

    # Retired product surfaces: one reason per group, exit 2 via parser.error
    # instead of argparse's generic unknown-argument error.
    retired = (
        (
            "parent-asset resolution is retired (product decision, Gate G 2026-09-10)",
            ("--include-parent-assets", "--asset-root"),
        ),
        (
            "log cleanup / file logging helpers are retired "
            "(product decision, Gate L 2026-09-10); delete leftover ./log directories yourself",
            ("--clean-logs", "--log-dir", "--log-keep-latest", "--log-max-total-mb"),
        ),
        (
            "part of the v1 pipeline; the v2 document output (--depth) is the only parse path",
            ("--legacy-json", "--markdown", "--list-formats", "--diff"),
        ),
    )
    for reason, flags in retired:
        hit = next((flag for flag in sys.argv if flag in flags), None)
        if hit is not None:
            parser.error(f"{hit} was removed: {reason}")

    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code == 0:
            sys.exit(EXIT_SUCCESS)
        sys.exit(EXIT_ARGUMENT_ERROR)

    # --batch mode
    if args.batch is not None:
        _handle_batch(args)
        sys.exit(EXIT_SUCCESS)

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

    # --list-package-files
    if args.list_package_files:
        _handle_list_package_files(args.file)
        return

    # PackageDocument v2 (the only parse path).
    try:
        projected = _parse_and_project(file_path, args)
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
