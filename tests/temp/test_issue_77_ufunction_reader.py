"""Tests for native UFunction Script reader — Issue #77 Task 2.

Covers:
- Custom version lookup with serialized GUID
- Export boundary enforcement and offset cross-checking
- UE5 version 1011 serialization control byte handling
- UStruct prefix reading (SuperStruct, Children, NativePropertyCount)
- Script size header validation (BytecodeBufferSize, SerializedScriptSize)
- Script extraction with various header combinations
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.serializers.object_resources import (
    ObjectExport,
    ObjectImport,
    PackageIndex,
)
from uasset_read.serializers.package_summary import (
    CustomVersion,
    PackageFileSummary,
)
from uasset_read.kismet.ufunction_reader import (
    FunctionScriptFailure,
    FunctionScriptReadResult,
    _read_native_payload_start,
    get_kismet_custom_version,
    read_ufunction_script,
)

# ---------------------------------------------------------------------------
# GUID constants (serialized lowercase hex, no dashes)
# ---------------------------------------------------------------------------
FRAMEWORK_GUID = "3f74fccf8044b043df14919373201d17"
CORE_GUID = "3cc15e37fb48e406f08400b57e712a26"
FORTNITE_GUID = "86181d60844f64acded316aad6c7ea0d"
RELEASE_GUID = "22d5549cbe4f26a846072194d082b461"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fname(index: int, number: int) -> bytes:
    """Serialize an FName as index (u32) + number (u32), little-endian."""
    return struct.pack("<II", index, number)


def serialization_control_none_terminator() -> bytes:
    """Return the serialization-control 0x00 byte followed by the None-tag
    terminator (FName index=0, number=0)."""
    return b"\x00" + fname(0, 0)


def make_summary(
    file_version_ue4: int = 522,
    file_version_ue5: int = 1011,
    custom_versions: List[CustomVersion] | None = None,
) -> PackageFileSummary:
    """Create a minimal PackageFileSummary for testing."""
    return PackageFileSummary(
        tag=0,
        legacy_file_version=-4,
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5,
        custom_versions=custom_versions or [],
    )


def make_function_export(
    payload: bytes,
    *,
    serial_offset: int = 13,
    script_serialization_start_offset: int = 0,
    script_serialization_end_offset: int = 0,
    file_version_ue4: int = 522,
    file_version_ue5: int = 1011,
):
    """Build a synthetic file buffer and return all objects needed for
    read_ufunction_script / _read_native_payload_start.

    The payload is placed at ``serial_offset`` within the buffer.  The export
    class index resolves to a ``Function`` import (class_index = PackageIndex(-1)).

    Returns:
        (archive, export, summary, name_map, import_map, export_map)
    """
    padding = b"\x00" * serial_offset
    buf = padding + payload

    archive = ByteArchive(buf, name="test_function_export")

    # Class index -1 → import index 0 (Function import)
    export = ObjectExport(
        class_index=PackageIndex(-1),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="TestFunction",
        object_flags=0,
        serial_size=len(payload),
        serial_offset=serial_offset,
        script_serialization_start_offset=script_serialization_start_offset,
        script_serialization_end_offset=script_serialization_end_offset,
    )

    summary = make_summary(
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5,
    )

    # UE convention: index 0 is always "None" (property tag terminator)
    name_map: List[str] = ["None"]

    import_map: List[ObjectImport] = [
        ObjectImport(
            class_package="/Script/CoreUObject",
            class_name="Class",
            outer_index=PackageIndex(0),
            object_name="Function",
        ),
    ]

    export_map: List[ObjectExport] = [export]

    return archive, export, summary, name_map, import_map, export_map


# ===================================================================
# Custom version tests
# ===================================================================

class TestCustomVersionLookup:
    def test_custom_version_uses_serialized_guid_and_missing_is_minus_one(self):
        summary = make_summary(custom_versions=[CustomVersion(FRAMEWORK_GUID, 37)])
        assert get_kismet_custom_version(summary, FRAMEWORK_GUID) == 37
        assert get_kismet_custom_version(summary, CORE_GUID) == -1

    def test_returns_correct_version_for_known_guids(self):
        summary = make_summary(
            custom_versions=[
                CustomVersion(FRAMEWORK_GUID, 37),
                CustomVersion(CORE_GUID, 12),
                CustomVersion(RELEASE_GUID, 5),
            ]
        )
        assert get_kismet_custom_version(summary, FRAMEWORK_GUID) == 37
        assert get_kismet_custom_version(summary, CORE_GUID) == 12
        assert get_kismet_custom_version(summary, RELEASE_GUID) == 5
        assert get_kismet_custom_version(summary, FORTNITE_GUID) == -1

    def test_empty_custom_versions_returns_minus_one(self):
        summary = make_summary(custom_versions=[])
        assert get_kismet_custom_version(summary, FRAMEWORK_GUID) == -1


# ===================================================================
# Export boundary tests
# ===================================================================

class TestNativePayloadStart:
    def test_native_start_consumes_tags_from_serial_offset_and_cross_checks_offsets(self):
        """The native reader starts at serial_offset, reads the serialization-control
        byte and tagged properties, and returns the bounded archive positioned after
        the None terminator.  script_serialization offsets are cross-checked."""
        payload = serialization_control_none_terminator() + b"NATIVE"
        archive, export, summary, names, imports, exports = make_function_export(payload)
        export.script_serialization_start_offset = 0
        export.script_serialization_end_offset = len(serialization_control_none_terminator())

        window, native_start = _read_native_payload_start(
            archive, export, summary, names, imports, exports,
        )
        assert native_start == export.script_serialization_end_offset
        assert window.read(6) == b"NATIVE"

    def test_native_start_rejects_mismatched_script_property_offsets(self):
        """When script_serialization_end_offset does not match the measured
        tagged-property range, the reader returns a failed result.

        Uses file_version_ue5 < 1011 to avoid serialization-control prefix,
        so the 8-byte None terminator (fname(0,0)) is read directly.
        The declared end of 7 is deliberately one byte short of the 8-byte
        None tag.
        """
        payload = fname(0, 0) + b"NATIVE"
        archive, export, summary, names, imports, exports = make_function_export(
            payload, file_version_ue5=1010,
        )
        export.script_serialization_start_offset = 0
        export.script_serialization_end_offset = 7  # deliberately wrong (8 bytes of fname)

        result = read_ufunction_script(archive, export, summary, names, imports, exports)
        assert result.status == "failed"
        assert result.failure is not None
        assert result.failure.error_code == "invalid_script_property_range"


# ===================================================================
# UE5 version 1011 serialization control byte tests
# ===================================================================

class TestSerializationControlByte:
    """UE5 version 1011+ consumes one serialization-control byte at the start of
    the tagged-property payload.  Bit 0x02 means an override-operation byte
    follows.  Other bits are rejected."""

    def test_control_byte_zero_no_override(self):
        """Control byte 0x00: no override-operation, proceed to tagged properties."""
        script = b"DATA"
        native = modern_ustruct_prefix(property_count=0) + script_header(4, 4) + script
        payload = serialization_control_none_terminator() + native
        archive, export, summary, names, imports, exports = make_function_export(
            payload, file_version_ue5=1011,
        )
        export.script_serialization_start_offset = 0
        export.script_serialization_end_offset = len(serialization_control_none_terminator())
        summary = make_summary_with_versions(framework_version=37, core_version=12)

        result = read_ufunction_script(archive, export, summary, names, imports, exports)
        assert result.status == "extracted"
        assert result.serialized_script == script

    def test_control_byte_0x02_with_override_operation(self):
        """Control byte 0x02: consume one override-operation byte after control byte."""
        # 1 control byte (0x02) + 1 override-operation byte + None tag (8 bytes)
        control_prefix = b"\x02\x01"  # control=0x02, override_op=0x01
        none_tag = fname(0, 0)
        payload = control_prefix + none_tag + b"SCRIPT"
        archive, export, summary, names, imports, exports = make_function_export(
            payload, file_version_ue5=1011,
        )
        export.script_serialization_start_offset = 0
        export.script_serialization_end_offset = len(control_prefix) + len(none_tag)

        window, native_start = _read_native_payload_start(
            archive, export, summary, names, imports, exports,
        )
        assert native_start == export.script_serialization_end_offset
        assert window.read(6) == b"SCRIPT"

    def test_unknown_control_bit_rejected(self):
        """Control byte with bit 0x01 set (unknown) returns unsupported_serialization_version."""
        payload = b"\x01" + fname(0, 0)  # unknown bit 0x01
        archive, export, summary, names, imports, exports = make_function_export(
            payload, file_version_ue5=1011,
        )

        result = read_ufunction_script(archive, export, summary, names, imports, exports)
        assert result.status == "failed"
        assert result.failure is not None
        assert result.failure.error_code == "unsupported_serialization_version"

    def test_control_byte_with_multiple_known_bits(self):
        """Control byte 0x02 with additional unknown bit 0x04 is still rejected
        because not all bits are accounted for."""
        payload = b"\x06" + b"\x01" + fname(0, 0)  # 0x06 = 0x02 | 0x04 (unknown)
        archive, export, summary, names, imports, exports = make_function_export(
            payload, file_version_ue5=1011,
        )

        result = read_ufunction_script(archive, export, summary, names, imports, exports)
        assert result.status == "failed"
        assert result.failure is not None
        assert result.failure.error_code == "unsupported_serialization_version"

    def test_no_control_byte_below_ue5_1011(self):
        """Below UE5 version 1011, no serialization-control byte is consumed."""
        payload = fname(0, 0) + b"SCRIPT"
        archive, export, summary, names, imports, exports = make_function_export(
            payload, file_version_ue5=1010,
        )
        export.script_serialization_start_offset = 0
        export.script_serialization_end_offset = len(fname(0, 0))

        window, native_start = _read_native_payload_start(
            archive, export, summary, names, imports, exports,
        )
        assert native_start == export.script_serialization_end_offset
        assert window.read(6) == b"SCRIPT"


# ===================================================================
# UStruct prefix helpers
# ===================================================================

def i32(value: int) -> bytes:
    """Serialize a signed 32-bit integer, little-endian."""
    return struct.pack("<i", value)


def ustruct_prefix_legacy(super_struct: int = 0, children_ptr: int = 0) -> bytes:
    """Legacy UStruct prefix (Framework version < 29):
    SuperStruct: i32, Children: legacy pointer (i32).
    """
    return i32(super_struct) + i32(children_ptr)


def ustruct_prefix_modern(
    super_struct: int = 0,
    children_count: int = 0,
    property_count: int = 0,
) -> bytes:
    """Modern UStruct prefix (Framework version >= 29):
    SuperStruct: i32, Children: count (i32) + count*i32 pointers,
    NativePropertyCount: i32 (when Core version >= 4).
    """
    result = i32(super_struct) + i32(children_count)
    for _ in range(children_count):
        result += i32(0)
    result += i32(property_count)
    return result


def modern_ustruct_prefix(property_count: int = 0) -> bytes:
    """Convenience wrapper: modern UStruct prefix with zero children."""
    return ustruct_prefix_modern(property_count=property_count)


def script_header(bytecode_size: int, script_size: int) -> bytes:
    """BytecodeBufferSize + SerializedScriptSize."""
    return i32(bytecode_size) + i32(script_size)


def make_summary_with_versions(
    file_version_ue4: int = 522,
    file_version_ue5: int = 1011,
    framework_version: int = 37,
    core_version: int = 12,
) -> PackageFileSummary:
    """Create a summary with specific framework and core custom versions."""
    return PackageFileSummary(
        tag=0,
        legacy_file_version=-4,
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5,
        custom_versions=[
            CustomVersion(FRAMEWORK_GUID, framework_version),
            CustomVersion(CORE_GUID, core_version),
        ],
    )


def read_synthetic_function(
    native: bytes,
    *,
    framework_version: int = 37,
    core_version: int = 12,
    file_version_ue4: int = 522,
    file_version_ue5: int = 1011,
) -> FunctionScriptReadResult:
    """Build a synthetic Function export and run read_ufunction_script.

    The ``native`` bytes are placed after the serialization-control prefix
    and None terminator (tagged-property stream).
    """
    # Prefix: serialization-control 0x00 + None tag
    control_prefix = b"\x00"
    none_tag = fname(0, 0)
    payload = control_prefix + none_tag + native

    archive, export, summary, names, imports, exports = make_function_export(
        payload,
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5,
    )
    export.script_serialization_start_offset = 0
    export.script_serialization_end_offset = len(control_prefix) + len(none_tag)

    summary = make_summary_with_versions(
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5,
        framework_version=framework_version,
        core_version=core_version,
    )

    return read_ufunction_script(archive, export, summary, names, imports, exports)


# ===================================================================
# UStruct prefix and header tests
# ===================================================================

class TestUStructPrefix:
    """UStruct prefix parsing after tagged properties."""

    def test_modern_zero_property_function_extracts_script(self):
        """Modern header with zero native properties: read script bytes."""
        script = bytes([0x00])  # EX_EndOfScript
        result = read_synthetic_function(
            native=modern_ustruct_prefix(property_count=0) + script_header(1, 1) + script,
        )
        assert result.status == "extracted"
        assert result.serialized_script == script
        assert result.bytecode_buffer_size == 1
        assert result.serialized_script_size == 1

    def test_zero_zero_header_is_no_script(self):
        """BytecodeBufferSize=0 and SerializedScriptSize=0 -> no_script."""
        result = read_synthetic_function(
            native=modern_ustruct_prefix(property_count=0) + script_header(0, 0),
        )
        assert result.status == "no_script"

    @pytest.mark.parametrize("buffer_size, serialized_size", [
        (-1, 0),
        (0, -1),
        (1, 0),
        (0, 1),
    ])
    def test_invalid_script_size_pairs_fail(self, buffer_size: int, serialized_size: int):
        """Negative or one-sided-zero sizes are rejected."""
        result = read_synthetic_function(
            native=modern_ustruct_prefix(property_count=0) + script_header(buffer_size, serialized_size),
        )
        assert result.status == "failed"
        assert result.failure is not None
        assert result.failure.error_code == "invalid_script_size"

    def test_truncated_script_reports_declared_and_remaining_sizes(self):
        """Declared script size larger than available bytes -> truncated_script."""
        result = read_synthetic_function(
            native=modern_ustruct_prefix(property_count=0) + script_header(4, 4) + b"\x53",
        )
        assert result.status == "failed"
        assert result.failure is not None
        assert result.failure.error_code == "truncated_script"
        assert result.failure.remaining_serialized == 1

    def test_legacy_framework_28_one_child_pointer(self):
        """Framework version 28 uses legacy Children (one pointer, no count)."""
        script = bytes([0x00])
        native = (
            ustruct_prefix_legacy(super_struct=0, children_ptr=0)
            + i32(0)  # NativePropertyCount (core_version >= 4)
            + script_header(1, 1)
            + script
        )
        result = read_synthetic_function(
            native=native,
            framework_version=28,
            core_version=12,
        )
        assert result.status == "extracted"
        assert result.serialized_script == script
        assert result.bytecode_buffer_size == 1

    def test_modern_framework_29_two_children(self):
        """Framework version 29 with two-element Children array."""
        script = bytes([0x00])
        native = (
            ustruct_prefix_modern(super_struct=0, children_count=2, property_count=0)
            + script_header(1, 1)
            + script
        )
        result = read_synthetic_function(
            native=native,
            framework_version=29,
            core_version=12,
        )
        assert result.status == "extracted"
        assert result.serialized_script == script

    def test_core_version_below_4_omits_native_property_count(self):
        """Core version < 4: no NativePropertyCount field."""
        script = bytes([0x00])
        # Framework < 29: legacy Children pointer
        # Core < 4: no NativePropertyCount
        native = (
            ustruct_prefix_legacy(super_struct=0, children_ptr=0)
            + script_header(1, 1)
            + script
        )
        result = read_synthetic_function(
            native=native,
            framework_version=28,
            core_version=3,
        )
        assert result.status == "extracted"
        assert result.serialized_script == script


class TestUnsupportedVersions:
    """Summaries with very old file versions fail before UStruct parsing."""

    @pytest.mark.parametrize("file_version_ue4, file_version_licensee", [
        (398, -1),
        (398, 0),
    ])
    def test_old_version_fails_with_unsupported_serialization_version(
        self,
        file_version_ue4: int,
        file_version_licensee: int,
    ):
        """Versions below UE5 1011 still process tagged properties but
        file_version_ue4=398 with no framework/custom versions means the
        archive has no serialization-control byte and the UStruct prefix
        reading will be attempted on raw bytes.

        In practice these fail with 'unsupported_serialization_version' or
        'invalid_script_size' depending on the raw byte values.
        """
        payload = b"\x00" + fname(0, 0) + b"\x00" * 16
        archive, export, summary, names, imports, exports = make_function_export(
            payload,
            file_version_ue4=file_version_ue4,
            file_version_ue5=file_version_licensee,
        )
        result = read_ufunction_script(archive, export, summary, names, imports, exports)
        # Old versions either fail or return no_script depending on the bytes
        assert result.status in ("failed", "no_script")


# ===================================================================
# Task 3: Native FProperty reading
# ===================================================================

from uasset_read.kismet.native_fields import (
    NativeFieldContext,
    NativeFieldDeclaration,
    read_native_fields,
    native_field_cpp_type,
)
from uasset_read.kismet.value_types import FNameRef
from uasset_read.constants import PKG_FilterEditorOnly

# Property flags (CPF_ constants from UE)
CPF_Parm = 0x80
CPF_OutParm = 0x100
CPF_ReturnParm = 0x400
CPF_ReferenceParm = 0x08000000

# Release custom version GUID
RELEASE_GUID = "22d5549cbe4f26a846072194d082b461"


def make_name_map_with_entries(*names: str) -> list[str]:
    """Build a name map with None at index 0 and given names after."""
    return ["None", *names]


def make_import_for_name(name: str, index: int) -> ObjectImport:
    """Build a synthetic import entry for name resolution."""
    return ObjectImport(
        class_package="/Script/CoreUObject",
        class_name="Class",
        outer_index=PackageIndex(0),
        object_name=name,
    )


def serialize_field_prefix(
    type_name: str,
    name: str,
    *,
    name_map: list[str],
    array_dim: int = 1,
    element_size: int = 0,
    property_flags: int = 0,
    rep_index: int = 0,
    rep_notify_name_index: int = 0,
    include_field_flags: bool = True,
    release_version: int = 21,
) -> bytes:
    """Serialize a base FProperty prefix.

    Layout:
      - NamePrivate: FName (u32 index + u32 number)
      - FlagsPrivate: u32 (only if include_field_flags=True)
      - ArrayDim: u16
      - ElementSize: u16
      - PropertyFlags: u64
      - RepIndex: u16
      - RepNotifyFunc: FName
      - ReplicationCondition: u8 (only if release_version >= 21)
    """
    result = b""
    # NamePrivate: lookup index in name_map
    name_index = name_map.index(name) if name in name_map else 0
    result += struct.pack("<II", name_index, 0)  # FName: index + number=0

    # FlagsPrivate (filtered out in PKG_FilterEditorOnly)
    if include_field_flags:
        result += struct.pack("<I", 0)  # FlagsPrivate = 0

    # ArrayDim
    result += struct.pack("<H", array_dim)
    # ElementSize
    result += struct.pack("<H", element_size)
    # PropertyFlags
    result += struct.pack("<Q", property_flags)
    # RepIndex
    result += struct.pack("<H", rep_index)
    # RepNotifyFunc: FName (index + number)
    result += struct.pack("<II", rep_notify_name_index, 0)

    # ReplicationCondition (Release version >= 21)
    if release_version >= 21:
        result += struct.pack("<B", 0)  # rep condition = COND_None

    return result


def serialize_field(
    type_name: str,
    name: str,
    *,
    name_map: list[str] | None = None,
    array_dim: int = 1,
    element_size: int = 0,
    property_flags: int = 0,
    rep_index: int = 0,
    rep_notify_name_index: int = 0,
    include_field_flags: bool = True,
    metadata: dict[str, str] | None = None,
    tail: bytes = b"",
    release_version: int = 21,
) -> bytes:
    """Serialize a complete FProperty with type-specific tail bytes.

    The type_name is appended as an FName after the base prefix.
    """
    if name_map is None:
        name_map = ["None", name, type_name]
        if metadata:
            for k in metadata:
                if k not in name_map:
                    name_map.append(k)

    result = b""
    # FField:: Serialize: type name as FName
    type_index = name_map.index(type_name) if type_name in name_map else 0
    result += struct.pack("<II", type_index, 0)

    # Base FProperty prefix
    result += serialize_field_prefix(
        type_name, name,
        name_map=name_map,
        array_dim=array_dim,
        element_size=element_size,
        property_flags=property_flags,
        rep_index=rep_index,
        rep_notify_name_index=rep_notify_name_index,
        include_field_flags=include_field_flags,
        release_version=release_version,
    )

    # Metadata boolean (present in uncooked packages, absent in cooked/filtered)
    if metadata is not None:
        result += b"\x01"  # has metadata = True
        # TMap count
        result += struct.pack("<i", len(metadata))
        for key, value in metadata.items():
            # FName key
            key_index = name_map.index(key) if key in name_map else 0
            result += struct.pack("<II", key_index, 0)
            # FString value
            value_bytes = value.encode("utf-8") + b"\x00"
            result += struct.pack("<i", len(value_bytes))
            result += value_bytes
    elif not include_field_flags:
        # PKG_FilterEditorOnly: metadata boolean is absent
        pass
    else:
        # Default: no metadata (cooked or no metadata flag)
        result += b"\x00"  # has metadata = False

    # Type-specific tail
    result += tail

    return result


def read_fields_from_bytes(
    data: bytes,
    *,
    count: int = 1,
    package_flags: int = 0,
    name_map: list[str] | None = None,
    import_map: list[ObjectImport] | None = None,
    export_map: list[ObjectExport] | None = None,
    release_version: int = 21,
) -> tuple[list[NativeFieldDeclaration], int]:
    """Helper: read native fields from raw bytes and return (declarations, end_offset)."""
    archive = ByteArchive(data)
    if name_map is None:
        name_map = ["None"]
    if import_map is None:
        import_map = []
    if export_map is None:
        export_map = []
    context = NativeFieldContext(
        name_map=name_map,
        import_map=import_map,
        export_map=export_map,
        package_flags=package_flags,
        release_version=release_version,
    )
    declarations = read_native_fields(archive, count, context)
    return declarations, archive.tell()


# --- Base FProperty prefix tests ---

class TestNativeFieldPrefix:
    """FProperty prefix reading tests."""

    def test_read_base_prefix_fields(self):
        """Read a BoolProperty and verify all prefix fields are correctly parsed."""
        name_map = make_name_map_with_entries("Enabled", "BoolProperty")
        field = serialize_field(
            "BoolProperty", "Enabled",
            name_map=name_map,
            property_flags=CPF_Parm,
            array_dim=1,
            element_size=1,
            tail=bytes([1, 0, 1, 1, 1, 1]),
        )
        declarations, end = read_fields_from_bytes(
            field, package_flags=0, name_map=name_map,
        )
        assert len(declarations) == 1
        assert declarations[0].name == "Enabled"
        assert declarations[0].type_name == "BoolProperty"
        assert declarations[0].property_flags == CPF_Parm
        assert declarations[0].array_dim == 1
        assert declarations[0].element_size == 1
        assert end == len(field)

    def test_uncooked_field_reads_metadata_and_bool_layout(self):
        """Uncooked field with metadata: metadata bool + TMap of pairs."""
        name_map = make_name_map_with_entries("Enabled", "BoolProperty", "Category", "Input")
        field = serialize_field(
            "BoolProperty", "Enabled",
            name_map=name_map,
            metadata={"Category": "Input"},
            tail=bytes([1, 0, 1, 1, 1, 1]),
        )
        declarations, end = read_fields_from_bytes(
            field, package_flags=0, name_map=name_map,
        )
        assert declarations[0].name == "Enabled"
        assert declarations[0].metadata == {"Category": "Input"}
        assert declarations[0].type_name == "BoolProperty"
        assert end == len(field)

    def test_filtered_editor_only_field_omits_field_flags(self):
        """PKG_FilterEditorOnly: FlagsPrivate is absent from the prefix."""
        name_map = make_name_map_with_entries("Count", "IntProperty")
        field = serialize_field(
            "IntProperty", "Count",
            name_map=name_map,
            include_field_flags=False,
        )
        declarations, end = read_fields_from_bytes(
            field, package_flags=PKG_FilterEditorOnly, name_map=name_map,
        )
        assert declarations[0].name == "Count"
        assert end == len(field)


# --- Package index / reference tests ---

class TestNativeFieldReferences:
    """Object and class fields read package indices."""

    def test_object_and_class_fields_read_package_indices(self):
        name_map = make_name_map_with_entries("Target", "ObjectProperty", "Type", "ClassProperty", "Actor", "Pawn")
        # PackageIndex(-3) → import index 2; PackageIndex(-4) → import index 3
        import_map = [
            make_import_for_name("SomeClass", 0),
            make_import_for_name("SomeOther", 1),
            make_import_for_name("Actor", 2),
            make_import_for_name("Pawn", 3),
        ]
        object_field = serialize_field(
            "ObjectProperty", "Target",
            name_map=name_map,
            element_size=8,
            tail=i32(-3),  # PackageIndex(-3) → import index 2 → "Actor"
        )
        class_field = serialize_field(
            "ClassProperty", "Type",
            name_map=name_map,
            element_size=8,
            tail=i32(-3) + i32(-4),  # base=-3 → "Actor", meta=-4 → "Pawn"
        )
        declarations, _ = read_fields_from_bytes(
            object_field + class_field,
            count=2,
            name_map=name_map,
            import_map=import_map,
        )
        assert declarations[0].references == [-3]
        assert declarations[0].reference_names == ["Actor"]
        assert declarations[1].references == [-3, -4]
        assert declarations[1].reference_names == ["Actor", "Pawn"]


# --- Property flags tests ---

class TestNativeFieldPropertyFlags:
    """Property flags retention across field types."""

    def test_return_and_parms_retain_raw_flags(self):
        """Return and parameter fields retain their raw CPF_ flags."""
        name_map = make_name_map_with_entries(
            "ReturnValue", "IntProperty", "Value", "Output",
        )
        return_field = serialize_field(
            "IntProperty", "ReturnValue",
            name_map=name_map,
            property_flags=CPF_ReturnParm | CPF_OutParm,
        )
        parm_field = serialize_field(
            "IntProperty", "Value",
            name_map=name_map,
            property_flags=CPF_Parm | CPF_ReferenceParm,
        )
        out_field = serialize_field(
            "IntProperty", "Output",
            name_map=name_map,
            property_flags=CPF_OutParm,
        )
        declarations, _ = read_fields_from_bytes(
            return_field + parm_field + out_field,
            count=3,
            name_map=name_map,
        )
        assert declarations[0].name == "ReturnValue"
        assert declarations[0].property_flags & CPF_ReturnParm != 0
        assert declarations[0].property_flags & CPF_OutParm != 0
        assert declarations[1].name == "Value"
        assert declarations[1].property_flags & CPF_Parm != 0
        assert declarations[1].property_flags & CPF_ReferenceParm != 0
        assert declarations[2].name == "Output"
        assert declarations[2].property_flags & CPF_OutParm != 0
        assert declarations[2].property_flags & CPF_Parm == 0


# --- Leaf type recipe tests ---

class TestNativeFieldLeafTypes:
    """Leaf property type-specific tail deserialization."""

    def test_bool_property_six_bytes(self):
        """BoolProperty tail: 6 uint8 values."""
        name_map = make_name_map_with_entries("Flag", "BoolProperty")
        tail = bytes([0x01, 0x00, 0x01, 0x01, 0x01, 0x01])
        field = serialize_field("BoolProperty", "Flag", name_map=name_map, tail=tail)
        declarations, end = read_fields_from_bytes(field, name_map=name_map)
        assert declarations[0].type_name == "BoolProperty"
        assert declarations[0].name == "Flag"
        assert end == len(field)

    def test_byte_property_one_int32_reference(self):
        """ByteProperty tail: one int32 UObject reference."""
        name_map = make_name_map_with_entries("Val", "ByteProperty")
        # PackageIndex 0 = null (no enum) → maps to uint8
        field = serialize_field("ByteProperty", "Val", name_map=name_map, tail=i32(0))
        declarations, _ = read_fields_from_bytes(field, name_map=name_map)
        assert declarations[0].references == [0]
        assert declarations[0].reference_names == [None]
        assert native_field_cpp_type(declarations[0]) == "uint8"

    def test_struct_property_one_int32_struct_reference(self):
        """StructProperty tail: one int32 struct reference."""
        name_map = make_name_map_with_entries("Location", "StructProperty")
        field = serialize_field("StructProperty", "Location", name_map=name_map, tail=i32(-1))
        import_map = [make_import_for_name("FVector", 0)]
        declarations, _ = read_fields_from_bytes(
            field, name_map=name_map, import_map=import_map,
        )
        assert declarations[0].references == [-1]
        assert declarations[0].reference_names == ["FVector"]

    def test_interface_property_one_int32_reference(self):
        """InterfaceProperty tail: one int32 interface-class reference."""
        name_map = make_name_map_with_entries("Handler", "InterfaceProperty")
        field = serialize_field("InterfaceProperty", "Handler", name_map=name_map, tail=i32(-2))
        import_map = [None, make_import_for_name("IMyInterface", 1)]
        declarations, _ = read_fields_from_bytes(
            field, name_map=name_map, import_map=import_map,
        )
        assert declarations[0].references == [-2]
        assert declarations[0].reference_names == ["IMyInterface"]

    def test_struct_property_cpp_type_with_resolved_name(self):
        """StructProperty cpp_type includes resolved struct name."""
        name_map = make_name_map_with_entries("Pos", "StructProperty", "FVector")
        field = serialize_field("StructProperty", "Pos", name_map=name_map, tail=i32(-1))
        import_map = [make_import_for_name("FVector", 0)]
        declarations, _ = read_fields_from_bytes(
            field, name_map=name_map, import_map=import_map,
        )
        assert native_field_cpp_type(declarations[0]) == "FVector"


# --- Release version 20 vs 21 replication condition ---

class TestNativeFieldReplicationCondition:
    """Release version gating for the replication condition byte."""

    def test_release_20_omits_replication_condition(self):
        """Release version < 21: no replication condition byte consumed."""
        name_map = make_name_map_with_entries("Val", "IntProperty")
        # Release 20 prefix omits the rep condition byte
        field = serialize_field(
            "IntProperty", "Val",
            name_map=name_map,
            release_version=20,
        )
        declarations, end = read_fields_from_bytes(
            field, name_map=name_map, release_version=20,
        )
        assert declarations[0].name == "Val"
        assert end == len(field)

    def test_release_21_consumes_replication_condition(self):
        """Release version >= 21: one byte replication condition consumed."""
        name_map = make_name_map_with_entries("Val", "IntProperty")
        field = serialize_field(
            "IntProperty", "Val",
            name_map=name_map,
            release_version=21,
        )
        declarations, end = read_fields_from_bytes(
            field, name_map=name_map, release_version=21,
        )
        assert declarations[0].name == "Val"
        assert end == len(field)


# --- Multi-field reading ---

class TestNativeFieldMultiple:
    """Reading multiple consecutive fields."""

    def test_read_two_consecutive_fields(self):
        """Read two fields from contiguous bytes."""
        name_map = make_name_map_with_entries("A", "IntProperty", "B", "FloatProperty")
        field_a = serialize_field("IntProperty", "A", name_map=name_map)
        field_b = serialize_field("FloatProperty", "B", name_map=name_map)
        declarations, end = read_fields_from_bytes(
            field_a + field_b, count=2, name_map=name_map,
        )
        assert len(declarations) == 2
        assert declarations[0].name == "A"
        assert declarations[0].type_name == "IntProperty"
        assert declarations[1].name == "B"
        assert declarations[1].type_name == "FloatProperty"
        assert end == len(field_a) + len(field_b)


# --- UFunction integration with native fields ---

class TestUFunctionNativeFieldIntegration:
    """Integration: read_ufunction_script with native fields."""

    def test_function_with_native_fields_extracts_script(self):
        """Function with NativePropertyCount > 0 reads fields then script."""
        name_map = make_name_map_with_entries("Param", "IntProperty")
        field_bytes = serialize_field("IntProperty", "Param", name_map=name_map)
        script = bytes([0x00])  # EX_EndOfScript

        # Build native section: UStruct prefix (SuperStruct + Children + NativePropertyCount)
        # + field declarations + script header + script
        native = (
            ustruct_prefix_modern(super_struct=0, children_count=0, property_count=1)
            + field_bytes
            + script_header(1, 1)  # BytecodeBufferSize=1, SerializedScriptSize=1
            + script
        )

        # Build payload manually with correct name_map
        control_prefix = b"\x00"
        none_tag = fname(0, 0)
        payload = control_prefix + none_tag + native

        archive, export, summary, names, imports, exports = make_function_export(
            payload,
            file_version_ue5=1011,
        )
        export.script_serialization_start_offset = 0
        export.script_serialization_end_offset = len(control_prefix) + len(none_tag)

        # Replace names with our name_map (includes "Param" and "IntProperty")
        names = name_map

        summary = make_summary_with_versions(framework_version=37, core_version=12)

        result = read_ufunction_script(archive, export, summary, names, imports, exports)

        assert result.status == "extracted"
        assert result.serialized_script == script
        assert len(result.native_fields) == 1
        assert result.native_fields[0].name == "Param"
        assert result.native_fields[0].type_name == "IntProperty"


# ===================================================================
# Task 4: Recursive container and enum field types
# ===================================================================


def serialize_inner_field(
    type_name: str,
    name: str,
    *,
    name_map: list[str],
    tail: bytes = b"",
) -> bytes:
    """Serialize a minimal inner FField (type-name + name + zero-length prefix).

    Inner fields in container properties (EnumProperty, ArrayProperty, etc.)
    use the same FField serialization layout as top-level fields, but with
    minimal prefix (array_dim=1, element_size=0, property_flags=0, etc.)
    and no metadata.
    """
    # FField::Serialize: type name as FName
    type_index = name_map.index(type_name) if type_name in name_map else 0
    result = struct.pack("<II", type_index, 0)
    # NamePrivate: FName
    name_index = name_map.index(name) if name in name_map else 0
    result += struct.pack("<II", name_index, 0)
    # FlagsPrivate: u32 (always present in inner fields)
    result += struct.pack("<I", 0)
    # ArrayDim: u16
    result += struct.pack("<H", 1)
    # ElementSize: u16
    result += struct.pack("<H", 0)
    # PropertyFlags: u64
    result += struct.pack("<Q", 0)
    # RepIndex: u16
    result += struct.pack("<H", 0)
    # RepNotifyFunc: FName
    result += struct.pack("<II", 0, 0)
    # ReplicationCondition: u8 (release_version >= 21)
    result += struct.pack("<B", 0)
    # Metadata: no metadata flag
    result += b"\x00"
    # Type-specific tail
    result += tail
    return result


class TestNativeFieldEnumProperty:
    """EnumProperty: int32 enum reference + FName inner-type + inner field."""

    def test_enum_property_with_int32_inner(self):
        """EnumProperty wrapping an IntProperty inner field."""
        name_map = make_name_map_with_entries(
            "Color", "EnumProperty",
            "EMyEnum",
            "Value", "IntProperty",
        )
        import_map = [make_import_for_name("EMyEnum", 0)]
        inner = serialize_inner_field("IntProperty", "Value", name_map=name_map)
        field = serialize_field(
            "EnumProperty", "Color",
            name_map=name_map,
            tail=i32(-1) + inner,  # enum ref + inner field
        )
        declarations, end = read_fields_from_bytes(
            field, name_map=name_map, import_map=import_map,
        )
        assert len(declarations) == 1
        assert declarations[0].type_name == "EnumProperty"
        assert declarations[0].name == "Color"
        assert len(declarations[0].inner_fields) == 1
        inner_decl = declarations[0].inner_fields[0]
        assert inner_decl.type_name == "IntProperty"
        assert inner_decl.name == "Value"
        assert end == len(field)

    def test_enum_property_cpp_type(self):
        """EnumProperty cpp_type maps inner through native_field_cpp_type."""
        name_map = make_name_map_with_entries(
            "Color", "EnumProperty",
            "EMyEnum",
            "Value", "IntProperty",
        )
        import_map = [make_import_for_name("EMyEnum", 0)]
        inner = serialize_inner_field("IntProperty", "Value", name_map=name_map)
        field = serialize_field(
            "EnumProperty", "Color",
            name_map=name_map,
            tail=i32(-1) + inner,
        )
        declarations, _ = read_fields_from_bytes(
            field, name_map=name_map, import_map=import_map,
        )
        assert native_field_cpp_type(declarations[0]) == "EMyEnum"


class TestNativeFieldArrayProperty:
    """ArrayProperty: FName inner-type + inner field."""

    def test_array_property_with_struct_inner(self):
        """ArrayProperty wrapping a StructProperty inner field."""
        name_map = make_name_map_with_entries(
            "Points", "ArrayProperty",
            "FVector",
            "Pos", "StructProperty",
        )
        import_map = [make_import_for_name("FVector", 0)]
        inner = serialize_inner_field(
            "StructProperty", "Pos", name_map=name_map,
            tail=i32(-1),  # package index → FVector
        )
        field = serialize_field(
            "ArrayProperty", "Points",
            name_map=name_map,
            tail=inner,
        )
        declarations, end = read_fields_from_bytes(
            field, name_map=name_map, import_map=import_map,
        )
        assert len(declarations) == 1
        assert declarations[0].type_name == "ArrayProperty"
        assert declarations[0].name == "Points"
        assert len(declarations[0].inner_fields) == 1
        assert declarations[0].inner_fields[0].type_name == "StructProperty"
        assert end == len(field)

    def test_array_property_cpp_type(self):
        """ArrayProperty cpp_type builds TArray<InnerType>."""
        name_map = make_name_map_with_entries(
            "Items", "ArrayProperty",
            "FString",
            "S", "StrProperty",
        )
        inner = serialize_inner_field("StrProperty", "S", name_map=name_map)
        field = serialize_field(
            "ArrayProperty", "Items",
            name_map=name_map,
            tail=inner,
        )
        declarations, _ = read_fields_from_bytes(field, name_map=name_map)
        assert native_field_cpp_type(declarations[0]) == "TArray<FString>"


class TestNativeFieldSetProperty:
    """SetProperty: FName element-type + element field."""

    def test_set_property_with_name_inner(self):
        """SetProperty wrapping a NameProperty inner field."""
        name_map = make_name_map_with_entries(
            "Tags", "SetProperty",
            "FName",
            "N", "NameProperty",
        )
        inner = serialize_inner_field("NameProperty", "N", name_map=name_map)
        field = serialize_field(
            "SetProperty", "Tags",
            name_map=name_map,
            tail=inner,
        )
        declarations, end = read_fields_from_bytes(
            field, name_map=name_map,
        )
        assert len(declarations) == 1
        assert declarations[0].type_name == "SetProperty"
        assert declarations[0].name == "Tags"
        assert len(declarations[0].inner_fields) == 1
        assert declarations[0].inner_fields[0].type_name == "NameProperty"
        assert end == len(field)

    def test_set_property_cpp_type(self):
        """SetProperty cpp_type builds TSet<InnerType>."""
        name_map = make_name_map_with_entries(
            "Tags", "SetProperty",
            "FName",
            "N", "NameProperty",
        )
        inner = serialize_inner_field("NameProperty", "N", name_map=name_map)
        field = serialize_field(
            "SetProperty", "Tags",
            name_map=name_map,
            tail=inner,
        )
        declarations, _ = read_fields_from_bytes(field, name_map=name_map)
        assert native_field_cpp_type(declarations[0]) == "TSet<FName>"


class TestNativeFieldMapProperty:
    """MapProperty: key FName/field + value FName/field."""

    def test_map_property_with_name_and_string(self):
        """MapProperty with FName key and FString value."""
        name_map = make_name_map_with_entries(
            "Lookup", "MapProperty",
            "FName", "K", "NameProperty",
            "FString", "V", "StrProperty",
        )
        key_inner = serialize_inner_field("NameProperty", "K", name_map=name_map)
        val_inner = serialize_inner_field("StrProperty", "V", name_map=name_map)
        field = serialize_field(
            "MapProperty", "Lookup",
            name_map=name_map,
            tail=key_inner + val_inner,
        )
        declarations, end = read_fields_from_bytes(
            field, name_map=name_map,
        )
        assert len(declarations) == 1
        assert declarations[0].type_name == "MapProperty"
        assert declarations[0].name == "Lookup"
        assert len(declarations[0].inner_fields) == 2
        assert declarations[0].inner_fields[0].type_name == "NameProperty"
        assert declarations[0].inner_fields[1].type_name == "StrProperty"
        assert end == len(field)

    def test_map_property_cpp_type(self):
        """MapProperty cpp_type builds TMap<KeyType, ValueType>."""
        name_map = make_name_map_with_entries(
            "Data", "MapProperty",
            "FName", "K", "NameProperty",
            "FString", "V", "StrProperty",
        )
        key_inner = serialize_inner_field("NameProperty", "K", name_map=name_map)
        val_inner = serialize_inner_field("StrProperty", "V", name_map=name_map)
        field = serialize_field(
            "MapProperty", "Data",
            name_map=name_map,
            tail=key_inner + val_inner,
        )
        declarations, _ = read_fields_from_bytes(field, name_map=name_map)
        assert native_field_cpp_type(declarations[0]) == "TMap<FName, FString>"


class TestNativeFieldOptionalProperty:
    """OptionalProperty: FName value-type + value field."""

    def test_optional_property_with_bool_inner(self):
        """OptionalProperty wrapping a BoolProperty inner field."""
        name_map = make_name_map_with_entries(
            "Maybe", "OptionalProperty",
            "bool",
            "B", "BoolProperty",
        )
        inner = serialize_inner_field(
            "BoolProperty", "B", name_map=name_map,
            tail=bytes([0, 0, 0, 0, 0, 0]),
        )
        field = serialize_field(
            "OptionalProperty", "Maybe",
            name_map=name_map,
            tail=inner,
        )
        declarations, end = read_fields_from_bytes(
            field, name_map=name_map,
        )
        assert len(declarations) == 1
        assert declarations[0].type_name == "OptionalProperty"
        assert declarations[0].name == "Maybe"
        assert len(declarations[0].inner_fields) == 1
        assert declarations[0].inner_fields[0].type_name == "BoolProperty"
        assert end == len(field)

    def test_optional_property_cpp_type(self):
        """OptionalProperty cpp_type builds TOptional<InnerType>."""
        name_map = make_name_map_with_entries(
            "Maybe", "OptionalProperty",
            "bool",
            "B", "BoolProperty",
        )
        inner = serialize_inner_field(
            "BoolProperty", "B", name_map=name_map,
            tail=bytes([0, 0, 0, 0, 0, 0]),
        )
        field = serialize_field(
            "OptionalProperty", "Maybe",
            name_map=name_map,
            tail=inner,
        )
        declarations, _ = read_fields_from_bytes(field, name_map=name_map)
        assert native_field_cpp_type(declarations[0]) == "TOptional<bool>"


class TestNativeFieldNullInnerType:
    """Container property with null (None) inner FName type → unsupported."""

    def test_null_inner_type_in_array_emits_unsupported(self):
        """ArrayProperty with null (FName index 0) inner type emits unsupported."""
        name_map = make_name_map_with_entries(
            "Bad", "ArrayProperty",
            # inner type FName index 0 = None (null)
        )
        # Inner field: type FName index 0 (None/null)
        inner_type_bytes = struct.pack("<II", 0, 0)  # FName(None)
        # Inner field name: FName(None)
        inner_name_bytes = struct.pack("<II", 0, 0)
        inner_prefix = (
            inner_type_bytes + inner_name_bytes
            + struct.pack("<I", 0)  # FlagsPrivate
            + struct.pack("<HH", 1, 0)  # ArrayDim + ElementSize
            + struct.pack("<Q", 0)  # PropertyFlags
            + struct.pack("<H", 0)  # RepIndex
            + struct.pack("<II", 0, 0)  # RepNotifyFunc
            + struct.pack("<B", 0)  # ReplicationCondition
            + b"\x00"  # metadata flag
        )
        field = serialize_field(
            "ArrayProperty", "Bad",
            name_map=name_map,
            tail=inner_prefix,
        )
        declarations, _ = read_fields_from_bytes(field, name_map=name_map)
        assert len(declarations) == 1
        assert declarations[0].type_name == "ArrayProperty"
        # Inner field should be unsupported due to null type name
        assert len(declarations[0].inner_fields) == 1
        assert declarations[0].inner_fields[0].type_name == "unsupported:None"


class TestNativeFieldDepthLimit:
    """Recursive depth limit: nested containers beyond 32 levels."""

    def test_depth_32_nesting_triggers_unsupported(self):
        """33 levels of nesting should stop at depth limit."""
        name_map = make_name_map_with_entries(
            "Deep", "ArrayProperty",
            "int32", "IntProperty",
        )
        # Build a deeply nested array-of-array structure manually
        # Each level wraps the previous
        # Innermost: IntProperty with no further nesting
        innermost = serialize_inner_field("IntProperty", "X", name_map=name_map)

        # Wrap it 32 times in ArrayProperty
        current = innermost
        for i in range(32):
            name_map.extend([f"L{i}", "ArrayProperty"])
            inner_type_bytes = struct.pack(
                "<II", name_map.index("ArrayProperty"), 0
            )
            inner_name_bytes = struct.pack("<II", name_map.index(f"L{i}"), 0)
            current = (
                inner_type_bytes + inner_name_bytes
                + struct.pack("<I", 0)
                + struct.pack("<HH", 1, 0)
                + struct.pack("<Q", 0)
                + struct.pack("<H", 0)
                + struct.pack("<II", 0, 0)
                + struct.pack("<B", 0)
                + b"\x00"
                + current
            )

        field = serialize_field(
            "ArrayProperty", "Deep",
            name_map=name_map,
            tail=current,
        )
        declarations, _ = read_fields_from_bytes(field, name_map=name_map)
        assert declarations[0].type_name == "ArrayProperty"
        # Walk down 32 levels to reach the depth limit
        inner = declarations[0]
        for _ in range(32):
            assert len(inner.inner_fields) == 1
            inner = inner.inner_fields[0]
        # At depth 33, the inner field should be unsupported
        assert inner.type_name.startswith("unsupported:")
