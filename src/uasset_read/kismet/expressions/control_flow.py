from __future__ import annotations

"""Kismet control flow expressions.

Contains expression subclasses for jumps, conditional branches, execution flow stack operations,
and other control-flow-related constructs.
"""


from dataclasses import dataclass
from typing import TYPE_CHECKING

from uasset_read.kismet.expressions.base import (
    KismetExpression, KismetExpressionT, make_simple_expression,
)
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_Jump(KismetExpression):
    """Unconditional jump to a specified code offset."""

    CodeOffset: int = 0

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_Jump

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_Jump:
        offset = archive.read_u32()
        return cls(CodeOffset=offset)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["CodeOffset"] = self.CodeOffset
        return d


@dataclass
class EX_JumpIfNot(EX_Jump):
    """Conditional jump: jump if the boolean expression is false."""

    BooleanExpression: KismetExpression | None = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_JumpIfNot

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_JumpIfNot:
        offset = archive.read_u32()
        expr = archive.read_expression()
        return cls(CodeOffset=offset, BooleanExpression=expr)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["BooleanExpression"] = (
            self.BooleanExpression.to_dict() if self.BooleanExpression else None
        )
        return d


@dataclass
class EX_Skip(EX_Jump):
    """Skip over an expression code block."""

    SkipExpression: KismetExpression | None = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_Skip

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_Skip:
        offset = archive.read_u32()
        expr = archive.read_expression()
        return cls(CodeOffset=offset, SkipExpression=expr)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["SkipExpression"] = (
            self.SkipExpression.to_dict() if self.SkipExpression else None
        )
        return d


@dataclass
class EX_ComputedJump(KismetExpression):
    """Dynamically computed jump target offset."""

    CodeOffsetExpression: KismetExpression | None = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_ComputedJump

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_ComputedJump:
        expr = archive.read_expression()
        return cls(CodeOffsetExpression=expr)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["CodeOffsetExpression"] = (
            self.CodeOffsetExpression.to_dict() if self.CodeOffsetExpression else None
        )
        return d


@dataclass
class EX_PushExecutionFlow(KismetExpression):
    """Push the return address onto the execution flow stack."""

    PushingAddress: int = 0

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_PushExecutionFlow

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_PushExecutionFlow:
        addr = archive.read_u32()
        return cls(PushingAddress=addr)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["PushingAddress"] = self.PushingAddress
        return d


# Data-free expression: returns Token only
EX_PopExecutionFlow = make_simple_expression(EExprToken.EX_PopExecutionFlow)


@dataclass
class EX_PopExecutionFlowIfNot(KismetExpression):
    """Conditional execution flow pop: pop and jump when the boolean expression is false."""

    BooleanExpression: KismetExpression | None = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_PopExecutionFlowIfNot

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_PopExecutionFlowIfNot:
        expr = archive.read_expression()
        return cls(BooleanExpression=expr)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["BooleanExpression"] = (
            self.BooleanExpression.to_dict() if self.BooleanExpression else None
        )
        return d


# Data-free expression: returns Token only
EX_EndOfScript = make_simple_expression(EExprToken.EX_EndOfScript)


@dataclass
class EX_SkipOffsetConst(KismetExpressionT[int]):
    """Skip offset constant."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_SkipOffsetConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_SkipOffsetConst:
        return cls(Value=archive.read_u32())
