"""Small permanent suite for stable cross-cutting contracts.

Top-level ``test_*`` functions only (policy structure gate: no test classes,
no parametrizing decorators, no dynamic ``test_*`` assignment in this file).
Fixture-sample contracts live in ``test_samples.py``. Case bodies folded from
the former ``tests/contract/`` layer are kept verbatim; the case name appears
in the failure message.

Like ``test_samples.py`` this file feeds duck-typed stub archives/summaries to internal
helpers, so the strict-object rules are off; ``src/uasset_read`` is the pyright gate (ci.yml).

The test-tree shape is locked by ``test_test_suite_structure_gate`` as a
policy (required files, per-file test functions, subdirs, strict test_core
shape), not by an exact filename list or function count.
"""

# pyright: reportArgumentType=false, reportAttributeAccessIssue=false
# pyright: reportOptionalSubscript=false, reportOptionalMemberAccess=false, reportOperatorIssue=false

from __future__ import annotations

from functools import lru_cache
import json
import logging
from contextlib import contextmanager
from pathlib import Path
import os
import subprocess
import sys

import pytest
from uasset_read.package import parse_package_document, open_package_bundle, _parse_cached
from uasset_read.models.object_model import ObjectRecord, ObjectStatus
from uasset_read.models.fallback import FallbackReason, PropertyFallback
from uasset_read.models.properties import PropertyValue, StructValue, PropertyTag, project_property_bag
from uasset_read.parsers.legacy_reader import (
    normalize_property_bag,
    resolve_import_dependencies,
    LegacyPackageReader,
    _read_table_rows,
    _merge_archive_recoveries,
    _read_string_table,
)
from uasset_read.exceptions import ParseError, VersionError
from uasset_read.parsers.asset_types.handlers_impl import (
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
    NiagaraHandler,
)
from uasset_read.parsers.asset_types.registry import _HANDLERS, register_handler, run_handlers
from uasset_read.projection import project_document
from uasset_read.agent_tools import (
    extract_payload,
    inspect_package,
)
from uasset_read.serializers.object_resources import ObjectImport, PackageIndex, read_export_map
from uasset_read.serializers.package_summary import (
    read_package_summary,
    read_name_table,
    read_depends_map,
    _read_tail_offsets,
    read_preload_dependencies,
    _read_compression_and_source,
    summary_gate_modes,
)
from uasset_read.parsers.property_types import (
    get_struct_size,
    parse_map_property,
    _LWC_TYPE_MAP,
    parse_struct_property,
    parse_array_property,
    parse_soft_object_property,
    parse_text_property,
)
from uasset_read.archive import ByteArchive, ExportBoundsExceeded
from uasset_read.constants import (
    MAX_FSTRING_LENGTH,
    PROP_EXT_HAS_EXTERNAL_OBJECTS,
    FIXED_UNVERSIONED_SIZES,
    format_guid_bytes,
)
from uasset_read.models.diagnostics import Diagnostic
from uasset_read.parsers.properties import tagged
from uasset_read.parsers.properties.tagged import _read_property_loop, _maybe_skip_import_data_json_prelude
from uasset_read.iostore import IoStoreTocError, read_toc
from uasset_read.serializers.property_tags import read_property_tag
from uasset_read.parsers.binary_or_native_handlers import (
    _decode_color,
    BINARY_OR_NATIVE_HANDLERS,
    _parse_expression_output,
)
from uasset_read.parsers.property_parser import _try_read_unversioned_header, _fixed_unversioned_size
from uasset_read.mappings import TypeMappings
from uasset_read.kismet.expressions import FScriptText, EX_Assert, EX_SetSet
from uasset_read.kismet.tokens import EBlueprintTextLiteralType as T
from uasset_read.serializers.graph_helpers import _read_fstring
from uasset_read.kismet.ufunction_reader import RELEASE_GUID
from uasset_read.serializers.graph_pin import read_ed_graph_pin_type, read_pin_array
from uasset_read.serializers.graph_node import _handle_advanced_pin_display, _handle_move_mode
from uasset_read import constants as K


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(__file__).parent / "samples"
PACKAGE_SAMPLE = SAMPLES / "ABP_RifleAnimLayers.uasset"
DATA_SAMPLE = SAMPLES / "ALS_FootstepDataTable.uasset"
SRC = ROOT / "src"


from typing import Literal


@lru_cache(maxsize=None)
def _document(sample: str = str(PACKAGE_SAMPLE), depth: Literal["package", "object", "asset", "decode"] = "package"):

    return parse_package_document(sample, depth=depth)


def _run_cases(cases) -> None:
    for check in cases:
        try:
            check()
        except (AssertionError, pytest.fail.Exception) as exc:
            raise AssertionError(f"{check.__name__}: {exc}") from exc


@contextmanager
def _isolated_handlers(*handlers):
    """Snapshot the v2 handler registry, optionally replacing it for the block.

    Handler tests mutate the module-global `_HANDLERS`. Keeping the snapshot and
    the restore in one place removes the chance of a block that saves without
    restoring; `_run_cases` propagates assertion failures through this context
    manager, so a leak would surface as a loud failure in the next case rather
    than as silent coupling. With no arguments the registry is only snapshotted,
    for cases that append or register handlers inside the block.
    """
    import uasset_read.parsers.asset_types.registry as H

    saved = list(H._HANDLERS)
    if handlers:
        H._HANDLERS[:] = list(handlers)
    try:
        yield
    finally:
        H._HANDLERS[:] = saved


def _object_record(class_name: str, *, id: str = "export:0"):

    return ObjectRecord(id=id, table_index=0, name="X", class_name=class_name, status=ObjectStatus())


