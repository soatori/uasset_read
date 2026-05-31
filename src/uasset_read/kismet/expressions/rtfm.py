"""
Kismet 表达式系统 — AutoRTFM 表达式。

包含事务相关的 AutoRTFM 指令，用于软件事务内存（STM）支持。
对应 EX_AutoRtfmTransact, EX_AutoRtfmStopTransact, EX_AutoRtfmAbortIfNot。
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

    Id: int = 0
    CodeOffset: int = 0
    Parameters: list[KismetExpression] = None

    @property
    def Token(self):
        return EExprToken.EX_AutoRtfmTransact

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_AutoRtfmTransact:
        id_ = archive.read_i32()
        offset = archive.read_u32()
        params = archive.read_expression_array(EExprToken.EX_EndOfScript)
        return cls(Id=id_, CodeOffset=offset, Parameters=params)


@dataclass
class EX_AutoRtfmStopTransact(KismetExpression):
    """AutoRTFM: if in transaction, abort or break."""

    Id: int = 0
    Mode: EAutoRtfmStopTransactMode = EAutoRtfmStopTransactMode.Commit

    @property
    def Token(self):
        return EExprToken.EX_AutoRtfmStopTransact

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_AutoRtfmStopTransact:
        id_ = archive.read_i32()
        mode = EAutoRtfmStopTransactMode(archive.read_u8())
        return cls(Id=id_, Mode=mode)


@dataclass
class EX_AutoRtfmAbortIfNot(KismetExpression):
    """AutoRTFM: evaluate bool condition, abort transaction on false."""

    @property
    def Token(self):
        return EExprToken.EX_AutoRtfmAbortIfNot
