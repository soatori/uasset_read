"""Parse configuration dataclasses — ParseConfig / LogConfig.

Extract scattered configuration parameters from parse_package() and core API into structured objects,
reducing function parameter count and improving readability and composability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
    from uasset_read.memory_safety import MemoryPolicy


@dataclass
class ParseConfig:
    """Parse pipeline configuration.

    Contains all parameters that affect parsing behavior (excluding file paths, provider,
    and other runtime inputs).

    Typical usage::

        from uasset_read.config import ParseConfig

        cfg = ParseConfig(tolerant=False, game="Fortnite")
        result = parse_package("file.uasset", config=cfg)
    """

    # --- Tolerant / Debug ---
    tolerant: bool = True
    """Whether to enable tolerant mode (default: enabled)."""
    force_full_parse: bool = False
    """Force full parse for large blueprints (ignore lightweight mode threshold)."""
    hex_view: bool = False
    """Enable HexView byte offset tracking."""

    # --- Asset Relationships ---
    include_parent_assets: bool = False
    """Whether to parse parent assets."""
    asset_roots: Optional[Sequence[str]] = field(default=None)
    """Root directories for locating parent assets."""

    # --- Type Mappings / Game Adaptation ---
    mappings_path: Optional[str] = None
    """.usmap/.jmap type mapping file path."""
    game: Optional[str] = None
    """Game identifier, enables game-specific property parsing."""

    # --- Lightweight Mode ---
    lightweight_threshold: Optional[int] = None
    """Lightweight mode trigger threshold (export count). None uses default value."""

    # --- Memory Strategy ---
    memory_policy: Optional["MemoryPolicy"] = None
    """Optional memory strategy, controls RSS limits and isolation behavior."""

    def apply_to_package(self, kwargs: dict) -> dict:
        """Inject configuration into parse_package() keyword argument dictionary.

        Used for internal bridging. Does not override existing values in kwargs
        (such as path, provider, etc.), and does not inject None-valued fields
        to avoid overriding caller's explicit None.
        """
        for fld in self.__dataclass_fields__:
            if fld not in kwargs:
                val = getattr(self, fld)
                if val is not None:
                    kwargs[fld] = val
        return kwargs


@dataclass
class LogConfig:
    """Logging configuration.

    Contains all parameters related to file logging, used by core APIs
    such as parse_single / parse_batch / diff_single.

    Typical usage::

        from uasset_read.config import LogConfig

        log = LogConfig(level="info", dir="./my_logs")
        output = parse_single("file.uasset", log_config=log)
    """

    level: Optional[str] = None
    """Log level: debug / info / warning / error / off. None means default."""
    dir: Optional[str] = None
    """Log output directory. None uses default ./log."""
    enabled: bool = True
    """Whether to enable file logging."""
    run_id: Optional[str] = None
    """Log run ID. Child processes can reuse parent process ID."""
    keep_latest: Optional[int] = None
    """Keep only the newest N log files (used with cleanup)."""
    max_total_bytes: Optional[int] = None
    """Total log size limit (bytes)."""
    cleanup: bool = False
    """Whether to clean old logs on startup."""
    auto_cleanup: bool = False
    """Whether to automatically clean old logs after log session ends."""
    max_bytes: int = 10_000_000
    """Maximum size per log file (bytes), default 10MB."""
    backup_count: int = 5
    """Number of backup log files to keep, default 5."""
    repeat_limit: int = 5
    """Number of same DEBUG message templates to keep. 0 means no aggregation."""

    def to_configure_kwargs(self) -> dict:
        """Convert to keyword arguments for configure_project_logging()."""
        effective_enabled = self.enabled and self.level != "off"
        return {
            "level": self.level or "DEBUG",
            "log_dir": self.dir,
            "enabled": effective_enabled,
            "max_bytes": self.max_bytes,
            "backup_count": self.backup_count,
            "repeat_limit": self.repeat_limit,
            **({"run_id": self.run_id} if self.run_id is not None else {}),
            **({"keep_latest": self.keep_latest} if self.keep_latest is not None else {}),
            **({"max_total_bytes": self.max_total_bytes} if self.max_total_bytes is not None else {}),
            **({"cleanup": True} if self.cleanup else {}),
            **({"cleanup_on_close": True} if self.auto_cleanup else {}),
        }
