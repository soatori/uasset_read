"""Kismet 控制流表达式。

包含跳转、条件分支、执行流栈操作等控制流相关的表达式子类。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from uasset_read.kismet.expressions.base import KismetExpression, KismetExpressionT
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_Jump(KismetExpression):
    """无条件跳转到指定代码偏移量。"""

    CodeOffset: int = 0

    @property
    def Token(self):
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
    """条件跳转：如果布尔表达式为假则跳转。"""

    BooleanExpression: KismetExpression | None = None

    @property
    def Token(self):
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
    """跳过一段表达式代码块。"""

    SkipExpression: KismetExpression | None = None

    @property
    def Token(self):
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
    """动态计算跳转目标偏移量。"""

    CodeOffsetExpression: KismetExpression | None = None

    @property
    def Token(self):
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
    """将返回地址压入执行流栈。"""

    PushingAddress: int = 0

    @property
    def Token(self):
        return EExprToken.EX_PushExecutionFlow

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_PushExecutionFlow:
        addr = archive.read_u32()
        return cls(PushingAddress=addr)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["PushingAddress"] = self.PushingAddress
        return d


@dataclass
class EX_PopExecutionFlow(KismetExpression):
    """从执行流栈弹出并跳转到该地址。"""

    @property
    def Token(self):
        return EExprToken.EX_PopExecutionFlow


@dataclass
class EX_PopExecutionFlowIfNot(KismetExpression):
    """条件弹出执行流：布尔表达式为假时弹出并跳转。"""

    BooleanExpression: KismetExpression | None = None

    @property
    def Token(self):
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


@dataclass
class EX_EndOfScript(KismetExpression):
    """脚本结束标记。"""

    @property
    def Token(self):
        return EExprToken.EX_EndOfScript


@dataclass
class EX_SkipOffsetConst(KismetExpressionT[int]):
    """Skip 偏移量常量。"""

    @property
    def Token(self):
        return EExprToken.EX_SkipOffsetConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_SkipOffsetConst:
        return cls(Value=archive.read_u32())
