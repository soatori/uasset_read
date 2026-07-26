from __future__ import annotations

"""Kismet assignment expressions.

Contains expression subclasses for the EX_Let family of assignment instructions.
"""


from dataclasses import dataclass
from typing import TYPE_CHECKING

from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive
    from uasset_read.kismet.property_pointer import FKismetPropertyPointer


@dataclass
class EX_LetBase(KismetExpression):
    """Abstract base class for assignment expressions."""

    Variable: KismetExpression | None = None
    Assignment: KismetExpression | None = None

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_LetBase:
        var = archive.read_expression()
        assign = archive.read_expression()
        return cls(Variable=var, Assignment=assign)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Variable"] = self.Variable.to_dict() if self.Variable else None
        d["Assignment"] = self.Assignment.to_dict() if self.Assignment else None
        return d


@dataclass
class EX_Let(KismetExpression):
    """Standard assignment expression with a property pointer."""

    Property: FKismetPropertyPointer | None = None
    Variable: KismetExpression | None = None
    Assignment: KismetExpression | None = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_Let

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_Let:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        prop = FKismetPropertyPointer.from_archive(archive, name_map)
        var = archive.read_expression()
        assign = archive.read_expression()
        return cls(Property=prop, Variable=var, Assignment=assign)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Property"] = self.Property.to_dict() if self.Property else None
        d["Variable"] = self.Variable.to_dict() if self.Variable else None
        d["Assignment"] = self.Assignment.to_dict() if self.Assignment else None
        return d


@dataclass
class EX_LetBool(EX_LetBase):
    """Boolean type assignment."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_LetBool


@dataclass
class EX_LetDelegate(EX_LetBase):
    """Delegate type assignment."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_LetDelegate


@dataclass
class EX_LetMulticastDelegate(EX_LetBase):
    """Multicast delegate type assignment."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_LetMulticastDelegate


@dataclass
class EX_LetObj(EX_LetBase):
    """Object type assignment."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_LetObj


@dataclass
class EX_LetWeakObjPtr(EX_LetBase):
    """Weak object pointer assignment."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_LetWeakObjPtr


@dataclass
class EX_LetValueOnPersistentFrame(KismetExpression):
    """Set value on persistent frame (used for loop variables / local variables)."""

    DestinationProperty: FKismetPropertyPointer | None = None
    AssignmentExpression: KismetExpression | None = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_LetValueOnPersistentFrame

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_LetValueOnPersistentFrame:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        prop = FKismetPropertyPointer.from_archive(archive, name_map)
        expr = archive.read_expression()
        return cls(DestinationProperty=prop, AssignmentExpression=expr)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["DestinationProperty"] = (
            self.DestinationProperty.to_dict() if self.DestinationProperty else None
        )
        d["AssignmentExpression"] = (
            self.AssignmentExpression.to_dict() if self.AssignmentExpression else None
        )
        return d
