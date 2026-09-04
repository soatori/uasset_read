from __future__ import annotations

"""
Kismet expression subclasses — Variable reference expressions.

All share FKismetPropertyPointer for the Variable field.
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uasset_read.kismet.expressions.base import KismetExpression, make_token_subclass
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.property_pointer import FKismetPropertyPointer
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_VariableBase(KismetExpression):
    """Abstract base for variable expressions."""

    Variable: FKismetPropertyPointer | None = None

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_VariableBase:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        var = FKismetPropertyPointer.from_archive(archive, name_map)
        return cls(Variable=var)


EX_LocalVariable = make_token_subclass(EX_VariableBase, EExprToken.EX_LocalVariable)
EX_InstanceVariable = make_token_subclass(EX_VariableBase, EExprToken.EX_InstanceVariable)
EX_DefaultVariable = make_token_subclass(EX_VariableBase, EExprToken.EX_DefaultVariable)
EX_LocalOutVariable = make_token_subclass(EX_VariableBase, EExprToken.EX_LocalOutVariable)
EX_ClassSparseDataVariable = make_token_subclass(EX_VariableBase, EExprToken.EX_ClassSparseDataVariable)
