"""Extension registry — maps exact UE class names to domain extractors.

Domain issues (#554-#557) register their extractors here. The builder
invokes registered hooks; unregistered assets emit opaque output.
"""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import ExportIR
    from uasset_read.semantic.models import SemanticIR


# Registry: UE class name -> extractor function
_REGISTRY: dict[str, Callable] = {}


def register_extension(class_name: str, extractor: Callable) -> None:
    """Register a domain extractor for an exact UE class name.

    Raises ValueError on duplicate registration (deterministic check).
    """
    if class_name in _REGISTRY:
        raise ValueError(f"Extension already registered for class '{class_name}'")
    _REGISTRY[class_name] = extractor


def get_extractor(class_name: str) -> Callable | None:
    """Get the registered extractor for a class, or None."""
    return _REGISTRY.get(class_name)


def is_registered(class_name: str) -> bool:
    """Check whether a class has a registered extractor."""
    return class_name in _REGISTRY
