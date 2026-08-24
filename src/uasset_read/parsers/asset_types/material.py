"""Material Asset type handler."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport


def parse_material(archive: "FArchive", name_map: list, export: "ObjectExport") -> dict:
    """Parse Material export — delegates to IR builder pipeline."""
    return {"asset_type": "Material", "material_type": "Material"}
