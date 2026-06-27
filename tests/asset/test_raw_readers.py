from __future__ import annotations

from pathlib import Path

from uasset_read.raw import parse_audio_metadata, parse_ini_file, parse_json_descriptor, parse_raw_file


def test_parse_uplugin_descriptor(tmp_path: Path):
    path = tmp_path / "Example.uplugin"
    path.write_text('{"FileVersion": 3, "FriendlyName": "Example"}', encoding="utf-8")

    result = parse_json_descriptor(str(path))

    assert result.is_success
    assert result.file_type == "uplugin"
    assert result.metadata["FriendlyName"] == "Example"


def test_parse_ini_file(tmp_path: Path):
    path = tmp_path / "DefaultGame.ini"
    path.write_text("[/Script/Game]\nName=Demo\n", encoding="utf-8")

    result = parse_ini_file(str(path))

    assert result.is_success
    assert result.metadata["/Script/Game"]["Name"] == "Demo"


def test_parse_audio_metadata_reads_size_and_magic(tmp_path: Path):
    path = tmp_path / "Sound.bnk"
    path.write_bytes(b"BKHD\x00\x00\x00\x00\x7b\x00\x00\x00")

    result = parse_audio_metadata(str(path))

    assert result.is_success
    assert result.metadata["codec"] == "wwise-bank"
    assert result.metadata["soundbank_id"] == 123


def test_parse_raw_file_rejects_unknown_type(tmp_path: Path):
    path = tmp_path / "unknown.txt"
    path.write_text("x", encoding="utf-8")

    result = parse_raw_file(str(path))

    assert not result.is_success
    assert result.file_type == "unknown"

