"""Asset handlers — domain-specific enrichments for package objects.

The AssetHandler protocol defines how domain extractors add semantic
extensions to ObjectRecord instances. Handlers are registered by class
name and invoked lazily when depth >= asset.
"""

from __future__ import annotations

import re
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


def _prop_value(props: dict[str, Any], name: str) -> Any:
    """Unwrap a tagged ``{"kind":"value", ...}`` bag entry."""
    val = props.get(name)
    if isinstance(val, dict) and val.get("kind") == "value":
        return val.get("value")
    return None


def _array_value(props: dict[str, Any], name: str) -> list[Any] | None:
    """Return a normalized array value, or None when absent/unreadable.

    Top-level tagged arrays arrive as ``{"kind":"value","value":[...]}``;
    arrays nested inside structs are serialized as plain lists.
    """
    val = props.get(name)
    if isinstance(val, dict) and val.get("kind") == "value":
        val = val.get("value")
    return val if isinstance(val, list) else None


def _number_value(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, (int, float)) else None


def _enum_name(value: Any) -> str | None:
    """ByteProperty/enum values surface as {"value_name": ...} or a plain string."""
    if isinstance(value, dict):
        name = value.get("value_name")
        return str(name) if name is not None else None
    return str(value) if isinstance(value, str) else None


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
    """Enrich DataTable/CurveTable objects.

    Row data comes from the bounded table payload slice the legacy reader
    extracts right after the tagged properties. StringTable assets use a
    different trailer layout and are handled by StringTableHandler (#615).
    """

    capability = "decoded"  # row struct/count read from real property + payload data

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        cn = obj.class_name or ""
        return cn in ("DataTable", "CurveTable")

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


class StringTableHandler:
    """Enrich StringTable objects from the bounded FStringTable trailer slice.

    Trailer layout per UE source: Runtime/Core/Private/Internationalization/
    StringTableCore.cpp ``FStringTable::Serialize`` (namespace + key/value
    entries), serialized by UStringTable::Serialize after the tagged
    properties; see the comment on ``_read_string_table`` in
    ``v2/package/legacy.py`` for the trigger conditions.

    Summary tier until a decoded fixture backfills #615: trailing per-key
    metadata is not parsed, so this never claims ``semantic="complete"``
    (#629).
    """

    capability = "summary"

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") == "StringTable"

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        extras = package_data[2] if isinstance(package_data, tuple) and len(package_data) >= 3 else None
        st = (extras or {}).get(obj.id, {}).get("string_table")
        result: dict[str, Any] = {"kind": "string_table", "table_type": "StringTable"}
        if not st:
            obj.coverage.append(
                CoverageEntry(
                    feature="handler.StringTableHandler",
                    status="missing",
                    detail="StringTable trailer unavailable (property parse overrun or payload not sliced)",
                )
            )
            return result

        entries = st.get("entries") or []
        result["namespace"] = st.get("namespace", "")
        result["entry_count"] = st.get("entry_count", 0)
        result["entries"] = entries[:100]
        if len(entries) > 100:
            result["entries_truncated"] = True
        detail = "" if st.get("complete") else f"parsed {len(entries)}/{st.get('entry_count', 0)} entries"
        obj.coverage.append(
            CoverageEntry(
                feature="handler.StringTableHandler",
                status="present" if st.get("complete") else "partial",
                detail=detail or "metadata map not parsed (summary tier)",
            )
        )
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
register_handler(StringTableHandler())
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


_BONE_NAME_RE = re.compile(
    r"^(root|pelvis|spine_\d+|head|neck|clavicle_[lr]|upperarm_[lr]|"
    r"lowerarm_[lr]|hand_[lr]|thigh_[lr]|calf_[lr]|foot_[lr]|ball_[lr]|"
    r"ik_\w+|twist_\d+_[lr]|finger\w*)$"
)


