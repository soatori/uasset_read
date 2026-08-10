"""Regression tests for Kismet archive safety guards.

Covers:
- Recursion depth limit (MAX_EXPRESSION_RECURSION_DEPTH = 256)
- No-progress detection (expression handler that does not advance stream)
- Bounded array guard (read_expression_array bounded by remaining bytes)
- Unknown token handling in tolerant vs strict mode
"""
from __future__ import annotations

import struct

import pytest

from uasset_read.kismet.archive import (
    FKismetArchive,
    MAX_EXPRESSION_RECURSION_DEPTH,
)
from uasset_read.kismet.tokens import EExprToken
from uasset_read.exceptions import ParseError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_archive(data: bytes, *, tolerant: bool = False) -> FKismetArchive:
    """Create a FKismetArchive wrapping synthetic byte data."""
    return FKismetArchive(data, name="test", name_map=[], tolerant=tolerant)


# ---------------------------------------------------------------------------
# Test: recursion depth guard
# ---------------------------------------------------------------------------

def test_read_expression_rejects_excessive_recursion_depth():
    """read_expression() must raise ParseError when recursion depth >= 256.

    Instead of constructing 256 nested bytecode levels, we mock _expression_depth
    to simulate deep recursion, then call read_expression() which should fail
    immediately at the depth check.
    """
    # EX_Self (0x17) is a simple expression that does not call from_archive
    archive = _make_archive(bytes([EExprToken.EX_Self]))
    archive._expression_depth = MAX_EXPRESSION_RECURSION_DEPTH

    with pytest.raises(ParseError, match="recursion depth"):
        archive.read_expression()


# ---------------------------------------------------------------------------
# Test: no-progress guard
# ---------------------------------------------------------------------------

def test_read_expression_rejects_handler_that_makes_no_progress():
    """read_expression() must raise ParseError when the handler does not advance the stream.

    We feed a valid token byte (EX_Nothing = 0x0B, which is a simple expression
    requiring no additional bytes), but wrap the underlying stream so that tell()
    always returns 0. This simulates a handler that made no progress: the progress
    check compares serialized_end against serialized_start and finds no advancement.
    """
    data = bytes([EExprToken.EX_Nothing, 0x00])
    archive = _make_archive(data)

    # Replace _file with a wrapper that always reports position 0 from tell().
    # The read() still works normally (delegates to the real BytesIO), but
    # tell() always returns 0, making serialized_end == serialized_start.
    class _NoProgressStream:
        """Wrapper that hides read progress from tell()."""

        def __init__(self, inner):
            self._inner = inner

        def read(self, n=-1):
            return self._inner.read(n)

        def seek(self, pos, whence=0):
            return self._inner.seek(pos, whence)

        def tell(self):
            return 0

    archive._file = _NoProgressStream(archive._file)

    with pytest.raises(ParseError, match="made no progress"):
        archive.read_expression()


# ---------------------------------------------------------------------------
# Test: bounded array guard
# ---------------------------------------------------------------------------

def test_read_expression_array_is_bounded_by_remaining_bytes():
    """read_expression_array() must raise ParseError when it exceeds the
    number of remaining bytes without finding the end token.

    We create a small buffer with non-end-token bytes. The array guard
    limits iterations to remaining() bytes; when no end token appears,
    it must raise.
    """
    # Fill buffer with bytes that will each be parsed as EX_LocalVariable (0x00)
    # which needs 8 additional bytes (name_index + number). Since we provide
    # only 3 bytes total, the first EX_LocalVariable will try to read and fail.
    # Instead, use EX_Nothing (0x0B) which is 1 byte and valid.
    # Array of 3 EX_Nothing bytes, no end token
    data = bytes([EExprToken.EX_Nothing] * 3)
    archive = _make_archive(data)

    with pytest.raises(ParseError, match="exceeded"):
        # EX_EndFunctionParms (0x16) will never appear in the data
        archive.read_expression_array(EExprToken.EX_EndFunctionParms)


# ---------------------------------------------------------------------------
# Test: unknown token in tolerant vs strict mode
# ---------------------------------------------------------------------------

def test_unknown_token_strict_mode_raises():
    """In strict mode, an unknown token byte raises ParseError."""
    # 0x6E is not a recognized EExprToken
    archive = _make_archive(bytes([0x6E]), tolerant=False)

    with pytest.raises(ParseError, match="Unknown EExprToken"):
        archive.read_expression()


def test_unknown_token_tolerant_mode_skips():
    """In tolerant mode, unknown tokens are skipped and parsing continues.

    We feed an unknown byte (0x6E) followed by EX_Nothing (0x0B).
    After skipping 0x6E, the archive should successfully parse EX_Nothing.
    """
    data = bytes([0x6E, EExprToken.EX_Nothing])
    archive = _make_archive(data, tolerant=True)

    expr = archive.read_expression()
    assert expr.Token == EExprToken.EX_Nothing
    assert archive.tell() == 2
