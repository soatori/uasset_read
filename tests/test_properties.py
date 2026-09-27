"""Property bag, tagged/unversioned readers, and expression-input structure."""

from __future__ import annotations

from dataclasses import replace

from tests.fixtures import make_property_input
from uasset_read.models.byte_ranges import ByteRegion
from uasset_read.models.properties import PropertyBag, PropertyEntry, project_property_bag
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


def test_projection_keeps_complete_entries_alongside_lookup_map():
    bag = duplicate_bag()
    projected = project_property_bag(bag)
    tags = [entry for entry in bag.entries if entry.name == "Tags"]
    assert len(tags) == 2
    # The lookup map resolves to the last occurrence, matching PropertyBag.get.
    assert projected["Tags"] == tags[-1].value


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