def _guess_bone_names(name_map: list[str]) -> list[dict[str, Any]]:
    """Heuristic NameMap-regex name guess — never a decoded skeleton hierarchy (#630)."""
    return [
        {"name": name, "index": i} for i, name in enumerate(name_map) if _BONE_NAME_RE.match(name)
    ]


def _decoded_bone_names(prop: Any) -> list[dict[str, Any]]:
    """Bone names decoded from a BoneTree/ReferenceSkeleton property value.

    FBoneNode ``Name`` fields surface either as BoneNode struct entries or —
    the property reader emits each FName twice — as consecutive duplicated
    string array entries; other array elements are misaligned noise and get
    skipped. Returns [] when the property carries no decodable names.
    """
    if not isinstance(prop, dict) or not isinstance(prop.get("value"), list):
        return []
    names: list[dict[str, Any]] = []
    for entry in prop["value"]:
        name = None
        if isinstance(entry, dict) and entry.get("struct_type") == "BoneNode":
            n = (entry.get("fields") or {}).get("Name")
            if isinstance(n, str):
                name = n
        elif isinstance(entry, str):
            name = entry
        if name and name != "None" and (not names or names[-1]["name"] != name):
            names.append({"name": name, "index": len(names)})
    return names


class SkeletonHandler:
    """Enrich Skeleton objects with bone hierarchy summary.

    Real bone names decoded from the BoneTree/ReferenceSkeleton properties
    win; the NameMap regex path is an explicit name guess marked
    ``bone_source="name_guess"`` and stays summary-tier (#630).
    """

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") == "Skeleton"

    def capability(self, result: dict[str, Any]) -> str:
        # A name guess or an empty fallback is a summary; only decoded property
        # bone data counts as complete (#629, #630).
        return "decoded" if result.get("bone_source") in ("bone_tree", "reference_skeleton") else "summary"

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        result: dict[str, Any] = {"kind": "skeleton", "name": obj.name}
        coverage: list[CoverageEntry] = []
        bag = obj.properties or {}

        # Real hierarchy first: BoneTree/ReferenceSkeleton property data wins.
        bones: list[dict[str, Any]] = []
        bone_source = ""
        for prop_name, source in (("BoneTree", "bone_tree"), ("ReferenceSkeleton", "reference_skeleton")):
            bones = _decoded_bone_names(bag.get(prop_name))
            if bones:
                bone_source = source
                break

        if not bones:
            # Fallback: heuristic name guess over the NameMap, explicitly marked.
            name_map: list[str] = []
            if isinstance(package_data, tuple) and len(package_data) >= 2:
                name_map = package_data[1]
            bones = _guess_bone_names(name_map)
            if bones:
                bone_source = "name_guess"
                coverage.append(
                    CoverageEntry(
                        feature="skeleton.bones",
                        status="partial",
                        detail="heuristic: NameMap regex name-guess, not a decoded hierarchy",
                    )
                )
            else:
                coverage.append(
                    CoverageEntry(
                        feature="skeleton.bones",
                        status="missing",
                        detail="BoneTree/ReferenceSkeleton not decoded and no NameMap name matched",
                    )
                )
        else:
            coverage.append(
                CoverageEntry(feature="skeleton.bones", status="present", detail=f"from {bone_source} property")
            )

        result["bones"] = bones
        result["bone_count"] = len(bones)
        if bone_source:
            result["bone_source"] = bone_source

        # Count virtual bones and sockets from the v2 property bag
        for prop_name, key, feature in (
            ("VirtualBones", "virtual_bone_count", "skeleton.virtual_bones"),
            ("Sockets", "socket_count", "skeleton.sockets"),
        ):
            val = bag.get(prop_name)
            if isinstance(val, dict) and isinstance(val.get("value"), list):
                result[key] = len(val["value"])
                coverage.append(CoverageEntry(feature=feature, status="present"))

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
    At depth="decode": real graphs arrive via extras (reader-side pass).
    Only the owning asset export carries them; GeneratedClass exports
    keep the summary and stay "partial" (#629 tier contract).
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

        if context.depth == "asset":
            obj.coverage.append(
                CoverageEntry(
                    feature=f"{self._feature}.summary",
                    status="present",
                    detail="light summary at depth=asset",
                )
            )
            return result

        # depth == "decode": real graphs arrive via extras (reader-side pass).
        # Only the owning asset export carries them; GeneratedClass exports
        # keep the summary and stay "partial" (#629 tier contract).
        if context.depth == "decode":
            extras = package_data[2] if package_data else {}
            entry = extras.get(obj.id, {}) if isinstance(extras, dict) else {}
            graphs = entry.get("graphs", []) if isinstance(entry, dict) else []
            if graphs:
                fg_ids = _function_graph_ids(obj.properties)
                self._finalize_graph_kinds(graphs, fg_ids)
                truncated = any(
                    g["truncated"]["nodes"] or g["truncated"]["pins"] for g in graphs
                )
                result["graphs"] = graphs
                result["truncated_graphs"] = truncated
                result["declaration"] = _extract_declaration(
                    obj, entry, graphs, fg_ids, package_data[0] if package_data else None
                )
                result["variables"] = _extract_variables(obj)
                detail = f"{len(graphs)} graphs, {sum(g['node_count'] for g in graphs)} nodes"
                if truncated:
                    detail += " (truncated)"
                obj.coverage.append(
                    CoverageEntry(
                        feature=f"{self._feature}.graph",
                        status="truncated" if truncated else "present",
                        detail=detail,
                    )
                )
            else:
                obj.coverage.append(
                    CoverageEntry(
                        feature=f"{self._feature}.graph",
                        status="missing",
                        detail="no graphs owned by this export",
                    )
                )
            return result

    @staticmethod
    def _finalize_graph_kinds(graphs: list[dict[str, Any]], fg_ids: set[str]) -> None:
        """Set per-graph kind from name / FunctionGraphs membership.

        Deterministic derivation: EventGraph/UserConstructionScript by name,
        graphs listed in FunctionGraphs -> "function", else "unknown".
        """
        for graph in graphs:
            if graph["name"] == "EventGraph":
                graph["kind"] = "event_graph"
            elif graph["name"] == "UserConstructionScript":
                graph["kind"] = "construction_script"
            elif graph["id"] in fg_ids:
                graph["kind"] = "function"
            else:
                graph["kind"] = "unknown"

    def capability(self, result: dict[str, Any]) -> str:
        # Truncated decode output must not claim "complete" (#629, bounded by
        # default); summary echoes stay summary tier.
        if result.get("graphs") and not result.get("truncated_graphs"):
            return "decoded"
        return "summary"


def _function_graph_ids(properties: dict[str, Any] | None) -> set[str]:
    """Export ids of the FunctionGraphs property (positive refs = export idx + 1)."""
    fg = properties.get("FunctionGraphs", {}).get("value") if properties else None
    ids: set[str] = set()
    if isinstance(fg, list):
        for ref in fg:
            if isinstance(ref, int) and ref > 0:
                ids.add(f"export:{ref - 1}")
    return ids


def _extract_declaration(
    obj: ObjectRecord,
    entry: dict[str, Any],
    graphs: list[dict[str, Any]],
    fg_ids: set[str],
    export_map: Any,
) -> dict[str, Any]:
    """parent_class / interfaces / functions for the owning asset export."""
    props = obj.properties or {}
    parent = None
    parent_value = props.get("ParentClass")
    if isinstance(parent_value, dict):
        value = parent_value.get("value")
        if isinstance(value, dict):
            parent = value.get("object_name")
        elif isinstance(value, int) and value > 0 and export_map is not None:
            entry_obj = export_map[value - 1] if value - 1 < len(export_map) else None
            if entry_obj is not None:
                parent = getattr(entry_obj, "object_name", None)
    functions: list[dict[str, Any]] = []
    graph_by_id = {g["id"]: g for g in graphs}
    for oid in sorted(fg_ids):
        graph = graph_by_id.get(oid)
        if graph is not None and graph.get("name"):
            functions.append({"id": oid, "name": graph["name"]})
    return {
        "parent_class": parent,
        "interfaces": entry.get("interfaces", []),
        "functions": functions,
    }


def _guid_hex(guid_fields: Any) -> str:
    """Serialize a decoded Guid struct fields dict (A/B/C/D int32) to 32 hex."""
    if not isinstance(guid_fields, dict):
        return ""
    return "".join(f"{int(guid_fields.get(k, 0)) & 0xFFFFFFFF:08x}" for k in ("A", "B", "C", "D"))


def _extract_variables(obj: ObjectRecord) -> list[dict[str, Any]]:
    """NewVariables (BPVariableDescription) names and GUIDs; VarType stays opaque.

    VarType bodies are serialized member-wise (FEdGraphPinType, TStructOpsTypeTraits)
    and are NOT decoded — type claims are therefore never made (#630). A
    UE-source-verified VarType decode is a tracked follow-up.
    """
    props = obj.properties or {}
    raw = props.get("NewVariables")
    if not isinstance(raw, dict) or not isinstance(raw.get("value"), list):
        return []
    out: list[dict[str, Any]] = []
    for desc in raw["value"]:
        if not isinstance(desc, dict):
            continue
        fields = desc.get("fields", {})
        if not isinstance(fields, dict):
            continue
        out.append(
            {
                "name": fields.get("VarName"),
                "guid": _guid_hex(fields.get("VarGuid", {}).get("fields"))
                if isinstance(fields.get("VarGuid"), dict)
                else "",
                "type": "opaque",
            }
        )
    return out


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
            CoverageEntry(
                feature="niagara.domain",
                status="partial",
                detail="kind/name only; graph and variable summaries not extracted",
            ),
        ]
        obj.coverage.extend(coverage)
        return result


