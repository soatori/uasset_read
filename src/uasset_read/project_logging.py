from __future__ import annotations

import logging
import os
import sys
import threading
import inspect
import time as _time
from functools import wraps
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from uuid import uuid4
import json as _json

_LOGGER_NAME = "uasset_read"
_HANDLER_MARKER = "_uasset_read_project_log_handler"
_WORKER_HANDLER_MARKER = "_uasset_read_worker_log_handler"
_state_lock = threading.Lock()
_scope_lock = threading.Lock()
_configured_log_path: Path | None = None
_configured_run_id: str | None = None
_configured_signature: tuple | None = None
_disabled_by_request = False
_original_level: int | None = None
_original_propagate: bool | None = None
_log_asset: ContextVar[str] = ContextVar("uasset_read_log_asset", default="-")
_log_stage: ContextVar[str] = ContextVar("uasset_read_log_stage", default="-")


class _LogContextFilter(logging.Filter):
    def __init__(self, run_id: str) -> None:
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = self.run_id
        record.process_id = record.process
        record.asset = _log_asset.get()
        record.stage = _log_stage.get()
        return True


class _RepeatedDebugFilter(logging.Filter):
    def __init__(
        self, repeat_limit: int, suppress_levels: set[int] | None = None
    ) -> None:
        super().__init__()
        self.limit = repeat_limit
        self.repeat_limit = repeat_limit
        self.counts: dict[tuple[str, str, str], int] = {}
        self.message_counts: dict[str, int] = {}
        self.suppressed_count: int = 0
        self.suppress_levels = suppress_levels or {logging.DEBUG}

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if msg not in self.message_counts:
            self.message_counts[msg] = 0
        self.message_counts[msg] += 1
        # 按 suppress_levels 抑制重复消息，按原始模板分组
        if self.limit <= 0 or record.levelno not in self.suppress_levels:
            return True
        key = (_log_asset.get(), record.name, str(record.msg))
        count = self.counts.get(key, 0) + 1
        self.counts[key] = count
        if count > self.limit:
            self.suppressed_count += 1
            return False
        return True

    def summaries(self) -> list[tuple[str, str, str, int]]:
        return [
            (asset, logger_name, template, count - self.limit)
            for (asset, logger_name, template), count in self.counts.items()
            if count > self.limit
        ]

    def get_summary(self) -> str:
        if not self.suppressed_count:
            return ""
        summary_parts = []
        for msg, count in self.message_counts.items():
            if count > self.repeat_limit:
                summary_parts.append(
                    f"{msg} (suppressed {count - self.repeat_limit} times)"
                )
        return "Repeated warnings: " + "; ".join(summary_parts)


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects.

    Output format::

        {"ts":"2026-08-21T10:00:00","level":"INFO","run":"abc123",
         "pid":1234,"asset":"BP_Player","stage":"link",
         "logger":"uasset_read","msg":"event=parse_start"}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "run": getattr(record, "run_id", "-"),
            "pid": getattr(record, "process_id", record.process),
            "asset": getattr(record, "asset", "-"),
            "stage": getattr(record, "stage", "-"),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exc"] = self.formatException(record.exc_info)
        return _json.dumps(log_entry, ensure_ascii=False, default=str)


