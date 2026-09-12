"""Payload models and discovery for large binary data.

PayloadDescriptor matches the v2 contract schema
(docs/designs/contract/package_document_v2.schema.json $defs.PayloadDescriptor).
kind and source_region are schema-enums.  discover_payload_descriptor is the
payload-discovery engine (serial-region seek + BulkData header scan with a
bounded fallback); agent_tools is a thin parse→extract→budget wrapper over it.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class PayloadDescriptor:
    """Descriptor for a large payload that can be extracted on demand.

    Fields match $defs.PayloadDescriptor in the v2 contract schema.
    Emitted by discover_payload_descriptor (BulkData / serial-region
    fallback); kind and source_region use the schema's enum values.
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


def discover_payload_descriptor(
    payload_id: str,
    export_index: int,
    *,
    main_path: Path,
    sidecar_paths: dict[str, Path],
) -> PayloadDescriptor:
    """Locate an export's payload: BulkData header scan, then serial-region fallback.

    Parses the package at ``main_path`` (package depth), reads the export's
    serial region from the main file or the .uexp sidecar, and prefers a
    BulkData header found in that serial data.  When no header is found (or
    the export/serial region is unavailable), returns a descriptor bounded by
    the export's serial region — or by the whole sidecar as a last resort.

    Args:
        payload_id: Payload identifier echoed into the descriptor (e.g.
            "payload:(export:0)").
        export_index: Index of the export that owns the payload.
        main_path: Path to the main .uasset/.umap file.
        sidecar_paths: Region name ("uexp"/"ubulk"/"uptnl") to sidecar path.

    Returns:
        A PayloadDescriptor; never None.  Bytes are read separately via
        extract_payload_bytes.
    """
    from ..package import parse_package_document
    from ..parsers.bulk_data import (
        BULKDATA_CompressedOodle,
        BULKDATA_CompressedZlib,
        extract_bulk_data_descriptors,
    )

    try:
        doc = parse_package_document(str(main_path), depth="package")
    except Exception:
        doc = None

    descriptor: PayloadDescriptor | None = None
    if doc is not None and export_index < len(doc.objects):
        export = doc.objects[export_index]
        if export.serial_region is not None and export.serial_region.size > 0:
            # For cooked packages, serial data may be in the uexp sidecar.
            # serial_region.offset is absolute in the combined stream; if
            # offset >= total_header_size, data lives in the uexp sidecar.
            total_header_size = doc.package.total_header_size
            serial_offset = export.serial_region.offset
            serial_size = export.serial_region.size

            serial_data = b""
            try:
                if serial_offset >= total_header_size and total_header_size > 0:
                    uexp_path = sidecar_paths.get("uexp")
                    if uexp_path is not None:
                        with open(uexp_path, "rb") as f:
                            f.seek(serial_offset - total_header_size)
                            serial_data = f.read(serial_size)
                else:
                    with open(main_path, "rb") as f:
                        f.seek(serial_offset)
                        serial_data = f.read(serial_size)

                if len(serial_data) < serial_size:
                    serial_data = b""  # Short read, skip BulkData extraction
            except (OSError, ValueError):
                # Include diagnostic but don't fail — fallback will handle
                serial_data = b""

            if serial_data:
                try:
                    bulk_headers = extract_bulk_data_descriptors(serial_data)
                    if bulk_headers:
                        # Use the first (last in serial data) BulkData header
                        header = bulk_headers[0]

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
                except (ValueError, struct.error):
                    # BulkData parsing failed — fallback will handle
                    pass

    if descriptor is not None:
        return descriptor

    # Fallback: bound the read by the export's serial region when known.
    source_region = "uexp" if "uexp" in sidecar_paths else "ubulk" if "ubulk" in sidecar_paths else "main"
    fallback_offset = 0
    fallback_size = 0
    if doc is not None and export_index < len(doc.objects):
        export = doc.objects[export_index]
        if export.serial_region is not None:
            total_header_size = doc.package.total_header_size
            if export.serial_region.offset >= total_header_size and total_header_size > 0:
                fallback_offset = export.serial_region.offset - total_header_size
            fallback_size = export.serial_region.size

    if fallback_size == 0:
        # No serial region info — use entire sidecar as last resort
        sidecar_path = sidecar_paths.get(source_region)
        if sidecar_path is not None:
            try:
                fallback_size = sidecar_path.stat().st_size
            except OSError:
                fallback_size = 0

    return PayloadDescriptor(
        id=payload_id,
        owner=f"export:{export_index}",
        kind="bulk_data",
        source_region=source_region,  # type: ignore[arg-type]
        offset=fallback_offset,
        stored_size=fallback_size,
        status="available",
    )


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
