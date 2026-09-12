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
