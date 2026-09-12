"""Kismet expression -- type casts.

Contains type-cast related expressions (EX_Cast / EX_MetaCast / EX_DynamicCast, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uasset_read.kismet.expressions.base import KismetExpression, make_token_subclass
from uasset_read.kismet.tokens import EExprToken, ECastToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_CastBase(KismetExpression):
    """Abstract base class for cast expressions -- reads class pointer and target expression."""

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_CastBase:
        archive.xfer_object_pointer()
        archive.read_expression()
        return cls()


@dataclass
class EX_Cast(KismetExpression):
    """General type cast operator -- reads a conversion type byte followed by the target expression."""

    ConversionType: ECastToken = ECastToken.CST_ObjectToInterface

    Token = EExprToken.EX_Cast

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_Cast:
        conv = ECastToken(archive.read_u8())
        archive.read_expression()
        return cls(ConversionType=conv)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["ConversionType"] = self.ConversionType.name
        return d


# Token-only cast variants — share EX_CastBase serialization exactly.
EX_MetaCast = make_token_subclass(EX_CastBase, EExprToken.EX_MetaCast)
EX_DynamicCast = make_token_subclass(EX_CastBase, EExprToken.EX_DynamicCast)
EX_ObjToInterfaceCast = make_token_subclass(EX_CastBase, EExprToken.EX_ObjToInterfaceCast)
EX_CrossInterfaceCast = make_token_subclass(EX_CastBase, EExprToken.EX_CrossInterfaceCast)
EX_InterfaceToObjCast = make_token_subclass(EX_CastBase, EExprToken.EX_InterfaceToObjCast)
