"""Native UFunction Script reader — Issue #77.

Provides bounded reading of UE5 UFunction serialized scripts, including
serialization-control prefix parsing, tagged-property navigation, and
export-boundary cross-checking.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from uasset_read.archive import ByteArchive
from uasset_read.serializers.object_resources import (
    ObjectExport,
    ObjectImport,
    resolve_class_name,
)
from uasset_read.serializers.package_summary import PackageFileSummary
from uasset_read.serializers.property_tags import read_property_tag

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Serialized GUID constants for custom-version lookup
# ---------------------------------------------------------------------------

FRAMEWORK_GUID = "3f74fccf8044b043df14919373201d17"
CORE_GUID = "3cc15e37fb48e406f08400b57e712a26"
FORTNITE_GUID = "86181d60844f64acded316aad6c7ea0d"
RELEASE_GUID = "22d5549cbe4f26a846072194d082b461"

# UE5 version threshold for serialization-control byte
UE5_SERIALIZATION_CONTROL_VERSION = 1011

# Known serialization-control bits
_SER_CTRL_OVERRIDE_OPERATION = 0x02


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FunctionScriptFailure:
    """Structured failure information for UFunction script reads."""
    error_code: str
    error_message: str
    function_name: str
    export_index: int
    class_name: str
    package_offset: int
    export_offset: int
    bytecode_index: int | None = None
    bytecode_buffer_size: int | None = None
    serialized_script_size: int | None = None
    remaining_serialized: int | None = None


@dataclass
class FunctionScriptReadResult:
    """Result of reading a native UFunction script."""
    status: Literal["extracted", "no_script", "failed"]
    serialized_script: bytes = b""
    bytecode_buffer_size: int = 0
    serialized_script_size: int = 0
    serialized_start: int | None = None
    native_fields: list[NativeFieldDeclaration] = field(default_factory=list)
    failure: FunctionScriptFailure | None = None


# Forward reference for NativeFieldDeclaration (implemented in Task 3)
@dataclass
class NativeFieldDeclaration:
    """Placeholder for native FField declarations (Task 3)."""
    name: str = ""
    type_name: str = ""


# ---------------------------------------------------------------------------
# Custom version lookup
# ---------------------------------------------------------------------------

def get_kismet_custom_version(
    summary: PackageFileSummary,
    serialized_guid: str,
) -> int:
    """Look up a custom version by serialized GUID.

    Returns the version number if found, or -1 if the GUID is not present
    in the summary's custom version table.
    """
    for cv in summary.custom_versions:
        if cv.guid == serialized_guid:
            return cv.version
    return -1


# ---------------------------------------------------------------------------
# Bounded native payload reader
# ---------------------------------------------------------------------------

def _read_native_payload_start(
    archive: FArchive,
    export: ObjectExport,
    summary: PackageFileSummary,
    name_map: list[str],
    import_map: list[ObjectImport],
    export_map: list[ObjectExport],
) -> tuple[ByteArchive, int]:
    """Read the serialization-control prefix and tagged-property stream,
    returning a bounded ByteArchive positioned after the None terminator.

    The native start is measured as the byte offset within the bounded
    archive where the tagged-property data begins (after any
    serialization-control prefix).

    Returns:
        (window, native_start) where window is a ByteArchive of the
        serialized-script region and native_start is the offset within that
        archive where tagged-property data begins.

    Raises:
        ValueError: if script_serialization offsets are mismatched.
    """
    # Copy exactly the export's serial range into a bounded archive
    archive.seek(export.serial_offset)
    payload = archive.read(export.serial_size)
    window = ByteArchive(payload, name=f"export_{export.object_name}")
    window._file_version_ue4 = summary.file_version_ue4
    window._file_version_ue5 = summary.file_version_ue5

    # Position at the start of the payload
    window.seek(0)

    # UE5 version 1011+: consume serialization-control prefix
    if summary.file_version_ue5 >= UE5_SERIALIZATION_CONTROL_VERSION:
        ctrl_byte = window.read_u8()
        if ctrl_byte & ~_SER_CTRL_OVERRIDE_OPERATION:
            # Unknown bits set — reject
            raise _make_control_bit_error(
                ctrl_byte, export, summary, window,
            )
        if ctrl_byte & _SER_CTRL_OVERRIDE_OPERATION:
            # Consume the override-operation byte
            window.read_u8()

    # Read tagged properties until the None terminator
    pos_after_tags = _consume_tagged_properties(window, name_map, summary)

    # Cross-check script_serialization offsets if they are non-zero
    if export.script_serialization_start_offset != 0 or export.script_serialization_end_offset != 0:
        declared_start = export.script_serialization_start_offset
        declared_end = export.script_serialization_end_offset
        measured_end = pos_after_tags

        if declared_end != measured_end:
            raise _make_offset_mismatch_error(
                declared_start, declared_end, measured_end, export, summary, window,
            )

    # Position window at the end of tagged properties (the native payload start)
    window.seek(pos_after_tags)
    return window, pos_after_tags


def _consume_tagged_properties(
    archive: ByteArchive,
    name_map: list[str],
    summary: PackageFileSummary,
) -> int:
    """Read property tags until the None terminator and return the archive
    position after the terminator.

    The archive must be positioned at the start of the tagged-property
    stream.
    """
    while True:
        tag = read_property_tag(archive, name_map, tolerant=False)
        if tag.name == "None":
            return archive.tell()
        # Seek to the tag's value_end_offset to skip the property value
        if tag.value_end_offset is not None:
            archive.seek(tag.value_end_offset)


def _make_control_bit_error(
    ctrl_byte: int,
    export: ObjectExport,
    summary: PackageFileSummary,
    window: ByteArchive,
) -> ValueError:
    """Create an error for unknown serialization-control bits."""
    # Seek back so the window reflects the error state
    error = FunctionScriptFailure(
        error_code="unsupported_serialization_version",
        error_message=(
            f"Unknown serialization-control bits 0x{ctrl_byte:02X} "
            f"(known: 0x{_SER_CTRL_OVERRIDE_OPERATION:02X})"
        ),
        function_name=export.object_name,
        export_index=0,
        class_name=resolve_class_name(
            export.class_index, [], [export],
        ) or "Unknown",
        package_offset=export.serial_offset,
        export_offset=export.serial_offset,
    )
    return ValueError(error.error_message)


def _make_offset_mismatch_error(
    declared_start: int,
    declared_end: int,
    measured_end: int,
    export: ObjectExport,
    summary: PackageFileSummary,
    window: ByteArchive,
) -> ValueError:
    """Create an error for mismatched script property offsets."""
    error = FunctionScriptFailure(
        error_code="invalid_script_property_range",
        error_message=(
            f"Script serialization offset mismatch: "
            f"declared end={declared_end}, measured end={measured_end}"
        ),
        function_name=export.object_name,
        export_index=0,
        class_name=resolve_class_name(
            export.class_index, [], [export],
        ) or "Unknown",
        package_offset=export.serial_offset,
        export_offset=export.serial_offset,
    )
    return ValueError(error.error_message)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def read_ufunction_script(
    archive: FArchive,
    export: ObjectExport,
    summary: PackageFileSummary,
    name_map: list[str],
    import_map: list[ObjectImport],
    export_map: list[ObjectExport],
) -> FunctionScriptReadResult:
    """Read a native UFunction script from a Function export.

    This is the main entry point for UFunction script reading.  It validates
    the export class, copies the serial range into a bounded ByteArchive,
    and navigates the serialization-control prefix and tagged-property
    stream.

    Args:
        archive: source archive (file or byte stream)
        export: the Function export entry
        summary: package file summary
        name_map: name table
        import_map: import table
        export_map: export table

    Returns:
        FunctionScriptReadResult with status and any failure information.
    """
    # Validate that this is a Function export
    class_name = resolve_class_name(export.class_index, import_map, export_map)
    if class_name not in ("Function", "UFunction"):
        return FunctionScriptReadResult(
            status="no_script",
            failure=FunctionScriptFailure(
                error_code="not_function_export",
                error_message=f"Export class is {class_name!r}, not Function",
                function_name=export.object_name,
                export_index=0,
                class_name=class_name or "Unknown",
                package_offset=export.serial_offset,
                export_offset=export.serial_offset,
            ),
        )

    try:
        window, native_start = _read_native_payload_start(
            archive, export, summary, name_map, import_map, export_map,
        )
        # Read remaining bytes after tagged properties
        remaining = window.read(window.total_size() - window.tell())
        return FunctionScriptReadResult(
            status="extracted",
            serialized_script=remaining,
            serialized_start=native_start,
        )
    except ValueError as exc:
        # Extract error_code from the message pattern
        error_code = "unsupported_serialization_version"
        error_msg = str(exc)
        if "offset mismatch" in error_msg or "invalid_script_property_range" in error_msg:
            error_code = "invalid_script_property_range"
        elif "Unknown serialization-control" in error_msg:
            error_code = "unsupported_serialization_version"
        else:
            error_code = "internal_error"

        failure = FunctionScriptFailure(
            error_code=error_code,
            error_message=error_msg,
            function_name=export.object_name,
            export_index=0,
            class_name=class_name or "Unknown",
            package_offset=export.serial_offset,
            export_offset=export.serial_offset,
        )
        return FunctionScriptReadResult(status="failed", failure=failure)
