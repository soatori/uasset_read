"""Consolidated IR builder tests — trimmed to essential regression/safety coverage.

Kept tests:
- MagicMock must not leak into _safe_int (safety)
- _build_debug_ir must not crash on empty/None (safety)
- UsmapParser must reject invalid magic (safety)
- format_hex_view must handle empty entries (safety)
- sanitize_identifier must reject spaces (safety)
"""
from __future__ import annotations

import json
import struct
from unittest.mock import MagicMock

import pytest

from uasset_read.debug.hex_view import HexViewEntry, format_hex_view
from uasset_read.ir_builder import _safe_int, _build_debug_ir
from uasset_read.mappings import UsmapParser
from uasset_read.cpp_gen.sanitizer import sanitize_identifier


def test_magicmock_does_not_leak_through_safe_int():
    """MagicMock implements __int__ but _safe_int must intercept it.

    Regression: mock objects from unittest.mock were silently converted to
    int values, causing downstream data corruption.
    """
    mock = MagicMock()
    assert _safe_int(mock) == 0
    assert _safe_int(mock, 99) == 99


def test_build_debug_ir_rejects_empty_and_none():
    """_build_debug_ir returns None for empty or None input.

    Regression: passing an empty list caused AttributeError downstream.
    """
    assert _build_debug_ir([]) is None
    assert _build_debug_ir(None) is None


def test_usmap_parser_rejects_invalid_magic():
    """UsmapParser must raise ParseError on invalid magic number.

    Safety: parsing corrupt data without validation could cause silent
    data corruption or buffer overruns.
    """
    from uasset_read.exceptions import ParseError

    data = struct.pack("<H", 0x1234) + b"\x00" * 20
    with pytest.raises(ParseError, match="magic"):
        UsmapParser(data)


def test_format_hex_view_empty_entries():
    """format_hex_view must handle empty entries without crashing.

    Regression: an empty list caused an IndexError in the sort step.
    """
    result = format_hex_view([])
    assert "no hex view entries" in result


def test_sanitize_identifier_replaces_spaces():
    """sanitize_identifier must replace spaces with underscores.

    Safety: identifiers with spaces produce invalid C++ code and
    silently corrupt generated headers.
    """
    assert sanitize_identifier("hello world") == "hello_world"
