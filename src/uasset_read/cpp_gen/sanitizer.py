"""
C++ identifier and content sanitization module.

Provides functionality to convert UE asset-derived fields to safe C++ code, preventing injection.
All user-derived content in generated C++ code must be sanitized through this module.

Exports:
    sanitize_identifier: Sanitize C++ identifier function
    sanitize_string_literal: Sanitize C++ string literal / TEXT() content
    sanitize_uproperty_marks: Sanitize UPROPERTY specifier list
    sanitize_category: Sanitize UPROPERTY Category string
"""

import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# UPROPERTY specifier whitelist
# ============================================================================

_UPROPERTY_SPECIFIER_WHITELIST = frozenset(
    {
        # Visibility / Edit
        "EditAnywhere",
        "EditInstanceOnly",
        "EditDefaultsOnly",
        "VisibleAnywhere",
        "VisibleInstanceOnly",
        "VisibleDefaultsOnly",
        # Blueprint access
        "BlueprintReadWrite",
        "BlueprintReadOnly",
        "BlueprintCallable",
        "BlueprintAssignable",
        "BlueprintPure",
        "BlueprintType",
        "NotBlueprintType",
        # Instance
        "Instanced",
        "DuplicateTransient",
        "Transient",
        # Network
        "Replicated",
        "ReplicatedUsing",
        # Config
        "Config",
        "GlobalConfig",
        # Other
        "SaveGame",
        "NoClear",
        "NoExport",
        "Interp",
        "NonTransactional",
        "ExposeOnSpawn",
        "AllowPrivateAccess",
        "Deprecated",
        "AdvancedDisplay",
        "Protected",
        "Meta",
        "Category",
        "Ref",
        "SubobjectReference",
    }
)


def sanitize_identifier(name: str, fallback: str = "_unnamed") -> str:
    """Convert UE pin name/variable name to a valid C++ identifier.

    Rules:
    1. Spaces -> underscores ("Target Touch UI" -> "Target_Touch_UI")
    2. Remove illegal characters (keep only letters, digits, underscores)
    3. Starts with digit -> prefix _ ("123Var" -> "_123Var")
    4. Empty string / None -> fallback

    Args:
        name: Raw name (may contain spaces, special characters)
        fallback: Fallback value when sanitized result is empty

    Returns:
        Valid C++ identifier

    Examples:
        >>> sanitize_identifier("Target Touch UI")
        'Target_Touch_UI'
        >>> sanitize_identifier("MyVar@#$")
        'MyVar'
        >>> sanitize_identifier("123Var")
        '_123Var'
        >>> sanitize_identifier("")
        '_unnamed'
        >>> sanitize_identifier(None, "_fallback")
        '_fallback'
        >>> sanitize_identifier("Left / Right")
        'Left__Right'
        >>> sanitize_identifier("Primary Thumbstick")
        'Primary_Thumbstick'
    """
    if not name:
        return fallback

    # 1. Spaces -> underscores
    cleaned = name.replace(" ", "_")

    # 2. Remove illegal characters (keep only letters, digits, underscores)
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", cleaned)

    # 3. Starts with digit -> prefix _
    if cleaned and cleaned[0].isdigit():
        cleaned = "_" + cleaned

    # 4. Empty string -> default name
    if not cleaned:
        return fallback

    return cleaned


def sanitize_string_literal(value: str) -> str:
    """Sanitize value for use in C++ string literals / TEXT().

    Escapes backslashes, double quotes, newlines, carriage returns, and tabs to prevent injection.
    Output can be directly embedded in TEXT("...") or "...".

    Args:
        value: Raw string value

    Returns:
        Escaped string, safe for embedding in C++ string literals

    Examples:
        >>> sanitize_string_literal('Hello "World"')
        'Hello \\\\"World\\\\"'
        >>> sanitize_string_literal('C:\\\\path')
        'C:\\\\\\\\path'
        >>> sanitize_string_literal('line1\\nline2')
        'line1\\\\nline2'
        >>> sanitize_string_literal('tab\\there')
        'tab\\\\there'
        >>> sanitize_string_literal('cr\\rhere')
        'cr\\\\rhere'
        >>> sanitize_string_literal('null\\x00byte')
        'null\\\\0byte'
    """
    if value is None:
        return ""

    result = value
    # Backslashes must be escaped first (otherwise subsequent escape backslashes would be double-escaped)
    result = result.replace("\\", "\\\\")
    # Double quotes
    result = result.replace('"', '\\"')
    # null bytes
    result = result.replace("\x00", "\\0")
    # Newlines
    result = result.replace("\n", "\\n")
    # Carriage returns
    result = result.replace("\r", "\\r")
    # Tabs
    result = result.replace("\t", "\\t")

    return result


def sanitize_uproperty_marks(marks: Optional[List[str]]) -> List[str]:
    """Sanitize UPROPERTY specifier list.

    Only keeps valid specifiers from the whitelist, filtering dangerous content.
    Empty value or None returns empty list.

    Args:
        marks: List of UPROPERTY specifier strings

    Returns:
        Filtered list of valid specifiers

    Examples:
        >>> sanitize_uproperty_marks(["EditAnywhere", "BlueprintReadWrite"])
        ['EditAnywhere', 'BlueprintReadWrite']
        >>> sanitize_uproperty_marks(["EditAnywhere", "INJECTED_CODE", "Transient"])
        ['EditAnywhere', 'Transient']
        >>> sanitize_uproperty_marks(None)
        []
        >>> sanitize_uproperty_marks([])
        []
        >>> sanitize_uproperty_marks(["EditAnywhere", "EditAnywhere"])
        ['EditAnywhere']
    """
    if not marks:
        return []

    result: List[str] = []
    for mark in marks:
        if not mark or not isinstance(mark, str):
            continue
        # Exact match with whitelist (case-sensitive, UE specifiers are PascalCase)
        if mark in _UPROPERTY_SPECIFIER_WHITELIST:
            if mark not in result:
                result.append(mark)
        else:
            logger.debug(f"Filtered invalid UPROPERTY specifier: {mark!r}")

    return result


def sanitize_category(category: str) -> str:
    """Sanitize UPROPERTY Category string.

    Removes quotes, backslashes, newlines and other dangerous characters,
    keeping only letters, digits, spaces, and underscores.
    Output can be directly embedded in Category = "...".

    Args:
        category: Raw Category string

    Returns:
        Sanitized Category string

    Examples:
        >>> sanitize_category('My "Category"')
        'My Category'
        >>> sanitize_category('C:\\\\path/to')
        'Cpathto'
        >>> sanitize_category("line\\nbreak")
        'linebreak'
        >>> sanitize_category('  Trimmed  ')
        'Trimmed'
        >>> sanitize_category('Valid_Category 123')
        'Valid_Category 123'
    """
    if not category:
        return ""

    # Remove quotes (prevent escaping out of Category = "...")
    result = category.replace('"', "").replace("'", "")
    # Remove backslashes
    result = result.replace("\\", "")
    # Remove newlines and carriage returns
    result = result.replace("\n", "").replace("\r", "")
    # Remove tabs
    result = result.replace("\t", " ")
    # Keep only letters, digits, spaces, underscores
    result = re.sub(r"[^A-Za-z0-9 _]", "", result)
    # Compress consecutive spaces
    result = re.sub(r" +", " ", result)
    # Strip leading/trailing spaces
    result = result.strip()

    return result


__all__ = [
    "sanitize_identifier",
    "sanitize_string_literal",
    "sanitize_uproperty_marks",
    "sanitize_category",
]