register_handler(NiagaraHandler())


# ── Physics family (#619) — summary tier until decoded fixtures exist ──


class PhysicsAssetHandler:
    """Enrich PhysicsAsset objects with body/constraint summary (#619).

    Property names per UE source:
    ``Engine/Source/Runtime/Engine/Classes/PhysicsEngine/PhysicsAsset.h`` —
    ``UPROPERTY() TArray<int32> BoundsBodies``, ``UPROPERTY(instanced)
    TArray<TObjectPtr<USkeletalBodySetup>> SkeletalBodySetups``,
    ``UPROPERTY(instanced) TArray<TObjectPtr<UPhysicsConstraintTemplate>>
    ConstraintSetup`` (editor-saved packages carry these as tagged
    properties; instanced bodies are exports in the same package).
    ``UPhysicsAsset::Serialize`` in
    ``Engine/Source/Runtime/Engine/Private/PhysicsEngine/PhysicsAsset.cpp``
    writes CollisionDisableTable as raw binary after the tagged properties —
    not decoded here. Summary tier: never yields ``semantic="complete"``
    (#629).
    """

    capability = "summary"

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") == "PhysicsAsset"

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        result: dict[str, Any] = {"kind": "physics_asset", "name": obj.name}
        props = obj.properties or {}
        coverage: list[CoverageEntry] = []

        bodies = _array_value(props, "SkeletalBodySetups")
        if bodies is not None:
            result["body_count"] = len(bodies)
            coverage.append(CoverageEntry(feature="physics_asset.bodies", status="present"))
        else:
            coverage.append(
                CoverageEntry(feature="physics_asset.bodies", status="missing", detail="SkeletalBodySetups not in property bag")
            )

        constraints = _array_value(props, "ConstraintSetup")
        if constraints is not None:
            result["constraint_count"] = len(constraints)
            coverage.append(CoverageEntry(feature="physics_asset.constraints", status="present"))
        else:
            coverage.append(
                CoverageEntry(feature="physics_asset.constraints", status="missing", detail="ConstraintSetup not in property bag")
            )

        # Instanced body/constraint exports live in the same package; their
        # per-body collision shapes are not decoded at this tier.
        body_exports = [o.name for o in all_objects if (o.class_name or "") == "SkeletalBodySetup"]
        if body_exports:
            result["bodies"] = body_exports[:100]
            coverage.append(
                CoverageEntry(
                    feature="physics_asset.shapes",
                    status="partial",
                    detail="collision shapes inside USkeletalBodySetup exports not decoded",
                )
            )

        coverage.append(
            CoverageEntry(
                feature="physics_asset.collision_disable_table",
                status="missing",
                detail="raw binary after tagged properties (PhysicsAsset.cpp UPhysicsAsset::Serialize), not decoded",
            )
        )
        obj.coverage.extend(coverage)
        return result


