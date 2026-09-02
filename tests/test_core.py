"""Small permanent suite for stable cross-cutting contracts.

Exactly ten top-level ``test_*`` functions (design: test-organization
constraints). Fixture-sample contracts live in ``test_samples.py``. Case
bodies folded from the former ``tests/contract/`` layer are kept verbatim;
the case name appears in the failure message.
"""

from __future__ import annotations

from functools import lru_cache
import json
import logging
from pathlib import Path
import os
import subprocess
import sys

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(__file__).parent / "samples"
PACKAGE_SAMPLE = SAMPLES / "ABP_RifleAnimLayers.uasset"
DATA_SAMPLE = SAMPLES / "ALS_FootstepDataTable.uasset"
SCHEMA = ROOT / "docs/designs/contract/package_document_v2.schema.json"
EXAMPLE = ROOT / "docs/designs/contract/package_document_v2.example.json"


@lru_cache(maxsize=None)
def _document(sample: str = str(PACKAGE_SAMPLE), depth: str = "package"):
    from uasset_read.v2.api import parse_package_document

    return parse_package_document(sample, depth=depth)


def _run_cases(cases) -> None:
    for case_name, check in cases:
        try:
            check()
        except (AssertionError, pytest.fail.Exception) as exc:
            raise AssertionError(f"{case_name}: {exc}") from exc


def test_reader_boundaries_reject_malformed_access(tmp_path):
    """A bounded reader must never escape its declared source region."""
    from uasset_read.package import PackageArchive
    from uasset_read.v2.source import FileSource, MemorySource, SliceReader

    def core_contract():
        source = MemorySource(b"0123456789")
        reader = SliceReader(source, 2, 5)
        assert reader.read(3) == b"234"
        assert reader.sub_slice(1, 2).read(2) == b"34"
        for operation in (
            lambda: source.read_at(-1, 1),
            lambda: reader.seek(6),
            lambda: reader.read(3),
        ):
            with pytest.raises(IndexError):
                operation()

    def test_size():
        assert MemorySource(b"hello world").size() == 11

    def test_read_at():
        src = MemorySource(b"hello world")
        assert src.read_at(0, 5) == b"hello"
        assert src.read_at(6, 5) == b"world"

    def test_read_at_negative_offset():
        with pytest.raises(IndexError):
            MemorySource(b"hello").read_at(-1, 1)

    def test_read_at_overflow():
        with pytest.raises(IndexError):
            MemorySource(b"hello").read_at(3, 5)

    def test_describe():
        info = MemorySource(b"test", name="test.bin").describe()
        assert info.kind == "memory"
        assert info.name == "test.bin"
        assert info.size == 4

    def test_file_read():
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00\x01\x02\x03\x04")
        src = FileSource(f)
        assert src.size() == 5
        assert src.read_at(1, 3) == b"\x01\x02\x03"

    def test_file_read_out_of_range():
        f = tmp_path / "oob.bin"
        f.write_bytes(b"\x00\x01")
        with pytest.raises(IndexError):
            FileSource(f).read_at(0, 10)

    def test_basic_read():
        sr = SliceReader(MemorySource(b"0123456789"), 2, 5)
        assert sr.source_size == 5
        assert sr.read(3) == b"234"
        assert sr.tell() == 3
        assert sr.remaining() == 2

    def test_seek():
        sr = SliceReader(MemorySource(b"0123456789"), 0, 10)
        sr.seek(5)
        assert sr.tell() == 5
        assert sr.read(3) == b"567"

    def test_seek_out_of_range():
        sr = SliceReader(MemorySource(b"0123456789"), 0, 10)
        with pytest.raises(IndexError):
            sr.seek(11)

    def test_read_exceeds_slice():
        sr = SliceReader(MemorySource(b"0123456789"), 2, 3)
        with pytest.raises(IndexError):
            sr.read(4)

    def test_sub_slice():
        sub = SliceReader(MemorySource(b"0123456789"), 0, 10).sub_slice(2, 4)
        assert sub.source_size == 4
        assert sub.read(4) == b"2345"

    def test_sub_slice_out_of_range():
        sr = SliceReader(MemorySource(b"0123456789"), 2, 3)
        with pytest.raises(IndexError):
            sr.sub_slice(0, 10)

    def test_nested_sub_slice():
        sub2 = SliceReader(MemorySource(b"0123456789"), 0, 10).sub_slice(2, 6).sub_slice(1, 3)
        assert sub2.read(3) == b"345"

    def test_invalid_slice_negative_base():
        with pytest.raises(IndexError):
            SliceReader(MemorySource(b"0123456789"), -1, 5)

    def test_invalid_slice_exceeds_source():
        with pytest.raises(IndexError):
            SliceReader(MemorySource(b"0123456789"), 8, 5)

    def test_slice_reader_satisfies_archive_like():
        reader = SliceReader(MemorySource(b"abcdef"), 1, 4)
        archive = PackageArchive(reader)
        assert archive.total_size() == 4
        archive.set_byte_swapping(True)
        assert archive.read(2) == b"bc"
        archive.close()

    def test_export_read_within_range_succeeds():
        """Reading within (50, 100) from pos 80 must return data and advance."""
        from uasset_read.archive import ByteArchive

        archive = ByteArchive(b"\x00" * 256)
        archive._read_range = (50, 100)
        archive._pos = 80
        data = archive.read(20)
        assert data == b"\x00" * 20
        assert archive._pos == 100

    def test_export_read_past_upper_bound_fails():
        from uasset_read.archive import ByteArchive, ExportBoundsExceeded

        archive = ByteArchive(b"\x00" * 256)
        archive._read_range = (50, 100)
        archive._pos = 80
        with pytest.raises(ExportBoundsExceeded):
            archive.read(50)

    def test_export_seek_past_lower_bound_fails():
        from uasset_read.archive import ByteArchive, ExportBoundsExceeded

        archive = ByteArchive(b"\x00" * 256)
        archive._read_range = (50, 100)
        with pytest.raises(ExportBoundsExceeded):
            archive.validate_offset(10, "test_seek")

    def test_export_seek_past_upper_bound_fails():
        from uasset_read.archive import ByteArchive, ExportBoundsExceeded

        archive = ByteArchive(b"\x00" * 256)
        archive._read_range = (50, 100)
        with pytest.raises(ExportBoundsExceeded):
            archive.validate_offset(150, "test_seek")

    def depends_map_stops_at_unsized_count():
        import struct
        from types import SimpleNamespace
        from uasset_read.archive import ByteArchive
        from uasset_read.serializers.package_summary import read_depends_map
        # Leading filler int32 so depends_offset=4 is a positive, in-bounds table start.
        data = struct.pack("<iiii", 0, 10_001, 1, 1)
        arc = ByteArchive(data)
        summary = SimpleNamespace(depends_offset=4, export_count=3, import_count=0)
        warnings: list[str] = []
        result = read_depends_map(arc, summary, warnings=warnings)
        assert result == [[]]
        assert any("stopped" in w for w in warnings)
        assert any(d.code == "DEPENDS_MAP_TRUNCATED" for d in arc.get_structured_diagnostics())

    def chunk_ids_count_beyond_file_rejected_immediately():
        import struct
        from uasset_read.archive import ByteArchive
        from uasset_read.exceptions import ParseError
        from uasset_read.serializers.package_summary import _read_tail_offsets
        data = struct.pack("<iqii", 0, 0, 0, 10_000_000)
        with pytest.raises(ParseError, match="ChunkIDs"):
            _read_tail_offsets(ByteArchive(data))

    def sources_reject_negative_size():
        with pytest.raises(ValueError, match="negative"):
            FileSource(str(PACKAGE_SAMPLE)).read_at(0, -1)
        with pytest.raises(ValueError, match="negative"):
            MemorySource(b"abcd").read_at(0, -1)
        with pytest.raises(ValueError, match="negative"):
            SliceReader(MemorySource(b"abcd"), 0, 4).read(-1)
        sr = SliceReader(MemorySource(b"abcd"), 0, 4)
        assert sr.read(4) == b"abcd"
        with pytest.raises(IndexError):
            sr.read(1)
        assert sr.tell() == 4  # failed reads must not move the cursor

    def preload_count_beyond_file_rejected_immediately():
        import struct
        from types import SimpleNamespace
        from uasset_read.archive import ByteArchive
        from uasset_read.exceptions import ParseError
        from uasset_read.serializers.package_summary import read_preload_dependencies
        # offset 4 is a positive, in-bounds table start in the 8-byte payload.
        data = struct.pack("<ii", 7, 9)
        summary = SimpleNamespace(preload_dependency_offset=4, preload_dependency_count=10_000_000)
        with pytest.raises(ParseError, match="PreloadDependencies"):
            read_preload_dependencies(ByteArchive(data), summary)

    def tolerant_fstring_overrun_records_recovery_not_just_a_log():
        import struct
        from uasset_read.archive import ByteArchive
        from uasset_read.exceptions import ParseError
        for header, enc in ((6, "UTF-8"), (-6, "UTF-16")):  # claims 6/12 bytes, 2 remain
            arc = ByteArchive(struct.pack("<i", header) + b"ab", tolerant=True)
            assert arc.read_fstring() == ""
            sd = [d for d in arc.get_structured_diagnostics() if d.code == "fstring_out_of_range"]
            assert sd and sd[0].offset == 0 and sd[0].fallback == "used_empty_string", enc
        with pytest.raises(ParseError):  # strict mode still fails hard
            ByteArchive(struct.pack("<i", 6) + b"ab").read_fstring()

    def fstring_internal_null_truncation_is_recorded():
        import struct
        from uasset_read.archive import ByteArchive
        arc = ByteArchive(struct.pack("<i", 4) + b"ab\x00c", tolerant=True)
        assert arc.read_fstring() == "ab"
        sd = [d for d in arc.get_structured_diagnostics() if d.code == "fstring_truncated_at_null"]
        assert sd and sd[0].offset == 0 and sd[0].fallback == "truncated_at_first_null"

    def fname_shift_recovery_is_recorded():
        import struct
        from uasset_read.archive import ByteArchive
        # Garbage FName at pos 4 (index 2**24); a shifted view of the same bytes
        # carries a valid (index, number) pair, so recovery must fire and report.
        data = bytearray(b"\x00" * 12)
        struct.pack_into("<I", data, 4, 1 << 24)
        data[7] = 0x01  # doubles as the shifted instance number
        arc = ByteArchive(bytes(data), tolerant=True)
        arc.seek(4)
        assert arc.read_name(["Alpha"])
        sd = [d for d in arc.get_structured_diagnostics() if d.code == "fname_index_shift_recovered"]
        assert sd and sd[0].offset == 4 and sd[0].fallback == "shifted_read"

    def export_map_recoveries_are_attributed_to_their_slot():
        import struct
        from types import SimpleNamespace
        from uasset_read.archive import ByteArchive
        from uasset_read.serializers.object_resources import read_export_map
        # One FObjectExport entry (UE4.5-era version gates: no TemplateIndex,
        # preload or script-serialization fields) whose ObjectName carries
        # out-of-range index 5 for a 1-name table. bools are uint32 (7 fields),
        # plus a 16-byte PackageGuid.
        entry = struct.pack("<iiiiiiii", 0, 0, -1, 5, 0, 0, 0, 0) + b"\x00" * (7 * 4 + 16 + 4)
        arc = ByteArchive(b"\x00" * 4 + entry, tolerant=True)
        summary = SimpleNamespace(
            export_count=1, export_offset=4, package_flags=0, file_version_ue4=500, file_version_ue5=0
        )
        export_map = read_export_map(arc, summary, ["Alpha"])
        assert len(export_map) == 1
        sd = [d for d in arc.get_structured_diagnostics() if d.code == "name_index_out_of_range"]
        assert sd and sd[0].object_id == "export:0"
        assert arc._current_object_id == ""  # context must not leak past the table

    _run_cases(
        [
            ("core.reader_out_of_range", core_contract),
            ("MemorySource.test_size", test_size),
            ("MemorySource.test_read_at", test_read_at),
            ("MemorySource.test_read_at_negative_offset", test_read_at_negative_offset),
            ("MemorySource.test_read_at_overflow", test_read_at_overflow),
            ("MemorySource.test_describe", test_describe),
            ("FileSource.test_read", test_file_read),
            ("FileSource.test_read_out_of_range", test_file_read_out_of_range),
            ("SliceReader.test_basic_read", test_basic_read),
            ("SliceReader.test_seek", test_seek),
            ("SliceReader.test_seek_out_of_range", test_seek_out_of_range),
            ("SliceReader.test_read_exceeds_slice", test_read_exceeds_slice),
            ("SliceReader.test_sub_slice", test_sub_slice),
            ("SliceReader.test_sub_slice_out_of_range", test_sub_slice_out_of_range),
            ("SliceReader.test_nested_sub_slice", test_nested_sub_slice),
            ("SliceReader.test_invalid_slice_negative_base", test_invalid_slice_negative_base),
            ("SliceReader.test_invalid_slice_exceeds_source", test_invalid_slice_exceeds_source),
            ("test_slice_reader_satisfies_archive_like", test_slice_reader_satisfies_archive_like),
            ("export_bounds.read_within_range_succeeds", test_export_read_within_range_succeeds),
            ("export_bounds.read_past_upper_bound_fails", test_export_read_past_upper_bound_fails),
            ("export_bounds.seek_past_lower_bound_fails", test_export_seek_past_lower_bound_fails),
            ("export_bounds.seek_past_upper_bound_fails", test_export_seek_past_upper_bound_fails),
            ("depends_map.stops_at_unsized_count", depends_map_stops_at_unsized_count),
            ("chunk_ids.count_beyond_file_rejected", chunk_ids_count_beyond_file_rejected_immediately),
            ("source.reject_negative_size", sources_reject_negative_size),
            ("preload.count_beyond_file_rejected", preload_count_beyond_file_rejected_immediately),
            ("recovery.fstring_overrun_recorded", tolerant_fstring_overrun_records_recovery_not_just_a_log),
            ("recovery.fstring_null_truncation_recorded", fstring_internal_null_truncation_is_recorded),
            ("recovery.fname_shift_recorded", fname_shift_recovery_is_recorded),
            ("recovery.export_map_attribution", export_map_recoveries_are_attributed_to_their_slot),
        ]
    )


