"""解析配置 dataclass — ParseConfig / LogConfig。

将 parse_package() 和 core API 中散落的配置参数提取为结构化对象，
减少函数参数数量，提升可读性和可组合性。
"""

from __future__ import annotations

from dataclasses import dataclass, field
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

    def apply_to_package(self, kwargs: dict) -> dict:
        """将配置项注入 parse_package() 的调用参数字典。

        用于内部桥接，不覆盖 kwargs 中已有的值（如 path、provider 等），
        也不注入值为 None 的字段，避免覆盖调用方的显式 None。
        """
        for fld in self.__dataclass_fields__:
            if fld not in kwargs:
                val = getattr(self, fld)
                if val is not None:
                    kwargs[fld] = val
        return kwargs


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
    max_bytes: int = 10_000_000
    """单个日志文件最大大小（字节），默认 10MB。"""
    backup_count: int = 5
    """保留的备份日志文件数量，默认 5。"""

    def to_configure_kwargs(self) -> dict:
        """转换为 configure_project_logging() 的关键字参数。"""
        effective_enabled = self.enabled and self.level != "off"
        return {
            "level": self.level or "DEBUG",
            "log_dir": self.dir,
            "enabled": effective_enabled,
            "max_bytes": self.max_bytes,
            "backup_count": self.backup_count,
            **({"run_id": self.run_id} if self.run_id is not None else {}),
            **({"keep_latest": self.keep_latest} if self.keep_latest is not None else {}),
            **({"max_total_bytes": self.max_total_bytes} if self.max_total_bytes is not None else {}),
            **({"cleanup": True} if self.cleanup else {}),
        }
