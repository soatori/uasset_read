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


class UserDefinedEnumHandler:
    """Enrich UserDefinedEnum objects."""

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") == "UserDefinedEnum"

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        # Enum entries live in the name map, not in properties.
        # We extract what we can from the object record.
        result: dict[str, Any] = {
            "kind": "user_defined_enum",
            "enum_name": obj.name,
        }
        return result


class UserDefinedStructHandler:
    """Enrich UserDefinedStruct objects."""

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") == "UserDefinedStruct"

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        result: dict[str, Any] = {
            "kind": "user_defined_struct",
            "struct_name": obj.name,
        }
        props = obj.properties or {}
        if props:
            result["field_count"] = len(props)
        return result


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
    """Enrich Texture2D/TextureCube objects."""

    _RESOURCE_KEYS = (
        "size_x",
        "size_y",
        "format",
        "num_mips",
        "is_streaming",
        "streaming_channels",
        "lod_group",
        "address_x",
        "address_y",
        "filter",
        "srgb",
    )
    _BULK_KEYS = ("total_mip_bytes", "compressed_mip_bytes", "chunk_count", "first_mip")

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        cn = obj.class_name or ""
        return cn in ("Texture2D", "TextureCube")

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

        result: dict[str, Any] = {"kind": "texture"}
        resource = {k: asset_type_data[k] for k in self._RESOURCE_KEYS if k in asset_type_data}
        if resource:
            result["resource"] = resource
        bulk = {k: asset_type_data[k] for k in self._BULK_KEYS if k in asset_type_data}
        if bulk:
            result["bulk"] = bulk
        return result if len(result) > 1 else None


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
register_handler(UserDefinedEnumHandler())
register_handler(UserDefinedStructHandler())
register_handler(DataTableHandler())
register_handler(TextureHandler())
register_handler(SoundHandler())
