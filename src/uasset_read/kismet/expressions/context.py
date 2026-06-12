from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive
    from uasset_read.kismet.property_pointer import FKismetPropertyPointer


@dataclass
class EX_Context(KismetExpression):
    ObjectExpression: KismetExpression = None
    Offset: int = 0
    RValuePointer: FKismetPropertyPointer = None
    ContextExpression: KismetExpression = None

    @property
    def Token(self): return EExprToken.EX_Context

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_Context:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer
        obj = archive.read_expression()
        offset = archive.read_u32()
        rvalue = FKismetPropertyPointer.from_archive(archive, name_map)
        ctx = archive.read_expression()
        return cls(ObjectExpression=obj, Offset=offset, RValuePointer=rvalue, ContextExpression=ctx)


@dataclass
class EX_Context_FailSilent(EX_Context):
    @property
    def Token(self): return EExprToken.EX_Context_FailSilent


@dataclass
class EX_ClassContext(EX_Context):
    @property
    def Token(self): return EExprToken.EX_ClassContext


@dataclass
class EX_InterfaceContext(KismetExpression):
    InterfaceValue: KismetExpression = None

    @property
    def Token(self): return EExprToken.EX_InterfaceContext

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_InterfaceContext:
        val = archive.read_expression()
        return cls(InterfaceValue=val)


@dataclass
class EX_StructMemberContext(KismetExpression):
    Property: FKismetPropertyPointer = None
    StructExpression: KismetExpression = None

    @property
    def Token(self): return EExprToken.EX_StructMemberContext

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_StructMemberContext:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer
        prop = FKismetPropertyPointer.from_archive(archive, name_map)
        expr = archive.read_expression()
        return cls(Property=prop, StructExpression=expr)
