"""Real-sample gates for parse-quality hardening (temp/parse_completion_report.md)."""

from __future__ import annotations

from pathlib import Path

from uasset_read.package import parse_package_document

SAMPLES = Path(__file__).parent / "samples"


def _codes(doc):
    return [d.code for d in doc.diagnostics or []]


def test_lyra_seq_fstring_out_of_range_is_bounded():
    """P0: MovieScene misalignment must not fan out to 28 identical OORs."""
    doc = parse_package_document(
        SAMPLES / "Lyra_SEQ_LobbyScreen_LevelSequence.uasset",
        depth="asset",
        tolerant=True,
    )
    oor = [c for c in _codes(doc) if c == "fstring_out_of_range"]
    # Acceptance from the report: 0 or 1 after short-circuit (not 28).
    assert len(oor) <= 1, f"fstring_out_of_range={len(oor)}"
    movie = next(o for o in doc.objects if o.id == "export:9")
    assert movie.status.parse == "partial"
    # Top-level MovieScene tags must still be present (not skipped wholesale).
    for key in ("Spawnables", "ObjectBindings", "PlaybackRange"):
        assert key in (movie.properties or {})


def test_import_data_samples_have_no_name_index_out_of_range():
    """P0: ImportData JSON prelude must not be parsed as tagged FNames."""
    names = (
        "ALS_Concrete_Step_01_SoundWave.uasset",
        "ALS_N_FallLoop.uasset",
        "FirstPerson_T_GridChecker_A.uasset",
        "StarterContent_SM_Chair.uasset",
    )
    for name in names:
        doc = parse_package_document(SAMPLES / name, depth="object", tolerant=True)
        codes = _codes(doc)
        assert "name_index_out_of_range" not in codes, name
        for o in doc.objects:
            if "ImportData" in str(o.class_name or ""):
                assert o.status.parse == "complete", name
                trailers = [
                    d
                    for d in doc.diagnostics
                    if d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED"
                    and d.object_id == o.id
                    and "leaves 2" in (d.message or "")
                ]
                assert not trailers, f"{name}:{o.id}"


# ---------------------------------------------------------------------------
# Task 6A: count and memory hardening
# ---------------------------------------------------------------------------


def test_resource_budget_rejects_negative_reserve():
    import pytest

    from uasset_read.memory_safety import MemoryLimitExceeded, reserve_memory

    with pytest.raises(MemoryLimitExceeded, match="negative"):
        reserve_memory(-100, "unit")


def test_read_native_fields_rejects_oversized_count():
    import pytest

    from uasset_read.archive import ByteArchive
    from uasset_read.constants import MAX_SAFE_COUNT
    from uasset_read.exceptions import ParseError
    from uasset_read.kismet.native_fields import NativeFieldContext, read_native_fields

    context = NativeFieldContext(name_map=[], import_map=[], export_map=[])
    with pytest.raises(ParseError, match="native field count"):
        read_native_fields(ByteArchive(b""), MAX_SAFE_COUNT + 1, context)


def test_read_native_fields_rejects_negative_count():
    import pytest

    from uasset_read.archive import ByteArchive
    from uasset_read.exceptions import ParseError
    from uasset_read.kismet.native_fields import NativeFieldContext, read_native_fields

    context = NativeFieldContext(name_map=[], import_map=[], export_map=[])
    with pytest.raises(ParseError, match="native field count"):
        read_native_fields(ByteArchive(b""), -1, context)


def _usmap_v0_with_payload(payload: bytes) -> bytes:
    """Minimal uncompressed version-0 usmap blob wrapping *payload*."""
    return (
        (0x30C4).to_bytes(2, "little")  # FILE_MAGIC
        + bytes([0])  # version 0 (skips package/custom-version block)
        + bytes([0])  # compression method 0 (none)
        + len(payload).to_bytes(4, "little")
        + len(payload).to_bytes(4, "little")
        + payload
    )


def test_usmap_rejects_negative_custom_version_count():
    import pytest

    from uasset_read.exceptions import ParseError
    from uasset_read.mappings import UsmapParser

    # version >= 1 with has_package_versions=1, then custom_count = -1.
    blob = (
        (0x30C4).to_bytes(2, "little")
        + bytes([1, 1])
        + b"\x00" * 8  # PackageFileVersion
        + (-1).to_bytes(4, "little", signed=True)
    )
    with pytest.raises(ParseError, match="CustomVersion"):
        UsmapParser(blob)


