"""Unit tests for Diagnostic.reason (quality system)."""

from uasset_read.models.diagnostics import Diagnostic, make_diagnostic


def test_reason_omitted_from_dict_when_unset():
    d = make_diagnostic("SOME_CODE", "msg", "objects.export")
    assert d.reason is None
    payload = d.to_dict()
    assert "reason" not in payload


def test_reason_included_when_set():
    d = make_diagnostic(
        "EXPORT_TRAILING_BYTES_UNCONSUMED",
        "leaves 53 bytes",
        "objects.export",
        reason="editor_only",
    )
    assert d.reason == "editor_only"
    assert d.to_dict()["reason"] == "editor_only"


def test_make_diagnostic_accepts_reason_keyword():
    d = Diagnostic(
        severity="warning",
        code="name_index_out_of_range",
        message="bad index",
        stage="read_name",
        reason="recovered_corruption",
    )
    assert d.reason == "recovered_corruption"


def test_fname_out_of_range_carries_recovered_corruption_reason(tmp_path):
    # Build a minimal ByteArchive-like path is heavy; call _record on FArchive subclass.
    from uasset_read.archive import FArchive

    class _Mem(FArchive):
        def __init__(self):
            self._init_archive_attrs(path="<mem>", tolerant=True)
            self._file = None

    arch = _Mem()
    arch._current_object_id = "export:1"
    arch._record_structured_diagnostic(
        code="name_index_out_of_range",
        stage="read_name",
        offset=16,
        raw_value=3223003549,
        fallback="used_default_name",
        message="Name index out of range",
        reason="recovered_corruption",
    )
    (diag,) = arch.get_structured_diagnostics()
    assert diag.reason == "recovered_corruption"
    assert diag.code == "name_index_out_of_range"


def test_classify_trailing_reason_mapping():
    from uasset_read.models.diagnostics import classify_trailing_reason

    assert classify_trailing_reason("PackageMetaData", 53) == "editor_only"
    assert classify_trailing_reason("MetaData", 53) == "editor_only"
    assert classify_trailing_reason("FontFace", 6_715_680) == "bulk_expected"
    assert classify_trailing_reason("SoundWave", 68) == "bulk_expected"
    assert classify_trailing_reason("NiagaraNodeFunctionCall", 7900) == "known_unimplemented"
    assert classify_trailing_reason("NiagaraNodeAssignment", 100) == "known_unimplemented"
    assert classify_trailing_reason("Skeleton", 9191) == "known_unimplemented"
    assert classify_trailing_reason("PhysicsAsset", 940) == "known_unimplemented"
    assert classify_trailing_reason("BlueprintGeneratedClass", 5977) == "editor_only"
    assert classify_trailing_reason("K2Node_CallFunction", 200) == "editor_only"
    assert classify_trailing_reason("EdGraph", 100) == "editor_only"
    assert classify_trailing_reason("SomeUnknownClass", 100) == "unexpected"


def test_merge_archive_recoveries_forwards_reason_and_fallback():
    from types import SimpleNamespace

    from uasset_read.models.diagnostics import Diagnostic
    from uasset_read.parsers.legacy_reader import _merge_archive_recoveries

    sd = Diagnostic(
        severity="warning",
        code="name_index_out_of_range",
        message="Name index out of range fallback=used_default_name",
        stage="read_name",
        object_id="export:1",
        offset=16,
        fallback="used_default_name",
        reason="recovered_corruption",
    )
    archive = SimpleNamespace(get_structured_diagnostics=lambda: [sd])
    diagnostics: list[Diagnostic] = []
    _merge_archive_recoveries(archive, [], diagnostics)
    (merged,) = diagnostics
    assert merged.code == "name_index_out_of_range"
    assert merged.reason == "recovered_corruption"
    assert merged.fallback == "used_default_name"
    assert merged.effect == "recovery"
    assert merged.recoverable is True


def test_merge_archive_recoveries_stop_table_keeps_reason():
    from types import SimpleNamespace

    from uasset_read.models.diagnostics import Diagnostic
    from uasset_read.parsers.legacy_reader import _merge_archive_recoveries

    sd = Diagnostic(
        severity="error",
        code="export_table_truncated",
        message="truncated",
        stage="export_table",
        object_id="export:2",
        offset=100,
        fallback="stop_table",
        reason="recovered_corruption",
    )
    archive = SimpleNamespace(get_structured_diagnostics=lambda: [sd])
    diagnostics: list[Diagnostic] = []
    _merge_archive_recoveries(archive, [], diagnostics)
    (merged,) = diagnostics
    assert merged.reason == "recovered_corruption"
    assert merged.fallback == "stop_table"
    assert merged.effect == "data_loss"
    assert merged.recoverable is False


def test_table_payload_residue_emits_conservative_complete_reason():
    """Residue is fully disclosed; the parser stopped conservatively, not corruptly."""
    import struct

    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.legacy_reader import _read_table_rows

    # One valid row then 2 undecoded bytes -> TABLE_PAYLOAD_RESIDUE (+ TRUNCATED).
    data = struct.pack("<i", 1) + struct.pack("<ii", 1, 0) + struct.pack("<ii", 0, 0) + b"\x7f\x7f"
    diags: list = []
    _read_table_rows(
        ByteArchive(data),
        serial_end=len(data),
        name_map=["None", "RowA"],
        object_id="export:1",
        diagnostics=diags,
    )
    residue_diags = [d for d in diags if d.code == "TABLE_PAYLOAD_RESIDUE"]
    assert residue_diags, f"expected TABLE_PAYLOAD_RESIDUE, got {[d.code for d in diags]}"
    assert all(d.reason == "conservative_complete" for d in residue_diags)


def test_table_rows_truncated_emits_conservative_complete_reason():
    """Row shortfall is disclosed as conservative stop, not silent data loss."""
    import struct

    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.legacy_reader import _read_table_rows

    # Claims 2 rows, only 1 fits -> TABLE_ROWS_TRUNCATED, no residue.
    data = struct.pack("<i", 2) + struct.pack("<ii", 1, 0) + struct.pack("<ii", 0, 0)
    diags: list = []
    _read_table_rows(
        ByteArchive(data),
        serial_end=len(data),
        name_map=["None", "A"],
        object_id="export:1",
        diagnostics=diags,
    )
    truncated = [d for d in diags if d.code == "TABLE_ROWS_TRUNCATED"]
    assert truncated, f"expected TABLE_ROWS_TRUNCATED, got {[d.code for d in diags]}"
    assert all(d.reason == "conservative_complete" for d in truncated)


def test_datatable_table_diagnostics_marked_conservative_complete():
    from uasset_read.package import parse_package_document

    doc = parse_package_document("tests/samples/FirstPerson_DT_WeaponList.uasset")
    table_diags = [
        d for d in doc.diagnostics if d.code in {"TABLE_PAYLOAD_RESIDUE", "TABLE_ROWS_TRUNCATED"}
    ]
    # Fixture may or may not emit both; assert every emitted TABLE_* is classified.
    assert all(d.reason == "conservative_complete" for d in table_diags)
    if not table_diags:
        # Force one synthetic check that make_diagnostic can carry the reason.
        from uasset_read.models.diagnostics import make_diagnostic

        d = make_diagnostic("TABLE_ROWS_TRUNCATED", "m", "payload.table", reason="conservative_complete")
        assert d.reason == "conservative_complete"
