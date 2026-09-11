"""Kismet property pointer — FFieldPath + FKismetPropertyPointer.

Corresponds to UE engine's FFieldPath and FKismetPropertyPointer structs,
used to reference object properties in Kismet bytecode.

UE5 FFieldPath stores a sequence of FName path segments plus an optional
resolved owner (PackageIndex). FKismetPropertyPointer wraps FFieldPath.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.serializers.object_resources import PackageIndex


@dataclass(frozen=True)
class FNameRef:
    """Lossless FName reference: raw index + number + resolved base name.

    Index zero is a legitimate null where UE permits it; nonzero invalid
    indices produce a structured failure rather than a guessed name.
    """

    name_index: int
    number: int
    base_name: str | None  # None when index is null or out-of-range


@dataclass
class FFieldPathSegment:
    """Single segment in an FFieldPath: FName index + number + resolved name."""

    name_index: int
    number: int
    base_name: str


@dataclass
class FFieldPath:
    """UE5 FFieldPath — property path reference.

    Path stores list of path segments resolved from FName name table.
    ResolvedOwner is a UE5 new field storing the owner PackageIndex for path resolution.
    """

    path: list[FFieldPathSegment] = field(default_factory=list)
    resolved_owner: PackageIndex | None = field(default=None)


@dataclass
class FKismetPropertyPointer:
    """FKismetPropertyPointer — property reference pointer in Kismet bytecode.

    Wraps an FFieldPath for property references in Kismet bytecode.
    """

    bNew: bool = True
    path: FFieldPath | None = field(default=None)

    @classmethod
    def from_archive(cls, archive: FArchive) -> FKismetPropertyPointer:
        """Deserialize FKismetPropertyPointer from FArchive.

        Persistent Kismet Script serialization routes FProperty* through
        FPropertyProxyArchive, which writes an FFieldPath directly.
        """
        return cls(bNew=True, path=archive.xfer_field_pointer())  # type: ignore[reportAttributeAccessIssue]

    def to_dict(self) -> dict:
        """JSON-serializable dict for this property pointer."""
        d: dict = {"bNew": self.bNew}
        if self.path:
            if self.path.path:
                d["segments"] = [
                    {
                        "name_index": seg.name_index,
                        "number": seg.number,
                        "base_name": seg.base_name,
                    }
                    for seg in self.path.path
                ]
            if self.path.resolved_owner is not None:
                d["resolved_owner"] = self.path.resolved_owner.index
        return d

    def __str__(self) -> str:
        """Return string representation of the property path."""
        if self.path and self.path.path:
            return self.path.path[0].base_name
        if self.path and self.path.resolved_owner is not None:
            idx = self.path.resolved_owner.index
            if idx == 0:
                return "None"
            return f"Property_{idx}"
        return "None"
