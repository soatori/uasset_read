from __future__ import annotations

"""Class-specific payload type identification + tolerant skip helper functions.

When the generic property parser enters an unsupported serialization region,
this module provides type identification and safe skip logic.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary

logger = logging.getLogger(__name__)

# Export class name prefixes/keywords that need skipping.
# These classes have serialization data not fully compatible with the generic property parser.
SKIP_CLASS_PREFIXES = (
    # P0: Builder / Brush
    "GeomModifier_",
    "BrushBuilder",
    # P0: Animation -- migrated to opaque whitelist (#166)
    # P1: Niagara
    "NiagaraMeshRendererProperties",
    "NiagaraNodeParameterMapGet",
    "NiagaraNode",
    "NiagaraSystem",
    # P1: MovieScene -- moved to opaque whitelist (#164)
    # P2: MetaSound -- moved to opaque whitelist (#165)
    # P2: K2Node
    # K2Node_FunctionEntry removed from skip list (#286):
    # Generic tagged property parser can handle it. K2Node_FunctionEntry specific fields
    # are serialized via PropertyTag, no skip needed. Skipping would mark legitimate assets as partial.
    "K2Node_FormatText",
    # P2: Material
    # MaterialExpressionDynamicParameter removed from skip list (#136 extension):
    # Generic tagged property parser can handle it; failures handled by generic fallback.
    # MaterialExpression removed from skip list (#136):
    # Generic tagged property parser can handle most MaterialExpression subclasses.
    # Subclasses that fail to parse are handled by generic fallback (opaque/partial).
    # P3: Other
    "SkySphereMesh",
    "AggGeom_",
)


def should_skip_export_for_tolerant_parsing(
    export: "ObjectExport",
    class_name: str | None = None,
) -> bool:
    """True when the export should bypass the generic property parser."""
    return str(export.object_name).startswith(SKIP_CLASS_PREFIXES) or (
        class_name or ""
    ).startswith(SKIP_CLASS_PREFIXES)


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
