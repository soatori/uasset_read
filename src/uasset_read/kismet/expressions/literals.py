"""
Kismet expression subclasses — Numeric and boolean literal constants.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uasset_read.kismet.expressions.base import KismetExpression, KismetExpressionT
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_IntConst(KismetExpressionT[int]):
    @property
    def Token(self): return EExprToken.EX_IntConst
    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_IntConst:
        return cls(Value=archive.read_i32())


@dataclass
class EX_FloatConst(KismetExpressionT[float]):
    @property
    def Token(self): return EExprToken.EX_FloatConst
    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_FloatConst:
        return cls(Value=archive.read_f32())


@dataclass
class EX_ByteConst(KismetExpressionT[int]):
    @property
    def Token(self): return EExprToken.EX_ByteConst
    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_ByteConst:
        return cls(Value=archive.read_u8())


@dataclass
class EX_IntConstByte(KismetExpressionT[int]):
    @property
    def Token(self): return EExprToken.EX_IntConstByte
    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_IntConstByte:
        return cls(Value=archive.read_u8())


@dataclass
class EX_Int64Const(KismetExpressionT[int]):
    @property
    def Token(self): return EExprToken.EX_Int64Const
    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_Int64Const:
        return cls(Value=archive.read_i64())


@dataclass
class EX_UInt64Const(KismetExpressionT[int]):
    @property
    def Token(self): return EExprToken.EX_UInt64Const
    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_UInt64Const:
        return cls(Value=archive.read_u64())


@dataclass
class EX_DoubleConst(KismetExpressionT[float]):
    @property
    def Token(self): return EExprToken.EX_DoubleConst
    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_DoubleConst:
        return cls(Value=archive.read_f64())


@dataclass
class EX_IntZero(KismetExpression):
    @property
    def Token(self): return EExprToken.EX_IntZero


@dataclass
class EX_IntOne(KismetExpression):
    @property
    def Token(self): return EExprToken.EX_IntOne


@dataclass
class EX_True(KismetExpression):
    @property
    def Token(self): return EExprToken.EX_True


@dataclass
class EX_False(KismetExpression):
    @property
    def Token(self): return EExprToken.EX_False
