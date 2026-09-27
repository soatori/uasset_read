import struct

import pytest

from tests.fixtures import sample_path
from uasset_read.exceptions import ParseError
from uasset_read.layout import detect_layout
from uasset_read.package import parse_package_document
from uasset_read.parsers.legacy_reader import LegacyPackageReader
from uasset_read.sources import CompositeSource, MemorySource


def test_loose_sample_selects_legacy_reader():
    source = CompositeSource.from_package(sample_path("StackOBot_BP_Drone.uasset"))
    layout = detect_layout(source)
    assert layout.kind == "legacy"
    assert layout.detection_reason == "validated_legacy"


def test_reader_selection_does_not_use_ue_major_version_only():
    # Bytes that look nothing like PACKAGE_FILE_TAG and are not a Zen header.
    layout = detect_layout(MemorySource(b"NOT_A_PACKAGE!!!!"))
    assert layout.kind == "unknown"
    assert layout.detection_reason == "unknown"


def _forbid_legacy_read(*_args, **_kwargs):
    raise AssertionError("LegacyPackageReader.read must not run for a non-legacy layout")


def test_unknown_layout_never_reaches_legacy_parse(tmp_path, monkeypatch):
    bad = tmp_path / "NotAPackage.uasset"
    bad.write_bytes(b"NOT_A_PACKAGE!!!!")
    monkeypatch.setattr(LegacyPackageReader, "read", _forbid_legacy_read)
    with pytest.raises(ParseError) as excinfo:
        parse_package_document(str(bad))
    # Structured failure, never a fabricated Legacy document.
    assert excinfo.value.code == "LAYOUT_UNKNOWN_UNSUPPORTED"
    assert excinfo.value.diagnostics
    assert excinfo.value.diagnostics[0].stage == "package.layout"


def test_zen_layout_never_reaches_legacy_parse(tmp_path, monkeypatch):
    # Structural FZenPackageSummary prefix: HeaderSize fits the source and the
    # seven offset fields are absent-optional (-1) — passes the detector's
    # zen check without any payload parsing (fixture limit).
    blob = bytearray(64)
    struct.pack_into("<I", blob, 4, len(blob))  # HeaderSize at byte 4
    for i in range(7):
        struct.pack_into("<i", blob, 20 + 4 * i, -1)
    path = tmp_path / "ZenLike.uasset"
    path.write_bytes(bytes(blob))
    monkeypatch.setattr(LegacyPackageReader, "read", _forbid_legacy_read)
    with pytest.raises(ParseError) as excinfo:
        parse_package_document(str(path))
    assert excinfo.value.code == "ZEN_PACKAGE_UNSUPPORTED"
    diag = excinfo.value.diagnostics[0]
    assert diag.stage == "package.layout"
    assert diag.offset == 0
    assert diag.size == 64
    assert diag.reason == "known_unimplemented"


def test_legacy_orchestration_stamps_document_layout():
    doc = parse_package_document(str(sample_path("StackOBot_BP_Drone.uasset")))
    assert doc.layout == "legacy"
