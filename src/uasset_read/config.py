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

    由 CLI（`cli._log_config_from_args`）从 `--log-*` 参数构造。日志文件
    本身的写出配置已随 v1 管线一并移除：库代码不再配置进程级日志，
    只有 `--clean-logs` 路径会读取 `keep_latest` / `max_total_bytes` 并
    把它们交给 `cleanup_project_logs()`。其余字段目前仅作为参数载体保留，
    对应的 CLI 旗标是否退役由单独的产品决定。

    典型用法::

        from uasset_read.config import LogConfig

        log = LogConfig(level="info", dir="./my_logs")
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
    """历史字段：日志会话机制已删除，当前无人读取。"""
    max_bytes: int = 10_000_000
    """单个日志文件最大大小（字节），默认 10MB。"""
    backup_count: int = 5
    """保留的备份日志文件数量，默认 5。"""
    format: str = "text"
    """日志输出格式：'text'（默认）或 'json'。"""
