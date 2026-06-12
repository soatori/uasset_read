"""
Kismet 表达式系统 — 特殊表达式。

包含 switch/instrumentation/常量/自引用等特殊表达式类型。
对应 EX_Return, EX_Assert, EX_SwitchValue, EX_InstrumentationEvent 等。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from uasset_read.kismet.expressions.base import KismetExpression, KismetExpressionT
from uasset_read.kismet.tokens import EExprToken, EScriptInstrumentationType

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive
    from uasset_read.kismet.property_pointer import FKismetPropertyPointer


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
    def Token(self):
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
    def Token(self):
        return EExprToken.EX_Assert

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_Assert:
        line = archive.read_u16()
        debug = archive.read_bool()
        expr = archive.read_expression()
        return cls(LineNumber=line, DebugMode=debug, AssertExpression=expr)


@dataclass
class EX_Nothing(KismetExpression):
    """No operation."""

    @property
    def Token(self):
        return EExprToken.EX_Nothing


@dataclass
class EX_NothingInt32(KismetExpressionT[int]):
    """No operation with an int32 argument."""

    Value: int = 0

    @property
    def Token(self):
        return EExprToken.EX_NothingInt32

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_NothingInt32:
        return cls(Value=archive.read_i32())


@dataclass
class EX_Self(KismetExpression):
    """Self object reference."""

    @property
    def Token(self):
        return EExprToken.EX_Self


@dataclass
class EX_NoObject(KismetExpression):
    """Null object reference."""

    @property
    def Token(self):
        return EExprToken.EX_NoObject


@dataclass
class EX_NoInterface(KismetExpression):
    """Null interface reference."""

    @property
    def Token(self):
        return EExprToken.EX_NoInterface


@dataclass
class EX_SwitchValue(KismetExpression):
    """Switch expression — evaluates index, matches cases, falls through to default."""

    EndGotoOffset: int = 0
    IndexTerm: KismetExpression = None
    Cases: list[FKismetSwitchCase] = None
    DefaultTerm: KismetExpression = None

    @property
    def Token(self):
        return EExprToken.EX_SwitchValue

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_SwitchValue:
        end_offset = archive.read_u32()
        index = archive.read_expression()
        case_count = archive.read_u32()
        cases = []
        for _ in range(case_count):
            case = FKismetSwitchCase.from_archive(archive, name_map)
            cases.append(case)
        default = archive.read_expression()
        return cls(EndGotoOffset=end_offset, IndexTerm=index, Cases=cases, DefaultTerm=default)


@dataclass
class EX_InstrumentationEvent(KismetExpression):
    """Instrumentation event — reads event type and optional name."""

    EventType: EScriptInstrumentationType = EScriptInstrumentationType.None_
    EventName: Optional[str] = None

    @property
    def Token(self):
        return EExprToken.EX_InstrumentationEvent

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_InstrumentationEvent:
        evt_type = EScriptInstrumentationType(archive.read_u8())
        name = None
        if evt_type not in (
            EScriptInstrumentationType.Entry,
            EScriptInstrumentationType.Exit,
            EScriptInstrumentationType.PureEntry,
            EScriptInstrumentationType.PureExit,
        ):
            pass  # some types have no name
        else:
            name = archive.xfer_string()
            archive.skip(1)
        return cls(EventType=evt_type, EventName=name)


@dataclass
class EX_DeprecatedOp4A(KismetExpression):
    """Deprecated opcode 0x4A."""

    @property
    def Token(self):
        return EExprToken.EX_DeprecatedOp4A


@dataclass
class EX_Breakpoint(KismetExpression):
    """Breakpoint (editor only, else EX_Nothing)."""

    @property
    def Token(self):
        return EExprToken.EX_Breakpoint


@dataclass
class EX_Tracepoint(KismetExpression):
    """Tracepoint (editor only)."""

    @property
    def Token(self):
        return EExprToken.EX_Tracepoint


@dataclass
class EX_WireTracepoint(KismetExpression):
    """Wire tracepoint (editor only)."""

    @property
    def Token(self):
        return EExprToken.EX_WireTracepoint


@dataclass
class EX_FieldPathConst(KismetExpression):
    """FProperty constant — wraps a field path expression."""

    Value: KismetExpression = None

    @property
    def Token(self):
        return EExprToken.EX_FieldPathConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_FieldPathConst:
        val = archive.read_expression()
        return cls(Value=val)


@dataclass
class EX_ObjectConst(KismetExpressionT[int]):
    """Object constant — reads object reference index."""

    Value: int = 0

    @property
    def Token(self):
        return EExprToken.EX_ObjectConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_ObjectConst:
        return cls(Value=archive.read_i32())


@dataclass
class EX_NameConst(KismetExpressionT[str]):
    """Name constant — reads FName index + number from name_map."""

    Value: str = ""

    @property
    def Token(self):
        return EExprToken.EX_NameConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_NameConst:
        # Read FName: index + number
        idx = archive.read_u32()
        num = archive.read_u32()
        name = archive.resolve_fname(idx, num)
        return cls(Value=name)


@dataclass
class EX_Unknown6E(KismetExpressionT[bytes]):
    """Game-specific opcode 0x6E — placeholder that reads remaining bytecode as raw bytes."""

    Value: bytes = b""

    @property
    def Token(self):
        return EExprToken.EX_6E

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_Unknown6E:
        # 0x6E 格式未知，读取单个字节并回退（交由 tolerant 模式继续解析）
        archive.seek(archive.tell() - 1)  # 回退到 opcode 位置
        return cls(Value=b"")


@dataclass
class EX_Unknown6F(KismetExpressionT[bytes]):
    """Game-specific opcode 0x6F — placeholder that reads remaining bytecode as raw bytes."""

    Value: bytes = b""

    @property
    def Token(self):
        return EExprToken.EX_6F

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_Unknown6F:
        # 0x6F 格式未知，读取单个字节并回退（交由 tolerant 模式继续解析）
        archive.seek(archive.tell() - 1)  # 回退到 opcode 位置
        return cls(Value=b"")


@dataclass
class EX_MaxSentinel(KismetExpression):
    """EX_Max (0xFF) 哨兵值 — 标记脚本结束，与 EX_EndOfScript 行为相同。

    在 UE 蓝图中，0xFF 是 EExprToken 枚举的上限哨兵，不是有效操作码。
    出现在字节码末尾 padding 或未初始化数据中。
    将其视为脚本结束标记，避免 tolerant 模式逐字节跳过导致组合爆炸。
    """

    @property
    def Token(self):
        return EExprToken.EX_Max

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_MaxSentinel:
        # EX_Max 无额外数据，仅消耗 1 字节 opcode
        return cls()
