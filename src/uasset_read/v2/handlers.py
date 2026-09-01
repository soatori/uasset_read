"""Asset handlers — domain-specific enrichments for package objects.

The AssetHandler protocol defines how domain extractors add semantic
extensions to ObjectRecord instances. Handlers are registered by class
name and invoked lazily when depth >= asset.
"""

from __future__ import annotations

from typing import Any, Protocol

from .diagnostics import Diagnostic
from .object_model import ObjectRecord, CoverageEntry
from .version import VersionContext


class AssetHandler(Protocol):
    """Domain handler that enriches an object with semantic data.

    Handlers may declare a capability tier via a ``capability`` member:
    either a plain ``"summary"``/``"decoded"`` string, or a callable of the
    produced result for handlers whose tier depends on the data actually
    found. Undeclared handlers are summary-tier: only decoded-tier output
    may yield ``status.semantic = "complete"`` (#629).
    """

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool: ...

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None: ...


# Global handler registry
_HANDLERS: list[AssetHandler] = []


def register_handler(handler: AssetHandler) -> None:
    """Register a global asset handler."""
    _HANDLERS.append(handler)


def get_handlers() -> list[AssetHandler]:
    """Get all registered handlers."""
    return list(_HANDLERS)


def _capability_tier(handler: AssetHandler, result: dict[str, Any]) -> str:
    """Resolve a handler's declared tier ("decoded"/"summary") for its output.

    ``capability`` may be a plain tier string or a callable of the produced
    result. Undeclared handlers default to "summary": an undeclared handler
    must not claim that a type was fully decoded (#629).
    """
    cap = getattr(handler, "capability", "summary")
    return cap(result) if callable(cap) else cap


def run_handlers(
    obj: ObjectRecord,
    context: VersionContext,
    all_objects: list[ObjectRecord],
    package_data: Any,
) -> tuple[dict[str, Any] | None, list[CoverageEntry], list[Diagnostic]]:
    """Run all matching handlers on an object.

    Returns (semantic, coverage, diagnostics).
    Handler failure only affects this object — no propagation.
    ``status.semantic`` is bound to the capability tier: "complete" only
    when a decoded-tier handler produced output; summary-tier results and
    failures stay "partial" (#629).
    """
    semantic: dict[str, Any] = {}
    coverage: list[CoverageEntry] = []
    diagnostics: list[Diagnostic] = []
    matched = False
    failed = False
    decoded = False

    for handler in _HANDLERS:
        try:
            if handler.supports(obj, context):
                matched = True
                result = handler.enrich(obj, context, all_objects, package_data)
                if result is not None:
                    semantic.update(result)
                    if _capability_tier(handler, result) == "decoded":
                        decoded = True
        except Exception as e:
            # Handler failure must not affect other objects
            matched = True
            failed = True
            handler_name = type(handler).__name__
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

    if matched:
        # "complete" means a decoded-tier handler delivered semantics.
        # A summary-tier result (name/kind echo, light digest), a handler
        # that matched but produced nothing, or a failure stays "partial".
        obj.status.semantic = "complete" if (decoded and not failed) else "partial"

    if not semantic:
        return None, coverage, diagnostics
    return semantic, coverage, diagnostics


# ── Built-in handlers ──────────────────────────────────────────────


def _flatten_text(val: Any) -> str | None:
    """Pull a readable string out of a normalized property value.

    Plain strings pass through; FText/FString structs are unwrapped by
    looking for a source-string field at any nesting level.
    """
    if isinstance(val, str):
        return val
    if not isinstance(val, dict):
        return None
    fields = val.get("fields")
    if isinstance(fields, dict):
        for key in ("source_string", "SourceString"):
            if isinstance(fields.get(key), str):
                return fields[key]
    return _flatten_text(val.get("value"))


