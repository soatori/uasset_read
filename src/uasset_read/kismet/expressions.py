"""Kismet bytecode expression classes and token-to-class map.

Holds the KismetExpression hierarchy, the EX_* token expression classes, and
EXPR_CLASS_MAP used by FKismetArchive.read_expression() to dispatch token parsing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import fields, is_dataclass, dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from uasset_read.constants import UE5_LARGE_WORLD_COORDINATES
from uasset_read.exceptions import ParseError
from uasset_read.models.byte_ranges import ByteRegion
from uasset_read.kismet.tokens import (
    EAutoRtfmStopTransactMode,
    EBlueprintTextLiteralType,
    ECastToken,
    EExprToken,
    EScriptInstrumentationType,
)

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive
    from uasset_read.kismet.property_pointer import FKismetPropertyPointer

# === Base classes and factories (from base.py) ===


def _operand_to_json(value: Any) -> Any:
    """JSON-safe recursive operand projection; never str() embeds 0x bytes."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        try:
            return value.name
        except Exception:
            return {"kind": "opaque_value", "type": type(value).__name__}
    if isinstance(value, bytes):
        import base64

        return {"kind": "opaque_value", "type": "bytes", "base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, (list, tuple)):
        return [_operand_to_json(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _operand_to_json(v) for k, v in value.items()}
    if is_dataclass(value) and not isinstance(value, type):
        if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
            try:
                return project_operand_safe(value.to_dict())
            except Exception:
                pass
        return {f.name: _operand_to_json(getattr(value, f.name)) for f in fields(value)}
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        try:
            return project_operand_safe(value.to_dict())
        except Exception:
            pass
    return {"kind": "opaque_value", "type": type(value).__name__}


def project_operand_safe(data: Any) -> Any:
    if isinstance(data, dict):
        return {str(k): project_operand_safe(v) for k, v in data.items()}
    if isinstance(data, list):
        return [project_operand_safe(v) for v in data]
    if data is None or isinstance(data, (bool, int, float, str)):
        return data
    if isinstance(data, bytes):
        import base64

        return {"kind": "opaque_value", "type": "bytes", "base64": base64.b64encode(data).decode("ascii")}
    if isinstance(data, Enum):
        try:
            return data.name
        except Exception:
            return {"kind": "opaque_value", "type": type(data).__name__}
    if is_dataclass(data) and not isinstance(data, type):
        return {f.name: _operand_to_json(getattr(data, f.name)) for f in fields(data)}
    return {"kind": "opaque_value", "type": type(data).__name__}


class KismetExpression(ABC):
    """
    Kismet bytecode expression abstract base class.

    All EX_* instruction parse results inherit from this class.
    Subclasses must define a Token class attribute and a from_archive classmethod.

    Dual offsets: ``StatementIndex`` is the UE logical script address
    (CodeOffset coordinate). ``SerializedStart``/``SerializedEnd`` are the
    on-disk cursors captured by ``FKismetArchive.read_expression``; they
    default to ``-1`` until the archive fills them.
    """

    StatementIndex: int
    SerializedStart: int = -1
    SerializedEnd: int = -1

    @property
    @abstractmethod
    def Token(self) -> EExprToken:
        """Return the EExprToken value corresponding to this expression."""
        ...

    def __init__(
        self,
        statement_index: int = 0,
        serialized_start: int = -1,
        serialized_end: int = -1,
    ) -> None:
        self.StatementIndex = statement_index
        self.SerializedStart = serialized_start
        self.SerializedEnd = serialized_end

    def to_dict(self) -> dict:
        """Serialize to dictionary format (for JSON output).

        Emits every dataclass operand field so consumed payload is never
        dropped at the projection boundary (operand-preservation invariant).
        """
        out: dict[str, Any] = {
            "Inst": self.Token.name,
            "StatementIndex": getattr(self, "StatementIndex", 0),
            "SerializedStart": getattr(self, "SerializedStart", -1),
            "SerializedEnd": getattr(self, "SerializedEnd", -1),
        }
        if is_dataclass(self) and not isinstance(self, type):
            for f in fields(self):
                if f.name in {"StatementIndex", "SerializedStart", "SerializedEnd", "Token"}:
                    continue
                out[f.name] = _operand_to_json(getattr(self, f.name))
        return out

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} token={self.Token.name}>"


@dataclass
class OpaqueExpression(KismetExpression):
    """Bounded opaque tail for an unknown/unmapped expression token.

    Covers the unknown token through the end of the function slice so a
    malformed payload cannot silently disappear or corrupt CFG targets.
    The parser stops reading further top-level expressions for that function.
    """

    token: int
    raw_region: ByteRegion
    reason: str = "unknown_expression_token"

    @property
    def Token(self) -> EExprToken:  # type: ignore[override]
        # Not a real mapped opcode. Fall back to a neutral token so generic
        # Token.name accessors do not crash; the raw byte stays in ``token``.
        try:
            return EExprToken(self.token)
        except ValueError:
            return EExprToken.EX_Nothing

    def to_dict(self) -> dict:
        from uasset_read.models.byte_ranges import project_region

        return {
            "Inst": "Opaque",
            "StatementIndex": self.StatementIndex,
            "SerializedStart": self.SerializedStart,
            "SerializedEnd": self.SerializedEnd,
            "token": self.token,
            "reason": self.reason,
            "raw_region": project_region(self.raw_region),
        }

@dataclass(kw_only=True)
class KismetExpressionT(KismetExpression):
    """
    Base class for Kismet expressions that carry a value.

    Suitable for expressions with associated data (constants, variable references, etc.).

    Uses kw_only=True so subclasses can freely pass Value=... from
    from_archive() without positional-argument conflicts.
    """

    Value: Any = None

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["Value"] = self.Value
        return result

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} token={self.Token.name} value={self.Value!r}>"

