"""src/uasset_read/models/diagnostics.py — Diagnostic data models.

Structured diagnostics emitted during parsing: stable-code structured
records and PackageDocument diagnostics.
"""

from dataclasses import dataclass, asdict
from typing import Any, Literal


# Stable diagnostic codes for structured warnings
DIAGNOSTIC_CODE_INVALID_SERIAL_SIZE = "invalid_serial_size"
DIAGNOSTIC_CODE_INVALID_SERIAL_OFFSET = "invalid_serial_offset"

DiagnosticReason = Literal[
    "bulk_expected",
    "editor_only",
    "known_unimplemented",
    "recovered_corruption",
    "conservative_complete",
    "unexpected",
    "schema_required",
]


@dataclass(frozen=True)
class TrailingContext:
    """Identity context for trailing-reason classification.

    class_name alone drives every current rule; object_name/outer_name
    exist so identity-sensitive rules (e.g. AnimBlueprint CDO detection,
    owned by a sibling plan) can be added without another signature change.
    """

    class_name: str
    object_name: str = ""
    outer_name: str | None = None


@dataclass
class Diagnostic:
    """Structured diagnostic for the PackageDocument."""

    severity: Literal["info", "warning", "error", "critical"] = "warning"
    code: str = ""
    message: str = ""
    stage: str = ""  # "package.summary", "properties.tagged", "objects.export", etc.
    object_id: str | None = None  # "export:3"
    offset: int | None = None
    size: int | None = None
    effect: Literal["semantic_loss", "data_loss", "parse_failure", "recovery"] | None = None
    recoverable: bool = True
    fallback: str | None = None  # fallback action for structured diagnostics
    reason: DiagnosticReason | None = None  # optional classification

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # recoverable is always included (False is explicit, True is default)
        return {k: v for k, v in d.items() if v is not None and (k == "recoverable" or (not isinstance(v, bool) or v))}


def diagnostic_summary(item: Diagnostic) -> dict[str, Any]:
    """Common summary diagnostic (v4): detailed fields never ride along.

    ``count`` is the number of summarized occurrences; current producers emit
    one Diagnostic per occurrence, so it is always 1. Detail fields live in
    ``debug.diagnostic_details`` keyed by the summary's index.
    """
    out: dict[str, Any] = {
        "severity": item.severity,
        "code": item.code,
        "message": item.message,
        "stage": item.stage,
        "count": 1,
    }
    if item.object_id is not None:
        out["object_id"] = item.object_id
    if item.effect is not None:
        out["effect"] = item.effect
    return out


def diagnostic_detail(item: Diagnostic, index: int) -> dict[str, Any]:
    """Debug evidence for ``diagnostics[index]``: offset/size/reason/fallback."""
    out: dict[str, Any] = {"index": index}
    if item.offset is not None:
        out["offset"] = item.offset
    if item.size is not None:
        out["size"] = item.size
    if item.reason is not None:
        out["reason"] = item.reason
    if item.fallback is not None:
        out["fallback"] = item.fallback
    out["recoverable"] = item.recoverable
    return out


def make_diagnostic(
    code: str,
    message: str,
    stage: str,
    *,
    object_id: str | None = None,
    severity: Literal["info", "warning", "error", "critical"] = "warning",
    effect: Literal["semantic_loss", "data_loss", "parse_failure", "recovery"] | None = "semantic_loss",
    reason: DiagnosticReason | None = None,
    size: int | None = None,
) -> Diagnostic:
    """Build a Diagnostic with common defaults."""
    return Diagnostic(
        severity=severity,
        code=code,
        message=message,
        stage=stage,
        object_id=object_id,
        effect=effect,
        reason=reason,
        size=size,
    )


_EDITOR_ONLY_PREFIXES = (
    "MetaData",
    "PackageMetaData",
    "K2Node_",
    "EdGraph",
    "Blueprint",
    "WidgetBlueprint",
    "AnimBlueprint",
    "Function",
    "SoundNode",
)

_BULK_CLASSES = frozenset(
    {
        "FontFace",
        "Font",
        "SoundWave",
        "SoundCue",
        "RawAudio",
    }
)

_BULK_PREFIXES = ("Texture",)

_KNOWN_UNIMPLEMENTED_CLASSES = frozenset(
    {
        "Skeleton",
        "PhysicsAsset",
        "SkeletalBodySetup",
        "StaticMesh",
        "StaticMeshDescriptionBulkData",
        "UserDefinedStruct",
        # Native-payload reader gaps disclosed as opaque (2026-09-23 plan).
        "Level",
        "Model",
        "Polys",
        "World",
        "BodySetup",
        "NavCollision",
        "UserDefinedEnum",
        "PoseAsset",
        "MovieScene",
    }
)

_KNOWN_UNIMPLEMENTED_PREFIXES = (
    "NiagaraNode",
    "NiagaraScript",
    "NiagaraEmitter",
    "NiagaraSystem",
    "BlendSpace",
    "Material",
    "Anim",
)

_ANIM_GENERATED_DATA_OBJECTS = frozenset(
    {
        "AnimBlueprintGeneratedConstantData",
        "AnimBlueprintGeneratedMutableData",
    }
)


def classify_trailing_reason(context: TrailingContext | str) -> DiagnosticReason:
    """Map export trailing-bytes context to a closed reason value.

    Accepts a bare class name (str) as shorthand for TrailingContext.
    Bulk-data classes are checked first so names such as ``FontFace`` are
    never swallowed by a broader prefix rule. Identity rules keyed on
    object_name/outer_name/roles slot in after the class-prefix tables,
    immediately before the fallback return.
    """
    if isinstance(context, str):
        context = TrailingContext(class_name=context)
    cn = context.class_name
    if cn in _BULK_CLASSES or any(cn.startswith(p) for p in _BULK_PREFIXES):
        return "bulk_expected"
    if any(cn.startswith(p) for p in _EDITOR_ONLY_PREFIXES):
        return "editor_only"
    if cn in _KNOWN_UNIMPLEMENTED_CLASSES or any(cn.startswith(p) for p in _KNOWN_UNIMPLEMENTED_PREFIXES):
        return "known_unimplemented"
    # Identity-rule slot: object_name / outer_name / roles evaluated here
    # (sibling AnimBlueprint plan). Empty by design in this plan.
    if context.object_name.startswith("Default__") and context.class_name.endswith("_C"):
        return "known_unimplemented"
    if (
        context.object_name in _ANIM_GENERATED_DATA_OBJECTS
        and context.outer_name is not None
        and context.outer_name.endswith("_C")
    ):
        return "known_unimplemented"
    return "unexpected"
