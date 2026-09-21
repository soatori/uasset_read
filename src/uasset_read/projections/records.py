"""Shared projection records and helper contracts (plan Task 10A / R3).

Document-boundary projection records stay frozen dataclasses. Projectors
never reopen package bytes and never invoke Unreal Editor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from uasset_read.models.byte_ranges import ByteRegion, project_region
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
    source_range: ByteRegion | None = None
    external: SidecarRecord | None = None


@runtime_checkable
class AssetProjector(Protocol):
    """Type-aware projector protocol. Match semantic kind, then class family."""

    asset_kinds: tuple[str, ...]

    def can_project(self, obj: ObjectRecord) -> bool: ...

    def project(
        self,
        document: PackageDocument,
        obj: ObjectRecord,
    ) -> list[ProjectionRecord]: ...


def dependency_ids(document: PackageDocument, object_id: str) -> list[str]:
    """Return deterministic outgoing relation targets for one source object."""
    return sorted(
        {
            relation.to_id
            for relation in document.relations
            if relation.from_id == object_id and relation.to_id != object_id
        }
    )


def projection_to_dict(record: ProjectionRecord) -> dict[str, Any]:
    """JSON-safe projection record for the canonical document envelope."""
    return {
        "kind": record.kind,
        "source_object_id": record.source_object_id,
        "media_type": record.media_type,
        "content": record.content,
        "embedded": record.embedded,
        "status": record.status,
        "completeness": record.completeness,
        "dependencies": list(record.dependencies),
        "diagnostics": [
            item.to_dict() if hasattr(item, "to_dict") else item for item in record.diagnostics
        ],
        "source_range": project_region(record.source_range),
        "external": None if record.external is None else {
            "path": record.external.path,
            "size": record.external.size,
            "sha256": record.external.sha256,
            "reason": record.external.reason,
            "source_range": project_region(record.external.source_range),
            "projection_kind": record.external.projection_kind,
        },
    }


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
