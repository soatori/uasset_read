"""src/uasset_read/models/diagnostics.py — Diagnostic data models.

Structured diagnostics emitted during parsing: stable-code structured
records and PackageDocument diagnostics.
"""

from dataclasses import dataclass, asdict
from typing import Any, Literal


# Stable diagnostic codes for structured warnings
DIAGNOSTIC_CODE_INVALID_SERIAL_SIZE = "invalid_serial_size"
DIAGNOSTIC_CODE_INVALID_SERIAL_OFFSET = "invalid_serial_offset"
DIAGNOSTIC_CODE_INVALID_SCRIPT_SERIALIZATION_OFFSET = "invalid_script_serialization_offset"

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
    offset: int | None = None,
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
        offset=offset,
    )


# Trailing-classifier provenance annotations (rules:
# docs/designs/2026-10-05-undecoded-classification-rules.md §4). Tags per table entry:
#   [engine] engine basis (UE source class/mechanism); [gap] gap record (design doc /
#   manifest fixture_gaps key); [heur] heuristic (prefix/identity semantics).
#   TODO(T2) = provenance still to confirm in the T2 audit; backfill lands with T4.
_EDITOR_ONLY_PREFIXES = (
    "MetaData",  # [heur] package metadata = editor annotation semantics (2026-09-15 plan seed sweep).
    "PackageMetaData",  # [heur] metadata container export (2026-09-15 plan seed sweep).
    "K2Node_",  # [engine] blueprint graph nodes; BlueprintGraph module is editor-only (Engine/Source/Editor/BlueprintGraph).
    "EdGraph",  # [engine] graph/pin serialization is WITH_EDITOR / !IsFilterEditorOnly; cooked builds drop it (issue-521-b0-gate-decision.md: EdGraphNode.cpp:214, EdGraphPin.cpp:1859).
    "Blueprint",  # [engine] UBlueprint carries WITH_EDITORONLY_DATA regions (Engine/.../Engine/Blueprint.h:430ff); prefix also matches BlueprintGeneratedClass.
    "WidgetBlueprint",  # [heur] UMG blueprint subclass; same editor-graph semantics as "Blueprint".
    "AnimBlueprint",  # [heur] anim blueprint subclass; prefix also matches AnimBlueprintGeneratedClass (identity rules below).
    "Function",  # [heur] corpus class is literally "Function" (BP function/graph exports; T2 inventory: 230 / 141,400 B across 11 samples, every outer an export); prefix semantics = blueprint graph/library objects.
    "SoundNode",  # [engine] USoundNode::Serialize reads FStripDataFlags + GraphNode under WITH_EDITORONLY_DATA, stripped when editor data is stripped (SoundNode.cpp:44-52; peer corroboration: 2026-09-23 trailer-reason plan Peer coverage table).
)

_BULK_CLASSES = frozenset(
    {
        "FontFace",  # [engine] face bytes live in FFontFaceData/bulk data, not property serialization (Engine/.../Engine/FontFace.h:134).
        "Font",  # [gap] bulk/stream payload class (2026-09-15 plan: bulk_expected taxonomy + seed sweep).
        "SoundWave",  # [engine] raw-audio payload rides BulkData buffers (Engine/.../SoundWave.h includes Serialization/BulkData.h, FBulkDataBuffer).
        "SoundCue",  # [gap] bulk/stream payload class (2026-09-15 plan seed sweep).
        "RawAudio",  # [heur] name semantics: raw audio bytes = bulk stream, not properties.
    }
)

_BULK_PREFIXES = (
    "Texture",  # [engine] UTexture family stores bulk mip payloads outside properties (Engine/.../Texture2D.h includes BulkData.h; rationale: quality-review-fixes spec, commit a00a0bcb).
)

