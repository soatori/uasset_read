"""Semantic IR — immutable intermediate representation for semantic JSON output.

This IR is separate from PackageIR. It represents the public JSON contract
and is produced by domain extractors from PackageIR data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from uasset_read.semantic.kinds import AssetKind


@dataclass(frozen=True)
class AssetMeta:
    """Asset metadata — identifies the asset and its kind."""
    kind: AssetKind
    class_name: str
    object_name: str
    package_path: str = ""
    parse_status: str = "success"


@dataclass(frozen=True)
class ReferenceEntry:
    """A single import or export reference."""
    index: int
    kind: str  # "import" | "export"
    class_name: str
    object_name: str
    package_path: str = ""


@dataclass(frozen=True)
class CoverageInfo:
    """Parse coverage information."""
    fields_expected: int
    fields_parsed: int
    coverage_pct: float
    unparsed_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.unparsed_fields, list):
            object.__setattr__(self, "unparsed_fields", tuple(self.unparsed_fields))


@dataclass(frozen=True)
class DiagnosticEntry:
    """A single diagnostic message."""
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str


@dataclass(frozen=True)
class ContentNode:
    """Tree node for structured content output.

    Leaf nodes have ``value`` set; branch nodes have ``children`` set.
    """
    key: str
    value: object = None
    children: tuple[ContentNode, ...] | None = None

    def __post_init__(self) -> None:
        if isinstance(self.children, list):
            object.__setattr__(self, "children", tuple(self.children))


@dataclass(frozen=True)
class SemanticIR:
    """Top-level Semantic IR — the complete public JSON contract.

    This is the input to SemanticJSONRenderer.
    """
    format: str  # always "uasset_read.asset_semantic"
    format_version: str  # always "1.0.0"
    mode: str  # "standard" | "debug"
    asset: AssetMeta
    references: tuple[ReferenceEntry, ...]
    content: ContentNode
    coverage: CoverageInfo
    diagnostics: tuple[DiagnosticEntry, ...]

    def __post_init__(self) -> None:
        if isinstance(self.references, list):
            object.__setattr__(self, "references", tuple(self.references))
        if isinstance(self.diagnostics, list):
            object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
