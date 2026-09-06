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

import json
from typing import Any, Literal

from .package import parse_package_document
from .projection import dependency_to_dict, fit_list_response, select_objects, paginate, project_document

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
    depth: Literal["package", "object", "asset", "decode"] = "package",
    limit: int = 0,
) -> dict[str, Any]:
    """Tool: inspect_package — source/package/summary/diagnostic overview.

    Returns a concise summary of the package without listing all objects.
    Default limit=0 gives "package envelope + diagnostics summary" semantics.
    """
    doc = parse_package_document(file_path, depth=depth)
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
    selected = select_objects(doc, object_ids=object_ids, roles=roles, classes=classes)
    return project_document(
        doc,
        object_ids=object_ids,
        roles=roles,
        classes=classes,
        offset=offset,
        limit=limit,
        max_bytes=max_bytes,
        response_extras={"total": len(selected), "offset": offset},
    )


def get_object(
    file_path: str,
    object_id: str,
    *,
    max_bytes: int = _MAX_BYTES_GET_OBJECT,
) -> dict[str, Any]:
    """Tool: get_object — single object properties and optional semantic.

    Returns full object detail including serial region and diagnostics.

    Existence is decided on the parsed document before the byte budget is
    applied (#644): the old order trimmed the whole envelope first and then
    read the resulting empty page as a missing object.
    """
    doc = parse_package_document(file_path)

    if not any(o.id == object_id for o in doc.objects):
        # Stable structured-diagnostic shape (cf. extract_payload's deferred code):
        # consumers branch on code/stage/recoverable, not on message text.
        return {
            "error": f"Object '{object_id}' not found",
            "code": "OBJECT_NOT_FOUND",
            "stage": "agent.get_object",
            "recoverable": True,
            "available_ids": [o.id for o in doc.objects[:20]],
        }

    full = project_document(doc, object_ids=[object_id], view="raw")
    # The whole response is what the budget has to cover; the object alone is
    # never returned over cap, and 'too small' is never dressed up as 'missing'.
    size = len(json.dumps(full, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if size <= max_bytes:
        return full["objects"][0]
    return {
        "error": f"Object '{object_id}' exists but needs {size} bytes, over the {max_bytes}-byte budget",
        "code": "BUDGET_EXHAUSTED",
        "stage": "agent.get_object",
        "recoverable": True,
        "object_id": object_id,
        "max_bytes": max_bytes,
        "min_bytes": size,
    }


def list_dependencies(
    file_path: str,
    *,
    offset: int = 0,
    limit: int = 50,
    max_bytes: int = _MAX_BYTES_LIST_DEPS,
) -> dict[str, Any]:
    """Tool: list_dependencies — paginated full import dependency set.

    Pages the complete `doc.dependencies` import set; the response is bounded
    to `max_bytes` by dropping trailing items (adjust `next_offset` accordingly).
    """
    doc = parse_package_document(file_path)
    deps = [dependency_to_dict(d) for d in doc.dependencies]
    page, next_offset, _trunc = paginate(deps, offset=offset, limit=limit)
    response: dict[str, Any] = {
        "dependencies": page,
        "total_dependencies": len(deps),
        "offset": offset,
        "returned": len(page),
    }
    if next_offset is not None:
        response["next_offset"] = next_offset
    return fit_list_response(response, max_bytes, list_key="dependencies", total_key="total_dependencies")


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

    # Apply filters
    filtered = list(doc.diagnostics)
    if stage:
        filtered = [d for d in filtered if d.stage == stage]
    if severity:
        filtered = [d for d in filtered if d.severity == severity]
    if object_id:
        filtered = [d for d in filtered if d.object_id == object_id]

    # Paginate
    page, next_offset, _truncation = paginate(filtered, offset=offset, limit=limit)

    response: dict[str, Any] = {
        "diagnostics": [d.to_dict() for d in page],
        "total": len(filtered),
        "offset": offset,
        "returned": len(page),
        **({"next_offset": next_offset} if next_offset is not None else {}),
    }
    return fit_list_response(response, max_bytes, list_key="diagnostics")


def extract_payload(
    file_path: str,
    payload_id: str,
    *,
    max_bytes: int = _MAX_BYTES_EXTRACT_PAYLOAD,
    offset: int = 0,
) -> dict[str, Any]:
    """Tool: extract_payload — deferred; never opens or reads the file.

    Real extraction requires .uexp/.ubulk/.utoc/.ucas container support
    (issue #621).  Legacy emits no payload descriptors, so the response
    is always the stable deferred error shape.
    """
    from .models.payloads import PAYLOAD_EXTRACTION_DEFERRED, PAYLOAD_EXTRACTION_DEFERRED_MESSAGE

    response: dict[str, Any] = {
        "id": payload_id,
        "error": PAYLOAD_EXTRACTION_DEFERRED_MESSAGE,
        "code": PAYLOAD_EXTRACTION_DEFERRED,
        "available_ids": [],
        # fit_list_response requires offset/returned/total whenever the list
        # carries items; there is no larger universe behind available_ids
        # today, so returned/total are the length of the visible list.
        "offset": 0,
        "returned": 0,
        "total": 0,
    }
    return fit_list_response(response, max_bytes, list_key="available_ids")