def test_property_bag_normalization_is_bounded_lossless():
    """normalize_property_bag must bound, describe, and never embed raw bytes."""
    from uasset_read.models.fallback import FallbackReason, PropertyFallback
    from uasset_read.models.properties import PropertyValue, StructValue
    from uasset_read.v2.properties import normalize_property_bag

    def test_empty_list_returns_empty_dict():
        assert normalize_property_bag([]) == {}

    def test_unknown_property_is_descriptor_not_blob():
        prop = PropertyFallback(
            name="Mystery",
            type="UnknownProperty",
            size=4,
            raw_bytes=b"\x01\x02\x03\x04",
            reason=FallbackReason.UNSUPPORTED_TYPE,
        )
        bag = normalize_property_bag([prop])
        assert bag["Mystery"] == {
            "kind": "opaque",
            "type": "UnknownProperty",
            "size": 4,
            "reason": "unsupported_type",
        }
        assert "raw_bytes" not in bag["Mystery"]
        json.dumps(bag)

    def test_known_property_preserves_value():
        bag = normalize_property_bag([PropertyValue(name="Health", type="FloatProperty", value=100.0)])
        assert bag["Health"]["kind"] == "value"
        assert bag["Health"]["value"] == 100.0
        json.dumps(bag)

    def test_struct_property_normalizes():
        sv = StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})
        prop = PropertyValue(name="Location", type="StructProperty", value=sv)
        bag = normalize_property_bag([prop])
        assert bag["Location"]["kind"] == "struct"
        assert bag["Location"]["struct_type"] == "Vector"
        assert bag["Location"]["fields"]["X"] == 1.0
        json.dumps(bag)

    def test_bytes_value_serializes():
        bag = normalize_property_bag([PropertyValue(name="Data", type="BlobProperty", value=b"\x00\x01")])
        assert bag["Data"]["kind"] == "value"
        assert bag["Data"]["value"]["kind"] == "bytes"
        assert bag["Data"]["value"]["length"] == 2
        json.dumps(bag)

    def test_lwc_box_size_52_and_double_read():
        import struct
        from uasset_read.archive import ByteArchive
        from uasset_read.models.properties import PropertyTag
        from uasset_read.parsers.property_types import _LWC_TYPE_MAP, parse_struct_property
        assert _LWC_TYPE_MAP["Box"] == (28, 52)
        payload = struct.pack("<ddddddi", 1, 2, 3, 4, 5, 6, 1)  # Min 3xd + Max 3xd + IsValid i32 = 52
        assert len(payload) == 52
        tag = PropertyTag(name="B", type="StructProperty", size=52)
        tag.struct_type = "Box"
        arc = ByteArchive(payload)
        out = parse_struct_property(tag, arc, ["None"], [], None)
        assert out.struct_type == "Box"
        assert out.fields["Min"]["X"] == 1.0 and out.fields["Max"]["Z"] == 6.0
        # IsValid is a 4-byte UBOOL (Archive.h); float Box branch names the field bIsValid.
        assert out.fields["bIsValid"] is True

    def test_property_tag_extension_external_objects():
        import struct
        from uasset_read.archive import ByteArchive
        from uasset_read.constants import PROP_EXT_HAS_EXTERNAL_OBJECTS
        from uasset_read.serializers.property_tags import read_property_tag
        assert PROP_EXT_HAS_EXTERNAL_OBJECTS == 0x04
        # Legacy header (routes via archive._file_version_ue5 < 1012):
        # name FName + type FName + size i32 + array_index i32 + HasPropertyGuid u8=0 + ext u8 [+ payload]
        names = ["None", "IntProperty"]

        def legacy_tag(ext: bytes):
            # Name uses index 1; index 0 would hit the "None" sentinel early-return.
            return struct.pack("<ii", 1, 0) + struct.pack("<ii", 1, 0) + struct.pack("<ii", 4, 0) + b"\x00" + ext

        arc = ByteArchive(legacy_tag(b"\x04\x07") + struct.pack("<i", 99))
        arc._file_version_ue5 = 1011  # legacy routing (<1012) with the extension block on (>=1011)
        arc._file_version_ue4 = 522
        tag = read_property_tag(arc, names)
        assert tag.value_start_offset == 27  # 8+8+4+4+1 header + 1 ext + 1 external-object slot
        assert tag.flags == 0x04
        assert arc.read_i32() == 99  # value stream starts right after the consumed slot
        # and the 0x02|0x04 combined case: two control bytes + one external byte
        arc2 = ByteArchive(legacy_tag(b"\x06\x00\x00\x07") + struct.pack("<i", 99))
        arc2._file_version_ue5 = 1011
        arc2._file_version_ue4 = 522
        assert read_property_tag(arc2, names).value_start_offset == 29

    _run_cases(
        [
            ("property.test_empty_list_returns_empty_dict", test_empty_list_returns_empty_dict),
            ("property.test_unknown_property_is_descriptor_not_blob", test_unknown_property_is_descriptor_not_blob),
            ("property.test_known_property_preserves_value", test_known_property_preserves_value),
            ("property.test_struct_property_normalizes", test_struct_property_normalizes),
            ("property.test_bytes_value_serializes", test_bytes_value_serializes),
            ("property.lwc_box_size_52_and_double_read", test_lwc_box_size_52_and_double_read),
            ("property.tag_extension_external_objects", test_property_tag_extension_external_objects),
        ]
    )


def test_package_document_preserves_every_export_and_role():
    """Package parsing must preserve every export, including packages without an asset role."""
    doc = _document()
    assert [obj.id for obj in doc.objects] == [f"export:{index}" for index in range(10)]
    assert len(doc.summary.asset_object_ids) == 2
    assert all(relation.from_id.startswith(("export:", "import:")) for relation in doc.relations)

    def test_all_exports_present():
        assert len(doc.objects) == 10

    def test_ids_are_export_prefix():
        for obj in doc.objects:
            assert obj.id.startswith("export:")
            idx = int(obj.id.split(":")[1])
            assert idx == obj.table_index

    def test_stable_id_across_calls():
        from uasset_read.v2.api import parse_package_document

        doc1 = parse_package_document(str(PACKAGE_SAMPLE))
        doc2 = parse_package_document(str(PACKAGE_SAMPLE))
        ids1 = [o.id for o in doc1.objects]
        ids2 = [o.id for o in doc2.objects]
        assert ids1 == ids2

    _run_cases(
        [
            ("document.test_all_exports_present", test_all_exports_present),
            ("document.test_ids_are_export_prefix", test_ids_are_export_prefix),
            ("document.test_stable_id_across_calls", test_stable_id_across_calls),
        ]
    )

    zero_role = _document(str(SAMPLES / "uasset_rs_UE410_SimpleRefsSoftRef.uasset"))
    assert len(zero_role.objects) == 6
    assert zero_role.summary.asset_object_ids == ()


