"""Canonical single-document materialization for type-aware projections (R3).

``build_canonical_document`` always includes every object id, semantic data,
projection records, capabilities, diagnostics, and payload references.
``write_projected_document`` serializes one UTF-8 JSON file and never
implements automatic sidecars.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from uasset_read.models.byte_ranges import project_region
from uasset_read.models.diagnostics import Diagnostic
from uasset_read.models.document import PackageDocument
from uasset_read.projection import FORMAT_VERSION, dependency_to_dict, obj_to_dict
from uasset_read.projections.records import ProjectionRecord, projection_to_dict
from uasset_read.projections.registry import CAPABILITY_MATRIX, ProjectorRegistry


class OutputBudgetError(ValueError):
    """The requested main-document limit cannot fit the mandatory envelope."""


def _diagnostic_dicts(items: list[Diagnostic]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        out.append(item.to_dict() if hasattr(item, "to_dict") else item)
    return out


def _payload_references(document: PackageDocument) -> list[dict[str, Any]]:
    """Payload descriptors referenced by export serial regions (never embedded bytes)."""
    payloads: list[dict[str, Any]] = []
    for obj in document.objects:
        if not obj.id.startswith("export:"):
            continue
        region = obj.serial_region
        if region is None or region.size <= 0:
            continue
        payload_ref = region.payload_ref or f"payload:{obj.id}"
        payloads.append(
            {
                "id": payload_ref,
                "owner": obj.id,
                "kind": "other",
                "source_region": "main",
                "offset": region.start,
                "stored_size": region.size,
                "status": "available",
                "payload_ref": payload_ref,
            }
        )
    return payloads


def _object_entry(obj: Any) -> dict[str, Any]:
    return obj_to_dict(obj, view="semantic")


def build_canonical_document(
    document: PackageDocument,
    *,
    registry: ProjectorRegistry | None = None,
) -> dict[str, Any]:
    """Materialize the complete format_version 3.0 canonical document dict.

    No pagination, no selection, no sidecars. Every object remains addressable.
    """
    active = registry if registry is not None else ProjectorRegistry.default()
    projections = active.project_document(document)
    package = document.package
    source = document.source
    return {
        "format": "uasset_read.package",
        "format_version": FORMAT_VERSION,
        "view": "semantic",
        "depth": document.depth,
        "layout": document.layout,
        "source": None
        if source is None
        else {"kind": source.kind, "name": source.name, "size": source.size},
        "package": None
        if package is None
        else {
            "name": package.name,
            "layout": package.layout,
            "engine_version": package.engine_version,
            "compatible_engine_version": package.compatible_engine_version,
            "package_flags": package.package_flags,
            "total_header_size": package.total_header_size,
            "export_count": package.export_count,
            "import_count": package.import_count,
            "name_count": package.name_count,
        },
        "objects": [_object_entry(obj) for obj in document.objects],
        "relations": [
            {"kind": rel.kind, "from": rel.from_id, "to": rel.to_id}
            for rel in document.relations
        ],
        "dependencies": [dependency_to_dict(dep) for dep in document.dependencies],
        "projections": [projection_to_dict(item) for item in projections],
        "capabilities": [dict(entry) for entry in CAPABILITY_MATRIX],
        "sidecars": [],
        "payloads": _payload_references(document),
        "diagnostics": _diagnostic_dicts(document.diagnostics + document.reader_diagnostics),
        "summary": {
            "object_count": document.summary.object_count,
            "asset_object_ids": list(document.summary.asset_object_ids),
            "total_imports": document.summary.total_imports,
            "total_exports": document.summary.total_exports,
        },
        "byte_accounting": {
            "scopes": [
                {
                    "scope_id": scope_id,
                    "object_id": scope_id,
                    "leaves": [project_region(leaf) for leaf in scope.leaves],
                }
                for scope_id, scope in document.byte_accounting.scopes.items()
            ]
        },
    }


def _serialize_canonical(payload: dict[str, Any]) -> str:
    """Deterministic compact UTF-8 JSON encoding used for size measure + write."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _utf8_size(payload: dict[str, Any]) -> int:
    return len(_serialize_canonical(payload).encode("utf-8"))


def minimum_canonical_envelope_bytes(
    document: PackageDocument,
    *,
    registry: ProjectorRegistry | None = None,
) -> int:
    """UTF-8 byte length of the complete mandatory canonical envelope.

    ``registry`` must match the registry used by ``write_projected_document``
    so budget checks measure the same projection set.
    """
    return _utf8_size(build_canonical_document(document, registry=registry))


def write_projected_document(
    document: PackageDocument,
    output_path: Path,
    *,
    max_main_bytes: int | None = None,
    registry: ProjectorRegistry | None = None,
) -> Path:
    """Write one UTF-8 canonical JSON document. Never writes sidecars.

    Raises OutputBudgetError before creating any file when ``max_main_bytes``
    cannot fit the complete document or falls below
    ``minimum_canonical_envelope_bytes(document, registry=registry)``.
    """
    payload = build_canonical_document(document, registry=registry)
    text = _serialize_canonical(payload)
    size = len(text.encode("utf-8"))
    if max_main_bytes is not None:
        minimum = minimum_canonical_envelope_bytes(document, registry=registry)
        if max_main_bytes < minimum:
            raise OutputBudgetError(
                f"max_main_bytes={max_main_bytes} is below mandatory envelope "
                f"{minimum} bytes"
            )
        if size > max_main_bytes:
            raise OutputBudgetError(
                f"complete canonical document is {size} bytes; "
                f"max_main_bytes={max_main_bytes} cannot fit it"
            )
    output_path = Path(output_path)
    output_path.write_text(text, encoding="utf-8")
    return output_path
