"""Kismet 赋值表达式。

包含 EX_Let 系列赋值指令的表达式子类。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive
    from uasset_read.kismet.property_pointer import FKismetPropertyPointer


@dataclass
class EX_LetBase(KismetExpression):
    """赋值表达式的抽象基类。"""

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
    """标准赋值表达式，包含属性指针。"""

    Property: FKismetPropertyPointer | None = None
    Variable: KismetExpression | None = None
    Assignment: KismetExpression | None = None

    @property
    def Token(self):
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
    """布尔类型赋值。"""

    @property
    def Token(self):
        return EExprToken.EX_LetBool


@dataclass
class EX_LetDelegate(EX_LetBase):
    """委托类型赋值。"""

    @property
    def Token(self):
        return EExprToken.EX_LetDelegate


@dataclass
class EX_LetMulticastDelegate(EX_LetBase):
    """多播委托类型赋值。"""

    @property
    def Token(self):
        return EExprToken.EX_LetMulticastDelegate


@dataclass
class EX_LetObj(EX_LetBase):
    """对象类型赋值。"""

    @property
    def Token(self):
        return EExprToken.EX_LetObj


@dataclass
class EX_LetWeakObjPtr(EX_LetBase):
    """弱对象指针赋值。"""

    @property
    def Token(self):
        return EExprToken.EX_LetWeakObjPtr


@dataclass
class EX_LetValueOnPersistentFrame(KismetExpression):
    """在持久化帧上设置值（用于循环变量/局部变量）。"""

    DestinationProperty: FKismetPropertyPointer | None = None
    AssignmentExpression: KismetExpression | None = None

    @property
    def Token(self):
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
