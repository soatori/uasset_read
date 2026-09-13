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

from typing import Any, Literal

from .package import parse_package_document
from .projection import dependency_to_dict, fit_list_response, json_byte_size, paginate, project_document, select_objects

# Max response sizes per tool (bytes)
_MAX_BYTES_INSPECT = 4096
_MAX_BYTES_LIST_OBJECTS = 16384
_MAX_BYTES_GET_OBJECT = 32768
_MAX_BYTES_LIST_DEPS = 8192
_MAX_BYTES_GET_DIAG = 8192
_MAX_BYTES_EXTRACT_PAYLOAD = 65536


def _err(
    code: str,
    stage: str,
    *,
    recoverable: bool,
    message: str,
    **extra: Any,
) -> dict[str, Any]:
    """Stable structured-error envelope for agent tools."""
    return {
        "error": message,
        "code": code,
        "stage": stage,
        "recoverable": recoverable,
        **extra,
    }


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
    return project_document(doc, depth=depth, limit=limit, max_bytes=max_bytes)


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
        return _err(
            "OBJECT_NOT_FOUND",
            "agent.get_object",
            recoverable=True,
            message=f"Object '{object_id}' not found",
            available_ids=[o.id for o in doc.objects[:20]],
        )

    full = project_document(doc, object_ids=[object_id], view="raw")
    # The whole response is what the budget has to cover; the object alone is
    # never returned over cap, and 'too small' is never dressed up as 'missing'.
    size = json_byte_size(full)
    if size <= max_bytes:
        return full["objects"][0]
    return _err(
        "BUDGET_EXHAUSTED",
        "agent.get_object",
        recoverable=True,
        message=f"Object '{object_id}' exists but needs {size} bytes, over the {max_bytes}-byte budget",
        object_id=object_id,
        max_bytes=max_bytes,
        min_bytes=size,
    )


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
    export_index: int | None = None,
) -> dict[str, Any]:
    """Tool: extract_payload — extract payload bytes from a cooked package.

    Parses the package, delegates payload discovery (sidecar map, serial
    region, BulkData headers) to models.payloads, and enforces the response
    byte budget.

    Args:
        file_path: Path to the .uasset file.
        payload_id: Payload identifier (e.g., "payload:(export:0)").
        max_bytes: Maximum response size in bytes.
        export_index: Index of the export that owns the payload. If not
            provided, derived from payload_id.

    Returns:
        Dict with either 'data' (base64-encoded) or 'error'.
    """
    import base64
    from pathlib import Path

    from .models.payloads import (
        PAYLOAD_EXTRACTION_DEFERRED,
        discover_payload_descriptor,
        extract_payload_bytes,
    )
    from .package import open_package_bundle

    main_path = Path(file_path)
    if not main_path.exists():
        return _err(
            "PACKAGE_NOT_FOUND",
            "agent.extract_payload",
            recoverable=False,
            message=f"Package not found: {file_path}",
        )

    # Discover sidecars
    try:
        bundle = open_package_bundle(str(main_path))
    except Exception as e:
        return _err(
            "BUNDLE_OPEN_FAILED",
            "agent.extract_payload",
            recoverable=False,
            message=f"Failed to open package bundle: {e}",
        )

    # Build sidecar paths dict
    sidecar_paths: dict[str, Path] = {}
    if bundle.uexp_path is not None:
        sidecar_paths["uexp"] = bundle.uexp_path
    if bundle.ubulk_path is not None:
        sidecar_paths["ubulk"] = bundle.ubulk_path
    if bundle.uptnl_path is not None:
        sidecar_paths["uptnl"] = bundle.uptnl_path

    # Determine export index from payload_id if not provided
    if export_index is None:
        import re

        match = re.search(r"\((export|import):(\d+)\)", payload_id)
        if match:
            export_index = int(match.group(2))

    if export_index is None:
        response = {
            "id": payload_id,
            "error": "Payload extraction is deferred: real payloads require per-export BulkData mapping from cooked fixtures (issue #627)",
            "code": PAYLOAD_EXTRACTION_DEFERRED,
            "available_ids": [],
            "offset": 0,
            "returned": 0,
            "total": 0,
        }
        return fit_list_response(response, max_bytes, list_key="available_ids")

    # Discovery: BulkData header scan with serial-region fallback.
    descriptor = discover_payload_descriptor(
        payload_id,
        export_index,
        main_path=main_path,
        sidecar_paths=sidecar_paths,
    )

    # Extract payload bytes
    data, error = extract_payload_bytes(
        descriptor,
        main_path=main_path,
        sidecar_paths=sidecar_paths,
    )

    if error is not None:
        # Return structured error
        response = {
            "id": payload_id,
            "error": error,
            "code": PAYLOAD_EXTRACTION_DEFERRED if error == PAYLOAD_EXTRACTION_DEFERRED else "EXTRACTION_FAILED",
            "stage": "agent.extract_payload",
            "recoverable": True,
            "available_ids": [],
            "offset": 0,
            "returned": 0,
            "total": 0,
        }
        return fit_list_response(response, max_bytes, list_key="available_ids")

    # Encode as base64 for JSON serialization
    encoded_data = base64.b64encode(data).decode("ascii")
    response_payload = {
        "id": payload_id,
        "payload_id": descriptor.id,
        "data": encoded_data,
        "size": len(data),
        "source_region": descriptor.source_region,
        "offset": descriptor.offset,
    }

    # Enforce max_bytes on success path
    response_size = json_byte_size(response_payload)
    if response_size > max_bytes:
        return _err(
            "BUDGET_EXHAUSTED",
            "agent.extract_payload",
            recoverable=True,
            message=f"Payload response ({response_size} bytes) exceeds budget ({max_bytes} bytes)",
            object_id=payload_id,
            max_bytes=max_bytes,
            min_bytes=response_size,
        )

    return response_payload
