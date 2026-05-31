"""StaticMesh asset metadata extractor."""
from __future__ import annotations

from typing import Any


def parse_static_mesh(archive: Any, name_map: list[str]) -> dict[str, Any]:
    """Parse minimal StaticMesh metadata from the current export payload."""
    start = archive.tell()
    if archive.total_size() - start >= 12:
        magic = archive.read(4)
        if magic == b"USMH":
            material_slot_count = archive.read_i32()
            lod_count = archive.read_i32()
            lods: list[dict[str, Any]] = []
            section_count = 0
            for _lod_index in range(max(0, lod_count)):
                sections: list[dict[str, int]] = []
                lod_section_count = archive.read_i32()
                for _section_index in range(max(0, lod_section_count)):
                    section = {
                        "material_index": archive.read_i32(),
                        "first_index": archive.read_i32(),
                        "num_triangles": archive.read_i32(),
                    }
                    sections.append(section)
                section_count += len(sections)
                lods.append({"section_count": len(sections), "sections": sections})
            return {
                "lod_count": len(lods),
                "section_count": section_count,
                "material_slot_count": material_slot_count,
                "lods": lods,
                "raw_offset": start,
                "raw_size": archive.tell() - start,
                "parse_status": "metadata",
            }
        archive.seek(start)
    remaining = max(0, archive.total_size() - start)
    sample = archive.read(min(remaining, 256))
    return {
        "lod_count": 0,
        "section_count": 0,
        "material_slot_count": 0,
        "raw_offset": start,
        "sample_size": len(sample),
        "parse_status": "metadata" if sample else "opaque",
    }