class UserDefinedEnumHandler:
    """Enrich UserDefinedEnum objects."""

    capability = "decoded"  # real enum entries decoded from the name table

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") == "UserDefinedEnum"

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        name_map = package_data[1] if isinstance(package_data, tuple) and len(package_data) >= 2 else []

        # Enum value names live in the name table as "EnumName::ValueName".
        prefix = f"{obj.name}::"
        entries: list[dict[str, Any]] = []
        display_names: dict[str, str] = {}

        # DisplayNameMap: TMap<FName, FText> — normalized bag value is a list
        # of {"key": ..., "value": ...} entries; the FText value is a struct
        # whose fields carry "source_string" (or a plain string).
        dm = (obj.properties or {}).get("DisplayNameMap")
        if isinstance(dm, dict) and isinstance(dm.get("value"), list):
            for entry in dm["value"]:
                if isinstance(entry, dict):
                    key = entry.get("key")
                    val = _flatten_text(entry.get("value"))
                    if key is not None and val is not None:
                        display_names[str(key)] = val

        for name in name_map:
            if not name.startswith(prefix):
                continue
            short = name[len(prefix) :]
            if short == "Enum_MAX" or short.endswith("::Enum_MAX"):
                continue
            if any(e["name"] == short for e in entries):
                continue
            entries.append({"name": short, "display_name": display_names.get(short, short)})

        cpp_type = ""
        ct = (obj.properties or {}).get("CppType")
        if isinstance(ct, dict):
            cpp_type = str(ct.get("value") or "")

        result: dict[str, Any] = {
            "kind": "user_defined_enum",
            "enum_name": obj.name,
            "cpp_type": cpp_type,
            "entries": entries,
        }

        coverage: list[CoverageEntry] = [
            CoverageEntry(
                feature="handler.UserDefinedEnumHandler",
                status="present" if entries else "missing",
            ),
        ]
        obj.coverage.extend(coverage)
        return result if entries else None


class UserDefinedStructHandler:
    """Enrich UserDefinedStruct objects."""

    capability = "decoded"  # only returns output when real fields were extracted

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") == "UserDefinedStruct"

    _INTERNAL_PROPS = (
        "None",
        "ClassDefaultObject",
        "ClassCDO",
        "ClassGeneratedBy",
        "DeprecatedData",
        "EditorOnlyData",
        "Native",
        "StructFlags",
        "Guid",
    )

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        props = obj.properties or {}
        fields: list[dict[str, Any]] = []
        for name, val in props.items():
            if name in self._INTERNAL_PROPS or not isinstance(val, dict):
                continue
            field: dict[str, Any] = {"name": name, "type": val.get("type", "")}
            inner = val.get("value")
            if val.get("type") == "StructProperty" and isinstance(inner, dict):
                field["struct_type"] = inner.get("struct_type", "")
            elif isinstance(inner, (bool, int, float, str)):
                field["default_value"] = str(inner)
            fields.append(field)

        struct_flags = 0
        sf = props.get("StructFlags")
        if isinstance(sf, dict) and isinstance(sf.get("value"), int):
            struct_flags = sf["value"]

        guid = ""
        gv = props.get("Guid")
        if isinstance(gv, dict) and isinstance(gv.get("value"), dict):
            gv = gv["value"]  # unwrap {"kind":"value", "value": {...struct...}}
        if isinstance(gv, dict) and isinstance(gv.get("fields"), dict):
            f = gv["fields"]
            if all(k in f for k in ("A", "B", "C", "D")):
                a, b, c, d = (f.get("A", 0), f.get("B", 0), f.get("C", 0), f.get("D", 0))
                guid = f"{a:08X}-{b:04X}-{c:04X}-{(d >> 16) & 0xFFFF:04X}-{d & 0xFFFF:04X}00000000"

        result: dict[str, Any] = {
            "kind": "user_defined_struct",
            "struct_name": obj.name,
            "struct_flags": struct_flags,
            "guid": guid,
            "fields": fields,
        }

        coverage_status = "present" if (fields and guid) else ("partial" if fields else "missing")
        obj.coverage.append(
            CoverageEntry(feature="handler.UserDefinedStructHandler", status=coverage_status),
        )
        return result if fields else None


