"""
Unified version management — VersionContainer and custom-version lookup.

Corresponds to COR-02: FCustomVersion system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Mapping


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
class MappingInfo:
    """Type mapping source (e.g. .usmap file path)."""

    path: str = ""


@dataclass(frozen=True)
class VersionContext:
    """Immutable parse context. All readers share this."""

    file_version_ue4: int = 0
    file_version_ue5: int = 0
    licensee_version: int = 0
    custom_versions: Mapping[str, int] = field(default_factory=dict)
    engine_version: EngineVersion | None = None
    compatible_engine_version: EngineVersion | None = None
    package_layout: Literal["legacy", "zen"] = "legacy"
    cooked: bool | None = None
    editor_only_filtered: bool | None = None
    platform: str | None = None
    game: str | None = None
    byte_order: Literal["little", "big"] = "little"
    mappings: MappingInfo | None = None
    depth: Literal["package", "object", "asset", "decode"] = "package"

    @property
    def is_ue5(self) -> bool:
        # ObjectVersion.h: UE5 range starts at INITIAL_VERSION=1000
        return self.file_version_ue5 >= 1000

    @property
    def version_string(self) -> str:
        if self.engine_version:
            return str(self.engine_version)
        if self.is_ue5:
            return f"UE5.{self.file_version_ue5}"
        return f"UE4.{self.file_version_ue4}"


def build_version_context_from_summary(
    summary: Any,
    *,
    package_layout: Literal["legacy", "zen"] = "legacy",
    cooked: bool | None = None,
    editor_only_filtered: bool | None = None,
    platform: str | None = None,
    game: str | None = None,
    mappings: MappingInfo | None = None,
    depth: Literal["package", "object", "asset", "decode"] = "package",
) -> VersionContext:
    """Build a VersionContext from an existing PackageFileSummary.

    This is the bridge between v1 and v2 — callers pass the v1 summary
    and get back a frozen v2 context.
    """
    # Build custom versions map from summary.custom_versions
    custom_versions: dict[str, int] = {}
    for cv in getattr(summary, "custom_versions", []):
        guid = getattr(cv, "guid", "")
        ver = getattr(cv, "version", 0)
        if guid:
            custom_versions[guid] = ver

    # Build engine version
    engine_version = None
    saved = getattr(summary, "saved_by_engine_version", None)
    if saved and hasattr(saved, "major"):
        engine_version = EngineVersion(
            major=getattr(saved, "major", 0),
            minor=getattr(saved, "minor", 0),
            patch=getattr(saved, "patch", 0),
            changelist=getattr(saved, "changelist", 0),
            branch=getattr(saved, "branch", ""),
        )

    compat_version = None
    compat = getattr(summary, "compatible_with_engine_version", None)
    if compat and hasattr(compat, "major"):
        compat_version = EngineVersion(
            major=getattr(compat, "major", 0),
            minor=getattr(compat, "minor", 0),
            patch=getattr(compat, "patch", 0),
            changelist=getattr(compat, "changelist", 0),
            branch=getattr(compat, "branch", ""),
        )

    return VersionContext(
        file_version_ue4=getattr(summary, "file_version_ue4", 0),
        file_version_ue5=getattr(summary, "file_version_ue5", 0),
        licensee_version=getattr(summary, "file_version_licensee", 0),
        custom_versions=custom_versions,
        engine_version=engine_version,
        compatible_engine_version=compat_version,
        package_layout=package_layout,
        cooked=cooked,
        editor_only_filtered=editor_only_filtered,
        platform=platform,
        game=game,
        mappings=mappings,
        depth=depth,
    )
