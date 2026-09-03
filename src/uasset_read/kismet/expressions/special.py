"""
Kismet expression system -- special expressions.

Contains special expression types such as switch/instrumentation/constants/self-references.
Corresponding opcodes: EX_Return, EX_Assert, EX_SwitchValue, EX_InstrumentationEvent, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from uasset_read.kismet.expressions.base import (
    KismetExpression,
    KismetExpressionT,
    make_simple_expression,
)
from uasset_read.kismet.tokens import EExprToken, EScriptInstrumentationType
from uasset_read.kismet.value_types import FNameRef
from uasset_read.serializers.object_resources import PackageIndex

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class FKismetSwitchCase:
    """Switch case struct for EX_SwitchValue."""

    CaseIndexValueTerm: KismetExpression = None
    NextOffset: int = 0
    CaseTerm: KismetExpression = None

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> FKismetSwitchCase:
        case_idx = archive.read_expression()
        offset = archive.read_u32()
        case_term = archive.read_expression()
        return cls(CaseIndexValueTerm=case_idx, NextOffset=offset, CaseTerm=case_term)


@dataclass
class EX_Return(KismetExpression):
    """Return from function — reads return expression."""

    ReturnExpression: KismetExpression = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_Return

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_Return:
        expr = archive.read_expression()
        return cls(ReturnExpression=expr)


@dataclass
class EX_Assert(KismetExpression):
    """Assertion — reads line number, debug mode, and assert expression."""

    LineNumber: int = 0
    DebugMode: bool = False
    AssertExpression: KismetExpression = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_Assert

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_Assert:
        line = archive.read_u16()
        # ScriptSerialization.inl:597-603 — debug flag is uint8 (XFER(uint8)), NOT a 4-byte UBOOL.
        debug = archive.read_u8() != 0
        expr = archive.read_expression()
        return cls(LineNumber=line, DebugMode=debug, AssertExpression=expr)


@dataclass
class EX_NothingInt32(KismetExpressionT):
    """No operation with an int32 argument."""

    Value: int = 0

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_NothingInt32

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_NothingInt32:
        return cls(Value=archive.read_i32())


@dataclass
class EX_SwitchValue(KismetExpression):
    """Switch expression — evaluates index, matches cases, falls through to default."""

    EndGotoOffset: int = 0
    IndexTerm: KismetExpression = None
    Cases: list[FKismetSwitchCase] = None
    DefaultTerm: KismetExpression = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_SwitchValue

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_SwitchValue:
        num_cases = archive.read_u16()
        end_offset = archive.read_u32()
        index = archive.read_expression()
        cases = []
        for _ in range(num_cases):
            case = FKismetSwitchCase.from_archive(archive, name_map)
            cases.append(case)
        default = archive.read_expression()
        return cls(EndGotoOffset=end_offset, IndexTerm=index, Cases=cases, DefaultTerm=default)


@dataclass
class EX_InstrumentationEvent(KismetExpression):
    """Instrumentation event — reads event type and optional name."""

    EventType: EScriptInstrumentationType = EScriptInstrumentationType.None_
    EventName: Optional[str] = None
    EventNameRef: Optional[FNameRef] = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_InstrumentationEvent

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_InstrumentationEvent:
        evt_type = EScriptInstrumentationType(archive.read_u8())
        name = None
        name_ref = None
        if evt_type == EScriptInstrumentationType.InlineEvent:
            fname_ref = archive.xfer_fname()
            name = fname_ref.base_name
            name_ref = fname_ref
        return cls(EventType=evt_type, EventName=name, EventNameRef=name_ref)


# Data-free expression: returns Token only
EX_DeprecatedOp4A = make_simple_expression(EExprToken.EX_DeprecatedOp4A)
EX_Breakpoint = make_simple_expression(EExprToken.EX_Breakpoint)
EX_Tracepoint = make_simple_expression(EExprToken.EX_Tracepoint)
EX_WireTracepoint = make_simple_expression(EExprToken.EX_WireTracepoint)


@dataclass
class EX_FieldPathConst(KismetExpression):
    """FProperty constant — wraps a field path expression."""

    Value: KismetExpression = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_FieldPathConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_FieldPathConst:
        val = archive.read_expression()
        return cls(Value=val)


@dataclass
class EX_ObjectConst(KismetExpressionT):
    """Object constant — reads object reference index."""

    Value: int = 0
    ObjectRef: PackageIndex | None = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_ObjectConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_ObjectConst:
        obj_ref = archive.xfer_object_pointer()
        return cls(Value=obj_ref.index, ObjectRef=obj_ref)


@dataclass
class EX_NameConst(KismetExpressionT):
    """Name constant — reads FName index + number from name_map."""

    Value: str = ""
    NameRef: FNameRef | None = None

    @property
    def Token(self) -> EExprToken:
        return EExprToken.EX_NameConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_NameConst:
        fname_ref = archive.xfer_fname()
        return cls(Value=fname_ref.base_name, NameRef=fname_ref)
