"""Pins for residual-review intentional behavior changes."""

from __future__ import annotations

import struct

from uasset_read.archive import ByteArchive
from uasset_read.constants import (
    MAX_REASONABLE_CAP,
    UE5_DATA_RESOURCES,
    UE5_LARGE_PROPERTY_MAX_REASONABLE,
    UE5_PAYLOAD_TOC,
    get_max_reasonable,
)
from uasset_read.models.properties import PropertyTag
from uasset_read.parsers.custom_properties import (
    CUSTOM_PROPERTY_HANDLERS,
    handle_custom_property,
)


def test_custom_property_unhandled_is_descriptor():
    archive = ByteArchive(b"\xaa\xbb\xcc\xdd")
    tag = PropertyTag(name="Mystery", type="CustomProperty", size=4)
    result = handle_custom_property(0xFD, tag, archive, name_map=[])
    assert result == {
        "kind": "custom_property_unhandled",
        "type_id": 0xFD,
        "property_type": "CustomProperty",
        "size": 4,
        "raw_data": b"\xaa\xbb\xcc\xdd",
    }


def test_custom_property_bl4_handlers_still_routed():
    # GbxDefPtrProperty: FName (index u32 + number u32) + struct ref i32
    payload = struct.pack("<IIi", 0, 0, 7)
    archive = ByteArchive(payload)
    tag = PropertyTag(name="Def", type="CustomProperty", size=12)
    result = handle_custom_property(0xFD, tag, archive, name_map=["Foo"], game="borderlands4")
    assert result == {"kind": "GbxDefPtrProperty", "name": "Foo", "struct": 7}
    assert ("borderlands4", 0xFD) in CUSTOM_PROPERTY_HANDLERS


def test_max_reasonable_map_property_is_large_cap():
    assert get_max_reasonable("MapProperty") == UE5_LARGE_PROPERTY_MAX_REASONABLE
    assert get_max_reasonable("IntProperty") == MAX_REASONABLE_CAP


def test_ue5_version_pins():
    assert UE5_PAYLOAD_TOC == 1002
    assert UE5_DATA_RESOURCES == 1009


def test_error_tuples_live_on_exceptions_module():
    import struct

    from uasset_read.exceptions import BINARY_READ_ERRORS, REFERENCE_RESOLVE_ERRORS

    assert BINARY_READ_ERRORS == (struct.error, OSError, ValueError)
    assert REFERENCE_RESOLVE_ERRORS == (KeyError, IndexError, AttributeError)
