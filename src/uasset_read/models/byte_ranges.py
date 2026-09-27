"""Package-virtual byte ranges, physical source slices, and per-export scopes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class SourceSlice:
    source_id: str
    source_start: int
    size: int


@dataclass(frozen=True)
class ByteRegion:
    """One contiguous package-virtual range with optional physical mapping."""

    start: int
    size: int
    status: Literal["decoded", "opaque", "payload", "unavailable"]
    source_id: str = "package"
    source_start: int | None = None
    source_slices: tuple[SourceSlice, ...] = ()
    reason: str | None = None
    feature: str = ""
    payload_ref: str | None = None

    @property
    def end(self) -> int:
        return self.start + self.size

    @property
    def source_end(self) -> int | None:
        return None if self.source_start is None else self.source_start + self.size


# Canonical opaque-region type (Tasks 4/6/9). status must be "opaque".
OpaqueRegion = ByteRegion


def opaque_region(
    start: int,
    size: int,
    reason: str,
    *,
    source_id: str = "package",
    source_start: int | None = None,
    feature: str = "",
    payload_ref: str | None = None,
) -> ByteRegion:
    return ByteRegion(
        start=start,
        size=size,
        status="opaque",
        source_id=source_id,
        source_start=source_start,
        reason=reason,
        feature=feature,
        payload_ref=payload_ref,
    )


def project_region(region: ByteRegion | None) -> dict[str, Any] | None:
    if region is None:
        return None
    return {
        "start": region.start,
        "size": region.size,
        "end": region.end,
        "source_id": region.source_id,
        "source_start": region.source_start,
        "source_end": region.source_end,
        "source_slices": [
            {
                "source_id": item.source_id,
                "source_start": item.source_start,
                "size": item.size,
                "source_end": item.source_start + item.size,
            }
            for item in region.source_slices
        ],
        "status": region.status,
        "reason": region.reason,
        "feature": region.feature,
        "payload_ref": region.payload_ref,
    }


def region_from_source(
    source: Any,
    start: int,
    size: int,
    *,
    status: Literal["decoded", "opaque", "payload", "unavailable"],
    reason: str | None = None,
    feature: str = "",
    payload_ref: str | None = None,
) -> ByteRegion:
    mapped = source.map_range(start, size)
    slices = tuple(SourceSlice(*item) for item in mapped)
    single = len(slices) == 1
    return ByteRegion(
        start=start,
        size=size,
        status=status,
        source_id=slices[0].source_id if single else "composite",
        source_start=slices[0].source_start if single else None,
        source_slices=slices,
        reason=reason,
        feature=feature,
        payload_ref=payload_ref,
    )


@dataclass
class ByteScope:
    """Non-overlapping leaf coverage of one export serial range (virtual coords)."""

    scope_id: str
    start: int
    size: int
    leaves: list[ByteRegion] = field(default_factory=list)

    def validate_full_coverage(self) -> None:
        if not self.leaves:
            raise ValueError(f"{self.scope_id}: no accounting leaves")
        cursor = self.start
        for leaf in sorted(self.leaves, key=lambda item: item.start):
            if leaf.size <= 0 or leaf.start != cursor:
                raise ValueError(f"{self.scope_id}: gap/overlap at {cursor}")
            cursor = leaf.end
        if cursor != self.start + self.size:
            raise ValueError(f"{self.scope_id}: coverage ends at {cursor}")


@dataclass
class ByteAccounting:
    scopes: dict[str, ByteScope] = field(default_factory=dict)


def split_region_at_physical(
    region: ByteRegion,
    source: Any,
) -> list[ByteRegion]:
    """Split one virtual region into leaves that each map a single physical source."""
    if region.size <= 0:
        return []
    try:
        mapped = source.map_range(region.start, region.size)
    except Exception:
        return [region]
    leaves: list[ByteRegion] = []
    virtual = region.start
    for source_id, physical_start, size in mapped:
        leaves.append(
            ByteRegion(
                start=virtual,
                size=size,
                status=region.status,
                source_id=source_id,
                source_start=physical_start,
                source_slices=(SourceSlice(source_id, physical_start, size),),
                reason=region.reason,
                feature=region.feature,
                payload_ref=region.payload_ref,
            )
        )
        virtual += size
    if virtual != region.end and not leaves:
        return [region]
    return leaves


def tile_export_scope(
    scope_id: str,
    start: int,
    size: int,
    decoded: list[ByteRegion],
    source: Any,
    *,
    gap_reason: str = "unconsumed",
) -> ByteScope:
    """Tile [start, start+size) with decoded leaves plus reasoned opaque gaps."""
    if size <= 0:
        return ByteScope(scope_id=scope_id, start=start, size=size, leaves=[])

    ordered = sorted(
        (r for r in decoded if r.size > 0 and r.start >= start and r.end <= start + size),
        key=lambda r: r.start,
    )
    pieces: list[ByteRegion] = []
    cursor = start
    for region in ordered:
        if region.start > cursor:
            gap = opaque_region(
                cursor,
                region.start - cursor,
                gap_reason,
                source_id=region.source_id if region.source_id != "composite" else "package",
                source_start=None,
                feature="byte_accounting",
            )
            pieces.append(gap)
        pieces.append(region)
        cursor = max(cursor, region.end)
    if cursor < start + size:
        pieces.append(
            opaque_region(
                cursor,
                start + size - cursor,
                gap_reason,
                feature="byte_accounting",
            )
        )

    leaves: list[ByteRegion] = []
    for piece in pieces:
        leaves.extend(split_region_at_physical(piece, source))

    # Re-tile if physical split left virtual gaps (map_range incomplete).
    leaves.sort(key=lambda r: r.start)
    fixed: list[ByteRegion] = []
    cursor = start
    end = start + size
    for leaf in leaves:
        if leaf.start > cursor:
            fixed.append(opaque_region(cursor, leaf.start - cursor, gap_reason, feature="byte_accounting"))
            cursor = leaf.start
        if leaf.start < cursor:
            continue
        fixed.append(leaf)
        cursor = leaf.end
    if cursor < end:
        fixed.append(opaque_region(cursor, end - cursor, gap_reason, feature="byte_accounting"))

    scope = ByteScope(scope_id=scope_id, start=start, size=size, leaves=fixed)
    scope.validate_full_coverage()
    return scope
