"""Opaque handler factory function -- eliminates duplicate partial metadata handler code.

All opaque handlers returning partial_metadata share the same logic:
read up to 256 bytes of sample data at current position, return raw_offset + sample_size + parse_status.
Use make_opaque_stub() to generate, avoiding one stub file per type.
"""

from typing import Any, Callable


def make_opaque_stub(class_name: str) -> Callable[[Any, list[str]], dict[str, Any]]:
    """Create an opaque partial metadata handler.

    The generated function reads up to 256 bytes of sample data at the current archive position,
    returning a dictionary containing raw_offset, sample_size, and parse_status.

    Args:
        class_name: UE class name (for logging/diagnostics)

    Returns:
        Parse function with signature (archive, name_map) -> dict
    """

    def _parse(archive: Any, name_map: list[str]) -> dict[str, Any]:
        start = archive.tell()
        remaining = max(0, archive.total_size() - start)
        sample = archive.read(min(remaining, 256))
        return {
            "raw_offset": start,
            "sample_size": len(sample),
            "parse_status": "partial_metadata",
        }

    return _parse
