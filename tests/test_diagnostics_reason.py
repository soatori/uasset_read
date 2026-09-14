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
