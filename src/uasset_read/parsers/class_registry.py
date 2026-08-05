from __future__ import annotations

"""src/uasset_read/parsers/class_registry.py -- Class Handler Registry.

Reference: CUE4Parse ObjectTypeRegistry pattern:
1. Exact class handler lookup
2. Parent class handler lookup (for future extension)
3. Generic UObject fallback
4. Skip policy as last resort

Handler interface:
- can_handle(class_name) -> bool
- parse(export, archive, context) -> HandlerResult
- fallback_policy -> FallbackPolicy
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.models.properties import PropertyValue

logger = logging.getLogger(__name__)


class FallbackPolicy(str, Enum):
    """Fallback strategy when a handler cannot process the class."""
    GENERIC_UOBJECT = "generic_uobject"
    SKIP = "skip"
    RAISE = "raise"
    PROPERTY_FALLBACK = "property_fallback"


@dataclass
class HandlerResult:
    """Parse result from a class handler."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    fallback_policy: FallbackPolicy = FallbackPolicy.GENERIC_UOBJECT


class ClassHandler(ABC):
    """Abstract base class for class handlers."""

    @abstractmethod
    def can_handle(self, class_name: str) -> bool:
        """Determine whether this handler can handle the given class_name."""
        ...

    @property
    @abstractmethod
    def handler_name(self) -> str:
        """Handler name (used for logging and diagnostics)."""
        ...

    @property
    def fallback_policy(self) -> FallbackPolicy:
        """Fallback strategy when handler parsing fails."""
        return FallbackPolicy.GENERIC_UOBJECT

    @abstractmethod
    def parse(
        self,
        export: "ObjectExport",
        archive: "FArchive",
        context: Optional[Any] = None,
    ) -> HandlerResult:
        """Parse property data from an export."""
        ...


class ClassHandlerRegistry:
    """Class handler registry."""

    def __init__(self) -> None:
        self._handlers: List[ClassHandler] = []
        self._cache: Dict[str, Optional[ClassHandler]] = {}

    def register(self, handler: ClassHandler) -> None:
        """Register a class handler."""
        self._handlers.append(handler)
        self._cache.clear()

    def find_handler(self, class_name: str) -> Optional[ClassHandler]:
        """Find a handler that can handle the given class_name."""
        if class_name in self._cache:
            return self._cache[class_name]

        for handler in self._handlers:
            if handler.can_handle(class_name):
                self._cache[class_name] = handler
                return handler

        self._cache[class_name] = None
        return None

    def get_registered_handlers(self) -> List[ClassHandler]:
        """Return all registered handlers."""
        return list(self._handlers)

    def clear(self) -> None:
        """Clear all registrations and cache."""
        self._handlers.clear()
        self._cache.clear()

    def reset_cache(self) -> None:
        """Clear the class_name -> handler lookup cache.

        Intended for batch parsing scenarios; called from the finally block
        of parse_package to prevent the _cache dict from growing unboundedly.
        Note: does not clear the registered handlers.
        """
        self._cache.clear()


# Global default registry instance
_default_registry: Optional[ClassHandlerRegistry] = None
_bootstrap_done: bool = False


def _bootstrap_handlers() -> None:
    """Register all built-in asset type handlers into the default registry.

    Uses a lazy import of ``uasset_read.parsers.asset_types`` to avoid
    circular-import issues while keeping registration deterministic.
    Called exactly once on the first ``get_class_registry()`` invocation.
    """
    global _bootstrap_done
    if _bootstrap_done:
        return
    _bootstrap_done = True
    try:
        from uasset_read.parsers.asset_types import register_asset_type_handlers
        register_asset_type_handlers()
    except Exception:
        logger.debug("Failed to bootstrap asset type handlers", exc_info=True)


def get_class_registry() -> ClassHandlerRegistry:
    """Get the global default class handler registry.

    The first call automatically bootstraps all built-in asset type
    handlers, so callers never need to import or call
    ``register_asset_type_handlers()`` themselves.
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = ClassHandlerRegistry()
        _bootstrap_handlers()
    return _default_registry


def reset_class_registry() -> None:
    """Reset the global default registry (for testing)."""
    global _default_registry, _bootstrap_done
    _default_registry = None
    _bootstrap_done = False
