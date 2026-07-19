"""
uasset_read - Unreal Engine .uasset 文件解析器

版本 0.5.4.44

公共API通过__all__控制。
"""
__version__ = "0.5.4.44"

# ============================================================================
# 稳定公共 API（直接导入）
# ============================================================================

from .core import parse_single, parse_batch, diff_single, list_formats, BatchResult
from .config import ParseConfig, LogConfig
from .parse_uasset import parse_package, parse_uasset, parse_uasset_with_linker
from .project_logging import (
    ProjectLogSession,
    configure_project_logging,
    project_logging_session,
    shutdown_project_logging,
)
from .models import ParseResult
from .exceptions import ParseError
from .archive import FArchive

__all__ = [
    "__version__",
    # Core API
    "parse_single",
    "parse_batch",
    "diff_single",
    "list_formats",
    "BatchResult",
    # 配置
    "ParseConfig",
    "LogConfig",
    # 解析管线
    "parse_package",
    "parse_uasset",
    "parse_uasset_with_linker",
    # 日志
    "configure_project_logging",
    "ProjectLogSession",
    "project_logging_session",
    "shutdown_project_logging",
    # 核心模型
    "ParseResult",
    # 异常
    "ParseError",
    # 二进制读取器
    "FArchive",
]
