"""CLI 配置 dataclass — LogConfig。

将命令行中散落的日志相关参数提取为结构化对象，减少函数参数数量。
`ParseConfig` 已随 v1 解析管线删除：v2 的 `parse_package_document()`
直接接受关键字参数，不再需要单独的管线配置对象。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class LogConfig:
    """日志配置。

    由 CLI 的 `--clean-logs` 路径使用：日志文件本身的写出配置已随 v1
    管线一并移除，库代码不再配置进程级日志，只有 `keep_latest` /
    `max_total_bytes` 会被读取并交给 `cleanup_project_logs()`。

    典型用法（只有 `dir` / `keep_latest` / `max_total_bytes` 会被读取）::

        from uasset_read.config import LogConfig

        cfg = LogConfig(dir="./my_logs", keep_latest=20)
    """

    level: Optional[str] = None
    """日志级别：debug / info / warning / error / off。None 表示默认。"""
    dir: Optional[str] = None
    """日志输出目录，None 使用默认 ./log。"""
    keep_latest: Optional[int] = None
    """保留最新 N 个日志文件（配合 cleanup 使用）。"""
    max_total_bytes: Optional[int] = None
    """日志总大小上限（字节）。"""
    cleanup: bool = False
    """是否在启动时清理旧日志。"""
