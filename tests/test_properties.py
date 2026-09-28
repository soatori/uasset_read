"""Property bag, tagged/unversioned readers, and expression-input structure."""

from __future__ import annotations

import json
from dataclasses import replace

from tests.fixtures import make_property_input
from uasset_read.models.byte_ranges import ByteRegion
from uasset_read.models.properties import (
    PropertyBag,
    PropertyEntry,
    project_property_bag,
    project_property_value,
)
from uasset_read.parsers.properties.tagged import TaggedPropertyReader
from uasset_read.parsers.properties.unversioned import parse_unversioned_header


def test_tagged_reader_reports_consumed_boundary(tagged_fixture):
    result = TaggedPropertyReader().read(tagged_fixture)
    assert result.consumed >= 0
    assert result.regions[-1].end == tagged_fixture.start + result.consumed


def test_tagged_reader_recovery_reports_partial_with_diagnostics(tagged_fixture):
    """Recovery on the PropertyInput path must not claim complete with no diagnostics.

    The fixture's first FName index is out of range; tolerant read_name recovers
    with "None" and records name_index_out_of_range on the bounded window, so
    the unified-loop read must surface partial + that diagnostic.
    """
    result = TaggedPropertyReader().read(tagged_fixture)
    assert result.status == "partial"
    assert result.diagnostics
    diag = next(d for d in result.diagnostics if d.code == "name_index_out_of_range")
    assert diag.reason == "recovered_corruption"
    assert diag.object_id == tagged_fixture.object_id


def test_tagged_reader_property_fallback_reports_partial_with_diagnostics():
    """A PropertyFallback recovered by the loop yields PROPERTY_VALUE_READ_FAILED + partial."""
    inp = make_property_input("StarterContent_Starter_Background_Cue.uasset")
    result = TaggedPropertyReader().read(inp)
    assert result.status == "partial"
    diag = next(d for d in result.diagnostics if d.code == "PROPERTY_VALUE_READ_FAILED")
    assert diag.reason == "recovered_corruption"
    assert diag.object_id == inp.object_id
    # Recovery keeps the bag populated and the region boundary intact.
    assert result.consumed >= 0
    assert result.values.entries
    assert result.regions[-1].end == inp.start + result.consumed


def test_tagged_reader_clean_stream_reports_complete():
    """status=complete only when the stream is clean (None-terminated, no recovery)."""
    base = make_property_input("StackOBot_BP_Drone.uasset")
    # The UE5.4+ serialization-control byte precedes the tags and read() enters
    # the loop directly, so align past it to reach the clean tagged stream.
    aligned = replace(base, start=base.start + 1, size=base.size - 1)
    result = TaggedPropertyReader().read(aligned)
    assert result.status == "complete"
    assert result.diagnostics == []
    assert result.values.entries
    assert result.regions[-1].end == aligned.start + result.consumed


def test_tagged_reader_with_context_reads_only_bounded_slice(tagged_fixture):
    class NoWholeSource:
        def __init__(self, source):
            self._source = source

        def read_at(self, offset, size):
            if offset == 0 and size == self._source.size():
                raise AssertionError("reader attempted an unbounded whole-source read")
            return self._source.read_at(offset, size)

        def size(self):
            return self._source.size()

        def map_range(self, offset, size):
            return self._source.map_range(offset, size)

    result = TaggedPropertyReader().read(replace(tagged_fixture, source=NoWholeSource(tagged_fixture.source)))
    assert result.status in {"partial", "complete"}


def test_tagged_reader_without_package_context_is_structured_unavailable(tagged_fixture):
    result = TaggedPropertyReader().read(replace(tagged_fixture, package_context=None))
    assert result.status == "unavailable"
    assert result.diagnostics[0].code == "TAGGED_CONTEXT_REQUIRED"


