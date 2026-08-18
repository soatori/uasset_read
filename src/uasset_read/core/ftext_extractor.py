"""FText localization text extraction utility.

Extracts and formats localizable text data from parsed Blueprint expressions,
providing namespace, key, and source string information for localization workflows.

Usage:
    from uasset_read.core.ftext_extractor import FTextExtractor, extract_texts_from_expressions

    # Extract from a list of expressions
    texts = extract_texts_from_expressions(expressions)

    # Format as localization report
    report = FTextExtractor.format_locres(texts)
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FTextEntry:
    """A single extracted FText value with localization metadata."""

    namespace: str
    """Localization namespace (e.g. "MyGame", "Engine")."""

    key: str
    """Localization key (e.g. "MSG_HELLO", "UI_Button_OK")."""

    source_string: str
    """Source text string (may contain placeholders)."""

    text_type: str
    """Text type: 'localized', 'invariant', 'literal', 'string_table', 'empty'."""

    string_table_asset: Optional[str] = None
    """String table asset path (for string_table type)."""

    table_id: Optional[str] = None
    """String table ID (for string_table type)."""

    @property
    def is_localizable(self) -> bool:
        """True if this text can be localized."""
        return self.text_type == "localized"

    @property
    def locres_id(self) -> str:
        """Lookup ID for .locres files."""
        if self.text_type == "string_table" and self.table_id:
            return f"StringTable:{self.table_id}"
        return f"{self.namespace}:{self.key}"

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        d = {
            "namespace": self.namespace,
            "key": self.key,
            "source_string": self.source_string,
            "text_type": self.text_type,
        }
        if self.string_table_asset:
            d["string_table_asset"] = self.string_table_asset
        if self.table_id:
            d["table_id"] = self.table_id
        return d


class FTextExtractor:
    """FText extraction and formatting utility."""

    @staticmethod
    def from_script_text(script_text) -> Optional[FTextEntry]:
        """Extract FTextEntry from an FScriptText object.

        Args:
            script_text: FScriptText instance from EX_TextConst

        Returns:
            FTextEntry or None if empty
        """
        lit_type = script_text.TextLiteralType
        type_name = lit_type.name.lower() if hasattr(lit_type, "name") else str(lit_type).lower()

        # Map type names
        type_map = {
            "localizedtext": "localized",
            "invariant": "invariant",
            "cultureinvariant": "invariant",
            "literalstring": "literal",
            "stringtableentry": "string_table",
            "empty": "empty",
        }
        text_type = type_map.get(type_name, type_name)

        namespace = getattr(script_text, "Namespace", None) or ""
        key = getattr(script_text, "KeyString", None) or ""
        source = getattr(script_text, "SourceString", None) or ""
        st_asset = getattr(script_text, "StringTableAsset", None)
        table_id = getattr(script_text, "TableIdString", None)

        if text_type == "empty" and not source:
            return None

        return FTextEntry(
            namespace=namespace,
            key=key,
            source_string=source,
            text_type=text_type,
            string_table_asset=st_asset,
            table_id=table_id,
        )

    @staticmethod
    def format_locres(entries: list[FTextEntry]) -> str:
        """Format entries as a .locres-style text report.

        Args:
            entries: List of FTextEntry objects

        Returns:
            Formatted text report
        """
        lines: list[str] = ["# FText Localization Report", ""]

        localizable = [e for e in entries if e.is_localizable]
        non_localizable = [e for e in entries if not e.is_localizable]

        lines.append(f"# Total: {len(entries)} entries")
        lines.append(f"# Localizable: {len(localizable)}")
        lines.append(f"# Non-localizable: {len(non_localizable)}")
        lines.append("")

        if localizable:
            lines.append("## Localizable Texts")
            lines.append("")
            for entry in sorted(localizable, key=lambda e: (e.namespace, e.key)):
                ns = entry.namespace or "(default)"
                lines.append(f"[{ns}] {entry.key}")
                lines.append(f"    \"{entry.source_string}\"")
                lines.append("")

        if non_localizable:
            lines.append("## Non-Localizable Texts")
            lines.append("")
            for entry in non_localizable:
                ns = entry.namespace or "(default)"
                key = entry.key or "(no key)"
                lines.append(f"  [{ns}] {key}: \"{entry.source_string}\"")

        return "\n".join(lines)

    @staticmethod
    def format_json(entries: list[FTextEntry]) -> list[dict]:
        """Format entries as JSON-serializable list.

        Args:
            entries: List of FTextEntry objects

        Returns:
            List of dicts
        """
        return [e.to_dict() for e in entries]


def extract_texts_from_expressions(expressions: list) -> list[FTextEntry]:
    """Extract all FText values from a list of Kismet expressions.

    Recursively searches expression trees for EX_TextConst nodes
    and extracts their localization data.

    Args:
        expressions: List of KismetExpression objects

    Returns:
        List of FTextEntry objects
    """
    from uasset_read.kismet.expressions.string_consts import EX_TextConst

    results: list[FTextEntry] = []
    seen: set[str] = set()

    def _walk(expr) -> None:
        if expr is None:
            return

        if isinstance(expr, EX_TextConst) and expr.Text is not None:
            entry = FTextExtractor.from_script_text(expr.Text)
            if entry is not None:
                dedup_key = f"{entry.namespace}:{entry.key}:{entry.source_string}"
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    results.append(entry)

        # Recurse into expression children
        for attr_name in ("SubExpressions", "Args", "Parameters", "TrueExpr", "FalseExpr",
                          "Then", "Else", "Body"):
            child = getattr(expr, attr_name, None)
            if child is None:
                continue
            if isinstance(child, list):
                for item in child:
                    _walk(item)
            else:
                _walk(child)

    for expr in expressions:
        _walk(expr)

    return results
