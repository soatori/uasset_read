from __future__ import annotations

import struct
from pathlib import Path

import pytest

from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError
from uasset_read.serializers.graph import _read_ftext_value


def _make_archive(tmp_path: Path, data: bytes) -> FArchive:
    path = tmp_path / "ftext.bin"
    path.write_bytes(data)
    return FArchive(str(path), tolerant=True)


def _fstring(value: str) -> bytes:
    encoded = value.encode("utf-8") + b"\x00"
    return struct.pack("<i", len(encoded)) + encoded


def _ftext_none(value: str = "") -> bytes:
    body = struct.pack("<I", 1 if value else 0)
    if value:
        body += _fstring(value)
    return struct.pack("<iB", 0, 255) + body


def _ftext_base(source: str, namespace: str = "", key: str = "") -> bytes:
    return struct.pack("<iB", 8, 0) + _fstring(namespace) + _fstring(key) + _fstring(source)


def test_read_ftext_none_history(tmp_path: Path) -> None:
    archive = _make_archive(tmp_path, _ftext_none())
    try:
        value, flags, history_type, consumed = _read_ftext_value(archive, tolerant=True)
        assert value == ""
        assert flags == 0
        assert history_type == -1
        assert consumed == 9
    finally:
        archive.close()


def test_read_ftext_base_history(tmp_path: Path) -> None:
    archive = _make_archive(tmp_path, _ftext_base("Jump"))
    try:
        value, flags, history_type, _ = _read_ftext_value(archive, tolerant=True)
        assert value == "Jump"
        assert flags == 8
        assert history_type == 0
    finally:
        archive.close()


def test_read_ftext_named_format_history(tmp_path: Path) -> None:
    data = b"".join(
        [
            struct.pack("<iB", 0, 1),
            _ftext_base("{PinDisplayName} {ProtoPinDisplayName}", "KismetSchema", "SplitPinFriendlyNameFormat"),
            struct.pack("<i", 2),
            _fstring("PinDisplayName"),
            struct.pack("<B", 4),
            _ftext_none("Action Value"),
            _fstring("ProtoPinDisplayName"),
            struct.pack("<B", 4),
            _ftext_none("X"),
        ]
    )
    archive = _make_archive(tmp_path, data)
    try:
        value, flags, history_type, _ = _read_ftext_value(archive, tolerant=True)
        assert value == "Action Value X"
        assert flags == 0
        assert history_type == 1
    finally:
        archive.close()


def test_invalid_ftext_length_does_not_consume_following_bytes(tmp_path: Path) -> None:
    invalid = struct.pack("<iB", 8, 0) + struct.pack("<i", 20_001)
    archive = _make_archive(tmp_path, invalid + struct.pack("<i", 1234))
    try:
        with pytest.raises(ParseError):
            _read_ftext_value(archive, tolerant=True)
        assert archive.tell() == 9
        assert archive.read_i32() == 1234
    finally:
        archive.close()
