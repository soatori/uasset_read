from __future__ import annotations

"""Kismet expression -- string constant expressions."""


from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from uasset_read.exceptions import ParseError
from uasset_read.kismet.expressions.base import KismetExpression, KismetExpressionT
from uasset_read.kismet.tokens import EBlueprintTextLiteralType, EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_StringConst(KismetExpressionT):
    """String constant expression (EX_StringConst, 0x1F)."""

    @property
    def Token(self):
        return EExprToken.EX_StringConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_StringConst:
        value = archive.xfer_ansi_string()
        return cls(Value=value)


@dataclass
class EX_UnicodeStringConst(KismetExpressionT):
    """Unicode string constant expression (EX_UnicodeStringConst, 0x34)."""

    @property
    def Token(self):
        return EExprToken.EX_UnicodeStringConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_UnicodeStringConst:
        value = archive.xfer_unicode_string()
        return cls(Value=value)


@dataclass
class FScriptText:
    """FScriptText data for EX_TextConst."""

    TextLiteralType: EBlueprintTextLiteralType
    SourceString: Optional[str] = None
    KeyString: Optional[str] = None
    Namespace: Optional[str] = None
    DevNotes: Optional[str] = None
    StringTableAsset: Optional[str] = None
    TableIdString: Optional[str] = None

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
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> FScriptText:
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

    Text: FScriptText = None  # type: ignore[assignment]

    @property
    def Token(self):
        return EExprToken.EX_TextConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_TextConst:
        text = FScriptText.from_archive(archive, name_map)
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

    SoftObject: KismetExpression = None  # type: ignore[assignment]

    @property
    def Token(self):
        return EExprToken.EX_SoftObjectConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_SoftObjectConst:
        expr = archive.read_expression()
        return cls(SoftObject=expr)
