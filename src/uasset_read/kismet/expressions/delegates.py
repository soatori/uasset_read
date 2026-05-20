"""Kismet 表达式 — Delegate 相关表达式。

包含 EX_AddMulticastDelegate、EX_ClearMulticastDelegate、EX_BindDelegate、
EX_RemoveMulticastDelegate、EX_InstanceDelegate。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_AddMulticastDelegate(KismetExpression):
    """Adds a delegate to a multicast delegate's targets (EX_AddMulticastDelegate, 0x5C)."""

    Delegate: Optional[KismetExpression] = None
    DelegateToAdd: Optional[KismetExpression] = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_AddMulticastDelegate

    @classmethod
    def from_archive(
        cls, archive: FKismetArchive, name_map: list[str]
    ) -> EX_AddMulticastDelegate:
        d = archive.read_expression()
        d_add = archive.read_expression()
        return cls(Delegate=d, DelegateToAdd=d_add)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["Delegate"] = self.Delegate.to_dict() if self.Delegate else None
        result["DelegateToAdd"] = self.DelegateToAdd.to_dict() if self.DelegateToAdd else None
        return result


@dataclass
class EX_ClearMulticastDelegate(KismetExpression):
    """Clears all delegates in a multicast target (EX_ClearMulticastDelegate, 0x5D)."""

    DelegateToClear: Optional[KismetExpression] = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_ClearMulticastDelegate

    @classmethod
    def from_archive(
        cls, archive: FKismetArchive, name_map: list[str]
    ) -> EX_ClearMulticastDelegate:
        d = archive.read_expression()
        return cls(DelegateToClear=d)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["DelegateToClear"] = self.DelegateToClear.to_dict() if self.DelegateToClear else None
        return result


@dataclass
class EX_BindDelegate(KismetExpression):
    """Bind object and name to delegate (EX_BindDelegate, 0x61)."""

    FunctionName: str = ""
    Delegate: Optional[KismetExpression] = None
    ObjectTerm: Optional[KismetExpression] = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_BindDelegate

    @classmethod
    def from_archive(
        cls, archive: FKismetArchive, name_map: list[str]
    ) -> EX_BindDelegate:
        name = archive.xfer_string()
        archive.skip(1)
        d = archive.read_expression()
        obj = archive.read_expression()
        return cls(FunctionName=name, Delegate=d, ObjectTerm=obj)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["FunctionName"] = self.FunctionName
        result["Delegate"] = self.Delegate.to_dict() if self.Delegate else None
        result["ObjectTerm"] = self.ObjectTerm.to_dict() if self.ObjectTerm else None
        return result


@dataclass
class EX_RemoveMulticastDelegate(KismetExpression):
    """Remove a delegate from a multicast delegate's targets (EX_RemoveMulticastDelegate, 0x62)."""

    Delegate: Optional[KismetExpression] = None
    DelegateToAdd: Optional[KismetExpression] = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_RemoveMulticastDelegate

    @classmethod
    def from_archive(
        cls, archive: FKismetArchive, name_map: list[str]
    ) -> EX_RemoveMulticastDelegate:
        d = archive.read_expression()
        d_add = archive.read_expression()
        return cls(Delegate=d, DelegateToAdd=d_add)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["Delegate"] = self.Delegate.to_dict() if self.Delegate else None
        result["DelegateToAdd"] = self.DelegateToAdd.to_dict() if self.DelegateToAdd else None
        return result


@dataclass
class EX_InstanceDelegate(KismetExpression):
    """Const reference to a delegate or normal function object (EX_InstanceDelegate, 0x4B)."""

    FunctionName: str = ""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_InstanceDelegate

    @classmethod
    def from_archive(
        cls, archive: FKismetArchive, name_map: list[str]
    ) -> EX_InstanceDelegate:
        name = archive.xfer_string()
        archive.skip(1)
        return cls(FunctionName=name)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["FunctionName"] = self.FunctionName
        return result
