"""VersionContext — immutable parse context.

Extends VersionContainer with layout, platform, cook state,
and other fields the v2 design requires.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping


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
        return self.file_version_ue5 >= 522

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