def make_simple_expression(token: EExprToken):
    """Create a simple expression class (no extra fields, only returns Token value).

    Used for EX_Nothing, EX_IntZero, EX_IntOne and other data-free expressions.
    """

    @dataclass
    class _SimpleExpr(KismetExpression):
        Token = token

    _SimpleExpr.__name__ = token.name
    _SimpleExpr.__qualname__ = token.name
    return _SimpleExpr

def make_value_expression(token: EExprToken, read_func_name: str):
    """Create a value-carrying expression class (reads a single value from the archive).

    Used for EX_IntConst, EX_FloatConst and other single-value expressions.

    Args:
        token: The corresponding EExprToken enum value.
        read_func_name: The read method name on FArchive (e.g. "read_i32", "read_f32").
    """

    @dataclass
    class _ValueExpr(KismetExpressionT):
        Token = token

        @classmethod
        def from_archive(cls, archive):
            reader = getattr(archive, read_func_name)
            return cls(Value=reader())

    _ValueExpr.__name__ = token.name
    _ValueExpr.__qualname__ = token.name
    return _ValueExpr

def make_token_subclass(base: type, token: EExprToken):
    """Create a token-only subclass of *base* (inherits fields and from_archive).

    Used for expression variants that differ from their base only by Token,
    e.g. the EX_Let family or EX_CallMath vs EX_FinalFunction.
    """

    @dataclass
    class _TokenExpr(base):  # type: ignore[misc,valid-type]
        Token = token

    _TokenExpr.__name__ = token.name
    _TokenExpr.__qualname__ = token.name
    return _TokenExpr

# === Variable reference expressions (from variables.py) ===

@dataclass
class EX_VariableBase(KismetExpression):
    """Abstract base for variable expressions."""

    Variable: FKismetPropertyPointer | None = None

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_VariableBase:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        var = FKismetPropertyPointer.from_archive(archive)
        return cls(Variable=var)

EX_LocalVariable = make_token_subclass(EX_VariableBase, EExprToken.EX_LocalVariable)
EX_InstanceVariable = make_token_subclass(EX_VariableBase, EExprToken.EX_InstanceVariable)
EX_DefaultVariable = make_token_subclass(EX_VariableBase, EExprToken.EX_DefaultVariable)
EX_LocalOutVariable = make_token_subclass(EX_VariableBase, EExprToken.EX_LocalOutVariable)
EX_ClassSparseDataVariable = make_token_subclass(EX_VariableBase, EExprToken.EX_ClassSparseDataVariable)

# === Numeric and boolean literals (from literals.py) ===

# Single-value expression: read one value from the archive
EX_IntConst = make_value_expression(EExprToken.EX_IntConst, "read_i32")
EX_FloatConst = make_value_expression(EExprToken.EX_FloatConst, "read_f32")
EX_ByteConst = make_value_expression(EExprToken.EX_ByteConst, "read_u8")
EX_IntConstByte = make_value_expression(EExprToken.EX_IntConstByte, "read_u8")
EX_Int64Const = make_value_expression(EExprToken.EX_Int64Const, "read_i64")
EX_UInt64Const = make_value_expression(EExprToken.EX_UInt64Const, "read_u64")
EX_DoubleConst = make_value_expression(EExprToken.EX_DoubleConst, "read_f64")

# Data-free expression: returns Token only
EX_IntZero = make_simple_expression(EExprToken.EX_IntZero)
EX_IntOne = make_simple_expression(EExprToken.EX_IntOne)
EX_True = make_simple_expression(EExprToken.EX_True)
EX_False = make_simple_expression(EExprToken.EX_False)
EX_NoObject = make_simple_expression(EExprToken.EX_NoObject)
EX_NoInterface = make_simple_expression(EExprToken.EX_NoInterface)
EX_Self = make_simple_expression(EExprToken.EX_Self)
EX_Nothing = make_simple_expression(EExprToken.EX_Nothing)

# === String constants (from string_consts.py) ===

@dataclass
class EX_StringConst(KismetExpressionT):
    """String constant expression (EX_StringConst, 0x1F)."""

    Token = EExprToken.EX_StringConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_StringConst:
        value = archive.xfer_ansi_string()
        return cls(Value=value)

@dataclass
class EX_UnicodeStringConst(KismetExpressionT):
    """Unicode string constant expression (EX_UnicodeStringConst, 0x34)."""

    Token = EExprToken.EX_UnicodeStringConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_UnicodeStringConst:
        value = archive.xfer_unicode_string()
        return cls(Value=value)