class SamplingFilter(logging.Filter):
    """Drop a fraction of DEBUG records to reduce log volume.

    ``rate`` is the keep probability (0.0 = drop all, 1.0 = keep all).
    Only applies to records at or below ``sample_level`` (default DEBUG).

    Uses a deterministic hash (sum of char ordinals) so that the same
    message is always sampled the same way across processes.
    """

    def __init__(self, rate: float = 1.0, sample_level: int = logging.DEBUG):
        super().__init__()
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"rate must be 0.0-1.0, got {rate}")
        self.rate = rate
        self.sample_level = sample_level

    @staticmethod
    def _stable_hash(msg: str) -> int:
        """Deterministic hash — not affected by PYTHONHASHSEED.

        Uses FNV-1a for uniform distribution across similar strings.
        """
        h = 0x811C9DC5  # FNV offset basis
        for c in msg:
            h ^= ord(c)
            h = (h * 0x01000193) & 0xFFFFFFFF  # FNV prime
        return h % 1000

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno > self.sample_level:
            return True
        if self.rate >= 1.0:
            return True
        if self.rate <= 0.0:
            return False
        return self._stable_hash(record.msg) < int(self.rate * 1000)


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


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit a structured log event with key-value fields.

    Fields are appended to the message as ``key=value`` pairs, sorted
    alphabetically.  The ``event`` keyword is always first.

    Example::

        log_event(logger, logging.INFO, "parse_start",
                  asset="BP_Player", stage="link")

    Emits::

        2026-08-21 10:00:00 [INFO] [run=abc123 pid=1234 asset=BP_Player stage=link]
        uasset_read: event=parse_start
    """
    if not fields:
        logger.log(level, "event=%s", event)
        return
    sorted_fields = sorted(fields.items())
    field_str = " ".join(f"{k}={v}" for k, v in sorted_fields)
    logger.log(level, "event=%s %s", event, field_str)


def log_stage_timing(
    logger: logging.Logger,
    stage_name: str,
    asset: str | None = None,
):
    """Return an object usable as both decorator and context manager.

    Usage as context manager::

        with log_stage_timing(logger, "preload", asset="BP_Player"):
            do_work()

    Usage as decorator::

        @log_stage_timing(logger, "link")
        def link(self): ...
    """

    class _TimingContext:
        def __init__(self):
            self._start: float = 0.0

        def __enter__(self):
            if asset is not None:
                _log_asset.set(asset)
            _log_stage.set(stage_name)
            self._start = _time.monotonic()
            logger.debug("stage_start stage=%s", stage_name)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            elapsed_ms = (_time.monotonic() - self._start) * 1000
            status = "error" if exc_type else "success"
            logger.debug(
                "stage_end stage=%s status=%s duration_ms=%.1f",
                stage_name,
                status,
                elapsed_ms,
            )
            return False

        def __call__(self, func):
            """Allow use as a decorator."""
            ctx = self

            @wraps(func)
            def wrapper(*args, **kwargs):
                with ctx:
                    return func(*args, **kwargs)

            return wrapper

    return _TimingContext()


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def new_log_run_id() -> str:
    return uuid4().hex[:12]


def _build_log_path(log_dir: Path, run_id: str) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_run_id = "".join(
        char if char.isalnum() or char in "-_" else "_" for char in run_id
    )
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return log_dir / f"uasset_read-{timestamp}-pid{os.getpid()}-{safe_run_id}.log"


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


def _shutdown_locked(package_logger: logging.Logger) -> None:
    global _configured_log_path
    global _configured_run_id
    global _configured_signature
    global _original_level
    global _original_propagate

    for handler in list(package_logger.handlers):
        if not getattr(handler, _HANDLER_MARKER, False):
            continue
        for installed_filter in handler.filters:
            if isinstance(installed_filter, _RepeatedDebugFilter):
                for (
                    asset,
                    logger_name,
                    template,
                    suppressed,
                ) in installed_filter.summaries():
                    with log_context(asset=asset):
                        package_logger.info(
                            "Repeated message summary logger=%s template=%s suppressed=%d",
                            logger_name,
                            template,
                            suppressed,
                        )
        handler.flush()
    _remove_project_handlers(package_logger)
    if _original_level is not None:
        package_logger.setLevel(_original_level)
    if _original_propagate is not None:
        package_logger.propagate = _original_propagate
    _configured_log_path = None
    _configured_run_id = None
    _configured_signature = None
    _original_level = None
    _original_propagate = None


def shutdown_project_logging() -> None:
    """Flush and remove handlers owned by the current project log session."""
    with _state_lock:
        _shutdown_locked(logging.getLogger(_LOGGER_NAME))


@dataclass
class ProjectLogSession:
    """A scoped owner for one project log file."""

    log_path: Path
    run_id: str
    cleanup_on_close: bool = False
    keep_latest: int | None = None
    max_total_bytes: int | None = None
    older_than_days: int | None = None
    _started_at: float = field(default_factory=_time.monotonic)
    _owns_scope_lock: bool = False
    _closed: bool = False

    def __enter__(self) -> "ProjectLogSession":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            try:
                duration_ms = (_time.monotonic() - self._started_at) * 1000
                logging.getLogger(_LOGGER_NAME).info(
                    "session_end run_id=%s duration_ms=%.1f",
                    self.run_id,
                    duration_ms,
                )
                shutdown_project_logging()
                self._closed = True
                if self.cleanup_on_close:
                    cleanup_project_logs(
                        log_dir=self.log_path.parent,
                        keep_latest=self.keep_latest,
                        max_total_bytes=self.max_total_bytes,
                        older_than_days=self.older_than_days,
                        dry_run=False,
                    )
            finally:
                if self._owns_scope_lock:
                    self._owns_scope_lock = False
                    _scope_lock.release()


class _DisabledLogSession:
    """无操作日志会话 — 日志禁用时的占位实现。"""

    _owns_scope_lock: bool = False
    _closed: bool = False

    def __enter__(self) -> "_DisabledLogSession":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            if self._owns_scope_lock:
                self._owns_scope_lock = False
                _scope_lock.release()


def project_logging_session(**kwargs) -> ProjectLogSession | _DisabledLogSession:
    """Configure and return a scoped project logging session."""
    if not _scope_lock.acquire(blocking=False):
        raise RuntimeError("A project logging session is already active")
    cleanup_on_close = bool(kwargs.pop("cleanup_on_close", False))
    keep_latest = kwargs.get("keep_latest")
    max_total_bytes = kwargs.get("max_total_bytes")
    older_than_days = kwargs.get("older_than_days")
    try:
        log_path = configure_project_logging(**kwargs)
    except BaseException:
        _scope_lock.release()
        raise
    if log_path is None or _configured_run_id is None:
        session = _DisabledLogSession()
        session._owns_scope_lock = True
        return session
    logging.getLogger(_LOGGER_NAME).info("session_start run_id=%s", _configured_run_id)
    return ProjectLogSession(
        log_path=log_path,
        run_id=_configured_run_id,
        cleanup_on_close=cleanup_on_close,
        keep_latest=keep_latest,
        max_total_bytes=max_total_bytes,
        older_than_days=older_than_days,
        _owns_scope_lock=True,
    )


def current_log_run_id() -> str | None:
    return _configured_run_id


def scoped_project_logging(func):
    """Scope an explicit ``log_config`` argument to one public API call."""
    signature = inspect.signature(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        bound = signature.bind_partial(*args, **kwargs)
        config = bound.arguments.get("log_config")
        if config is None:
            return func(*args, **kwargs)
        bound.arguments["log_config"] = None
        path_value = (
            bound.arguments.get("file_path")
            or bound.arguments.get("path")
            or bound.arguments.get("input_dir")
        )
        asset = Path(path_value).name if path_value else "-"
        with project_logging_session(**config.to_configure_kwargs()):
            stage = "batch" if func.__name__ == "parse_batch" else "parse"
            with log_context(asset=asset, stage=stage):
                started_at = _time.monotonic()
                status = "success"
                logging.getLogger(_LOGGER_NAME).info("asset_start")
                try:
                    return func(*bound.args, **bound.kwargs)
                except BaseException:
                    status = "error"
                    raise
                finally:
                    duration_ms = (_time.monotonic() - started_at) * 1000
                    logging.getLogger(_LOGGER_NAME).info(
                        "asset_end status=%s duration_ms=%.1f",
                        status,
                        duration_ms,
                    )

    return wrapper


def configure_worker_stream_logging(
    *,
    stream=None,
    level: str | int | None = "DEBUG",
    run_id: str,
    asset: str,
) -> logging.Handler:
    """Send worker diagnostics to the parent-owned stderr pipe."""
    package_logger = logging.getLogger(_LOGGER_NAME)
    for existing in list(package_logger.handlers):
        if getattr(existing, _WORKER_HANDLER_MARKER, False):
            package_logger.removeHandler(existing)
            existing.close()
    handler = logging.StreamHandler(stream or sys.stderr)
    setattr(handler, _WORKER_HANDLER_MARKER, True)
    handler.setLevel(_coerce_level(level))
    handler.setFormatter(
        logging.Formatter(
            fmt=(
                f"%(asctime)s [%(levelname)s] [run={run_id} pid={os.getpid()} "
                f"asset={asset} stage=worker] %(name)s: %(message)s"
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    package_logger.setLevel(logging.DEBUG)
    package_logger.propagate = False
    package_logger.addHandler(handler)
    return handler


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
    repeat_limit: int = 5,
    cleanup_on_close: bool = False,
    format: str = "text",
    sample_rate: float = 1.0,
) -> Path | None:
    """Configure a per-process file logger under <project>/log/."""
    global _configured_log_path
    global _configured_run_id
    global _configured_signature
    global _disabled_by_request
    global _original_level
    global _original_propagate

    with _state_lock:
        package_logger = logging.getLogger(_LOGGER_NAME)
        if not enabled or (isinstance(level, str) and level.lower() == "off"):
            _shutdown_locked(package_logger)
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
            and repeat_limit == 5
            and cleanup_on_close is False
            and format == "text"
            and sample_rate == 1.0
        )
        if _disabled_by_request and default_request:
            return None
        _disabled_by_request = False

        root = (
            Path(project_root) if project_root is not None else _default_project_root()
        )
        root = root.resolve()
        resolved_log_dir = (
            Path(log_dir).resolve() if log_dir is not None else root / "log"
        )
        log_level = _coerce_level(level)
        signature = (
            root,
            resolved_log_dir,
            log_level,
            run_id,
            max_bytes,
            backup_count,
            keep_latest,
            max_total_bytes,
            older_than_days,
            cleanup,
            repeat_limit,
            cleanup_on_close,
            format,
            sample_rate,
        )
        if _configured_log_path is not None and signature == _configured_signature:
            return _configured_log_path
        if _configured_log_path is not None:
            _remove_project_handlers(package_logger)

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
        log_path = _build_log_path(resolved_log_dir, active_run_id)

        if _original_level is None:
            _original_level = package_logger.level
            _original_propagate = package_logger.propagate
        package_logger.setLevel(min(logging.DEBUG, log_level))
        package_logger.propagate = True

        handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        setattr(handler, _HANDLER_MARKER, True)
        handler.setLevel(log_level)
        handler.addFilter(_LogContextFilter(active_run_id))
        handler.addFilter(
            _RepeatedDebugFilter(
                repeat_limit, suppress_levels={logging.DEBUG, logging.WARNING}
            )
        )
        if format == "json":
            handler.setFormatter(JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
        else:
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
        if sample_rate < 1.0:
            handler.addFilter(SamplingFilter(rate=sample_rate))
        package_logger.addHandler(handler)

        _configured_log_path = log_path
        _configured_run_id = active_run_id
        _configured_signature = signature
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

    files = list(resolved_log_dir.glob("uasset_read*.log*"))

    def family_base(path: Path) -> Path:
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
    active_family = family_base(_configured_log_path) if _configured_log_path else None
    selected_families: set[Path] = set()

    if keep_latest is not None:
        if keep_latest < 0:
            raise ValueError("keep_latest must be >= 0")
        effective_keep_latest = max(1, keep_latest)
        selected_families.update(
            family
            for family in ordered_families[effective_keep_latest:]
            if family != active_family
        )

    if older_than_days is not None:
        if older_than_days < 0:
            raise ValueError("older_than_days must be >= 0")
        cutoff = datetime.now() - timedelta(days=older_than_days)
        selected_families.update(
            family
            for family in ordered_families
            if family != active_family
            and datetime.fromtimestamp(
                max(path.stat().st_mtime for path in families[family])
            )
            < cutoff
        )

    if max_total_bytes is not None:
        if max_total_bytes < 0:
            raise ValueError("max_total_bytes must be >= 0")
        remaining_total = sum(path.stat().st_size for path in files)
        remaining_total -= sum(
            path.stat().st_size
            for family in selected_families
            for path in families[family]
        )
        newest_family = ordered_families[0] if ordered_families else None
        for family in reversed(ordered_families):
            if remaining_total <= max_total_bytes:
                break
            if family in selected_families or family in {active_family, newest_family}:
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


def _reset_logging_state_for_tests() -> None:
    """Remove only handlers installed by configure_project_logging()."""
    global _configured_log_path
    global _configured_run_id
    global _configured_signature
    global _disabled_by_request
    global _original_level
    global _original_propagate

    with _state_lock:
        package_logger = logging.getLogger(_LOGGER_NAME)
        _shutdown_locked(package_logger)
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
