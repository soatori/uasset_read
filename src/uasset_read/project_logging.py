"""Log-file cleanup and the `log_context` scope helper.

Library code does not configure logging. Nothing in `src/` calls
`logging.config.dictConfig`, `fileConfig` or `basicConfig`; the package-document
(v2) path returns structured diagnostics instead. The process-global logging
configuration machinery (`configure_project_logging`, `shutdown_project_logging`,
`ProjectLogSession`, `project_logging_session`, `scoped_project_logging`,
`configure_worker_stream_logging`, `JSONFormatter`, `_LogContextFilter`,
`log_event`) was deleted as unreachable: its only callers disappeared with the
v1 pipeline, and no live import site remained.

What survives has exactly two consumers:

* `cleanup_project_logs` — the CLI's `--clean-logs` path (`cli.py`).
* `log_context` — scopes `asset`/`stage` onto records for callers that opt in.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_log_asset: ContextVar[str] = ContextVar("uasset_read_log_asset", default="-")
_log_stage: ContextVar[str] = ContextVar("uasset_read_log_stage", default="-")


@contextmanager
def log_context(*, asset: str | None = None, stage: str | None = None):
    """Attach asset and stage fields to records emitted in this context."""
    asset_token = _log_asset.set(asset or _log_asset.get())
    stage_token = _log_stage.set(stage or _log_stage.get())
    try:
        yield
    finally:
        _log_stage.reset(stage_token)
        _log_asset.reset(asset_token)


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def cleanup_project_logs(
    *,
    project_root: str | Path | None = None,
    log_dir: str | Path | None = None,
    keep_latest: int | None = None,
    max_total_bytes: int | None = None,
    dry_run: bool = True,
) -> list[Path]:
    """Plan or delete project log files explicitly.

    By default this is a dry run. Callers must pass ``dry_run=False`` to delete.
    """
    root = Path(project_root) if project_root is not None else _default_project_root()
    resolved_log_dir = Path(log_dir) if log_dir is not None else root / "log"
    if not resolved_log_dir.exists():
        return []

    files = list(resolved_log_dir.glob("uasset_read*.log*"))

    def family_base(path: Path) -> Path:
        # RotatingFileHandler appends .1, .2, … to the base log filename.
        # Stripping that numeric suffix groups all backups of the same run
        # into one "family" so they can be kept or deleted as a unit.
        name = path.name
        base, separator, suffix = name.rpartition(".")
        if separator and suffix.isdigit() and base.endswith(".log"):
            return path.with_name(base)
        return path

    families: dict[Path, list[Path]] = {}
    for path in files:
        families.setdefault(family_base(path), []).append(path)
    ordered_families = sorted(
        families,
        key=lambda base: max(path.stat().st_mtime for path in families[base]),
        reverse=True,
    )
    selected_families: set[Path] = set()

    if keep_latest is not None:
        if keep_latest < 0:
            raise ValueError("keep_latest must be >= 0")
        effective_keep_latest = max(1, keep_latest)
        selected_families.update(family for family in ordered_families[effective_keep_latest:])

    if max_total_bytes is not None:
        if max_total_bytes < 0:
            raise ValueError("max_total_bytes must be >= 0")
        remaining_total = sum(path.stat().st_size for path in files)
        remaining_total -= sum(path.stat().st_size for family in selected_families for path in families[family])
        newest_family = ordered_families[0] if ordered_families else None
        for family in reversed(ordered_families):
            if remaining_total <= max_total_bytes:
                break
            if family in selected_families or family == newest_family:
                continue
            selected_families.add(family)
            remaining_total -= sum(path.stat().st_size for path in families[family])

    planned = sorted(
        (path for family in selected_families for path in families[family]),
        key=lambda path: path.stat().st_mtime,
    )
    if not dry_run:
        for path in planned:
            path.unlink(missing_ok=True)
    return planned