@dataclass
class FScriptText:
    """FScriptText data for EX_TextConst."""

    TextLiteralType: EBlueprintTextLiteralType
    SourceString: str | None = None
    KeyString: str | None = None
    Namespace: str | None = None
    DevNotes: str | None = None
    TableIdString: str | None = None

    @staticmethod
    def _read_string_operand(archive) -> str:
        """Each text operand is [EX_StringConst|EX_UnicodeStringConst][string] (ScriptSerialization.inl)."""
        token = archive.read_u8()
        if token == EExprToken.EX_StringConst:
            return archive.xfer_ansi_string()
        if token == EExprToken.EX_UnicodeStringConst:
            return archive.xfer_unicode_string()
        raise ParseError(f"FScriptText: unexpected string operand token {token:#x}")

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> FScriptText:
        lit_type = EBlueprintTextLiteralType(archive.read_u8())
        if lit_type == EBlueprintTextLiteralType.Empty:
            return cls(TextLiteralType=lit_type)
        if lit_type in (
            EBlueprintTextLiteralType.LocalizedText,
            EBlueprintTextLiteralType.LocalizedTextWithNotes,
        ):
            # Script.h: disk order is source, key, namespace (+ devnotes variant).
            source = cls._read_string_operand(archive)
            key = cls._read_string_operand(archive)
            namespace = cls._read_string_operand(archive)
            notes = (
                cls._read_string_operand(archive)
                if lit_type == EBlueprintTextLiteralType.LocalizedTextWithNotes
                else None
            )
            return cls(
                TextLiteralType=lit_type,
                SourceString=source,
                KeyString=key,
                Namespace=namespace,
                DevNotes=notes,
            )
        if lit_type in (
            EBlueprintTextLiteralType.InvariantText,
            EBlueprintTextLiteralType.LiteralString,
        ):
            # One string operand (ScriptSerialization.inl EX_TextConst).
            return cls(TextLiteralType=lit_type, SourceString=cls._read_string_operand(archive))
        if lit_type == EBlueprintTextLiteralType.StringTableEntry:
            archive.read_i32()  # object pointer, unused on disk (4 bytes)
            table_id = cls._read_string_operand(archive)
            key = cls._read_string_operand(archive)
            return cls(TextLiteralType=lit_type, TableIdString=table_id, KeyString=key)
        return cls(TextLiteralType=lit_type)

@dataclass
class EX_TextConst(KismetExpression):
    """FText constant expression (EX_TextConst, 0x29)."""

    Text: FScriptText | None = None  # type: ignore[assignment]

    Token = EExprToken.EX_TextConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_TextConst:
        text = FScriptText.from_archive(archive)
        return cls(Text=text)

    def to_dict(self) -> dict:
        d = super().to_dict()
        if self.Text:
            d["Text"] = {
                "TextLiteralType": self.Text.TextLiteralType.name,
                "SourceString": self.Text.SourceString,
                "KeyString": self.Text.KeyString,
                "Namespace": self.Text.Namespace,
                "DevNotes": self.Text.DevNotes,
            }
        return d

@dataclass
class EX_SoftObjectConst(KismetExpression):
    """Soft object constant expression (EX_SoftObjectConst, 0x67)."""

    Token = EExprToken.EX_SoftObjectConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_SoftObjectConst:
        archive.read_expression()
        return cls()

# === Vector / rotation / transform constants (from vector_consts.py) ===

def _is_lwc(archive: "FKismetArchive") -> bool:
    """Check if Large World Coordinates (double-width vectors) are enabled."""
    summary = getattr(archive, "summary", None)
    if summary is None:
        return False
    return getattr(summary, "file_version_ue5", 0) >= UE5_LARGE_WORLD_COORDINATES

@dataclass
class EX_VectorConst(KismetExpression):
    """Vector constant (X, Y, Z).

    Reads doubles when summary.file_version_ue5 >= UE5_LARGE_WORLD_COORDINATES,
    otherwise reads floats.
    """

    X: float = 0.0
    Y: float = 0.0
    Z: float = 0.0

    Token = EExprToken.EX_VectorConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_VectorConst:
        if _is_lwc(archive):
            x = archive.read_f64()
            y = archive.read_f64()
            z = archive.read_f64()
        else:
            x = archive.read_f32()
            y = archive.read_f32()
            z = archive.read_f32()
        return cls(X=x, Y=y, Z=z)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Value"] = f"({self.X}, {self.Y}, {self.Z})"
        return d

@dataclass
class EX_RotationConst(KismetExpression):
    """Rotation constant expression (EX_RotationConst, 0x22).

    Reads doubles when summary.file_version_ue5 >= UE5_LARGE_WORLD_COORDINATES.
    """

    Pitch: float = 0.0
    Yaw: float = 0.0
    Roll: float = 0.0

    Token = EExprToken.EX_RotationConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_RotationConst:
        if _is_lwc(archive):
            p = archive.read_f64()
            y = archive.read_f64()
            r = archive.read_f64()
        else:
            p = archive.read_f32()
            y = archive.read_f32()
            r = archive.read_f32()
        return cls(Pitch=p, Yaw=y, Roll=r)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Value"] = f"(Pitch={self.Pitch}, Yaw={self.Yaw}, Roll={self.Roll})"
        return d

@dataclass
class EX_TransformConst(KismetExpression):
    """Transform constant expression (EX_TransformConst, 0x2B).

    UE FTransform serialization order: quaternion rotation (XYZW) -> translation (XYZ) -> scale (XYZ).
    Reads doubles when summary.file_version_ue5 >= UE5_LARGE_WORLD_COORDINATES.
    """

    Rotation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    Translation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    Scale: tuple[float, float, float] = (0.0, 0.0, 0.0)

    Token = EExprToken.EX_TransformConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_TransformConst:
        read_num = archive.read_f64 if _is_lwc(archive) else archive.read_f32
        # Rotation (quat): X, Y, Z, W
        rot = (read_num(), read_num(), read_num(), read_num())
        # Translation: X, Y, Z
        trans = (read_num(), read_num(), read_num())
        # Scale: X, Y, Z
        scale = (read_num(), read_num(), read_num())
        return cls(Rotation=rot, Translation=trans, Scale=scale)

