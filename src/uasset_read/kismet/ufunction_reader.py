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
from uasset_read.kismet.native_fields import (
    NativeFieldContext,
    NativeFieldDeclaration,
    read_native_fields,
)
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
    bytecode_buffer_size: int | None = None
    serialized_script_size: int | None = None
    remaining_serialized: int | None = None


# ---------------------------------------------------------------------------
# Custom exception types for UFunction script failures
# ---------------------------------------------------------------------------


class UnsupportedSerializationVersion(Exception):
    """Raised when the serialization-control byte contains unknown bits."""

    def __init__(self, failure: FunctionScriptFailure):
        self.failure = failure
        super().__init__(failure.error_message)


class InvalidScriptPropertyRange(Exception):
    """Raised when script serialization offsets are mismatched."""

    def __init__(self, failure: FunctionScriptFailure):
        self.failure = failure
        super().__init__(failure.error_message)


@dataclass
class FunctionScriptReadResult:
    """Result of reading a native UFunction script."""

    status: Literal["extracted", "no_script", "failed"]
    serialized_script: bytes = b""
    bytecode_buffer_size: int = 0
    serialized_script_size: int = 0
    native_fields: list[NativeFieldDeclaration] = field(default_factory=list)
    failure: FunctionScriptFailure | None = None


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
    for cv in getattr(summary, "custom_versions", ()):
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
    *,
    export_index: int = 0,
) -> ByteArchive:
    """Read the UObject prefix before the native UStruct payload.

    The window is positioned after serialization control, tagged
    properties, and UObject's optional lazy-object GUID record.

    Returns:
        window bounded to the export's serial range and positioned at the
        native UStruct payload.

    Raises:
        UnsupportedSerializationVersion: if control bits are unknown.
        InvalidScriptPropertyRange: if script_serialization offsets are mismatched.
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
                ctrl_byte,
                export,
                summary,
                export_index=export_index,
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
                declared_start,
                declared_end,
                measured_end,
                export,
                summary,
                export_index=export_index,
            )

    # UObject::Serialize follows tagged properties with the optional lazy-object
    # GUID record. Persistent binary archives encode the presence flag as a
    # four-byte bool; a present GUID contributes another 16 bytes.
    window.seek(pos_after_tags)
    has_object_guid = window.read_bool("HasObjectGuid")
    if has_object_guid:
        window.read(16)

    return window


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
    *,
    export_index: int = 0,
) -> UnsupportedSerializationVersion:
    """Create an error for unknown serialization-control bits."""
    failure = FunctionScriptFailure(
        error_code="unsupported_serialization_version",
        error_message=(
            f"Unknown serialization-control bits 0x{ctrl_byte:02X} (known: 0x{_SER_CTRL_OVERRIDE_OPERATION:02X})"
        ),
        function_name=export.object_name,
        export_index=export_index,
        class_name=resolve_class_name(
            export.class_index,
            [],
            [export],
        )
        or "Unknown",
        package_offset=export.serial_offset,
        export_offset=export.serial_offset,
    )
    return UnsupportedSerializationVersion(failure)


def _make_offset_mismatch_error(
    declared_start: int,
    declared_end: int,
    measured_end: int,
    export: ObjectExport,
    summary: PackageFileSummary,
    *,
    export_index: int = 0,
) -> InvalidScriptPropertyRange:
    """Create an error for mismatched script property offsets."""
    failure = FunctionScriptFailure(
        error_code="invalid_script_property_range",
        error_message=(
            f"Script serialization offset mismatch: declared end={declared_end}, measured end={measured_end}"
        ),
        function_name=export.object_name,
        export_index=export_index,
        class_name=resolve_class_name(
            export.class_index,
            [],
            [export],
        )
        or "Unknown",
        package_offset=export.serial_offset,
        export_offset=export.serial_offset,
    )
    return InvalidScriptPropertyRange(failure)


# ---------------------------------------------------------------------------
# UStruct prefix and script header reader
# ---------------------------------------------------------------------------

# Custom version GUIDs for gating
FRAMEWORK_REMOVE_UFIELD_NEXT_VERSION = 29
CORE_FPROPERTIES_VERSION = 4


def _read_ustruct_prefix_and_script(
    window: ByteArchive,
    export: ObjectExport,
    summary: PackageFileSummary,
    *,
    export_index: int = 0,
    name_map: list[str] | None = None,
    import_map: list[ObjectImport] | None = None,
    export_map: list[ObjectExport] | None = None,
    package_flags: int = 0,
) -> FunctionScriptReadResult:
    """Read the UStruct prefix and script header after the UObject prefix.

    The window must be positioned at the native UStruct payload.
    Reads:
      1. SuperStruct: int32
      2. Children: int32 (legacy pointer) OR int32 (count) + count * int32 pointers
      3. NativePropertyCount: int32 (only when Core version >= 4)
      4. NativeField declarations (when NativePropertyCount > 0)
      5. BytecodeBufferSize: int32
      6. SerializedScriptSize: int32
      7. SerializedScript: SerializedScriptSize bytes

    Returns FunctionScriptReadResult with status "extracted", "no_script", or "failed".
    """
    # Look up custom versions
    framework_version = get_kismet_custom_version(summary, FRAMEWORK_GUID)
    core_version = get_kismet_custom_version(summary, CORE_GUID)

    # Check remaining capacity
    remaining_bytes = window.total_size() - window.tell()
    max_i32_slots = remaining_bytes // 4

    try:
        # 1. SuperStruct
        _super_struct = window.read_i32("SuperStruct")

        # 2. Children
        if framework_version >= FRAMEWORK_REMOVE_UFIELD_NEXT_VERSION:
            # Modern: count + pointers
            children_count = window.read_i32("ChildrenCount")
            if children_count < 0:
                return _make_invalid_script_size_failure(
                    f"Negative Children count: {children_count}",
                    export,
                    export_index,
                )
            if children_count > max_i32_slots:
                return _make_invalid_script_size_failure(
                    f"Children count {children_count} exceeds remaining capacity ({max_i32_slots} slots)",
                    export,
                    export_index,
                )
            for i in range(children_count):
                window.read_i32(f"Child[{i}]")
        else:
            # Legacy: single pointer
            _children_ptr = window.read_i32("ChildrenPtr")

        # 3. NativePropertyCount (only when Core version >= 4)
        native_property_count = 0
        if core_version >= CORE_FPROPERTIES_VERSION:
            native_property_count = window.read_i32("NativePropertyCount")
            if native_property_count < 0:
                return _make_invalid_script_size_failure(
                    f"Negative NativePropertyCount: {native_property_count}",
                    export,
                    export_index,
                )

        # 3a. Read native field declarations when count > 0
        native_fields: list[NativeFieldDeclaration] = []
        if native_property_count > 0:
            release_version = get_kismet_custom_version(summary, RELEASE_GUID)
            ctx = NativeFieldContext(
                name_map=name_map or [],
                import_map=import_map or [],
                export_map=export_map or [],
                package_flags=package_flags,
                release_version=release_version if release_version >= 0 else 21,
                saved_engine_version=(
                    summary.saved_by_engine_version.major or 5,
                    summary.saved_by_engine_version.minor,
                ),
            )
            native_fields = read_native_fields(window, native_property_count, ctx)

        # 4. BytecodeBufferSize
        bytecode_buffer_size = window.read_i32("BytecodeBufferSize")

        # 5. SerializedScriptSize
        serialized_script_size = window.read_i32("SerializedScriptSize")

        # Validate size pair
        validation = _validate_script_sizes(bytecode_buffer_size, serialized_script_size)
        if validation is not None:
            return FunctionScriptReadResult(
                status="failed",
                failure=FunctionScriptFailure(
                    error_code=validation[0],
                    error_message=validation[1],
                    function_name=export.object_name,
                    export_index=export_index,
                    class_name=resolve_class_name(export.class_index, [], [export]) or "Unknown",
                    package_offset=export.serial_offset,
                    export_offset=export.serial_offset,
                ),
            )

        # 0/0 = no_script
        if bytecode_buffer_size == 0 and serialized_script_size == 0:
            return FunctionScriptReadResult(
                status="no_script",
                bytecode_buffer_size=0,
                serialized_script_size=0,
                native_fields=native_fields,
            )

        # Check remaining bytes vs declared size
        remaining_after_header = window.total_size() - window.tell()
        if serialized_script_size > remaining_after_header:
            return FunctionScriptReadResult(
                status="failed",
                failure=FunctionScriptFailure(
                    error_code="truncated_script",
                    error_message=(
                        f"Declared SerializedScriptSize={serialized_script_size} "
                        f"but only {remaining_after_header} bytes remain"
                    ),
                    function_name=export.object_name,
                    export_index=export_index,
                    class_name=resolve_class_name(export.class_index, [], [export]) or "Unknown",
                    package_offset=export.serial_offset,
                    export_offset=export.serial_offset,
                    bytecode_buffer_size=bytecode_buffer_size,
                    serialized_script_size=serialized_script_size,
                    remaining_serialized=remaining_after_header,
                ),
            )

        # 6. SerializedScript
        script = window.read(serialized_script_size)
        return FunctionScriptReadResult(
            status="extracted",
            serialized_script=script,
            bytecode_buffer_size=bytecode_buffer_size,
            serialized_script_size=serialized_script_size,
            native_fields=native_fields,
        )

    except Exception as exc:
        # Catch any read errors during UStruct prefix parsing
        return FunctionScriptReadResult(
            status="failed",
            failure=FunctionScriptFailure(
                error_code="read_error",
                error_message=f"Error reading UStruct prefix: {exc}",
                function_name=export.object_name,
                export_index=export_index,
                class_name=resolve_class_name(export.class_index, [], [export]) or "Unknown",
                package_offset=export.serial_offset,
                export_offset=export.serial_offset,
            ),
        )


def _validate_script_sizes(
    bytecode_buffer_size: int,
    serialized_script_size: int,
) -> tuple[str, str] | None:
    """Validate the script size pair.

    Returns (error_code, error_message) if invalid, or None if valid.

    In UE, BytecodeBufferSize is the logical buffer size and
    SerializedScriptSize is the physical size. Both sizes are zero for a
    function with no script; a one-sided zero size pair is invalid.
    """
    # Negative sizes
    if bytecode_buffer_size < 0 or serialized_script_size < 0:
        return (
            "invalid_script_size",
            f"Negative size: BytecodeBufferSize={bytecode_buffer_size}, SerializedScriptSize={serialized_script_size}",
        )
    # Both zero is valid (no script)
    # A one-sided zero size pair is invalid
    if (bytecode_buffer_size == 0) != (serialized_script_size == 0):
        return (
            "invalid_script_size",
            "Mismatched zero size pair: "
            f"BytecodeBufferSize={bytecode_buffer_size}, "
            f"SerializedScriptSize={serialized_script_size}",
        )
    return None


def _make_invalid_script_size_failure(
    message: str,
    export: ObjectExport,
    export_index: int,
) -> FunctionScriptReadResult:
    """Create a failed result for invalid script size."""
    return FunctionScriptReadResult(
        status="failed",
        failure=FunctionScriptFailure(
            error_code="invalid_script_size",
            error_message=message,
            function_name=export.object_name,
            export_index=export_index,
            class_name=resolve_class_name(export.class_index, [], [export]) or "Unknown",
            package_offset=export.serial_offset,
            export_offset=export.serial_offset,
        ),
    )


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
    *,
    export_index: int = 0,
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
        export_index: index of this export in the export table

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
                export_index=export_index,
                class_name=class_name or "Unknown",
                package_offset=export.serial_offset,
                export_offset=export.serial_offset,
            ),
        )

    try:
        window = _read_native_payload_start(
            archive,
            export,
            summary,
            name_map,
            import_map,
            export_map,
            export_index=export_index,
        )
        return _read_ustruct_prefix_and_script(
            window,
            export,
            summary,
            export_index=export_index,
            name_map=name_map,
            import_map=import_map,
            export_map=export_map,
            package_flags=summary.package_flags,
        )
    except (UnsupportedSerializationVersion, InvalidScriptPropertyRange) as exc:
        return FunctionScriptReadResult(status="failed", failure=exc.failure)
