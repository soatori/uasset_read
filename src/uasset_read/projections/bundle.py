"""Canonical single-document materialization for type-aware projections (R3).

``build_canonical_document`` always includes every object id, semantic data,
projection records, diagnostics, payload references, and byte-accounting
scopes in the v3 contract shape. ``write_projected_document`` serializes one
UTF-8 JSON file and never implements automatic sidecars. Capability status
rides each projection record (status/completeness); the matrix itself stays
on ``uasset_read.projections.registry.CAPABILITY_MATRIX``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from uasset_read.models.document import PackageDocument
from uasset_read.projection import (
    FORMAT_VERSION,
    build_projection_records,
    dependency_to_dict,
    obj_to_dict,
)
from uasset_read.projections.records import projection_to_dict
from uasset_read.projections.registry import ProjectorRegistry


class OutputBudgetError(ValueError):
    """The requested main-document limit cannot fit the mandatory envelope."""


def _payload_references(document: PackageDocument) -> list[dict[str, Any]]:
    """Payload descriptors referenced by export serial regions (never embedded bytes).

    Keys match contract PayloadDescriptor: no extra ``payload_ref`` field.
    """
    payloads: list[dict[str, Any]] = []
    for obj in document.objects:
        if not obj.id.startswith("export:"):
            continue
        region = obj.serial_region
        if region is None or region.size <= 0:
            continue
        if len(region.source_slices) != 1:
            # A single PayloadDescriptor cannot represent a range split across
            # physical files without inventing one source/offset pair.
            continue
        physical = region.source_slices[0]
        source_id = physical.source_id.lower()
        if source_id.endswith(".uexp"):
            source_region = "uexp"
        elif source_id.endswith(".ubulk"):
            source_region = "ubulk"
        elif source_id.endswith(".uptnl"):
            source_region = "uptnl"
        elif source_id.endswith((".uasset", ".umap")):
            source_region = "main"
        else:
            # Memory/unknown sources have no contract-safe physical region.
            continue
        payload_ref = region.payload_ref or f"payload:{obj.id}"
        payloads.append(
            {
                "id": payload_ref,
                "owner": obj.id,
                "kind": "other",
                "source_region": source_region,
                "offset": physical.source_start,
                "stored_size": physical.size,
                "status": "available",
            }
        )
    return payloads


def _byte_accounting_array(document: PackageDocument) -> list[dict[str, Any]]:
    """Contract-shaped byte-accounting scopes (array of ByteAccountingScope)."""
    objects_by_id = {obj.id: obj for obj in document.objects}
    scopes: list[dict[str, Any]] = []
    for scope_id, scope in document.byte_accounting.scopes.items():
        obj = objects_by_id.get(scope_id)
        if obj is not None and obj.serial_region is not None:
            window = {"offset": obj.serial_region.start, "size": obj.serial_region.size}
        elif scope.leaves:
            window = {"offset": scope.leaves[0].start, "size": scope.size}
        else:
            window = {"offset": 0, "size": 0}
        leaves = []
        for leaf in scope.leaves:
            entry: dict[str, Any] = {
                "offset": leaf.start,
                "size": leaf.size,
                "status": leaf.status,
            }
            if leaf.reason:
                entry["reason"] = leaf.reason
            if leaf.payload_ref:
                entry["payload_ref"] = leaf.payload_ref
            leaves.append(entry)
        scopes.append(
            {
                "object_id": scope_id,
                "window": window,
                "leaves": leaves,
            }
        )
    return scopes


def build_canonical_document(
    document: PackageDocument,
    *,
    registry: ProjectorRegistry | None = None,
) -> dict[str, Any]:
    """Materialize the complete format_version 3.0 canonical document dict.

    No pagination, no selection, no sidecars. Every object remains addressable.
    Embedded type-specific content is created only via ``build_projection_records``
    (sole-creator API); this function materializes the envelope around it.
    """
    projections = build_projection_records(document, registry=registry)
    package = document.package
    source = document.source
    # Envelope keys match docs/designs/contract/package_document_v3.schema.json:
    # no top-level layout/capabilities (layout lives on package; capability
    # status rides each projection record via status/completeness).
    return {
        "format": "uasset_read.package",
        "format_version": FORMAT_VERSION,
        "view": "semantic",
        "depth": document.depth,
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
        "objects": [obj_to_dict(obj, view="semantic") for obj in document.objects],
        "relations": [
            {"kind": rel.kind, "from": rel.from_id, "to": rel.to_id}
            for rel in document.relations
        ],
        "dependencies": [dependency_to_dict(dep) for dep in document.dependencies],
        "projections": [projection_to_dict(item) for item in projections],
        "sidecars": [],
        "payloads": _payload_references(document),
        "diagnostics": [
            item.to_dict() if hasattr(item, "to_dict") else item
            for item in document.diagnostics + document.reader_diagnostics
        ],
        "summary": {
            "object_count": document.summary.object_count,
            "asset_object_ids": list(document.summary.asset_object_ids),
            "total_imports": document.summary.total_imports,
            "total_exports": document.summary.total_exports,
        },
        "byte_accounting": _byte_accounting_array(document),
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
    cannot fit the complete document.
    """
    payload = build_canonical_document(document, registry=registry)
    text = _serialize_canonical(payload)
    size = len(text.encode("utf-8"))
    if max_main_bytes is not None:
        if size > max_main_bytes:
            raise OutputBudgetError(
                f"complete canonical document is {size} bytes; "
                f"max_main_bytes={max_main_bytes} cannot fit it"
            )
    output_path = Path(output_path)
    output_path.write_text(text, encoding="utf-8")
    return output_path