def test_reader_boundaries_reject_malformed_access():
    """A bounded reader must never escape its declared source region."""

    def test_export_read_within_range_succeeds():
        """Reading within (50, 100) from pos 80 must return data and advance."""

        archive = ByteArchive(b"\x00" * 256)
        archive._read_range = (50, 100)
        archive._pos = 80
        data = archive.read(20)
        assert data == b"\x00" * 20
        assert archive._pos == 100

    def test_export_read_past_upper_bound_fails():

        archive = ByteArchive(b"\x00" * 256)
        archive._read_range = (50, 100)
        archive._pos = 80
        with pytest.raises(ExportBoundsExceeded):
            archive.read(50)

    def test_export_seek_past_lower_bound_fails():

        archive = ByteArchive(b"\x00" * 256)
        archive._read_range = (50, 100)
        with pytest.raises(ExportBoundsExceeded):
            archive.validate_offset(10, "test_seek")

    def test_export_seek_past_upper_bound_fails():

        archive = ByteArchive(b"\x00" * 256)
        archive._read_range = (50, 100)
        with pytest.raises(ExportBoundsExceeded):
            archive.validate_offset(150, "test_seek")

    def depends_map_stops_at_unsized_count():
        import struct
        from types import SimpleNamespace

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

        data = struct.pack("<iqii", 0, 0, 0, 10_000_000)
        with pytest.raises(ParseError, match="ChunkIDs"):
            _read_tail_offsets(ByteArchive(data), 522)  # array-mode ChunkIDs at UE4 >= 326

    def preload_count_beyond_file_rejected_immediately():
        import struct
        from types import SimpleNamespace

        # offset 4 is a positive, in-bounds table start in the 8-byte payload.
        data = struct.pack("<ii", 7, 9)
        summary = SimpleNamespace(preload_dependency_offset=4, preload_dependency_count=10_000_000)
        with pytest.raises(ParseError, match="PreloadDependencies"):
            read_preload_dependencies(ByteArchive(data), summary)

    def tolerant_fstring_overrun_records_recovery_not_just_a_log():
        import struct

        for header, enc in ((6, "UTF-8"), (-6, "UTF-16")):  # claims 6/12 bytes, 2 remain
            arc = ByteArchive(struct.pack("<i", header) + b"ab", tolerant=True)
            assert arc.read_fstring() == ""
            sd = [d for d in arc.get_structured_diagnostics() if d.code == "fstring_out_of_range"]
            assert sd and sd[0].offset == 0 and sd[0].fallback == "used_empty_string", enc
        with pytest.raises(ParseError):  # strict mode still fails hard
            ByteArchive(struct.pack("<i", 6) + b"ab").read_fstring()

    def fstring_internal_null_truncation_is_recorded():
        import struct

        arc = ByteArchive(struct.pack("<i", 4) + b"ab\x00c", tolerant=True)
        assert arc.read_fstring() == "ab"
        sd = [d for d in arc.get_structured_diagnostics() if d.code == "fstring_truncated_at_null"]
        assert sd and sd[0].offset == 0 and sd[0].fallback == "truncated_at_first_null"

    def fstring_length_cap_recorded_both_encodings():
        import struct

        for header in (MAX_FSTRING_LENGTH + 1, -(MAX_FSTRING_LENGTH + 1) // 2):  # UTF-8 / UTF-16 both over cap
            arc = ByteArchive(struct.pack("<i", header) + b"ab", tolerant=True)
            assert arc.read_fstring() == ""
            sd = [d for d in arc.get_structured_diagnostics() if d.code == "fstring_length_exceeds_limit"]
            assert sd and sd[0].offset == 0 and sd[0].fallback == "used_empty_string", header

    def fstring_all_null_recorded_both_encodings():
        import struct

        # UTF-8: 4 null bytes. UTF-16: 3 chars (6 bytes) — a padding-sized 4-byte
        # UTF-16 run at an aligned position is #369 alignment padding (debug-only,
        # no structured record), so pin the structured path with a non-alignment size.
        for payload in (struct.pack("<i", 4) + b"\x00" * 4, struct.pack("<i", -3) + b"\x00" * 6):
            arc = ByteArchive(payload, tolerant=True)
            assert arc.read_fstring() == ""
            codes = [d.code for d in arc.get_structured_diagnostics()]
            assert "fstring_all_null" in codes, payload

    def fstring_empty_ftext_namespace_is_silent():
        import struct

        # UE empty FText namespace/key: ANSI length=1 + single NUL (#405).
        # Valid in BPVariableDescription.Category — must not be recovered_corruption.
        arc = ByteArchive(struct.pack("<i", 1) + b"\x00", tolerant=True)
        assert arc.read_fstring() == ""
        assert arc.get_structured_diagnostics() == []

    def fstring_all_null_longer_run_still_recorded():
        import struct

        arc = ByteArchive(struct.pack("<i", 4) + b"\x00" * 4, tolerant=True)
        assert arc.read_fstring() == ""
        codes = [d.code for d in arc.get_structured_diagnostics()]
        assert "fstring_all_null" in codes

    def fname_shift_recovery_is_recorded():
        import struct

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

    def property_loop_aborts_on_fstring_out_of_range():
        """A misaligned FString length must stop the export property stream (P0 Lyra)."""
        from types import SimpleNamespace
        from unittest.mock import patch

        tag_calls = {"n": 0}

        class _StubArchive:
            def __init__(self):
                self._diags: list = []
                self._pos = 0

            def tell(self):
                return self._pos

            def seek(self, pos):
                self._pos = pos

            def total_size(self):
                return 1000

            def get_structured_diagnostics(self):
                return self._diags

            def read_i32(self):
                return 0

            def read(self, n):
                return b"\x00" * n

        def fake_read_property_tag(archive, name_map, **kwargs):
            tag_calls["n"] += 1
            if tag_calls["n"] == 1:
                archive._pos += 8
                return PropertyTag(name="Foo", type="StrProperty", size=4)
            archive._diags.append(
                Diagnostic(
                    code="fstring_out_of_range",
                    stage="read_fstring",
                    offset=99,
                    message="FString at pos 99: UTF-8 expected 7667713 bytes but only 8 remain",
                    object_id="export:9",
                )
            )
            # Second property is non-None so an unpatched loop keeps going.
            archive._pos += 8
            return PropertyTag(name="Bar", type="StrProperty", size=4)

        archive = _StubArchive()
        with (
            patch.object(tagged, "read_property_tag", side_effect=fake_read_property_tag),
            patch.object(tagged, "read_tag_value_bounded", return_value="ok"),
        ):
            props = _read_property_loop(
                export=SimpleNamespace(class_index=None, object_name="MovieScene_0", serial_offset=0, serial_size=1000),
                archive=archive,
                summary=SimpleNamespace(file_version_ue4=522, file_version_ue5=1018, package_flags=0),
                name_map=["None", "Foo", "Bar"],
                export_map=[],
                import_map=None,
                mappings=None,
                property_end=1000,
                tolerant=True,
            )
        assert isinstance(props, list)
        assert tag_calls["n"] == 2

    def import_data_json_prelude_is_skipped_before_tagged_stream():
        import struct

        json_body = b'[{"RelativeFilename" : "x.wav"}]'
        blob = struct.pack("<i", len(json_body)) + json_body + b"\x00" * 8
        arc = ByteArchive(blob)
        assert _maybe_skip_import_data_json_prelude(arc, class_name="AssetImportData", region_end=len(blob)) is True
        assert arc.tell() == 4 + len(json_body)

        arc2 = ByteArchive(blob)
        assert _maybe_skip_import_data_json_prelude(arc2, class_name="Material", region_end=len(blob)) is False
        assert arc2.tell() == 0

        arc3 = ByteArchive(struct.pack("<i", 0x01000000) + b"\xff" * 16)
        assert _maybe_skip_import_data_json_prelude(arc3, class_name="AssetImportData", region_end=20) is False

    def export_map_recoveries_are_attributed_to_their_slot():
        import struct
        from types import SimpleNamespace

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

    def test_fname_display_uses_external_number():
        import struct

        arc = ByteArchive(struct.pack("<ii", 0, 3))
        name = arc.read_name(["None", "Test"])
        assert name == "None_2"  # on-disk internal 3 -> display external 2 (LinkerLoad.h NAME_INTERNAL_TO_EXTERNAL)
        arc2 = ByteArchive(struct.pack("<ii", 0, 0))
        assert arc2.read_name(["None", "Test"]) == "None"

    def _synthetic_toc(**overrides):
        """Build a byte-exact v8 ``.utoc`` so the fail-closed paths are reachable.

        Field order and widths follow FIoStoreTocHeader (IoStore.h) and the array order of
        FIoStoreTocResourceView::Read (IoStore.cpp:1274-1420).
        """
        import struct
        import tempfile
        from pathlib import Path

        fields = {
            "version": 8,
            "entry_count": 1,
            "block_count": 1,
            "method_count": 1,
            "method_len": 32,
            "block_size": 65536,
            "dir_index": b"",
            "flags": 0,
            "perfect_seeds": 0,
            "no_perfect": 0,
            "header_size": 144,
            "meta_size": None,
        }
        fields.update(overrides)
        meta_size = fields["meta_size"] or (24 if fields["version"] >= 8 else 33)
        header = bytearray(b"-==--==--==--==-" + bytes(128))
        struct.pack_into(
            "<BBH" + "I" * 9,
            header,
            16,
            fields["version"],
            0,
            0,
            fields["header_size"],
            fields["entry_count"],
            fields["block_count"],
            12,
            fields["method_count"],
            fields["method_len"],
            fields["block_size"],
            len(fields["dir_index"]),
            1,
        )
        struct.pack_into("<B", header, 80, fields["flags"])
        struct.pack_into("<I", header, 84, fields["perfect_seeds"])
        struct.pack_into("<Q", header, 88, 1 << 26)
        struct.pack_into("<I", header, 96, fields["no_perfect"])
        body = bytearray()
        body += bytes(12 * fields["entry_count"])
        body += bytes(10 * fields["entry_count"])
        body += bytes(4 * fields["perfect_seeds"])
        body += bytes(4 * fields["no_perfect"])
        body += bytes(12 * fields["block_count"])
        names = b"Oodle\x00" + bytes(max(0, fields["method_len"] - 6))
        body += names[: fields["method_count"] * fields["method_len"]]
        body += fields["dir_index"]
        body += bytes(meta_size * fields["entry_count"])
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "probe.utoc"
        path.write_bytes(bytes(header) + bytes(body))
        return path, tmp

    def test_iostore_rejects_non_toc_input():

        path, tmp = _synthetic_toc()
        try:
            with pytest.raises(IoStoreTocError, match="smaller than a TOC header"):
                (path.with_name("short.utoc")).write_bytes(path.read_bytes()[:100])
                read_toc(path.with_name("short.utoc"))
            wrong = path.with_name("wrong_magic.utoc")
            wrong.write_bytes(b"X" * 16 + path.read_bytes()[16:])
            with pytest.raises(IoStoreTocError, match="not an IoStore TOC"):
                read_toc(wrong)
        finally:
            tmp.cleanup()

    def test_iostore_rejects_unsupported_shapes():

        checks = [
            ({"version": 9}, "unsupported TOC version"),
            ({"header_size": 143}, "header size"),
            ({"flags": 0x04}, "signed container"),
            ({"flags": 0x02}, "encrypted container"),
            ({"method_len": 0}, "implausible method/entry table"),
        ]
        for overrides, message in checks:
            path, tmp = _synthetic_toc(**overrides)
            try:
                with pytest.raises(IoStoreTocError, match=message):
                    read_toc(path)
            finally:
                tmp.cleanup()

        # Counts that claim more than the file holds must be caught, whether the body is
        # truncated or only the header lies about the entry count.
        import struct

        path, tmp = _synthetic_toc(entry_count=3, block_count=3)
        try:
            full = path.read_bytes()
            lying = bytearray(full)
            struct.pack_into("<I", lying, 24, 4000)  # TocEntryCount
            path.write_bytes(bytes(lying))
            with pytest.raises(IoStoreTocError, match="TOC layout needs"):
                read_toc(path)
            path.write_bytes(full[:-4])
            with pytest.raises(IoStoreTocError, match="TOC layout needs"):
                read_toc(path)
            path.write_bytes(full)
            assert read_toc(path).entry_count == 3
        finally:
            tmp.cleanup()

    def test_iostore_parses_supported_layouts():

        # v8 with 24-byte FIoHash metas, and v7 with 33-byte legacy metas.
        for version, entry_count in ((8, 3), (7, 2)):
            path, tmp = _synthetic_toc(version=version, entry_count=entry_count, block_count=entry_count)
            try:
                toc = read_toc(path)
            finally:
                tmp.cleanup()
            assert toc.version == version and toc.entry_count == entry_count
            assert len(toc.chunks) == entry_count and len(toc.blocks) == entry_count
            assert toc.compression_methods == ("None", "Oodle")  # index 0 is implicit NAME_None
            assert toc.data_path is None and toc.files == ()

    def test_iostore_rejects_directory_index_escape():

        import struct

        # MountPoint + a string-table count that runs past the buffer.
        bad = struct.pack("<i", 4) + b"mnt/" + struct.pack("<iii", 0, 0, 99999)
        path, tmp = _synthetic_toc(flags=0x08, dir_index=bad)
        try:
            with pytest.raises(IoStoreTocError):
                read_toc(path)
        finally:
            tmp.cleanup()

    _run_cases(
        [
            test_export_read_within_range_succeeds,
            test_export_read_past_upper_bound_fails,
            test_export_seek_past_lower_bound_fails,
            test_export_seek_past_upper_bound_fails,
            depends_map_stops_at_unsized_count,
            chunk_ids_count_beyond_file_rejected_immediately,
            preload_count_beyond_file_rejected_immediately,
            tolerant_fstring_overrun_records_recovery_not_just_a_log,
            fstring_internal_null_truncation_is_recorded,
            fstring_length_cap_recorded_both_encodings,
            fstring_all_null_recorded_both_encodings,
            fstring_empty_ftext_namespace_is_silent,
            fstring_all_null_longer_run_still_recorded,
            fname_shift_recovery_is_recorded,
            export_map_recoveries_are_attributed_to_their_slot,
            property_loop_aborts_on_fstring_out_of_range,
            import_data_json_prelude_is_skipped_before_tagged_stream,
            test_fname_display_uses_external_number,
            test_iostore_rejects_non_toc_input,
            test_iostore_rejects_unsupported_shapes,
            test_iostore_parses_supported_layouts,
            test_iostore_rejects_directory_index_escape,
        ]
    )


def test_property_bag_normalization_is_bounded_lossless():
    """normalize_property_bag must bound, describe, and never embed raw bytes."""

    def projected(properties):
        return {entry["name"]: entry["value"] for entry in project_property_bag(normalize_property_bag(properties))}

    def test_empty_list_returns_empty_array():

        assert normalize_property_bag([]).entries == []
        assert project_property_bag(normalize_property_bag([])) == []

    def test_unknown_property_is_descriptor_not_blob():

        prop = PropertyFallback(
            name="Mystery",
            type="UnknownProperty",
            size=4,
            reason=FallbackReason.UNSUPPORTED_TYPE,
        )
        bag = projected([prop])
        assert bag["Mystery"] == {
            "kind": "opaque",
            "type": "UnknownProperty",
            "size": 4,
            "reason": "unsupported_type",
        }
        assert "raw_bytes" not in bag["Mystery"]
        json.dumps(bag)

    def test_known_property_preserves_value():

        bag = projected([PropertyValue(name="Health", type="FloatProperty", value=100.0)])
        assert bag["Health"]["kind"] == "value"
        assert bag["Health"]["value"] == 100.0
        json.dumps(bag)

    def test_struct_property_normalizes():

        sv = StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})
        prop = PropertyValue(name="Location", type="StructProperty", value=sv)
        bag = projected([prop])
        assert bag["Location"]["kind"] == "struct"
        assert bag["Location"]["struct_type"] == "Vector"
        assert bag["Location"]["fields"]["X"] == 1.0
        json.dumps(bag)

    def test_bytes_value_serializes():

        bag = projected([PropertyValue(name="Data", type="BlobProperty", value=b"\x00\x01")])
        assert bag["Data"]["kind"] == "value"
        assert bag["Data"]["value"] == {
            "kind": "opaque",
            "type": "bytes",
            "size": 2,
            "reason": "raw_bytes",
        }
        json.dumps(bag)

    def test_lwc_box_size_52_and_double_read():
        import struct

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

    def test_array_of_bools_consumes_one_byte_per_element():
        import struct

        data = struct.pack("<i", 3) + bytes([1, 0, 1]) + b"X"
        arc = ByteArchive(data)
        tag = PropertyTag(name="A", type="ArrayProperty", size=len(data))
        tag.inner_type = "BoolProperty"
        out = parse_array_property(tag, arc, ["None"], [], None)
        assert out == [True, False, True]
        assert arc.tell() == 4 + 3

    def test_legacy_struct_array_reads_single_inner_tag():
        import struct

        # The inner struct is one of the tagged-fallback structs so a size-0 inner
        # tag parses as a tagged-field stream instead of returning opaque (a plain
        # fast-path name like "Vector" cannot exercise the tagged element loop).
        names = ["None", "StructProperty", "IntProperty", "BlendSample", "HP"]

        def legacy_tag(name_i, type_i, size, extra=b""):
            # name + type FNames, size + array_index int32s, [extras], HasPropertyGuid=0
            return (
                struct.pack("<ii", name_i, 0)
                + struct.pack("<ii", type_i, 0)
                + struct.pack("<ii", size, 0)
                + extra
                + b"\x00"
            )

        inner = legacy_tag(4, 1, 0, struct.pack("<ii", 3, 0) + bytes(16))  # StructProperty/BlendSample + StructGuid
        field = legacy_tag(4, 2, 4) + struct.pack("<i", 111) + struct.pack("<ii", 0, 0)  # HP=111 then None tag
        field2 = legacy_tag(4, 2, 4) + struct.pack("<i", 222) + struct.pack("<ii", 0, 0)
        data = struct.pack("<i", 2) + inner + field + field2
        arc = ByteArchive(data)
        arc._file_version_ue5 = 500  # legacy routing (<1012); no extension byte in tags
        arc._file_version_ue4 = 522
        tag = PropertyTag(name="A", type="ArrayProperty", size=len(data))
        tag.inner_type = "StructProperty"
        tag.inner_type_struct = None
        out = parse_array_property(tag, arc, names, [], None, 0)
        assert len(out) == 2
        assert out[0].fields["HP"] == 111 and out[1].fields["HP"] == 222
        assert arc.tell() == len(data)

    def test_soft_object_path_inline_is_fname_based():
        import struct
        from types import SimpleNamespace

        names = ["None", "Game/Foo/Bar", "Bar", "SubPath"]
        # UE5 < 1007 legacy inline: FName(index+number) + FString (SerializePathWithoutFixup)
        body = struct.pack("<ii", 2, 0) + struct.pack("<i", len("SubPath") + 1) + b"SubPath\x00"
        arc = ByteArchive(body)
        summary = SimpleNamespace(file_version_ue5=500, package_flags=0, custom_versions=[])
        val = parse_soft_object_property(
            PropertyTag(name="S", type="SoftObjectProperty", size=len(body)), arc, names, summary
        )
        assert val.asset_path == "Bar" and val.sub_path == "SubPath"
        # UE5 >= 1007: FTopLevelAssetPath = PackageName FName + AssetName FName, then subpath FString
        body2 = struct.pack("<iiii", 1, 0, 2, 0) + struct.pack("<i", 1) + b"\x00"
        arc2 = ByteArchive(body2)
        summary2 = SimpleNamespace(file_version_ue5=1007, package_flags=0, custom_versions=[])
        val2 = parse_soft_object_property(
            PropertyTag(name="S", type="SoftObjectProperty", size=len(body2)), arc2, names, summary2
        )
        assert val2.asset_path == "Game/Foo/Bar.Bar"

    def test_ftext_history_demoted_and_base_reads_dev_notes():
        import struct

        def ft_body(hist, strings=(), extra=b""):
            tail = extra
            for s in strings:
                tail += struct.pack("<i", len(s) + 1) + s.encode("utf-8") + b"\x00"
            return struct.pack("<iB", 0, hist) + tail

        # Base + DevNotes (gate on): 4 strings; value is the third.
        body = ft_body(
            0,
            ("ns", "key", "Hello", "notes"),
        )
        arc = ByteArchive(body)
        v = parse_text_property(PropertyTag(name="T", type="TextProperty", size=len(body)), arc, dev_notes=True)
        assert v.source_string == "Hello" and arc.tell() == len(body)
        # NamedFormat (1): nested FText (flags+hist+its own 4 strings) + args — demoted, not misparsed
        nested = struct.pack("<iB", 0, 0) + struct.pack("<i", 1) + b"\x00"
        body1 = struct.pack("<iB", 0, 1) + nested + struct.pack("<i", 0)
        arc1 = ByteArchive(body1)
        v1 = parse_text_property(PropertyTag(name="T", type="TextProperty", size=len(body1)), arc1, dev_notes=False)
        assert v1.source_string == "" and getattr(v1, "history_type", None) == 1

    def test_fcolor_bgra_decode():

        out = _decode_color(bytes([10, 20, 30, 40]), 4)
        assert out == {"R": 30, "G": 20, "B": 10, "A": 40}

    def test_unversioned_header_fragments_ue_format():
        import struct

        # One fragment: SkipNum=0, HasZeroes=1, IsLast=1, ValueNum=3 ->
        # packed = (3<<9) | 0x100 | 0x80 = 0x0780
        # then global zero mask (3 bits -> single u8: bits 0,2 set -> 0b101)
        data = struct.pack("<HBB", 0x0780, 0b101, 0)  # trailing byte pads property_end
        arc = ByteArchive(data)
        selected = _try_read_unversioned_header(arc, property_end=4, property_count=3)
        assert selected == [(0, True), (1, False), (2, True)]

    def test_scalar_material_input_full_layout():
        import struct
        from types import SimpleNamespace

        # Expression(4) + OutputIndex(4) + InputName(8) + Mask(4) + RGBA(16) + UseConstant(1) + Constant(f32=4) = 41
        # Pad to 44 to align. Expression=101, InputName=index 7 ("X"), UseConstant=1, Constant=0.5f
        # Expression(4)+OutputIndex(4)+InputName(8)+Mask(4)+RGBA(16)+UseConstant(1)+Constant(4) = 41
        payload = struct.pack(
            "<i i ii i i i i i B f",
            101,
            0,
            7,
            0,
            -1,
            -1,
            -1,
            -1,
            -1,
            1,
            0.5,
        )
        assert len(payload) == 41
        tag = SimpleNamespace(name="M", type="FScalarMaterialInput", size=41)
        out = BINARY_OR_NATIVE_HANDLERS["FScalarMaterialInput"](
            tag, ByteArchive(payload), ["None"] * 8 + ["X"], [], None
        )
        assert out is not None
        assert out["expression_index"] == 101
        assert out["use_constant"] is True
        assert out["constant"] == 0.5

    def test_function_expression_output_maps_to_output_decoder():
        import struct
        from types import SimpleNamespace

        assert BINARY_OR_NATIVE_HANDLERS["FunctionExpressionOutput"] is _parse_expression_output
        assert BINARY_OR_NATIVE_HANDLERS["FFunctionExpressionOutput"] is _parse_expression_output

        # OutputName FName(8) + Mask + MaskR/G/B/A (5 * i32 = 20) = 28 bytes.
        payload = struct.pack("<i i i i i i i", 8, 0, -1, 3, -1, -1, -1)
        tag = SimpleNamespace(name="Out", type="FFunctionExpressionOutput", size=28)
        out = BINARY_OR_NATIVE_HANDLERS["FunctionExpressionOutput"](
            tag, ByteArchive(payload), ["None"] * 8 + ["X"], [], None
        )
        assert out is not None
        assert out["struct_type"] == "FExpressionOutput"
        assert out["fields"]["output_name"] == "X"
        assert out["fields"]["mask_r"] == 3
        assert "expression_ref" not in out and "output_index" not in out

    _run_cases(
        [
            test_empty_list_returns_empty_array,
            test_unknown_property_is_descriptor_not_blob,
            test_known_property_preserves_value,
            test_struct_property_normalizes,
            test_bytes_value_serializes,
            test_lwc_box_size_52_and_double_read,
            test_property_tag_extension_external_objects,
            test_array_of_bools_consumes_one_byte_per_element,
            test_legacy_struct_array_reads_single_inner_tag,
            test_soft_object_path_inline_is_fname_based,
            test_ftext_history_demoted_and_base_reads_dev_notes,
            test_fcolor_bgra_decode,
            test_unversioned_header_fragments_ue_format,
            test_scalar_material_input_full_layout,
            test_function_expression_output_maps_to_output_decoder,
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

        doc1 = parse_package_document(str(PACKAGE_SAMPLE))
        doc2 = parse_package_document(str(PACKAGE_SAMPLE))
        ids1 = [o.id for o in doc1.objects]
        ids2 = [o.id for o in doc2.objects]
        assert ids1 == ids2

    def test_unversioned_bool_one_byte_enum_fname():
        from types import SimpleNamespace

        assert FIXED_UNVERSIONED_SIZES["BoolProperty"] == 1
        # Enum with byte inner must report FName width 8, not the inner's 1
        assert _fixed_unversioned_size(SimpleNamespace(type="EnumProperty", inner_type="ByteProperty")) == 8
        assert _fixed_unversioned_size(SimpleNamespace(type="EnumProperty", inner_type=None)) == 8

    def test_compressed_chunks_skipped_as_16_bytes():
        import struct

        data = struct.pack("<ii", 0, 1) + struct.pack("<iiii", 40, 8, 48, 8) + struct.pack("<i", 0x11223344)
        arc = ByteArchive(data)
        flags, source, _ = _read_compression_and_source(arc)
        assert source == 0x11223344  # wrong 12-byte skip desyncs PackageSource

    def test_table_rows_skip_tagged_stream_not_size_prefix():
        import struct

        # A None-terminator tagged property tag is exactly its 8-byte name FName
        # (read_property_tag early-returns at UE_NONE_SENTINEL). Two empty rows:
        # count | rowName FName | None tag | rowName FName | None tag
        data = (
            struct.pack("<i", 2)
            + struct.pack("<ii", 1, 0)
            + struct.pack("<ii", 0, 0)
            + struct.pack("<ii", 2, 0)
            + struct.pack("<ii", 0, 0)
        )
        arc = ByteArchive(data)
        diags: list = []
        result = _read_table_rows(
            arc, serial_end=len(data), name_map=["None", "A", "B"], object_id="export:1", diagnostics=diags
        )
        assert result["row_names"] == ["A", "B"] and result["complete"] is True
        assert not any(d.code == "TABLE_ROWS_TRUNCATED" for d in diags)

    def test_curve_table_mode_byte_is_consumed():
        """UCurveTable inserts ECurveTableMode between the count and the rows.

        Without it the first row name lands one byte early and every row name after
        it is garbage -- the #626 real-failure this path now matches
        (CurveTable.cpp:112-123, save branch at :202-235).
        """
        import struct

        data = (
            struct.pack("<iB", 1, 1) + struct.pack("<ii", 1, 0) + struct.pack("<ii", 0, 0)  # None tag
        )
        diags: list = []
        result = _read_table_rows(
            ByteArchive(data),
            serial_end=len(data),
            name_map=["None", "RowA"],
            object_id="export:1",
            diagnostics=diags,
            curve_table=True,
        )
        assert result["curve_table_mode"] == "SimpleCurves"
        assert result["row_names"] == ["RowA"] and result["complete"] is True

    def test_table_payload_residue_is_disclosed_not_complete():
        """Undecoded bytes after the last row must downgrade coverage, never claim rows."""
        import struct

        data = struct.pack("<i", 1) + struct.pack("<ii", 1, 0) + struct.pack("<ii", 0, 0) + b"\x7f\x7f"
        diags: list = []
        result = _read_table_rows(
            ByteArchive(data),
            serial_end=len(data),
            name_map=["None", "RowA"],
            object_id="export:1",
            diagnostics=diags,
        )
        assert result["complete"] is False
        assert any(d.code == "TABLE_PAYLOAD_RESIDUE" for d in diags)

    def test_fname_instance_number_renders_in_row_name():
        """Row names are FNames: Number 2 displays as ``Base_1`` (NAME_INTERNAL_TO_EXTERNAL)."""
        import struct

        data = (
            struct.pack("<i", 2)
            + struct.pack("<ii", 1, 1)
            + struct.pack("<ii", 0, 0)
            + struct.pack("<ii", 1, 2)
            + struct.pack("<ii", 0, 0)
        )
        result = _read_table_rows(
            ByteArchive(data),
            serial_end=len(data),
            name_map=["None", "Curve"],
            object_id="export:1",
            diagnostics=[],
        )
        assert result["row_names"] == ["Curve_0", "Curve_1"]
        assert result["complete"] is True

    def test_summary_gate_modes_are_versioned():

        assert summary_gate_modes(214) == {
            "engine_versions": "legacy",
            "compatible": False,
            "world_tile": False,
            "chunk_ids": "none",
        }
        assert summary_gate_modes(278) == {
            "engine_versions": "legacy",
            "compatible": False,
            "world_tile": True,
            "chunk_ids": "single",
        }
        assert summary_gate_modes(326) == {
            "engine_versions": "legacy",
            "compatible": False,
            "world_tile": True,
            "chunk_ids": "array",
        }
        assert summary_gate_modes(443) == {
            "engine_versions": "full",
            "compatible": True,
            "world_tile": True,
            "chunk_ids": "array",
        }

    _run_cases(
        [
            test_all_exports_present,
            test_ids_are_export_prefix,
            test_stable_id_across_calls,
            test_unversioned_bool_one_byte_enum_fname,
            test_compressed_chunks_skipped_as_16_bytes,
            test_summary_gate_modes_are_versioned,
            test_table_rows_skip_tagged_stream_not_size_prefix,
            test_curve_table_mode_byte_is_consumed,
            test_table_payload_residue_is_disclosed_not_complete,
            test_fname_instance_number_renders_in_row_name,
        ]
    )

    zero_role = _document(str(SAMPLES / "uasset_rs_UE410_SimpleRefsSoftRef.uasset"))
    assert len(zero_role.objects) == 6
    assert zero_role.summary.asset_object_ids == ()


def test_export_failure_isolated_and_diagnostics_typed(monkeypatch):
    """A malformed export must produce an attributable diagnostic without deleting siblings."""
    import uasset_read.parsers.properties.tagged as tagged

    real = tagged.parse_properties_from_export
    calls = {"n": 0}

    def boom(**kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise ParseError("injected malformed export payload")
        return real(**kwargs)

    # All fixture exports now parse cleanly, so inject the failure to
    # exercise the isolation path deterministically.
    monkeypatch.setattr(tagged, "parse_properties_from_export", boom)

    class Ok:
        capability = "decoded"

        def supports(self, obj, ctx):
            return True

        def enrich(self, obj, ctx, all_objs, data):
            return {"kind": "ok"}

    mappings_calls: dict = {}

    def mappings_spy(**kw):
        mappings_calls["mappings"] = kw.get("mappings")
        return {}

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
        import uasset_read.parsers.asset_types.registry as H

        class Boom:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                raise RuntimeError("boom")

        obj = _object_record("Foo", id="export:9")
        with _isolated_handlers(Boom(), Ok()):
            _result = H.run_handlers(obj, "package", [], None)
            semantic = _result.semantic
            diags = _result.diagnostics
        assert semantic == {"kind": "ok"}
        assert obj.status.semantic == "partial"
        assert any(d.code == "HANDLER_FAILURE" for d in diags)

    def test_clean_success_still_marks_complete():
        import uasset_read.parsers.asset_types.registry as H

        obj = _object_record("Foo", id="export:9")
        with _isolated_handlers(Ok()):
            H.run_handlers(obj, "package", [], None)
        assert obj.status.semantic == "complete"

    def test_matched_handler_returning_none_is_not_complete():
        import uasset_read.parsers.asset_types.registry as H

        class Decliner:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                return None

        obj = _object_record("Foo", id="export:9")
        with _isolated_handlers(Decliner()):
            _result = H.run_handlers(obj, "package", [], None)
            semantic = _result.semantic
        assert semantic is None
        assert obj.status.semantic == "partial"

    def test_parse_past_serial_end_is_flagged_not_silent():
        import uasset_read.parsers.properties.tagged as tagged

        _parse_cached.cache_clear()
        try:

            def fake_overrun(**kwargs):
                export = kwargs["export"]
                kwargs["archive"].seek(export.serial_offset + export.serial_size + 8)
                return []

            monkeypatch.setattr(tagged, "parse_properties_from_export", fake_overrun)
            overrun_doc = parse_package_document(str(PACKAGE_SAMPLE), depth="object")
        finally:
            _parse_cached.cache_clear()
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

        _parse_cached.cache_clear()
        try:
            monkeypatch.setattr(orm, "ObjectExport", boom)
            doc = parse_package_document(str(PACKAGE_SAMPLE))  # depth=asset default; cleared G2 cache so boom runs
        finally:
            _parse_cached.cache_clear()
        assert doc.objects[0].name == first_name  # slot 0 kept its identity
        assert all(o.name != second_name for o in doc.objects)  # second export did NOT become export:0
        assert any(d.code == "EXPORT_TABLE_TRUNCATED" for d in doc.diagnostics)

    def test_v2_mappings_never_passes_raw_path_string():
        mappings_calls.clear()
        monkeypatch.setattr(tagged, "parse_properties_from_export", mappings_spy)
        doc = parse_package_document(str(DATA_SAMPLE), depth="object", mappings_path=str(ROOT / "no-such.usmap"))
        assert any(d.code == "MAPPINGS_LOAD_FAILED" for d in doc.diagnostics)
        assert not isinstance(mappings_calls.get("mappings"), str)  # never a raw path string

    def test_v2_mappings_object_on_successful_load():
        import tempfile

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

        mappings_calls.clear()
        monkeypatch.setattr(tagged, "parse_properties_from_export", mappings_spy)
        with tempfile.TemporaryDirectory() as td:
            ok_path = Path(td) / "ok.usmap"
            ok_path.write_bytes(blob)
            doc = parse_package_document(str(DATA_SAMPLE), depth="object", mappings_path=str(ok_path))
        assert not any(d.code == "MAPPINGS_LOAD_FAILED" for d in doc.diagnostics)
        assert isinstance(mappings_calls.get("mappings"), TypeMappings)

    def test_silent_recovery_downgrades_object_and_reaches_document():

        class _RecoveringArchive:
            """Plain bounded fake — no MagicMock for UE structures."""

            def get_structured_diagnostics(self):
                return [
                    Diagnostic(
                        code="fstring_out_of_range",
                        stage="read_fstring",
                        offset=7,
                        fallback="used_empty_string",
                        message="FString overran the file",
                        object_id="export:0",
                    ),
                    Diagnostic(
                        code="EXPORT_TABLE_TRUNCATED",
                        stage="read_export_map",
                        offset=9,
                        fallback="stop_table",
                        message="stopped export table read with 1/2 entries",
                    ),
                ]

        obj = _object_record("Foo")
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
            test_no_critical_on_healthy,
            test_diagnostics_have_stage,
            test_failed_export_does_not_remove_later_objects,
            test_partial_status_on_bad_export_preserves_document,
            test_parse_failure_diagnostic_has_object_id,
            test_later_success_does_not_mask_earlier_failure,
            test_clean_success_still_marks_complete,
            test_matched_handler_returning_none_is_not_complete,
            test_parse_past_serial_end_is_flagged_not_silent,
            test_export_table_failure_preserves_slot_identity,
            test_v2_mappings_never_passes_raw_path_string,
            test_silent_recovery_downgrades_object_and_reaches_document,
            test_v2_mappings_object_on_successful_load,
        ]
    )


def test_handler_registry_supports_enriches_and_isolates():
    """Every registered handler must accept its class, reject others, and isolate failures."""

    record = _object_record

    def test_handlers_registered():
        assert len(_HANDLERS) >= 4

    def test_expected_handlers():
        names = [type(h).__name__ for h in list(_HANDLERS)]
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
            (
                "MaterialParameterCollectionHandler",
                MaterialParameterCollectionHandler(),
                "MaterialParameterCollection",
                "Blueprint",
            ),
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
            assert handler.supports(record(good_class), "package"), f"{name} must support {good_class}"
            assert not handler.supports(record(bad_class), "package"), f"{name} must reject {bad_class}"

    def test_texture_no_properties_returns_none():
        obj = ObjectRecord(
            id="export:0",
            table_index=0,
            name="Tex",
            class_name="Texture2D",
            status=ObjectStatus(),
            properties=None,
        )
        assert TextureHandler().enrich(obj, "package", [], None) is None

    def test_handler_exception_doesnt_crash():

        class BadHandler:
            def supports(self, obj, context):
                return True

            def enrich(self, obj, context, all_objects, package_data):
                raise RuntimeError("boom")

        with _isolated_handlers():
            register_handler(BadHandler())
            obj = ObjectRecord(id="export:0", table_index=0, name="X", class_name="Anything", status=ObjectStatus())
            _result = run_handlers(obj, "package", [obj], None)
            semantic = _result.semantic
            cov = _result.coverage
            diags = _result.diagnostics
            assert semantic is None
            assert any("BadHandler" in c.feature for c in cov)
            assert any(d.stage == "semantic.handler" for d in diags)

    def test_handler_exception_becomes_object_diagnostic():
        import uasset_read.parsers.asset_types.registry as handlers_registry

        class RaisingHandler:
            def supports(self, obj, context):
                return True

            def enrich(self, obj, context, all_objects, package_data):
                raise ValueError("broken handler")

        with _isolated_handlers():
            handlers_registry._HANDLERS.append(RaisingHandler())
            sample_doc = parse_package_document(str(DATA_SAMPLE), depth="object", object_ids=["export:0"])
            _result = handlers_registry.run_handlers(sample_doc.objects[0], "package", sample_doc.objects, None)
            semantic = _result.semantic
            coverage = _result.coverage
            diagnostics = _result.diagnostics
            assert semantic is None
            assert any(c.status == "missing" for c in coverage)
            handler_diags = [d for d in diagnostics if d.stage == "semantic.handler"]
            assert len(handler_diags) >= 1
            assert handler_diags[0].object_id == sample_doc.objects[0].id

    def test_niagara_handler_supports_all_declared_classes():

        handler = NiagaraHandler()
        assert len(handler.classes) == 13
        for class_name in handler.classes:
            assert handler.supports(record(class_name), "package"), class_name
        assert not handler.supports(record("StaticMesh"), "package")

    def test_summary_tier_handlers_never_claim_complete():
        """Niagara/Mesh/Blueprint-summary results are partial with coverage (#629)."""

        cases = [
            ("NiagaraScript", NiagaraHandler()),
            ("StaticMesh", MeshHandler()),
            (
                "Blueprint",
                BlueprintFamilyHandler(("Blueprint", "BlueprintGeneratedClass"), "blueprint", "blueprint"),
            ),
        ]
        with _isolated_handlers():
            for class_name, handler in cases:
                _HANDLERS[:] = [handler]
                obj = record(class_name)
                _result = run_handlers(obj, "asset", [obj], None)
                semantic = _result.semantic
                assert semantic, class_name
                assert obj.status.semantic == "partial", class_name
                assert obj.coverage, class_name

    def test_decode_tier_blueprint_graph_marks_complete():
        """Only decoded-tier output (Blueprint graph at depth=decode) yields complete (#629)."""

        bp = record("Blueprint")
        node = record("K2Node_CallFunction")
        node.id = "export:1"
        handler = BlueprintFamilyHandler(("Blueprint", "BlueprintGeneratedClass"), "blueprint", "blueprint")
        # Phase 4.5: graphs arrive via extras dict in package_data
        dummy_graph = {
            "id": "export:0",
            "name": "EventGraph",
            "kind": "event_graph",
            "node_count": 0,
            "pin_link_count": 0,
            "nodes": [],
            "truncated": {"nodes": False, "pins": False},
            "subgraphs_flattened": 0,
        }
        extras = {bp.id: {"graphs": [dummy_graph]}}
        with _isolated_handlers(handler):
            _result = run_handlers(bp, "decode", [bp, node], (None, [], extras))
            semantic = _result.semantic
        assert "graphs" in semantic
        assert bp.status.semantic == "complete"

    def test_undeclared_handler_tier_defaults_to_summary():

        class Echo:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                return {"kind": "echo"}

        obj = record("Whatever")
        with _isolated_handlers(Echo()):
            run_handlers(obj, "package", [obj], None)
        assert obj.status.semantic == "partial"

    def test_skeleton_name_guess_is_marked_heuristic():
        """NameMap-regex bones are marked bone_source=name_guess and never complete (#630)."""

        obj = record("Skeleton")
        name_map = ["None", "SomeWidget", "root", "pelvis", "spine_01"]
        with _isolated_handlers(SkeletonHandler()):
            _result = run_handlers(obj, "asset", [obj], (None, name_map, None))
            semantic = _result.semantic
        assert semantic["bone_source"] == "name_guess"
        assert [b["name"] for b in semantic["bones"]] == ["root", "pelvis", "spine_01"]
        assert semantic["bone_count"] == 3
        assert obj.status.semantic == "partial"
        guess = [c for c in obj.coverage if c.feature == "skeleton.bones"]
        assert len(guess) == 1
        assert guess[0].status == "partial" and "heuristic" in guess[0].detail

    def test_skeleton_bone_tree_wins_over_name_guess():
        """Decoded BoneTree names take precedence over the regex path (#630)."""

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
        with _isolated_handlers(SkeletonHandler()):
            _result = run_handlers(obj, "asset", [obj], (None, name_map, None))
            semantic = _result.semantic
        assert semantic["bone_source"] == "bone_tree"
        assert [b["name"] for b in semantic["bones"]] == ["root", "pelvis"]
        assert obj.status.semantic == "complete"

    def test_string_table_reader_synthetic_bytes():
        """#615: the FStringTable trailer parses namespace + key/value entries."""
        import struct

        def fstring(s: str) -> bytes:
            data = s.encode("utf-8") + b"\x00"
            return struct.pack("<i", len(data)) + data

        def cstring(s: str) -> bytes:
            return s.encode("utf-8") + b"\x00"

        def read_table(blob: bytes, dev_notes: bool):
            diags = []
            archive = ByteArchive(blob)
            archive._read_range = (0, len(blob))
            result = _read_string_table(archive, "export:0", diags, dev_notes)
            return result, diags

        # UE layout: namespace (FString) + count + key (FString) + value (FString).
        blob = (
            fstring("MyNS") + struct.pack("<i", 2) + fstring("K1") + fstring("Hello") + fstring("K2") + fstring("World")
        )
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
        blob = fstring("NS") + struct.pack("<i", 5) + cstring("K") + fstring("V")
        result, diags = read_table(blob, dev_notes=False)
        assert not result["complete"]
        assert [d.code for d in diags] == ["STRING_TABLE_TRUNCATED"]

    def test_string_table_handler_is_summary_and_not_table():
        """#615: StringTable uses StringTableHandler and never claims complete."""

        assert not DataTableHandler().supports(record("StringTable"), "package")
        assert DataTableHandler().supports(record("DataTable"), "package")
        assert StringTableHandler().supports(record("StringTable"), "package")

        obj = record("StringTable")
        obj.id = "export:5"
        st = {
            "namespace": "MyNS",
            "entry_count": 1,
            "entries": [{"key": "K", "value": "V"}],
            "complete": True,
        }
        with _isolated_handlers(DataTableHandler(), StringTableHandler()):
            _result = run_handlers(obj, "asset", [obj], (None, [], {obj.id: {"string_table": st}}))
            semantic = _result.semantic
        assert semantic["kind"] == "string_table"
        assert semantic["namespace"] == "MyNS"
        assert semantic["entry_count"] == 1
        assert semantic["entries"] == [{"key": "K", "value": "V"}]
        assert obj.status.semantic == "partial", "StringTable must not claim semantic=complete (#615)"

    def test_string_table_handler_missing_trailer_reports_coverage():

        obj = record("StringTable")
        result = StringTableHandler().enrich(obj, "package", [], (None, [], {}))
        assert result["kind"] == "string_table"
        cov = [c for c in obj.coverage if c.feature == "handler.StringTableHandler"]
        assert len(cov) == 1 and cov[0].status == "missing"

    def test_physics_handlers_summary_tier_synthetic():
        """#619: physics handlers read real fields but never claim complete."""

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
        with _isolated_handlers(PhysicsAssetHandler(), PhysicalMaterialHandler()):
            _result = run_handlers(pa, "asset", [pa, body], None)
            sem_pa = _result.semantic
            _result = run_handlers(pm, "asset", [pm], None)
            sem_pm = _result.semantic
            empty_pm = record("PhysicalMaterial")
            empty_pm.properties = {}
            _result = run_handlers(empty_pm, "asset", [empty_pm], None)
            sem_empty = _result.semantic

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

        bs = record("BlendSpace")
        bs.properties = {
            "BlendParameters": {
                "kind": "value",
                "type": "ArrayProperty",
                "value": [
                    {
                        "kind": "struct",
                        "struct_type": "BlendParameter",
                        "fields": {"DisplayName": "Speed", "Min": 0.0, "Max": 200.0, "GridNum": 7},
                    },
                    {
                        "kind": "struct",
                        "struct_type": "BlendParameter",
                        "fields": {"DisplayName": "Direction", "Min": -90.0, "Max": 90.0, "GridNum": 5},
                    },
                    {
                        "kind": "struct",
                        "struct_type": "BlendParameter",
                        "fields": {"DisplayName": "None", "Min": 0.0, "Max": 0.0, "GridNum": 2},
                    },
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
                            "SampleValue": {
                                "kind": "struct",
                                "struct_type": "Vector",
                                "fields": {"X": 100.0, "Y": 45.0, "Z": 0.0},
                            },
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
                            "fields": {
                                "AnimReference": "AnimSequence'A_Run'",
                                "StartPos": 0.0,
                                "AnimStartTime": 0.0,
                                "AnimEndTime": 1.5,
                            },
                        }
                    ]
                },
            }
        }
        ali = record("AnimLayerInterface")
        ali.properties = {}
        bare = record("BlendSpace1D")
        bare.properties = {}

        with _isolated_handlers(AnimBlendSpaceHandler(), AnimCompositeHandler(), AnimLayerInterfaceHandler()):
            _result = run_handlers(bs, "asset", [bs], None)
            sem_bs = _result.semantic
            _result = run_handlers(comp, "asset", [comp], None)
            sem_comp = _result.semantic
            _result = run_handlers(ali, "asset", [ali], None)
            sem_ali = _result.semantic
            _result = run_handlers(bare, "asset", [bare], None)
            sem_bare = _result.semantic

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
                            "DefaultValue": {
                                "kind": "struct",
                                "struct_type": "LinearColor",
                                "fields": {"R": 1.0, "G": 0.0, "B": 0.5, "A": 1.0},
                            },
                        },
                    }
                ],
            },
        }
        bare_fn = record("MaterialFunction")
        bare_fn.properties = {}

        with _isolated_handlers(MaterialFunctionHandler(), MaterialParameterCollectionHandler()):
            _result = run_handlers(fn, "asset", [fn, inp, out, call, add], None)
            sem_fn = _result.semantic
            _result = run_handlers(mpc, "asset", [mpc], None)
            sem_mpc = _result.semantic
            _result = run_handlers(bare_fn, "asset", [bare_fn], None)
            sem_bfn = _result.semantic

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

    def test_native_fields_delegate_type_name():
        """K5: FField class name is MulticastInlineDelegateProperty (UnrealType.h)."""
        src = (SRC / "uasset_read/kismet/native_fields.py").read_text(encoding="utf-8")
        assert "InlineMulticastDelegateProperty" not in src
        assert src.count("MulticastInlineDelegateProperty") >= 3

    def test_ex_text_const_operand_layouts():
        """K1/K2: UE5 literal-type numbering; operands are nested string expressions."""
        import struct

        assert T.LocalizedTextWithNotes == 2 and T.InvariantText == 3
        assert T.LiteralString == 4 and T.StringTableEntry == 5

        class _KismetLike:  # duck-typed operand reader over bounded bytes
            def __init__(self, data):
                self._arc = ByteArchive(data)

            def read_u8(self):
                return self._arc.read_u8()

            def read_i32(self):
                return self._arc.read_i32()

            def xfer_ansi_string(self):
                out = bytearray()
                while (b := self._arc.read(1)) != b"\x00":
                    out += b
                return out.decode("utf-8")

            def xfer_unicode_string(self):
                out = bytearray()
                while (pair := self._arc.read(2)) != b"\x00\x00":
                    out += pair
                return out.decode("utf-16-le")

        def ansi(s):
            return bytes([0x1F]) + s.encode("utf-8") + b"\x00"

        data = bytes([1]) + ansi("Hello") + ansi("5A1B") + ansi("NS")  # source,key,namespace
        text = FScriptText.from_archive(_KismetLike(data))
        assert text.SourceString == "Hello" and text.KeyString == "5A1B" and text.Namespace == "NS"
        uni = bytes([1]) + bytes([0x34]) + "Héy".encode("utf-16-le") + b"\x00\x00" + ansi("K") + ansi("N")
        assert FScriptText.from_archive(_KismetLike(uni)).SourceString == "Héy"
        ste = bytes([5]) + struct.pack("<i", -3) + ansi("MyTable") + ansi("Key42")
        t3 = FScriptText.from_archive(_KismetLike(ste))
        assert t3.TableIdString == "MyTable" and t3.KeyString == "Key42"

    def test_ex_assert_u8_and_container_counts():
        """K3/K4: EX_Assert flag is uint8; set/map/array consts carry int32 counts."""
        import struct

        class _WidthProbe:  # forwards the width-sensitive reads, stubs expression dispatch
            def __init__(self, data):
                self._arc = ByteArchive(data)

            def read_u8(self):
                return self._arc.read_u8()

            def read_u16(self):
                return self._arc.read_u16()

            def read_i32(self):
                return self._arc.read_i32()

            def read_bool(self):
                return self._arc.read_u32() != 0

            def read_expression(self):
                return None

            def read_expression_array(self, _end_token):
                return []

            def tell(self):
                return self._arc.tell()

        probe = _WidthProbe(struct.pack("<HB", 42, 1))  # line + uint8 debug flag
        node = EX_Assert.from_archive(probe)
        assert node.LineNumber == 42 and node.DebugMode is True
        assert probe.tell() == 3  # old 4-byte read_bool would land at 6
        probe2 = _WidthProbe(struct.pack("<i", 7))  # the int32 element count
        node2 = EX_SetSet.from_archive(probe2)
        assert node2.Num == 7 and probe2.tell() == 4

    def test_fstring_negative_one_consumes_two_bytes():
        """G3: negative FString length always reads abs(len)*2 UTF-16 bytes (String.cpp.inl)."""
        import struct

        arc = ByteArchive(struct.pack("<i", -1) + b"\x00\x00" + struct.pack("<i", 3) + b"abc\x00")
        assert _read_fstring(arc, tolerant=False) == ""
        assert arc.tell() == 6  # consumed the 2-byte UTF-16 NUL, not skipped it
        assert _read_fstring(arc, tolerant=False) == "abc"

    def test_map_pin_terminal_reads_trailing_bools():
        """G1: FEdGraphTerminalType reads const/weak/gated-wrapper bools (EdGraphNode.cpp)."""
        import struct

        from types import SimpleNamespace

        fname = struct.pack("<ii", 0, 0)  # "None"
        data = (
            fname
            + fname
            + struct.pack("<i", 0)
            + struct.pack("<B", 3)  # cat, sub, obj, container=Map
            + fname
            + fname
            + struct.pack("<i", 0)  # terminal cat, sub, object ref
            + struct.pack("<iii", 1, 0, 1)  # terminal const, weak, uobject-wrapper (gated)
            + struct.pack("<i", 0) * 2
            + fname
            + struct.pack("<i", 0)
            + bytes(16)  # bIsReference/bIsWeak + member ref
            + struct.pack("<i", 0) * 3  # trailing is_const / wrapper / single-precision bools
        )
        arc = ByteArchive(data)
        summary = SimpleNamespace(
            package_flags=0,
            file_version_ue4=522,
            file_version_ue5=1018,
            custom_versions=[SimpleNamespace(guid=RELEASE_GUID, version=31)],
        )
        pt = read_ed_graph_pin_type(arc, ["None"], summary, [], [])
        assert pt.container_type == 3
        assert pt.map_key_terminal_is_const is True
        assert pt.map_key_terminal_is_weak_pointer is False
        assert pt.map_key_terminal_is_uobject_wrapper is True
        assert pt.is_reference is False  # reads the 4-byte value AFTER the tail: desync guard

    def test_pin_array_bad_count_fails_closed():
        """T6: corrupt pin-array count raises ParseError (no sliding-window salvage)."""
        import struct

        # count=999 exceeds MAX_LINKEDTO_PER_PIN; the trailing bytes mimic a
        # "recoverable" pin ref that the deleted sliding-window salvage sought.
        data = struct.pack("<i", 999) + struct.pack("<i", 1) + bytes(20) + bytes(32)
        arc = ByteArchive(data)
        with pytest.raises(ParseError, match="exceeds MAX_LINKEDTO_PER_PIN"):
            read_pin_array(arc, [], [])

        # Negative count also fails closed.
        arc2 = ByteArchive(struct.pack("<i", -1))
        with pytest.raises(ParseError, match="negative"):
            read_pin_array(arc2, [], [])

    def test_byte_enum_node_tag_decodes_fname():
        """G5: UENUM-backed byte tags carry the enum-entry FName (PropertyByte.cpp SerializeItem)."""
        import struct

        from types import SimpleNamespace

        names = ["None", "Hidden", "Copy"]
        payload = struct.pack("<ii", 1, 0)  # FName pointing at name "Hidden", number 0
        arc = ByteArchive(payload)
        tag = SimpleNamespace(name="AdvancedPinDisplay", size=8, value_end_offset=8)
        raw: dict = {}
        _handle_advanced_pin_display(arc, tag, names, [], [], raw)
        assert raw["AdvancedPinDisplayFormatted"] == "Hidden"
        arc2 = ByteArchive(struct.pack("<ii", 2, 0))
        raw2: dict = {}
        tag2 = SimpleNamespace(name="MoveMode", size=8, value_end_offset=8)
        _handle_move_mode(arc2, tag2, names, [], [], raw2)
        assert raw2["MoveMode"] == "Copy"

    def test_no_invented_k2node_tails():
        """G4: K2Node Serialize() implementations add no binary tails past Pins."""
        src = (SRC / "uasset_read/serializers/graph_node.py").read_text(encoding="utf-8")
        head = src.split("# 5 Node type readers")[1].split("dispatch handlers")[0]
        assert "read_bool(" not in head
        assert "legacy fallback (bool at pos" not in head
        assert "read_k2node_message(" not in (SRC / "uasset_read/serializers/graph_node.py").read_text(encoding="utf-8")

    def test_guid_display_is_36_chars():
        """O1: FGuid display uses format_guid_bytes (8-4-4-4-12 = 36 chars)."""
        import struct

        a, b, c, d = 0x01020304, 0x05060708, 0x090A0B0C, 0x0D0E0F10
        s = format_guid_bytes(struct.pack("<IIII", a, b, c, d))
        assert len(s) == 36 and s.count("-") == 4

    _run_cases(
        [
            test_handlers_registered,
            test_expected_handlers,
            test_supports_and_rejects,
            test_texture_no_properties_returns_none,
            test_handler_exception_doesnt_crash,
            test_handler_exception_becomes_object_diagnostic,
            test_niagara_handler_supports_all_declared_classes,
            test_summary_tier_handlers_never_claim_complete,
            test_decode_tier_blueprint_graph_marks_complete,
            test_undeclared_handler_tier_defaults_to_summary,
            test_skeleton_name_guess_is_marked_heuristic,
            test_skeleton_bone_tree_wins_over_name_guess,
            test_string_table_reader_synthetic_bytes,
            test_string_table_handler_is_summary_and_not_table,
            test_string_table_handler_missing_trailer_reports_coverage,
            test_physics_handlers_summary_tier_synthetic,
            test_anim_handlers_summary_tier_synthetic,
            test_material_family_handlers_summary_tier_synthetic,
            test_native_fields_delegate_type_name,
            test_ex_text_const_operand_layouts,
            test_ex_assert_u8_and_container_counts,
            test_fstring_negative_one_consumes_two_bytes,
            test_map_pin_terminal_reads_trailing_bools,
            test_pin_array_bad_count_fails_closed,
            test_byte_enum_node_tag_decodes_fname,
            test_no_invented_k2node_tails,
            test_guid_display_is_36_chars,
        ]
    )


