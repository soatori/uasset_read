"""Property bag, tagged/unversioned readers, and expression-input structure."""

from __future__ import annotations

from uasset_read.models.byte_ranges import ByteRegion
from uasset_read.models.properties import PropertyBag, PropertyEntry, project_property_bag, project_property_entries
from uasset_read.parsers.properties.tagged import TaggedPropertyReader
from uasset_read.parsers.properties.unversioned import UnversionedPropertyReader, parse_unversioned_header


def test_tagged_reader_reports_consumed_boundary(tagged_fixture):
    result = TaggedPropertyReader().read(tagged_fixture)
    assert result.consumed >= 0
    assert result.regions[-1].end == tagged_fixture.start + result.consumed


def test_unversioned_reader_does_not_guess_without_schema(unversioned_fixture):
    result = UnversionedPropertyReader(schema=None).read(unversioned_fixture)
    assert result.status in {"opaque", "unavailable"}
    assert result.diagnostics[0].reason == "schema_required"


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


def duplicate_bag():
    return PropertyBag(
        entries=[
            PropertyEntry("Tags", "ArrayProperty", "A", 0, None, ByteRegion(0, 1, "decoded")),
            PropertyEntry("Tags", "ArrayProperty", "B", 1, None, ByteRegion(1, 1, "decoded")),
        ]
    )


def test_property_bag_preserves_duplicate_names_and_array_indices():
    entries = duplicate_bag().get_all("Tags")
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
        item
        for item in entries
        if isinstance(item.value, dict) and item.value.get("expression_ref") is not None
    )
    expression_input = entry.value
    assert expression_input["expression_ref"] is not None
    assert "output_index" in expression_input
    assert entry.value_region is not None


def test_projection_keeps_complete_entries_alongside_lookup_map():
    bag = duplicate_bag()
    projected = project_property_bag(bag)
    entries = project_property_entries(bag)
    assert projected["Tags"] == entries[-1]["value"]
    assert len([item for item in entries if item["name"] == "Tags"]) == 2


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