class DataTableHandler:
    """Enrich DataTable/CurveTable/StringTable objects.

    Row data comes from the bounded table payload slice the legacy reader
    extracts right after the tagged properties.
    """

    capability = "decoded"  # row struct/count read from real property + payload data

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
        props = obj.properties or {}

        row_struct_name = props.get("RowStructName")
        if isinstance(row_struct_name, dict) and isinstance(row_struct_name.get("value"), str):
            result["row_struct"] = row_struct_name["value"]
        else:
            row_struct = props.get("RowStruct")
            if isinstance(row_struct, dict):
                # RowStruct is an ObjectProperty referencing the row struct
                result["row_struct_ref"] = row_struct.get("value")

        # Row count comes from the table payload the legacy reader sliced out
        # right after the tagged properties (package_data[2] extras dict).
        extras = package_data[2] if isinstance(package_data, tuple) and len(package_data) >= 3 else None
        rows = (extras or {}).get(obj.id, {}).get("table_rows")
        if rows is not None:
            result["row_count"] = rows["row_count"]
            if rows.get("row_names"):
                result["row_names"] = rows["row_names"][:100]
            status = "present" if rows["complete"] else "partial"
        else:
            result["row_count"] = 0
            status = "missing"

        obj.coverage.append(CoverageEntry(feature="handler.DataTableHandler", status=status))
        return result


class TextureHandler:
    """Enrich Texture2D/TextureCube objects from obj.properties.

    Extracts semantic fields: kind, texture_type, srgb, compression_settings.
    Each extracted field produces a CoverageEntry.
    """

    capability = "decoded"  # fields read from the tagged property bag

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

    capability = "decoded"  # descriptor read from the real ImportedSize struct

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
        cn = obj.class_name or ""
        result: dict[str, Any] = {"kind": "sound", "sound_type": cn}

        # SoundWave resource fields from the v2 property bag.
        props = obj.properties or {}
        resource: dict[str, Any] = {}
        for prop_name, key in (
            ("Duration", "duration"),
            ("SampleRate", "sample_rate"),
            ("NumChannels", "channel_count"),
        ):
            val = props.get(prop_name)
            if isinstance(val, dict) and isinstance(val.get("value"), (int, float)):
                resource[key] = val["value"]
        if resource:
            result["resource"] = resource

        # Exactly one coverage entry: "present" only when real resource data
        # was found; the kind projection alone is "partial".
        obj.coverage.append(
            CoverageEntry(
                feature="handler.SoundHandler",
                status="present" if resource else "partial",
            )
        )
        return result

    def capability(self, result: dict[str, Any]) -> str:
        # Decoded only with real resource fields; a kind/sound_type echo is a summary.
        return "decoded" if "resource" in result else "summary"


# Register built-in handlers
register_handler(UserDefinedEnumHandler())
register_handler(UserDefinedStructHandler())
register_handler(DataTableHandler())
register_handler(TextureHandler())
register_handler(TexturePayloadHandler())
register_handler(SoundHandler())