@dataclass
class EX_Vector3fConst(KismetExpression):
    """3-component float vector constant (EX_Vector3fConst, 0x41)."""

    X: float = 0.0
    Y: float = 0.0
    Z: float = 0.0

    Token = EExprToken.EX_Vector3fConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_Vector3fConst:
        x = archive.read_f32()
        y = archive.read_f32()
        z = archive.read_f32()
        return cls(X=x, Y=y, Z=z)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Value"] = f"({self.X}, {self.Y}, {self.Z})"
        return d

# === Control flow (from control_flow.py) ===

@dataclass
class EX_Jump(KismetExpression):
    """Unconditional jump to a specified code offset."""

    CodeOffset: int = 0

    Token = EExprToken.EX_Jump

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_Jump:
        offset = archive.read_u32()
        return cls(CodeOffset=offset)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["CodeOffset"] = self.CodeOffset
        return d

@dataclass
class EX_JumpIfNot(EX_Jump):
    """Conditional jump: jump if the boolean expression is false."""

    BooleanExpression: KismetExpression | None = None

    Token = EExprToken.EX_JumpIfNot

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_JumpIfNot:
        offset = archive.read_u32()
        expr = archive.read_expression()
        return cls(CodeOffset=offset, BooleanExpression=expr)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["BooleanExpression"] = self.BooleanExpression.to_dict() if self.BooleanExpression else None
        return d

@dataclass
class EX_Skip(EX_Jump):
    """Skip over an expression code block."""

    SkipExpression: KismetExpression | None = None

    Token = EExprToken.EX_Skip

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_Skip:
        offset = archive.read_u32()
        expr = archive.read_expression()
        return cls(CodeOffset=offset, SkipExpression=expr)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["SkipExpression"] = self.SkipExpression.to_dict() if self.SkipExpression else None
        return d

@dataclass
class EX_ComputedJump(KismetExpression):
    """Dynamically computed jump target offset."""

    CodeOffsetExpression: KismetExpression | None = None

    Token = EExprToken.EX_ComputedJump

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_ComputedJump:
        expr = archive.read_expression()
        return cls(CodeOffsetExpression=expr)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["CodeOffsetExpression"] = self.CodeOffsetExpression.to_dict() if self.CodeOffsetExpression else None
        return d

@dataclass
class EX_PushExecutionFlow(KismetExpression):
    """Push the return address onto the execution flow stack."""

    PushingAddress: int = 0

    Token = EExprToken.EX_PushExecutionFlow

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_PushExecutionFlow:
        addr = archive.read_u32()
        return cls(PushingAddress=addr)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["PushingAddress"] = self.PushingAddress
        return d

# Data-free expression: returns Token only
EX_PopExecutionFlow = make_simple_expression(EExprToken.EX_PopExecutionFlow)

@dataclass
class EX_PopExecutionFlowIfNot(KismetExpression):
    """Conditional execution flow pop: pop and jump when the boolean expression is false."""

    BooleanExpression: KismetExpression | None = None

    Token = EExprToken.EX_PopExecutionFlowIfNot

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_PopExecutionFlowIfNot:
        expr = archive.read_expression()
        return cls(BooleanExpression=expr)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["BooleanExpression"] = self.BooleanExpression.to_dict() if self.BooleanExpression else None
        return d

# Data-free expression: returns Token only
EX_EndOfScript = make_simple_expression(EExprToken.EX_EndOfScript)

@dataclass
class EX_SkipOffsetConst(KismetExpressionT):
    """Skip offset constant."""

    Token = EExprToken.EX_SkipOffsetConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_SkipOffsetConst:
        return cls(Value=archive.read_u32())

# === Assignments (from assignments.py) ===

@dataclass
class EX_LetBase(KismetExpression):
    """Abstract base class for assignment expressions."""

    Variable: KismetExpression | None = None
    Assignment: KismetExpression | None = None

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_LetBase:
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
    """Standard assignment expression with a property pointer."""

    Property: FKismetPropertyPointer | None = None
    Variable: KismetExpression | None = None
    Assignment: KismetExpression | None = None

    Token = EExprToken.EX_Let

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_Let:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        prop = FKismetPropertyPointer.from_archive(archive)
        var = archive.read_expression()
        assign = archive.read_expression()
        return cls(Property=prop, Variable=var, Assignment=assign)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Property"] = self.Property.to_dict() if self.Property else None
        d["Variable"] = self.Variable.to_dict() if self.Variable else None
        d["Assignment"] = self.Assignment.to_dict() if self.Assignment else None
        return d

# Token-only EX_Let variants — share EX_LetBase serialization exactly.
EX_LetBool = make_token_subclass(EX_LetBase, EExprToken.EX_LetBool)
EX_LetDelegate = make_token_subclass(EX_LetBase, EExprToken.EX_LetDelegate)
EX_LetMulticastDelegate = make_token_subclass(EX_LetBase, EExprToken.EX_LetMulticastDelegate)
EX_LetObj = make_token_subclass(EX_LetBase, EExprToken.EX_LetObj)
EX_LetWeakObjPtr = make_token_subclass(EX_LetBase, EExprToken.EX_LetWeakObjPtr)

