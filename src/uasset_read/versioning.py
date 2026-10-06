"""
Unified version management — custom-version lookup.

Corresponds to COR-02: FCustomVersion system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Mapping

from uasset_read.constants import PKG_FilterEditorOnly
from uasset_read.exceptions import ParseError
from uasset_read.models.diagnostics import Diagnostic

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
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
    """Immutable per-document version context (方案甲 / G1 binding contract).

    Constructed once by ``LegacyPackageReader.read()`` immediately after
    summary bootstrap and mounted as ``archive.version_context``; windows
    (``ByteArchive``/``FKismetArchive``) reference the same instance.
    Consumers read the mounted context; pre-mount access is a structured
    failure. Contract: ``docs/designs/2026-08-31-version-context-field-contract.md``.
    ``custom_versions`` is copied into a MappingProxyType so the context is
    immutable after construction.
    """

    file_version_ue4: int
    file_version_ue5: int
    custom_versions: Mapping[str, int] = field(default_factory=dict)
    package_layout: Literal["legacy", "zen", "unknown"] = "legacy"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "custom_versions",
            MappingProxyType(dict(self.custom_versions)),
        )


def build_version_context(
    summary: PackageFileSummary,
    *,
    package_layout: Literal["legacy", "zen", "unknown"] = "legacy",
) -> VersionContext:
    """Construct the one per-document VersionContext from a read summary.

    方案甲 / G1: called once by ``LegacyPackageReader.read()`` right after
    summary bootstrap and mounted as ``archive.version_context``. Field
    population rules (normalized ue4/ue5, first-wins custom_versions,
    layout) follow the G1 contract.
    """
    custom_versions: dict[str, int] = {}
    for cv in summary.custom_versions:
        # First occurrence wins (G1: 首项优先 — equivalent to the former
        # linear first-match lookup); insertion order of the list is kept.
        custom_versions.setdefault(cv.guid, cv.version)
    return VersionContext(
        file_version_ue4=summary.file_version_ue4,
        file_version_ue5=summary.file_version_ue5,
        custom_versions=custom_versions,
        package_layout=package_layout,
    )


def require_version_context(archive: FArchive) -> VersionContext:
    """Return the mounted VersionContext; missing mount fails structurally.

    G1 §3: consumers never fall back to derived/defaults — a pre-bootstrap
    or bypassing caller raises ``ParseError(code="VERSION_CONTEXT_MISSING")``
    carrying a ``Diagnostic(stage="package.version_context")`` (same pattern
    as the package.py layout rejection).
    """
    context = getattr(archive, "version_context", None)
    if context is None:
        error = ParseError("archive has no VersionContext mounted (pre-bootstrap access)")
        error.code = "VERSION_CONTEXT_MISSING"
        error.diagnostics = [
            Diagnostic(
                severity="error",
                code=error.code,
                message=str(error),
                stage="package.version_context",
                effect="parse_failure",
                reason="unexpected",
            )
        ]
        raise error
    return context