_KNOWN_UNIMPLEMENTED_CLASSES = frozenset(
    {
        "Skeleton",  # [gap] 2026-09-15 plan: ALS_Mannequin_Skeleton seed; RefSkeleton deep parse deferred to backlog.
        "PhysicsAsset",  # [gap] 2026-09-15 plan: seed sweep; deep parse out of scope.
        "SkeletalBodySetup",  # [gap] 2026-09-15 plan: seed sweep; deep parse out of scope.
        "StaticMesh",  # [gap] 2026-09-15 plan: seed sweep; deep parse out of scope.
        "StaticMeshDescriptionBulkData",  # [gap] 2026-09-15 plan: seed sweep; deep parse out of scope.
        "UserDefinedStruct",  # [gap] 2026-09-15 plan: seed sweep; deep parse out of scope.
        # Native-payload reader gaps disclosed as opaque ([gap] 2026-09-23 trailer-reason
        # plan, docs/designs/archive/2026-09-23-trailer-reason-quality-gate-plan.md,
        # team-lead ruling 2026-09-23; per-entry peers below):
        "Level",  # [gap] peer corroboration: UAssetAPI LevelExport (native tail then explicit TODO).
        "Model",  # [gap] peer corroboration: CUE4Parse UModel native Deserialize tail.
        "Polys",  # [gap] peer corroboration: CUE4Parse UPolys native Deserialize tail.
        "World",  # [gap] peer corroboration: CUE4Parse UWorld native Deserialize tail.
        "BodySetup",  # [gap] peer corroboration: CUE4Parse UBodySetup (BodySetupGuid + cooked flag tail).
        "NavCollision",  # [gap] peer corroboration: CUE4Parse UNavCollision (magic/version/guid/cooked header).
        "UserDefinedEnum",  # [gap] peer corroboration: UAssetAPI EnumExport; CUE4Parse leaves DisplayNameMap undecoded.
        "PoseAsset",  # [gap] no peer parser decodes this type (2026-09-23 trailer-reason plan).
        "MovieScene",  # [gap] no peer parser decodes this type (2026-09-23 trailer-reason plan).
    }
)

_KNOWN_UNIMPLEMENTED_PREFIXES = (
    # [gap] Niagara family: deep Niagara parse deferred by the 2026-09-15 plan backlog;
    # native pin-tail layout audited against UE source in issue-521-b0-gate-decision.md
    # (UNiagaraNode : UEdGraphNode; pin path WITH_EDITOR, dropped when cooked):
    "NiagaraNode",  # [gap] 2026-09-15 plan backlog; UE audit: issue-521-b0-gate-decision.md.
    "NiagaraScript",  # [gap] 2026-09-15 plan backlog; UE audit: issue-521-b0-gate-decision.md.
    "NiagaraEmitter",  # [gap] 2026-09-15 plan backlog; UE audit: issue-521-b0-gate-decision.md.
    "NiagaraSystem",  # [gap] 2026-09-15 plan backlog; UE audit: issue-521-b0-gate-decision.md.
    # [gap] quality-review-fixes spec (docs/compose/spec/quality-review-fixes.md, commit a00a0bcb):
    "BlendSpace",  # [gap] trailing sample data / axes not specialized (quality-review-fixes spec).
    "Material",  # [gap] expression graph / instance params not deeply decoded (MaterialInstance* folded here by 4a4628ac; quality-review-fixes spec).
    "Anim",  # [gap] short fixed tails, body not specialized (AnimSequence/AnimMontage/AnimComposite folded into this prefix by 4a4628ac; quality-review-fixes spec; prefix also catches AnimGraphNode_*).
)

_ANIM_GENERATED_DATA_OBJECTS = frozenset(
    {
        # [gap] object names fixed by the 2026-09-23 AnimBlueprint trailer plan
        # (docs/designs/archive/2026-09-23-animblueprint-native-trailer-plan.md evidence table).
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
    # Identity-rule slot: object_name / outer_name / roles evaluated here.
    # [gap] Both rules are fixed by the 2026-09-23 AnimBlueprint trailer plan
    # (docs/designs/archive/2026-09-23-animblueprint-native-trailer-plan.md):
    if context.object_name.startswith("Default__") and context.class_name.endswith("_C"):
        # [gap] CDO identity: Default__ instance of a *_C generated class (3 fixtures / 621,736 B).
        return "known_unimplemented"
    if (
        context.object_name in _ANIM_GENERATED_DATA_OBJECTS
        and context.outer_name is not None
        and context.outer_name.endswith("_C")
    ):
        # [gap] generated-data identity: named object outered to the *_C class (5 ScriptStruct trailers / 70,532 B).
        return "known_unimplemented"
    # [heur] closed-set fallback: anything unmatched stays the CI attention signal
    # (2026-09-15 plan taxonomy: "unexpected = does not fit the above — CI attention").
    return "unexpected"
