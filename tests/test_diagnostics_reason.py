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
