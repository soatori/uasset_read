"""Shared projection records and helper contracts (plan Task 10A / R3).

Document-boundary projection records stay frozen dataclasses. Projectors
never reopen package bytes and never invoke Unreal Editor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from uasset_read.models.byte_ranges import ByteRegion
from uasset_read.models.diagnostics import Diagnostic
from uasset_read.models.document import PackageDocument
from uasset_read.models.object_model import ObjectRecord

ProjectionStatus = Literal["translated", "represented", "untranslated", "unavailable"]


@dataclass(frozen=True)
class SidecarRecord:
    """Schema-ready external sidecar reference (not materialized in R3)."""

    path: str
    size: int
    sha256: str
    reason: Literal["size_limit", "unsafe_payload"]
    source_range: ByteRegion | None
    projection_kind: str | None


@dataclass(frozen=True)
class ProjectionRecord:
    """One type-aware embedded projection derived from the same PackageDocument."""

    kind: str
    source_object_id: str
    media_type: str
    content: str | dict[str, Any] | None
    embedded: bool
    status: ProjectionStatus
    completeness: float | None
    dependencies: list[str]
    diagnostics: list[Diagnostic] = field(default_factory=list)
    external: SidecarRecord | None = None


def semantic_dict(obj: ObjectRecord) -> dict[str, Any]:
    """The projected semantic dict for an object, or ``{}`` when absent."""
    semantic = obj.semantic
    return semantic if isinstance(semantic, dict) else {}


def dependency_ids(document: PackageDocument, object_id: str) -> list[str]:
    """Return deterministic outgoing relation targets for one source object."""
    return sorted(
        {
            relation.to_id
            for relation in document.relations
            if relation.from_id == object_id and relation.to_id != object_id
        }
    )


def matches_family(
    obj: ObjectRecord,
    asset_kinds: tuple[str, ...] | frozenset[str] | set[str],
    class_names: tuple[str, ...] | frozenset[str] | set[str],
) -> bool:
    """Kind-first family match.

    When semantic ``kind`` is present it is the sole owner key — class_name
    never steals an object whose kind already belongs to another family.
    Class-name fallback applies only when no semantic kind was projected.
    """
    semantic = obj.semantic
    if isinstance(semantic, dict):
        kind = semantic.get("kind")
        if isinstance(kind, str) and kind:
            return kind in asset_kinds
    return (obj.class_name or "") in class_names


def _diagnostic_code(item: object) -> str | None:
    if hasattr(item, "code"):
        code = getattr(item, "code", None)
        return code if isinstance(code, str) else None
    if isinstance(item, dict):
        code = item.get("code")
        return code if isinstance(code, str) else None
    return None


def _completeness_label(
    status: str,
    completeness: float | None,
    diagnostics: list[Any] | None = None,
) -> str:
    """Map internal completeness ratio + status to the v3 contract enum.

    Schema values: complete | partial | opaque | unavailable | failed.
    Independent of migration ``status``; never overclaims ``complete`` when
    the projector did not measure a full ratio.

    - ``failed``: diagnostics carry a projection-failure code (e.g. render_failed).
    - ``unavailable``: status unavailable without a failure code (source absent).
    - ``complete``: only when a measured ratio is ``>= 1.0``.
    - ``partial``: measured ``0 < ratio < 1``, or represented/translated
      without a measured ratio (capability not proven complete).
    - ``opaque``: source information exists but was not mapped
      (``untranslated`` with ratio None/0).
    """
    codes = [_diagnostic_code(d) for d in diagnostics or ()]
    if any(code is not None and "failed" in code for code in codes):
        return "failed"
    if status == "unavailable":
        return "unavailable"
    if completeness is not None and completeness >= 1.0:
        return "complete"
    if completeness is not None and completeness > 0:
        return "partial"
    # completeness is None or 0 — never emit complete.
    if status == "untranslated":
        return "opaque"
    if status in {"translated", "represented"}:
        return "partial"
    return "unavailable"


def projection_to_dict(record: ProjectionRecord) -> dict[str, Any]:
    """JSON-safe projection record for the v3 contract envelope.

    Contract rules (package_document_v3.schema.json):
    - ``completeness`` is the capability enum string, not a float.
    - Embedded records carry ``content`` + ``provenance`` and omit ``external``.
    - External records carry ``external`` and omit ``content``.
    - Unknown keys (``source_range`` on ProjectionRecord) are never emitted.
    """
    out: dict[str, Any] = {
        "kind": record.kind,
        "source_object_id": record.source_object_id,
        "media_type": record.media_type,
        "embedded": record.embedded,
        "status": record.status,
        "completeness": _completeness_label(
            record.status, record.completeness, record.diagnostics
        ),
        "dependencies": list(record.dependencies),
        "diagnostics": [
            item.to_dict() if hasattr(item, "to_dict") else item for item in record.diagnostics
        ],
    }
    if record.embedded:
        out["content"] = record.content
        out["provenance"] = {
            "derived_from": [record.source_object_id, *record.dependencies],
            "generator": f"uasset_read.projections.{record.kind}",
        }
    else:
        external = record.external
        if external is None:
            raise ValueError(
                f"non-embedded projection {record.kind!r} for {record.source_object_id} "
                "requires an external sidecar record"
            )
        if external.source_range is None:
            raise ValueError(
                f"external projection {record.kind!r} for {record.source_object_id} "
                "requires a source range"
            )
        out["external"] = {
            "path": external.path,
            "size": external.size,
            "sha256": external.sha256,
            "reason": external.reason,
            "source_range": {
                "offset": external.source_range.start,
                "size": external.source_range.size,
            },
        }
    return out


def unavailable_records(
    object_id: str,
    pairs: tuple[tuple[str, str], ...],
    *,
    code: str,
    message: str,
    stage: str,
    dependencies: list[str] | None = None,
) -> list[ProjectionRecord]:
    """Build explicit unavailable records for a recognized-but-missing family."""
    from uasset_read.models.diagnostics import make_diagnostic

    deps = list(dependencies or [])
    return [
        ProjectionRecord(
            kind=kind,
            source_object_id=object_id,
            media_type=media_type,
            content=None,
            embedded=True,
            status="unavailable",
            completeness=None,
            dependencies=deps,
            diagnostics=[
                make_diagnostic(
                    code,
                    message,
                    stage,
                    object_id=object_id,
                )
            ],
        )
        for kind, media_type in pairs
    ]
