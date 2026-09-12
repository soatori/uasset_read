"""
Kismet expression system -- AutoRTFM expressions.

Contains transaction-related AutoRTFM instructions for software transactional memory (STM) support.
Corresponding opcodes: EX_AutoRtfmTransact, EX_AutoRtfmStopTransact, EX_AutoRtfmAbortIfNot.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.tokens import EExprToken, EAutoRtfmStopTransactMode

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_AutoRtfmTransact(KismetExpression):
    """AutoRTFM: run following code in a transaction."""

    CodeOffset: int = 0

    Token = EExprToken.EX_AutoRtfmTransact

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_AutoRtfmTransact:
        archive.read_i32()
        offset = archive.read_u32()
        archive.read_expression_array(EExprToken.EX_AutoRtfmStopTransact)
        return cls(CodeOffset=offset)


@dataclass
class EX_AutoRtfmStopTransact(KismetExpression):
    """AutoRTFM: if in transaction, abort or break."""

    Token = EExprToken.EX_AutoRtfmStopTransact

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_AutoRtfmStopTransact:
        archive.read_i32()
        EAutoRtfmStopTransactMode(archive.read_u8())
        return cls()


@dataclass
class EX_AutoRtfmAbortIfNot(KismetExpression):
    """AutoRTFM: evaluate bool condition, abort transaction on false."""

    Token = EExprToken.EX_AutoRtfmAbortIfNot

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_AutoRtfmAbortIfNot:
        archive.read_expression()
        return cls()
