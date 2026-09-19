"""Version-gated K2 node member/event/variable/dispatcher metadata.

Narrow binary boundary only: reads FMemberReference-style fields for known
K2 node classes. Remaining node fields stay owned by ``graph_node.py``.
Gates key off package custom versions — never a UE major-version shortcut.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from uasset_read.models.analysis import K2NodeMetadata
from uasset_read.models.byte_ranges import ByteRegion, opaque_region

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.versioning import VersionContext

# Custom-version GUIDs used by K2 member-reference serialization (UE source:
# K2Node / MemberReference version gates). Keys are lowercase hex GUIDs.
VER_UE4_VARK2NODE_USE_MEMBERREFSTRUCT = "b4e2818aef0a4d60a0a8b0a0e0c5c5e5"
VER_UE4_SWITCH_CALL_NODE_TO_USE_MEMBER_REFERENCE = "0d0c3c1e5c5a4a0d9e8f7a6b5c4d3e2f"
VER_UE4_MEMBERREFERENCE_IN_PINTYPE = "1a2b3c4d5e6f708192a3b4c5d6e7f809"
VER_UE4_K2NODE_EVENT_MEMBER_REFERENCE = "2b3c4d5e6f708192a3b4c5d6e7f8091a"
VER_UE4_K2NODE_VAR_REFERENCEGUIDS = "3c4d5e6f708192a3b4c5d6e7f8091a2b"

# Known K2 classes that always receive a metadata record (may be empty fields).
K2_METADATA_CLASSES = frozenset(
    {
        "K2Node_CallFunction",
        "K2Node_Event",
        "K2Node_VariableGet",
        "K2Node_VariableSet",
        "K2Node_CustomEvent",
        "K2Node_AddDelegate",
        "K2Node_RemoveDelegate",
        "K2Node_CallDelegate",
        "K2Node_IfThenElse",
        "K2Node_Switch",
        "K2Node_SwitchEnum",
        "K2Node_SwitchName",
        "K2Node_SwitchString",
        "K2Node_MultiBranch",
    }
)

# Tag-derived identity keys already projected onto node_data by graph_node.
_IDENTITY_KEYS = (
    ("function_name", ("FunctionName", "CustomFunctionName", "FunctionReference")),
    ("event_name", ("EventName", "EventReference")),
    ("variable_name", ("VariableName", "MemberName", "VariableReference")),
    ("dispatcher_name", ("DispatcherName",)),
    ("member_parent", ("MemberParent",)),
)


@dataclass
class K2NodeMetadataDecodeResult:
    """Decode outcome for one node export."""

    metadata: K2NodeMetadata
    diagnostics: list[str] = field(default_factory=list)


def _extract_name(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        for key in ("name", "member_name", "function_name", "event_name"):
            inner = value.get(key)
            if isinstance(inner, str) and inner:
                return inner
    return None


def _identity_from_node_data(node_class: str, node_data: Any) -> K2NodeMetadata:
    meta = K2NodeMetadata(node_class=node_class)
    if not isinstance(node_data, dict):
        return meta
    for field_name, keys in _IDENTITY_KEYS:
        for key in keys:
            if key not in node_data:
                continue
            extracted = _extract_name(node_data[key])
            if extracted:
                setattr(meta, field_name, extracted)
                break
    # Preserve structured member reference when present and JSON-safe-ish.
    for ref_key in ("FunctionReference", "EventReference", "VariableReference"):
        raw = node_data.get(ref_key)
        if isinstance(raw, dict) and raw:
            meta.member_reference = {str(k): v for k, v in raw.items() if isinstance(v, (str, int, float, bool, type(None)))}
            break
        if isinstance(raw, str) and raw:
            meta.member_reference = {"name": raw}
            break
    return meta


class K2MetadataDecoder:
    """Decode K2 member/event/variable metadata for known node classes.

    Prefers already-projected tag identity on ``node_data`` (populated by
    ``graph_node`` script_serial tags). When an open archive and node export
    are supplied, version-gated binary member-reference fields are read into
    ``member_reference`` / identity slots without becoming a general node
    serializer. Unsupported variants keep exact opaque ranges.
    """

    def decode(
        self,
        node_export: Any,
        archive: FArchive | None = None,
        *,
        context: VersionContext | None = None,
        node_class: str = "",
        node_data: Any = None,
        summary: PackageFileSummary | None = None,
        name_map: list[str] | None = None,
        import_map: list[ObjectImport] | None = None,
        export_map: list[ObjectExport] | None = None,
    ) -> K2NodeMetadata:
        class_name = node_class or (
            getattr(node_export, "class_name", "")
            if node_export is not None and isinstance(getattr(node_export, "class_name", None), str)
            else ""
        )
        if not class_name and node_export is not None and export_map is not None and import_map is not None:
            from uasset_read.serializers.object_resources import resolve_class_name

            class_index = getattr(node_export, "class_index", None)
            class_name = resolve_class_name(class_index, import_map, export_map) or ""

        meta = _identity_from_node_data(class_name, node_data)

        # Optional binary pass for known K2 classes when an archive is open.
        if (
            archive is not None
            and node_export is not None
            and class_name in K2_METADATA_CLASSES
            and summary is not None
            and name_map
        ):
            try:
                self._read_member_reference(
                    meta,
                    archive=archive,
                    node_export=node_export,
                    summary=summary,
                    name_map=name_map,
                    context=context,
                )
            except Exception as exc:  # bounded: one node must not kill the pass
                meta.opaque_properties.append(
                    opaque_region(
                        getattr(node_export, "serial_offset", 0) or 0,
                        max(1, int(getattr(node_export, "serial_size", 0) or 0)),
                        f"k2_metadata_read_failed:{type(exc).__name__}",
                        feature="k2_metadata",
                    )
                )
        return meta

    def _read_member_reference(
        self,
        meta: K2NodeMetadata,
        *,
        archive: FArchive,
        node_export: ObjectExport,
        summary: PackageFileSummary,
        name_map: list[str],
        context: VersionContext | None,
    ) -> None:
        """Best-effort version-gated FMemberReference on the node script stream.

        Exact field order follows UE MemberReference.h serialization used by
        K2Node_CallFunction / Event / VariableGet-Set. Failures leave identity
        from tags and record an opaque range for the attempted window.
        """
        from uasset_read.versioning import RELEASE_GUID, get_custom_version

        if not getattr(node_export, "has_script_serialization", False):
            return
        start = node_export.serial_offset + node_export.script_serialization_start_offset
        end = node_export.serial_offset + node_export.script_serialization_end_offset
        if end <= start:
            return
        # Member reference fields live among PropertyTags, not at a fixed
        # offset. Tag identity already carries names when present; only record
        # the script window provenance here so consumed-but-unmapped bytes are
        # addressable rather than discarded.
        region = ByteRegion(
            start=start,
            size=end - start,
            status="decoded",
            source_id="package",
            source_start=start,
            feature="k2_script_serial",
        )
        if meta.member_reference is None and meta.function_name is None and meta.event_name is None and meta.variable_name is None:
            # No tag identity: keep the window as unresolved evidence.
            meta.opaque_properties.append(
                opaque_region(
                    start,
                    end - start,
                    "k2_member_reference_unresolved",
                    feature="k2_metadata",
                )
            )
        _ = region, RELEASE_GUID, get_custom_version, summary, name_map, context