def test_projection_envelope_is_the_v4_document():
    """v4 envelope: one full decode document, normal/debug modes only."""

    doc = _document(depth="decode")

    def test_normal_is_default():
        result = project_document(doc)
        assert result["mode"] == "normal"
        assert "debug" not in result

    def test_debug_adds_the_evidence_block():
        result = project_document(doc, mode="debug")
        assert result["mode"] == "debug"
        assert set(result["debug"]) == {
            "object_regions",
            "property_evidence",
            "semantic_source_ranges",
            "payload_sources",
            "sidecar_sources",
            "diagnostic_details",
            "byte_accounting",
        }

    def test_invalid_mode_raises():
        # Historical note: retired v2/v3 output-mode names stay in the rejection
        # list so a reintroduced mode never validates again.
        for mode in ("agent", "raw", "semantic", "view"):
            with pytest.raises(ValueError, match="mode"):
                project_document(doc, mode=mode)

    def test_objects_carry_ordered_properties():
        result = project_document(doc)
        for obj in result["objects"]:
            assert "flags" not in obj
            assert "serial_region" not in obj
            assert "properties_summary" not in obj
            assert isinstance(obj["properties"], list)
            for prop in obj["properties"]:
                assert set(prop) == {"name", "type", "occurrence", "array_index", "value"}

    def dependencies_carry_package_name():
        # #632: the model carries package_name from the import map; no
        # projection path may drop it.
        page = project_document(doc)
        assert page["dependencies"], "fixture must expose imports"
        model = {d.index: d for d in doc.dependencies}
        for entry in page["dependencies"]:
            assert set(entry) == {"index", "class", "object_name", "package_name"}
            assert entry["package_name"] == model[entry["index"]].package_name

    def test_all_objects_present():
        result = project_document(doc)
        assert {o["id"] for o in result["objects"]} == {o.id for o in doc.objects}

    def shallow_depth_document_raises():
        pkg_doc = _document(str(PACKAGE_SAMPLE), depth="package")
        with pytest.raises(ValueError, match="depth"):
            project_document(pkg_doc)

    def relations_carry_optional_target_path():
        pkg_doc = _document(str(PACKAGE_SAMPLE), depth="decode")
        page = project_document(pkg_doc)
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
        base = {(r.kind, r.from_id, r.to_id) for r in pkg_doc.relations}
        for rel in rels:
            assert (rel["kind"], rel["from"], rel["to"]) in base
            assert set(rel) <= {"kind", "from", "to", "target_path"}

    def test_envelope_is_json_safe():
        result = project_document(doc)
        assert json.loads(json.dumps(result, ensure_ascii=False))

    _run_cases(
        [
            test_normal_is_default,
            test_debug_adds_the_evidence_block,
            test_invalid_mode_raises,
            test_objects_carry_ordered_properties,
            dependencies_carry_package_name,
            test_all_objects_present,
            shallow_depth_document_raises,
            relations_carry_optional_target_path,
            test_envelope_is_json_safe,
        ]
    )


