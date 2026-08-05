"""Regression coverage for the source-proven #515 EditedDocumentInfo slice."""

from __future__ import annotations

import struct
from types import SimpleNamespace

from uasset_read.archive import ByteArchive
from uasset_read.models.properties import PropertyTag, StructValue
from uasset_read.parsers import property_types
from uasset_read.parsers.property_parser import parse_property_value
from uasset_read.parsers.property_types import parse_struct_property


def _binary_struct_value(
    struct_type: str,
    raw: bytes,
    summary: object | None = None,
) -> dict:
    return parse_property_value(
        PropertyTag(
            name=struct_type,
            type="StructProperty",
            size=len(raw),
            struct_type=struct_type,
            serialize_type="BinaryOrNative",
        ),
        ByteArchive(raw),
        [],
        [],
        summary,
    )


def test_soft_object_path_binary_index_resolves_header_path_list() -> None:
    """A four-byte native FSoftObjectPath index exposes its header-table entry."""
    summary = SimpleNamespace(
        _soft_object_path_list=[
            {"asset_path": "/Game/BP.BP", "sub_path": "EventGraph"},
            {"asset_path": "/Game/BP.BP", "sub_path": "Move"},
        ]
    )

    value = _binary_struct_value("SoftObjectPath", struct.pack("<i", 1), summary)

    assert value == {
        "kind": "struct_binary_decoded",
        "struct_type": "SoftObjectPath",
        "size": 4,
        "fields": {
            "asset_path": "/Game/BP.BP",
            "sub_path": "Move",
            "index": 1,
        },
    }

def test_soft_object_path_without_header_table_preserves_raw_bytes() -> None:
    """No table means no fabricated path; the existing raw fallback is retained."""
    raw = struct.pack("<i", 3)

    value = _binary_struct_value(
        "SoftObjectPath",
        raw,
        SimpleNamespace(_soft_object_path_list=[]),
    )

    assert value["kind"] == "binary_or_native_property"
    assert value["struct_type"] == "SoftObjectPath"
    assert value["raw_data"] == raw


def test_soft_object_path_out_of_range_index_preserves_raw_bytes() -> None:
    """An invalid index is not silently turned into an empty resolved reference."""
    raw = struct.pack("<i", 2)

    value = _binary_struct_value(
        "SoftObjectPath",
        raw,
        SimpleNamespace(
            _soft_object_path_list=[
                {"asset_path": "/Game/BP.BP", "sub_path": "EventGraph"},
            ]
        ),
    )

    assert value["kind"] == "binary_or_native_property"
    assert value["struct_type"] == "SoftObjectPath"
    assert value["raw_data"] == raw


def test_deprecate_slate_vector2d_binary_payload_decodes_two_float32_values() -> None:
    """UE 5.8 serializes FDeprecateSlateVector2D as an eight-byte FVector2f."""
    value = _binary_struct_value(
        "DeprecateSlateVector2D",
        struct.pack("<ff", 12.5, -4.0),
    )

    assert value == {
        "kind": "struct_binary_decoded",
        "struct_type": "DeprecateSlateVector2D",
        "size": 8,
        "fields": {"X": 12.5, "Y": -4.0},
    }


def test_edited_document_info_zero_size_uses_tagged_fields(monkeypatch) -> None:
    """The outer struct retains the document path, view offset, and zoom fields."""
    tags = iter((
        PropertyTag(
            name="EditedObjectPath",
            type="StructProperty",
            size=4,
            struct_type="SoftObjectPath",
            serialize_type="BinaryOrNative",
        ),
        PropertyTag(
            name="SavedViewOffset",
            type="StructProperty",
            size=8,
            struct_type="DeprecateSlateVector2D",
            serialize_type="BinaryOrNative",
        ),
        PropertyTag(name="SavedZoomAmount", type="FloatProperty", size=4),
        PropertyTag(name="None", type="", size=0),
    ))
    monkeypatch.setattr(
        property_types,
        "_get_read_property_tag",
        lambda: lambda *_args, **_kwargs: next(tags),
    )
    summary = SimpleNamespace(
        _soft_object_path_list=[
            {"asset_path": "/Game/BP.BP", "sub_path": "EventGraph"},
        ]
    )
    archive = ByteArchive(
        struct.pack("<i", 0)
        + struct.pack("<ff", 12.5, -4.0)
        + struct.pack("<f", 0.5)
    )

    value = parse_struct_property(
        PropertyTag(
            name="LastEditedDocuments[0]",
            type="StructProperty",
            size=0,
            struct_type="EditedDocumentInfo",
        ),
        archive,
        [],
        [],
        summary,
    )

    assert isinstance(value, StructValue)
    assert value.struct_type == "EditedDocumentInfo"
    assert value.parse_status == "success"
    assert value.fields == {
        "EditedObjectPath": {
            "kind": "struct_binary_decoded",
            "struct_type": "SoftObjectPath",
            "size": 4,
            "fields": {
                "asset_path": "/Game/BP.BP",
                "sub_path": "EventGraph",
                "index": 0,
            },
        },
        "SavedViewOffset": {
            "kind": "struct_binary_decoded",
            "struct_type": "DeprecateSlateVector2D",
            "size": 8,
            "fields": {"X": 12.5, "Y": -4.0},
        },
        "SavedZoomAmount": 0.5,
    }
