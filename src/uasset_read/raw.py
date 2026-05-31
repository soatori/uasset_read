"""Lightweight readers for non-package Unreal-adjacent files."""
from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json
import struct


RAW_JSON_EXTENSIONS = {".uplugin", ".upluginmanifest"}
RAW_INI_EXTENSIONS = {".ini"}
RAW_AUDIO_EXTENSIONS = {".wem", ".bnk", ".pck", ".bank", ".awb", ".acb"}


@dataclass
class RawFileResult:
    path: str
    file_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    entries: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return not self.errors


def parse_raw_file(path: str) -> RawFileResult:
    """Parse a supported non-package file into lightweight metadata."""

    p = Path(path)
    ext = p.suffix.lower()
    if ext in RAW_JSON_EXTENSIONS:
        return parse_json_descriptor(path)
    if ext in RAW_INI_EXTENSIONS:
        return parse_ini_file(path)
    if ext == ".locres":
        return parse_locres(path)
    if ext == ".locmeta":
        return parse_locmeta(path)
    if ext in RAW_AUDIO_EXTENSIONS:
        return parse_audio_metadata(path)
    return RawFileResult(path=path, file_type="unknown", errors=[f"Unsupported raw file type: {ext}"])


def parse_json_descriptor(path: str) -> RawFileResult:
    result = RawFileResult(path=path, file_type=Path(path).suffix.lower().lstrip("."))
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        result.metadata = data if isinstance(data, dict) else {"value": data}
    except Exception as exc:
        result.errors.append(str(exc))
    return result


def parse_ini_file(path: str) -> RawFileResult:
    result = RawFileResult(path=path, file_type="ini")
    parser = ConfigParser(strict=False)
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8-sig")
        result.metadata = {section: dict(parser.items(section)) for section in parser.sections()}
    except Exception as exc:
        result.errors.append(str(exc))
    return result


def parse_audio_metadata(path: str) -> RawFileResult:
    p = Path(path)
    result = RawFileResult(path=path, file_type=p.suffix.lower().lstrip("."))
    try:
        data = p.read_bytes()
        result.metadata = {
            "size": len(data),
            "magic": data[:4].hex(),
            "codec": _detect_audio_container(data, p.suffix.lower()),
        }
        if p.suffix.lower() == ".bnk" and len(data) >= 12:
            result.metadata["soundbank_id"] = struct.unpack_from("<I", data, 8)[0]
    except Exception as exc:
        result.errors.append(str(exc))
    return result


def parse_locmeta(path: str) -> RawFileResult:
    result = RawFileResult(path=path, file_type="locmeta")
    try:
        data = Path(path).read_bytes()
        result.metadata = {
            "size": len(data),
            "magic": data[:4].hex(),
            "raw_preview": data[:64].hex(),
        }
    except Exception as exc:
        result.errors.append(str(exc))
    return result


def parse_locres(path: str) -> RawFileResult:
    """Best-effort locres reader with conservative string scraping."""

    result = RawFileResult(path=path, file_type="locres")
    try:
        data = Path(path).read_bytes()
        result.metadata = {"size": len(data), "magic": data[:4].hex()}
        result.entries = _scrape_locres_strings(data)
    except Exception as exc:
        result.errors.append(str(exc))
    return result


def _detect_audio_container(data: bytes, ext: str) -> str:
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "riff-wav"
    if data.startswith(b"BKHD"):
        return "wwise-bank"
    if ext in {".awb", ".acb"}:
        return "criware"
    if ext in {".wem", ".bnk", ".pck", ".bank"}:
        return "wwise"
    return "unknown"


def _scrape_locres_strings(data: bytes) -> list[dict[str, Any]]:
    strings: list[str] = []
    current = bytearray()
    for byte in data:
        if 32 <= byte < 127:
            current.append(byte)
        else:
            if len(current) >= 3:
                strings.append(current.decode("utf-8", errors="replace"))
            current.clear()
    if len(current) >= 3:
        strings.append(current.decode("utf-8", errors="replace"))
    return [{"value": value} for value in strings[:200]]

