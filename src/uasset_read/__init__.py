"""
uasset_read - Unreal Engine .uasset 文件解析器

版本 0.5.4

公共API通过__all__控制。内部导出通过 __getattr__ 延迟加载并发出 deprecation 警告。
"""
__version__ = "0.5.4"

import warnings as _warnings

# ============================================================================
# 稳定公共 API（直接导入）
# ============================================================================

from .core import parse_single, parse_batch, diff_single, list_formats, BatchResult
from .config import ParseConfig, LogConfig
from .parse_uasset import parse_package, parse_uasset, parse_uasset_with_linker
from .project_logging import configure_project_logging
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
    # 核心模型
    "ParseResult",
    # 异常
    "ParseError",
    # 二进制读取器
    "FArchive",
]

# ============================================================================
# 内部导出映射（通过 __getattr__ 延迟加载 + deprecation 警告）
# ============================================================================

from ._compat import DEPRECATED_IMPORTS as _DEPRECATED_IMPORTS


def __getattr__(name: str):
    """延迟加载内部导出项，同时发出 DeprecationWarning。"""
    if name in _DEPRECATED_IMPORTS:
        module_path, attr_name = _DEPRECATED_IMPORTS[name]
        import importlib
        mod = importlib.import_module(module_path, __package__)
        value = getattr(mod, attr_name)
        _warnings.warn(
            f"uasset_read.{name} 已废弃，请从子模块直接导入 "
            f"（如 from {module_path} import {attr_name}），"
            "此导出将在未来版本移除。",
            DeprecationWarning,
            stacklevel=2,
        )
        # 缓存到模块命名空间，避免重复警告
        globals()[name] = value
        return value
    raise AttributeError(f"module 'uasset_read' has no attribute {name!r}")


def __dir__():
    """暴露 __all__ + 废弃项（便于自动补全和测试发现）。"""
    public = set(__all__)
    deprecated = set(_DEPRECATED_IMPORTS.keys())
    return sorted(public | deprecated)
