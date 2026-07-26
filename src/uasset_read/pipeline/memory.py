"""parse_memory.py — Memory cleanup and resource release."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _cleanup_parse_memory(result) -> None:
    """Unified memory cleanup: break circular references, reset global caches.

    Called in the finally block of parse_package / parse_package_lazy to prevent
    memory leaks from UObjectInstance <-> linker circular references during batch parsing,
    and unbounded growth of global caches (ClassHandlerRegistry).
    """
    # Break UObjectInstance <-> linker circular references
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
            logger.debug("linker circular references broken, export/import objects cleared")
        except Exception as e:
            logger.debug("linker circular reference cleanup exception, ignored: %s", e)

    # Reset global class_registry cache
    try:
        from uasset_read.parsers.class_registry import get_class_registry
        get_class_registry().reset_cache()
        logger.debug("class_registry.reset_cache() called")
    except Exception as e:
        logger.debug("class_registry.reset_cache() exception, ignored: %s", e)