@dataclass
class EX_LetValueOnPersistentFrame(KismetExpression):
    """Set value on persistent frame (used for loop variables / local variables)."""

    DestinationProperty: FKismetPropertyPointer | None = None
    AssignmentExpression: KismetExpression | None = None

    Token = EExprToken.EX_LetValueOnPersistentFrame

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_LetValueOnPersistentFrame:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        prop = FKismetPropertyPointer.from_archive(archive)
        expr = archive.read_expression()
        return cls(DestinationProperty=prop, AssignmentExpression=expr)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["DestinationProperty"] = self.DestinationProperty.to_dict() if self.DestinationProperty else None
        d["AssignmentExpression"] = self.AssignmentExpression.to_dict() if self.AssignmentExpression else None
        return d

# === Function calls (from functions.py) ===

# Data-free expression: returns Token only
EX_EndParmValue = make_simple_expression(EExprToken.EX_EndParmValue)
EX_EndFunctionParms = make_simple_expression(EExprToken.EX_EndFunctionParms)

@dataclass
class EX_FinalFunction(KismetExpression):
    """Pre-bound function call (native/final function) with a parameter list."""

    StackNode: int = 0
    Parameters: list[KismetExpression] = field(default_factory=list)

    Token = EExprToken.EX_FinalFunction

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_FinalFunction:
        stack_ref = archive.xfer_object_pointer()
        params = archive.read_expression_array(EExprToken.EX_EndFunctionParms)
        return cls(StackNode=stack_ref.index, Parameters=params)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["StackNode"] = self.StackNode
        d["ParamCount"] = len(self.Parameters) if self.Parameters else 0
        d["parameters"] = [p.to_dict() if hasattr(p, "to_dict") else p for p in self.Parameters]
        return d

# Token-only EX_FinalFunction variants — share its serialization exactly.
EX_CallMath = make_token_subclass(EX_FinalFunction, EExprToken.EX_CallMath)
EX_LocalFinalFunction = make_token_subclass(EX_FinalFunction, EExprToken.EX_LocalFinalFunction)