def test_export_failure_isolated_and_diagnostics_typed(monkeypatch):
    """A malformed export must produce an attributable diagnostic without deleting siblings."""
    import uasset_read.parsers.property_parser as pp
    from uasset_read.exceptions import ParseError
    from uasset_read.v2.api import parse_package_document

    real = pp.parse_properties_from_export
    calls = {"n": 0}

    def boom(**kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise ParseError("injected malformed export payload")
        return real(**kwargs)

    # All fixture exports now parse cleanly, so inject the failure to
    # exercise the isolation path deterministically.
    monkeypatch.setattr(pp, "parse_properties_from_export", boom)
    doc = parse_package_document(str(PACKAGE_SAMPLE), depth="object")
    failures = [
        item
        for item in doc.diagnostics
        if item.code in ("EXPORT_PROPERTY_PARSE_FAILED", "EXPORT_PROPERTY_BOUNDS_EXCEEDED")
    ]
    assert len(doc.objects) == 10
    assert len(doc.relations) > 0
    assert [(f.code, f.object_id) for f in failures] == [("EXPORT_PROPERTY_PARSE_FAILED", "export:1")]
    assert all(item.object_id and item.stage == "properties.tagged" for item in failures)
    assert not [item for item in doc.diagnostics if item.severity == "critical"]

    def test_no_critical_on_healthy():
        critical = [d for d in doc.diagnostics if d.severity == "critical"]
        assert len(critical) == 0

    def test_diagnostics_have_stage():
        for d in doc.diagnostics:
            assert d.stage, f"Diagnostic missing stage: {d.code}"

    def test_failed_export_does_not_remove_later_objects():
        with_props = [o for o in doc.objects if o.properties is not None]
        assert len(with_props) > 0

    def test_partial_status_on_bad_export_preserves_document():
        assert doc.package.export_count == 10
        assert len(doc.objects) == 10
        assert len(doc.relations) > 0
        critical = [d for d in doc.diagnostics if d.severity == "critical"]
        assert len(critical) == 0

    def test_parse_failure_diagnostic_has_object_id():
        parse_failures = [
            d for d in doc.diagnostics if d.code in ("EXPORT_PROPERTY_PARSE_FAILED", "EXPORT_PROPERTY_BOUNDS_EXCEEDED")
        ]
        for diag in parse_failures:
            assert diag.object_id is not None
            assert diag.stage == "properties.tagged"

    def test_later_success_does_not_mask_earlier_failure():
        from uasset_read.v2 import handlers as H
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus

        class Boom:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                raise RuntimeError("boom")

        class Ok:
            capability = "decoded"

            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                return {"kind": "ok"}

        obj = ObjectRecord(
            id="export:9",
            table_index=0,
            name="X",
            class_name="Foo",
            status=ObjectStatus(parse="complete", semantic="not_requested"),
        )
        saved = H._HANDLERS[:]
        try:
            H._HANDLERS[:] = [Boom(), Ok()]
            semantic, _cov, diags = H.run_handlers(obj, H.VersionContext(), [], None)
        finally:
            H._HANDLERS[:] = saved
        assert semantic == {"kind": "ok"}
        assert obj.status.semantic == "partial"
        assert any(d.code == "HANDLER_FAILURE" for d in diags)

    def test_clean_success_still_marks_complete():
        from uasset_read.v2 import handlers as H
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus

        class Ok:
            capability = "decoded"

            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                return {"kind": "ok"}

        obj = ObjectRecord(
            id="export:9",
            table_index=0,
            name="X",
            class_name="Foo",
            status=ObjectStatus(parse="complete", semantic="not_requested"),
        )
        saved = H._HANDLERS[:]
        try:
            H._HANDLERS[:] = [Ok()]
            H.run_handlers(obj, H.VersionContext(), [], None)
        finally:
            H._HANDLERS[:] = saved
        assert obj.status.semantic == "complete"

    def test_matched_handler_returning_none_is_not_complete():
        from uasset_read.v2 import handlers as H
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus

        class Decliner:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                return None

        obj = ObjectRecord(
            id="export:9",
            table_index=0,
            name="X",
            class_name="Foo",
            status=ObjectStatus(parse="complete", semantic="not_requested"),
        )
        saved = H._HANDLERS[:]
        try:
            H._HANDLERS[:] = [Decliner()]
            semantic, _cov, _diags = H.run_handlers(obj, H.VersionContext(), [], None)
        finally:
            H._HANDLERS[:] = saved
        assert semantic is None
        assert obj.status.semantic == "partial"

    def test_parse_past_serial_end_is_flagged_not_silent():
        import uasset_read.parsers.property_parser as pp
        from uasset_read.v2.api import parse_package_document

        def fake_overrun(**kwargs):
            export = kwargs["export"]
            kwargs["archive"].seek(export.serial_offset + export.serial_size + 8)
            return []

        monkeypatch.setattr(pp, "parse_properties_from_export", fake_overrun)
        overrun_doc = parse_package_document(str(PACKAGE_SAMPLE), depth="object")
        overrun = [d for d in overrun_doc.diagnostics if d.code == "EXPORT_PROPERTY_BOUNDS_EXCEEDED"]
        assert overrun, "property parse exceeded the serial region with no diagnostic"
        assert all(d.object_id and d.stage == "properties.tagged" for d in overrun)

    def test_export_table_failure_preserves_slot_identity():
        import uasset_read.serializers.object_resources as orm
        healthy = _document(str(PACKAGE_SAMPLE), depth="package")
        first_name = healthy.objects[0].name
        second_name = healthy.objects[1].name
        real = orm.ObjectExport
        calls = {"n": 0}

        def boom(**kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise ValueError("injected export table entry failure")
            return real(**kwargs)

        monkeypatch.setattr(orm, "ObjectExport", boom)
        doc = parse_package_document(str(PACKAGE_SAMPLE))  # direct call, NOT the lru_cache'd _document
        assert doc.objects[0].name == first_name                   # slot 0 kept its identity
        assert all(o.name != second_name for o in doc.objects)     # second export did NOT become export:0
        assert any(d.code == "EXPORT_TABLE_TRUNCATED" for d in doc.diagnostics)

    def test_v2_mappings_never_passes_raw_path_string():
        calls = {}

        def spy(**kw):
            calls["mappings"] = kw.get("mappings")
            return {}

        monkeypatch.setattr(pp, "parse_properties_from_export", spy)
        doc = parse_package_document(
            str(DATA_SAMPLE), depth="object", mappings_path=str(ROOT / "no-such.usmap")
        )
        assert any(d.code == "MAPPINGS_LOAD_FAILED" for d in doc.diagnostics)
        assert not isinstance(calls.get("mappings"), str)  # never a raw path string

    def test_v2_mappings_provider_object_on_successful_load():
        import tempfile

        from uasset_read.mappings import TypeMappingsProvider

        # Minimal uncompressed version-0 .usmap: empty name/enum/struct tables.
        payload = b"\x00" * 12  # name_count=0, enum_count=0, struct_count=0
        blob = (
            (0x30C4).to_bytes(2, "little")  # FILE_MAGIC
            + bytes([0])  # version 0 (skips package/custom-version block)
            + bytes([0])  # compression method 0 (none)
            + len(payload).to_bytes(4, "little")
            + len(payload).to_bytes(4, "little")
            + payload
        )

        calls = {}

        def spy(**kw):
            calls["mappings"] = kw.get("mappings")
            return {}

        monkeypatch.setattr(pp, "parse_properties_from_export", spy)
        with tempfile.TemporaryDirectory() as td:
            ok_path = Path(td) / "ok.usmap"
            ok_path.write_bytes(blob)
            doc = parse_package_document(str(DATA_SAMPLE), depth="object", mappings_path=str(ok_path))
        assert not any(d.code == "MAPPINGS_LOAD_FAILED" for d in doc.diagnostics)
        assert isinstance(calls.get("mappings"), TypeMappingsProvider)

    def test_silent_recovery_downgrades_object_and_reaches_document():
        from uasset_read.models.diagnostics import StructuredDiagnostic
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.package.legacy import _merge_archive_recoveries

        class _RecoveringArchive:
            """Plain bounded fake — no MagicMock for UE structures."""

            def get_structured_diagnostics(self):
                return [
                    StructuredDiagnostic(
                        code="fstring_out_of_range",
                        stage="read_fstring",
                        offset=7,
                        fallback="used_empty_string",
                        message="FString overran the file",
                        object_id="export:0",
                    ),
                    StructuredDiagnostic(
                        code="EXPORT_TABLE_TRUNCATED",
                        stage="read_export_map",
                        offset=9,
                        fallback="stop_table",
                        message="stopped export table read with 1/2 entries",
                    ),
                ]

        obj = ObjectRecord(
            id="export:0", table_index=0, name="X", class_name="Foo",
            status=ObjectStatus(parse="complete", semantic="not_requested"),
        )
        diagnostics: list = []
        _merge_archive_recoveries(_RecoveringArchive(), [obj], diagnostics)
        assert obj.status.parse == "partial"  # a recovered read must not claim complete
        assert obj.status.semantic == "not_requested"  # only parse is downgraded
        assert len(diagnostics) == 2
        diag = diagnostics[0]
        assert (diag.code, diag.effect, diag.offset, diag.object_id) == (
            "fstring_out_of_range",
            "recovery",
            7,
            "export:0",
        )
        # A stop_table abort lost entries — it must not masquerade as a recovery.
        trunc = diagnostics[1]
        assert (trunc.code, trunc.effect, trunc.recoverable, trunc.object_id) == (
            "EXPORT_TABLE_TRUNCATED",
            "data_loss",
            False,
            None,
        )

    _run_cases(
        [
            ("document.test_no_critical_on_healthy", test_no_critical_on_healthy),
            ("document.test_diagnostics_have_stage", test_diagnostics_have_stage),
            (
                "diagnostics.test_failed_export_does_not_remove_later_objects",
                test_failed_export_does_not_remove_later_objects,
            ),
            (
                "diagnostics.test_partial_status_on_bad_export_preserves_document",
                test_partial_status_on_bad_export_preserves_document,
            ),
            ("diagnostics.test_parse_failure_diagnostic_has_object_id", test_parse_failure_diagnostic_has_object_id),
            (
                "handler.test_later_success_does_not_mask_earlier_failure",
                test_later_success_does_not_mask_earlier_failure,
            ),
            ("handler.test_clean_success_still_marks_complete", test_clean_success_still_marks_complete),
            (
                "handler.test_matched_handler_returning_none_is_not_complete",
                test_matched_handler_returning_none_is_not_complete,
            ),
            (
                "property.test_parse_past_serial_end_is_flagged_not_silent",
                test_parse_past_serial_end_is_flagged_not_silent,
            ),
            (
                "document.test_export_table_failure_preserves_slot_identity",
                test_export_table_failure_preserves_slot_identity,
            ),
            (
                "mappings.test_v2_mappings_never_passes_raw_path_string",
                test_v2_mappings_never_passes_raw_path_string,
            ),
            (
                "recovery.test_silent_recovery_downgrades_object_and_reaches_document",
                test_silent_recovery_downgrades_object_and_reaches_document,
            ),
            (
                "mappings.test_v2_mappings_provider_object_on_successful_load",
                test_v2_mappings_provider_object_on_successful_load,
            ),
        ]
    )


def test_handler_registry_supports_enriches_and_isolates():
    """Every registered handler must accept its class, reject others, and isolate failures."""
    from uasset_read.v2.handlers import (
        AnimBlendSpaceHandler,
        AnimCompositeHandler,
        AnimLayerInterfaceHandler,
        BlueprintFamilyHandler,
        DataTableHandler,
        MaterialHandler,
        MaterialInstanceHandler,
        MaterialFunctionHandler,
        MaterialParameterCollectionHandler,
        MeshHandler,
        PhysicalMaterialHandler,
        PhysicsAssetHandler,
        SkeletonHandler,
        StringTableHandler,
        TextureHandler,
        UserDefinedEnumHandler,
        UserDefinedStructHandler,
        get_handlers,
    )
    from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
    from uasset_read.v2.version import VersionContext

    def record(class_name):
        return ObjectRecord(id="export:0", table_index=0, name="X", class_name=class_name, status=ObjectStatus())

    def test_handlers_registered():
        assert len(get_handlers()) >= 4

    def test_expected_handlers():
        names = [type(h).__name__ for h in get_handlers()]
        assert "DataTableHandler" in names
        assert "TextureHandler" in names
        assert "TexturePayloadHandler" in names
        assert "SoundHandler" in names

    def test_supports_and_rejects():
        cases = [
            ("DataTableHandler", DataTableHandler(), "DataTable", "Blueprint"),
            ("UserDefinedEnumHandler", UserDefinedEnumHandler(), "UserDefinedEnum", "Blueprint"),
            ("UserDefinedStructHandler", UserDefinedStructHandler(), "UserDefinedStruct", "DataTable"),
            ("TextureHandler", TextureHandler(), "Texture2D", "Blueprint"),
            ("SkeletonHandler", SkeletonHandler(), "Skeleton", "Blueprint"),
            ("MeshHandler/Static", MeshHandler(), "StaticMesh", "Blueprint"),
            ("MeshHandler/Skeletal", MeshHandler(), "SkeletalMesh", "Blueprint"),
            ("MaterialHandler", MaterialHandler(), "Material", "Blueprint"),
            ("MaterialInstanceHandler", MaterialInstanceHandler(), "MaterialInstanceConstant", "Blueprint"),
            ("PhysicsAssetHandler", PhysicsAssetHandler(), "PhysicsAsset", "Blueprint"),
            ("PhysicalMaterialHandler", PhysicalMaterialHandler(), "PhysicalMaterial", "Blueprint"),
            ("AnimBlendSpaceHandler", AnimBlendSpaceHandler(), "BlendSpace1D", "Blueprint"),
            ("AnimCompositeHandler", AnimCompositeHandler(), "AnimComposite", "Blueprint"),
            ("AnimLayerInterfaceHandler", AnimLayerInterfaceHandler(), "AnimLayerInterface", "Blueprint"),
            ("StringTableHandler", StringTableHandler(), "StringTable", "DataTable"),
            ("MaterialFunctionHandler", MaterialFunctionHandler(), "MaterialFunction", "Blueprint"),
            ("MaterialParameterCollectionHandler", MaterialParameterCollectionHandler(), "MaterialParameterCollection", "Blueprint"),
            (
                "BlueprintFamilyHandler/anim",
                BlueprintFamilyHandler(
                    ("AnimBlueprint", "AnimBlueprintGeneratedClass"), "anim_blueprint", "anim_blueprint"
                ),
                "AnimBlueprintGeneratedClass",
                "StaticMesh",
            ),
            (
                "BlueprintFamilyHandler/bp",
                BlueprintFamilyHandler(("Blueprint", "BlueprintGeneratedClass"), "blueprint", "blueprint"),
                "BlueprintGeneratedClass",
                "StaticMesh",
            ),
        ]
        for name, handler, good_class, bad_class in cases:
            assert handler.supports(record(good_class), VersionContext()), f"{name} must support {good_class}"
            assert not handler.supports(record(bad_class), VersionContext()), f"{name} must reject {bad_class}"

    def test_texture_no_properties_returns_none():
        obj = ObjectRecord(
            id="export:0",
            table_index=0,
            name="Tex",
            class_name="Texture2D",
            status=ObjectStatus(),
            properties=None,
        )
        assert TextureHandler().enrich(obj, VersionContext(), [], None) is None

    def test_handler_exception_doesnt_crash():
        from uasset_read.v2.handlers import register_handler, run_handlers

        class BadHandler:
            def supports(self, obj, context):
                return True

            def enrich(self, obj, context, all_objects, package_data):
                raise RuntimeError("boom")

        original_handlers = list(get_handlers())
        try:
            register_handler(BadHandler())
            obj = ObjectRecord(id="export:0", table_index=0, name="X", class_name="Anything", status=ObjectStatus())
            semantic, cov, diags = run_handlers(obj, VersionContext(), [obj], None)
            assert semantic is None
            assert any("BadHandler" in c.feature for c in cov)
            assert any(d.stage == "semantic.handler" for d in diags)
        finally:
            from uasset_read.v2.handlers import _HANDLERS

            _HANDLERS[:] = original_handlers

    def test_handler_exception_becomes_object_diagnostic():
        import uasset_read.v2.handlers as handlers
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.version import VersionContext

        class RaisingHandler:
            def supports(self, obj, context):
                return True

            def enrich(self, obj, context, all_objects, package_data):
                raise ValueError("broken handler")

        original_handlers = list(handlers._HANDLERS)
        try:
            handlers._HANDLERS.append(RaisingHandler())
            sample_doc = parse_package_document(str(DATA_SAMPLE), depth="object", object_ids=["export:0"])
            semantic, coverage, diagnostics = handlers.run_handlers(
                sample_doc.objects[0], VersionContext(), sample_doc.objects, None
            )
            assert semantic is None
            assert any(c.status == "missing" for c in coverage)
            handler_diags = [d for d in diagnostics if d.stage == "semantic.handler"]
            assert len(handler_diags) >= 1
            assert handler_diags[0].object_id == sample_doc.objects[0].id
        finally:
            handlers._HANDLERS[:] = original_handlers

    def test_niagara_handler_supports_all_declared_classes():
        from uasset_read.v2.handlers import NiagaraHandler

        handler = NiagaraHandler()
        assert len(handler._NIAGARA_CLASSES) == 13
        for class_name in handler._NIAGARA_CLASSES:
            assert handler.supports(record(class_name), VersionContext()), class_name
        assert not handler.supports(record("StaticMesh"), VersionContext())

    def test_class_handlers_kwarg_defaults_true_for_v1():
        import inspect

        from uasset_read.parsers.property_parser import parse_properties_from_export

        param = inspect.signature(parse_properties_from_export).parameters["run_class_handlers"]
        assert param.default is True, "v1 default must keep class-handler dispatch byte-identical"

    def test_summary_tier_handlers_never_claim_complete():
        """Niagara/Mesh/Blueprint-summary results are partial with coverage (#629)."""
        from uasset_read.v2.handlers import (
            _HANDLERS,
            BlueprintFamilyHandler,
            MeshHandler,
            NiagaraHandler,
            run_handlers,
        )
        from uasset_read.v2.version import VersionContext

        cases = [
            ("NiagaraScript", NiagaraHandler()),
            ("StaticMesh", MeshHandler()),
            (
                "Blueprint",
                BlueprintFamilyHandler(("Blueprint", "BlueprintGeneratedClass"), "blueprint", "blueprint"),
            ),
        ]
        saved = list(_HANDLERS)
        try:
            for class_name, handler in cases:
                _HANDLERS[:] = [handler]
                obj = record(class_name)
                semantic, _cov, _diags = run_handlers(obj, VersionContext(depth="asset"), [obj], None)
                assert semantic, class_name
                assert obj.status.semantic == "partial", class_name
                assert obj.coverage, class_name
        finally:
            _HANDLERS[:] = saved

    def test_decode_tier_blueprint_graph_marks_complete():
        """Only decoded-tier output (Blueprint graph at depth=decode) yields complete (#629)."""
        from uasset_read.v2.handlers import _HANDLERS, BlueprintFamilyHandler, run_handlers
        from uasset_read.v2.version import VersionContext

        bp = record("Blueprint")
        node = record("K2Node_CallFunction")
        node.id = "export:1"
        handler = BlueprintFamilyHandler(
            ("Blueprint", "BlueprintGeneratedClass"), "blueprint", "blueprint"
        )
        saved = list(_HANDLERS)
        try:
            _HANDLERS[:] = [handler]
            semantic, _cov, _diags = run_handlers(
                bp, VersionContext(depth="decode"), [bp, node], None
            )
        finally:
            _HANDLERS[:] = saved
        assert "graph" in semantic
        assert bp.status.semantic == "complete"

    def test_undeclared_handler_tier_defaults_to_summary():
        from uasset_read.v2.handlers import _HANDLERS, run_handlers
        from uasset_read.v2.version import VersionContext

        class Echo:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                return {"kind": "echo"}

        obj = record("Whatever")
        saved = list(_HANDLERS)
        try:
            _HANDLERS[:] = [Echo()]
            run_handlers(obj, VersionContext(), [obj], None)
        finally:
            _HANDLERS[:] = saved
        assert obj.status.semantic == "partial"

    def test_skeleton_name_guess_is_marked_heuristic():
        """NameMap-regex bones are marked bone_source=name_guess and never complete (#630)."""
        from uasset_read.v2.handlers import _HANDLERS, SkeletonHandler, run_handlers
        from uasset_read.v2.version import VersionContext

        obj = record("Skeleton")
        name_map = ["None", "SomeWidget", "root", "pelvis", "spine_01"]
        saved = list(_HANDLERS)
        try:
            _HANDLERS[:] = [SkeletonHandler()]
            semantic, _cov, _diags = run_handlers(
                obj, VersionContext(depth="asset"), [obj], (None, name_map, None)
            )
        finally:
            _HANDLERS[:] = saved
        assert semantic["bone_source"] == "name_guess"
        assert [b["name"] for b in semantic["bones"]] == ["root", "pelvis", "spine_01"]
        assert semantic["bone_count"] == 3
        assert obj.status.semantic == "partial"
        guess = [c for c in obj.coverage if c.feature == "skeleton.bones"]
        assert len(guess) == 1
        assert guess[0].status == "partial" and "heuristic" in guess[0].detail

    def test_skeleton_bone_tree_wins_over_name_guess():
        """Decoded BoneTree names take precedence over the regex path (#630)."""
        from uasset_read.v2.handlers import _HANDLERS, SkeletonHandler, run_handlers
        from uasset_read.v2.version import VersionContext

        obj = record("Skeleton")
        obj.properties = {
            "BoneTree": {
                "kind": "value",
                "type": "ArrayProperty",
                "value": [
                    {"kind": "struct", "struct_type": "BoneNode", "fields": {"Name": "root", "ParentIndex": -1}},
                    "pelvis",
                    "pelvis",
                    {"kind": "opaque", "type": "", "size": 0, "reason": "unsupported_type"},
                ],
            }
        }
        # "head" would match the NameMap regex — its absence proves the real path won.
        name_map = ["head", "thigh_l"]
        saved = list(_HANDLERS)
        try:
            _HANDLERS[:] = [SkeletonHandler()]
            semantic, _cov, _diags = run_handlers(
                obj, VersionContext(depth="asset"), [obj], (None, name_map, None)
            )
        finally:
            _HANDLERS[:] = saved
        assert semantic["bone_source"] == "bone_tree"
        assert [b["name"] for b in semantic["bones"]] == ["root", "pelvis"]
        assert obj.status.semantic == "complete"

    def test_string_table_reader_synthetic_bytes():
        """#615: the FStringTable trailer parses namespace + key/value entries."""
        import struct

        from uasset_read.archive import ByteArchive
        from uasset_read.v2.package.legacy import _read_string_table

        def fstring(s: str) -> bytes:
            data = s.encode("utf-8") + b"\x00"
            return struct.pack("<i", len(data)) + data

        def read_table(blob: bytes, dev_notes: bool):
            diags = []
            archive = ByteArchive(blob)
            archive._read_range = (0, len(blob))
            result = _read_string_table(archive, "export:0", diags, dev_notes)
            return result, diags

        # UE4-era layout: key + value only.
        blob = fstring("MyNS") + struct.pack("<i", 2) + fstring("K1") + fstring("Hello") + fstring("K2") + fstring("World")
        result, diags = read_table(blob, dev_notes=False)
        assert result["namespace"] == "MyNS"
        assert result["entry_count"] == 2
        assert result["entries"] == [{"key": "K1", "value": "Hello"}, {"key": "K2", "value": "World"}]
        assert result["complete"] and not diags

        # DevNotes variant (StringTableCore.cpp writes a third string per
        # entry for editor-saved packages with the AddDevNotesToFText version).
        blob_dev = fstring("NS") + struct.pack("<i", 1) + fstring("A") + fstring("V") + fstring("notes")
        result, diags = read_table(blob_dev, dev_notes=True)
        assert result["entries"] == [{"key": "A", "value": "V"}]
        assert result["complete"] and not diags

        # Garbage entry count: diagnostic, no entries trusted.
        blob = fstring("NS") + struct.pack("<i", 10**7)
        result, diags = read_table(blob, dev_notes=False)
        assert not result["complete"] and not result["entries"]
        assert [d.code for d in diags] == ["TABLE_ENTRY_COUNT_INVALID"]

        # Truncated entries: bounded failure with diagnostic, never silent.
        blob = fstring("NS") + struct.pack("<i", 5) + fstring("K") + fstring("V")
        result, diags = read_table(blob, dev_notes=False)
        assert not result["complete"]
        assert [d.code for d in diags] == ["STRING_TABLE_TRUNCATED"]

    def test_string_table_handler_is_summary_and_not_table():
        """#615: StringTable uses StringTableHandler and never claims complete."""
        from uasset_read.v2.handlers import (
            _HANDLERS,
            DataTableHandler,
            StringTableHandler,
            run_handlers,
        )
        from uasset_read.v2.version import VersionContext

        assert not DataTableHandler().supports(record("StringTable"), VersionContext())
        assert DataTableHandler().supports(record("DataTable"), VersionContext())
        assert StringTableHandler().supports(record("StringTable"), VersionContext())

        obj = record("StringTable")
        obj.id = "export:5"
        st = {
            "namespace": "MyNS",
            "entry_count": 1,
            "entries": [{"key": "K", "value": "V"}],
            "complete": True,
        }
        saved = list(_HANDLERS)
        try:
            _HANDLERS[:] = [DataTableHandler(), StringTableHandler()]
            semantic, _cov, _diags = run_handlers(
                obj, VersionContext(depth="asset"), [obj], (None, [], {obj.id: {"string_table": st}})
            )
        finally:
            _HANDLERS[:] = saved
        assert semantic["kind"] == "string_table"
        assert semantic["namespace"] == "MyNS"
        assert semantic["entry_count"] == 1
        assert semantic["entries"] == [{"key": "K", "value": "V"}]
        assert obj.status.semantic == "partial", "StringTable must not claim semantic=complete (#615)"

    def test_string_table_handler_missing_trailer_reports_coverage():
        from uasset_read.v2.handlers import StringTableHandler
        from uasset_read.v2.version import VersionContext

        obj = record("StringTable")
        result = StringTableHandler().enrich(obj, VersionContext(), [], (None, [], {}))
        assert result["kind"] == "string_table"
        cov = [c for c in obj.coverage if c.feature == "handler.StringTableHandler"]
        assert len(cov) == 1 and cov[0].status == "missing"

    def test_physics_handlers_summary_tier_synthetic():
        """#619: physics handlers read real fields but never claim complete."""
        from uasset_read.v2.handlers import (
            _HANDLERS,
            PhysicsAssetHandler,
            PhysicalMaterialHandler,
            run_handlers,
        )
        from uasset_read.v2.version import VersionContext

        pa = record("PhysicsAsset")
        pa.properties = {
            "SkeletalBodySetups": {"kind": "value", "type": "ArrayProperty", "value": ["ref0", "ref1"]},
            "ConstraintSetup": {"kind": "value", "type": "ArrayProperty", "value": []},
        }
        body = record("SkeletalBodySetup")
        body.id = "export:1"
        body.name = "Body_pelvis"
        pm = record("PhysicalMaterial")
        pm.properties = {
            "Friction": {"kind": "value", "type": "FloatProperty", "value": 0.7},
            "Restitution": {"kind": "value", "type": "FloatProperty", "value": 0.2},
            "Density": {"kind": "value", "type": "FloatProperty", "value": 0},
            "SurfaceType": {"kind": "value", "type": "ByteProperty", "value": {"value_name": "SCE_Plastic"}},
        }
        saved = list(_HANDLERS)
        try:
            _HANDLERS[:] = [PhysicsAssetHandler(), PhysicalMaterialHandler()]
            sem_pa, _c, _d = run_handlers(pa, VersionContext(depth="asset"), [pa, body], None)
            sem_pm, _c, _d = run_handlers(pm, VersionContext(depth="asset"), [pm], None)
            empty_pm = record("PhysicalMaterial")
            empty_pm.properties = {}
            sem_empty, _c, _d = run_handlers(empty_pm, VersionContext(depth="asset"), [empty_pm], None)
        finally:
            _HANDLERS[:] = saved

        assert sem_pa["kind"] == "physics_asset"
        assert sem_pa["body_count"] == 2
        assert sem_pa["constraint_count"] == 0
        assert sem_pa["bodies"] == ["Body_pelvis"]
        assert pa.status.semantic == "partial"
        disable = [c for c in pa.coverage if c.feature == "physics_asset.collision_disable_table"]
        assert disable and disable[0].status == "missing"

        assert sem_pm["friction"] == 0.7
        assert sem_pm["restitution"] == 0.2
        assert sem_pm["density"] == 0
        assert sem_pm["surface_type"] == "SCE_Plastic"
        assert pm.status.semantic == "partial"
        assert sem_empty is None
        assert empty_pm.status.semantic == "partial"

    def test_anim_handlers_summary_tier_synthetic():
        """#618: blend space axes/samples, composite track, ALI missing-function state."""
        from uasset_read.v2.handlers import (
            _HANDLERS,
            AnimBlendSpaceHandler,
            AnimCompositeHandler,
            AnimLayerInterfaceHandler,
            run_handlers,
        )
        from uasset_read.v2.version import VersionContext

        bs = record("BlendSpace")
        bs.properties = {
            "BlendParameters": {
                "kind": "value",
                "type": "ArrayProperty",
                "value": [
                    {"kind": "struct", "struct_type": "BlendParameter", "fields": {"DisplayName": "Speed", "Min": 0.0, "Max": 200.0, "GridNum": 7}},
                    {"kind": "struct", "struct_type": "BlendParameter", "fields": {"DisplayName": "Direction", "Min": -90.0, "Max": 90.0, "GridNum": 5}},
                    {"kind": "struct", "struct_type": "BlendParameter", "fields": {"DisplayName": "None", "Min": 0.0, "Max": 0.0, "GridNum": 2}},
                ],
            },
            "SampleData": {
                "kind": "value",
                "type": "ArrayProperty",
                "value": [
                    {
                        "kind": "struct",
                        "struct_type": "BlendSample",
                        "fields": {
                            "Animation": "AnimSequence'A_Walk'",
                            "SampleValue": {"kind": "struct", "struct_type": "Vector", "fields": {"X": 100.0, "Y": 45.0, "Z": 0.0}},
                        },
                    }
                ],
            },
        }
        comp = record("AnimComposite")
        comp.properties = {
            "AnimationTrack": {
                "kind": "struct",
                "struct_type": "AnimTrack",
                "fields": {
                    "AnimSegments": [
                        {
                            "kind": "struct",
                            "struct_type": "AnimSegment",
                            "fields": {"AnimReference": "AnimSequence'A_Run'", "StartPos": 0.0, "AnimStartTime": 0.0, "AnimEndTime": 1.5},
                        }
                    ]
                },
            }
        }
        ali = record("AnimLayerInterface")
        ali.properties = {}
        bare = record("BlendSpace1D")
        bare.properties = {}

        saved = list(_HANDLERS)
        try:
            _HANDLERS[:] = [AnimBlendSpaceHandler(), AnimCompositeHandler(), AnimLayerInterfaceHandler()]
            sem_bs, _c, _d = run_handlers(bs, VersionContext(depth="asset"), [bs], None)
            sem_comp, _c, _d = run_handlers(comp, VersionContext(depth="asset"), [comp], None)
            sem_ali, _c, _d = run_handlers(ali, VersionContext(depth="asset"), [ali], None)
            sem_bare, _c, _d = run_handlers(bare, VersionContext(depth="asset"), [bare], None)
        finally:
            _HANDLERS[:] = saved

        assert sem_bs["kind"] == "anim_blend_space"
        assert sem_bs["dimension"] == 2, "unconfigured BlendParameters slot must not count as an axis"
        assert [a["name"] for a in sem_bs["axes"]] == ["Speed", "Direction"]
        assert sem_bs["axes"][0]["max"] == 200.0
        assert sem_bs["sample_count"] == 1
        assert sem_bs["samples"][0] == {"animation": "AnimSequence'A_Walk'", "position": [100.0, 45.0, 0.0]}
        assert bs.status.semantic == "partial"

        assert sem_comp["segment_count"] == 1
        assert sem_comp["segments"][0]["animation"] == "AnimSequence'A_Run'"
        assert sem_comp["segments"][0]["end_time"] == 1.5
        assert comp.status.semantic == "partial"

        assert sem_ali["kind"] == "anim_layer_interface"
        assert "functions" not in sem_ali
        ali_cov = [c for c in ali.coverage if c.feature == "anim_layer_interface.functions"]
        assert ali_cov and ali_cov[0].status == "missing"
        assert ali.status.semantic == "partial"

        assert sem_bare["blend_space_type"] == "BlendSpace1D"
        bare_axes = [c for c in bare.coverage if c.feature == "anim_blend_space.axes"]
        bare_samples = [c for c in bare.coverage if c.feature == "anim_blend_space.samples"]
        assert bare_axes and bare_axes[0].status == "missing"
        assert bare_samples and bare_samples[0].status == "missing"

    def test_material_family_handlers_summary_tier_synthetic():
        """#620: function I/O from expression exports; MPC scalar/vector params."""
        from uasset_read.v2.handlers import (
            _HANDLERS,
            MaterialFunctionHandler,
            MaterialParameterCollectionHandler,
            run_handlers,
        )
        from uasset_read.v2.version import VersionContext

        fn = record("MaterialFunction")
        inp = record("MaterialExpressionFunctionInput")
        inp.id = "export:1"
        inp.properties = {"InputName": {"kind": "value", "type": "NameProperty", "value": "Speed"}}
        out = record("MaterialExpressionFunctionOutput")
        out.id = "export:2"
        out.properties = {"OutputName": {"kind": "value", "type": "NameProperty", "value": "Emissive"}}
        call = record("MaterialExpressionMaterialFunctionCall")
        call.id = "export:3"
        add = record("MaterialExpressionAdd")
        add.id = "export:4"

        mpc = record("MaterialParameterCollection")
        mpc.properties = {
            "ScalarParameters": {
                "kind": "value",
                "type": "ArrayProperty",
                "value": [
                    {
                        "kind": "struct",
                        "struct_type": "CollectionScalarParameter",
                        "fields": {"ParameterName": "Intensity", "DefaultValue": 0.5},
                    }
                ],
            },
            "VectorParameters": {
                "kind": "value",
                "type": "ArrayProperty",
                "value": [
                    {
                        "kind": "struct",
                        "struct_type": "CollectionVectorParameter",
                        "fields": {
                            "ParameterName": "Tint",
                            "DefaultValue": {"kind": "struct", "struct_type": "LinearColor", "fields": {"R": 1.0, "G": 0.0, "B": 0.5, "A": 1.0}},
                        },
                    }
                ],
            },
        }
        bare_fn = record("MaterialFunction")
        bare_fn.properties = {}

        saved = list(_HANDLERS)
        try:
            _HANDLERS[:] = [MaterialFunctionHandler(), MaterialParameterCollectionHandler()]
            sem_fn, _c, _d = run_handlers(fn, VersionContext(depth="asset"), [fn, inp, out, call, add], None)
            sem_mpc, _c, _d = run_handlers(mpc, VersionContext(depth="asset"), [mpc], None)
            sem_bfn, _c, _d = run_handlers(bare_fn, VersionContext(depth="asset"), [bare_fn], None)
        finally:
            _HANDLERS[:] = saved

        assert sem_fn["kind"] == "material_function"
        assert sem_fn["input_names"] == ["Speed"]
        assert sem_fn["output_names"] == ["Emissive"]
        assert sem_fn["expression_count"] == 4
        assert sem_fn["function_call_count"] == 1
        assert fn.status.semantic == "partial"

        assert sem_mpc["scalar_param_count"] == 1
        assert sem_mpc["scalar_params"] == [{"name": "Intensity", "default_value": 0.5}]
        assert sem_mpc["vector_param_count"] == 1
        assert sem_mpc["vector_params"] == [{"name": "Tint", "default_rgba": [1.0, 0.0, 0.5, 1.0]}]
        assert mpc.status.semantic == "partial"

        assert sem_bfn["expression_count"] == 0
        expr_cov = [c for c in bare_fn.coverage if c.feature == "material_function.expressions"]
        assert expr_cov and expr_cov[0].status == "missing"

    _run_cases(
        [
            ("handler.test_handlers_registered", test_handlers_registered),
            ("handler.test_expected_handlers", test_expected_handlers),
            ("handler.test_supports_and_rejects", test_supports_and_rejects),
            ("handler.test_texture_no_properties_returns_none", test_texture_no_properties_returns_none),
            ("handler.test_handler_exception_doesnt_crash", test_handler_exception_doesnt_crash),
            (
                "handler.test_handler_exception_becomes_object_diagnostic",
                test_handler_exception_becomes_object_diagnostic,
            ),
            (
                "handler.test_niagara_handler_supports_all_declared_classes",
                test_niagara_handler_supports_all_declared_classes,
            ),
            ("handler.test_class_handlers_kwarg_defaults_true_for_v1", test_class_handlers_kwarg_defaults_true_for_v1),
            ("handler.test_summary_tier_handlers_never_claim_complete", test_summary_tier_handlers_never_claim_complete),
            ("handler.test_decode_tier_blueprint_graph_marks_complete", test_decode_tier_blueprint_graph_marks_complete),
            ("handler.test_undeclared_handler_tier_defaults_to_summary", test_undeclared_handler_tier_defaults_to_summary),
            ("handler.test_skeleton_name_guess_is_marked_heuristic", test_skeleton_name_guess_is_marked_heuristic),
            ("handler.test_skeleton_bone_tree_wins_over_name_guess", test_skeleton_bone_tree_wins_over_name_guess),
            ("handler.test_string_table_reader_synthetic_bytes", test_string_table_reader_synthetic_bytes),
            (
                "handler.test_string_table_handler_is_summary_and_not_table",
                test_string_table_handler_is_summary_and_not_table,
            ),
            (
                "handler.test_string_table_handler_missing_trailer_reports_coverage",
                test_string_table_handler_missing_trailer_reports_coverage,
            ),
            ("handler.test_physics_handlers_summary_tier_synthetic", test_physics_handlers_summary_tier_synthetic),
            ("handler.test_anim_handlers_summary_tier_synthetic", test_anim_handlers_summary_tier_synthetic),
            (
                "handler.test_material_family_handlers_summary_tier_synthetic",
                test_material_family_handlers_summary_tier_synthetic,
            ),
        ]
    )


def test_projection_views_depths_pagination_table():
    """View shape, pagination, and selection contracts on one synthetic-parse document."""
    from uasset_read.v2.projection import paginate, project_document, select_objects

    doc = _document(depth="asset")

    def test_semantic_default():
        assert project_document(doc)["view"] == "semantic"

    def test_raw_has_flags():
        result = project_document(doc, view="raw", limit=2)
        for obj in result["objects"]:
            assert "flags" in obj
            assert "serial_region" in obj

    def test_debug_has_stats():
        result = project_document(doc, view="debug")
        assert "debug" in result
        assert "total_objects" in result["debug"]

    def test_invalid_view_raises():
        with pytest.raises(ValueError, match="Invalid view"):
            project_document(doc, view="invalid")

    def test_semantic_no_raw_fields():
        result = project_document(doc, view="semantic", limit=2)
        for obj in result["objects"]:
            assert "flags" not in obj
            assert "serial_region" not in obj
            assert "properties" not in obj

    def test_limit_truncates():
        items = list(range(10))
        page, next_offset, info = paginate(items, offset=0, limit=3)
        assert len(page) == 3
        assert next_offset == 3
        assert info["truncated"] == 1

    def test_offset_skips():
        items = list(range(10))
        page, next_offset, info = paginate(items, offset=5, limit=3)
        assert page == [5, 6, 7]
        assert next_offset == 8

    def test_no_limit_returns_all():
        items = list(range(10))
        page, next_offset, info = paginate(items, offset=0)
        assert len(page) == 10
        assert next_offset is None
        assert info["truncated"] == 0

    def test_page_through_all():
        all_objects = []
        offset = 0
        while True:
            result = project_document(doc, limit=3, offset=offset)
            all_objects.extend(result["objects"])
            if "next_offset" not in result:
                break
            offset = result["next_offset"]
        assert len(all_objects) == len(doc.objects)

    def test_select_by_role():
        asset_objs = select_objects(doc, roles=["asset"])
        assert len(asset_objs) >= 2

    def test_select_by_id():
        result = select_objects(doc, object_ids=["export:0", "export:1"])
        assert len(result) == 2

    def test_select_all_when_no_filters():
        result = select_objects(doc)
        assert len(result) == len(doc.objects)

    def dependencies_carry_package_name():
        # #632: the model carries package_name from the import map; no
        # projection path may drop it.
        from uasset_read.v2.projection import dependency_to_dict

        page = project_document(doc, limit=100)
        assert page["dependencies"], "fixture must expose page-reachable imports"
        model = {d.index: d for d in doc.dependencies}
        for entry in page["dependencies"]:
            assert set(entry) == {"index", "class", "object_name", "package_name"}
            assert entry == dependency_to_dict(model[entry["index"]])

    def semantic_object_depth_carries_properties_summary():
        # #636: bounded compact property view replaces the raw bag in semantic.
        obj_doc = _document(str(PACKAGE_SAMPLE), depth="object")
        page = project_document(obj_doc, depth="object", view="semantic")
        with_props = [o for o in page["objects"] if "properties_summary" in o]
        assert with_props, "object-depth fixture must produce at least one summary"
        for o in with_props:
            assert "properties" not in o, "full bag stays raw/debug-only"
            summary = o["properties_summary"]
            assert set(summary) == {"properties", "property_count"}
            assert summary["property_count"] >= len(summary["properties"])
            blob = json.dumps(summary, separators=(",", ":"))
            assert '"fields":' not in blob, "structs must be length-elided"
            assert '"raw_data' not in blob, "raw bytes must not ride along"
            assert '"value":[' not in blob, "array values must be length-elided"
        raw_page = project_document(obj_doc, depth="object", view="raw", limit=5)
        for o in raw_page["objects"]:
            assert "properties_summary" not in o, "raw view carries the full bag, not the summary"

    def package_depth_document_has_no_summary():
        pkg_doc = _document(str(PACKAGE_SAMPLE), depth="package")
        page = project_document(pkg_doc, depth="package", view="semantic")
        for o in page["objects"]:
            assert "properties_summary" not in o

    def test_all_views_json():
        for view in ("semantic", "raw", "debug"):
            result = project_document(doc, view=view, limit=3)
            json_str = json.dumps(result, ensure_ascii=False)
            parsed = json.loads(json_str)
            assert parsed["view"] == view

    def core_projection_honors_views():
        # View shape: semantic omits raw fields, raw includes them
        pkg_doc = _document()
        sem_obj = project_document(pkg_doc, depth="package", view="semantic", limit=2)["objects"][0]
        raw_obj = project_document(pkg_doc, depth="package", view="raw", limit=2)["objects"][0]
        assert "flags" not in sem_obj
        assert "serial_region" not in sem_obj
        assert "properties" not in sem_obj
        assert "flags" in raw_obj
        assert "serial_region" in raw_obj
        assert "debug" in project_document(pkg_doc, depth="package", view="debug", limit=2)

        # Pagination and byte budget
        full = project_document(pkg_doc, depth="package", limit=100)
        full_size = len(json.dumps(full, separators=(",", ":")).encode())
        # budget must exceed minimal reachable envelope (depends_on imports)
        # but be less than the full page to trigger truncation
        budget = full_size - 1000
        page = project_document(pkg_doc, depth="package", limit=100, max_bytes=budget)
        assert len(json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode()) <= budget
        assert page["next_offset"] > 0
        assert page["truncation"]["reason"] == "max_bytes"

        # fields filter: only requested fields plus id/name are returned
        result = project_document(pkg_doc, depth="package", limit=2, fields=["id"])
        assert len(result["objects"]) == 2
        assert set(result["objects"][0].keys()).issubset({"id", "name"})
        assert isinstance(result["payloads"], list)
        assert isinstance(result["relations"], list)

    def depth_beyond_parsed_document_raises():
        pkg_doc = _document(str(PACKAGE_SAMPLE), depth="package")
        with pytest.raises(ValueError, match="cannot project"):
            project_document(pkg_doc, depth="asset")

    def shallower_depth_caps_content():
        asset_doc = _document(str(PACKAGE_SAMPLE), depth="asset")
        page = project_document(asset_doc, depth="package", view="raw")
        for o in page["objects"]:
            assert "semantic" not in o and "coverage" not in o and "properties" not in o
        obj_page = project_document(asset_doc, depth="object")
        for o in obj_page["objects"]:
            assert "semantic" not in o
        sem_pkg = project_document(asset_doc, depth="package", view="semantic")
        for o in sem_pkg["objects"]:
            assert "properties_summary" not in o, "summary needs depth >= object"
        assert project_document(asset_doc, depth="asset")["depth"] == "asset"

    def relations_carry_optional_target_path():
        pkg_doc = _document(str(PACKAGE_SAMPLE), depth="asset")
        page = project_document(pkg_doc, depth="package")
        display = {o.id: o.name for o in pkg_doc.objects}
        for d in pkg_doc.dependencies:
            display[f"import:{d.index}"] = f"{d.package_name}.{d.object_name}" if d.package_name else d.object_name
        rels = page["relations"]
        assert any(r["kind"] == "class_of" and r["to"].startswith("import:") for r in rels)
        assert any(r["kind"] == "outer_of" and r["to"].startswith("export:") for r in rels)
        for rel in rels:
            if rel["to"] in display:
                assert rel.get("target_path") == display[rel["to"]]
            else:
                assert "target_path" not in rel
        # from/kind/to themselves are untouched
        base = {(r.kind, r.from_id, r.to_id) for r in pkg_doc.relations}
        for rel in rels:
            assert (rel["kind"], rel["from"], rel["to"]) in base
            assert set(rel) <= {"kind", "from", "to", "target_path"}

    _run_cases(
        [
            ("projection.test_semantic_default", test_semantic_default),
            ("projection.test_raw_has_flags", test_raw_has_flags),
            ("projection.test_debug_has_stats", test_debug_has_stats),
            ("projection.test_invalid_view_raises", test_invalid_view_raises),
            ("projection.test_semantic_no_raw_fields", test_semantic_no_raw_fields),
            ("projection.test_limit_truncates", test_limit_truncates),
            ("projection.test_offset_skips", test_offset_skips),
            ("projection.test_no_limit_returns_all", test_no_limit_returns_all),
            ("projection.test_page_through_all", test_page_through_all),
            ("projection.test_select_by_role", test_select_by_role),
            ("projection.test_select_by_id", test_select_by_id),
            ("projection.test_select_all_when_no_filters", test_select_all_when_no_filters),
            ("projection.dependencies_carry_package_name", dependencies_carry_package_name),
            ("projection.semantic_object_depth_carries_properties_summary", semantic_object_depth_carries_properties_summary),
            ("projection.package_depth_document_has_no_summary", package_depth_document_has_no_summary),
            ("projection.test_all_views_json", test_all_views_json),
            ("core.test_projection_honors_views_pagination_and_byte_budget", core_projection_honors_views),
            ("projection.depth_beyond_parsed_document_raises", depth_beyond_parsed_document_raises),
            ("projection.shallower_depth_caps_content", shallower_depth_caps_content),
            ("projection.relations_carry_optional_target_path", relations_carry_optional_target_path),
        ]
    )


def test_projection_byte_budget_and_fields_filter():
    """The encoded page must respect max_bytes and re-scope relations/diagnostics."""
    from uasset_read.v2.projection import project_document

    doc = _document(depth="asset")

    def test_max_bytes_is_enforced_and_continuable():
        empty = project_document(doc, limit=0)
        envelope_size = len(json.dumps(empty, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        # must fit at least one object, else the page all-drops (24000 covers
        # export:0's dense relations, target_path strings, and its bounded
        # properties_summary)
        budget = envelope_size + 24000
        page = project_document(doc, limit=100, max_bytes=budget)
        encoded = json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        assert len(encoded) <= budget
        assert page["truncation"]["reason"] == "max_bytes"
        assert page["next_offset"] > 0
        assert any(d["code"] == "TRUNCATED" for d in page["diagnostics"])

    def all_objects_dropped_yields_no_cursor():
        empty = project_document(doc, limit=0)
        envelope = len(json.dumps(empty, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        page = project_document(doc, limit=100, max_bytes=envelope + 1)
        assert page["objects"] == []
        assert "next_offset" not in page, "all-dropped page must not hand out a cursor"
        assert page["truncation"]["objects_dropped"] == 10
        assert any(d["code"] == "BUDGET_EXHAUSTED" for d in page["diagnostics"])

    def every_object_returned_exactly_once_under_budget():
        empty = project_document(doc, limit=0)
        envelope_size = len(json.dumps(empty, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        seen = []
        offset = 0
        while True:
            page = project_document(doc, offset=offset, limit=100, max_bytes=envelope_size + 24000)
            seen += [o["id"] for o in page["objects"]]
            if "next_offset" not in page:
                break
            assert page["next_offset"] > offset, "cursor must be strictly monotonic"
            offset = page["next_offset"]
        assert sorted(seen) == sorted(f"export:{i}" for i in range(10))

    def dropped_count_is_page_relative():
        empty = project_document(doc, limit=0)
        envelope = len(json.dumps(empty, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        page = project_document(doc, offset=5, limit=100, max_bytes=envelope + 1)
        assert page["truncation"]["objects_dropped"] == 5

    def limit_and_budget_compose_page_relative():
        # With limit=2 only min(limit, len(selected)-offset)=2 objects are in
        # play; the dropped count must stay page-relative, not 10-kept.
        one = project_document(doc, limit=1, max_bytes=1_000_000)
        one_size = len(json.dumps(one, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        page = project_document(doc, offset=0, limit=2, max_bytes=one_size + 500)
        assert len(page["objects"]) == 1, "budget should keep exactly one of the two page objects"
        assert page["truncation"]["objects_dropped"] == 1

    def out_of_range_empty_page_never_stalls_or_overshoots():
        with pytest.raises(ValueError, match="too small"):
            project_document(doc, offset=10, limit=100, max_bytes=64)
        page = project_document(doc, offset=10, limit=100, max_bytes=1000)
        assert page["objects"] == []
        assert "next_offset" not in page, "empty page must not hand out a self-pointing cursor"

    def test_truncated_page_rescopes_relations_and_dependencies():
        """Popping objects for max_bytes must re-scope relations and dependencies."""
        empty = project_document(doc, limit=0)
        envelope_size = len(json.dumps(empty, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        budget = envelope_size + 24000  # fits 1-2 of 10 objects: a genuine partial page, not an all-drop
        page = project_document(doc, limit=100, max_bytes=budget)
        page_ids = {o["id"] for o in page["objects"]}
        assert len(page_ids) > 0, "page must keep at least one object for the re-scope checks to mean anything"
        assert len(page_ids) < 10, "budget should force dropping at least one object"
        for rel in page["relations"]:
            assert rel["from"] in page_ids, f"relation kept for dropped object: {rel}"
        targets = {rel["to"] for rel in page["relations"]}
        for dep in page["dependencies"]:
            assert f"import:{dep['index']}" in targets, f"dependency not reachable from page: {dep}"

    def test_relations_scoped_to_returned_page():
        page = project_document(doc, limit=2)
        page_ids = {o["id"] for o in page["objects"]}
        assert len(page_ids) == 2
        for r in page["relations"]:
            assert r["from"] in page_ids

    def test_object_diagnostics_scoped_to_page():
        page = project_document(doc, limit=2)
        page_ids = {o["id"] for o in page["objects"]}
        for d in page["diagnostics"]:
            oid = d.get("object_id")
            assert oid is None or oid in page_ids

    def test_budget_too_small_raises():
        with pytest.raises(ValueError, match="too small"):
            project_document(doc, max_bytes=64)

    def test_no_truncation_when_budget_generous():
        page = project_document(doc, limit=2, max_bytes=1_000_000)
        assert page.get("truncation") is None or page["truncation"].get("reason") != "max_bytes"

    def sections_opt_out_drops_scope_before_budget():
        # #631: sections is an allowlist of the scoped envelope sections;
        # excluded ones never enter the response, so max_bytes measures the
        # leaner envelope (default behavior with sections=None is unchanged).
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

        def size(d: dict) -> int:
            return len(json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

        default = project_document(doc, limit=3)
        assert "relations" in default and "dependencies" in default
        both = project_document(doc, limit=3, sections=[])
        assert "relations" not in both and "dependencies" not in both
        jsonschema.validate(both, schema)
        assert size(both) < size(default), "opted-out sections must free bytes"
        rel_only = project_document(doc, limit=3, sections=["relations"])
        assert "relations" in rel_only and "dependencies" not in rel_only
        with pytest.raises(ValueError, match="Invalid sections"):
            project_document(doc, sections=["objects"])

        full = project_document(doc, limit=100)
        trimmed = project_document(doc, limit=100, max_bytes=size(full) - 400)
        assert len(trimmed["objects"]) < 100, "budget should have trimmed the default page"
        lean = project_document(doc, limit=100, sections=[], max_bytes=size(trimmed))
        assert len(lean["objects"]) >= len(trimmed["objects"]), "freed bytes go to the object page"
        for rel in lean.get("relations", []):
            assert rel["from"] in {o["id"] for o in lean["objects"]}

    def core_fields_filter_scopes_payloads():
        pkg_doc = _document()
        result = project_document(pkg_doc, depth="package", limit=2, fields=["class"])
        assert len(result["objects"]) == 2
        assert set(result["objects"][0]).issubset({"id", "name", "class"})
        assert isinstance(result["payloads"], list)
        assert isinstance(result["relations"], list)

    def core_fields_properties_in_raw_view():
        obj_doc = _document(depth="object")
        result = project_document(obj_doc, depth="object", view="raw", limit=2, fields=["properties"])
        assert len(result["objects"]) == 2
        for obj in result["objects"]:
            assert set(obj.keys()).issubset({"id", "name", "properties"})
            assert "properties" in obj  # object-depth raw view carries the property bag
            assert "serial_region" not in obj  # not in requested fields

    def core_fields_properties_absent_in_semantic_view():
        pkg_doc = _document()
        result = project_document(pkg_doc, depth="package", view="semantic", limit=2, fields=["properties"])
        assert len(result["objects"]) == 2
        for obj in result["objects"]:
            # semantic view never has properties, so fields=["properties"] yields only id/name
            assert set(obj.keys()).issubset({"id", "name"})

    def core_max_bytes_caps_final_output():
        pkg_doc = _document()
        full = project_document(pkg_doc, depth="package", limit=100)
        full_size = len(json.dumps(full, separators=(",", ":")).encode())
        budget = full_size - 1000  # strictly less than full page
        page = project_document(pkg_doc, depth="package", limit=100, max_bytes=budget)
        final = len(json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode())
        assert final <= budget
        assert page["truncation"]["reason"] == "max_bytes"
        assert page["next_offset"] > 0

    _run_cases(
        [
            ("projection.test_max_bytes_is_enforced_and_continuable", test_max_bytes_is_enforced_and_continuable),
            ("projection.all_objects_dropped_yields_no_cursor", all_objects_dropped_yields_no_cursor),
            ("projection.every_object_returned_exactly_once_under_budget", every_object_returned_exactly_once_under_budget),
            ("projection.dropped_count_is_page_relative", dropped_count_is_page_relative),
            ("projection.limit_and_budget_compose_page_relative", limit_and_budget_compose_page_relative),
            ("projection.out_of_range_empty_page_never_stalls_or_overshoots", out_of_range_empty_page_never_stalls_or_overshoots),
            (
                "projection.test_truncated_page_rescopes_relations_and_dependencies",
                test_truncated_page_rescopes_relations_and_dependencies,
            ),
            ("projection.test_relations_scoped_to_returned_page", test_relations_scoped_to_returned_page),
            ("projection.test_object_diagnostics_scoped_to_page", test_object_diagnostics_scoped_to_page),
            ("projection.test_budget_too_small_raises", test_budget_too_small_raises),
            ("projection.test_no_truncation_when_budget_generous", test_no_truncation_when_budget_generous),
            ("projection.sections_opt_out_drops_scope_before_budget", sections_opt_out_drops_scope_before_budget),
            (
                "core.test_projection_fields_filter_does_not_crash_and_scopes_payloads",
                core_fields_filter_scopes_payloads,
            ),
            (
                "core.test_fields_properties_available_in_raw_view",
                core_fields_properties_in_raw_view,
            ),
            (
                "core.test_fields_properties_absent_in_semantic_view",
                core_fields_properties_absent_in_semantic_view,
            ),
            ("core.test_max_bytes_caps_final_output_including_truncation_block", core_max_bytes_caps_final_output),
        ]
    )


def test_schema_contract_statics():
    """The shipped schema must validate the example and match code enumerations."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_example_validates_against_schema():
        """The checked contract example must validate against the schema."""
        jsonschema.validate(json.loads(EXAMPLE.read_text(encoding="utf-8")), schema)

    def test_schema_has_required_fields():
        required = set(schema.get("required", []))
        assert "format" in required
        assert "format_version" in required
        assert "view" in required
        assert "depth" in required
        assert "source" in required
        assert "package" in required
        assert "objects" in required
        assert "payloads" in required
        assert "diagnostics" in required
        assert "summary" in required
        # #631: these ride along unless the requester opts the section out,
        # so they are properties but not required keys.
        assert "relations" in schema["properties"] and "relations" not in required
        assert "dependencies" in schema["properties"] and "dependencies" not in required

    def test_schema_enums_match_code():
        view_enum = schema["properties"]["view"]["enum"]
        assert set(view_enum) == {"semantic", "raw", "debug"}

        depth_enum = schema["properties"]["depth"]["enum"]
        assert set(depth_enum) == {"package", "object", "asset", "decode"}

    def ue4_version_constants_are_pinned_to_peer_numbering():
        """UE4 file versions carry 4.x-era ordinals; newer UE5 headers renumbered -1
        (Epic's 'version clash'). Values below match CUE4Parse/UAssetAPI/uasset-rs
        mirrors; changing them without a real boundary-version fixture is forbidden."""
        from uasset_read import constants as K
        expected = {
            "UE4_LOAD_FOR_EDITOR_GAME": 365,
            "UE4_ADD_STRING_ASSET_REFERENCES_MAP": 384,
            "UE4_SERIALIZE_TEXT_IN_PACKAGES": 459,
            "UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT": 485,
            "UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS": 507,
            "UE4_TemplateIndex_IN_COOKED_EXPORTS": 508,
            "UE4_ADDED_SEARCHABLE_NAMES": 510,
            "UE4_64BIT_EXPORTMAP_SERIALSIZES": 511,
            "UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID": 516,
            "UE4_ADDED_PACKAGE_OWNER": 518,
            "UE4_NON_OUTER_PACKAGE_IMPORT": 520,
        }
        for name, value in expected.items():
            assert getattr(K, name) == value, f"{name} drifted: {getattr(K, name)} != {value}"

    _run_cases(
        [
            ("schema.test_example_validates_against_schema", test_example_validates_against_schema),
            ("schema.test_schema_has_required_fields", test_schema_has_required_fields),
            ("schema.test_schema_enums_match_code", test_schema_enums_match_code),
            ("schema.ue4_version_constants_are_pinned_to_peer_numbering", ue4_version_constants_are_pinned_to_peer_numbering),
        ]
    )


def test_cli_python_agent_share_default_projection_and_logging_inert(tmp_path, monkeypatch):
    """CLI (default v2), Python API, and agent tools must agree; parsing must be side-effect free."""
    from uasset_read.v2.agent_tools import (
        extract_payload,
        get_diagnostics,
        get_object,
        inspect_package,
        list_dependencies,
        list_objects,
    )
    from uasset_read.v2.projection import project_document

    _env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

    def run_cli_json(*args: str) -> dict:
        result = subprocess.run(
            [sys.executable, "-m", "uasset_read", *map(str, args)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env=_env,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr[:500]}"
        return json.loads(result.stdout)

    # CLI default output is the v2 package document; the package assertion is
    # presence-only because package.name is legitimately "" on real fixtures
    # (follow-up #621).
    plain = run_cli_json(str(DATA_SAMPLE))
    assert plain["format"] == "uasset_read.package"
    assert "objects" in plain and plain["package"]
    assert len(plain["objects"]) > 0

    # --legacy-json opts back into v1 shape.
    legacy = run_cli_json("--legacy-json", str(DATA_SAMPLE))
    assert legacy["format"] != "uasset_read.package" or "objects" not in legacy

    # --markdown renders through the v1 pipeline (the only markdown renderer).
    md = subprocess.run(
        [sys.executable, "-m", "uasset_read", "--markdown", str(DATA_SAMPLE)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env=_env,
    )
    assert md.returncode == 0, md.stderr[:500]
    assert md.stdout.strip() and not md.stdout.lstrip().startswith("{")

    # v1-only flags under the v2 default warn instead of silently dropping.
    warned = subprocess.run(
        [sys.executable, "-m", "uasset_read", "--hex-view", str(DATA_SAMPLE)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env=_env,
    )
    assert warned.returncode == 0
    assert "--hex-view" in warned.stderr and "ignored" in warned.stderr
    assert json.loads(warned.stdout)["format"] == "uasset_read.package"

    # All public entry points project the same page.
    expected = project_document(_document(str(DATA_SAMPLE)), depth="package", limit=2, max_bytes=4096)
    cli = run_cli_json("--depth", "package", "--limit", "2", "--max-bytes", "4096", str(DATA_SAMPLE))
    assert cli["depth"] == "package"
    assert len(cli["objects"]) <= 2
    agent = inspect_package(str(DATA_SAMPLE), depth="package", limit=2, max_bytes=4096)
    for actual in (cli, agent):
        assert [item["id"] for item in actual["objects"]] == [item["id"] for item in expected["objects"]]
        assert actual["diagnostics"] == expected["diagnostics"]

    # Agent tool shapes.
    inspected = inspect_package(str(DATA_SAMPLE))
    assert "source" in inspected
    assert "package" in inspected
    assert "summary" in inspected
    parsed = json.loads(json.dumps(inspected))
    assert "source" in parsed and "package" in parsed and "summary" in parsed

    listed = list_objects(str(DATA_SAMPLE))
    assert listed["total"] > 0
    assert len(listed["objects"]) > 0

    paged = list_objects(str(PACKAGE_SAMPLE), limit=3, max_bytes=65536)
    assert len(paged["objects"]) == 3
    assert paged["next_offset"] == 3

    # G7 terminal predicate: every bounded tool's FINAL compact response
    # respects max_bytes; budgets below the empty-list envelope raise.
    for budget in (2048, 4096, 8192):
        r = list_objects(str(PACKAGE_SAMPLE), max_bytes=budget)
        assert len(json.dumps(r, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= budget
        d = get_diagnostics(str(PACKAGE_SAMPLE), max_bytes=budget)
        assert len(json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= budget
        insp = inspect_package(str(PACKAGE_SAMPLE), max_bytes=budget)
        assert len(json.dumps(insp, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= budget
    with pytest.raises(ValueError, match="too small"):
        # Healthy samples carry 0 diagnostics, so get_diagnostics' minimal
        # envelope is the fixed 52-byte empty-list form; 48 < 52 must raise.
        get_diagnostics(str(PACKAGE_SAMPLE), max_bytes=48)
    with pytest.raises(ValueError, match="too small"):
        extract_payload(str(DATA_SAMPLE), "payload:export:0", max_bytes=16)
    with pytest.raises(ValueError, match="too small"):
        inspect_package(str(PACKAGE_SAMPLE), max_bytes=64)

    fetched = get_object(str(DATA_SAMPLE), "export:0")
    assert fetched["id"] == "export:0"
    assert "name" in fetched

    # Agent Gate: a missing object is a structured diagnostic, not a bare string.
    missing = get_object(str(DATA_SAMPLE), "export:999999")
    assert missing["error"] == "Object 'export:999999' not found"
    assert missing["code"] == "OBJECT_NOT_FOUND"
    assert missing["stage"] == "agent.get_object"
    assert missing["recoverable"] is True
    assert missing["available_ids"] and all(i.startswith("export:") for i in missing["available_ids"])

    full_deps = _document(str(DATA_SAMPLE), depth="package").dependencies
    deps = list_dependencies(str(DATA_SAMPLE))
    assert deps["total_dependencies"] == len(full_deps)
    assert [d["index"] for d in deps["dependencies"]] == [d.index for d in full_deps][:50]
    abp = _document(str(PACKAGE_SAMPLE), depth="package").dependencies
    paged = list_dependencies(str(PACKAGE_SAMPLE), limit=25)
    assert paged["total_dependencies"] == len(abp)
    assert len(paged["dependencies"]) == 25 and paged["next_offset"] == 25
    with pytest.raises(ValueError, match="too small"):
        list_dependencies(str(DATA_SAMPLE), max_bytes=64)

    diags = get_diagnostics(str(DATA_SAMPLE))
    assert "diagnostics" in diags
    assert "total" in diags

    # extract_payload is deferred: stable code, no ids, no payload bytes.
    extracted = extract_payload(str(DATA_SAMPLE), "payload:export:0")
    assert extracted["code"] == "PAYLOAD_EXTRACTION_DEFERRED"
    assert extracted["available_ids"] == []
    assert not {"data", "data_b64", "truncated", "next_offset"} & extracted.keys()

    # Logging lifecycle: no process-global mutation, no stray files.
    handlers = tuple(logging.root.handlers)
    level = logging.root.level
    monkeypatch.chdir(tmp_path)
    _document(str(DATA_SAMPLE.resolve()))
    assert tuple(logging.root.handlers) == handlers
    assert logging.root.level == level
    assert list(tmp_path.iterdir()) == []

    from uasset_read.pipeline.core import parse_package

    pkg_handlers = tuple(logging.getLogger("uasset_read").handlers)
    parse_package(str(DATA_SAMPLE))
    assert tuple(logging.root.handlers) == handlers
    assert tuple(logging.getLogger("uasset_read").handlers) == pkg_handlers

    old_level = logging.root.level
    try:
        logging.root.setLevel(logging.WARNING)
        from uasset_read.v2.api import parse_package_document

        parse_package_document(str(DATA_SAMPLE))
    finally:
        logging.root.setLevel(old_level)
    assert len(logging.root.handlers) == len(handlers)
    assert logging.root.level == level

    # --- CLI budget regression: compact JSON respects max_bytes ---
    BUDGET_SAMPLE = str(SAMPLES / "FirstPerson_T_GridChecker_A.uasset")
    budget = 1500
    budget_result = subprocess.run(
        [sys.executable, "-m", "uasset_read", "--depth", "decode", "--max-bytes", str(budget), BUDGET_SAMPLE],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env=_env,
    )
    assert budget_result.returncode == 0, f"CLI budget failed: {budget_result.stderr[:500]}"
    stdout_bytes = budget_result.stdout.encode("utf-8")
    assert len(stdout_bytes.rstrip()) <= budget
    budget_doc = json.loads(budget_result.stdout)
    assert budget_doc["truncation"]["reason"] == "max_bytes"

    # --- Payload extraction is fully deferred (merged from test_samples) ---
    from uasset_read.v2.api import parse_package_document

    decode_doc = parse_package_document(
        str(SAMPLES / "FirstPerson_T_GridChecker_A.uasset"),
        depth="decode",
        object_ids=["export:2"],
    )
    sem_payload = (decode_doc.objects[2].semantic or {}).get("payload")
    if isinstance(sem_payload, dict):
        assert "ref" not in sem_payload and "stored_size" not in sem_payload

    pb_tool = extract_payload(str(SAMPLES / "FirstPerson_T_GridChecker_A.uasset"), "payload:export:2")
    assert pb_tool["code"] == "PAYLOAD_EXTRACTION_DEFERRED"
    assert pb_tool["available_ids"] == []
    assert not {"data", "data_b64", "sha256"} & pb_tool.keys()


def test_test_suite_structure_gate():
    import ast

    root = Path(__file__).parent
    test_files = sorted(p.name for p in root.glob("test_*.py"))
    assert test_files == ["test_core.py", "test_samples.py"]
    subdirs = {p.name for p in root.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert subdirs == {"samples"}
    tree = ast.parse((root / "test_core.py").read_text(encoding="utf-8"))
    funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    assert len(funcs) == 10
    assert not any(isinstance(n, ast.ClassDef) for n in tree.body)
    # The design bans decorators on test functions; cache helpers like
    # _document legitimately carry @lru_cache, so the check is scoped to
    # the collected test_* defs (the plan's gate body over-blocked here).
    assert all(not n.decorator_list for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))
    assigned = {
        t.id
        for n in tree.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id.startswith("test_")
    }
    assert not assigned
