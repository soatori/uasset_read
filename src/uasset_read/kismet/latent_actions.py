"""Latent action detection and resume body inlining.

Detects common latent actions (Delay, MoveTo, etc.) and provides
utilities for inlining their resume bodies in decompiled output.

Latent actions are asynchronous Blueprint operations that suspend execution
and resume later. They compile to specific bytecode patterns involving
latent action delegates and resume nodes.
"""

from dataclasses import dataclass, field
from typing import Optional


# Known latent action class names (UE4/UE5)
_KNOWN_LATENT_ACTIONS: dict[str, str] = {
    "KismetSystemLibrary_Delay": "Delay",
    "KismetSystemLibrary_DelayAction": "Delay",
    "KismetSystemLibrary_DelayDuration": "Delay",
    "KismetSystemLibrary_DelayRealTime": "Delay (RealTime)",
    "KismetSystemLibrary_DelayRealTimeAction": "Delay (RealTime)",
    "AITypes_BlueprintPathFollowingComponent_FollowPathSegment": "FollowPathSegment",
    "AITypes_BlueprintPathFollowingComponent_MoveToLocation": "MoveToLocation",
    "AITypes_BlueprintPathFollowingComponent_MoveToActor": "MoveToActor",
    "AITypes_BlueprintPathFollowingComponent_SimpleMoveToLocation": "SimpleMoveToLocation",
    "AITypes_BlueprintPathFollowingComponent_SimpleMoveToActor": "SimpleMoveToActor",
    "GameplayStatics_SuggestProjectileVelocity_CustomArc": "SuggestProjectileVelocity",
    "GameplayStatics_PredictProjectilePath_ByTraceChannel": "PredictProjectilePath",
    "GameplayStatics_PredictProjectilePath_ByObjectType": "PredictProjectilePath",
    "GameplayStatics_PredictProjectilePath_ByRadius": "PredictProjectilePath",
    "PlayMontageAndWait": "PlayMontageAndWait",
    "AbilityAsync_WaitDelay": "WaitDelay",
    "AbilityAsync_WaitGameplayEvent": "WaitGameplayEvent",
    "AbilityAsync_WaitInputPress": "WaitInputPress",
    "AbilityAsync_WaitConfirmCancel": "WaitConfirmCancel",
    "AbilityAsync_WaitAbility Activate": "WaitAbilityActivate",
    "AbilityAsync_WaitAbilityEnd": "WaitAbilityEnd",
}


@dataclass
class LatentActionInfo:
    """Information about a detected latent action."""

    class_name: str
    """Original UE class name."""

    friendly_name: str
    """Human-readable name."""

    function_name: str
    """Function that creates the latent action (e.g. "Delay")."""

    resume_block: Optional[int] = None
    """Block ID where execution resumes after the latent action."""

    pin_values: dict[str, str] = field(default_factory=dict)
    """Extracted pin values (e.g. {"Duration": "2.0"})."""

    @property
    def is_known(self) -> bool:
        """True if this is a recognized latent action type."""
        return self.class_name in _KNOWN_LATENT_ACTIONS


@dataclass
class LatentActionResult:
    """Result of latent action detection."""

    latent_actions: list[LatentActionInfo] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.latent_actions)

    def get_by_type(self, friendly_name: str) -> list[LatentActionInfo]:
        """Get all latent actions matching a friendly name."""
        return [la for la in self.latent_actions if la.friendly_name == friendly_name]


def detect_latent_actions(expressions: list) -> LatentActionResult:
    """Detect latent action patterns in a list of expressions.

    Scans for function calls to known latent action classes and
    extracts their parameters.

    Args:
        expressions: List of KismetExpression objects

    Returns:
        LatentActionResult with detected latent actions
    """
    from uasset_read.kismet.expressions.functions import (
        EX_FinalFunction, EX_VirtualFunction,
        EX_LocalFinalFunction,
    )

    result = LatentActionResult()

    def _walk(expr) -> None:
        if expr is None:
            return

        # Check for latent action function calls
        if isinstance(expr, (EX_FinalFunction, EX_VirtualFunction, EX_LocalFinalFunction)):
            func_ref = getattr(expr, "FunctionReference", None)
            if func_ref and hasattr(func_ref, "member_name"):
                member_name = func_ref.member_name
                if member_name in _KNOWN_LATENT_ACTIONS:
                    # Extract pin values from parameters
                    pin_values: dict[str, str] = {}
                    args = getattr(expr, "Parameters", None) or []
                    for i, arg in enumerate(args):
                        # Try to get parameter name from context
                        pin_values[f"Param{i}"] = str(arg)[:50] if arg else ""

                    result.latent_actions.append(LatentActionInfo(
                        class_name=member_name,
                        friendly_name=_KNOWN_LATENT_ACTIONS[member_name],
                        function_name=member_name.split(".")[-1] if "." in member_name else member_name,
                        pin_values=pin_values,
                    ))

        # Recurse into child expressions
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

    return result


def format_latent_action_summary(result: LatentActionResult) -> str:
    """Format latent action detection results as a readable summary.

    Args:
        result: LatentActionResult from detect_latent_actions

    Returns:
        Formatted text summary
    """
    if not result.latent_actions:
        return "No latent actions detected."

    lines: list[str] = [f"Detected {result.count} latent action(s):", ""]

    for i, la in enumerate(result.latent_actions, 1):
        lines.append(f"  {i}. {la.friendly_name}")
        lines.append(f"     Class: {la.class_name}")
        if la.pin_values:
            lines.append(f"     Pins: {la.pin_values}")
        lines.append("")

    return "\n".join(lines)
