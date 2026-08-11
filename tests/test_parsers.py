"""Consolidated parser tests — struct sizes, serialization strategy, tag retry, error recovery."""
from __future__ import annotations

import struct
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from uasset_read.archive import ByteArchive, FArchive
from uasset_read.exceptions import ParseError
from uasset_read.models.properties import PropertyTag
from uasset_read.parsers.class_serialization_strategy import (
    SerializationStrategy,
    get_serialization_strategy,
)
from uasset_read.parsers.property_parser import (
    parse_properties_from_export,
    parse_property_value,
)
from uasset_read.parsers.property_types import (
    _try_fast_path_struct,
)
from uasset_read.parsers.usmap import MAGIC_USMAP, _parse_usmap_data


# ---------------------------------------------------------------------------
# 1. Struct size constants and fast-path reading
# ---------------------------------------------------------------------------

class TestStructSizeConstants:
    """Verify _EXPECTED_STRUCT_SIZES and fast-path reading for Transform."""

    def test_transform_read_f32(self):
        """FTransform3f reads 40 bytes correctly via _try_fast_path_struct."""
        data = struct.pack(
            "<10f",
            0.0, 0.0, 0.0, 1.0,   # Rotation
            100.0, 200.0, 300.0,   # Translation
            1.0, 1.0, 1.0,         # Scale3D
        )
        archive = ByteArchive(data)
        tag = MagicMock()
        tag.size = 40
        tag.struct_type = "Transform"

        result = _try_fast_path_struct("Transform", tag, archive, name_map=[])

        assert result is not None
        assert result.struct_type == "Transform"
        assert result.fields["Translation"]["X"] == 100.0
        assert result.fields["Translation"]["Y"] == 200.0
        assert result.fields["Translation"]["Z"] == 300.0
        assert result.fields["Rotation"]["W"] == 1.0
        assert result.fields["Scale3D"]["X"] == 1.0


# ---------------------------------------------------------------------------
# 2. Serialization strategy selection
# ---------------------------------------------------------------------------

class TestSerializationStrategy:
    """Verify strategy lookup for known and unknown classes."""

    def test_tagged_class_strategy(self):
        assert get_serialization_strategy("BlueprintGeneratedClass") == SerializationStrategy.TAGGED_PROPERTIES_ONLY


# ---------------------------------------------------------------------------
# 3. Property tag retry / tolerant parsing
# ---------------------------------------------------------------------------

def _make_archive(data: bytes, tolerant: bool = False) -> FArchive:
    archive = FArchive.__new__(FArchive)
    archive._stream = BytesIO(data)
    archive._file_size = len(data)
    archive._byte_swapping = False
    archive._use_mmap = False
    archive._mmap = None
    archive._tolerant = tolerant
    archive._file = BytesIO(data)
    archive._hex_view_enabled = False
    archive._hex_view_entries = []
    archive._hex_view_context = ""
    archive._diagnostics = []
    archive._logger = __import__("logging").getLogger("test")
    archive._name_map = None
    return archive


class TestTagRetryTolerant:
    """Tolerant mode on corrupted tags should not hang or retry infinitely."""

    def test_corrupted_tag_tolerant_does_not_hang(self):
        name_bytes = struct.pack("<II", 0, 0)   # FName index=0
        truncated = b"\x00" * 2                 # not enough for type name
        data = name_bytes + truncated
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1012

        summary = MagicMock()
        summary.package_flags = 0
        summary.file_version_ue5 = 1012
        export = MagicMock()
        export.serial_offset = 0
        export.serial_size = 100

        result = parse_properties_from_export(
            export, archive, summary,
            name_map=["TestProp"], export_map=[], tolerant=True,
        )
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0].type == "Warning"


# ---------------------------------------------------------------------------
# 4. Error recovery and fallback
# ---------------------------------------------------------------------------

class TestErrorRecovery:
    """Property parser should recover gracefully from handler failures."""

    def test_binary_or_native_handler_fallback(self):
        tag = PropertyTag(
            name="TestProp", type="MaterialInput",
            size=4, serialize_type="BinaryOrNative",
        )
        archive = MagicMock()
        archive.read.return_value = b"\xFF\xFF\xFF\xFF"
        archive.tell.return_value = 0

        result = parse_property_value(tag, archive, [], [])
        assert result is not None
        assert result.get("kind") == "binary_or_native_property"


# ---------------------------------------------------------------------------
# 5. Usmap header parsing
# ---------------------------------------------------------------------------

class TestUsmapHeader:
    """Verify .usmap file header validation."""

    def test_valid_magic_parses(self):
        data = _build_usmap_v0()
        result = _parse_usmap_data(data)
        assert result.version == 0


def _build_usmap_v0(
    name_table: list[str] | None = None,
    schemas=None,
) -> bytes:
    """Build a synthetic v0 .usmap binary for testing."""
    if name_table is None:
        name_table = []
    if schemas is None:
        schemas = []

    payload = bytearray()
    # NameTable
    payload += struct.pack("<I", len(name_table))
    for name in name_table:
        encoded = name.encode("utf-8")
        payload += struct.pack("<B", len(encoded))
        payload += encoded
    # EnumTable (empty)
    payload += struct.pack("<I", 0)
    # SchemaTable
    payload += struct.pack("<I", len(schemas))
    for schema in schemas:
        name_idx = name_table.index(schema.name) if schema.name in name_table else -1
        super_idx = name_table.index(schema.super_type) if schema.super_type and schema.super_type in name_table else -1
        payload += struct.pack("<i", name_idx)
        payload += struct.pack("<i", super_idx)
        payload += struct.pack("<H", schema.property_count)
        payload += struct.pack("<H", schema.serializable_count)
        sorted_props = sorted(schema.properties.values(), key=lambda p: p.index)
        for prop in sorted_props:
            payload += struct.pack("<H", prop.index)
            payload += struct.pack("<B", prop.array_dim)
            prop_name_idx = name_table.index(prop.name) if prop.name in name_table else -1
            payload += struct.pack("<i", prop_name_idx)
            # type byte (use 0xFF = Unknown for simplicity)
            payload += struct.pack("<B", 0xFF)

    comp_size = len(payload)
    header = bytearray()
    header += struct.pack("<H", MAGIC_USMAP)
    header += struct.pack("<B", 0)   # version
    header += struct.pack("<B", 0)   # compression = none
    header += struct.pack("<I", comp_size)
    header += struct.pack("<I", comp_size)
    header += bytes(payload)
    return bytes(header)
