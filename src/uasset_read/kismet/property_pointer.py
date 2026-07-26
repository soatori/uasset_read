from __future__ import annotations

"""
Kismet property pointer — FFieldPath + FKismetPropertyPointer.

Corresponds to UE engine's FFieldPath and FKismetPropertyPointer structs,
used to reference object properties in Kismet bytecode.

UE4.25+ introduced bNew flag: True uses FFieldPath path reference,
False uses legacy FPackageIndex single-step reference.
Simplified implementation: always reads FFieldPath (UE5 default behavior).
"""


from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.serializers.object_resources import PackageIndex


@dataclass
class FFieldPath:
    """
    UE5 FFieldPath — property path reference.

    Path stores list of path segments resolved from FName name table.
    ResolvedOwner is a UE5 new field storing the owner PackageIndex for path resolution.
    """

    Path: list[str] = field(default_factory=list)
    ResolvedOwner: Optional[PackageIndex] = field(default=None)

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: list[str]) -> FFieldPath:
        """
        Deserialize FFieldPath from FArchive.

        Read logic:
        1. Read u32 array length (Path segment count)
        2. Loop reading each FName index (u32), look up name_map to resolve string
        3. If first element is "None", clear Path (indicates empty path)
        4. Check version/engine state to read optional ResolvedOwner
        """
        count = archive.read_u32()

        path: list[str] = []
        for _ in range(count):
            name_index = archive.read_u32()
            path.append(archive.resolve_fname(name_index))

        # If first element is "None", indicates empty path
        if path and path[0] == "None":
            path.clear()

        return cls(Path=path)


@dataclass
class FKismetPropertyPointer:
    """
    FKismetPropertyPointer — property reference pointer in Kismet bytecode.

    bNew flag distinguishes two reference modes:
    - True (UE4.25+): Uses FFieldPath multi-segment path reference
    - False (legacy): Uses FPackageIndex single-step reference

    Simplified implementation: always uses New (FFieldPath) path.
    """

    bNew: bool = True
    Old: Optional[PackageIndex] = field(default=None)
    New: Optional[FFieldPath] = field(default=None)

    @classmethod
    def from_archive(
        cls, archive: FArchive, name_map: list[str]
    ) -> FKismetPropertyPointer:
        """
        Deserialize FKismetPropertyPointer from FArchive.

        Simplified: after reading bNew flag, always uses New (FFieldPath) path.
        Full legacy Old path support deferred to future implementation.
        """
        b_new = archive.read_bool()

        if b_new:
            new_path = FFieldPath.from_archive(archive, name_map)
            return cls(bNew=True, New=new_path)
        else:
            # Legacy path: read FPackageIndex (single int32)
            old_index = PackageIndex(archive.read_i32())
            return cls(bNew=False, Old=old_index)

    def __str__(self) -> str:
        """Return string representation of the property path."""
        if self.New and self.New.Path:
            return self.New.Path[0]
        if self.Old is not None:
            idx = self.Old.index
            if idx == 0:
                return "None"
            return f"Property_{idx}"
        return "None"
