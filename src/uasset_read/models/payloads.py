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
from typing import Literal


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


PAYLOAD_EXTRACTION_DEFERRED = "PAYLOAD_EXTRACTION_DEFERRED"


def extract_payload_bytes(
    descriptor: PayloadDescriptor,
    main_path: Path,
    sidecar_paths: dict[str, Path] | None = None,
) -> tuple[bytes, str | None]:
    """Extract payload bytes from a cooked package.

    Reads actual bytes from the appropriate file (main or sidecar) based on
    the descriptor's source_region and offset fields.

    Args:
        descriptor: Payload descriptor from the package.
        main_path: Path to the main .uasset file.
        sidecar_paths: Optional dict mapping region names to sidecar file paths.

    Returns:
        (data, error) tuple. data is the extracted bytes; error is None on success.
    """
    sidecar_paths = sidecar_paths or {}

    # Determine which file to read from
    if descriptor.source_region == "main":
        file_path = main_path
    elif descriptor.source_region in sidecar_paths:
        file_path = sidecar_paths[descriptor.source_region]
    else:
        # No sidecar available, return deferred
        return (b"", PAYLOAD_EXTRACTION_DEFERRED)

    # Read the payload bytes
    try:
        with open(file_path, "rb") as f:
            f.seek(descriptor.offset)
            data = f.read(descriptor.stored_size)

        if len(data) < descriptor.stored_size:
            return (
                data,
                f"Short read: expected {descriptor.stored_size} bytes, got {len(data)}",
            )

        return (data, None)
    except Exception as e:
        return (b"", f"Read failed: {e}")