class PhysicalMaterialHandler:
    """Enrich PhysicalMaterial objects with friction/restitution/density summary (#619).

    Property names per UE source:
    ``Engine/Source/Runtime/PhysicsCore/Public/PhysicalMaterials/PhysicalMaterial.h`` —
    ``UPhysicalMaterial : UObject`` with UPROPERTY floats ``Friction``,
    ``StaticFriction``, ``Restitution``, ``Density`` and
    ``TEnumAsByte<EPhysicalSurface> SurfaceType``; serialized as ordinary
    tagged properties (no custom post-property binary). Summary tier until
    a decoded fixture backfills #619 (#629).
    """

    capability = "summary"

    _FLOAT_FIELDS = (
        ("Friction", "friction"),
        ("StaticFriction", "static_friction"),
        ("Restitution", "restitution"),
        ("Density", "density"),
    )

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") == "PhysicalMaterial"

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        result: dict[str, Any] = {"kind": "physical_material", "name": obj.name}
        props = obj.properties or {}
        coverage: list[CoverageEntry] = []
        found = 0

        for prop_name, key in self._FLOAT_FIELDS:
            num = _number_value(_prop_value(props, prop_name))
            if num is not None:
                result[key] = num
                found += 1
                coverage.append(CoverageEntry(feature=f"physical_material.{key}", status="present"))
            else:
                coverage.append(CoverageEntry(feature=f"physical_material.{key}", status="missing"))

        surface = _enum_name(_prop_value(props, "SurfaceType"))
        if surface is not None:
            result["surface_type"] = surface
            coverage.append(CoverageEntry(feature="physical_material.surface_type", status="present"))
        else:
            coverage.append(CoverageEntry(feature="physical_material.surface_type", status="missing"))

        obj.coverage.extend(coverage)
        return result if found or surface is not None else None


