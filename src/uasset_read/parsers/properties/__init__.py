"""Bounded property reader input/result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from uasset_read.models.byte_ranges import ByteRegion
from uasset_read.models.diagnostics import Diagnostic
from uasset_read.models.properties import PropertyBag

if TYPE_CHECKING:
    from uasset_read.sources import ByteSource
    from uasset_read.versioning import VersionContext


@dataclass(frozen=True)
class PropertyInput:
    source: ByteSource
    object_id: str
    start: int
    size: int
    class_name: str
    context: VersionContext


@dataclass
class PropertyReadResult:
    values: PropertyBag
    consumed: int
    regions: list[ByteRegion]
    diagnostics: list[Diagnostic]
    status: Literal["complete", "partial", "opaque", "unavailable", "failed"]
