"""
Unified version management — VersionContainer.

Corresponds to COR-02: FCustomVersion system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


from uasset_read.constants import (
    UE5_VERSION_MIN,
)


# ============================================================================
# VersionContainer
# ============================================================================


@dataclass
class VersionContainer:
    """Unified version query entry point, built from PackageFileSummary."""

    custom_versions: list[Any] = field(default_factory=list)
    file_version_ue5: int = UE5_VERSION_MIN
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
