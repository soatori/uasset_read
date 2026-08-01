from __future__ import annotations

"""Kismet expression -- function calls and end markers.

Contains function call related expressions (EX_FinalFunction / EX_CallMath / EX_VirtualFunction, etc.)
as well as function parameter end markers (EX_EndFunctionParms / EX_EndParmValue).
"""


from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from uasset_read.kismet.expressions.base import KismetExpression, make_simple_expression
from uasset_read.kismet.tokens import EExprToken
from uasset_read.kismet.value_types import FNameRef

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


# Data-free expression: returns Token only
EX_EndParmValue = make_simple_expression(EExprToken.EX_EndParmValue)
EX_EndFunctionParms = make_simple_expression(EExprToken.EX_EndFunctionParms)


@dataclass
class EX_FinalFunction(KismetExpression):
    """Pre-bound function call (native/final function) with a parameter list."""

    StackNode: int = 0
    Parameters: list[KismetExpression] = field(default_factory=list)

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_FinalFunction

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_FinalFunction:
        stack = archive.read_i32()
        params = archive.read_expression_array(EExprToken.EX_EndFunctionParms)
        return cls(StackNode=stack, Parameters=params)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["StackNode"] = self.StackNode
        d["ParamCount"] = len(self.Parameters) if self.Parameters else 0
        return d


@dataclass
class EX_CallMath(EX_FinalFunction):
    """Static pure function call (local call space)."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_CallMath


@dataclass
class EX_LocalFinalFunction(EX_FinalFunction):
    """Locally executed final function call."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_LocalFinalFunction


@dataclass
class EX_VirtualFunction(KismetExpression):
    """Virtual function call, resolved by function name."""

    VirtualFunctionName: str = ""
    VirtualFunctionNameRef: FNameRef | None = None
    Parameters: list[KismetExpression] = field(default_factory=list)

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_VirtualFunction

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_VirtualFunction:
        fname_ref = archive.xfer_fname()
        params = archive.read_expression_array(EExprToken.EX_EndFunctionParms)
        return cls(
            VirtualFunctionName=fname_ref.base_name,
            VirtualFunctionNameRef=fname_ref,
            Parameters=params,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Name"] = self.VirtualFunctionName
        d["ParamCount"] = len(self.Parameters) if self.Parameters else 0
        return d


@dataclass
class EX_LocalVirtualFunction(EX_VirtualFunction):
    """Locally executed virtual function call."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_LocalVirtualFunction


@dataclass
class EX_CallMulticastDelegate(KismetExpression):
    """Multicast delegate call."""

    StackNode: int = 0
    Delegate: Optional[KismetExpression] = None
    Parameters: list[KismetExpression] = field(default_factory=list)

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_CallMulticastDelegate

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_CallMulticastDelegate:
        stack = archive.read_i32()
        delegate = archive.read_expression()
        params = archive.read_expression_array(EExprToken.EX_EndFunctionParms)
        return cls(StackNode=stack, Delegate=delegate, Parameters=params)
