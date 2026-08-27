"""Payloads — extraction API for large binary data.

Payloads are references to bulk data (textures, audio, meshes) stored
in external regions (.ubulk, .uptnl, .ucas). The v2 model returns
descriptors only; actual extraction uses this module.

Phase 5 stub — real extraction requires Zen/IoStore container support.
"""

from __future__ import annotations

from dataclasses import dataclass

from .object_model import PayloadDescriptor
from .document import PackageDocument


@dataclass
class PayloadExtractionResult:
    """Result of a payload extraction attempt."""

    payload_id: str
    success: bool
    data: bytes | None = None
    error: str | None = None
    bytes_extracted: int = 0


def list_payloads(doc: PackageDocument) -> list[PayloadDescriptor]:
    """List all payload descriptors in a document."""
    return list(doc.payloads)


def extract_payload_bytes(
    doc: PackageDocument,
    payload_id: str,
    *,
    max_bytes: int | None = None,
) -> PayloadExtractionResult:
    """Extract payload bytes by ID.

    Phase 5 stub — payloads are currently empty.
    When Zen/IoStore support is implemented, this will:
    1. Look up the payload descriptor
    2. Resolve the source region (main, uexp, ubulk, ucas)
    3. Read from the appropriate Source
    4. Decompress if needed
    5. Return the bytes (bounded by max_bytes)
    """
    for p in doc.payloads:
        if p.id == payload_id:
            if p.status == "unsupported":
                return PayloadExtractionResult(
                    payload_id=payload_id,
                    success=False,
                    error="Payload extraction requires Phase 5 (Zen/Container) implementation",
                )
            if p.status == "missing":
                return PayloadExtractionResult(
                    payload_id=payload_id,
                    success=False,
                    error=f"Payload data missing from source region '{p.source_region}'",
                )
            return PayloadExtractionResult(
                payload_id=payload_id,
                success=False,
                error=f"Payload status '{p.status}' — extraction not yet implemented",
            )

    return PayloadExtractionResult(
        payload_id=payload_id,
        success=False,
        error=f"Payload '{payload_id}' not found in document",
    )


def write_payload_to_file(
    doc: PackageDocument,
    payload_id: str,
    output_path: str,
    *,
    max_bytes: int | None = None,
) -> PayloadExtractionResult:
    """Extract payload and write to a file.

    Phase 5 stub — same as extract_payload_bytes but writes to disk.
    """
    result = extract_payload_bytes(doc, payload_id, max_bytes=max_bytes)
    if result.success and result.data is not None:
        try:
            with open(output_path, "wb") as f:
                f.write(result.data)
        except OSError as e:
            return PayloadExtractionResult(
                payload_id=payload_id,
                success=False,
                error=f"Failed to write file: {e}",
            )
    return result
