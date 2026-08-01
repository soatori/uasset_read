"""Tests for native UFunction Script reader — Issue #77 Task 1.

Covers:
- Custom version lookup with serialized GUID
- Export boundary enforcement and offset cross-checking
- UE5 version 1011 serialization control byte handling
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
        payload = serialization_control_none_terminator() + b"DATA"
        archive, export, summary, names, imports, exports = make_function_export(
            payload, file_version_ue5=1011,
        )
        export.script_serialization_start_offset = 0
        export.script_serialization_end_offset = len(serialization_control_none_terminator())

        result = read_ufunction_script(archive, export, summary, names, imports, exports)
        assert result.status == "extracted"
        assert result.serialized_script == b"DATA"

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
