from __future__ import annotations

"""Kismet expression -- type casts.

Contains type-cast related expressions (EX_Cast / EX_MetaCast / EX_DynamicCast, etc.).
"""


from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.tokens import EExprToken, ECastToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_CastBase(KismetExpression):
    """Abstract base class for cast expressions -- reads class pointer and target expression."""

    ClassPtr: int = 0
    Target: Optional[KismetExpression] = None

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_CastBase:
        cls_ptr = archive.read_i32()
        target = archive.read_expression()
        return cls(ClassPtr=cls_ptr, Target=target)


@dataclass
class EX_Cast(KismetExpression):
    """General type cast operator -- reads a conversion type byte followed by the target expression."""

    ConversionType: ECastToken = ECastToken.CST_ObjectToInterface
    Target: Optional[KismetExpression] = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_Cast

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_Cast:
        conv = ECastToken(archive.read_u8())
        target = archive.read_expression()
        return cls(ConversionType=conv, Target=target)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["ConversionType"] = self.ConversionType.name
        return d


@dataclass
class EX_MetaCast(EX_CastBase):
    """Metaclass cast."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_MetaCast


@dataclass
class EX_DynamicCast(EX_CastBase):
    """Safe dynamic class cast."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_DynamicCast


@dataclass
class EX_ObjToInterfaceCast(EX_CastBase):
    """Object reference to native interface."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_ObjToInterfaceCast


@dataclass
class EX_CrossInterfaceCast(EX_CastBase):
    """Interface-to-interface cast."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_CrossInterfaceCast


@dataclass
class EX_InterfaceToObjCast(EX_CastBase):
    """Interface reference to object."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_InterfaceToObjCast
