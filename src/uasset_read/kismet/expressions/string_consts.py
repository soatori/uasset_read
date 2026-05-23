"""Kismet 表达式 — 字符串常量表达式。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from uasset_read.kismet.expressions.base import KismetExpression, KismetExpressionT
from uasset_read.kismet.tokens import EBlueprintTextLiteralType, EExprToken

if TYPE_CHECKING:
    from uasset_read.kismet.archive import FKismetArchive


@dataclass
class EX_StringConst(KismetExpressionT[str]):
    """String constant expression (EX_StringConst, 0x1F)."""

    @property
    def Token(self):
        return EExprToken.EX_StringConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_StringConst:
        value = archive.xfer_string()
        archive.skip(1)  # skip null terminator
        return cls(Value=value)


@dataclass
class EX_UnicodeStringConst(KismetExpressionT[str]):
    """Unicode string constant expression (EX_UnicodeStringConst, 0x34)."""

    @property
    def Token(self):
        return EExprToken.EX_UnicodeStringConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_UnicodeStringConst:
        value = archive.xfer_unicode_string()
        archive.skip(2)  # skip double-null terminator
        return cls(Value=value)


@dataclass
class FScriptText:
    """FScriptText data for EX_TextConst."""

    TextLiteralType: EBlueprintTextLiteralType
    SourceString: Optional[str] = None
    KeyString: Optional[str] = None
    Namespace: Optional[str] = None
    StringTableAsset: Optional[str] = None
    TableIdString: Optional[str] = None

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> FScriptText:
        lit_type = EBlueprintTextLiteralType(archive.read_u8())
        if lit_type == EBlueprintTextLiteralType.Empty:
            return cls(TextLiteralType=lit_type)
        elif lit_type == EBlueprintTextLiteralType.LocalizedText:
            namespace = archive.xfer_string()
            archive.skip(1)
            key = archive.xfer_string()
            archive.skip(1)
            source = archive.xfer_string()
            archive.skip(1)
            return cls(
                TextLiteralType=lit_type,
                Namespace=namespace,
                KeyString=key,
                SourceString=source,
            )
        elif lit_type == EBlueprintTextLiteralType.Invariant:
            key = archive.xfer_string()
            archive.skip(1)
            source = archive.xfer_string()
            archive.skip(1)
            return cls(TextLiteralType=lit_type, KeyString=key, SourceString=source)
        elif lit_type == EBlueprintTextLiteralType.CultureInvariant:
            source = archive.xfer_string()
            archive.skip(1)
            return cls(TextLiteralType=lit_type, SourceString=source)
        elif lit_type == EBlueprintTextLiteralType.StringTableEntry:
            asset = archive.xfer_string()
            archive.skip(1)
            table_id = archive.xfer_string()
            archive.skip(1)
            return cls(
                TextLiteralType=lit_type,
                StringTableAsset=asset,
                TableIdString=table_id,
            )
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
