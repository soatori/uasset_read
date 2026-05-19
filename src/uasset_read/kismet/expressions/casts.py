"""Kismet 表达式 — 类型转换。

包含类型转换相关表达式（EX_Cast / EX_MetaCast / EX_DynamicCast 等）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.tokens import EExprToken, ECastToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_CastBase(KismetExpression):
    """转换表达式的抽象基类 — 读取类指针和目标表达式。"""

    ClassPtr: int = 0
    Target: Optional[KismetExpression] = None

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_CastBase:
        cls_ptr = archive.read_i32()
        target = archive.read_expression()
        return cls(ClassPtr=cls_ptr, Target=target)


@dataclass
class EX_Cast(KismetExpression):
    """通用类型转换操作符 — 读取转换类型字节后跟目标表达式。"""

    ConversionType: ECastToken = ECastToken.CST_ObjectToInterface
    Target: Optional[KismetExpression] = None

    @property
    def Token(self):
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
    """元类转换（metaclass cast）。"""

    @property
    def Token(self):
        return EExprToken.EX_MetaCast


@dataclass
class EX_DynamicCast(EX_CastBase):
    """安全动态类转换。"""

    @property
    def Token(self):
        return EExprToken.EX_DynamicCast


@dataclass
class EX_ObjToInterfaceCast(EX_CastBase):
    """对象引用转原生接口。"""

    @property
    def Token(self):
        return EExprToken.EX_ObjToInterfaceCast


@dataclass
class EX_CrossInterfaceCast(EX_CastBase):
    """接口转接口转换。"""

    @property
    def Token(self):
        return EExprToken.EX_CrossInterfaceCast


@dataclass
class EX_InterfaceToObjCast(EX_CastBase):
    """接口引用转对象。"""

    @property
    def Token(self):
        return EExprToken.EX_InterfaceToObjCast