def test_tagged_reader_is_sole_production_entry():
    import inspect

    from uasset_read.parsers import legacy_reader, property_parser
    from uasset_read.parsers.properties import tagged
    from uasset_read.parsers.properties.tagged import TaggedPropertyReader

    # The production tag loop lives in tagged.py, not property_parser.
    assert "def _read_property_loop" in inspect.getsource(tagged)
    assert not hasattr(property_parser, "_read_property_loop")
    assert not hasattr(property_parser, "parse_properties_from_export")

    # legacy_reader reaches the stream only through TaggedPropertyReader.read_export.
    legacy_source = inspect.getsource(legacy_reader)
    assert "TaggedPropertyReader" in legacy_source
    assert "parse_properties_from_export" not in legacy_source
    assert hasattr(TaggedPropertyReader, "read_export")


def test_unversioned_fragment_bit_layout_synthetic():
    # UE FUnversionedHeader fragment: SkipNum=bits0-6, HasAnyZeroes=bit7,
    # IsLast=bit8, ValueNum=bits9+. ValueNum=1 | IsLast=1 => 0x0300.
    raw = (0x0300).to_bytes(2, "little")
    header = parse_unversioned_header(raw)
    assert header.fragments[0].value_num == 1
    assert header.fragments[0].is_last is True
    # Pure ValueNum-only packing (no IsLast) still parses as a non-terminal fragment.
    only_value = parse_unversioned_header((0x0200).to_bytes(2, "little") + (0x0200 | 0x0100).to_bytes(2, "little"))
    assert only_value.fragments[0].value_num == 1
    assert only_value.fragments[0].is_last is False
    assert only_value.fragments[1].is_last is True


def test_unversioned_zero_mask_is_serialized_directly_without_count_byte():
    # HasAnyZeroes=1, ValueNum=3, IsLast=1 => (3<<9)|0x100|0x80 = 0x0780.
    # 3 masked values <= 8 bits, so the zero mask is a single uint8 (0b101),
    # serialized directly with NO NumBits count byte (UE LoadZeroMaskData).
    raw = (0x0780).to_bytes(2, "little") + bytes([0b101])
    header = parse_unversioned_header(raw)
    assert header.fragments[0].has_any_zeroes is True
    assert header.fragments[0].value_num == 3
    assert header.zero_bits == (True, False, True)
    assert header.header_size == 3


def duplicate_bag():
    return PropertyBag(
        entries=[
            PropertyEntry("Tags", "ArrayProperty", "A", 0, None, ByteRegion(0, 1, "decoded")),
            PropertyEntry("Tags", "ArrayProperty", "B", 1, None, ByteRegion(1, 1, "decoded")),
        ]
    )


def test_property_bag_preserves_duplicate_names_and_array_indices():
    entries = [entry for entry in duplicate_bag().entries if entry.name == "Tags"]
    assert [item.array_index for item in entries] == [0, 1]
    assert [item.value_region for item in entries]


def test_known_expression_input_does_not_fall_back_to_generic_struct_bytes(stackobot_material):
    from uasset_read.models.properties import PropertyBag

    entries = [
        entry
        for obj in stackobot_material.objects
        if isinstance(obj.properties, PropertyBag)
        for entry in obj.properties.entries
    ]
    entry = next(
        item for item in entries if isinstance(item.value, dict) and item.value.get("expression_ref") is not None
    )
    expression_input = entry.value
    assert expression_input["expression_ref"] is not None
    assert "output_index" in expression_input
    assert entry.value_region is not None


def test_project_property_bag_keeps_duplicate_occurrences_in_order():
    bag = duplicate_bag()
    projected = project_property_bag(bag)
    assert [entry["name"] for entry in projected] == ["Tags", "Tags"]
    assert [entry["occurrence"] for entry in projected] == [0, 1]
    assert [entry["array_index"] for entry in projected] == [0, 1]
    assert [entry["value"] for entry in projected] == ["A", "B"]
    for entry in projected:
        assert set(entry) == {"name", "type", "occurrence", "array_index", "value"}


