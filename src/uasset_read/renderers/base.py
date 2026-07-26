"""Renderer base — IRenderer ABC + RenderOptions.

Renderers only accept PackageIR, they do not access ParseResult.
Renderers do not perform data transformations (GUID formatting etc. is done during IR construction).
Renderers do not assemble business logic, they only handle format layout.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


# ── Renderer shared constants ──
# Filter lists shared across renderers, defined here in a unified location.

# Editor layout properties (do not affect runtime and C++ translation)
EDITOR_PROPERTY_NAMES = frozenset({
    # Node layout
    "NodePosX", "NodePosY", "NodeWidth", "NodeHeight",
    "NodeGuid", "NodeComment", "bIsCommentBubbleVisible",
    # Comment-related
    "CommentColor", "FontSize",
    "bCommentBubbleVisible_InDetailsPanel",
    "bCommentBubblePinned", "bCommentBubbleVisible",
    # Graph-related
    "Schema", "GraphGuid", "ErrorType",
    "AdvancedPinDisplay", "MoveMode",
    # Event/function references (already extracted to other fields)
    "EventReference", "bOverrideFunction",
})

# Editor internal variables (do not affect runtime and C++ translation)
EDITOR_VARIABLE_NAMES = frozenset({
    "UbergraphPages",  # Graph page index list
    "FunctionGraphs",  # Function graph index list
    "CategorySorting",  # Editor category sorting
    "ImplementedInterfaces",  # Implemented interfaces (already in blueprint.interfaces)
    "LastEditedDocuments",  # Last edited documents
    "ThumbnailInfo",  # Thumbnail information
    "bLegacyNeedToPurgeSkelRefs",  # Skeleton reference cleanup flag
})

# Editor internal node classes (do not affect runtime, removed during UE compilation)
EDITOR_NODE_CLASSES = frozenset({
    "K2Node_Knot",  # Redirect node, used for editor layout only
})


def filter_editor_items(
    items: list,
    class_field: str = "object_class",
    exclude_classes: frozenset = EDITOR_NODE_CLASSES,
) -> list:
    """Filter editor-specific items (shared across renderers)."""
    return [item for item in items if getattr(item, class_field, None) not in exclude_classes]


def filter_variables(
    variables: list,
    exclude_names: frozenset = EDITOR_VARIABLE_NAMES,
) -> list:
    """Filter editor internal variables (shared across renderers)."""
    return [v for v in variables if v.name not in exclude_names]


def is_blueprint_export(export: ExportIR) -> bool:
    """Determine whether an export is blueprint-related.

    Blueprint export definition:
    - Class name ends with _C (e.g., BP_Character_C)
    - Or has graphs data
    """
    if getattr(export, "object_name", None) is not None and export.object_name.endswith("_C"):
        return True
    if export.graphs:
        return True
    return False


@dataclass
class RenderOptions:
    """Render options (read-only by renderers, not modified)."""
    verbose: bool = False
    indent: int = 2
    include_schema: bool = False
    include_function_graphs: bool = False
    output_level: str = "standard"  # "standard" (default, filters UI/empty fields) or "debug" (full output)
    hex_view: bool = False  # Output HexView parsing trace data


class IRenderer(ABC):
    """Renderer abstract base class."""

    @abstractmethod
    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        """Render IR to a string.

        Args:
            ir: PackageIR instance
            options: Render options

        Returns:
            Rendered string
        """
        ...

    def render_to(self, ir: PackageIR, writer: IO[str], options: RenderOptions | None = None) -> None:
        """Render to a file/stream.

        Default implementation writes the render() result.
        JSONRenderer overrides this method to use json.dump() for streaming writes.

        Args:
            ir: PackageIR instance
            writer: Writable text stream
            options: Render options, defaults to RenderOptions() when None
        """
        if options is None:
            options = RenderOptions()
        writer.write(self.render(ir, options))

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Format name handled by this renderer."""
        ...
