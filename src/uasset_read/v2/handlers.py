"""Asset handlers — domain-specific enrichments for package objects.

The AssetHandler protocol defines how domain extractors add semantic
extensions to ObjectRecord instances. Handlers are registered by class
name and invoked lazily when depth >= asset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .diagnostics import Diagnostic
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
) -> tuple[dict[str, Any] | None, list[CoverageEntry], list[Diagnostic]]:
    """Run all matching handlers on an object.

    Returns (semantic, coverage, diagnostics).
    Handler failure only affects this object — no propagation.
    """
    semantic: dict[str, Any] = {}
    coverage: list[CoverageEntry] = []
    diagnostics: list[Diagnostic] = []

    for handler in _HANDLERS:
        try:
            if handler.supports(obj, context):
                result = handler.enrich(obj, context, all_objects, package_data)
                if result is not None:
                    semantic.update(result)
                    obj.status.semantic = "complete"
        except Exception as e:
            # Handler failure must not affect other objects
            handler_name = type(handler).__name__
            obj.status.semantic = "partial"
            coverage.append(
                CoverageEntry(
                    feature=f"handler.{handler_name}",
                    status="missing",
                    detail=f"Handler error: {e}",
                )
            )
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="HANDLER_FAILURE",
                    message=f"{handler_name} failed for {obj.id}: {e}",
                    stage="semantic.handler",
                    object_id=obj.id,
                    recoverable=True,
                )
            )

    if not semantic:
        return None, coverage, diagnostics
    return semantic, coverage, diagnostics


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
        from uasset_read.parsers.asset_types.user_defined import (
            extract_user_defined_enum,
        )

        # package_data is (export_map, name_map) tuple from legacy reader
        export_map = package_data[0] if isinstance(package_data, tuple) else []
        name_map = package_data[1] if isinstance(package_data, tuple) else []

        # Find the matching export by index
        export = None
        if obj.table_index < len(export_map):
            export = export_map[obj.table_index]

        if export is None:
            return None

        enum_data = extract_user_defined_enum(export, name_map)

        if enum_data is None:
            return None

        result: dict[str, Any] = {
            "kind": "user_defined_enum",
            "enum_name": enum_data.get("enum_name", obj.name),
            "cpp_type": enum_data.get("cpp_type", ""),
            "entries": enum_data.get("entries", []),
        }

        # Determine coverage
        entries = result["entries"]
        if entries:
            coverage_status = "present"
        else:
            coverage_status = "missing"

        coverage: list[CoverageEntry] = [
            CoverageEntry(feature="handler.UserDefinedEnumHandler", status=coverage_status),
        ]
        obj.coverage.extend(coverage)
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
        from uasset_read.parsers.asset_types.user_defined import (
            extract_user_defined_struct,
        )

        # package_data is (export_map, name_map) tuple from legacy reader
        export_map = package_data[0] if isinstance(package_data, tuple) else []
        name_map = package_data[1] if isinstance(package_data, tuple) else []

        # Find the matching export by index
        export = None
        if obj.table_index < len(export_map):
            export = export_map[obj.table_index]

        if export is None:
            return None

        struct_data = extract_user_defined_struct(export, name_map)

        if struct_data is None:
            return None

        result: dict[str, Any] = {
            "kind": "user_defined_struct",
            "struct_name": struct_data.get("struct_name", obj.name),
            "struct_flags": struct_data.get("struct_flags", 0),
            "guid": struct_data.get("guid", ""),
            "fields": struct_data.get("fields", []),
        }

        # Determine coverage
        fields = result["fields"]
        guid = result["guid"]
        if fields and guid:
            coverage_status = "present"
        elif fields:
            coverage_status = "partial"
        else:
            coverage_status = "missing"

        coverage: list[CoverageEntry] = [
            CoverageEntry(feature="handler.UserDefinedStructHandler", status=coverage_status),
        ]
        obj.coverage.extend(coverage)
        return result


class DataTableHandler:
    """Enrich DataTable/CurveTable/StringTable objects.

    Falls back to v2 properties when v1 asset_type_data is unavailable.
    """

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
        cn = obj.class_name or ""
        result: dict[str, Any] = {"kind": "data_table", "table_type": cn}
        coverage: list[CoverageEntry] = [
            CoverageEntry(feature="handler.DataTableHandler", status="present"),
        ]

        # Try v1 asset_type_data first
        export_data = _get_export_data(obj, package_data)
        if export_data:
            asset_type_data = getattr(export_data, "_asset_type_data", None)
            if asset_type_data and isinstance(asset_type_data, dict):
                result["row_count"] = asset_type_data.get("row_count", 0)
                row_struct = asset_type_data.get("row_struct")
                if row_struct:
                    result["row_struct"] = row_struct
                rows = asset_type_data.get("rows", [])
                if rows:
                    result["row_names"] = [r.get("name", "") for r in rows[:100]]
                obj.coverage.extend(coverage)
                return result

        # Fallback: extract what we can from v2 properties
        props = obj.properties or {}
        row_struct = props.get("RowStruct")
        if row_struct and isinstance(row_struct, dict):
            # RowStruct is an ObjectProperty referencing the row struct
            result["row_struct_ref"] = row_struct.get("value")

        obj.coverage.extend(coverage)
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
            coverage.append(CoverageEntry(feature="texture.srgb", status="present"))
        else:
            coverage.append(CoverageEntry(feature="texture.srgb", status="missing"))

        # CompressionSettings (ByteProperty / enum)
        cs_prop = props.get("CompressionSettings")
        if cs_prop and cs_prop.get("kind") == "value":
            raw = cs_prop["value"]
            if isinstance(raw, dict) and "value_name" in raw:
                result["compression_settings"] = raw["value_name"]
            else:
                result["compression_settings"] = raw
            coverage.append(CoverageEntry(feature="texture.compression_settings", status="present"))
        else:
            coverage.append(CoverageEntry(feature="texture.compression_settings", status="missing"))

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
                total_size = int(size_val)  # safe: isinstance guard above

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
        cn = obj.class_name or ""
        result: dict[str, Any] = {"kind": "sound", "sound_type": cn}
        coverage: list[CoverageEntry] = []

        # Try v1 asset_type_data first
        export_data = _get_export_data(obj, package_data)
        if export_data:
            asset_type_data = getattr(export_data, "_asset_type_data", None)
            if asset_type_data and isinstance(asset_type_data, dict):
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
                coverage.append(CoverageEntry(feature="handler.SoundHandler", status="present"))
                obj.coverage.extend(coverage)
                return result if len(result) > 2 else None

        # Fallback: extract what we can from v2 properties
        props = obj.properties or {}
        if props:
            num_channels = props.get("NumChannels")
            if num_channels and isinstance(num_channels, dict):
                val = num_channels.get("value")
                if isinstance(val, dict):
                    inner = val.get("value")
                    if isinstance(inner, int):
                        result["channel_count"] = inner
                    elif isinstance(inner, dict) and inner.get("kind") == "opaque":
                        # Parse error — still record partial coverage
                        result["channel_count"] = None
                elif isinstance(val, int):
                    result["channel_count"] = val

        coverage.append(
            CoverageEntry(
                feature="handler.SoundHandler",
                status="present" if len(result) > 2 else "partial",
            )
        )
        obj.coverage.extend(coverage)
        return result if len(result) > 2 else None


def _get_export_data(obj: ObjectRecord, package_data: Any) -> Any:
    """Get the v1 export object from the parse result by index."""
    if package_data is None:
        return None
    # package_data may be: a list (export_map), a tuple (export_map, name_map),
    # or an object with export_map attribute
    if isinstance(package_data, tuple) and len(package_data) == 2:
        export_map = package_data[0]
    elif isinstance(package_data, list):
        export_map = package_data
    else:
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
register_handler(TexturePayloadHandler())
register_handler(SoundHandler())


class MaterialHandler:
    """Enrich Material objects with shader/material property summary."""

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") == "Material"

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        result: dict[str, Any] = {"kind": "material", "name": obj.name}
        coverage: list[CoverageEntry] = []
        props = obj.properties or {}

        # Shading domain flags
        for key in ("bUsedWithStaticLighting", "bUsedWithNanite", "bCanMaskedBeAssumedOpaque"):
            val = props.get(key)
            if val and isinstance(val, dict):
                result[key] = val.get("value", False)
                coverage.append(CoverageEntry(feature=f"material.{key}", status="present"))

        # Editor position
        for key in ("EditorX", "EditorY"):
            val = props.get(key)
            if val and isinstance(val, dict):
                result[key] = val.get("value", 0)
                coverage.append(CoverageEntry(feature=f"material.{key}", status="present"))

        obj.coverage.extend(coverage)
        return result if len(result) > 1 else None


class MaterialInstanceHandler:
    """Enrich MaterialInstance/MaterialInstanceConstant objects."""

    _INSTANCE_CLASSES = ("MaterialInstance", "MaterialInstanceConstant")

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") in self._INSTANCE_CLASSES

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        result: dict[str, Any] = {"kind": "material_instance", "name": obj.name}
        coverage: list[CoverageEntry] = []
        props = obj.properties or {}

        # Parent material reference
        parent = props.get("Parent")
        if parent is not None:
            result["has_parent"] = True
            coverage.append(CoverageEntry(feature="material_instance.parent", status="present"))

        # Scalar parameters
        scalar_params = props.get("ScalarParameterValues")
        if scalar_params and isinstance(scalar_params, dict):
            fields = scalar_params.get("fields", {})
            result["scalar_param_count"] = len(fields) if isinstance(fields, dict) else 0
            coverage.append(CoverageEntry(feature="material_instance.scalars", status="present"))

        # Vector parameters
        vector_params = props.get("VectorParameterValues")
        if vector_params and isinstance(vector_params, dict):
            fields = vector_params.get("fields", {})
            result["vector_param_count"] = len(fields) if isinstance(fields, dict) else 0
            coverage.append(CoverageEntry(feature="material_instance.vectors", status="present"))

        obj.coverage.extend(coverage)
        return result if len(result) > 1 else None


class SkeletonHandler:
    """Enrich Skeleton objects with bone hierarchy summary."""

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") == "Skeleton"

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        import re

        result: dict[str, Any] = {"kind": "skeleton", "name": obj.name}
        coverage: list[CoverageEntry] = []

        # Extract name_map from package_data tuple (export_map, name_map)
        name_map: list[str] = []
        if isinstance(package_data, tuple) and len(package_data) == 2:
            name_map = package_data[1]

        # Extract bone names from name map
        if name_map:
            bone_pattern = re.compile(
                r"^(root|pelvis|spine_\d+|head|neck|clavicle_[lr]|upperarm_[lr]|"
                r"lowerarm_[lr]|hand_[lr]|thigh_[lr]|calf_[lr]|foot_[lr]|ball_[lr]|"
                r"ik_\w+|twist_\d+_[lr]|finger\w*)$"
            )
            bones = []
            for i, name in enumerate(name_map):
                if bone_pattern.match(name):
                    bones.append({"name": name, "index": i})
            if bones:
                result["bones"] = bones
                result["bone_count"] = len(bones)
                coverage.append(CoverageEntry(feature="skeleton.bones", status="present"))

        # Count virtual bones from v1 data
        export_data = _get_export_data(obj, package_data)
        if export_data:
            props = getattr(export_data, "properties", None) or []
            for p in props:
                if getattr(p, "name", "") == "VirtualBones":
                    value = getattr(p, "value", None)
                    if isinstance(value, list):
                        result["virtual_bone_count"] = len(value)
                        coverage.append(CoverageEntry(feature="skeleton.virtual_bones", status="present"))
                    break

            # Count sockets
            for p in props:
                if getattr(p, "name", "") == "Sockets":
                    value = getattr(p, "value", None)
                    if isinstance(value, list):
                        result["socket_count"] = len(value)
                        coverage.append(CoverageEntry(feature="skeleton.sockets", status="present"))
                    break

        # Fallback: check v2 properties
        if "bone_count" not in result:
            props = obj.properties or {}
            bone_tree = props.get("BoneTree")
            if bone_tree and isinstance(bone_tree, dict):
                fields = bone_tree.get("fields", {})
                bone_count = len(fields) if isinstance(fields, dict) else 0
                result["bone_count"] = bone_count
                result["bones"] = []
                coverage.append(CoverageEntry(feature="skeleton.bone_tree", status="partial"))
            else:
                result["bone_count"] = 0
                result["bones"] = []
                coverage.append(
                    CoverageEntry(
                        feature="skeleton.bone_tree",
                        status="missing",
                        detail="BoneTree property not available",
                    )
                )

        obj.coverage.extend(coverage)
        return result


class MeshHandler:
    """Enrich StaticMesh/SkeletalMesh objects with geometry summary."""

    _MESH_CLASSES = ("StaticMesh", "SkeletalMesh")

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") in self._MESH_CLASSES

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        cn = obj.class_name or ""
        result: dict[str, Any] = {"kind": "mesh", "mesh_type": cn, "name": obj.name}
        coverage: list[CoverageEntry] = []

        # Try v1 export data first for actual LOD/source model info
        export_data = _get_export_data(obj, package_data)
        if export_data:
            props = getattr(export_data, "properties", None) or []
            for p in props:
                pname = getattr(p, "name", "")
                if pname == "SourceModels":
                    value = getattr(p, "value", None)
                    if isinstance(value, list):
                        lods = []
                        for i, item in enumerate(value):
                            lod: dict[str, Any] = {"index": i}
                            if hasattr(item, "fields") and isinstance(item.fields, dict):
                                build = item.fields.get("BuildSettings")
                                if build and hasattr(build, "fields"):
                                    lod["build_settings"] = {
                                        k: v
                                        for k, v in build.fields.items()
                                        if not isinstance(v, object) or isinstance(v, (bool, int, float, str))
                                    }
                                reduction = item.fields.get("ReductionSettings")
                                if reduction and hasattr(reduction, "fields"):
                                    lod["reduction_settings"] = {
                                        k: v
                                        for k, v in reduction.fields.items()
                                        if isinstance(v, (bool, int, float, str))
                                    }
                            lods.append(lod)
                        result["lods"] = lods
                        result["lod_count"] = len(lods)
                        coverage.append(CoverageEntry(feature="mesh.source_models", status="present"))
                        break

        # Fallback: check v2 properties
        if "lod_count" not in result:
            props = obj.properties or {}
            source_models = props.get("SourceModels")
            if source_models and isinstance(source_models, dict):
                fields = source_models.get("fields", {})
                result["lod_count"] = len(fields) if isinstance(fields, dict) else 0
                result["lods"] = []
                coverage.append(CoverageEntry(feature="mesh.source_models", status="partial"))
            else:
                result["lod_count"] = 0
                result["lods"] = []
                coverage.append(
                    CoverageEntry(
                        feature="mesh.source_models",
                        status="missing",
                        detail="SourceModels not available",
                    )
                )

        # Geometry flags from v2 properties
        props = obj.properties or {}
        for key in ("bRecalculateNormals", "bGenerateUniqueLightmapUVs", "bKeepSymmetry"):
            val = props.get(key)
            if val and isinstance(val, dict):
                result[key] = val.get("value", False)
                coverage.append(CoverageEntry(feature=f"mesh.{key}", status="present"))

        obj.coverage.extend(coverage)
        return result


register_handler(MaterialHandler())
register_handler(MaterialInstanceHandler())
register_handler(SkeletonHandler())
register_handler(MeshHandler())


class AnimBlueprintHandler:
    """Enrich AnimBlueprint/AnimBlueprintGeneratedClass objects.

    At depth="asset": light summary only (kind, name, class).
    At depth="decode": full graph data (nodes, edges, bytecode) for explicitly selected objects.
    """

    _ANIMBP_CLASSES = ("AnimBlueprint", "AnimBlueprintGeneratedClass")

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        cn = obj.class_name or ""
        return cn in self._ANIMBP_CLASSES

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        cn = obj.class_name or ""
        result: dict[str, Any] = {
            "kind": "anim_blueprint",
            "blueprint_type": cn,
            "name": obj.name,
        }
        coverage: list[CoverageEntry] = []

        # At depth="asset": light summary only, no heavy graph arrays
        if context.depth == "asset":
            coverage.append(
                CoverageEntry(
                    feature="anim_blueprint.summary",
                    status="present",
                    detail="light summary at depth=asset",
                )
            )
            obj.coverage.extend(coverage)
            return result

        # At depth="decode": full graph data
        if context.depth == "decode":
            # Find related graph objects (EdGraph, K2Node_*)
            graph_nodes: list[dict[str, Any]] = []
            graph_edges: list[dict[str, Any]] = []

            for other in all_objects:
                other_class = other.class_name or ""
                if other_class == "EdGraph":
                    # EdGraph is a container for graph nodes
                    graph_nodes.append(
                        {
                            "id": other.id,
                            "type": "EdGraph",
                            "name": other.name,
                        }
                    )
                elif other_class.startswith("K2Node_"):
                    # K2Node_* are graph nodes
                    node: dict[str, Any] = {
                        "id": other.id,
                        "type": other_class,
                        "name": other.name,
                    }
                    # Extract parent reference if available
                    if other.properties and "ParentNode" in other.properties:
                        parent_prop = other.properties["ParentNode"]
                        if isinstance(parent_prop, dict) and "value" in parent_prop:
                            node["parent_node"] = parent_prop["value"]
                    graph_nodes.append(node)

            # Build edges from parent references
            node_ids = {n["id"] for n in graph_nodes}
            for node_info in graph_nodes:
                if "parent_node" in node_info:
                    parent_id = node_info["parent_node"]
                    if parent_id in node_ids:
                        graph_edges.append(
                            {
                                "from_node": parent_id,
                                "to_node": node_info["id"],
                                "kind": "parent",
                            }
                        )

            if graph_nodes:
                result["graph"] = {
                    "nodes": graph_nodes,
                    "edges": graph_edges,
                    "node_count": len(graph_nodes),
                    "edge_count": len(graph_edges),
                }
                coverage.append(
                    CoverageEntry(
                        feature="anim_blueprint.graph",
                        status="present",
                        detail=f"{len(graph_nodes)} nodes, {len(graph_edges)} edges",
                    )
                )
            else:
                coverage.append(
                    CoverageEntry(
                        feature="anim_blueprint.graph",
                        status="missing",
                        detail="no graph objects found",
                    )
                )

            obj.coverage.extend(coverage)
            return result

        # For other depths, return light summary
        obj.coverage.extend(coverage)
        return result


class BlueprintHandler:
    """Enrich Blueprint/BlueprintGeneratedClass objects.

    At depth="asset": light summary only (kind, name, class).
    At depth="decode": full graph data (nodes, edges, bytecode) for explicitly selected objects.
    """

    _BP_CLASSES = ("Blueprint", "BlueprintGeneratedClass")

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        cn = obj.class_name or ""
        return cn in self._BP_CLASSES

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        cn = obj.class_name or ""
        result: dict[str, Any] = {
            "kind": "blueprint",
            "blueprint_type": cn,
            "name": obj.name,
        }
        coverage: list[CoverageEntry] = []

        # At depth="asset": light summary only, no heavy graph arrays
        if context.depth == "asset":
            coverage.append(
                CoverageEntry(
                    feature="blueprint.summary",
                    status="present",
                    detail="light summary at depth=asset",
                )
            )
            obj.coverage.extend(coverage)
            return result

        # At depth="decode": full graph data
        if context.depth == "decode":
            # Find related graph objects (EdGraph, K2Node_*)
            graph_nodes: list[dict[str, Any]] = []
            graph_edges: list[dict[str, Any]] = []

            for other in all_objects:
                other_class = other.class_name or ""
                if other_class == "EdGraph":
                    graph_nodes.append(
                        {
                            "id": other.id,
                            "type": "EdGraph",
                            "name": other.name,
                        }
                    )
                elif other_class.startswith("K2Node_"):
                    node: dict[str, Any] = {
                        "id": other.id,
                        "type": other_class,
                        "name": other.name,
                    }
                    if other.properties and "ParentNode" in other.properties:
                        parent_prop = other.properties["ParentNode"]
                        if isinstance(parent_prop, dict) and "value" in parent_prop:
                            node["parent_node"] = parent_prop["value"]
                    graph_nodes.append(node)

            # Build edges from parent references
            node_ids = {n["id"] for n in graph_nodes}
            for node_info in graph_nodes:
                if "parent_node" in node_info:
                    parent_id = node_info["parent_node"]
                    if parent_id in node_ids:
                        graph_edges.append(
                            {
                                "from_node": parent_id,
                                "to_node": node_info["id"],
                                "kind": "parent",
                            }
                        )

            if graph_nodes:
                result["graph"] = {
                    "nodes": graph_nodes,
                    "edges": graph_edges,
                    "node_count": len(graph_nodes),
                    "edge_count": len(graph_edges),
                }
                coverage.append(
                    CoverageEntry(
                        feature="blueprint.graph",
                        status="present",
                        detail=f"{len(graph_nodes)} nodes, {len(graph_edges)} edges",
                    )
                )
            else:
                coverage.append(
                    CoverageEntry(
                        feature="blueprint.graph",
                        status="missing",
                        detail="no graph objects found",
                    )
                )

            obj.coverage.extend(coverage)
            return result

        # For other depths, return light summary
        obj.coverage.extend(coverage)
        return result


register_handler(AnimBlueprintHandler())
register_handler(BlueprintHandler())
