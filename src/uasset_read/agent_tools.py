"""Agent tools — two library tools for programmatic consumers.

``inspect_package(file_path, *, mode=...)`` returns the same v4 package
document as ``project_document(parse_package_document(...))``. ``extract_payload``
stays a separate explicit binary operation with its own byte budget.
In-library API only; no MCP server/SDK or other agent transport here.

Errors are structured diagnostics, not log stacks; tools call the Python
document API directly.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, cast

from .exceptions import BINARY_READ_ERRORS, ParseError, VersionError
from .models.document import PackageDocument
from .package import parse_package_document
from .projection import project_document

# Max response size for extract_payload (bytes)
_MAX_BYTES_EXTRACT_PAYLOAD = 65536

# Canonical schema spelling is payload:export:N / payload:import:N; the
# parenthesized spelling payload:(export:N) is accepted only as a
# backward-compatible request alias.
_PAYLOAD_ID_RE = re.compile(
    r"^payload:(?:\((?P<p_kind>export|import):(?P<p_idx>\d+)\)"
    r"|(?P<s_kind>export|import):(?P<s_idx>\d+))$"
)


def json_byte_size(payload: Any) -> int:
    """Compact-JSON UTF-8 byte length — the single measure every byte-budget check shares."""
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def fit_list_response(response: dict, max_bytes: int, *, list_key: str, total_key: str = "total") -> dict:
    """Drop trailing items from response[list_key] until the compact encoding fits max_bytes.

    Mutates ``response`` in place; it must carry {list_key (a list), "offset",
    "returned", total_key}. Raises ValueError when max_bytes cannot hold even
    the empty-list envelope.
    """
    items = response[list_key]
    while json_byte_size(response) > max_bytes and items:
        items.pop()
        n = len(items)
        response["returned"] = n
        response["next_offset"] = response["offset"] + n
    if not items:
        response.pop("next_offset", None)  # a cursor that doesn't advance ends nothing
    size = json_byte_size(response)  # one measure serves both the test and the message
    if size > max_bytes:
        raise ValueError(f"Response budget {max_bytes} bytes too small for minimal envelope ({size} bytes)")
    if items and response["offset"] + len(items) >= response[total_key]:
        response.pop("next_offset", None)  # a cursor past the real end is a lie
    return response


def _parse_payload_id(payload_id: str) -> tuple[Literal["export", "import"], int] | None:
    """Parse canonical or parenthesized payload ids; None when malformed."""
    m = _PAYLOAD_ID_RE.match(payload_id.strip())
    if not m:
        return None
    kind = cast(Literal["export", "import"], m.group("p_kind") or m.group("s_kind"))
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
    mode: Literal["normal", "debug"] = "normal",
) -> dict[str, Any]:
    """Tool: inspect_package — the v4 package document for one package.

    Parses the full document at decode depth and returns exactly
    ``project_document(document, mode=mode)``.
    """
    doc, error = _parse_or_error(file_path, stage="agent.inspect_package", depth="decode")
    if error is not None:
        return error
    assert doc is not None
    return project_document(doc, mode=mode)


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

    def _unavailable(
        message: str,
        code: str = PAYLOAD_EXTRACTION_DEFERRED,
        stage: str | None = None,
    ) -> dict[str, Any]:
        """Bounded deferred/unavailable envelope, fitted to the list budget."""
        response: dict[str, Any] = {
            "id": payload_id,
            "error": message,
            "code": code,
            "available_ids": [],
            "offset": 0,
            "returned": 0,
            "total": 0,
        }
        if stage is not None:
            response["stage"] = stage
            response["recoverable"] = True
        return fit_list_response(response, max_bytes, list_key="available_ids")

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
        return _unavailable(
            "Payload extraction is deferred: real payloads require per-export "
            "BulkData mapping from cooked fixtures (issue #627)"
        )

    if export_index is None:
        export_index = _parse_export_index(payload_id)

    if export_index is None:
        return _unavailable(
            "Payload extraction is deferred: real payloads require per-export "
            "BulkData mapping from cooked fixtures (issue #627)"
        )

    # Discovery: BulkData header scan with serial-region fallback.
    descriptor = discover_payload_descriptor(
        payload_id,
        export_index,
        main_path=main_path,
        sidecar_paths=sidecar_paths,
    )

    if descriptor.status == "missing" or descriptor.stored_size <= 0:
        return _unavailable("Payload not available for this export index")

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
        return _unavailable(
            error,
            code=PAYLOAD_EXTRACTION_DEFERRED if error == PAYLOAD_EXTRACTION_DEFERRED else "EXTRACTION_FAILED",
            stage="agent.extract_payload",
        )

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
