"""Semantic IR — mode-independent intermediate representation for semantic JSON output.

This IR is separate from PackageIR. It represents the public semantic contract
and is produced by ``build_semantic_ir()`` from PackageIR data.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AssetStatus:
    """Parse and representation status — two independent dimensions."""

    parse: str  # "complete" | "partial" | "failed"
    representation: str  # "full" | "partial" | "opaque"


@dataclass(frozen=True)
class AssetMeta:
    """Asset identity — package path, name, and optional generated class.

    ``asset_type`` is a top-level ``SemanticIR`` field, not duplicated here.
    ``generated_class`` appears only when the type is ``unknown`` or the
    Unreal class cannot be uniquely represented by the normalized type.
    """

    package: str
    name: str
    generated_class: str | None = None


@dataclass(frozen=True)
class ReferenceEntry:
    """A single import or export reference.

    ``package_path`` is the package containing the referenced object (for
    imports, resolved through the outer chain). Empty when unresolvable.
    It is never the class package.
    """

    index: int
    kind: str  # "import" | "export"
    class_name: str
    object_name: str
    package_path: str = ""


@dataclass(frozen=True)
class CoverageInfo:
    """Honest coverage — reports actual semantic loss, not key counts."""

    scopes_expected: int
    scopes_available: int
    scopes_unavailable: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.scopes_unavailable, list):
            object.__setattr__(self, "scopes_unavailable", tuple(self.scopes_unavailable))


@dataclass(frozen=True)
class DiagnosticEntry:
    """A single deduplicated diagnostic message."""

    severity: str  # "error" | "warning" | "info"
    code: str
    message: str


@dataclass(frozen=True)
class EvidenceEntry:
    """Debug-only evidence — colocated with the relevant semantic object."""

    key: str
    value: object = None


@dataclass(frozen=True)
class SemanticIR:
    """Top-level Semantic IR — the complete public semantic contract.

    Produced by ``build_semantic_ir()``, projected by ``project_semantic()``,
    validated by ``validate_semantic_document()``, rendered by ``render_semantic_json()``.
    """

    format: str  # always "uasset_read.asset_semantic"
    format_version: str  # "1.0"
    mode: str  # "standard" | "debug"
    asset_type: str  # normalized type discriminator
    asset: AssetMeta
    status: AssetStatus
    references: tuple[ReferenceEntry, ...] = ()
    content: dict = field(
        default_factory=dict
    )  # staging area for domain extension fields; promoted to top-level JSON by renderer
    coverage: CoverageInfo | None = None
    diagnostics: tuple[DiagnosticEntry, ...] = ()
    evidence: tuple[EvidenceEntry, ...] = ()  # debug-only

    def __post_init__(self) -> None:
        if isinstance(self.references, list):
            object.__setattr__(self, "references", tuple(self.references))
        if isinstance(self.diagnostics, list):
            object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if isinstance(self.evidence, list):
            object.__setattr__(self, "evidence", tuple(self.evidence))
