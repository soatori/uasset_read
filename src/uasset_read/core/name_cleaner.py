"""Name cleaning heuristics for Blueprint identifiers.

Strips GUID suffixes, K2Node prefixes, CallFunc patterns, and other
auto-generated noise from Blueprint names to improve readability.

Usage:
    from uasset_read.core.name_cleaner import NameCleaner

    cleaner = NameCleaner()
    cleaned = cleaner.clean("__CustomEvent_7A3B9C2D4E5F6789")
    # -> "CustomEvent"

    mapping = cleaner.clean_all(raw_names)
    # -> {raw_name: cleaned_name, ...}
"""

import re


# GUID/UUID suffix patterns (8-32 hex chars, or standard UUID format)
_GUID_SUFFIX = re.compile(r"_[0-9A-Fa-f]{8,32}$")
_UUID_SUFFIX = re.compile(
    r"_[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)

# K2Node prefix mapping: strip prefix and keep the meaningful part
_K2NODE_PREFIXES: dict[str, str] = {
    "K2Node_MacroInstance": "MacroInstance",
    "K2Node_Event": "Event",
    "K2Node_CallFunction": "CallFunction",
    "K2Node_VariableGet": "VariableGet",
    "K2Node_VariableSet": "VariableSet",
    "K2Node_IfThenElse": "IfThenElse",
    "K2Node_ForEachElementInEnum": "ForEachEnum",
    "K2Node_SwitchEnum": "SwitchEnum",
    "K2Node_SwitchInt": "SwitchInt",
    "K2Node_SwitchString": "SwitchString",
    "K2Node_DynamicCast": "DynamicCast",
    "K2Node_MakeArray": "MakeArray",
    "K2Node_MakeMap": "MakeMap",
    "K2Node_MakeSet": "MakeSet",
    "K2Node_Select": "Select",
    "K2Node_MultiGate": "MultiGate",
    "K2Node_DoOnce": "DoOnce",
    "K2Node_FlipFlop": "FlipFlop",
    "K2Node_Gate": "Gate",
    "K2Node_Reroute": "Reroute",
    "K2Node_Self": "Self",
    "K2Node_Knot": "Knot",
    "K2Node_PureActivateScripturalDelegate": "Delegate",
    "K2Node_SetMembers": "SetMembers",
    "K2Node_SpawnActorFromClass": "SpawnActor",
    "K2Node_SetTimer": "SetTimer",
    "K2Node_RemoveTimer": "RemoveTimer",
    "K2Node_CompareBool": "CompareBool",
    "K2Node_ForEachLoop": "ForEachLoop",
    "K2Node_ForEachLoopWithBreak": "ForEachLoop",
    "K2Node_EnumEquals": "EnumEquals",
    "K2Node_EnumNotEquals": "EnumNotEquals",
    "K2Node_DataTableRowVector": "DataTableRow",
    "K2Node_DataTableRowName": "DataTableRow",
}

# CallFunc pattern: CallFunc_ClassName_FunctionName_ReturnValue
_CALLFUNC_PATTERN = re.compile(
    r"^CallFunc_([A-Za-z0-9]+)_([A-Za-z0-9]+)(_ReturnValue)?$"
)

# Temp variable patterns
_TEMP_VAR_PATTERNS = [
    re.compile(r"^TEMP_([A-Za-z0-9_]+)$"),
    re.compile(r"^TempVar_([A-Za-z0-9_]+)$"),
]

# __ prefixed auto-generated names
_AUTOGEN_PREFIX = re.compile(r"^__([A-Za-z0-9]+)_[0-9A-Fa-f]{4,}$")

# ExecuteUbergraph pattern — match base name after GUID strip
_EXEC_PREFIX = re.compile(r"^ExecuteUbergraph_([A-Za-z0-9_]+)$")


class NameCleaner:
    """Blueprint name cleaning heuristics.

    Strips auto-generated noise from Blueprint identifiers to produce
    human-readable names. Maintains a mapping table from original to
    cleaned names for traceability.
    """

    def clean(self, name: str) -> str:
        """Clean a single name by applying heuristic rules.

        Rules applied in order:
        1. Strip K2Node prefixes (with GUID handling)
        2. Strip __ prefix auto-generated patterns
        3. Normalize CallFunc patterns
        4. Clean temp variable names
        5. Strip GUID/UUID suffixes (generic)
        6. Simplify ExecuteUbergraph names (after GUID strip)

        Args:
            name: Raw Blueprint identifier

        Returns:
            Cleaned name (or original if no cleaning applied)
        """
        if not name:
            return name

        # 1. Strip K2Node prefix (before GUID strip to handle K2Node_Foo_Guid)
        for prefix, replacement in _K2NODE_PREFIXES.items():
            if name.startswith(prefix):
                rest = name[len(prefix):]
                # If rest is empty (exact prefix match), return replacement
                if not rest:
                    return replacement
                # If rest starts with _, extract the suffix
                if rest.startswith("_"):
                    suffix = rest[1:]
                    # Strip GUID from suffix
                    suffix = _GUID_SUFFIX.sub("", suffix)
                    suffix = _UUID_SUFFIX.sub("", suffix)
                    if suffix:
                        return f"{replacement}_{suffix}"
                    return replacement
                return replacement

        # 2. Strip __ prefix auto-generated pattern
        m = _AUTOGEN_PREFIX.match(name)
        if m:
            return m.group(1)

        # 3. Normalize CallFunc pattern
        m = _CALLFUNC_PATTERN.match(name)
        if m:
            class_name = m.group(1)
            func_name = m.group(2)
            return f"{class_name}::{func_name}"

        # 4. Clean temp variable names
        for pat in _TEMP_VAR_PATTERNS:
            m = pat.match(name)
            if m:
                return m.group(1)

        # 5. Strip GUID suffix (generic) — must happen before ExecuteUbergraph
        cleaned = _GUID_SUFFIX.sub("", name)
        if cleaned != name:
            # Check if this reveals an ExecuteUbergraph pattern
            m = _EXEC_PREFIX.match(cleaned)
            if m:
                return f"ExecuteUbergraph_{m.group(1)}"
            return cleaned

        cleaned = _UUID_SUFFIX.sub("", name)
        if cleaned != name:
            m = _EXEC_PREFIX.match(cleaned)
            if m:
                return f"ExecuteUbergraph_{m.group(1)}"
            return cleaned

        # 6. Simplify ExecuteUbergraph (no GUID to strip)
        m = _EXEC_PREFIX.match(name)
        if m:
            return f"ExecuteUbergraph_{m.group(1)}"

        return name

    def clean_all(self, names: list[str] | set[str]) -> dict[str, str]:
        """Clean a collection of names, returning a mapping.

        Args:
            names: Collection of raw names

        Returns:
            Dict mapping raw_name -> cleaned_name
        """
        return {name: self.clean(name) for name in names}

