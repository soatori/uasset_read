"""
Unified version management — custom-version lookup.

Corresponds to COR-02: FCustomVersion system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

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
# v2 Version classes (package-first refactor)
# ============================================================================


@dataclass(frozen=True)
class EngineVersion:
    major: int = 0
    minor: int = 0
    patch: int = 0
    changelist: int = 0
    branch: str = ""

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}.{self.changelist}"


@dataclass(frozen=True)
class VersionContext:
    """Immutable parse context shared by all readers.

    Production-used fields only (G1 amended 2026-09-13 after revert
    ``280b7e09``): handlers read ``depth``; version facts stay on the
    package summary / archive gates until a real consumer lands.
    """

    depth: Literal["package", "object", "asset", "decode"] = "package"
