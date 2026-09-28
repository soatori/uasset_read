"""CLI entry module — argparse parsing + output writing.

Single package in, one v4 package document out (modes: normal, debug).
Parsing is delegated to the package-document API; the CLI holds no parse
logic and no view/depth/selection/budget flags.
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

    # Output mode
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Emit the debug evidence block (default: normal)",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Write output to file instead of stdout",
    )

    # Parse controls (not output surfaces)
    parser.add_argument("--mappings", metavar="FILE", help="Load .usmap type mappings")
    parser.add_argument("--game", metavar="NAME", help="Enable game-specific property readers")
    parser.add_argument("--strict", action="store_true", help="Disable tolerant mode")

    return parser


def _write_stdout(output_str: str) -> None:
    """Print the projected document on stdout as UTF-8 JSON."""
    try:
        stdout = sys.stdout
        if hasattr(stdout, "reconfigure"):
            stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass
    print(output_str)


def _load_document(file_path: Path, args):
    """Parse one package in full at decode depth under the CLI parse flags."""
    from uasset_read.package import parse_package_document

    return parse_package_document(
        str(file_path),
        tolerant=not args.strict,
        mappings_path=args.mappings,
        game=args.game,
        depth="decode",
    )


def main():
    """Main CLI entry point."""
    parser = create_parser()

    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code == 0:
            sys.exit(EXIT_SUCCESS)
        sys.exit(EXIT_ARGUMENT_ERROR)

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

    from uasset_read.projection import project_document
    from uasset_read.projections.bundle import write_projected_document

    mode = "debug" if args.debug else "normal"
    try:
        doc = _load_document(file_path, args)
        if args.output:
            path = write_projected_document(doc, Path(args.output), mode=mode)
            print(f"Output written to {path}", file=sys.stderr)
        else:
            projected = project_document(doc, mode=mode)
            _write_stdout(json.dumps(projected, ensure_ascii=False, indent=2))
    except Exception as e:
        _logger.debug("Parse/project error (full): %s", e, exc_info=True)
        print(f"Error: {_sanitize_error_message(e)}", file=sys.stderr)
        sys.exit(EXIT_ARGUMENT_ERROR if isinstance(e, ValueError) else EXIT_PARSE_ERROR)
    sys.exit(EXIT_SUCCESS)
