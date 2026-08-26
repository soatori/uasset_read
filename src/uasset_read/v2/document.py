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


@dataclass(frozen=True)
class SourceInfo:
    kind: str  # "loose" | "pak" | "iostore" | "memory"
    name: str
    size: int
    path: str = ""


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
    diagnostic_counts: dict[str, int] = field(default_factory=dict)


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the v2 JSON contract."""
        return {
            "format": "uasset_read.package",
            "format_version": "2.0",
            "view": self.view,
            "depth": self.depth,
            "source": {
                "kind": self.source.kind,
                "name": self.source.name,
                "size": self.source.size,
            },
            "package": {
                "name": self.package.name,
                "layout": self.package.layout,
                "engine_version": self.package.engine_version,
                "compatible_engine_version": self.package.compatible_engine_version,
                "package_flags": self.package.package_flags,
                "total_header_size": self.package.total_header_size,
                "export_count": self.package.export_count,
                "import_count": self.package.import_count,
                "name_count": self.package.name_count,
            },
            "objects": [
                {
                    "id": obj.id,
                    "table_index": obj.table_index,
                    "name": obj.name,
                    "class": obj.class_name,
                    "roles": list(obj.roles),
                    "serial_region": (
                        {"offset": obj.serial_region.offset, "size": obj.serial_region.size}
                        if obj.serial_region
                        else None
                    ),
                    "status": {"parse": obj.status.parse, "semantic": obj.status.semantic},
                    "properties": obj.properties,
                    "semantic": obj.semantic,
                    "coverage": [
                        {"feature": c.feature, "status": c.status, **({"detail": c.detail} if c.detail else {})}
                        for c in obj.coverage
                    ],
                    "diagnostics": [d.to_dict() for d in obj.diagnostics] if obj.diagnostics else [],
                }
                for obj in self.objects
            ],
            "relations": [{"kind": r.kind, "from": r.from_id, "to": r.to_id} for r in self.relations],
            "dependencies": [
                {
                    "index": d.index,
                    "class": d.class_name,
                    "object_name": d.object_name,
                    **({"package_name": d.package_name} if d.package_name else {}),
                }
                for d in self.dependencies
            ],
            "payloads": [
                {
                    "id": p.id,
                    "owner": p.owner_id,
                    "kind": p.kind,
                    "source_region": p.source_region,
                    "offset": p.offset,
                    "stored_size": p.stored_size,
                    "logical_size": p.logical_size,
                    "compression": p.compression,
                    "status": p.status,
                    "hash": p.hash,
                }
                for p in self.payloads
            ],
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "summary": {
                "object_count": self.summary.object_count,
                "asset_object_ids": list(self.summary.asset_object_ids),
                "total_imports": self.summary.total_imports,
                "total_exports": self.summary.total_exports,
                "diagnostic_counts": self.summary.diagnostic_counts,
            },
        }
