"""EX_AutoRtfmTransact terminator regression test (issue #461)."""

from __future__ import annotations

import struct

from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.expressions.rtfm import (
    EX_AutoRtfmTransact,
    EX_AutoRtfmStopTransact,
)
from uasset_read.kismet.tokens import EAutoRtfmStopTransactMode, EExprToken


def _archive(data: bytes) -> FKismetArchive:
    return FKismetArchive(data, "test-rtfm-bytecode", [], tolerant=True)


def _build_transact_with_params(
    params: list[bytes],
    terminator: EExprToken,
) -> bytes:
    """Build EX_AutoRtfmTransact bytecode with given params and terminator.

    Format:
      - EX_AutoRtfmTransact (1 byte)
      - Id (4 bytes, i32)
      - CodeOffset (4 bytes, u32)
      - param expressions (variable)
      - terminator (1 byte)
    """
    buf = bytearray()
    buf.append(EExprToken.EX_AutoRtfmTransact)
    buf.extend(struct.pack("<i", 0))  # Id
    buf.extend(struct.pack("<I", 0))  # CodeOffset
    for param in params:
        buf.extend(param)
    buf.append(terminator)
    return bytes(buf)


def _nothing_bytes() -> bytes:
    return bytes([EExprToken.EX_Nothing])


class TestAutoRtfmTransactTerminator:
    """Verify EX_AutoRtfmTransact terminates at EX_AutoRtfmStopTransact, not EX_EndOfScript."""

    def test_terminates_at_stop_transact(self) -> None:
        """Parameters should be read until EX_AutoRtfmStopTransact."""
        data = _build_transact_with_params(
            params=[_nothing_bytes(), _nothing_bytes()],
            terminator=EExprToken.EX_AutoRtfmStopTransact,
        )
        archive = _archive(data)

        expr = archive.read_expression()

        assert isinstance(expr, EX_AutoRtfmTransact)
        assert len(expr.Parameters) == 2
        # The EX_AutoRtfmStopTransact should remain unread (next byte in stream)
        assert archive.tell() == len(data) - 1

    def test_terminates_before_end_of_script(self) -> None:
        """EX_EndOfScript should NOT be the terminator — reading must stop at EX_AutoRtfmStopTransact."""
        # Build bytecode where EX_AutoRtfmStopTransact appears before EX_EndOfScript.
        # With the correct terminator, reading stops at EX_AutoRtfmStopTransact.
        # With the wrong terminator (EX_EndOfScript), it would keep reading past it.
        buf = bytearray()
        buf.append(EExprToken.EX_AutoRtfmTransact)
        buf.extend(struct.pack("<i", 1))  # Id
        buf.extend(struct.pack("<I", 42))  # CodeOffset
        buf.extend(_nothing_bytes())  # param
        buf.append(EExprToken.EX_AutoRtfmStopTransact)  # correct terminator
        buf.append(EExprToken.EX_Nothing)  # should NOT be consumed as param
        buf.append(EExprToken.EX_EndOfScript)

        archive = _archive(bytes(buf))
        expr = archive.read_expression()

        assert isinstance(expr, EX_AutoRtfmTransact)
        # Only 1 parameter should be read (the Nothing before StopTransact)
        assert len(expr.Parameters) == 1
        # Position should be right before EX_AutoRtfmStopTransact
        assert archive.tell() == len(buf) - 3  # before StopTransact, Nothing, EndOfScript

    def test_empty_params_with_stop_transact(self) -> None:
        """EX_AutoRtfmTransact with zero parameters should work."""
        data = _build_transact_with_params(
            params=[],
            terminator=EExprToken.EX_AutoRtfmStopTransact,
        )
        archive = _archive(data)

        expr = archive.read_expression()

        assert isinstance(expr, EX_AutoRtfmTransact)
        assert len(expr.Parameters) == 0