def test_property_bag_get_item_compatibility():
    bag = PropertyBag(
        entries=[
            PropertyEntry(
                "AssetID",
                "StrProperty",
                {"kind": "value", "type": "StrProperty", "value": "X"},
                0,
                None,
                None,
            )
        ]
    )
    assert bag.get("AssetID", {}).get("kind") == "value"
    assert bag["AssetID"]["value"] == "X"
    assert bool(bag)


class Unstringable:
    """Unsupported value whose str()/repr() must never be called."""

    def __str__(self):
        raise AssertionError("str() fallback called")

    def __repr__(self):
        raise AssertionError("repr() fallback called")


class SelfDict:
    """to_dict() that returns itself — must become opaque, not recurse."""

    def to_dict(self):
        return self


class ExplodingDict:
    def to_dict(self):
        raise RuntimeError("to_dict failed")


def _typed_bag() -> PropertyBag:
    """One bag carrying every frozen value shape, duplicates included."""
    from uasset_read.models.fallback import FallbackReason, PropertyFallback, StructFallback
    from uasset_read.models.object_model import ObjectRef
    from uasset_read.models.properties import (
        DelegateValue,
        EnumValue,
        MapValue,
        SetValue,
        SoftObjectPathValue,
        StructValue,
        TextValue,
    )

    return PropertyBag(
        entries=[
            PropertyEntry("Tags", "ArrayProperty", "A", 0, None, ByteRegion(0, 1, "decoded")),
            PropertyEntry("Tags", "ArrayProperty", "B", 1, None, ByteRegion(1, 1, "decoded")),
            PropertyEntry(
                "Soft",
                "SoftObjectProperty",
                SoftObjectPathValue(raw_kind="SoftObjectProperty", asset_path="/Game/X.Y", sub_path="Sub"),
                0,
                ByteRegion(2, 4, "decoded", feature="property_tag"),
                ByteRegion(6, 8, "decoded", feature="property_value"),
            ),
            PropertyEntry(
                "Lazy",
                "LazyObjectProperty",
                SoftObjectPathValue(raw_kind="LazyObjectProperty", guid="aabbccdd"),
                0,
                None,
                None,
            ),
            PropertyEntry("Ref", "ObjectProperty", ObjectRef(table="export", index=2), 0, None, None),
            PropertyEntry(
                "Del",
                "DelegateProperty",
                DelegateValue(object_ref=3, function_name="OnDone"),
                0,
                None,
                None,
            ),
            PropertyEntry(
                "Multi",
                "MulticastDelegateProperty",
                [{"object": 4, "function": "OnA"}, {"object": 5, "function": "OnB"}],
                0,
                None,
                None,
            ),
            PropertyEntry(
                "Struct",
                "StructProperty",
                StructValue(
                    struct_type="Vector",
                    fields={"X": 1.0, "Nested": StructValue(struct_type="Rotator", fields={"Yaw": 2.0})},
                ),
                0,
                None,
                None,
            ),
            PropertyEntry("Arr", "ArrayProperty", [1, StructValue(struct_type="Vector", fields={"X": 1.0})], 0, None, None),
            PropertyEntry(
                "Map",
                "MapProperty",
                MapValue(key_type="NameProperty", value_type="IntProperty", entries=[{"key": "K", "value": 1}]),
                0,
                None,
                None,
            ),
            PropertyEntry(
                "Set",
                "SetProperty",
                SetValue(element_type="NameProperty", elements=["S"]),
                0,
                None,
                None,
            ),
            PropertyEntry(
                "Enum",
                "EnumProperty",
                EnumValue(enum_type="ESearchCase", value_name="IgnoreCase"),
                0,
                None,
                None,
            ),
            PropertyEntry(
                "Text",
                "TextProperty",
                TextValue(namespace="NS", key="Key", source_string="Src", history_type=0, property_type="TextProperty"),
                0,
                None,
                None,
            ),
            PropertyEntry(
                "Fallback",
                "UnknownProperty",
                PropertyFallback(name="Fallback", type="UnknownProperty", size=4, reason=FallbackReason.UNSUPPORTED_TYPE),
                0,
                None,
                None,
            ),
            PropertyEntry(
                "StructFallback",
                "StructProperty",
                StructFallback(
                    struct_type="Weird",
                    size=8,
                    raw_bytes=b"\x01\x02",
                    reason=FallbackReason.UNSUPPORTED_STRUCT,
                ),
                0,
                None,
                ByteRegion(14, 8, "opaque", reason="unsupported_struct"),
            ),
            PropertyEntry("Bytes", "BlobProperty", b"\x00\x01", 0, None, None),
            PropertyEntry("Weird", "WeirdProperty", Unstringable(), 0, None, None),
        ]
    )


