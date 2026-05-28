from __future__ import annotations

import struct
from pathlib import Path

from uasset_read.archive import FArchive
from uasset_read.serializers.graph import read_pin_array, read_pin_reference
from uasset_read.serializers.object_resources import ObjectExport, ObjectImport, PackageIndex


def _make_archive(tmp_path: Path, data: bytes) -> FArchive:
    path = tmp_path / "pin.bin"
    path.write_bytes(data)
    return FArchive(str(path), tolerant=True)


def _make_export(name: str) -> ObjectExport:
    return ObjectExport(
        class_index=PackageIndex(0),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name=name,
        object_flags=0,
        serial_size=0,
        serial_offset=0,
    )


def test_read_pin_reference_null(tmp_path: Path) -> None:
    archive = _make_archive(tmp_path, struct.pack("<i", 1))
    try:
        ref = read_pin_reference(archive, [], [], [])
        assert ref is None
        assert archive.tell() == 4
    finally:
        archive.close()


def test_read_pin_reference_non_null_parent_and_pass_through(tmp_path: Path) -> None:
    guid = bytes.fromhex("00112233445566778899AABBCCDDEEFF")
    data = struct.pack("<ii", 0, 1) + guid + struct.pack("<ii", 0, -1) + guid
    archive = _make_archive(tmp_path, data)
    export_map = [_make_export("NodeA")]
    import_map = [ObjectImport("/Script/CoreUObject", "Class", PackageIndex(0), "ImportNode")]
    try:
        parent_ref = read_pin_reference(archive, [], export_map, import_map)
        pass_ref = read_pin_reference(archive, [], export_map, import_map)
        assert parent_ref == {
            "owning_node": "NodeA",
            "pin_guid": guid.hex().upper(),
            "_pin_guid_valid": True,
        }
        assert pass_ref == {
            "owning_node": "ImportNode",
            "pin_guid": guid.hex().upper(),
            "_pin_guid_valid": True,
        }
    finally:
        archive.close()


def test_read_pin_array_reads_linkedto_and_subpins(tmp_path: Path) -> None:
    guid_a = bytes.fromhex("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
    guid_b = bytes.fromhex("BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB")
    data = b"".join(
        [
            struct.pack("<i", 1),
            struct.pack("<ii", 0, 1),
            guid_a,
            struct.pack("<i", 2),
            struct.pack("<ii", 0, 2),
            guid_a,
            struct.pack("<ii", 0, 1),
            guid_b,
        ]
    )
    archive = _make_archive(tmp_path, data)
    export_map = [_make_export("NodeA"), _make_export("NodeB")]
    try:
        linked_to = read_pin_array(archive, [], export_map, [], None)
        subpins = read_pin_array(archive, [], export_map, [], None)
        assert linked_to == [
            {
                "owning_node": "NodeA",
                "pin_guid": guid_a.hex().upper(),
                "_pin_guid_valid": True,
            }
        ]
        assert subpins == [
            {
                "owning_node": "NodeB",
                "pin_guid": guid_a.hex().upper(),
                "_pin_guid_valid": True,
            },
            {
                "owning_node": "NodeA",
                "pin_guid": guid_b.hex().upper(),
                "_pin_guid_valid": True,
            },
        ]
    finally:
        archive.close()
