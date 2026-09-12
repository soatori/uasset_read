from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uasset_read.kismet.expressions.base import KismetExpression, make_token_subclass
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_Context(KismetExpression):
    Token = EExprToken.EX_Context

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_Context:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        archive.read_expression()
        archive.read_u32()
        FKismetPropertyPointer.from_archive(archive)
        archive.read_expression()
        return cls()


# Token-only EX_Context variants — share EX_Context serialization exactly.
EX_Context_FailSilent = make_token_subclass(EX_Context, EExprToken.EX_Context_FailSilent)
EX_ClassContext = make_token_subclass(EX_Context, EExprToken.EX_ClassContext)


@dataclass
class EX_InterfaceContext(KismetExpression):
    Token = EExprToken.EX_InterfaceContext

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_InterfaceContext:
        archive.read_expression()
        return cls()


@dataclass
class EX_StructMemberContext(KismetExpression):
    Token = EExprToken.EX_StructMemberContext

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_StructMemberContext:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        FKismetPropertyPointer.from_archive(archive)
        archive.read_expression()
        return cls()