register_handler(PhysicsAssetHandler())
register_handler(PhysicalMaterialHandler())


# ── Animation family (#618) — summary tier until decoded fixtures exist ──


def _struct_fields(item: Any) -> dict[str, Any] | None:
    """Fields dict of a normalized struct value, or None."""
    if isinstance(item, dict) and item.get("kind") == "struct":
        fields = item.get("fields")
        return fields if isinstance(fields, dict) else None
    return None


class AnimBlendSpaceHandler:
    """Enrich BlendSpace/BlendSpace1D objects with axis and sample summary (#618).

    Property names per UE source:
    ``Engine/Source/Runtime/Engine/Classes/Animation/BlendSpace.h`` —
    ``UPROPERTY(EditAnywhere, Category = BlendParametersTest) struct
    FBlendParameter BlendParameters[3]`` (fixed 3-slot axis array; FBlendParameter
    fields ``DisplayName/Min/Max/GridNum``) and ``UPROPERTY(EditAnywhere,
    Category=BlendSamples) TArray<FBlendSample> SampleData`` (FBlendSample
    fields ``Animation/SampleValue``). Editor-saved packages carry both as
    tagged properties. Summary tier (#629).
    """

    capability = "summary"

    _BLEND_CLASSES = ("BlendSpace", "BlendSpace1D")

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") in self._BLEND_CLASSES

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        cn = obj.class_name or ""
        result: dict[str, Any] = {"kind": "anim_blend_space", "blend_space_type": cn, "name": obj.name}
        props = obj.properties or {}
        coverage: list[CoverageEntry] = []

        # BlendParameters is a fixed 3-slot array; unconfigured slots carry
        # empty/None display names.
        params = _array_value(props, "BlendParameters")
        if params is not None:
            axes: list[dict[str, Any]] = []
            for item in params:
                fields = _struct_fields(item)
                if fields is None:
                    continue
                name = fields.get("DisplayName")
                if not isinstance(name, str) or name in ("", "None"):
                    continue
                axis: dict[str, Any] = {"name": name}
                for key, out in (("Min", "min"), ("Max", "max"), ("GridNum", "grid_num")):
                    num = _number_value(fields.get(key))
                    if num is not None:
                        axis[out] = num
                axes.append(axis)
            result["axes"] = axes
            result["dimension"] = len(axes)
            coverage.append(CoverageEntry(feature="anim_blend_space.axes", status="present"))
        else:
            coverage.append(
                CoverageEntry(feature="anim_blend_space.axes", status="missing", detail="BlendParameters not in property bag")
            )

        samples = _array_value(props, "SampleData")
        if samples is not None:
            points: list[dict[str, Any]] = []
            for item in samples:
                fields = _struct_fields(item)
                if fields is None:
                    continue
                point: dict[str, Any] = {}
                ref = fields.get("Animation")
                if isinstance(ref, str):
                    point["animation"] = ref
                value = _struct_fields(fields.get("SampleValue"))
                if value is not None:
                    coords = [_number_value(value.get(c)) for c in ("X", "Y", "Z")]
                    point["position"] = [c if c is not None else 0.0 for c in coords]
                points.append(point)
            result["sample_count"] = len(samples)
            result["samples"] = points[:100]
            coverage.append(CoverageEntry(feature="anim_blend_space.samples", status="present"))
        else:
            coverage.append(
                CoverageEntry(
                    feature="anim_blend_space.samples",
                    status="missing",
                    detail="SampleData not in property bag; grid/triangulation data not decoded",
                )
            )

        obj.coverage.extend(coverage)
        return result


