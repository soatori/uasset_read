"""PackageDocument — the v2 unified output model.

One document per .uasset/.umap file, expressing all exports
as first-class objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .diagnostics import Diagnostic
from .object_model import (
    Dependency,
    ObjectRecord,
    PayloadDescriptor,
    Relation,
)
from .source import SourceInfo


@dataclass(frozen=True)
class PackageInfo:
    name: str
    layout: Literal["legacy", "zen"]
    engine_version: str = ""
    compatible_engine_version: str = ""
    package_flags: int = 0
    total_header_size: int = 0
    export_count: int = 0
    import_count: int = 0
    name_count: int = 0


@dataclass
class Summary:
    object_count: int = 0
    asset_object_ids: tuple[str, ...] = ()
    total_imports: int = 0
    total_exports: int = 0


@dataclass
class PackageDocument:
    """Unified package-level output. One per .uasset/.umap."""

    source: SourceInfo
    package: PackageInfo
    objects: list[ObjectRecord] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    payloads: list[PayloadDescriptor] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    summary: Summary = field(default_factory=Summary)
    view: str = "semantic"
    depth: str = "asset"

    def to_dict(self, *, view: str | None = None, depth: str | None = None) -> dict[str, Any]:
        """Serialize to the v2 JSON contract via project_document."""
        from .projection import project_document

        return project_document(self, view=view or self.view, depth=depth or self.depth)
