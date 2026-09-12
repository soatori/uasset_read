from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uasset_read.kismet.expressions.base import KismetExpression, make_simple_expression
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_SetArray(KismetExpression):
    """SetArray — version-dependent: with CHANGE_SETARRAY_BYTECODE has AssigningProperty."""

    Token = EExprToken.EX_SetArray

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_SetArray:
        # UE5's post-VER_UE4_CHANGE_SETARRAY_BYTECODE layout serializes the
        # array target as an expression, not as a bare FProperty pointer.
        archive.read_expression()
        archive.read_expression_array(EExprToken.EX_EndArray)
        return cls()


# Data-free expression: returns Token only
EX_EndArray = make_simple_expression(EExprToken.EX_EndArray)


@dataclass
class EX_SetMap(KismetExpression):
    Token = EExprToken.EX_SetMap

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_SetMap:
        archive.read_expression()
        archive.read_i32()  # ScriptSerialization.inl:531-534: int32 element count
        archive.read_expression_array(EExprToken.EX_EndMap)
        return cls()


# Data-free expression: returns Token only
EX_EndMap = make_simple_expression(EExprToken.EX_EndMap)


@dataclass
class EX_SetSet(KismetExpression):
    Num: int = 0

    Token = EExprToken.EX_SetSet

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_SetSet:
        archive.read_expression()
        num = archive.read_i32()  # ScriptSerialization.inl:526-529: int32 element count
        archive.read_expression_array(EExprToken.EX_EndSet)
        return cls(Num=num)


# Data-free expression: returns Token only
EX_EndSet = make_simple_expression(EExprToken.EX_EndSet)


@dataclass
class EX_ArrayConst(KismetExpression):
    Token = EExprToken.EX_ArrayConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_ArrayConst:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        FKismetPropertyPointer.from_archive(archive)
        archive.read_i32()  # ScriptSerialization.inl:536-541: int32 element count
        archive.read_expression_array(EExprToken.EX_EndArrayConst)
        return cls()


# Data-free expression: returns Token only
EX_EndArrayConst = make_simple_expression(EExprToken.EX_EndArrayConst)


@dataclass
class EX_MapConst(KismetExpression):
    Token = EExprToken.EX_MapConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_MapConst:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        FKismetPropertyPointer.from_archive(archive)
        FKismetPropertyPointer.from_archive(archive)
        archive.read_i32()
        archive.read_expression_array(EExprToken.EX_EndMapConst)
        return cls()


# Data-free expression: returns Token only
EX_EndMapConst = make_simple_expression(EExprToken.EX_EndMapConst)


@dataclass
class EX_SetConst(KismetExpression):
    Token = EExprToken.EX_SetConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_SetConst:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        FKismetPropertyPointer.from_archive(archive)
        archive.read_i32()  # ScriptSerialization.inl:543-548: int32 element count
        archive.read_expression_array(EExprToken.EX_EndSetConst)
        return cls()


# Data-free expression: returns Token only
EX_EndSetConst = make_simple_expression(EExprToken.EX_EndSetConst)


@dataclass
class EX_ArrayGetByRef(KismetExpression):
    Token = EExprToken.EX_ArrayGetByRef

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_ArrayGetByRef:
        archive.read_expression()
        archive.read_expression()
        return cls()
