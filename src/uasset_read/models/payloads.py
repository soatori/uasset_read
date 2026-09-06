"""Payload models for large binary data.

PayloadDescriptor matches the v2 contract schema
(docs/designs/contract/package_document_v2.schema.json $defs.PayloadDescriptor).
kind and source_region are schema-enums; per-export BulkData payloads
(#627) need real cooked fixtures to emit real descriptors, so today
zero emitters exist and this dataclass is a contract-sync placeholder.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional


@dataclass(frozen=True)
class PayloadDescriptor:
    """Descriptor for a large payload that can be extracted on demand.

    Fields match $defs.PayloadDescriptor in the v2 contract schema.
    No emitter populates this yet — per-export BulkData offsets need
    cooked fixtures (#627).  kind and source_region use the schema's
    enum values; the old kind Literal['ubulk','uexp',...] was wrong.
    """

    id: str  # ^payload:(export|import):[0-9]+$
    owner: str  # ^(export|import):[0-9]+$
    kind: Literal["texture_mip", "audio", "mesh_vertex", "mesh_index", "bulk_data", "other"]
    source_region: Literal["main", "uexp", "ubulk", "uptnl", "ucas"]
    offset: int  # sidecar-relative or main-relative, never fabricated
    stored_size: int
    status: Literal["available", "external", "missing", "unsupported"]
    logical_size: int | None = None
    compression: str | None = None
    hash: str | None = None


@dataclass
class PayloadExtraction:
    """Result of payload extraction."""

    descriptor: PayloadDescriptor
    data: bytes
    extracted: bool = True
    error: str | None = None


PAYLOAD_EXTRACTION_DEFERRED = "PAYLOAD_EXTRACTION_DEFERRED"

PAYLOAD_EXTRACTION_DEFERRED_MESSAGE = (
    "Payload extraction is deferred: real payloads require "
    "per-export BulkData mapping from cooked fixtures (issue #627)"
)


def extract_payload_bytes(
    descriptor: PayloadDescriptor,
    main_path: Path,
    sidecar_paths: Optional[dict[str, Path]] = None,
) -> PayloadExtraction:
    """Extract payload bytes from a cooked package.

    Currently returns PAYLOAD_EXTRACTION_DEFERRED for all attempts.
    Real extraction will follow when BulkData mapping is implemented.

    Args:
        descriptor: Payload descriptor from the package.
        main_path: Path to the main .uasset file.
        sidecar_paths: Optional dict mapping region names to sidecar file paths.

    Returns:
        PayloadExtraction with data or error.
    """
    # For now, return deferred for all extraction attempts
    # Real implementation will follow in Task 4
    return PayloadExtraction(
        descriptor=descriptor,
        data=b"",
        extracted=False,
        error=PAYLOAD_EXTRACTION_DEFERRED,
    )