def typed_property_document():
    """Minimal decode document wrapping the typed bag for envelope tests."""
    from uasset_read.archive import SourceInfo
    from uasset_read.models.document import PackageDocument, PackageInfo, Summary
    from uasset_read.models.object_model import ObjectRecord

    region = {
        "start": 4,
        "size": 8,
        "end": 12,
        "source_id": "typed.uasset",
        "source_start": 4,
        "source_end": 12,
        "source_slices": [{"source_id": "typed.uasset", "source_start": 4, "size": 8, "source_end": 12}],
        "status": "decoded",
        "reason": None,
        "feature": "typed_test",
        "payload_ref": None,
    }
    obj = ObjectRecord(
        id="export:0",
        table_index=0,
        name="Typed",
        class_name="TypedFixture",
        properties=_typed_bag(),
        semantic={"kind": "typed_fixture", "kept": 1, "source_range": region},
    )
    return PackageDocument(
        source=SourceInfo(kind="memory", name="typed.uasset", size=32),
        package=PackageInfo(name="/Game/Typed", layout="legacy"),
        objects=[obj],
        summary=Summary(object_count=1, asset_object_ids=("export:0",), total_exports=1),
        depth="decode",
    )


def test_project_property_value_matches_frozen_shapes():
    from uasset_read.models.fallback import FallbackReason, PropertyFallback, StructFallback
    from uasset_read.models.object_model import ObjectRef
    from uasset_read.models.properties import (
        DelegateValue,
        EnumValue,
        MapValue,
        SetValue,
        SoftObjectPathValue,
        StructValue,
        TextValue,
    )

    assert project_property_value(100.0) == 100.0
    assert project_property_value("X") == "X"
    assert project_property_value(None) is None
    assert project_property_value(
        SoftObjectPathValue(raw_kind="SoftObjectProperty", asset_path="/Game/X.Y", sub_path="Sub")
    ) == {"kind": "soft_object_path", "raw_kind": "SoftObjectProperty", "asset_path": "/Game/X.Y", "sub_path": "Sub"}
    assert project_property_value(SoftObjectPathValue(raw_kind="LazyObjectProperty", guid="aabb")) == {
        "kind": "soft_object_path",
        "raw_kind": "LazyObjectProperty",
        "asset_path": "",
        "sub_path": "",
        "guid": "aabb",
    }
    assert project_property_value(ObjectRef(table="import", index=3)) == {
        "kind": "object_ref",
        "table": "import",
        "index": 3,
        "id": "import:3",
    }
    assert project_property_value(DelegateValue(object_ref=2, function_name="Fn")) == {
        "kind": "delegate",
        "object_ref": 2,
        "function_name": "Fn",
    }
    assert project_property_value([{"object": 1, "function": "OnX"}]) == [
        {"kind": "delegate", "object_ref": 1, "function_name": "OnX"}
    ]
    assert project_property_value(StructValue(struct_type="Vector", fields={"X": 1.0})) == {
        "kind": "struct",
        "struct_type": "Vector",
        "fields": {"X": 1.0},
    }
    assert project_property_value([1, 2]) == {"kind": "array", "elements": [1, 2]}
    assert project_property_value(
        MapValue(key_type="NameProperty", value_type="IntProperty", entries=[{"key": "K", "value": 1}])
    ) == {
        "kind": "map",
        "key_type": "NameProperty",
        "value_type": "IntProperty",
        "entries": [{"key": "K", "value": 1}],
    }
    assert project_property_value(SetValue(element_type="NameProperty", elements=["S"])) == {
        "kind": "set",
        "element_type": "NameProperty",
        "elements": ["S"],
    }
    assert project_property_value(EnumValue(enum_type="ESearchCase", value_name="IgnoreCase")) == {
        "kind": "enum",
        "enum_type": "ESearchCase",
        "value": "IgnoreCase",
    }
    # Parser make_enum_value dicts use value_name and no kind discriminator.
    assert project_property_value({"enum_type": "ESearchCase", "value_name": "ESearchCase::IgnoreCase"}) == {
        "kind": "enum",
        "enum_type": "ESearchCase",
        "value": "ESearchCase::IgnoreCase",
    }
    assert project_property_value(TextValue(namespace="NS", key="K", source_string="S", history_type=0)) == {
        "kind": "text",
        "namespace": "NS",
        "key": "K",
        "source_string": "S",
        "history_type": 0,
    }
    assert project_property_value(
        PropertyFallback(name="M", type="UnknownProperty", size=4, reason=FallbackReason.UNSUPPORTED_TYPE)
    ) == {"kind": "opaque", "type": "UnknownProperty", "size": 4, "reason": "unsupported_type"}
    assert project_property_value(
        StructFallback(struct_type="Weird", size=8, raw_bytes=b"\x01\x02", reason=FallbackReason.UNSUPPORTED_STRUCT)
    ) == {
        "kind": "opaque",
        "type": "StructProperty",
        "size": 8,
        "reason": "unsupported_struct",
        "struct_type": "Weird",
    }
    assert project_property_value(b"\x00\x01") == {
        "kind": "opaque",
        "type": "bytes",
        "size": 2,
        "reason": "raw_bytes",
    }


