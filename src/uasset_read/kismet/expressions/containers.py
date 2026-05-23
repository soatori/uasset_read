from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.tokens import EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive
    from uasset_read.kismet.property_pointer import FKismetPropertyPointer


@dataclass
class EX_SetArray(KismetExpression):
    """SetArray — version-dependent: with CHANGE_SETARRAY_BYTECODE has AssigningProperty."""
    AssigningProperty: Optional[FKismetPropertyPointer] = None
    ArrayInnerProp: Optional[FKismetPropertyPointer] = None
    Elements: list[KismetExpression] = None

    @property
    def Token(self): return EExprToken.EX_SetArray

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_SetArray:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer
        # In UE5, SetArray reads a property then elements
        prop = FKismetPropertyPointer.from_archive(archive, name_map)
        elements = archive.read_expression_array(EExprToken.EX_EndArray)
        return cls(ArrayInnerProp=prop, Elements=elements)


@dataclass
class EX_EndArray(KismetExpression):
    @property
    def Token(self): return EExprToken.EX_EndArray


@dataclass
class EX_SetMap(KismetExpression):
    MapProperty: KismetExpression = None
    Elements: list[KismetExpression] = None

    @property
    def Token(self): return EExprToken.EX_SetMap

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_SetMap:
        prop = archive.read_expression()
        elements = archive.read_expression_array(EExprToken.EX_EndMap)
        return cls(MapProperty=prop, Elements=elements)


@dataclass
class EX_EndMap(KismetExpression):
    @property
    def Token(self): return EExprToken.EX_EndMap


@dataclass
class EX_SetSet(KismetExpression):
    SetProperty: KismetExpression = None
    Elements: list[KismetExpression] = None

    @property
    def Token(self): return EExprToken.EX_SetSet

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_SetSet:
        prop = archive.read_expression()
        elements = archive.read_expression_array(EExprToken.EX_EndSet)
        return cls(SetProperty=prop, Elements=elements)


@dataclass
class EX_EndSet(KismetExpression):
    @property
    def Token(self): return EExprToken.EX_EndSet


@dataclass
class EX_ArrayConst(KismetExpression):
    InnerProperty: FKismetPropertyPointer = None
    Elements: list[KismetExpression] = None

    @property
    def Token(self): return EExprToken.EX_ArrayConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_ArrayConst:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer
        prop = FKismetPropertyPointer.from_archive(archive, name_map)
        elements = archive.read_expression_array(EExprToken.EX_EndArrayConst)
        return cls(InnerProperty=prop, Elements=elements)


@dataclass
class EX_EndArrayConst(KismetExpression):
    @property
    def Token(self): return EExprToken.EX_EndArrayConst


@dataclass
class EX_MapConst(KismetExpression):
    KeyProperty: FKismetPropertyPointer = None
    ValueProperty: FKismetPropertyPointer = None
    Elements: list[KismetExpression] = None

    @property
    def Token(self): return EExprToken.EX_MapConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_MapConst:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer
        key_prop = FKismetPropertyPointer.from_archive(archive, name_map)
        val_prop = FKismetPropertyPointer.from_archive(archive, name_map)
        elements = archive.read_expression_array(EExprToken.EX_EndMapConst)
        return cls(KeyProperty=key_prop, ValueProperty=val_prop, Elements=elements)


@dataclass
class EX_EndMapConst(KismetExpression):
    @property
    def Token(self): return EExprToken.EX_EndMapConst


@dataclass
class EX_SetConst(KismetExpression):
    InnerProperty: FKismetPropertyPointer = None
    Elements: list[KismetExpression] = None

    @property
    def Token(self): return EExprToken.EX_SetConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_SetConst:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer
        prop = FKismetPropertyPointer.from_archive(archive, name_map)
        elements = archive.read_expression_array(EExprToken.EX_EndSetConst)
        return cls(InnerProperty=prop, Elements=elements)


@dataclass
class EX_EndSetConst(KismetExpression):
    @property
    def Token(self): return EExprToken.EX_EndSetConst


@dataclass
class EX_ArrayGetByRef(KismetExpression):
    ArrayVariable: KismetExpression = None
    ArrayIndex: KismetExpression = None

    @property
    def Token(self): return EExprToken.EX_ArrayGetByRef

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_ArrayGetByRef:
        arr = archive.read_expression()
        idx = archive.read_expression()
        return cls(ArrayVariable=arr, ArrayIndex=idx)
