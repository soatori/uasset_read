"""Phase 74 计划测试：UE/CUE4Parse PinReference 布局目标。

Phase 74 已实现：PinReference 布局已对齐 UE 源码 / CUE4Parse。
"""
from __future__ import annotations

import io
import struct
from unittest.mock import MagicMock

import pytest

from uasset_read.serializers.graph import (
    read_pin_array,
    read_pin_reference,
    read_ue_graph_pin,
    validate_pin_reference_at,
)
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex


class _BytesArchive:
    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)
        self._file_size = len(data)
        self.logger = MagicMock()

    def read(self, size: int) -> bytes:
        data = self._buf.read(size)
        if len(data) != size:
            raise EOFError(f"expected {size} bytes, got {len(data)}")
        return data

    def read_i32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def read_u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def read_u8(self) -> int:
        return struct.unpack("<B", self.read(1))[0]

    def read_bool(self) -> bool:
        value = self.read_u32()
        if value not in (0, 1):
            raise ValueError(f"invalid bool {value}")
        return value == 1

    def read_bytes(self, size: int) -> bytes:
        return self.read(size)

    def read_name(self, name_map: list[str]) -> str:
        index = self.read_u32()
        number = self.read_u32()
        if index >= len(name_map):
            return "None"
        name = name_map[index]
        return f"{name}_{number}" if number else name

    def seek(self, pos: int) -> None:
        self._buf.seek(pos)

    def tell(self) -> int:
        return self._buf.tell()


def _export_map(count: int = 4) -> list[ObjectExport]:
    return [
        ObjectExport(
            class_index=PackageIndex(0),
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name=f"Node{i + 1}",
            object_flags=0,
            serial_size=0,
            serial_offset=0,
        )
        for i in range(count)
    ]


def _pin_ref(owning_node: int = 1, guid_byte: int = 0xAB) -> bytes:
    return (
        struct.pack("<i", 0)
        + struct.pack("<i", owning_node)
        + bytes([guid_byte]) * 16
    )


def test_null_pin_reference_consumes_only_bool():
    archive = _BytesArchive(struct.pack("<i", 1) + b"\xAA" * 32)

    result = read_pin_reference(archive, [], _export_map(), [])

    assert result is None
    assert archive.tell() == 4


def test_non_null_pin_reference_consumes_bool_owning_node_and_guid():
    archive = _BytesArchive(_pin_ref(owning_node=1, guid_byte=0x11) + b"tail")

    result = read_pin_reference(archive, [], _export_map(), [])

    assert result is not None
    assert result["owning_node"] == "Node1"
    assert result["pin_guid"] == "11" * 16
    assert archive.tell() == 24


def test_validate_null_reference_accepts_four_byte_shape():
    archive = _BytesArchive(struct.pack("<i", 1))

    result = validate_pin_reference_at(archive, 0, _export_map(), [])

    assert result is not None
    assert result["valid"] is True
    assert result.get("serialized_size") == 4
    assert archive.tell() == 0


def test_pin_array_null_entry_does_not_swallow_next_entry():
    data = (
        struct.pack("<i", 2)
        + struct.pack("<i", 1)
        + _pin_ref(owning_node=2, guid_byte=0x22)
    )
    archive = _BytesArchive(data)

    result = read_pin_array(archive, [], _export_map(), [])

    assert len(result) == 1
    assert result[0]["owning_node"] == "Node2"
    assert archive.tell() == len(data)


def test_owning_pin_body_starts_at_pin_name_when_header_is_provided():
    # 最小 body：OwningNode+PinId(内部重复，被丢弃)、PinName(FName) 后跟 PinFriendlyName(None)、SourceIndex、Tooltip、
    # Direction、PinType、默认值、连接数组、Parent/Ref、PersistentGuid/BitField。
    name_map = ["execute", "exec", "None"]
    body = io.BytesIO()
    body.write(struct.pack("<i", 1))       # OwningNode (internal duplicate, discarded)
    body.write(b"\xAA" * 16)               # PinId (internal duplicate, discarded)
    body.write(struct.pack("<II", 0, 0))  # PinName = execute
    body.write(struct.pack("<iB", 0, 0xFF))  # PinFriendlyName flags+htype
    body.write(struct.pack("<I", 0))         # PinFriendlyName bHasCultureInvariantString
    body.write(struct.pack("<i", 0))  # SourceIndex
    body.write(struct.pack("<i", 0))  # PinToolTip
    body.write(struct.pack("<B", 0))  # Direction
    body.write(struct.pack("<II", 1, 0))  # PinType.PinCategory = exec
    body.write(struct.pack("<II", 2, 0))  # PinType.PinSubCategory = None
    body.write(struct.pack("<i", 0))  # PinSubCategoryObject
    body.write(struct.pack("<B", 0))  # ContainerType
    body.write(struct.pack("<I", 0))  # bIsReference
    body.write(struct.pack("<I", 0))  # bIsWeakPointer
    body.write(struct.pack("<i", 0))  # MemberParent
    body.write(struct.pack("<II", 2, 0))  # MemberName
    body.write(b"\x00" * 16)  # MemberGuid
    body.write(struct.pack("<I", 0))  # bIsConst
    body.write(struct.pack("<I", 0))  # bIsUObjectWrapper
    body.write(struct.pack("<I", 0))  # bSerializeAsSinglePrecisionFloat
    body.write(struct.pack("<i", 0))  # DefaultValue
    body.write(struct.pack("<i", 0))  # AutogeneratedDefaultValue
    body.write(struct.pack("<i", 0))  # DefaultObject
    body.write(struct.pack("<iB", 0, 0xFF))  # DefaultTextValue flags+htype
    body.write(struct.pack("<I", 0))         # DefaultTextValue bHasCultureInvariantString
    body.write(struct.pack("<i", 0))  # LinkedTo
    body.write(struct.pack("<i", 0))  # SubPins
    body.write(struct.pack("<i", 1))  # ParentPin null
    body.write(struct.pack("<i", 1))  # RefPassThrough null
    body.write(b"\x00" * 16)  # PersistentGuid
    body.write(struct.pack("<I", 0))  # BitField

    archive = _BytesArchive(body.getvalue())
    pin = read_ue_graph_pin(
        archive,
        name_map,
        MagicMock(),
        _export_map(),
        [],
        header_owning_node=1,
        header_pin_id="AA" * 16,
    )

    assert pin.pin_name == "execute"
