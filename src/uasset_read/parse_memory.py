"""parse_memory.py — 内存清理和资源释放。"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _cleanup_parse_memory(result) -> None:
    """统一内存清理：打破循环引用、重置全局缓存。

    在 parse_package / parse_package_lazy 的 finally 块中调用，
    防止批量解析时 UObjectInstance ↔ linker 循环引用导致的内存泄漏，
    以及全局缓存（ClassHandlerRegistry）无界增长。
    """
    # 打破 UObjectInstance ↔ linker 循环引用
    if result is not None and result.linker:
        try:
            if hasattr(result.linker, '_export_objects'):
                for obj in result.linker._export_objects:
                    obj.linker = None
            if hasattr(result.linker, '_import_objects'):
                for obj in result.linker._import_objects:
                    obj.linker = None
            result.linker._export_objects.clear()
            result.linker._import_objects.clear()
            result.linker._root_objects.clear()
            result.linker._preload_cache.clear()
            result.linker._archive = None
            logger.debug("linker 循环引用已打破，导出/导入对象已清理")
        except Exception as e:
            logger.debug("linker 循环引用清理异常，已忽略: %s", e)

    # 重置全局 class_registry 缓存
    try:
        from uasset_read.parsers.class_registry import get_class_registry
        get_class_registry().reset_cache()
        logger.debug("class_registry.reset_cache() 已调用")
    except Exception as e:
        logger.debug("class_registry.reset_cache() 异常，已忽略: %s", e)