def test_project_property_value_never_falls_back_to_str_or_repr():
    assert project_property_value(Unstringable()) == {
        "kind": "opaque",
        "type": "Unstringable",
        "size": 0,
        "reason": "unsupported_type",
    }


def test_project_property_value_reenters_to_dict_and_fences_recursion():
    assert project_property_value(SelfDict()) == {
        "kind": "opaque",
        "type": "SelfDict",
        "size": 0,
        "reason": "recursive",
    }
    assert project_property_value(ExplodingDict()) == {
        "kind": "opaque",
        "type": "ExplodingDict",
        "size": 0,
        "reason": "unsupported_type",
    }

    class Wrapper:
        def to_dict(self):
            return {"kind": "value", "type": "StrProperty", "value": b"\xaa"}

    assert project_property_value(Wrapper()) == {
        "kind": "value",
        "type": "StrProperty",
        "value": {"kind": "opaque", "type": "bytes", "size": 1, "reason": "raw_bytes"},
    }


def _collect_keys(value, keys: set) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(key)
            _collect_keys(item, keys)
    elif isinstance(value, list):
        for item in value:
            _collect_keys(item, keys)


def test_projected_entries_carry_no_ranges_or_raw_data():
    projected = project_property_bag(_typed_bag())
    assert [entry["name"] for entry in projected[:2]] == ["Tags", "Tags"]
    assert [entry["occurrence"] for entry in projected[:2]] == [0, 1]
    for entry in projected:
        assert set(entry) == {"name", "type", "occurrence", "array_index", "value"}
    keys: set = set()
    _collect_keys(projected, keys)
    # "index" is only banned on soft-object-path values (see exact-shape test);
    # ObjectRef legitimately carries it.
    assert keys.isdisjoint(
        {
            "tag_region",
            "value_region",
            "tag_range",
            "value_range",
            "raw_data",
            "raw_bytes",
            "package_index",
            "property_type",
        }
    )
    json.dumps(projected)  # must be JSON-safe
