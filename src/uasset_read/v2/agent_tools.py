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
from .projection import select_objects, paginate, project_document

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
    depth: str = "package",
    limit: int | None = None,
) -> dict[str, Any]:
    """Tool: inspect_package — source/package/summary/diagnostic overview.

    Returns a concise summary of the package without listing all objects.
    """
    doc = parse_package_document(file_path)
    projected = project_document(doc, depth=depth, limit=limit, max_bytes=max_bytes)
    return projected


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
    projected = project_document(
        doc,
        object_ids=object_ids,
        roles=roles,
        classes=classes,
        offset=offset,
        limit=limit,
        max_bytes=max_bytes,
    )
    # Add total count for agent tools
    selected = select_objects(doc, object_ids=object_ids, roles=roles, classes=classes)
    projected["total"] = len(selected)
    projected["offset"] = offset
    projected["returned"] = len(projected["objects"])
    return projected


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

    # Check if object exists
    obj_exists = any(o.id == object_id for o in doc.objects)
    if not obj_exists:
        return {
            "error": f"Object '{object_id}' not found",
            "available_ids": [o.id for o in doc.objects[:20]],
        }

    projected = project_document(
        doc,
        object_ids=[object_id],
        max_bytes=max_bytes,
    )
    if projected["objects"]:
        return projected["objects"][0]
    return {"error": f"Object '{object_id}' not found"}


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
    projected = project_document(doc, max_bytes=max_bytes)

    # Paginate dependencies
    deps = projected["dependencies"]
    deps_page = deps[offset : offset + limit] if limit else deps
    next_offset_dep = offset + len(deps_page) if len(deps_page) == limit and offset + limit < len(deps) else None

    return {
        "dependencies": deps_page,
        "relations": projected["relations"],
        "total_dependencies": len(deps),
        "total_relations": len(projected["relations"]),
        "offset": offset,
        "returned": len(deps_page),
        **({"next_offset": next_offset_dep} if next_offset_dep is not None else {}),
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
