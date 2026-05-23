"""Kismet 表达式 — 函数调用与结束标记。

包含函数调用相关表达式（EX_FinalFunction / EX_CallMath / EX_VirtualFunction 等）
以及函数参数结束标记（EX_EndFunctionParms / EX_EndParmValue）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_EndParmValue(KismetExpression):
    """可选函数参数默认值的结束标记。"""

    @property
    def Token(self):
        return EExprToken.EX_EndParmValue


@dataclass
class EX_EndFunctionParms(KismetExpression):
    """函数调用参数列表的结束标记。"""

    @property
    def Token(self):
        return EExprToken.EX_EndFunctionParms


@dataclass
class EX_FinalFunction(KismetExpression):
    """预绑定函数调用（native/final function），带参数列表。"""

    StackNode: int = 0
    Parameters: list[KismetExpression] = field(default_factory=list)

    @property
    def Token(self):
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
    """静态纯函数调用（本地调用空间）。"""

    @property
    def Token(self):
        return EExprToken.EX_CallMath


@dataclass
class EX_LocalFinalFunction(EX_FinalFunction):
    """仅本地执行的 final 函数调用。"""

    @property
    def Token(self):
        return EExprToken.EX_LocalFinalFunction


@dataclass
class EX_VirtualFunction(KismetExpression):
    """虚函数调用，通过函数名查找。"""

    VirtualFunctionName: str = ""
    Parameters: list[KismetExpression] = field(default_factory=list)

    @property
    def Token(self):
        return EExprToken.EX_VirtualFunction

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_VirtualFunction:
        name = archive.xfer_string()
        archive.skip(1)
        params = archive.read_expression_array(EExprToken.EX_EndFunctionParms)
        return cls(VirtualFunctionName=name, Parameters=params)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Name"] = self.VirtualFunctionName
        d["ParamCount"] = len(self.Parameters) if self.Parameters else 0
        return d


@dataclass
class EX_LocalVirtualFunction(EX_VirtualFunction):
    """仅本地执行的虚函数调用。"""

    @property
    def Token(self):
        return EExprToken.EX_LocalVirtualFunction


@dataclass
class EX_CallMulticastDelegate(KismetExpression):
    """多播委托调用。"""

    StackNode: int = 0
    Delegate: Optional[KismetExpression] = None
    Parameters: list[KismetExpression] = field(default_factory=list)

    @property
    def Token(self):
        return EExprToken.EX_CallMulticastDelegate

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_CallMulticastDelegate:
        stack = archive.read_i32()
        delegate = archive.read_expression()
        params = archive.read_expression_array(EExprToken.EX_EndFunctionParms)
        return cls(StackNode=stack, Delegate=delegate, Parameters=params)