class AnimCompositeHandler:
    """Enrich AnimComposite objects with track/segment summary (#618).

    Property names per UE source:
    ``Engine/Source/Runtime/Engine/Classes/Animation/AnimComposite.h`` —
    ``UPROPERTY() FAnimTrack AnimationTrack``; ``FAnimTrack`` and its
    ``UPROPERTY(...) TArray<FAnimSegment> AnimSegments`` are defined in
    ``Engine/Source/Runtime/Engine/Classes/Animation/AnimCompositeBase.h``
    (FAnimSegment fields ``AnimReference/StartPos/AnimStartTime/AnimEndTime``).
    Editor-saved packages carry the track as a tagged struct property.
    Summary tier (#629).
    """

    capability = "summary"

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") == "AnimComposite"

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        result: dict[str, Any] = {"kind": "anim_composite", "name": obj.name}
        props = obj.properties or {}

        track = _struct_fields(props.get("AnimationTrack"))
        if track is None:
            obj.coverage.append(
                CoverageEntry(
                    feature="anim_composite.track",
                    status="missing",
                    detail="AnimationTrack struct not in property bag",
                )
            )
            return result

        segments = _array_value(track, "AnimSegments") or []
        entries: list[dict[str, Any]] = []
        for item in segments:
            fields = _struct_fields(item)
            if fields is None:
                continue
            seg: dict[str, Any] = {}
            ref = fields.get("AnimReference")
            if isinstance(ref, str):
                seg["animation"] = ref
            for key, out in (("StartPos", "start"), ("AnimStartTime", "start_time"), ("AnimEndTime", "end_time")):
                num = _number_value(fields.get(key))
                if num is not None:
                    seg[out] = num
            entries.append(seg)
        result["segment_count"] = len(segments)
        result["segments"] = entries[:100]
        obj.coverage.append(
            CoverageEntry(
                feature="anim_composite.track",
                status="present" if segments else "partial",
                detail="tracks/blending behaviors beyond segments not decoded",
            )
        )
        return result


