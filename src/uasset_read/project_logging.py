from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from uuid import uuid4

_LOGGER_NAME = "uasset_read"
_HANDLER_MARKER = "_uasset_read_project_log_handler"
_state_lock = threading.Lock()
_configured_log_path: Path | None = None
_configured_run_id: str | None = None
_disabled_by_request = False


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def new_log_run_id() -> str:
    return uuid4().hex[:12]


def _build_log_path(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "uasset_read.log"


def _coerce_level(level: str | int | None) -> int:
    if level is None:
        return logging.DEBUG
    if isinstance(level, int):
        return level
    normalized = level.upper()
    if normalized == "OFF":
        return logging.CRITICAL + 1
    value = logging.getLevelName(normalized)
    if isinstance(value, int):
        return value
    raise ValueError(f"Unknown log level: {level}")


def _remove_project_handlers(package_logger: logging.Logger) -> None:
    for handler in list(package_logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            package_logger.removeHandler(handler)
            handler.close()


def configure_project_logging(
    project_root: str | Path | None = None,
    *,
    enabled: bool = True,
    level: str | int | None = "DEBUG",
    log_dir: str | Path | None = None,
    run_id: str | None = None,
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
    keep_latest: int | None = None,
    max_total_bytes: int | None = None,
    older_than_days: int | None = None,
    cleanup: bool = False,
) -> Path | None:
    """Configure a per-process file logger under <project>/log/."""
    global _configured_log_path
    global _configured_run_id
    global _disabled_by_request

    with _state_lock:
        package_logger = logging.getLogger(_LOGGER_NAME)
        if not enabled or (isinstance(level, str) and level.lower() == "off"):
            _remove_project_handlers(package_logger)
            package_logger.propagate = True
            _configured_log_path = None
            _configured_run_id = None
            _disabled_by_request = True
            return None

        default_request = (
            project_root is None
            and level == "DEBUG"
            and log_dir is None
            and run_id is None
            and max_bytes == 10_000_000
            and backup_count == 5
            and keep_latest is None
            and max_total_bytes is None
            and older_than_days is None
            and cleanup is False
        )
        if _disabled_by_request and default_request:
            return None
        _disabled_by_request = False

        if _configured_log_path is not None:
            return _configured_log_path

        root = Path(project_root) if project_root is not None else _default_project_root()
        root = root.resolve()
        resolved_log_dir = Path(log_dir).resolve() if log_dir is not None else root / "log"
        if cleanup:
            cleanup_project_logs(
                project_root=root,
                log_dir=resolved_log_dir,
                keep_latest=keep_latest,
                older_than_days=older_than_days,
                max_total_bytes=max_total_bytes,
                dry_run=False,
            )
        active_run_id = run_id or new_log_run_id()
        log_path = _build_log_path(resolved_log_dir)

        log_level = _coerce_level(level)
        package_logger.setLevel(min(logging.DEBUG, log_level))
        package_logger.propagate = False

        handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        setattr(handler, _HANDLER_MARKER, True)
        handler.setLevel(log_level)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        package_logger.addHandler(handler)

        _configured_log_path = log_path
        _configured_run_id = active_run_id
        package_logger.info("Project logging initialized: %s", log_path)
        for existing_handler in package_logger.handlers:
            existing_handler.flush()
        return log_path


def cleanup_project_logs(
    *,
    project_root: str | Path | None = None,
    log_dir: str | Path | None = None,
    keep_latest: int | None = None,
    older_than_days: int | None = None,
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

    files = sorted(
        resolved_log_dir.glob("uasset_read*.log*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    selected: set[Path] = set()

    if keep_latest is not None:
        if keep_latest < 0:
            raise ValueError("keep_latest must be >= 0")
        selected.update(files[keep_latest:])

    if older_than_days is not None:
        if older_than_days < 0:
            raise ValueError("older_than_days must be >= 0")
        cutoff = datetime.now() - timedelta(days=older_than_days)
        selected.update(
            path for path in files
            if datetime.fromtimestamp(path.stat().st_mtime) < cutoff
        )

    if max_total_bytes is not None:
        if max_total_bytes < 0:
            raise ValueError("max_total_bytes must be >= 0")
        remaining_total = sum(path.stat().st_size for path in files)
        for path in reversed(files):
            if remaining_total <= max_total_bytes:
                break
            selected.add(path)
            remaining_total -= path.stat().st_size

    planned = sorted(selected, key=lambda path: path.stat().st_mtime)
    if not dry_run:
        for path in planned:
            path.unlink(missing_ok=True)
    return planned


def _reset_logging_state_for_tests() -> None:
    """Remove only handlers installed by configure_project_logging()."""
    global _configured_log_path
    global _configured_run_id
    global _disabled_by_request

    with _state_lock:
        package_logger = logging.getLogger(_LOGGER_NAME)
        _remove_project_handlers(package_logger)
        package_logger.propagate = True
        _configured_log_path = None
        _configured_run_id = None
        _disabled_by_request = False


def setup_logging(
    *,
    log_dir: str | Path | None = None,
    level: str | int | None = "DEBUG",
    **kwargs,
) -> Path | None:
    """便捷日志配置入口，重置状态后调用 configure_project_logging。"""
    _reset_logging_state_for_tests()
    return configure_project_logging(log_dir=log_dir, level=level, **kwargs)
