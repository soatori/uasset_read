"""
Kismet expression subclasses — Variable reference expressions.

All share FKismetPropertyPointer for the Variable field.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.property_pointer import FKismetPropertyPointer
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_VariableBase(KismetExpression):
    """Abstract base for variable expressions."""
    Variable: FKismetPropertyPointer = None

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_VariableBase:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer
        var = FKismetPropertyPointer.from_archive(archive, name_map)
        return cls(Variable=var)


@dataclass
class EX_LocalVariable(EX_VariableBase):
    @property
    def Token(self): return EExprToken.EX_LocalVariable


@dataclass
class EX_InstanceVariable(EX_VariableBase):
    @property
    def Token(self): return EExprToken.EX_InstanceVariable


@dataclass
class EX_DefaultVariable(EX_VariableBase):
    @property
    def Token(self): return EExprToken.EX_DefaultVariable


@dataclass
class EX_LocalOutVariable(EX_VariableBase):
    @property
    def Token(self): return EExprToken.EX_LocalOutVariable


@dataclass
class EX_ClassSparseDataVariable(EX_VariableBase):
    @property
    def Token(self): return EExprToken.EX_ClassSparseDataVariable
