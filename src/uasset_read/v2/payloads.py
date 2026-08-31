"""Payloads — extraction API for large binary data.

Payloads are references to bulk data (textures, audio, meshes) stored
in external regions (.uexp, .ubulk, .uptnl, .ucas). The v2 model keeps
the descriptor surface; extraction is deferred until container-backed
source regions and legitimate sample fixtures exist (issue #621).
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


PAYLOAD_EXTRACTION_DEFERRED = "PAYLOAD_EXTRACTION_DEFERRED"

PAYLOAD_EXTRACTION_DEFERRED_MESSAGE = (
    "Payload extraction is deferred: real payloads require "
    ".uexp/.ubulk/.utoc/.ucas container support (issue #621)"
)


def extract_payload_bytes(
    doc: PackageDocument,
    payload_id: str,
    *,
    max_bytes: int | None = None,
    offset: int = 0,
) -> PayloadExtractionResult:
    """Always defers — never opens the file or returns bytes.

    Fabricated "property-end to export-end" descriptors were retracted;
    until container-backed source regions exist there is nothing
    legitimately extractable, so every attempt fails with
    ``PAYLOAD_EXTRACTION_DEFERRED`` semantics and no truncation state.
    """
    return PayloadExtractionResult(
        payload_id=payload_id,
        success=False,
        error=PAYLOAD_EXTRACTION_DEFERRED_MESSAGE,
    )
