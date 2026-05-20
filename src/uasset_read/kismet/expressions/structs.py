"""Kismet 表达式 — Struct 相关表达式。

包含 EX_StructConst、EX_EndStructConst、EX_PropertyConst、EX_BitFieldConst。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive
    from uasset_read.kismet.property_pointer import FKismetPropertyPointer


@dataclass
class EX_StructConst(KismetExpression):
    """An arbitrary UStruct constant (EX_StructConst, 0x2F)."""

    Struct: int = 0
    StructSize: int = 0
    Properties: list[KismetExpression] = field(default_factory=list)

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_StructConst

    @classmethod
    def from_archive(
        cls, archive: FKismetArchive, name_map: list[str]
    ) -> EX_StructConst:
        struct_idx = archive.read_i32()
        size = archive.read_u32()
        props = archive.read_expression_array(EExprToken.EX_EndStructConst)
        return cls(Struct=struct_idx, StructSize=size, Properties=props)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["Struct"] = self.Struct
        result["StructSize"] = self.StructSize
        result["Properties"] = [p.to_dict() for p in self.Properties]
        return result


@dataclass
class EX_EndStructConst(KismetExpression):
    """End of UStruct constant (EX_EndStructConst, 0x30)."""

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_EndStructConst


@dataclass
class EX_PropertyConst(KismetExpression):
    """FProperty constant (EX_PropertyConst, 0x33)."""

    Property: Optional[FKismetPropertyPointer] = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_PropertyConst

    @classmethod
    def from_archive(
        cls, archive: FKismetArchive, name_map: list[str]
    ) -> EX_PropertyConst:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        prop = FKismetPropertyPointer.from_archive(archive, name_map)
        return cls(Property=prop)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["Property"] = str(self.Property) if self.Property else None
        return result


@dataclass
class EX_BitFieldConst(KismetExpression):
    """Assign to a single bit, defined by an FProperty (EX_BitFieldConst, 0x11)."""

    InnerProperty: Optional[FKismetPropertyPointer] = None
    ConstValue: int = 0

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_BitFieldConst

    @classmethod
    def from_archive(
        cls, archive: FKismetArchive, name_map: list[str]
    ) -> EX_BitFieldConst:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        prop = FKismetPropertyPointer.from_archive(archive, name_map)
        val = archive.read_u8()
        return cls(InnerProperty=prop, ConstValue=val)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["InnerProperty"] = str(self.InnerProperty) if self.InnerProperty else None
        result["ConstValue"] = self.ConstValue
        return result