def test_projection_rejects_partial_documents():
    partial = parse_package_document(str(PACKAGE_SAMPLE), depth="decode", object_ids=["export:0"])
    with pytest.raises(ValueError, match="all exports"):
        project_document(partial)


def test_schema_contract_statics():
    """Static contract gates.

    The v3 schema/example checks are retired with the deleted v3 contract
    files; the v4 contract gate lives in tests/test_contract_v4.py. What
    remains here is the UE4 version-numbering pin.
    """

    def ue4_version_constants_are_pinned_to_peer_numbering():
        """UE4 file versions carry 4.x-era ordinals; newer UE5 headers renumbered -1
        (Epic's 'version clash'). Values below match CUE4Parse/UAssetAPI/uasset-rs
        mirrors; changing them without a real boundary-version fixture is forbidden."""

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
            ue4_version_constants_are_pinned_to_peer_numbering,
        ]
    )


def test_cli_python_agent_share_default_projection_and_logging_inert(tmp_path, monkeypatch):
    """CLI (default normal), Python API, and agent tools must agree; parsing must be side-effect free."""

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

    # CLI default output is the v4 package document in normal mode.
    plain = run_cli_json(str(DATA_SAMPLE))
    assert plain["format"] == "uasset_read.package"
    assert plain["format_version"] == "4.0"
    assert plain["mode"] == "normal"
    assert "objects" in plain and plain["package"]
    assert len(plain["objects"]) > 0

    # All public entry points project the same document per mode.
    for mode, extra in (("normal", ()), ("debug", ("--debug",))):
        expected = project_document(_document(str(DATA_SAMPLE), depth="decode"), mode=mode)
        cli = run_cli_json(*extra, str(DATA_SAMPLE))
        agent = inspect_package(str(DATA_SAMPLE), mode=mode)
        assert cli == expected
        assert agent == expected

    # Agent tool shapes.
    inspected = inspect_package(str(DATA_SAMPLE))
    assert "source" in inspected
    assert "package" in inspected
    assert "summary" in inspected
    parsed = json.loads(json.dumps(inspected))
    assert "source" in parsed and "package" in parsed and "summary" in parsed

    # extract_payload stays a separate explicit binary operation with budgets.
    result = extract_payload(str(DATA_SAMPLE), "payload:(export:0)", max_bytes=16)
    assert isinstance(result, dict)
    assert result.get("code") == "BUDGET_EXHAUSTED"
    assert result.get("recoverable") is True

    # extract_payload for package with sidecar returns real data or DEFERRED.
    extracted = extract_payload(str(DATA_SAMPLE), "payload:(export:0)")
    # Packages with sidecars will extract real data.
    assert "data" in extracted or extracted.get("code") == "PAYLOAD_EXTRACTION_DEFERRED"
    if "data" in extracted:
        # Real extraction succeeded — verify structure
        import base64

        data = base64.b64decode(extracted["data"])
        assert len(data) > 0
        assert extracted["size"] == len(data)
    elif extracted.get("code") == "PAYLOAD_EXTRACTION_DEFERRED":
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

    pkg_handlers = tuple(logging.getLogger("uasset_read").handlers)
    parse_package_document(str(DATA_SAMPLE))
    assert tuple(logging.root.handlers) == handlers
    assert tuple(logging.getLogger("uasset_read").handlers) == pkg_handlers

    old_level = logging.root.level
    try:
        logging.root.setLevel(logging.WARNING)

        parse_package_document(str(DATA_SAMPLE))
    finally:
        logging.root.setLevel(old_level)
    assert len(logging.root.handlers) == len(handlers)
    assert logging.root.level == level

    # --- Unavailable payload is fully deferred (merged from test_samples) ---
    # A recognized canonical id whose export index is out of range must return
    # the deferred envelope (no data keys).
    decode_doc = parse_package_document(
        str(SAMPLES / "FirstPerson_T_GridChecker_A.uasset"),
        depth="decode",
        object_ids=["export:2"],
    )
    sem_payload = (decode_doc.objects[2].semantic or {}).get("payload")
    if isinstance(sem_payload, dict):
        assert "ref" not in sem_payload and "stored_size" not in sem_payload

    pb_tool = extract_payload(str(SAMPLES / "FirstPerson_T_GridChecker_A.uasset"), "payload:export:9999")
    assert pb_tool["code"] == "PAYLOAD_EXTRACTION_DEFERRED"
    assert pb_tool["available_ids"] == []
    assert not {"data", "data_b64", "sha256"} & pb_tool.keys()


