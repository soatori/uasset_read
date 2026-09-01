"""Shared tagged-property projection handler for Niagara aux exports (#521).

NiagaraGraph, NiagaraScript and NiagaraScriptVariable all serialize the same
shape: project a fixed list of tagged properties, add one or two
class-specific derived fields, and capture the opaque native tail. The three
handlers differ only by the property tuple, the name key and the derived
field hook, so one parameterized handler plus the table below replaces them.

Verified tagged properties (fixture NM_BPSystemEvent.uasset):
- NiagaraScriptVariable: DefaultMode (EnumProperty), Variable / Metadata /
  DefaultValueVariant (structs, opaque here), ChangeId (Guid)
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport

from uasset_read.parsers.asset_types.property_extractor import build_properties_dict
from uasset_read.parsers.class_registry import ClassHandler, HandlerResult
from uasset_read.serializers.object_resources import resolve_class_name

logger = logging.getLogger(__name__)


def _node_exports(export: "ObjectExport", properties: dict[str, Any]) -> dict[str, Any]:
    """Resolve Nodes array references to NiagaraNode* export entries.

    Entries are PackageIndex values: positive = export index + 1,
    negative = import, zero = null. Only export references resolving
    to NiagaraNode* classes are projected (contract scope); comment
    nodes and invalid references are omitted.
    """
    refs: list[dict[str, Any]] = []
    nodes_value = properties.get("Nodes")
    if not isinstance(nodes_value, list):
        return {"node_exports": refs}
    export_map = getattr(export, "package_export_map", None)
    if export_map is None:
        logger.debug("No package_export_map available for node ref resolution")
        return {"node_exports": refs}
    import_map = getattr(export, "package_import_map", [])
    for ref in nodes_value:
        if not isinstance(ref, int) or ref <= 0:
            continue  # null or import reference: not an export node
        idx = ref - 1
        if idx >= len(export_map):
            continue  # invalid reference: omit per contract fallback
        try:
            cls = resolve_class_name(
                export_map[idx].class_index,
                import_map,
                export_map,
            )
        except (KeyError, AttributeError, IndexError):
            continue
        if cls and cls.startswith("NiagaraNode"):
            refs.append({"export_index": idx, "class": cls})
    return {"node_exports": refs}


def _script_usage(_export: "ObjectExport", properties: dict[str, Any]) -> dict[str, Any]:
    """Project script_usage from the Usage enum property."""
    usage = properties.get("Usage")
    if isinstance(usage, dict) and usage.get("value_name"):
        return {"script_usage": str(usage["value_name"])}
    if isinstance(usage, str):
        return {"script_usage": usage}
    return {}


class NiagaraProjectionHandler(ClassHandler):
    """Project a fixed tuple of tagged properties plus a derived-field hook."""

    def __init__(
        self,
        class_name: str,
        projected_props: tuple[str, ...],
        name_key: str,
        hook: Optional[Callable[["ObjectExport", dict[str, Any]], dict[str, Any]]] = None,
    ) -> None:
        self._class_name = class_name
        self._projected_props = projected_props
        self._name_key = name_key
        self._hook = hook

    def can_handle(self, class_name: str) -> bool:
        return class_name == self._class_name

    @property
    def handler_name(self) -> str:
        return f"{self._class_name}Handler"

    def parse(
        self,
        export: "ObjectExport",
        archive: "FArchive",
        context: Optional[Any] = None,
    ) -> HandlerResult:
        try:
            properties_list = getattr(export, "properties", [])
            if not properties_list:
                return HandlerResult(
                    success=False,
                    error_message="No properties found",
                )

            properties = build_properties_dict(properties_list)
            tagged_properties = {p: properties[p] for p in self._projected_props if p in properties}

            # Calculate native tail offset/size
            tail_offset = archive.tell()
            serial_end = export.serial_offset + export.serial_size
            tail_size = max(0, serial_end - tail_offset)

            data: dict[str, Any] = {
                "asset_type": self._class_name,
                "parse_status": "partial_metadata",
                self._name_key: str(export.object_name),
                "tagged_properties": tagged_properties,
            }
            if self._hook is not None:
                data.update(self._hook(export, properties))
            data["native_tail"] = {
                "offset": tail_offset,
                "size": tail_size,
                "status": "opaque",
            }

            return HandlerResult(success=True, data=data)

        except (KeyError, TypeError, ValueError) as e:
            logger.warning("%s parse error: %s", self._class_name, e)
            return HandlerResult(success=False, error_message=str(e))


# (class, projected tagged properties, name key, derived-field hook)
NIAGARA_PROJECTIONS: tuple[tuple[str, tuple[str, ...], str, Any], ...] = (
    (
        "NiagaraGraph",
        ("ChangeId", "LastBuiltTraversalDataChangeId", "CachedUsageInfo", "VariableToScriptVariable", "Nodes"),
        "graph_name",
        _node_exports,
    ),
    (
        "NiagaraScript",
        ("Usage", "ExposedVersion", "VersionData", "RapidIterationParameters"),
        "script_name",
        _script_usage,
    ),
    (
        "NiagaraScriptVariable",
        ("DefaultMode", "Variable", "Metadata", "DefaultValueVariant", "ChangeId"),
        "variable_name",
        None,
    ),
)

NIAGARA_HANDLERS: list[ClassHandler] = [NiagaraProjectionHandler(*spec) for spec in NIAGARA_PROJECTIONS]
