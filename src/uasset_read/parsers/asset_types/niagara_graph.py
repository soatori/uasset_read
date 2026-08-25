"""NiagaraGraph asset type handler

Parse UNiagaraGraph export data:
- Project tagged properties (ChangeId, Nodes, etc.)
- Extract node export references from Nodes array
- Capture native tail offset/size for opaque payload
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport

from uasset_read.parsers.asset_types.property_extractor import build_properties_dict
from uasset_read.parsers.class_registry import ClassHandler, FallbackPolicy, HandlerResult
from uasset_read.serializers.object_resources import resolve_class_name

logger = logging.getLogger(__name__)


class NiagaraGraphHandler(ClassHandler):
    """NiagaraGraph handler — projects tagged properties and node references."""

    def can_handle(self, class_name: str) -> bool:
        return class_name == "NiagaraGraph"

    @property
    def handler_name(self) -> str:
        return "NiagaraGraphHandler"

    @property
    def fallback_policy(self) -> FallbackPolicy:
        return FallbackPolicy.GENERIC_UOBJECT

    @staticmethod
    def _resolve_node_refs(export: "ObjectExport", nodes_value: Any) -> list[dict[str, Any]]:
        """Resolve Nodes array references to NiagaraNode* export entries.

        Entries are PackageIndex values: positive = export index + 1,
        negative = import, zero = null. Only export references resolving
        to NiagaraNode* classes are projected (contract scope); comment
        nodes and invalid references are omitted.
        """
        node_exports: list[dict[str, Any]] = []
        if not isinstance(nodes_value, list):
            return node_exports
        export_map = getattr(export, "package_export_map", None)
        if export_map is None:
            logger.debug("No package_export_map available for node ref resolution")
            return node_exports
        import_map = getattr(export, "package_import_map", [])
        for ref in nodes_value:
            if not isinstance(ref, int) or ref <= 0:
                continue  # null or import reference: not an export node
            idx = ref - 1
            if idx >= len(export_map):
                continue  # invalid reference: omit per contract fallback
            try:
                cls = resolve_class_name(
                    export_map[idx].class_index, import_map, export_map,
                )
            except (KeyError, AttributeError, IndexError):
                continue
            if cls and cls.startswith("NiagaraNode"):
                node_exports.append({"export_index": idx, "class": cls})
        return node_exports

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
                    fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
                )

            properties = build_properties_dict(properties_list)

            # Project tagged properties into structured output
            tagged_properties: dict[str, Any] = {}
            for prop_name in (
                "ChangeId", "LastBuiltTraversalDataChangeId",
                "CachedUsageInfo", "VariableToScriptVariable", "Nodes",
            ):
                if prop_name in properties:
                    tagged_properties[prop_name] = properties[prop_name]

            # Extract node export references from Nodes array.
            # Nodes is UEdGraph::Nodes serialized as object references
            # (PackageIndex: positive value = export index + 1).
            node_exports = self._resolve_node_refs(export, properties.get("Nodes"))

            # Calculate native tail offset/size
            tail_offset = archive.tell()
            serial_end = export.serial_offset + export.serial_size
            tail_size = max(0, serial_end - tail_offset)

            # Build result data
            data: dict[str, Any] = {
                "asset_type": "NiagaraGraph",
                "parse_status": "partial_metadata",
                "graph_name": str(export.object_name),
                "tagged_properties": tagged_properties,
                "node_exports": node_exports,
                "native_tail": {
                    "offset": tail_offset,
                    "size": tail_size,
                    "status": "opaque",
                },
            }

            return HandlerResult(
                success=True,
                data=data,
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )

        except (KeyError, TypeError, ValueError) as e:
            logger.warning("NiagaraGraph parse error: %s", e)
            return HandlerResult(
                success=False,
                error_message=str(e),
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )
