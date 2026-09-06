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
import struct
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
    export_index: int | None = None,
) -> dict[str, Any]:
    """Tool: extract_payload — extract payload bytes from a cooked package.

    Discovers sidecar files via PackageBundle, parses the package to locate
    the export, and extracts payload bytes from the appropriate region.

    Args:
        file_path: Path to the .uasset file.
        payload_id: Payload identifier (e.g., "payload:(export:0)").
        max_bytes: Maximum response size in bytes.
        offset: Byte offset for pagination (unused for now).
        export_index: Index of the export that owns the payload. If not
            provided, derived from payload_id.

    Returns:
        Dict with either 'data' (base64-encoded) or 'error'.
    """
    import base64
    from pathlib import Path

    from .models.payloads import (
        PAYLOAD_EXTRACTION_DEFERRED,
        PAYLOAD_EXTRACTION_DEFERRED_MESSAGE,
        PayloadDescriptor,
        extract_payload_bytes,
    )
    from .package import open_package_bundle

    main_path = Path(file_path)
    if not main_path.exists():
        return {
            "error": f"Package not found: {file_path}",
            "code": "PACKAGE_NOT_FOUND",
            "stage": "agent.extract_payload",
            "recoverable": False,
        }

    # Discover sidecars
    try:
        bundle = open_package_bundle(str(main_path))
    except Exception as e:
        return {
            "error": f"Failed to open package bundle: {e}",
            "code": "BUNDLE_OPEN_FAILED",
            "stage": "agent.extract_payload",
            "recoverable": False,
        }

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
        # Try to parse from payload_id format: "payload:(export:N)" or "payload:(import:N)"
        import re
        match = re.search(r"\((export|import):(\d+)\)", payload_id)
        if match:
            export_index = int(match.group(2))
        else:
            # Cannot determine export index, return deferred
            response: dict[str, Any] = {
                "id": payload_id,
                "error": PAYLOAD_EXTRACTION_DEFERRED_MESSAGE,
                "code": PAYLOAD_EXTRACTION_DEFERRED,
                "available_ids": [],
                "offset": 0,
                "returned": 0,
                "total": 0,
            }
            return fit_list_response(response, max_bytes, list_key="available_ids")

    # Parse the package to get export serial data for BulkData extraction
    from .parsers.bulk_data import extract_bulk_data_descriptors

    try:
        doc = parse_package_document(str(main_path), depth="package")
    except Exception:
        doc = None

    # Try to extract BulkData descriptors from the export
    descriptor: PayloadDescriptor | None = None
    if doc is not None and export_index < len(doc.objects):
        export = doc.objects[export_index]
        if export.serial_region is not None and export.serial_region.size > 0:
            # For cooked packages, serial data may be in the uexp sidecar.
            # serial_region.offset is absolute in the combined stream.
            # If offset >= total_header_size, data is in the uexp sidecar.
            total_header_size = doc.package.total_header_size
            serial_offset = export.serial_region.offset
            serial_size = export.serial_region.size

            # Determine which file to read serial data from
            serial_data = b""
            try:
                if serial_offset >= total_header_size and total_header_size > 0:
                    # Data is in uexp sidecar
                    uexp_path = sidecar_paths.get("uexp")
                    if uexp_path is not None:
                        with open(uexp_path, "rb") as f:
                            f.seek(serial_offset - total_header_size)
                            serial_data = f.read(serial_size)
                        serial_source = "uexp"
                else:
                    # Data is in main file
                    with open(main_path, "rb") as f:
                        f.seek(serial_offset)
                        serial_data = f.read(serial_size)

                if len(serial_data) < serial_size:
                    serial_data = b""  # Short read, skip BulkData extraction
            except (OSError, ValueError) as e:
                # Include diagnostic but don't fail — fallback will handle
                serial_data = b""

            # Try BulkData extraction if we have serial data
            if serial_data:
                try:
                    bulk_headers = extract_bulk_data_descriptors(
                        serial_data,
                        base_offset=serial_offset,
                        export_index=export_index,
                    )

                    if bulk_headers:
                        # Use the first (last in serial data) BulkData header
                        header = bulk_headers[0]

                        # Determine source region from header flags
                        from .parsers.bulk_data import BULKDATA_CompressedZlib, BULKDATA_CompressedOodle
                        if header.flags & (BULKDATA_CompressedZlib | BULKDATA_CompressedOodle):
                            source_region = "ubulk"
                        elif "uexp" in sidecar_paths:
                            source_region = "uexp"
                        elif "ubulk" in sidecar_paths:
                            source_region = "ubulk"
                        else:
                            source_region = "main"

                        descriptor = PayloadDescriptor(
                            id=payload_id,
                            owner=f"export:{export_index}",
                            kind="bulk_data",
                            source_region=source_region,  # type: ignore[arg-type]
                            offset=header.offset,
                            stored_size=header.size_on_disk,
                            status="available",
                            logical_size=header.element_count,
                            compression=header.compression_type,
                        )
                except (ValueError, struct.error) as e:
                    # BulkData parsing failed — fallback will handle
                    pass

    # Fallback: create a basic descriptor if BulkData extraction failed
    if descriptor is None:
        # Determine source region based on available sidecars
        source_region = "uexp" if "uexp" in sidecar_paths else "ubulk" if "ubulk" in sidecar_paths else "main"

        # For the fallback, we need to bound the read to the export's region.
        # Use serial_region if available, otherwise use the entire sidecar.
        fallback_offset = 0
        fallback_size = 0
        if doc is not None and export_index < len(doc.objects):
            export = doc.objects[export_index]
            if export.serial_region is not None:
                total_header_size = doc.package.total_header_size
                # If serial data is in a sidecar, adjust offset
                if export.serial_region.offset >= total_header_size and total_header_size > 0:
                    fallback_offset = export.serial_region.offset - total_header_size
                else:
                    fallback_offset = 0  # main file case
                fallback_size = export.serial_region.size

        if fallback_size == 0:
            # No serial region info — use entire sidecar as last resort
            sidecar_path = sidecar_paths.get(source_region)
            if sidecar_path is not None:
                try:
                    fallback_size = sidecar_path.stat().st_size
                except OSError:
                    fallback_size = 0

        descriptor = PayloadDescriptor(
            id=payload_id,
            owner=f"export:{export_index}",
            kind="bulk_data",
            source_region=source_region,  # type: ignore[arg-type]
            offset=fallback_offset,
            stored_size=fallback_size,
            status="available",
        )

    # Extract payload bytes
    result = extract_payload_bytes(
        descriptor,
        main_path=main_path,
        sidecar_paths=sidecar_paths,
    )

    if not result.extracted:
        # Return structured error
        response = {
            "id": payload_id,
            "error": result.error,
            "code": PAYLOAD_EXTRACTION_DEFERRED if result.error == PAYLOAD_EXTRACTION_DEFERRED else "EXTRACTION_FAILED",
            "stage": "agent.extract_payload",
            "recoverable": True,
            "available_ids": [],
            "offset": 0,
            "returned": 0,
            "total": 0,
        }
        return fit_list_response(response, max_bytes, list_key="available_ids")

    # Encode as base64 for JSON serialization
    encoded_data = base64.b64encode(result.data).decode("ascii")
    response_payload = {
        "id": payload_id,
        "payload_id": result.descriptor.id,
        "data": encoded_data,
        "size": len(result.data),
        "source_region": result.descriptor.source_region,
        "offset": result.descriptor.offset,
    }

    # Enforce max_bytes on success path
    response_size = len(json.dumps(response_payload, ensure_ascii=False).encode("utf-8"))
    if response_size > max_bytes:
        raise ValueError(
            f"Response budget {max_bytes} bytes too small for payload response "
            f"({response_size} bytes)"
        )

    return response_payload