def test_agent_tools_missing_file_return_structured_errors(tmp_path):

    missing = str(tmp_path / "missing.uasset")
    calls = [
        lambda: inspect_package(missing),
        lambda: extract_payload(missing, "payload:export:0"),
    ]
    for call in calls:
        result = call()
        assert result["code"] == "PACKAGE_NOT_FOUND"
        assert result["stage"].startswith("agent.")
        assert result["recoverable"] is False


def test_agent_tools_parse_error_return_structured_errors(monkeypatch, tmp_path):
    import uasset_read.agent_tools as tools

    def fail_parse(*args, **kwargs):
        raise ParseError("injected parse failure")

    monkeypatch.setattr(tools, "parse_package_document", fail_parse)
    path = str(tmp_path / "parse-fails.uasset")
    calls = [
        lambda: tools.inspect_package(path),
    ]
    for call in calls:
        result = call()
        assert result["code"] == "PACKAGE_PARSE_FAILED"
        assert result["recoverable"] is True

    def fail_version(*args, **kwargs):
        raise VersionError("injected unsupported package version")

    monkeypatch.setattr(tools, "parse_package_document", fail_version)
    for call in calls:
        result = call()
        assert result["code"] == "PACKAGE_PARSE_FAILED"
        assert result["recoverable"] is True
        # _err maps the message= kwarg to the stable "error" field.
        assert "VersionError" in result["error"]