class AnimLayerInterfaceHandler:
    """Enrich AnimLayerInterface objects (#618).

    UE source: ``Engine/Source/Runtime/Engine/Classes/Animation/
    AnimLayerInterface.h`` — in the 5.8 checkout ``UAnimLayerInterface`` is a
    MinimalAPI ``UInterface`` with no UPROPERTY members; function metadata
    (``TArray<FAnimFunction> Functions``) existed in older 4.2x-era releases
    of the same header. This handler reports ``Functions`` when a package
    carries it, and an explicit missing coverage entry otherwise. No peer
    parser decodes this type, so nothing is guessed. Summary tier (#629).
    """

    capability = "summary"

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") == "AnimLayerInterface"

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        result: dict[str, Any] = {"kind": "anim_layer_interface", "name": obj.name}
        props = obj.properties or {}
        functions = _array_value(props, "Functions")
        if functions is not None:
            entries: list[dict[str, Any]] = []
            for item in functions:
                fields = _struct_fields(item) or {}
                fn: dict[str, Any] = {}
                for key, out in (("Name", "name"), ("Type", "type")):
                    val = fields.get(key)
                    if isinstance(val, (str, int)):
                        fn[out] = val
                entries.append(fn)
            result["function_count"] = len(functions)
            result["functions"] = entries[:100]
            obj.coverage.append(
                CoverageEntry(feature="anim_layer_interface.functions", status="present")
            )
        else:
            obj.coverage.append(
                CoverageEntry(
                    feature="anim_layer_interface.functions",
                    status="missing",
                    detail="no Functions property (removed from UAnimLayerInterface in modern UE); inputs/outputs not decoded",
                )
            )
        return result


register_handler(AnimBlendSpaceHandler())
register_handler(AnimCompositeHandler())
register_handler(AnimLayerInterfaceHandler())


# ── Material family (#620) — summary tier until decoded fixtures exist ──


class MaterialFunctionHandler:
    """Enrich MaterialFunction objects with input/output and expression counts (#620).

    UE source: ``Engine/Source/Runtime/Engine/Public/Materials/
    MaterialFunction.h`` — ``UPROPERTY() FMaterialExpressionCollection
    ExpressionCollection``; the expressions (including
    ``UMaterialExpressionFunctionInput``/``...Output``, whose UPROPERTY
    ``FName InputName``/``OutputName`` are in
    ``Engine/Source/Runtime/Engine/Public/Materials/
    MaterialExpressionFunctionInput.h`` / ``...Output.h``) are stored as
    exports in the same editor-saved package. Node graph evaluation is not
    decoded; counts and connector names are real export data. Summary tier
    (#629).
    """

    capability = "summary"

    _FUNCTION_CLASSES = ("MaterialFunction", "MaterialFunctionInterface")

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") in self._FUNCTION_CLASSES

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        result: dict[str, Any] = {"kind": "material_function", "name": obj.name}
        coverage: list[CoverageEntry] = []

        inputs: list[str] = []
        outputs: list[str] = []
        expression_count = 0
        function_calls = 0
        for other in all_objects:
            other_class = other.class_name or ""
            if not other_class.startswith("MaterialExpression"):
                continue
            expression_count += 1
            if other_class == "MaterialExpressionFunctionInput":
                name = _prop_value(other.properties or {}, "InputName")
                inputs.append(str(name) if isinstance(name, (str, int)) else other.name)
            elif other_class == "MaterialExpressionFunctionOutput":
                name = _prop_value(other.properties or {}, "OutputName")
                outputs.append(str(name) if isinstance(name, (str, int)) else other.name)
            elif other_class == "MaterialExpressionMaterialFunctionCall":
                function_calls += 1

        result["input_names"] = inputs[:100]
        result["output_names"] = outputs[:100]
        result["input_count"] = len(inputs)
        result["output_count"] = len(outputs)
        result["expression_count"] = expression_count
        result["function_call_count"] = function_calls

        if expression_count:
            coverage.append(
                CoverageEntry(feature="material_function.expressions", status="present", detail=f"{expression_count} expression exports")
            )
        else:
            coverage.append(
                CoverageEntry(
                    feature="material_function.expressions",
                    status="missing",
                    detail="no MaterialExpression* exports (cooked or stripped editor data)",
                )
            )
        obj.coverage.extend(coverage)
        return result