@dataclass
class EX_VirtualFunction(KismetExpression):
    """Virtual function call, resolved by function name."""

    VirtualFunctionName: str = ""
    Parameters: list[KismetExpression] = field(default_factory=list)

    Token = EExprToken.EX_VirtualFunction

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_VirtualFunction:
        fname_ref = archive.xfer_fname()
        params = archive.read_expression_array(EExprToken.EX_EndFunctionParms)
        # Build full name with number suffix (e.g., "TestFunc_3")
        if fname_ref.base_name and fname_ref.number > 0:
            full_name = f"{fname_ref.base_name}_{fname_ref.number}"
        else:
            full_name = fname_ref.base_name or ""
        return cls(
            VirtualFunctionName=full_name,
            Parameters=params,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Name"] = self.VirtualFunctionName
        d["ParamCount"] = len(self.Parameters) if self.Parameters else 0
        d["parameters"] = [p.to_dict() if hasattr(p, "to_dict") else p for p in self.Parameters]
        return d

EX_LocalVirtualFunction = make_token_subclass(EX_VirtualFunction, EExprToken.EX_LocalVirtualFunction)

@dataclass
class EX_CallMulticastDelegate(KismetExpression):
    """Multicast delegate call."""

    StackNode: int = 0
    Delegate: KismetExpression | None = None
    Parameters: list[KismetExpression] = field(default_factory=list)

    Token = EExprToken.EX_CallMulticastDelegate

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_CallMulticastDelegate:
        stack_ref = archive.xfer_object_pointer()
        delegate = archive.read_expression()
        params = archive.read_expression_array(EExprToken.EX_EndFunctionParms)
        return cls(StackNode=stack_ref.index, Delegate=delegate, Parameters=params)

# === Type casts (from casts.py) ===

@dataclass
class EX_CastBase(KismetExpression):
    """Abstract base class for cast expressions -- reads class pointer and target expression."""

    TargetClass: int = 0
    TargetExpression: KismetExpression | None = None

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_CastBase:
        class_ref = archive.xfer_object_pointer()
        target = archive.read_expression()
        return cls(TargetClass=class_ref.index, TargetExpression=target)

@dataclass
class EX_Cast(KismetExpression):
    """General type cast operator -- reads a conversion type byte followed by the target expression."""

    ConversionType: ECastToken = ECastToken.CST_ObjectToInterface
    TargetExpression: KismetExpression | None = None

    Token = EExprToken.EX_Cast

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_Cast:
        conv = ECastToken(archive.read_u8())
        target = archive.read_expression()
        return cls(ConversionType=conv, TargetExpression=target)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["ConversionType"] = self.ConversionType.name
        d["TargetExpression"] = self.TargetExpression.to_dict() if self.TargetExpression else None
        return d

# Token-only cast variants — share EX_CastBase serialization exactly.
EX_MetaCast = make_token_subclass(EX_CastBase, EExprToken.EX_MetaCast)
EX_DynamicCast = make_token_subclass(EX_CastBase, EExprToken.EX_DynamicCast)
EX_ObjToInterfaceCast = make_token_subclass(EX_CastBase, EExprToken.EX_ObjToInterfaceCast)
EX_CrossInterfaceCast = make_token_subclass(EX_CastBase, EExprToken.EX_CrossInterfaceCast)
EX_InterfaceToObjCast = make_token_subclass(EX_CastBase, EExprToken.EX_InterfaceToObjCast)

# === Context expressions (from context.py) ===

@dataclass
class EX_Context(KismetExpression):
    ContextExpression: KismetExpression | None = None
    ContextualOffset: int = 0
    ContextualProperty: Any = None
    MemberExpression: KismetExpression | None = None

    Token = EExprToken.EX_Context

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_Context:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        context_expr = archive.read_expression()
        offset = archive.read_u32()
        prop = FKismetPropertyPointer.from_archive(archive)
        member = archive.read_expression()
        return cls(
            ContextExpression=context_expr,
            ContextualOffset=offset,
            ContextualProperty=prop,
            MemberExpression=member,
        )

# Token-only EX_Context variants — share EX_Context serialization exactly.
EX_Context_FailSilent = make_token_subclass(EX_Context, EExprToken.EX_Context_FailSilent)
EX_ClassContext = make_token_subclass(EX_Context, EExprToken.EX_ClassContext)

@dataclass
class EX_InterfaceContext(KismetExpression):
    InterfaceExpression: KismetExpression | None = None

    Token = EExprToken.EX_InterfaceContext

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_InterfaceContext:
        expr = archive.read_expression()
        return cls(InterfaceExpression=expr)

@dataclass
class EX_StructMemberContext(KismetExpression):
    MemberProperty: Any = None
    StructExpression: KismetExpression | None = None

    Token = EExprToken.EX_StructMemberContext

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_StructMemberContext:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        prop = FKismetPropertyPointer.from_archive(archive)
        expr = archive.read_expression()
        return cls(MemberProperty=prop, StructExpression=expr)

# === Container expressions (from containers.py) ===

@dataclass
class EX_SetArray(KismetExpression):
    """SetArray — version-dependent: with CHANGE_SETARRAY_BYTECODE has AssigningProperty."""

    TargetExpression: KismetExpression | None = None
    InitializingList: list[KismetExpression] = field(default_factory=list)

    Token = EExprToken.EX_SetArray

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_SetArray:
        # UE5's post-VER_UE4_CHANGE_SETARRAY_BYTECODE layout serializes the
        # array target as an expression, not as a bare FProperty pointer.
        target = archive.read_expression()
        elements = archive.read_expression_array(EExprToken.EX_EndArray)
        return cls(TargetExpression=target, InitializingList=elements)

# Data-free expression: returns Token only
EX_EndArray = make_simple_expression(EExprToken.EX_EndArray)

@dataclass
class EX_SetMap(KismetExpression):
    TargetExpression: KismetExpression | None = None
    Num: int = 0
    Elements: list[KismetExpression] = field(default_factory=list)

    Token = EExprToken.EX_SetMap

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_SetMap:
        target = archive.read_expression()
        num = archive.read_i32()  # ScriptSerialization.inl:531-534: int32 element count
        elements = archive.read_expression_array(EExprToken.EX_EndMap)
        return cls(TargetExpression=target, Num=num, Elements=elements)

# Data-free expression: returns Token only
EX_EndMap = make_simple_expression(EExprToken.EX_EndMap)

@dataclass
class EX_SetSet(KismetExpression):
    TargetExpression: KismetExpression | None = None
    Num: int = 0
    Elements: list[KismetExpression] = field(default_factory=list)

    Token = EExprToken.EX_SetSet

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_SetSet:
        target = archive.read_expression()
        num = archive.read_i32()  # ScriptSerialization.inl:526-529: int32 element count
        elements = archive.read_expression_array(EExprToken.EX_EndSet)
        return cls(TargetExpression=target, Num=num, Elements=elements)

# Data-free expression: returns Token only
EX_EndSet = make_simple_expression(EExprToken.EX_EndSet)

@dataclass
class EX_ArrayConst(KismetExpression):
    ElementType: Any = None
    Num: int = 0
    Values: list[KismetExpression] = field(default_factory=list)

    Token = EExprToken.EX_ArrayConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_ArrayConst:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        element_type = FKismetPropertyPointer.from_archive(archive)
        num = archive.read_i32()  # ScriptSerialization.inl:536-541: int32 element count
        values = archive.read_expression_array(EExprToken.EX_EndArrayConst)
        return cls(ElementType=element_type, Num=num, Values=values)

# Data-free expression: returns Token only
EX_EndArrayConst = make_simple_expression(EExprToken.EX_EndArrayConst)

@dataclass
class EX_MapConst(KismetExpression):
    KeyType: Any = None
    ValueType: Any = None
    Num: int = 0
    Values: list[KismetExpression] = field(default_factory=list)

    Token = EExprToken.EX_MapConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_MapConst:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        key_type = FKismetPropertyPointer.from_archive(archive)
        value_type = FKismetPropertyPointer.from_archive(archive)
        num = archive.read_i32()
        values = archive.read_expression_array(EExprToken.EX_EndMapConst)
        return cls(KeyType=key_type, ValueType=value_type, Num=num, Values=values)

# Data-free expression: returns Token only
EX_EndMapConst = make_simple_expression(EExprToken.EX_EndMapConst)

@dataclass
class EX_SetConst(KismetExpression):
    ElementType: Any = None
    Num: int = 0
    Values: list[KismetExpression] = field(default_factory=list)

    Token = EExprToken.EX_SetConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_SetConst:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        element_type = FKismetPropertyPointer.from_archive(archive)
        num = archive.read_i32()  # ScriptSerialization.inl:543-548: int32 element count
        values = archive.read_expression_array(EExprToken.EX_EndSetConst)
        return cls(ElementType=element_type, Num=num, Values=values)

# Data-free expression: returns Token only
EX_EndSetConst = make_simple_expression(EExprToken.EX_EndSetConst)

@dataclass
class EX_ArrayGetByRef(KismetExpression):
    Token = EExprToken.EX_ArrayGetByRef
    TargetExpression: KismetExpression | None = None
    IndexExpression: KismetExpression | None = None

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_ArrayGetByRef:
        target = archive.read_expression()
        index = archive.read_expression()
        return cls(TargetExpression=target, IndexExpression=index)

# === Struct expressions (from structs.py) ===

@dataclass
class EX_StructConst(KismetExpression):
    """An arbitrary UStruct constant (EX_StructConst, 0x2F)."""

    Struct: int = 0
    StructSize: int = 0
    Properties: list[KismetExpression] = field(default_factory=list)

    Token = EExprToken.EX_StructConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_StructConst:
        struct_ref = archive.xfer_object_pointer()
        size = archive.read_u32()
        props = archive.read_expression_array(EExprToken.EX_EndStructConst)
        return cls(Struct=struct_ref.index, StructSize=size, Properties=props)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["Struct"] = self.Struct
        result["StructSize"] = self.StructSize
        result["Properties"] = [p.to_dict() for p in self.Properties]
        return result

@dataclass
class EX_EndStructConst(KismetExpression):
    """End of UStruct constant (EX_EndStructConst, 0x30)."""

    Token = EExprToken.EX_EndStructConst

@dataclass
class EX_PropertyConst(KismetExpression):
    """FProperty constant (EX_PropertyConst, 0x33)."""

    Property: FKismetPropertyPointer | None = None

    Token = EExprToken.EX_PropertyConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_PropertyConst:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        prop = FKismetPropertyPointer.from_archive(archive)
        return cls(Property=prop)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["Property"] = str(self.Property) if self.Property else None
        return result

@dataclass
class EX_BitFieldConst(KismetExpression):
    """Assign to a single bit, defined by an FProperty (EX_BitFieldConst, 0x11)."""

    InnerProperty: FKismetPropertyPointer | None = None
    ConstValue: int = 0

    Token = EExprToken.EX_BitFieldConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_BitFieldConst:
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer

        prop = FKismetPropertyPointer.from_archive(archive)
        val = archive.read_u8()
        return cls(InnerProperty=prop, ConstValue=val)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["InnerProperty"] = str(self.InnerProperty) if self.InnerProperty else None
        result["ConstValue"] = self.ConstValue
        return result

# === Delegate expressions (from delegates.py) ===

@dataclass
class EX_AddMulticastDelegate(KismetExpression):
    """Adds a delegate to a multicast delegate's targets (EX_AddMulticastDelegate, 0x5C)."""

    Delegate: KismetExpression | None = None
    DelegateToAdd: KismetExpression | None = None

    Token = EExprToken.EX_AddMulticastDelegate

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_AddMulticastDelegate:
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

    DelegateToClear: KismetExpression | None = None

    Token = EExprToken.EX_ClearMulticastDelegate

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_ClearMulticastDelegate:
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
    Delegate: KismetExpression | None = None
    ObjectTerm: KismetExpression | None = None

    Token = EExprToken.EX_BindDelegate

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_BindDelegate:
        fname_ref = archive.xfer_fname()
        d = archive.read_expression()
        obj = archive.read_expression()
        return cls(
            FunctionName=fname_ref.base_name or "",
            Delegate=d,
            ObjectTerm=obj,
        )

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["FunctionName"] = self.FunctionName
        result["Delegate"] = self.Delegate.to_dict() if self.Delegate else None
        result["ObjectTerm"] = self.ObjectTerm.to_dict() if self.ObjectTerm else None
        return result

@dataclass
class EX_RemoveMulticastDelegate(KismetExpression):
    """Remove a delegate from a multicast delegate's targets (EX_RemoveMulticastDelegate, 0x62)."""

    Delegate: KismetExpression | None = None
    DelegateToRemove: KismetExpression | None = None

    Token = EExprToken.EX_RemoveMulticastDelegate

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_RemoveMulticastDelegate:
        d = archive.read_expression()
        d_remove = archive.read_expression()
        return cls(Delegate=d, DelegateToRemove=d_remove)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["Delegate"] = self.Delegate.to_dict() if self.Delegate else None
        result["DelegateToRemove"] = self.DelegateToRemove.to_dict() if self.DelegateToRemove else None
        return result

@dataclass
class EX_InstanceDelegate(KismetExpression):
    """Const reference to a delegate or normal function object (EX_InstanceDelegate, 0x4B)."""

    FunctionName: str = ""

    Token = EExprToken.EX_InstanceDelegate

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_InstanceDelegate:
        fname_ref = archive.xfer_fname()
        return cls(FunctionName=fname_ref.base_name or "")

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["FunctionName"] = self.FunctionName
        return result

# === Special expressions (from special.py) ===

@dataclass
class FKismetSwitchCase:
    """Switch case struct for EX_SwitchValue."""

    IndexExpression: KismetExpression | None = None
    NextOffset: int = 0
    CaseExpression: KismetExpression | None = None

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> FKismetSwitchCase:
        index_expr = archive.read_expression()
        offset = archive.read_u32()
        case_expr = archive.read_expression()
        return cls(IndexExpression=index_expr, NextOffset=offset, CaseExpression=case_expr)

@dataclass
class EX_Return(KismetExpression):
    """Return from function — reads return expression."""

    ReturnValue: KismetExpression | None = None

    Token = EExprToken.EX_Return

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_Return:
        value = archive.read_expression()
        return cls(ReturnValue=value)

@dataclass
class EX_Assert(KismetExpression):
    """Assertion — reads line number, debug mode, and assert expression."""

    LineNumber: int = 0
    DebugMode: bool = False
    AssertExpression: KismetExpression | None = None

    Token = EExprToken.EX_Assert

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_Assert:
        line = archive.read_u16()
        # ScriptSerialization.inl:597-603 — debug flag is uint8 (XFER(uint8)), NOT a 4-byte UBOOL.
        debug = archive.read_u8() != 0
        expr = archive.read_expression()
        return cls(LineNumber=line, DebugMode=debug, AssertExpression=expr)

@dataclass
class EX_NothingInt32(KismetExpressionT):
    """No operation with an int32 argument."""

    Value: int = 0

    Token = EExprToken.EX_NothingInt32

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_NothingInt32:
        return cls(Value=archive.read_i32())

@dataclass
class EX_SwitchValue(KismetExpression):
    """Switch expression — evaluates index, matches cases, falls through to default."""

    EndGotoOffset: int = 0
    IndexExpression: KismetExpression | None = None
    Cases: list[FKismetSwitchCase] | None = None
    DefaultExpression: KismetExpression | None = None

    Token = EExprToken.EX_SwitchValue

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_SwitchValue:
        num_cases = archive.read_u16()
        end_offset = archive.read_u32()
        index_expr = archive.read_expression()
        cases = []
        for _ in range(num_cases):
            case = FKismetSwitchCase.from_archive(archive)
            cases.append(case)
        default_expr = archive.read_expression()
        return cls(
            EndGotoOffset=end_offset,
            IndexExpression=index_expr,
            Cases=cases,
            DefaultExpression=default_expr,
        )

@dataclass
class EX_InstrumentationEvent(KismetExpression):
    """Instrumentation event — reads event type and optional name."""

    Token = EExprToken.EX_InstrumentationEvent

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_InstrumentationEvent:
        evt_type = EScriptInstrumentationType(archive.read_u8())
        if evt_type == EScriptInstrumentationType.InlineEvent:
            archive.xfer_fname()
        return cls()

# Data-free expression: returns Token only
EX_DeprecatedOp4A = make_simple_expression(EExprToken.EX_DeprecatedOp4A)
EX_Breakpoint = make_simple_expression(EExprToken.EX_Breakpoint)
EX_Tracepoint = make_simple_expression(EExprToken.EX_Tracepoint)
EX_WireTracepoint = make_simple_expression(EExprToken.EX_WireTracepoint)

@dataclass
class EX_FieldPathConst(KismetExpression):
    """FProperty constant — wraps a field path expression."""

    Token = EExprToken.EX_FieldPathConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_FieldPathConst:
        archive.read_expression()
        return cls()

@dataclass
class EX_ObjectConst(KismetExpressionT):
    """Object constant — reads object reference index."""

    Value: int = 0

    Token = EExprToken.EX_ObjectConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_ObjectConst:
        obj_ref = archive.xfer_object_pointer()
        return cls(Value=obj_ref.index)

@dataclass
class EX_NameConst(KismetExpressionT):
    """Name constant — reads FName index + number via the archive's name map."""

    Value: str = ""

    Token = EExprToken.EX_NameConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_NameConst:
        fname_ref = archive.xfer_fname()
        return cls(Value=fname_ref.base_name or "")

# === AutoRTFM expressions (from rtfm.py) ===

@dataclass
class EX_AutoRtfmTransact(KismetExpression):
    """AutoRTFM: run following code in a transaction."""

    CodeOffset: int = 0

    Token = EExprToken.EX_AutoRtfmTransact

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_AutoRtfmTransact:
        archive.read_i32()
        offset = archive.read_u32()
        archive.read_expression_array(EExprToken.EX_AutoRtfmStopTransact)
        return cls(CodeOffset=offset)

@dataclass
class EX_AutoRtfmStopTransact(KismetExpression):
    """AutoRTFM: if in transaction, abort or break."""

    Token = EExprToken.EX_AutoRtfmStopTransact

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_AutoRtfmStopTransact:
        archive.read_i32()
        EAutoRtfmStopTransactMode(archive.read_u8())
        return cls()

@dataclass
class EX_AutoRtfmAbortIfNot(KismetExpression):
    """AutoRTFM: evaluate bool condition, abort transaction on false."""

    Token = EExprToken.EX_AutoRtfmAbortIfNot

    @classmethod
    def from_archive(cls, archive: FKismetArchive) -> EX_AutoRtfmAbortIfNot:
        archive.read_expression()
        return cls()

# === Token-to-class map ===

EXPR_CLASS_MAP: dict[EExprToken, type[KismetExpression]] = {
    cls.Token: cls
    for cls in list(globals().values())
    if isinstance(cls, type)
    and issubclass(cls, KismetExpression)
    and cls is not KismetExpression
    and isinstance(getattr(cls, "Token", None), EExprToken)
}
