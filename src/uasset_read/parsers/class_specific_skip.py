from __future__ import annotations

"""Class-specific payload type identification + tolerant skip helper functions.

When the generic property parser enters an unsupported serialization region,
this module provides type identification and safe skip logic.
"""

import logging
from typing import TYPE_CHECKING, Optional

from uasset_read.parsers.class_registry import (
    FallbackPolicy,
    get_class_registry,
)

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary

logger = logging.getLogger(__name__)

# Export class name prefixes/keywords that need skipping.
# These classes have serialization data not fully compatible with the generic property parser.
SKIP_CLASS_PREFIXES = (
    # P0: Builder / Brush
    "CubeBuilder",
    "GeomModifier_",
    "BrushBuilder",
    # P0: Animation -- migrated to opaque whitelist (#166)
    # "AnimationDataModel",
    # P1: Niagara
    "NiagaraMeshRendererProperties",
    "NiagaraNodeParameterMapGet",
    "NiagaraNode",
    "NiagaraSystem",
    # P1: MovieScene -- moved to opaque whitelist (#164)
    # "MovieScene",
    # "MovieSceneSceneCaptureParams",
    # P2: MetaSound -- moved to opaque whitelist (#165)
    # "MetasoundEditorGraph",
    # "MetasoundEditorGraphInputObjectArray",
    # "MetasoundEditorGraphMemberDefaultObjectArray",
    # P2: K2Node
    # K2Node_FunctionEntry removed from skip list (#286):
    # Generic tagged property parser can handle it. K2Node_FunctionEntry specific fields
    # are serialized via PropertyTag, no skip needed. Skipping would mark legitimate assets as partial.
    # "K2Node_FunctionEntry",
    "K2Node_FormatText",
    # P2: Material
    # MaterialExpressionDynamicParameter removed from skip list (#136 extension):
    # Generic tagged property parser can handle it; failures handled by generic fallback.
    # MaterialExpression removed from skip list (#136):
    # Generic tagged property parser can handle most MaterialExpression subclasses.
    # Subclasses that fail to parse are handled by generic fallback (opaque/partial).
    # "MaterialExpression",
    # P3: Other
    "SkySphereMesh",
    "AggGeom_",
)


# Exact class names to skip (no prefix matching)
# These classes use fully custom serialization formats, cannot be handled by generic parser
#
def should_skip_export_class_prefix(class_name: str) -> bool:
    """Determine whether class name matches SKIP_CLASS_PREFIXES prefix.

    Args:
        class_name: UE class name

    Returns:
        True if class name starts with any SKIP_CLASS_PREFIXES prefix
    """
    return class_name.startswith(SKIP_CLASS_PREFIXES)


def should_skip_export_for_tolerant_parsing(
    export: "ObjectExport",
    class_name: Optional[str] = None,
) -> bool:
    """Determine whether tolerant skip should be used for an export (no property parsing attempted).

    Check order:
    1. class handler registry has a handler with fallback_policy == SKIP
    2. Whether export.object_name starts with SKIP_CLASS_PREFIXES
    3. Whether class_name starts with SKIP_CLASS_PREFIXES

    Args:
        export: ObjectExport instance
        class_name: Optional class name (resolved from class_index)

    Returns:
        True if property parsing should be skipped, keeping only export metadata
    """
    # Check 1: registry handler fallback policy
    if class_name is not None:
        registry = get_class_registry()
        handler = registry.find_handler(class_name)
        if handler is not None and handler.fallback_policy == FallbackPolicy.SKIP:
            return True

    # Check 2-4: original skip list (as fallback policy)
    # #521: check allowlist first — exact classes with verified tagged properties bypass prefix skip
    object_name = str(export.object_name)
    if class_name != "CubeBuilder" and object_name.startswith(SKIP_CLASS_PREFIXES):
        return True
    if class_name is not None and class_name != "CubeBuilder" and class_name.startswith(SKIP_CLASS_PREFIXES):
        return True
    return False


def skip_export_payload(
    archive: "FArchive",
    export: "ObjectExport",
    summary: "PackageFileSummary",
) -> None:
    """Safely skip the payload data of a single export.

    Seek past the export property region without attempting to parse.

    Args:
        archive: FArchive instance
        export: ObjectExport instance
        summary: PackageFileSummary instance
    """
    from uasset_read.constants import UE5_SCRIPT_SERIALIZATION_OFFSET

    if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
        # Use getattr for safe fallback to prevent AttributeError when attribute does not exist
        script_serial_end = getattr(export, "script_serialization_end_offset", None)
        if script_serial_end is None:
            # Fall back to serial_size for compatibility
            script_serial_end = export.serial_size
        payload_end = export.serial_offset + script_serial_end
    else:
        payload_end = export.serial_offset + export.serial_size

    # Ensure it does not exceed file size
    file_size = archive.total_size()
    safe_end = min(payload_end, file_size)

    logger.debug(
        "Skipping export '%s' payload: seek from %d to %d (%d bytes)",
        export.object_name,
        archive.tell(),
        safe_end,
        safe_end - archive.tell(),
    )
    archive.seek(safe_end)
