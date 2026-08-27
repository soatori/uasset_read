"""Agent tools — 6 tool functions for MCP/Agent consumption.

Each tool directly calls the v2 Python API and returns structured JSON.
Tools are transport-agnostic; MCP is just one possible adapter.

Design doc reference:
- Agent Gate: 6 tools sharing Python API
- Each tool has max response bytes, supports selection/pagination
- Returns stable ids, distinguishes not_requested vs unavailable
- Errors are structured diagnostics, not log stacks
"""

from __future__ import annotations

from typing import Any

from .api import parse_package_document
from .document import PackageDocument
from .projection import select_objects, paginate

# Max response sizes per tool (bytes)
_MAX_BYTES_INSPECT = 4096
_MAX_BYTES_LIST_OBJECTS = 16384
_MAX_BYTES_GET_OBJECT = 32768
_MAX_BYTES_LIST_DEPS = 8192
_MAX_BYTES_GET_DIAG = 8192
_MAX_BYTES_EXTRACT_PAYLOAD = 65536


def inspect_package(
    file_path: str,
    *,
    max_bytes: int = _MAX_BYTES_INSPECT,
) -> dict[str, Any]:
    """Tool: inspect_package — source/package/summary/diagnostic overview.

    Returns a concise summary of the package without listing all objects.
    """
    doc = parse_package_document(file_path)
    return {
        "source": {
            "kind": doc.source.kind,
            "name": doc.source.name,
            "size": doc.source.size,
        },
        "package": {
            "name": doc.package.name,
            "layout": doc.package.layout,
            "engine_version": doc.package.engine_version,
            "package_flags": doc.package.package_flags,
            "export_count": doc.package.export_count,
            "import_count": doc.package.import_count,
        },
        "summary": {
            "object_count": doc.summary.object_count,
            "asset_object_ids": list(doc.summary.asset_object_ids),
            "total_imports": doc.summary.total_imports,
            "total_exports": doc.summary.total_exports,
        },
        "diagnostics_count": len(doc.diagnostics),
        "diagnostics_summary": _summarize_diagnostics(doc),
    }


def list_objects(
    file_path: str,
    *,
    object_ids: list[str] | None = None,
    roles: list[str] | None = None,
    classes: list[str] | None = None,
    offset: int = 0,
    limit: int = 50,
    max_bytes: int = _MAX_BYTES_LIST_OBJECTS,
) -> dict[str, Any]:
    """Tool: list_objects — paginated object identity, class, roles, status.

    Returns object list with pagination info.
    """
    doc = parse_package_document(file_path)
    selected = select_objects(doc, object_ids=object_ids, roles=roles, classes=classes)
    page, next_offset, truncation = paginate(selected, offset=offset, limit=limit)

    objects = []
    for obj in page:
        objects.append(
            {
                "id": obj.id,
                "table_index": obj.table_index,
                "name": obj.name,
                "class": obj.class_name,
                "roles": list(obj.roles),
                "status": {"parse": obj.status.parse, "semantic": obj.status.semantic},
            }
        )

    result: dict[str, Any] = {
        "objects": objects,
        "total": len(selected),
        "offset": offset,
        "returned": len(objects),
    }
    if next_offset is not None:
        result["next_offset"] = next_offset
    return result


def get_object(
    file_path: str,
    object_id: str,
    *,
    max_bytes: int = _MAX_BYTES_GET_OBJECT,
) -> dict[str, Any]:
    """Tool: get_object — single object properties and optional semantic.

    Returns full object detail including serial region and diagnostics.
    """
    doc = parse_package_document(file_path)

    # Find the object
    obj = None
    for o in doc.objects:
        if o.id == object_id:
            obj = o
            break

    if obj is None:
        return {
            "error": f"Object '{object_id}' not found",
            "available_ids": [o.id for o in doc.objects[:20]],
        }

    result: dict[str, Any] = {
        "id": obj.id,
        "table_index": obj.table_index,
        "name": obj.name,
        "class": obj.class_name,
        "roles": list(obj.roles),
        "serial_region": (
            {"offset": obj.serial_region.offset, "size": obj.serial_region.size} if obj.serial_region else None
        ),
        "status": {"parse": obj.status.parse, "semantic": obj.status.semantic},
    }
    if obj.properties is not None:
        result["properties"] = obj.properties
    if obj.semantic is not None:
        result["semantic"] = obj.semantic
    if obj.coverage:
        result["coverage"] = [{"feature": c.feature, "status": c.status} for c in obj.coverage]
    if obj.diagnostics:
        result["diagnostics"] = [d.to_dict() for d in obj.diagnostics]

    return result


