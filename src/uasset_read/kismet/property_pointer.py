"""Kismet property pointer — FFieldPath + FKismetPropertyPointer.

Corresponds to UE engine's FFieldPath and FKismetPropertyPointer structs,
used to reference object properties in Kismet bytecode.

UE5 FFieldPath stores a sequence of FName path segments plus an optional
resolved owner (PackageIndex). FKismetPropertyPointer wraps FFieldPath.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.serializers.object_resources import PackageIndex


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
    resolved_owner: Optional[PackageIndex] = field(default=None)


@dataclass
class FKismetPropertyPointer:
    """FKismetPropertyPointer — property reference pointer in Kismet bytecode.

    Wraps an FFieldPath for property references in Kismet bytecode.
    """

    bNew: bool = True
    path: Optional[FFieldPath] = field(default=None)

    @classmethod
    def from_archive(
        cls, archive: FArchive, name_map: list[str]
    ) -> FKismetPropertyPointer:
        """Deserialize FKismetPropertyPointer from FArchive."""
        b_new = archive.read_bool()

        if b_new:
            # Use archive's xfer_field_pointer if available (dual-cursor)
            if hasattr(archive, 'xfer_field_pointer'):
                field_path = archive.xfer_field_pointer()
            else:
                # Legacy fallback: read FFieldPath manually
                count = archive.read_u32()
                from uasset_read.kismet.property_pointer import FFieldPathSegment
                segments: list[FFieldPathSegment] = []
                for _ in range(count):
                    name_index = archive.read_u32()
                    number = archive.read_u32()
                    if 0 <= name_index < len(name_map):
                        base_name = name_map[name_index]
                    else:
                        base_name = f"Unknown_{name_index}"
                    segments.append(FFieldPathSegment(
                        name_index=name_index,
                        number=number,
                        base_name=base_name,
                    ))
                field_path = FFieldPath(path=segments)
            return cls(bNew=True, path=field_path)
        else:
            # Legacy path: read FPackageIndex (single int32)
            old_index = PackageIndex(archive.read_i32())
            return cls(bNew=False, path=FFieldPath(
                path=[],
                resolved_owner=old_index,
            ))

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