class MaterialHandler:
    """Enrich Material objects with shader/material property summary."""

    capability = "decoded"  # returns output only when real properties were read

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

    capability = "decoded"  # returns output only when real properties were read

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

    capability = "decoded"  # bone counts read from the property bag

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

        # Extract name_map from package_data tuple (export_map, name_map, extras)
        name_map: list[str] = []
        if isinstance(package_data, tuple) and len(package_data) >= 2:
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

        # Count virtual bones and sockets from the v2 property bag
        bag = obj.properties or {}
        for prop_name, key, feature in (
            ("VirtualBones", "virtual_bone_count", "skeleton.virtual_bones"),
            ("Sockets", "socket_count", "skeleton.sockets"),
        ):
            val = bag.get(prop_name)
            if isinstance(val, dict) and isinstance(val.get("value"), list):
                result[key] = len(val["value"])
                coverage.append(CoverageEntry(feature=feature, status="present"))

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
    """Enrich StaticMesh/SkeletalMesh objects with geometry summary.

    Summary-tier: mesh geometry is not decoded, so this never yields
    ``semantic="complete"`` (#629).
    """

    capability = "summary"

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

        # LOD/source-model summary from the v2 property bag. SourceModels is
        # an array of structs; each element carries BuildSettings/
        # ReductionSettings sub-structs as nested "fields" dicts.
        props = obj.properties or {}
        source_models = props.get("SourceModels")
        models = source_models.get("value") if isinstance(source_models, dict) else None
        if isinstance(models, list) and models:
            lods: list[dict[str, Any]] = []
            for i, item in enumerate(models):
                lod: dict[str, Any] = {"index": i}
                fields = item.get("fields") if isinstance(item, dict) else None
                if isinstance(fields, dict):
                    for sub_key, out_key in (("BuildSettings", "build_settings"), ("ReductionSettings", "reduction_settings")):
                        sub = fields.get(sub_key)
                        if isinstance(sub, dict) and isinstance(sub.get("fields"), dict):
                            lod[out_key] = {
                                k: v
                                for k, v in sub["fields"].items()
                                if isinstance(v, (bool, int, float, str))
                            }
                lods.append(lod)
            result["lods"] = lods
            result["lod_count"] = len(lods)
            coverage.append(CoverageEntry(feature="mesh.source_models", status="present"))
        else:
            result["lod_count"] = 0
            result["lods"] = []
            coverage.append(
                CoverageEntry(
                    feature="mesh.source_models",
                    status="partial" if models == [] else "missing",
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


class BlueprintFamilyHandler:
    """Enrich Blueprint-family objects (Blueprint or AnimBlueprint variants).

    At depth="asset": light summary only (kind, name, class).
    At depth="decode": full graph data (nodes, edges) for explicitly selected objects.
    """

    def __init__(self, classes: tuple[str, ...], kind: str, feature: str):
        self._classes = classes
        self._kind = kind
        self._feature = feature

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        cn = obj.class_name or ""
        return cn in self._classes

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        cn = obj.class_name or ""
        result: dict[str, Any] = {
            "kind": self._kind,
            "blueprint_type": cn,
            "name": obj.name,
        }
        coverage: list[CoverageEntry] = []

        # At depth="asset": light summary only, no heavy graph arrays
        if context.depth == "asset":
            coverage.append(
                CoverageEntry(
                    feature=f"{self._feature}.summary",
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
                        feature=f"{self._feature}.graph",
                        status="present",
                        detail=f"{len(graph_nodes)} nodes, {len(graph_edges)} edges",
                    )
                )
            else:
                coverage.append(
                    CoverageEntry(
                        feature=f"{self._feature}.graph",
                        status="missing",
                        detail="no graph objects found",
                    )
                )

            obj.coverage.extend(coverage)
            return result

    def capability(self, result: dict[str, Any]) -> str:
        # Light summary at depth=asset; only decoded graph data counts (#629).
        return "decoded" if "graph" in result else "summary"


register_handler(
    BlueprintFamilyHandler(
        ("AnimBlueprint", "AnimBlueprintGeneratedClass"), "anim_blueprint", "anim_blueprint"
    )
)
register_handler(
    BlueprintFamilyHandler(("Blueprint", "BlueprintGeneratedClass"), "blueprint", "blueprint")
)


class NiagaraHandler:
    """Enrich Niagara objects with light summary.

    Summary-tier: the name/type echo is not a decoded Niagara script, so
    this never yields ``semantic="complete"`` (#629).
    """

    capability = "summary"

    _NIAGARA_CLASSES = (
        "NiagaraScript",
        "NiagaraScriptSource",
        "NiagaraScriptVariable",
        "NiagaraGraph",
        "NiagaraNodeFunctionCall",
        "NiagaraNodeInput",
        "NiagaraNodeOutput",
        "NiagaraNodeOp",
        "NiagaraNodeParameterMapGet",
        "NiagaraNodeParameterMapSet",
        "NiagaraNodeReroute",
        "NiagaraNodeSelect",
        "NiagaraNodeStaticSwitch",
    )

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        cn = obj.class_name or ""
        return cn in self._NIAGARA_CLASSES

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        cn = obj.class_name or ""
        result: dict[str, Any] = {"kind": "niagara", "niagara_type": cn, "name": obj.name}
        coverage: list[CoverageEntry] = [
            CoverageEntry(feature="niagara.kind", status="present", detail=cn),
        ]
        obj.coverage.extend(coverage)
        return result


register_handler(NiagaraHandler())
