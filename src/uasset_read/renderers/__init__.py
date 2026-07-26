"""Renderer registry — maps format names to renderers and dispatches.

Replaces the old ExporterRegistry + FORMAT_REGISTRY.
"""

from typing import Type

from uasset_read.renderers.base import IRenderer

# Renderer registry (auto-populated when concrete renderer modules are imported)
RENDERER_REGISTRY: dict[str, Type[IRenderer]] = {}


def register_renderer(format_name: str, renderer_class: Type[IRenderer]) -> None:
    """Register a mapping from a format name to a renderer class."""
    if format_name in RENDERER_REGISTRY:
        raise ValueError(f"Render format '{format_name}' is already registered")
    RENDERER_REGISTRY[format_name] = renderer_class


def get_renderer(format_name: str) -> IRenderer:
    """Get a renderer instance for the specified format."""
    renderer_class = RENDERER_REGISTRY.get(format_name)
    if renderer_class is None:
        available = ", ".join(sorted(RENDERER_REGISTRY.keys()))
        raise ValueError(f"Unknown render format: '{format_name}'. Available: {available}")
    return renderer_class()


def list_formats() -> list[str]:
    """Return all registered format names."""
    return sorted(RENDERER_REGISTRY.keys())


# Import concrete renderer modules to trigger registration
from uasset_read.renderers import json_renderer  # noqa: F401, E402
from uasset_read.renderers import markdown_renderer  # noqa: F401, E402
