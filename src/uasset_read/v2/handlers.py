"""Asset handlers — domain-specific enrichments for package objects.

The AssetHandler protocol defines how domain extractors add semantic
extensions to ObjectRecord instances. Handlers are registered by class
name and invoked lazily when depth >= asset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .object_model import ObjectRecord, CoverageEntry
from .version import VersionContext


@runtime_checkable
class AssetHandler(Protocol):
    """Domain handler that enriches an object with semantic data."""

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool: ...

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None: ...


@dataclass
class HandlerResult:
    """Result from an asset handler enrichment."""

    semantic: dict[str, Any]
    coverage: list[CoverageEntry] = field(default_factory=list)


# Global handler registry
_HANDLERS: list[AssetHandler] = []


def register_handler(handler: AssetHandler) -> None:
    """Register a global asset handler."""
    _HANDLERS.append(handler)


def get_handlers() -> list[AssetHandler]:
    """Get all registered handlers."""
    return list(_HANDLERS)


def run_handlers(
    obj: ObjectRecord,
    context: VersionContext,
    all_objects: list[ObjectRecord],
    package_data: Any,
) -> tuple[dict[str, Any] | None, list[CoverageEntry]]:
    """Run all matching handlers on an object. Returns (semantic, coverage)."""
    semantic: dict[str, Any] = {}
    coverage: list[CoverageEntry] = []

    for handler in _HANDLERS:
        try:
            if handler.supports(obj, context):
                result = handler.enrich(obj, context, all_objects, package_data)
                if result is not None:
                    semantic.update(result)
                    obj.status.semantic = "complete"
        except Exception as e:
            # Handler failure must not affect other objects
            coverage.append(
                CoverageEntry(
                    feature=f"handler.{type(handler).__name__}",
                    status="missing",
                    detail=f"Handler error: {e}",
                )
            )

    if not semantic:
        return None, coverage
    return semantic, coverage


# ── Built-in handlers ──────────────────────────────────────────────


class DataTableHandler:
    """Enrich DataTable/CurveTable/StringTable objects."""

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        cn = obj.class_name or ""
        return cn in ("DataTable", "CurveTable", "StringTable")

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        # Read from v1 parse result if available
        export_data = _get_export_data(obj, package_data)
        if not export_data:
            return None

        asset_type_data = getattr(export_data, "_asset_type_data", None)
        if not asset_type_data or not isinstance(asset_type_data, dict):
            return None

        row_count = asset_type_data.get("row_count", 0)
        rows = asset_type_data.get("rows", [])
        row_struct = asset_type_data.get("row_struct")

        result: dict[str, Any] = {"kind": "data_table"}
        result["row_count"] = row_count
        if row_struct:
            result["row_struct"] = row_struct
        if rows:
            result["row_names"] = [r.get("name", "") for r in rows[:100]]
        return result


class TextureHandler:
    """Enrich Texture2D/TextureCube objects from obj.properties.

    Extracts semantic fields: kind, texture_type, srgb, compression_settings.
    Each extracted field produces a CoverageEntry.
    """

    _TEXTURE_CLASSES = ("Texture2D", "TextureCube")

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        cn = obj.class_name or ""
        return cn in self._TEXTURE_CLASSES

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        props = obj.properties
        if not props:
            return None

        cn = obj.class_name or ""
        result: dict[str, Any] = {"kind": "texture", "texture_type": cn}
        coverage: list[CoverageEntry] = [
            CoverageEntry(feature="texture.kind", status="present"),
            CoverageEntry(feature="texture.texture_type", status="present", detail=cn),
        ]

        # SRGB (BoolProperty)
        srgb_prop = props.get("SRGB")
        if srgb_prop and srgb_prop.get("kind") == "value":
            result["srgb"] = srgb_prop["value"]
            coverage.append(
                CoverageEntry(feature="texture.srgb", status="present")
            )
        else:
            coverage.append(
                CoverageEntry(feature="texture.srgb", status="missing")
            )

        # CompressionSettings (ByteProperty / enum)
        cs_prop = props.get("CompressionSettings")
        if cs_prop and cs_prop.get("kind") == "value":
            raw = cs_prop["value"]
            if isinstance(raw, dict) and "value_name" in raw:
                result["compression_settings"] = raw["value_name"]
            else:
                result["compression_settings"] = raw
            coverage.append(
                CoverageEntry(feature="texture.compression_settings", status="present")
            )
        else:
            coverage.append(
                CoverageEntry(feature="texture.compression_settings", status="missing")
            )

        # Attach coverage to the object record
        obj.coverage.extend(coverage)
        return result


class TexturePayloadHandler:
    """Extract payload descriptors from texture properties.

    Reads ImportedSize struct to emit a texture_mip payload descriptor
    with stored_size / logical_size.
    """

    _TEXTURE_CLASSES = ("Texture2D", "TextureCube")

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        cn = obj.class_name or ""
        return cn in self._TEXTURE_CLASSES

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        props = obj.properties
        if not props:
            return None

        imported_size = props.get("ImportedSize")
        if not imported_size or imported_size.get("kind") != "struct":
            return None

        fields = imported_size.get("fields", {})
        # ImportedSize may have a nested struct with size fields,
        # or it may be a struct_binary_decoded with explicit size info.
        # Extract whatever size info is available.
        total_size = 0
        if fields:
            # Direct fields on the struct (e.g. SizeX, SizeY, or a single Size)
            size_val = fields.get("Size") or fields.get("total_size") or fields.get("BulkDataSize")
            if isinstance(size_val, (int, float)):
                total_size = int(size_val)

        # If the struct_type hints at size (e.g. "5_16"), try to extract
        struct_type = imported_size.get("struct_type", "")

        payload: dict[str, Any] = {
            "kind": "texture_mip",
            "source_region": "main",
            "logical_size": total_size,
        }
        if struct_type:
            payload["struct_type"] = struct_type

        coverage_entry = CoverageEntry(
            feature="texture.payload",
            status="present" if total_size else "partial",
            detail=f"ImportedSize struct_type={struct_type}" if struct_type else "",
        )
        obj.coverage.append(coverage_entry)

        return {"payload": payload}


class SoundHandler:
    """Enrich SoundWave/SoundCue/SoundAttenuation objects."""

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        cn = obj.class_name or ""
        return cn in ("SoundWave", "SoundCue", "SoundAttenuation")

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        export_data = _get_export_data(obj, package_data)
        if not export_data:
            return None

        asset_type_data = getattr(export_data, "_asset_type_data", None)
        if not asset_type_data or not isinstance(asset_type_data, dict):
            return None

        cn = obj.class_name or ""
        result: dict[str, Any] = {"kind": "sound", "sound_type": cn}

        if cn == "SoundWave":
            resource_keys = ("duration", "sample_rate", "channel_count", "format", "sound_group")
            resource = {k: asset_type_data[k] for k in resource_keys if k in asset_type_data}
            if resource:
                result["resource"] = resource
        elif cn == "SoundCue":
            result["node_count"] = asset_type_data.get("node_count", 0)
        elif cn == "SoundAttenuation":
            atten_keys = ("attenuation_shape", "attenuation_radius", "falloff_function")
            atten = {k: asset_type_data[k] for k in atten_keys if k in asset_type_data}
            if atten:
                result["attenuation"] = atten

        return result if len(result) > 2 else None


def _get_export_data(obj: ObjectRecord, package_data: Any) -> Any:
    """Get the v1 export object from the parse result by index."""
    if package_data is None:
        return None
    export_map = getattr(package_data, "export_map", None) or []
    idx = obj.table_index
    if 0 <= idx < len(export_map):
        return export_map[idx]
    return None


# Register built-in handlers
register_handler(DataTableHandler())
register_handler(TextureHandler())
register_handler(TexturePayloadHandler())
register_handler(SoundHandler())
