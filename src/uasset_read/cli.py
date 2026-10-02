"""CLI entry module — argparse parsing + output writing.

Single package in, one v4 package document out (modes: normal, debug).
Parsing is delegated to the package-document API; the CLI holds no parse
logic and no view/depth/selection/budget flags.
"""

import json
import logging
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterator
from uuid import uuid4

# CLI exit codes — this module is their only consumer.
EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3

logger = logging.getLogger(__name__)


class _RunLogContext(logging.Filter):
    def __init__(self, run_id: str, asset_name: str) -> None:
        super().__init__()
        self.run_id = run_id
        self.asset_name = asset_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = self.run_id
        record.process_id = os.getpid()
        record.asset = self.asset_name
        record.stage = "parse"
        return True


@contextmanager
def _file_log_scope(asset_name: str) -> Iterator[None]:
    """Write this CLI invocation's DEBUG records to its own rotated file."""
    try:
        log_dir = Path(__file__).resolve().parents[2] / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        run_id = uuid4().hex[:12]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        log_path = log_dir / f"uasset_read-{timestamp}-pid{os.getpid()}-{run_id}.log"
        handler = RotatingFileHandler(
            log_path,
            maxBytes=10_000_000,
            backupCount=5,
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"Warning: could not write parser log file: {exc}", file=sys.stderr)
        yield
        return

    handler.setLevel(logging.DEBUG)
    handler.addFilter(_RunLogContext(run_id, asset_name))
    handler.setFormatter(
        logging.Formatter(
            fmt=(
                "%(asctime)s [%(levelname)s] "
                "[run=%(run_id)s pid=%(process_id)s asset=%(asset)s stage=%(stage)s] "
                "%(name)s: %(message)s"
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    package_logger = logging.getLogger("uasset_read")
    previous_level = package_logger.level
    package_logger.setLevel(logging.DEBUG)
    package_logger.addHandler(handler)
    try:
        logger.info("Project logging initialized: %s", log_path)
        yield
    finally:
        package_logger.removeHandler(handler)
        package_logger.setLevel(previous_level)
        handler.close()


def _sanitize_error_message(message: object) -> str:
    """Reduce filesystem-looking path tokens in a CLI error to basenames.

    Only tokens with a file extension are reduced — avoids mangling type or
    attribute paths such as ``/defs/PayloadDescriptor``. Full messages stay
    available with ``--verbose``.
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
    parser.add_argument("--verbose", action="store_true", help="Show detailed parser logs on stderr")
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


def _run(args) -> None:
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    # Validate positional arg
    if args.file is None:
        logger.debug("File argument is required")
        print("Error: file argument is required", file=sys.stderr)
        sys.exit(EXIT_ARGUMENT_ERROR)

    file_path = Path(args.file)
    if not file_path.is_file():
        if file_path.is_dir():
            logger.debug("Not a file: %s", file_path.name)
            print(f"Error: Not a file: {args.file}", file=sys.stderr)
        else:
            logger.debug("File not found: %s", file_path.name)
            print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    logger.debug("Parsing package: %s", file_path.name)
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
        logger.debug("Parse/project error (full): %s", e, exc_info=True)
        print(f"Error: {_sanitize_error_message(e)}", file=sys.stderr)
        sys.exit(EXIT_ARGUMENT_ERROR if isinstance(e, ValueError) else EXIT_PARSE_ERROR)
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

    asset_name = Path(args.file).name if args.file is not None else "-"
    with _file_log_scope(asset_name):
        _run(args)
