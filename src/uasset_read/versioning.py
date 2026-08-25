"""
Unified version management — VersionContainer.

Provides GUID-based version lookup and file-version comparison,
replacing hardcoded version checks throughout the codebase.
Corresponds to COR-02: FCustomVersion system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from uasset_read.core.utils import normalize_hex_guid

from uasset_read.constants import (
    UE5_VERSION_MIN,
)


# ============================================================================
# VersionContainer
# ============================================================================


@dataclass
class FPackageFileVersion:
    """UE file version wrapper (dual-version joint comparison).

    Corresponds to UE's FPackageFileVersion struct:
    - FileVersionUE4: int32
    - FileVersionUE5: int32
    """
    file_version_ue4: int = 0
    file_version_ue5: int = 0

    def to_value(self) -> int:
        """Return the highest effective version (UE source: FPackageFileVersion::ToValue())."""
        if self.file_version_ue5 > 0:
            return self.file_version_ue5
        return self.file_version_ue4

    def __ge__(self, other: int) -> bool:
        """Version comparison: whether the threshold is reached."""
        return self.to_value() >= other

    def __gt__(self, other: int) -> bool:
        """Version comparison: whether it exceeds the threshold."""
        return self.to_value() > other

    def __le__(self, other: int) -> bool:
        """Version comparison: whether it is below the threshold."""
        return self.to_value() <= other

    def __lt__(self, other: int) -> bool:
        """Version comparison: whether it has not reached the threshold."""
        return self.to_value() < other


@dataclass
class VersionContainer:
    """Unified version query entry point.

    After construction from PackageFileSummary, provides:
    - get_version(guid) -> look up CustomVersion number
    """
    custom_versions: list[Any] = field(default_factory=list)
    file_version_ue5: int = UE5_VERSION_MIN
    file_version_ue4: int = 0
    _guid_cache: dict[str, int] = field(default_factory=dict, repr=False)

    @property
    def file_version(self) -> FPackageFileVersion:
        """Return the wrapped file version object."""
        return FPackageFileVersion(
            file_version_ue4=self.file_version_ue4,
            file_version_ue5=self.file_version_ue5,
        )

    def get_version(self, guid: str, default: int = 0) -> int:
        """Look up version number by GUID, returning default if not found.

        GUID comparison automatically strips hyphens and converts to lowercase.
        """
        normalized = normalize_hex_guid(guid)
        cached = self._guid_cache.get(normalized)
        if cached is not None:
            return cached

        for cv in self.custom_versions:
            cv_guid = normalize_hex_guid(cv.guid)
            if cv_guid == normalized:
                self._guid_cache[normalized] = cv.version
                return cv.version

        # Do not cache default on miss to avoid cross-caller default pollution
        return default

    @property
    def is_ue5(self) -> bool:
        """Whether file_version_ue5 is in the UE5 range."""
        return self.file_version_ue5 >= UE5_VERSION_MIN


# ============================================================================
# Convenience functions
# ============================================================================

def build_version_container(summary) -> "VersionContainer":
    """Build a VersionContainer from a PackageFileSummary.

    Args:
        summary: PackageFileSummary instance, must have custom_versions and file_version_ue5 attributes.
    """
    return VersionContainer(
        custom_versions=summary.custom_versions,
        file_version_ue5=summary.file_version_ue5,
        file_version_ue4=getattr(summary, 'file_version_ue4', 0),
    )
