"""Payloads — extraction API for large binary data.

Payloads are references to bulk data (textures, audio, meshes) stored
in external regions (.ubulk, .uptnl, .ucas). The v2 model returns
descriptors only; actual extraction uses this module.

Phase 5 stub — real extraction requires Zen/IoStore container support.
"""

from __future__ import annotations

from dataclasses import dataclass

from .document import PackageDocument


@dataclass
class PayloadExtractionResult:
    """Result of a payload extraction attempt."""

    payload_id: str
    success: bool
    data: bytes | None = None
    error: str | None = None
    bytes_extracted: int = 0
    truncated: bool = False
    next_offset: int | None = None


def extract_payload_bytes(
    doc: PackageDocument,
    payload_id: str,
    *,
    max_bytes: int | None = None,
    offset: int = 0,
) -> PayloadExtractionResult:
    """Extract payload bytes by ID from the descriptor's bounded region.

    Legacy descriptors point at ``main`` (the .uasset file itself) and are
    extractable now.  External regions (ubulk/uptnl/ucas, Zen containers)
    stay unsupported until Phase 2 container work — that is reported as an
    error, never returned as fake data.

    ``max_bytes`` bounds the read; when the payload exceeds the budget the
    result carries ``truncated=True`` and a resumable ``next_offset``.
    """
    budget = 16 * 1024 * 1024 if max_bytes is None else max(0, max_bytes)
    for p in doc.payloads:
        if p.id != payload_id:
            continue
        if p.status != "available" or p.source_region != "main":
            return PayloadExtractionResult(
                payload_id=payload_id,
                success=False,
                error=(
                    f"Payload region '{p.source_region}' (status '{p.status}') is not "
                    "extractable; external container support is deferred"
                ),
            )
        if doc.source.kind != "loose" or not doc.source.path:
            return PayloadExtractionResult(
                payload_id=payload_id,
                success=False,
                error=f"Payload source kind '{doc.source.kind}' is not file-backed",
            )
        start = p.offset + max(0, offset)
        remaining = max(0, p.stored_size - max(0, offset))
        length = min(remaining, budget)
        try:
            with open(doc.source.path, "rb") as stream:
                stream.seek(start)
                data = stream.read(length)
        except OSError as e:
            return PayloadExtractionResult(payload_id=payload_id, success=False, error=str(e))
        truncated = remaining > len(data)
        return PayloadExtractionResult(
            payload_id=payload_id,
            success=True,
            data=data,
            bytes_extracted=len(data),
            truncated=truncated,
            # next_offset is relative to the payload start, matching the
            # offset parameter the caller passes back in.
            next_offset=max(0, offset) + len(data) if truncated else None,
        )

    return PayloadExtractionResult(
        payload_id=payload_id,
        success=False,
        error=f"Payload '{payload_id}' not found in document",
    )
