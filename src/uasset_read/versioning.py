"""
Unified version management — VersionContainer and custom-version lookup.

Corresponds to COR-02: FCustomVersion system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any


from uasset_read.constants import (
    UE5_VERSION_MIN,
)

if TYPE_CHECKING:
    from uasset_read.serializers.package_summary import PackageFileSummary


# ============================================================================
# Serialized custom-version GUIDs (lowercase hex, no braces)
#
# These live here rather than with a consumer because they index the package
# summary's custom-version table, which is versioning data, not Kismet data.
# ============================================================================

FRAMEWORK_GUID = "3f74fccf8044b043df14919373201d17"
CORE_GUID = "3cc15e37fb48e406f08400b57e712a26"
FORTNITE_GUID = "86181d60844f64acded316aad6c7ea0d"
RELEASE_GUID = "22d5549cbe4f26a846072194d082b461"


def get_custom_version(summary: PackageFileSummary, serialized_guid: str) -> int:
    """Look up a custom version by serialized GUID.

    Returns the version number if found, or -1 if the GUID is not present
    in the summary's custom version table.
    """
    for cv in getattr(summary, "custom_versions", ()):
        if cv.guid == serialized_guid:
            return cv.version
    return -1


# ============================================================================
# VersionContainer
# ============================================================================


@dataclass
class VersionContainer:
    """Unified version query entry point, built from PackageFileSummary."""

    custom_versions: list[Any] = field(default_factory=list)
    file_version_ue5: int = 0
    file_version_ue4: int = 0

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
        file_version_ue4=getattr(summary, "file_version_ue4", 0),
    )
