"""Payload models and discovery for large binary data.

PayloadDescriptor matches the v2 contract schema
(tests/package_document_v4.schema.json $defs.PayloadDescriptor).
kind and source_region are schema-enums.  discover_payload_descriptor is the
payload-discovery engine (serial-region fallback); agent_tools is a thin
parse→extract→budget wrapper over it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class PayloadDescriptor:
    """Descriptor for a large payload that can be extracted on demand.

    Fields match $defs.PayloadDescriptor in the v2 contract schema.
    Emitted by discover_payload_descriptor (serial-region fallback);
    kind and source_region use the schema's enum values.
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
    """Locate an export's payload by its physical serial slice.

    Parses the package at ``main_path`` (package depth) and returns a
    descriptor bounded by the export's serial region — never by the whole
    sidecar; a region spanning two files (or an unresolved source) stays
    size-0 / missing.  The emitted ``id`` is the schema-canonical
    ``payload:export:N`` form.

    Args:
        payload_id: Caller identifier echoed unchanged when export_index is
            invalid; the Agent boundary accepts only the canonical
            ``payload:export:N`` form.
        export_index: Index of the export that owns the payload.
        main_path: Path to the main .uasset/.umap file.
        sidecar_paths: Region name ("uexp"/"ubulk"/"uptnl") to sidecar path.

    Returns:
        A PayloadDescriptor; never None.  Bytes are read separately via
        extract_payload_bytes.
    """
    from ..package import parse_package_document

    descriptor_id = f"payload:export:{export_index}" if export_index >= 0 else payload_id
    if export_index < 0:
        return PayloadDescriptor(
            id=descriptor_id,
            owner=f"export:{export_index}",
            kind="other",
            source_region="main",
            offset=0,
            stored_size=0,
            status="missing",
        )

    from ..exceptions import BINARY_READ_ERRORS, ParseError, VersionError

    try:
        doc = parse_package_document(str(main_path), depth="package")
    except BINARY_READ_ERRORS + (ParseError, VersionError):
        doc = None

    if doc is None or export_index >= len(doc.objects):
        return PayloadDescriptor(
            id=descriptor_id,
            owner=f"export:{export_index}",
            kind="other",
            source_region="main",
            offset=0,
            stored_size=0,
            status="missing",
        )

    export = doc.objects[export_index]

    # Fallback: address the export's physical serial slice — the file and
    # offset where the bytes actually are, not a TotalHeaderSize rebase.
    # Never fall back to the whole sidecar; a region spanning two files (or
    # an unresolved source) is not extractable, so it stays size-0 / missing.
    source_region = "main"
    fallback_offset = 0
    fallback_size = 0
    slices = export.serial_region.source_slices if export.serial_region is not None else ()
    if len(slices) == 1:
        sl = slices[0]
        region: str | None = (
            "main"
            if sl.source_id == main_path.name
            else next((key for key, path in sidecar_paths.items() if path.name == sl.source_id), None)
        )
        if region is not None:
            source_region = region
            fallback_offset = sl.source_start
            fallback_size = sl.size

    return PayloadDescriptor(
        id=descriptor_id,
        owner=f"export:{export_index}",
        # Unclassified bytes are "other"; the bulk kind stays unproduced without a UE-evidenced reader.
        kind="other",
        source_region=source_region,  # type: ignore[arg-type]
        offset=fallback_offset,
        stored_size=fallback_size,
        status="available" if fallback_size > 0 else "missing",
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

    # Reject invalid descriptors before any file open/read.
    if descriptor.stored_size < 0 or descriptor.offset < 0:
        return (b"", "INVALID_PAYLOAD_DESCRIPTOR")

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