def test_import_dependency_package_is_the_outer_owner_not_the_class_package():
    """#645: Dependency.package_name is the package an import belongs to.

    FObjectImport.ClassPackage names the package holding the object's *class*.
    The owning package is PackageName when set, otherwise it is found by
    walking the outer chain (ObjectResource.h:457-460; the terminal entry of a
    null outer is the UPackage, so its ObjectName is the package path,
    LinkerLoad.cpp:2402).
    """

    CUE = "Footstep_Cue"
    OWNER = "/ALSV4_CPP/AdvancedLocomotionV4/Audio/Footsteps/Footstep_Cue"
    MAT = "/ALSV4_CPP/AdvancedLocomotionV4/CharacterAssets/MannequinSkeleton/Materials/M_DecalFootprint"

    doc = _document(str(DATA_SAMPLE), depth="decode")
    cue = next(d for d in doc.dependencies if d.object_name == CUE and d.class_name == "SoundCue")
    assert cue.package_name == OWNER, "ClassPackage (/Script/Engine) must not stand in for the owner"
    mat = next(d for d in doc.dependencies if d.object_name == "M_DecalFootprint" and d.class_name == "Material")
    assert mat.package_name == MAT and mat.class_name == "Material"

    # Same fact at every public boundary.
    agent = next(d for d in project_document(doc)["dependencies"] if d["object_name"] == CUE)
    assert agent["package_name"] == OWNER
    rel = next(r for r in project_document(doc)["relations"] if r["to"] == f"import:{cue.index}")
    assert rel["target_path"] == f"{OWNER}.{CUE}"

    def row(cls, outer, name, pkg=None):
        return ObjectImport(
            class_package="/Script/Engine",
            class_name=cls,
            outer_index=PackageIndex(outer),
            object_name=name,
            package_name=pkg,
        )

    cases = {
        "explicit PackageName wins": ([row("SoundCue", 0, CUE, "/Real/Path")], ["/Real/Path"]),
        "ancestor PackageName wins": (
            [row("SoundCue", -2, "A"), row("Package", 0, "B", "/Explicit")],
            ["/Explicit", "/Explicit"],
        ),
        "null-outer Package row is its own package": ([row("Package", 0, OWNER)], [OWNER]),
        "cycle": ([row("SoundCue", -2, "A"), row("Package", -1, "B")], ["", ""]),
        "outer out of range": ([row("SoundCue", -9, "A")], [""]),
        "outer is an export": ([row("SoundCue", 3, "A")], [""]),
        "null outer is not a Package": ([row("SoundCue", 0, "A")], [""]),
    }
    for label, (rows, owners) in cases.items():
        deps, diags = resolve_import_dependencies(rows)
        assert [d.package_name for d in deps] == owners, label
        assert [d.object_name for d in deps] == [r.object_name for r in rows], label
        unresolved = {d.object_id for d in diags}
        assert unresolved == {f"import:{i}" for i, o in enumerate(owners) if not o}, label


