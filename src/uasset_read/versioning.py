"""
Unified version management — custom-version lookup.

Corresponds to COR-02: FCustomVersion system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Mapping

from uasset_read.constants import PKG_FilterEditorOnly

if TYPE_CHECKING:
    from uasset_read.serializers.package_summary import PackageFileSummary


def ftext_dev_notes_enabled(summary) -> bool:
    """TextHistory.cpp:915-937 — editor UE5 FText Base appends a gated DevNotes FString.

    Single home for the AddDevNotesToFText (260) + FilterEditorOnly gate;
    the FText reader, property parser, and StringTable trailer share it.
    """
    if summary is None or (summary.package_flags & PKG_FilterEditorOnly):
        return False
    return get_custom_version(summary, FORTNITE_GUID) >= 260  # AddDevNotesToFText


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


@dataclass(frozen=True)
class VersionContext:
    """Per-read version bundle passed to readers and handlers.

    Not a replacement for the summary/custom-version system: a small frozen
    value carrying the fields the current plan's readers consume.
    ``custom_versions`` is copied into a MappingProxyType so the context is
    immutable after construction.
    """

    depth: Literal["package", "object", "asset", "decode"]
    file_version_ue: int | None = None
    file_version_licensee_ue: int | None = None
    custom_versions: Mapping[str, int] = field(default_factory=dict)
    package_layout: Literal["legacy", "zen", "unknown"] = "legacy"
    cooked: bool | None = None
    editor_only_filtered: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "custom_versions",
            MappingProxyType(dict(self.custom_versions)),
        )
