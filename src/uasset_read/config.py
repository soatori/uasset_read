"""解析配置 dataclass — ParseConfig / LogConfig。

将 parse_package() 和 core API 中散落的配置参数提取为结构化对象，
减少函数参数数量，提升可读性和可组合性。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
    from uasset_read.memory_safety import MemoryPolicy


@dataclass
class ParseConfig:
    """解析管线配置。

    包含影响解析行为的所有参数（不含文件路径、provider 等运行时输入）。

    典型用法::

        from uasset_read.config import ParseConfig

        cfg = ParseConfig(tolerant=False, game="Fortnite")
        result = parse_package("file.uasset", config=cfg)
    """

    # --- 容错 / 调试 ---
    tolerant: bool = True
    """是否启用容错模式（默认开启）。"""
    force_full_parse: bool = False
    """强制完整解析大蓝图（忽略轻量模式阈值）。"""
    hex_view: bool = False
    """启用 HexView 字节偏移追踪。"""

    # --- 资产关系 ---
    include_parent_assets: bool = False
    """是否解析父资产。"""
    asset_roots: Optional[Sequence[str]] = field(default=None)
    """资产根目录列表，用于查找父资产。"""

    # --- 类型映射 / 游戏适配 ---
    mappings_path: Optional[str] = None
    """.usmap/.jmap 类型映射文件路径。"""
    game: Optional[str] = None
    """游戏标识，启用游戏特定属性解析。"""

    # --- 轻量模式 ---
    lightweight_threshold: Optional[int] = None
    """轻量模式触发阈值（export 数量），None 使用默认值。"""

    # --- 内存策略 ---
    memory_policy: Optional["MemoryPolicy"] = None
    """可选内存策略，控制 RSS 限制和隔离行为。"""

@dataclass
class LogConfig:
    """日志配置。

    包含文件日志相关的所有参数，用于 parse_single / parse_batch / diff_single
    等 core API。

    典型用法::

        from uasset_read.config import LogConfig

        log = LogConfig(level="info", dir="./my_logs")
        output = parse_single("file.uasset", log_config=log)
    """

    level: Optional[str] = None
    """日志级别：debug / info / warning / error / off。None 表示默认。"""
    dir: Optional[str] = None
    """日志输出目录，None 使用默认 ./log。"""
    enabled: bool = True
    """是否启用文件日志。"""
    run_id: Optional[str] = None
    """日志运行 ID，子进程可复用父进程的 ID。"""
    keep_latest: Optional[int] = None
    """保留最新 N 个日志文件（配合 cleanup 使用）。"""
    max_total_bytes: Optional[int] = None
    """日志总大小上限（字节）。"""
    cleanup: bool = False
    """是否在启动时清理旧日志。"""
    auto_cleanup: bool = False
    """是否在日志会话结束后自动清理旧日志。"""
    max_bytes: int = 10_000_000
    """单个日志文件最大大小（字节），默认 10MB。"""
    backup_count: int = 5
    """保留的备份日志文件数量，默认 5。"""
    format: str = "text"
    """日志输出格式：'text'（默认）或 'json'。"""

    def to_configure_kwargs(self) -> dict:
        """转换为 configure_project_logging() 的关键字参数。"""
        effective_enabled = self.enabled and self.level != "off"
        d = asdict(self)
        d.pop("enabled", None)
        d.pop("auto_cleanup", None)
        # Rename fields that differ
        if d.get("dir"):
            d["log_dir"] = d.pop("dir")
        else:
            d.pop("dir", None)
        d["enabled"] = effective_enabled
        if self.cleanup:
            d["cleanup"] = True
        if self.auto_cleanup:
            d["cleanup_on_close"] = True
        if self.format == "text":
            d.pop("format", None)
        # Remove None values to avoid overwriting caller's explicit None
        return {k: v for k, v in d.items() if v is not None}
