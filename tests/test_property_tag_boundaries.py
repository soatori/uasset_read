from __future__ import annotations

import struct
from pathlib import Path

from uasset_read.archive import FArchive
from uasset_read.constants import PROP_TAG_BOOL_TRUE
from uasset_read.models.properties import PropertyTag
from uasset_read.parsers.property_types import parse_struct_property


def _make_archive(tmp_path: Path, data: bytes) -> FArchive:
    path = tmp_path / "property.bin"
    path.write_bytes(data)
    return FArchive(str(path), tolerant=True)


def _tag(name: str, struct_type: str, size: int) -> PropertyTag:
    return PropertyTag(
        name=name,
        type="StructProperty",
        size=size,
        struct_type=struct_type,
        value_start_offset=0,
        value_end_offset=size,
    )


def _fname(index: int, number: int = 0) -> bytes:
    return struct.pack("<II", index, number)


def _type_node(name_index: int, inner_count: int = 0) -> bytes:
    return _fname(name_index) + struct.pack("<i", inner_count)


def _property_tag(name_index: int, type_index: int, size: int, flags: int = 0) -> bytes:
    return _fname(name_index) + _type_node(type_index) + struct.pack("<iB", size, flags)


def test_native_struct_fast_path_ends_at_value_boundary(tmp_path: Path) -> None:
    data = struct.pack("<IIII", 1, 2, 3, 4)
    archive = _make_archive(tmp_path, data)
    try:
        value = parse_struct_property(_tag("BlueprintGuid", "Guid", 16), archive, [], [])
        assert value.struct_type == "Guid"
        assert value.fields == {"A": 1, "B": 2, "C": 3, "D": 4}
        assert archive.tell() == 16
    finally:
        archive.close()


def test_unknown_struct_is_opaque_and_does_not_read_fake_property_tags(tmp_path: Path) -> None:
    data = b"\x00" * 4 + b"\x01\x02\x03\x04"
    archive = _make_archive(tmp_path, data)
    try:
        value = parse_struct_property(_tag("Mystery", "UnknownNativeStruct", len(data)), archive, [], [])
        assert value.struct_type == "UnknownNativeStruct"
        assert value.fields == {}
        assert value.raw_size == len(data)
        assert value.parse_status == "opaque"
        assert archive.tell() == len(data)
    finally:
        archive.close()


def test_member_reference_tagged_fallback_still_parses_fields(tmp_path: Path) -> None:
    name_map = [
        "MemberName",
        "NameProperty",
        "Jump",
        "bSelfContext",
        "BoolProperty",
        "MemberParent",
        "ObjectProperty",
        "None",
    ]
    data = b"".join(
        [
            _property_tag(0, 1, 8),
            _fname(2),
            _property_tag(3, 4, 0, PROP_TAG_BOOL_TRUE),
            _property_tag(5, 6, 4),
            struct.pack("<i", -1),
            _fname(7),
        ]
    )
    archive = _make_archive(tmp_path, data)
    try:
        value = parse_struct_property(_tag("FunctionReference", "MemberReference", len(data)), archive, name_map, [])
        assert value.struct_type == "MemberReference"
        assert value.fields["MemberName"] == "Jump"
        assert value.fields["bSelfContext"] is True
        assert value.fields["MemberParent"] == -1
        assert value.parse_status == "parsed"
        assert archive.tell() == len(data)
    finally:
        archive.close()