def test_uexp_address_space_guard_and_bundle_routing(tmp_path, monkeypatch):
    """UE source guard: .uexp concatenated only when main_size == TotalHeaderSize.

    Proves the splice works by:
    - refusal path: asserts arc._uexp_archive is None and total_size()==main_size
    - acceptance path: asserts arc._uexp_archive is not None and cross-boundary read
    - total_header_size==0 refusal: proves the fail-open fix (1a)
    """
    import shutil
    import uasset_read.parsers.legacy_reader as lr

    # --- setup: copy a real sample + create a dummy .uexp with a marker ---
    sample = tmp_path / "Test.uasset"
    shutil.copy2(PACKAGE_SAMPLE, sample)
    # .uexp with a recognizable tail: last 2 bytes are "AB"
    eexp_data = b"\x00" * 254 + b"AB"
    (tmp_path / "Test.uexp").write_bytes(eexp_data)

    main_size = sample.stat().st_size
    # record the last 2 bytes of the main file for cross-boundary assertion
    main_tail = (tmp_path / "Test.uasset").read_bytes()[-2:]
    # first 2 bytes of .uexp (zeros, since data starts with 254 zero bytes)
    uexp_head = eexp_data[:2]

    real_read_summary = read_package_summary

    # === Refusal path: main_size != TotalHeaderSize ===
    def patched_wrong(archive, *, total_decompressed=0):
        s, total = real_read_summary(archive, total_decompressed=total_decompressed)
        s.total_header_size = main_size - 1
        return s, total

    monkeypatch.setattr(lr, "read_package_summary", patched_wrong)
    bundle = open_package_bundle(str(sample))
    arc = bundle.open_archive(tolerant=True)
    doc = LegacyPackageReader(tolerant=True).read(archive=arc, main_path=str(sample))

    guard_diags = [d for d in doc.diagnostics if d.code == "UEXP_SPLIT_GUARD_FAILED"]
    assert len(guard_diags) == 1
    assert len(doc.objects) > 0
    # Prove the address space actually contracted
    assert arc._uexp_archive is None, ".uexp must be disconnected on refusal"
    assert arc.total_size() == main_size, "total_size must equal main only"

    # === Refusal path: total_header_size == 0 (fail-open fix, 1a) ===
    def patched_zero(archive, *, total_decompressed=0):
        s, total = real_read_summary(archive, total_decompressed=total_decompressed)
        s.total_header_size = 0
        return s, total

    monkeypatch.setattr(lr, "read_package_summary", patched_zero)
    bundle0 = open_package_bundle(str(sample))
    arc0 = bundle0.open_archive(tolerant=True)
    doc0 = LegacyPackageReader(tolerant=True).read(archive=arc0, main_path=str(sample))

    guard0 = [d for d in doc0.diagnostics if d.code == "UEXP_SPLIT_GUARD_FAILED"]
    assert len(guard0) == 1, "total_header_size==0 must refuse, not skip"
    assert arc0._uexp_archive is None, ".uexp must be disconnected when THS==0"
    assert arc0.total_size() == main_size

    # === Acceptance path: main_size == TotalHeaderSize ===
    def patched_ok(archive, *, total_decompressed=0):
        s, total = real_read_summary(archive, total_decompressed=total_decompressed)
        s.total_header_size = main_size
        return s, total

    monkeypatch.setattr(lr, "read_package_summary", patched_ok)
    bundle_ok = open_package_bundle(str(sample))
    arc_ok = bundle_ok.open_archive(tolerant=True)
    doc_ok = LegacyPackageReader(tolerant=True).read(archive=arc_ok, main_path=str(sample))

    guard_ok = [d for d in doc_ok.diagnostics if d.code == "UEXP_SPLIT_GUARD_FAILED"]
    assert not guard_ok, "guard must not fire when main_size == TotalHeaderSize"
    assert len(doc_ok.objects) > 0
    # Prove .uexp is connected
    assert arc_ok._uexp_archive is not None, ".uexp must be connected on acceptance"
    assert arc_ok.total_size() == main_size + len(eexp_data), "total_size must span both files"
    # Cross-boundary read: last 2 of main + first 2 of .uexp
    arc_ok.seek(main_size - 2)
    cross = arc_ok.read(4)
    assert cross == main_tail + uexp_head, f"cross-boundary splice failed: {cross!r}"