def test_usmap_custom_version_count_exceeds_remaining_bytes():
    import pytest

    from uasset_read.exceptions import ParseError
    from uasset_read.mappings import UsmapParser

    # custom_count=1 but zero of the required 20-byte entries follow.
    blob = (
        (0x30C4).to_bytes(2, "little")
        + bytes([1, 1])
        + b"\x00" * 8
        + (1).to_bytes(4, "little")
    )
    with pytest.raises(ParseError, match="CustomVersion count exceeds remaining bytes"):
        UsmapParser(blob)


def test_usmap_rejects_oversized_name_count():
    import pytest

    from uasset_read.constants import MAX_SAFE_COUNT
    from uasset_read.exceptions import ParseError
    from uasset_read.mappings import UsmapParser

    payload = (MAX_SAFE_COUNT + 1).to_bytes(4, "little") + b"\x00" * 8
    with pytest.raises(ParseError, match="name_count"):
        UsmapParser(_usmap_v0_with_payload(payload))


def test_usmap_rejects_oversized_enum_count():
    import pytest

    from uasset_read.constants import MAX_SAFE_COUNT
    from uasset_read.exceptions import ParseError
    from uasset_read.mappings import UsmapParser

    payload = (0).to_bytes(4, "little") + (MAX_SAFE_COUNT + 1).to_bytes(4, "little")
    with pytest.raises(ParseError, match="enum_count"):
        UsmapParser(_usmap_v0_with_payload(payload))


def test_usmap_rejects_oversized_struct_count():
    import pytest

    from uasset_read.constants import MAX_SAFE_COUNT
    from uasset_read.exceptions import ParseError
    from uasset_read.mappings import UsmapParser

    payload = b"\x00" * 8 + (MAX_SAFE_COUNT + 1).to_bytes(4, "little")
    with pytest.raises(ParseError, match="struct_count"):
        UsmapParser(_usmap_v0_with_payload(payload))


def test_xfer_field_pointer_rejects_negative_count():
    import struct

    import pytest

    from uasset_read.exceptions import ParseError
    from uasset_read.kismet.archive import FKismetArchive

    archive = FKismetArchive(struct.pack("<i", -1), "test", [])
    with pytest.raises(ParseError, match="FFieldPath count"):
        archive.xfer_field_pointer()


def test_xfer_field_pointer_rejects_oversized_count():
    import struct

    import pytest

    from uasset_read.exceptions import ParseError
    from uasset_read.kismet.archive import FKismetArchive

    # 100 path segments would need 800 bytes; only the count word is present.
    archive = FKismetArchive(struct.pack("<i", 100), "test", [])
    with pytest.raises(ParseError, match="FFieldPath count"):
        archive.xfer_field_pointer()


def test_read_metadata_rejects_oversized_count():
    import struct

    import pytest

    from uasset_read.archive import ByteArchive
    from uasset_read.constants import MAX_SAFE_COUNT
    from uasset_read.exceptions import ParseError
    from uasset_read.kismet.native_fields import NativeFieldContext, _read_metadata

    # package_flags=0 → metadata is serialized for both the cooked-flag and
    # editor-filter omission gates (has_metadata bool + i32 count follow).
    context = NativeFieldContext(name_map=[], import_map=[], export_map=[], package_flags=0)
    data = struct.pack("<Ii", 1, MAX_SAFE_COUNT + 1)
    with pytest.raises(ParseError, match="metadata count"):
        _read_metadata(ByteArchive(data), context)


def test_read_metadata_rejects_count_over_remaining_bytes():
    import struct

    import pytest

    from uasset_read.archive import ByteArchive
    from uasset_read.exceptions import ParseError
    from uasset_read.kismet.native_fields import NativeFieldContext, _read_metadata

    context = NativeFieldContext(name_map=[], import_map=[], export_map=[], package_flags=0)
    # count=100 needs at least 800 bytes of key/value pairs; none follow.
    data = struct.pack("<Ii", 1, 100)
    with pytest.raises(ParseError, match="metadata count"):
        _read_metadata(ByteArchive(data), context)