class MaterialParameterCollectionHandler:
    """Enrich MaterialParameterCollection objects with scalar/vector parameter summary (#620).

    Property names per UE source:
    ``Engine/Source/Runtime/Engine/Public/Materials/
    MaterialParameterCollection.h`` — ``UPROPERTY(EditAnywhere,
    Category=Material) TArray<FCollectionScalarParameter> ScalarParameters``
    and ``TArray<FCollectionVectorParameter> VectorParameters``; each carries
    ``FName ParameterName`` and a ``DefaultValue`` (float / FLinearColor with
    R/G/B/A float fields). Editor-saved packages carry these as tagged
    properties. Summary tier (#629).
    """

    capability = "summary"

    def supports(self, obj: ObjectRecord, context: VersionContext) -> bool:
        return (obj.class_name or "") == "MaterialParameterCollection"

    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        result: dict[str, Any] = {"kind": "material_parameter_collection", "name": obj.name}
        props = obj.properties or {}
        coverage: list[CoverageEntry] = []

        scalars = _array_value(props, "ScalarParameters")
        if scalars is not None:
            result["scalar_params"] = self._params(scalars, "default_value")
            result["scalar_param_count"] = len(scalars)
            coverage.append(CoverageEntry(feature="material_parameter_collection.scalars", status="present"))
        else:
            coverage.append(
                CoverageEntry(feature="material_parameter_collection.scalars", status="missing", detail="ScalarParameters not in property bag")
            )

        vectors = _array_value(props, "VectorParameters")
        if vectors is not None:
            result["vector_params"] = self._params(vectors, "default_rgba")
            result["vector_param_count"] = len(vectors)
            coverage.append(CoverageEntry(feature="material_parameter_collection.vectors", status="present"))
        else:
            coverage.append(
                CoverageEntry(feature="material_parameter_collection.vectors", status="missing", detail="VectorParameters not in property bag")
            )

        obj.coverage.extend(coverage)
        return result

    @staticmethod
    def _params(items: list[Any], value_key: str) -> list[dict[str, Any]]:
        params: list[dict[str, Any]] = []
        for item in items:
            fields = _struct_fields(item)
            if fields is None:
                continue
            entry: dict[str, Any] = {"name": str(fields.get("ParameterName", ""))}
            default = fields.get("DefaultValue")
            if value_key == "default_value":
                num = _number_value(default)
                if num is not None:
                    entry[value_key] = num
            else:
                color = _struct_fields(default)
                if color is not None:
                    rgba = [_number_value(color.get(c)) or 0.0 for c in ("R", "G", "B", "A")]
                    entry[value_key] = rgba
            params.append(entry)
        return params[:100]


register_handler(MaterialFunctionHandler())
register_handler(MaterialParameterCollectionHandler())
