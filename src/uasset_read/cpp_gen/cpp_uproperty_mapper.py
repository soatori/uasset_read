"""
CPF property flag -> UPROPERTY specifier mapping module.

Provides conversion from CPF flag bits to UPROPERTY macro specifiers.
Per D-04: CPF flags map directly to UPROPERTY specifiers.

Exports:
    CPF_TO_UPROPERTY_MAP: CPF flag to UPROPERTY specifier mapping
    cpf_flags_to_uproperty_marks: CPF flag -> UPROPERTY specifier list conversion function
"""

import logging
from typing import List, Tuple

from uasset_read.constants import (
    CPF_Edit,
    CPF_BlueprintVisible,
    CPF_BlueprintReadOnly,
    CPF_InstancedReference,
    CPF_BlueprintAssignable,
    CPF_BlueprintCallable,
    CPF_Net,
    CPF_Transient,
    CPF_DuplicateTransient,
    CPF_Config,
    CPF_SaveGame,
    CPF_NoClear,
    CPF_ExposeOnSpawn,
    CPF_Interp,
    CPF_RepNotify,
    CPF_Deprecated,
    CPF_AdvancedDisplay,
    CPF_Protected,
)

logger = logging.getLogger(__name__)

# ============================================================================
# CPF flag -> UPROPERTY specifier mapping
# D-04: Combined check mapping sorted by priority
# ============================================================================

# Mapping format: (check_flags, result_marks, is_combined_check)
# - is_combined_check=True: All check_flags must be set to trigger
# - is_combined_check=False: Any check_flags set triggers
# Order matters: more specific combined checks come first

_CPF_UPROPERTY_RULES: List[Tuple[int, List[str], bool]] = [
    # Single flag check (in UE UPROPERTY documentation order)
    (CPF_Edit, ["EditAnywhere"], False),
    (CPF_BlueprintReadOnly, ["BlueprintReadOnly"], False),
    (CPF_BlueprintVisible, ["BlueprintReadWrite"], False),
    (CPF_InstancedReference, ["Instanced"], False),
    (CPF_BlueprintAssignable, ["BlueprintAssignable"], False),
    (CPF_BlueprintCallable, ["BlueprintCallable"], False),
    (CPF_Net, ["Replicated"], False),
    (CPF_Transient, ["Transient"], False),
    (CPF_DuplicateTransient, ["DuplicateTransient"], False),
    (CPF_Config, ["Config"], False),
    (CPF_SaveGame, ["SaveGame"], False),
    (CPF_NoClear, ["NoClear"], False),
    (CPF_ExposeOnSpawn, ["ExposeOnSpawn"], False),
    (CPF_Interp, ["Interp"], False),
    (CPF_RepNotify, ["RepNotify"], False),
    (CPF_Deprecated, ["Deprecated"], False),
    (CPF_AdvancedDisplay, ["AdvancedDisplay"], False),
    (CPF_Protected, ["Protected"], False),
]

# CPF_Net maps to UPROPERTY Replicated specifier


def cpf_flags_to_uproperty_marks(cpf_flags: int, is_component: bool = False) -> List[str]:
    """
    Convert CPF flag bits to UPROPERTY specifier list.

    Converts CPF flags to UPROPERTY macro specifiers according to mapping rules.
    For components, automatically adds default specifiers if no explicit visibility flags are set.

    Args:
        cpf_flags: CPF property flag bit mask (from .uasset parsing)
        is_component: Whether this is a component property (affects default specifiers)

    Returns:
        List of UPROPERTY specifier strings

    Examples:
        >>> from uasset_read.constants import CPF_Edit, CPF_BlueprintVisible
        >>> cpf_flags_to_uproperty_marks(CPF_Edit | CPF_BlueprintVisible)
        ['EditAnywhere', 'BlueprintReadWrite']
        >>> cpf_flags_to_uproperty_marks(0)
        []
        >>> cpf_flags_to_uproperty_marks(CPF_InstancedReference)
        ['Instanced']
    """
    # T-056-02: Validate flag range
    if cpf_flags < 0:
        logger.warning(f"Invalid CPF flags (negative): {cpf_flags}")
        return []

    # CPF flags are 64-bit unsigned integers
    if cpf_flags >= (1 << 64):
        logger.warning(f"CPF flags out of 64-bit range: {cpf_flags}")
        cpf_flags = cpf_flags & ((1 << 64) - 1)

    marks: List[str] = []

    # Iterate mapping rules
    for check_flags, result_marks, is_combined in _CPF_UPROPERTY_RULES:
        if is_combined:
            # Combined check: all flags must be set
            if (cpf_flags & check_flags) == check_flags:
                for mark in result_marks:
                    if mark not in marks:
                        marks.append(mark)
        else:
            # Single flag check
            if cpf_flags & check_flags:
                for mark in result_marks:
                    if mark not in marks:
                        marks.append(mark)

    # Component default specifiers: UE SCS component default behavior
    # If component and no explicit visibility/edit flags, add VisibleAnywhere + BlueprintReadOnly
    if is_component:
        has_edit_flag = any(m in marks for m in ["EditAnywhere", "EditInstanceOnly", "EditDefaultsOnly"])
        has_visible_flag = any(m in marks for m in ["VisibleAnywhere", "VisibleInstanceOnly", "VisibleDefaultsOnly"])

        # If no edit or visible flags, add default VisibleAnywhere + BlueprintReadOnly
        if not has_edit_flag and not has_visible_flag:
            marks.insert(0, "VisibleAnywhere")

        # Components are typically read-only (managed by blueprint)
        has_blueprint_access = any(m in marks for m in ["BlueprintReadWrite", "BlueprintReadOnly", "BlueprintCallable"])
        if not has_blueprint_access:
            marks.append("BlueprintReadOnly")

    return marks


# ============================================================================
# Export list
# ============================================================================

# Expose rules list for external use (read-only)
CPF_TO_UPROPERTY_MAP = _CPF_UPROPERTY_RULES

__all__ = [
    "CPF_TO_UPROPERTY_MAP",
    "cpf_flags_to_uproperty_marks",
    "uproperty_mark_to_cpf",
]
