"""Agent tools — 6 bounded library tools for programmatic consumers.

Each tool directly calls the v2 Python API and returns structured JSON.
In-library API only; no MCP server/SDK or other agent transport here.

Design doc reference:
- Agent Gate: 6 tools sharing Python API
- Each tool has max response bytes, supports selection/pagination
- Returns stable ids, distinguishes not_requested vs unavailable
- Errors are structured diagnostics, not log stacks
"""

from __future__ import annotations

import re
from typing import Any, Literal

from .exceptions import BINARY_READ_ERRORS, ParseError, VersionError
from .models.document import PackageDocument
from .package import parse_package_document
from .projection import dependency_to_dict, fit_list_response, json_byte_size, paginate, project_document, select_objects

# Max response sizes per tool (bytes)
_MAX_BYTES_INSPECT = 4096
_MAX_BYTES_LIST_OBJECTS = 16384
_MAX_BYTES_GET_OBJECT = 32768
_MAX_BYTES_LIST_DEPS = 8192
_MAX_BYTES_GET_DIAG = 8192
_MAX_BYTES_EXTRACT_PAYLOAD = 65536

# Canonical schema spelling is payload:export:N / payload:import:N; the
# parenthesized spelling payload:(export:N) is accepted only as a
# backward-compatible request alias.
_PAYLOAD_ID_RE = re.compile(
    r"^payload:(?:\((?P<p_kind>export|import):(?P<p_idx>\d+)\)"
    r"|(?P<s_kind>export|import):(?P<s_idx>\d+))$"
)


def _parse_payload_id(payload_id: str) -> tuple[Literal["export", "import"], int] | None:
    """Parse canonical or parenthesized payload ids; None when malformed."""
    m = _PAYLOAD_ID_RE.match(payload_id.strip())
    if not m:
        return None
    kind = m.group("p_kind") or m.group("s_kind")
    raw = m.group("p_idx") if m.group("p_idx") is not None else m.group("s_idx")
    return (kind, int(raw))


def _parse_export_index(payload_id: str) -> int | None:
    """Return the export index for an export payload; imports are deferred."""
    parsed = _parse_payload_id(payload_id)
    return parsed[1] if parsed is not None and parsed[0] == "export" else None


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


def _parse_or_error(
    file_path: str, *, stage: str, **parse_kwargs: Any
) -> tuple[PackageDocument | None, dict[str, Any] | None]:
    """Parse a package, converting parse-layer failures into error envelopes.

    Returns ``(doc, None)`` on success, ``(None, envelope)`` on
    ``FileNotFoundError`` (PACKAGE_NOT_FOUND) or
    ``BINARY_READ_ERRORS + (ParseError, VersionError)`` (PACKAGE_PARSE_FAILED).
    Every parse-backed Agent tool funnels through here so callers receive the
    same structured error shape instead of a leaked parser exception.
    """
    try:
        return parse_package_document(file_path, **parse_kwargs), None
    except FileNotFoundError:
        return None, _err(
            "PACKAGE_NOT_FOUND",
            stage,
            recoverable=False,
            message=f"Package not found: {file_path}",
        )
    except BINARY_READ_ERRORS + (ParseError, VersionError) as exc:
        return None, _err(
            "PACKAGE_PARSE_FAILED",
            stage,
            recoverable=True,
            message=f"Package parse failed: {type(exc).__name__}: {exc}",
        )


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
    doc, error = _parse_or_error(file_path, stage="agent.inspect_package", depth=depth)
    if error is not None:
        return error
    assert doc is not None
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
    doc, error = _parse_or_error(file_path, stage="agent.list_objects")
    if error is not None:
        return error
    assert doc is not None
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
    doc, error = _parse_or_error(file_path, stage="agent.get_object")
    if error is not None:
        return error
    assert doc is not None

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
        obj_entry = full["objects"][0]
        # R4: expose embedded type-aware projection records through get_object.
        # They already rode in the bounded envelope measured above.
        matching = [
            item
            for item in (full.get("projections") or [])
            if isinstance(item, dict) and item.get("source_object_id") == object_id
        ]
        if matching:
            obj_entry = {**obj_entry, "projections": matching}
        return obj_entry
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
    doc, error = _parse_or_error(file_path, stage="agent.list_dependencies")
    if error is not None:
        return error
    assert doc is not None
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
    doc, error = _parse_or_error(file_path, stage="agent.get_diagnostics")
    if error is not None:
        return error
    assert doc is not None

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
        payload_id: Payload identifier (e.g., "payload:export:0"). The
            parenthesized spelling "payload:(export:0)" is accepted only as a
            backward-compatible request alias.
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

    # Always classify the payload id first. An import payload is deferred
    # even when the caller also passes an export_index — import ids are
    # never treated as exports.
    parsed = _parse_payload_id(payload_id)
    if parsed is not None and parsed[0] == "import":
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

    if export_index is None:
        export_index = _parse_export_index(payload_id)

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

    if descriptor.status == "missing" or descriptor.stored_size <= 0:
        response = {
            "id": payload_id,
            "error": "Payload not available for this export index",
            "code": PAYLOAD_EXTRACTION_DEFERRED,
            "available_ids": [],
            "offset": 0,
            "returned": 0,
            "total": 0,
        }
        return fit_list_response(response, max_bytes, list_key="available_ids")

    # Estimate the complete JSON response before opening the payload file.
    # Base64 has an exact 4 * ceil(n / 3) expansion; the empty-data envelope
    # accounts for escaped ids, metadata, and the remaining JSON overhead.
    encoded_size = 4 * ((descriptor.stored_size + 2) // 3)
    empty_response = {
        "id": payload_id,
        "payload_id": descriptor.id,
        "data": "",
        "size": descriptor.stored_size,
        "source_region": descriptor.source_region,
        "offset": descriptor.offset,
    }
    estimated = json_byte_size(empty_response) + encoded_size
    if estimated > max_bytes:
        return _err(
            "BUDGET_EXHAUSTED",
            "agent.extract_payload",
            recoverable=True,
            message=f"Payload stored_size={descriptor.stored_size} would exceed budget {max_bytes}",
            object_id=payload_id,
            max_bytes=max_bytes,
            min_bytes=estimated,
        )

    from .memory_safety import MemoryLimitExceeded, reserve_memory

    try:
        reserve_memory(descriptor.stored_size, "agent.extract_payload", payload_id)
    except MemoryLimitExceeded as e:
        return _err(
            "BUDGET_EXHAUSTED",
            "agent.extract_payload",
            recoverable=False,
            message=str(e),
            object_id=payload_id,
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
