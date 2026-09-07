"""Opaque partial-metadata handler shared by all stub-registered asset types.

Every opaque handler returns partial_metadata with the same logic: read up to
256 bytes of sample data at the current position, return raw_offset +
sample_size + parse_status. One module function, referenced directly by the
registration table — no factory, no per-handler closure.
"""

from typing import Any


def parse_opaque_stub(archive: Any, name_map: list[str]) -> dict[str, Any]:
    """Read up to 256 sample bytes at the current position; report partial metadata."""
    start = archive.tell()
    remaining = max(0, archive.total_size() - start)
    sample = archive.read(min(remaining, 256))
    return {
        "raw_offset": start,
        "sample_size": len(sample),
        "parse_status": "partial_metadata",
    }
