"""Regression coverage for #508's UE5-first asset metadata path."""

from __future__ import annotations

import struct
from types import SimpleNamespace

from uasset_read.archive import ByteArchive
from uasset_read.parsers import property_parser
from uasset_read.parsers.asset_types import PropertyMetadataHandler
from uasset_read.parsers.asset_types.property_metadata import build_property_metadata
from uasset_read.parsers.asset_types.sound_cue import parse_sound_cue
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.serializers.property_tags import read_property_tag


def _fname(index: int, number: int = 0) -> bytes:
    return struct.pack("<II", index, number)


def test_legacy_ue4_tag_does_not_consume_value_as_property_guid() -> None:
    """UE4 support is limited to preserving tag alignment for legacy packages."""
    archive = ByteArchive(
        _fname(0) + _fname(1) + struct.pack("<ii", 4, 0) + struct.pack("<i", 23)
    )
    archive._file_version_ue4 = 490  # UE4.11: predates PropertyGuid-in-tag.
    archive._file_version_ue5 = 0

    tag = read_property_tag(archive, ["FirstNode", "ObjectProperty"])

    assert tag.name == "FirstNode"
    assert tag.property_guid is None
    assert tag.value_start_offset == 24
    assert archive.read_i32() == 23


def test_minimal_ue4_support_reads_array_inner_type_from_its_actual_gate() -> None:
    archive = ByteArchive(
        _fname(0) + _fname(1) + struct.pack("<ii", 4, 0) + _fname(2) + struct.pack("<i", 23)
    )
    archive._file_version_ue4 = 282
    archive._file_version_ue5 = 0

    tag = read_property_tag(archive, ["Items", "ArrayProperty", "ObjectProperty"])

    assert tag.inner_type == "ObjectProperty"
    assert tag.value_start_offset == 32
    assert archive.read_i32() == 23


def test_asset_handler_runs_once_after_property_loop(monkeypatch) -> None:
    """The completed property list is the only asset-handler dispatch point."""
    calls: list[str] = []
    export = SimpleNamespace(
        serial_offset=0,
        serial_size=8,
        class_index=1,
        object_name="M_Test",
    )
    summary = SimpleNamespace(file_version_ue5=0, package_flags=0)
    monkeypatch.setattr(
        "uasset_read.serializers.object_resources.resolve_class_name",
        lambda *_: "Material",
    )
    monkeypatch.setattr(
        property_parser,
        "_try_asset_type_handler",
        lambda _export, _archive, _names, class_name, **_: calls.append(class_name),
    )

    property_parser.parse_properties_from_export(
        export,
        ByteArchive(_fname(0)),
        summary,
        ["None"],
        [],
        import_map=[object()],
    )

    assert calls == ["Material"]


def test_ue5_property_metadata_uses_only_serialized_values() -> None:
    """UE5 metadata is property-first and never fills absent engine defaults."""
    material = build_property_metadata(
        "Material",
        [
            SimpleNamespace(
                name="BlendMode",
                value={"enum_type": "EBlendMode", "value_name": "EBlendMode::BLEND_Masked"},
            ),
            SimpleNamespace(name="TwoSided", value=True),
            SimpleNamespace(
                name="TextureStreamingData",
                value=[SimpleNamespace(fields={"TextureName": "T_Bot_Albedo", "Raw": b"ignored"})],
            ),
        ],
        tail_offset=40,
        tail_size=12,
    )
    texture = build_property_metadata(
        "Texture2D",
        [
            SimpleNamespace(name="ImportedSize", value={"X": 512, "Y": 512}),
            SimpleNamespace(name="CompressionSettings", value="TC_Masks"),
            SimpleNamespace(name="SRGB", value=False),
        ],
    )
    cue = build_property_metadata(
        "SoundCue",
        [
            SimpleNamespace(name="FirstNode", value={"package_index": 23}),
            SimpleNamespace(name="VolumeMultiplier", value=0.75),
        ],
    )

    assert material == {
        "asset_type": "Material",
        "parse_status": "partial_metadata",
        "blend_mode": "EBlendMode::BLEND_Masked",
        "two_sided": True,
        "texture_references": ["T_Bot_Albedo"],
        "tail_offset": 40,
        "tail_size": 12,
    }
    assert "shading_model" not in material
    assert texture["imported_size"] == {"x": 512, "y": 512}
    assert texture["compression_settings"] == "TC_Masks"
    assert texture["srgb"] is False
    assert cue["first_node"] == {"package_index": 23}
    assert cue["volume_multiplier"] == 0.75
    assert "pitch_multiplier" not in cue


def test_property_metadata_handler_keeps_native_tail_opaque() -> None:
    export = SimpleNamespace(
        object_name="T_GridChecker_A",
        serial_offset=10,
        serial_size=50,
        properties=[
            SimpleNamespace(name="ImportedSize", value={"X": 512, "Y": 512}),
            SimpleNamespace(name="SRGB", value=False),
        ],
    )
    archive = ByteArchive(b"\0" * 100)
    archive.seek(40)

    result = PropertyMetadataHandler("Texture2D").parse(export, archive, [])

    assert result.success is True
    assert result.data == {
        "asset_type": "Texture2D",
        "parse_status": "partial_metadata",
        "imported_size": {"x": 512, "y": 512},
        "srgb": False,
        "tail_offset": 40,
        "tail_size": 20,
    }
    assert archive.tell() == 40


def test_standard_json_exposes_asset_metadata_without_raw_bytes() -> None:
    export = SimpleNamespace(
        object_name="M_BotBase",
        object_class="Material",
        serial_size=128,
        parent_class=None,
        properties=[],
        graphs=[],
        parse_status="partial_metadata",
        fallback_reason=None,
        error_message=None,
        asset_type_data={
            "asset_type": "Material",
            "parse_status": "partial_metadata",
            "blend_mode": "EBlendMode::BLEND_Masked",
            "tail_offset": 64,
            "tail_size": 64,
        },
    )

    rendered = JSONRenderer()._export_to_dict(export, RenderOptions())

    assert rendered["asset_type_data"] == export.asset_type_data
    assert "raw_bytes" not in rendered["asset_type_data"]


def test_legacy_sound_cue_function_never_reads_a_native_prefix() -> None:
    archive = ByteArchive(struct.pack("<iffi", 23, 1.0, 1.0, 7))

    data = parse_sound_cue(archive, [])

    assert archive.tell() == 0
    assert data == {"asset_type": "SoundCue", "parse_status": "opaque"}