def test_ufunction_native_property_count_over_limit_fails():
    """NativePropertyCount above MAX_SAFE_COUNT fails via the result shape."""
    from types import SimpleNamespace

    from uasset_read.archive import ByteArchive
    from uasset_read.constants import MAX_SAFE_COUNT
    from uasset_read.kismet.ufunction_reader import (
        _read_ustruct_prefix_and_script,
    )
    from uasset_read.serializers.object_resources import PackageIndex
    from uasset_read.versioning import CORE_GUID, FRAMEWORK_GUID

    # SuperStruct(i32) + Children count(i32)=0 + NativePropertyCount(i32).
    payload = (
        (0).to_bytes(4, "little", signed=True)
        + (0).to_bytes(4, "little", signed=True)
        + (MAX_SAFE_COUNT + 1).to_bytes(4, "little", signed=True)
    )
    window = ByteArchive(payload)
    export = SimpleNamespace(
        object_name="Fn",
        class_index=PackageIndex(0),
        serial_offset=0,
        serial_size=len(payload),
        script_serialization_start_offset=0,
        script_serialization_end_offset=0,
    )
    # CORE >= 4 so NativePropertyCount is read; FRAMEWORK >= 29 so the
    # modern children count layout is used.
    summary = SimpleNamespace(
        custom_versions=[
            SimpleNamespace(guid=CORE_GUID, version=4),
            SimpleNamespace(guid=FRAMEWORK_GUID, version=29),
        ],
        saved_by_engine_version=SimpleNamespace(major=5, minor=0),
    )
    result = _read_ustruct_prefix_and_script(
        window,
        export,  # type: ignore[arg-type]
        summary,  # type: ignore[arg-type]
        export_index=0,
        name_map=[],
        import_map=[],
        export_map=[],
    )
    assert result.status == "failed"
    assert result.failure is not None
    assert "NativePropertyCount" in result.failure.error_message


# ---------------------------------------------------------------------------
# Task 6B: property protocol stop and `.umap` batch discovery
# ---------------------------------------------------------------------------


def test_property_type_name_pending_incomplete_raises():
    import struct

    import pytest

    from uasset_read.archive import ByteArchive
    from uasset_read.constants import (
        MAX_PROPERTY_TYPE_NODES,
        PROPERTY_TAG_COMPLETE_TYPE_NAME,
    )
    from uasset_read.exceptions import ParseError
    from uasset_read.serializers.property_tags import _read_property_type_name

    # Each preorder node claims one inner child so pending never drains; the
    # node-cap loop must stop at MAX_PROPERTY_TYPE_NODES and raise instead of
    # silently returning a truncated tree.
    name_map = ["T"]
    # FName is (u32 index, u32 number) followed by the i32 inner_count.
    node = struct.pack("<IIi", 0, 0, 1)  # index=0, number=0, inner_count=1
    data = node * MAX_PROPERTY_TYPE_NODES
    archive = ByteArchive(data)
    with pytest.raises(ParseError, match="FPropertyTypeName"):
        _read_property_type_name(
            archive,
            name_map,
            file_version_ue5=PROPERTY_TAG_COMPLETE_TYPE_NAME,
        )


def test_serialization_control_unknown_bits_are_terminal(monkeypatch):
    from uasset_read.package import _parse_cached, parse_package_document
    from uasset_read.parsers import property_parser as pp

    sample = SAMPLES / "MyProject_UE58_TestMaterial.uasset"
    tag_reads = []

    def fake(archive, summary, export):
        archive._record_structured_diagnostic(
            code="unknown_serialization_control_bits",
            stage="parse_properties",
            offset=archive.tell(),
            fallback="skipped_subsequent_reads",
            message="injected unknown bits",
        )
        return False

    def must_not_read_tag(*args, **kwargs):
        tag_reads.append(True)
        raise AssertionError("tag reader ran after terminal serialization control")

    _parse_cached.cache_clear()
    try:
        monkeypatch.setattr(pp, "_handle_serialization_control", fake)
        monkeypatch.setattr(pp, "read_property_tag", must_not_read_tag)
        doc = parse_package_document(str(sample), depth="object", tolerant=True)
    finally:
        _parse_cached.cache_clear()
    assert tag_reads == []
    assert any(d.code == "unknown_serialization_control_bits" for d in doc.diagnostics)


def test_batch_scans_umap(tmp_path):
    from uasset_read.cli import _iter_batch_packages

    (tmp_path / "a.uasset").write_bytes(b"x")
    (tmp_path / "b.umap").write_bytes(b"x")
    (tmp_path / "c.txt").write_bytes(b"x")
    result = [p.name for p in _iter_batch_packages(tmp_path)]
    assert result == ["a.uasset", "b.umap"]