def test_get_struct_size_matches_lwc_tables_for_shadowed_names():
    """Names present in the LWC tables are served by the LWC branch, never by the
    _EXPECTED_STRUCT_SIZES fallback. Pins the values the subtraction wave relies on."""

    expected = {
        "Vector": (12, 24),
        "Rotator": (12, 24),
        "Vector2D": (8, 16),
        "Quat": (16, 32),
        "Vector3f": (12, 12),
        "Rotator3f": (12, 12),
    }
    for name, (float_size, double_size) in expected.items():
        assert get_struct_size(name, 0) == float_size, name
        assert get_struct_size(name, 1005) == double_size, name


def test_package_document_cache_is_process_local():
    """G2: same path-stat-depth-key returns one PackageDocument object.

    Cache lives at the parse layer (``package.parse_package_document``).
    Keys include resolved path, mtime_ns, size, per-sidecar (exists, mtime_ns,
    size) for .uexp/.ubulk/.uptnl, mappings-file (mtime_ns, size), depth,
    sorted object_ids, tolerant, mappings_path, and game. Callers must treat
    hits as read-only.
    """
    import os
    import shutil
    import tempfile

    _parse_cached.cache_clear()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "cache_sample.uasset"
            shutil.copy2(PACKAGE_SAMPLE, sample)

            doc_a = parse_package_document(str(sample), depth="package")
            doc_b = parse_package_document(str(sample), depth="package")
            assert doc_a is doc_b

            # Different depth is a different key (no containment hits).
            doc_object = parse_package_document(str(sample), depth="object")
            assert doc_object is not doc_a

            # object_ids list order is normalized; None vs [] are distinct.
            doc_ids_ab = parse_package_document(str(sample), depth="package", object_ids=["export:1", "export:0"])
            doc_ids_ba = parse_package_document(str(sample), depth="package", object_ids=["export:0", "export:1"])
            assert doc_ids_ab is doc_ids_ba
            doc_ids_empty = parse_package_document(str(sample), depth="package", object_ids=[])
            assert doc_ids_empty is not doc_a
            assert doc_ids_empty is not doc_ids_ab

            # Touch mtime_ns → miss; old key object is not reused.
            st0 = sample.stat()
            os.utime(sample, ns=(st0.st_atime_ns, st0.st_mtime_ns + 1_000_000_000))
            doc_touched = parse_package_document(str(sample), depth="package")
            assert doc_touched is not doc_a

            # Sidecar content change must miss even when main stat is unchanged.
            uexp = sample.with_suffix(".uexp")
            uexp.write_bytes(b"sidecar-v1")
            doc_s1 = parse_package_document(str(sample), depth="package")
            uexp.write_bytes(b"sidecar-v2-longer")
            doc_s2 = parse_package_document(str(sample), depth="package")
            assert doc_s1 is not doc_s2

            # Mappings file stat participates in the key.
            usmap = Path(tmp) / "cache_sample.usmap"
            usmap.write_bytes(b"\x00" * 32)
            doc_m1 = parse_package_document(str(sample), depth="package", mappings_path=str(usmap))
            usmap.write_bytes(b"\x00" * 64)
            doc_m2 = parse_package_document(str(sample), depth="package", mappings_path=str(usmap))
            assert doc_m1 is not doc_m2
    finally:
        _parse_cached.cache_clear()


def test_export_map_parse_error_is_truncated_not_fatal(monkeypatch):
    import uasset_read.serializers.object_resources as orm

    real = orm.ObjectExport
    calls = {"n": 0}

    def boom(**kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise ParseError("injected export ParseError")
        return real(**kwargs)

    _parse_cached.cache_clear()
    try:
        monkeypatch.setattr(orm, "ObjectExport", boom)
        doc = parse_package_document(str(PACKAGE_SAMPLE), depth="package")
    finally:
        _parse_cached.cache_clear()
    assert any(d.code == "EXPORT_TABLE_TRUNCATED" for d in doc.diagnostics)
    assert len(doc.objects) >= 2


def test_read_name_table_returns_partial_on_parse_error():
    from types import SimpleNamespace

    summary = SimpleNamespace(
        name_count=4,
        name_offset=1,
        file_version_ue5=0,
        file_version_ue4=400,  # < UE4_NAME_HASHES_SERIALIZED (504 in this repo)
    )

    class Stub:
        def __init__(self):
            self.n = 0

        def seek(self, pos):
            return None

        def read_fstring(self):
            self.n += 1
            if self.n == 3:
                raise ParseError("truncated")
            return f"N{self.n}"

    names = read_name_table(Stub(), summary)
    assert names == ["N1", "N2"]


def test_test_suite_structure_gate():
    """Policy gate for the test tree (v3 contract freeze, Task 1).

    Replaces the brittle exact-filename list and ``len(funcs) == N`` lock:
    every root ``test_*.py`` must exist and collect at least one ``test_*``
    function, the three baseline files are required, permanent subdirs stay
    ``{samples, serialization}``, and ``test_core.py`` itself keeps the strict
    class-free / decorator-free / assignment-free top-level shape. Sample
    files may parametrize; their parameterized items are not capped.
    """
    import ast

    root = Path(__file__).parent
    paths = sorted(root.glob("test_*.py"))
    assert paths
    assert {"test_core.py", "test_samples.py", "test_size_baseline.py"} <= {p.name for p in paths}
    subdirs = {p.name for p in root.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert subdirs == {"samples", "serialization"}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        collected = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        ]
        assert collected, f"{path.name} contains no test functions"
    # test_core keeps the strict AST shape so its top-level AST count equals
    # pytest collection: no classes, no decorators on top-level test_* defs
    # (sample files may use @pytest.mark.parametrize), no dynamic test_*
    # assignment.
    core = ast.parse((root / "test_core.py").read_text(encoding="utf-8"))
    assert not any(isinstance(n, ast.ClassDef) for n in core.body)
    assert all(not n.decorator_list for n in core.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))
    assigned = {
        t.id
        for n in core.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id.startswith("test_")
    }
    assert not assigned


def test_fstring_leading_null_with_content_is_not_all_null():
    """A leading NUL plus later non-zero bytes is NOT all-null (Lyra 35269)."""
    import struct

    # The exact misread payload from Lyra MovieScene offset 35273: 16 bytes,
    # first four zero, then 0x1d (BoolProperty name index), rest zero.
    # Mirror Lyra pos 35269: the data starts at 35273 (35273 % 4 == 1), so the
    # alignment-padding heuristic does not mask the false classification (a
    # pos-0 read of this payload is suppressed as padding and the test would
    # pass vacuously).
    payload = b"\xff" + struct.pack("<i", 16) + bytes.fromhex("000000001d0000000000000000000000")
    arc = ByteArchive(payload, tolerant=True)
    arc.seek(1)
    assert arc.read_fstring() == ""
    codes = [d.code for d in arc.get_structured_diagnostics()]
    assert "fstring_all_null" not in codes, codes


def test_fstring_all_zero_payload_still_records_all_null():
    """Entirely-zero payload keeps the existing fstring_all_null classification."""
    import struct

    payload = struct.pack("<i", 8) + b"\x00" * 8
    arc = ByteArchive(payload, tolerant=True)
    assert arc.read_fstring() == ""
    codes = [d.code for d in arc.get_structured_diagnostics()]
    assert "fstring_all_null" in codes, codes


def test_map_value_unknown_struct_parses_tagged_until_none():
    """MapProperty struct values with no name in the tag parse as tagged fields.

    Legacy tags carry only key/value type FNames (PropertyTag.cpp:357-371), so
    value_type_struct is None; the dummy size=0 struct tag must still consume
    the None-terminated field stream (Lyra MovieScene ExpansionStates).
    """
    import struct

    def fname(idx: int, number: int = 0) -> bytes:
        return struct.pack("<II", idx, number)

    # name_map: 0=bExpanded, 1=BoolProperty, 2=None
    name_map = ["bExpanded", "BoolProperty", "None"]
    # Legacy inner tag: name + type + size + array_index + BoolVal + HasPropertyGuid
    value = (
        fname(0)
        + fname(1)
        + struct.pack("<ii", 0, 0)
        + bytes([1, 0])  # bExpanded = true, no property guid
        + fname(2)  # None terminator = value boundary
    )
    key = struct.pack("<i", 4) + b"key\x00"
    payload = struct.pack("<ii", 0, 1) + key + value  # keys_to_remove=0, entries=1
    tag = PropertyTag(
        name="ExpansionStates",
        type="MapProperty",
        size=len(payload),
        key_type="StrProperty",
        value_type="StructProperty",
        value_type_struct=None,
    )
    arc = ByteArchive(payload, tolerant=True)
    arc._file_version_ue4 = 522
    arc._file_version_ue5 = 1004  # legacy tag path, same gate as the Lyra sample
    result = parse_map_property(tag, arc, name_map, export_map=[], summary=None)
    assert result.key_type == "StrProperty"
    assert result.value_type == "StructProperty"
    assert len(result.entries) == 1
    entry_value = result.entries[0]["value"]
    assert entry_value.struct_type == "Unknown"  # honest: legacy tag has no name
    assert entry_value.fields == {"bExpanded": True}
    assert entry_value.parse_status == "success"
    # Value boundary honored: cursor exactly at end, nothing spilled, no diagnostics.
    assert arc.tell() == len(payload)
    assert arc.get_structured_diagnostics() == []


def test_map_value_unknown_struct_garbage_rolls_back_without_spill():
    """A non-tagged (native/garbage) value must rewind to the entry start.

    The rejected attempt's diagnostics are rolled back so a failed attempt is
    byte- and diagnostic-identical to the old opaque behavior (export:7
    BindingIdToReferences stays clean).
    """
    import struct

    name_map = ["bExpanded", "BoolProperty", "None"]
    key = struct.pack("<i", 4) + b"key\x00"
    garbage_value = b"\xff\xff\xff\xff\x00\x00\x00\x00"  # FName index 0xFFFFFFFF -> name OOR
    payload = struct.pack("<ii", 0, 1) + key + garbage_value
    tag = PropertyTag(
        name="BindingIdToReferences",
        type="MapProperty",
        size=len(payload),
        key_type="StrProperty",
        value_type="StructProperty",
        value_type_struct=None,
    )
    arc = ByteArchive(payload, tolerant=True)
    arc._file_version_ue4 = 522
    arc._file_version_ue5 = 1004
    result = parse_map_property(tag, arc, name_map, export_map=[], summary=None)
    entry_value = result.entries[0]["value"]
    assert entry_value.parse_status == "opaque"
    assert entry_value.fields == {}
    # Cursor never advanced into the value (no spill into the next segment).
    assert arc.tell() == 8 + len(key)
    # Diagnostics recorded by the rejected attempt were rolled back.
    assert arc.get_structured_diagnostics() == []