def list_dependencies(
    file_path: str,
    *,
    offset: int = 0,
    limit: int = 50,
    max_bytes: int = _MAX_BYTES_LIST_DEPS,
) -> dict[str, Any]:
    """Tool: list_dependencies — paginated import dependencies and relations.

    Returns dependencies (imports) and relations (object-to-object links).
    """
    doc = parse_package_document(file_path)
    deps_page, next_offset, truncation = paginate(
        doc.dependencies,
        offset=offset,
        limit=limit,
    )

    return {
        "dependencies": [
            {
                "index": d.index,
                "class": d.class_name,
                "object_name": d.object_name,
                "package_name": d.package_name,
            }
            for d in deps_page
        ],
        "relations": [{"kind": r.kind, "from": r.from_id, "to": r.to_id} for r in doc.relations],
        "total_dependencies": len(doc.dependencies),
        "total_relations": len(doc.relations),
        "offset": offset,
        "returned": len(deps_page),
        **({"next_offset": next_offset} if next_offset is not None else {}),
    }


def get_diagnostics(
    file_path: str,
    *,
    stage: str | None = None,
    severity: str | None = None,
    object_id: str | None = None,
    offset: int = 0,
    limit: int = 50,
    max_bytes: int = _MAX_BYTES_GET_DIAG,
) -> dict[str, Any]:
    """Tool: get_diagnostics — filtered diagnostic list.

    Filters by stage, severity, and/or object_id.
    """
    doc = parse_package_document(file_path)

    # Collect all diagnostics (package-level + object-level)
    all_diags = list(doc.diagnostics)
    for obj in doc.objects:
        all_diags.extend(obj.diagnostics)

    # Apply filters
    filtered = all_diags
    if stage:
        filtered = [d for d in filtered if d.stage == stage]
    if severity:
        filtered = [d for d in filtered if d.severity == severity]
    if object_id:
        filtered = [d for d in filtered if d.object_id == object_id]

    # Paginate
    page, next_offset, truncation = paginate(filtered, offset=offset, limit=limit)

    return {
        "diagnostics": [d.to_dict() for d in page],
        "total": len(filtered),
        "offset": offset,
        "returned": len(page),
        **({"next_offset": next_offset} if next_offset is not None else {}),
    }


def extract_payload(
    file_path: str,
    payload_id: str,
    *,
    max_bytes: int = _MAX_BYTES_EXTRACT_PAYLOAD,
) -> dict[str, Any]:
    """Tool: extract_payload — return or write specified payload.

    Phase 5 stub — payloads are not yet extracted from external regions.
    Returns payload descriptor information only.
    """
    doc = parse_package_document(file_path)

    # Find the payload
    for p in doc.payloads:
        if p.id == payload_id:
            return {
                "id": p.id,
                "owner": p.owner_id,
                "kind": p.kind,
                "source_region": p.source_region,
                "offset": p.offset,
                "stored_size": p.stored_size,
                "status": p.status,
                "note": "Payload extraction requires Phase 5 (Zen/Container) implementation",
            }

    return {
        "error": f"Payload '{payload_id}' not found",
        "available_ids": [p.id for p in doc.payloads],
        "note": "Payloads are currently empty — Phase 5 will populate them from external regions",
    }


def _summarize_diagnostics(doc: PackageDocument) -> dict[str, int]:
    """Count diagnostics by severity."""
    counts: dict[str, int] = {}
    for d in doc.diagnostics:
        counts[d.severity] = counts.get(d.severity, 0) + 1
    for obj in doc.objects:
        for d in obj.diagnostics:
            counts[d.severity] = counts.get(d.severity, 0) + 1
    return counts
