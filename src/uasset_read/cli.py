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
    """Reduce filesystem-looking path tokens in a CLI error to basenames.

    Only tokens with a file extension are reduced — avoids mangling type or
    attribute paths such as ``/defs/PayloadDescriptor``. Full messages stay
    available at DEBUG.
    """
    return re.sub(
        r"(?:(?:[A-Za-z]:)?(?:[/\\][^\s:;\"']+)+|(?:[^\s:;\"'\\/]+[/\\])+[^\s:;\"'\\/]+)\.[A-Za-z0-9_]{1,16}\b",
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
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Write output to file instead of stdout",
    )
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

    Shared by the stdout single-file path and any bounded query response.
    Canonical file/batch materialization uses write_projected_document /
    build_canonical_document instead.
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


def _reject_bounded_flags_for_canonical(args, *, context: str) -> None:
    """Canonical output never paginates; --limit is a usage error with it."""
    if args.limit is not None:
        print(
            f"Error: --limit cannot be combined with {context} "
            f"(canonical v3 documents are never paginated)",
            file=sys.stderr,
        )
        sys.exit(EXIT_ARGUMENT_ERROR)


def _parse_and_write_canonical(file_path: Path, args, output_path: Path) -> Path:
    """Parse one package and write the complete format_version 3.0 canonical file."""
    from uasset_read.package import parse_package_document
    from uasset_read.projections.bundle import write_projected_document

    doc = parse_package_document(
        str(file_path),
        tolerant=not args.strict,
        mappings_path=args.mappings,
        game=args.game,
        depth=args.depth,
    )
    return write_projected_document(doc, output_path, max_main_bytes=args.max_bytes)


def _build_canonical_result(file_path: Path, args) -> dict:
    """Parse one package and return its complete v3 canonical document dict."""
    from uasset_read.package import parse_package_document
    from uasset_read.projections.bundle import build_canonical_document

    doc = parse_package_document(
        str(file_path),
        tolerant=not args.strict,
        mappings_path=args.mappings,
        game=args.game,
        depth=args.depth,
    )
    return build_canonical_document(doc)


def _iter_batch_packages(batch_dir: Path) -> list[Path]:
    """Discover package files for batch mode: sorted ``*.uasset`` and ``*.umap``."""
    files = list(batch_dir.rglob("*.uasset")) + list(batch_dir.rglob("*.umap"))
    return sorted(files)


def _handle_batch(args) -> None:
    """Handle batch mode: parse all .uasset/.umap files in a directory.

    The batch envelope stays ``uasset_read.batch`` / ``1.0``; each successful
    ``results[]`` entry is a complete v3 canonical document.
    """
    _reject_bounded_flags_for_canonical(args, context="--batch")
    batch_dir = Path(args.batch)
    if not batch_dir.is_dir():
        print(f"Error: Not a directory: {args.batch}", file=sys.stderr)
        sys.exit(EXIT_ARGUMENT_ERROR)

    # Collect all .uasset and .umap files
    uasset_files = _iter_batch_packages(batch_dir)
    if not uasset_files:
        print(f"Error: No .uasset/.umap files found in {args.batch}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    results = []
    errors = []
    total = len(uasset_files)

    for i, file_path in enumerate(uasset_files, 1):
        print(f"[{i}/{total}] {file_path.name}", file=sys.stderr)
        try:
            projected = _build_canonical_result(file_path, args)
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

    # Canonical file path: one complete format_version 3.0 document.
    # Never paginated; --limit/--offset/object selection are usage errors.
    if args.output:
        _reject_bounded_flags_for_canonical(args, context="-o/--output")
        try:
            path = _parse_and_write_canonical(file_path, args, Path(args.output))
            print(f"Output written to {path}", file=sys.stderr)
        except Exception as e:
            _logger.debug("Canonical write error (full): %s", e, exc_info=True)
            print(f"Error: {_sanitize_error_message(e)}", file=sys.stderr)
            # OutputBudgetError is a ValueError: the requested budget cannot
            # fit the mandatory envelope — a usage problem, not a parse failure.
            sys.exit(EXIT_ARGUMENT_ERROR if isinstance(e, ValueError) else EXIT_PARSE_ERROR)
        sys.exit(EXIT_SUCCESS)

    # Stdout/query path: bounded project_document() projection.
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
