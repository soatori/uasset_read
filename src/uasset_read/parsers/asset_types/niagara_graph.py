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
from uasset_read.models.validators import validate_parse_status

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

            # Extract node export references from Nodes array
            # Nodes is an ArrayProperty containing integer export indices
            node_exports: list[dict[str, Any]] = []
            nodes_value = properties.get("Nodes")
            if isinstance(nodes_value, list):
                for idx, node_ref in enumerate(nodes_value):
                    # node_ref may be an integer index or an object reference
                    if isinstance(node_ref, int):
                        node_exports.append({
                            "export_index": node_ref,
                            "class": "unknown",
                        })
                    elif isinstance(node_ref, dict):
                        # Object reference with export_index info
                        export_idx = node_ref.get("export_index")
                        if export_idx is not None:
                            node_exports.append({
                                "export_index": export_idx,
                                "class": node_ref.get("class", "unknown"),
                            })

            # Calculate native tail offset/size
            tail_offset = archive.tell()
            serial_end = export.serial_offset + export.serial_size
            tail_size = max(0, serial_end - tail_offset)

            # Build result data
            data: dict[str, Any] = {
                "asset_type": "NiagaraGraph",
                "parse_status": validate_parse_status("partial_metadata"),
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
