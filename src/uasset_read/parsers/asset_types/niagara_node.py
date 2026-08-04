"""NiagaraNode asset type handler

Generic handler for all NiagaraNode* classes.
Projects tagged properties (class-specific) and captures native tail.

Node families and their verified properties:
- NiagaraNodeInput: Input, CallSortPriority, ChangeId
- NiagaraNodeFunctionCall: FunctionScript, CachedChangeId, FunctionDisplayName, ChangeId
- NiagaraNodeParameterMapGet: PinOutputToPinDefaultPersistentId, ChangeId
- NiagaraNodeParameterMapSet: ChangeId
- NiagaraNodeOp: OpName, ChangeId
- NiagaraNodeOutput: Outputs, ScriptType, ChangeId
- NiagaraNodeReroute: ChangeId
- NiagaraNodeSelect: SelectorPinType, SelectorPinGuid, OutputVars, OutputVarGuids, NumOptionsPerVariable, ChangeId
- NiagaraNodeStaticSwitch: InputParameterName, SwitchTypeData, OutputVars, OutputVarGuids, NumOptionsPerVariable, ChangeId
"""

import logging
from typing import TYPE_CHECKING, Any, Optional, Set

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport

from uasset_read.parsers.asset_types.property_extractor import build_properties_dict
from uasset_read.parsers.class_registry import ClassHandler, FallbackPolicy, HandlerResult
from uasset_read.models.validators import validate_parse_status

logger = logging.getLogger(__name__)

# Classes this handler can handle
_HANDLED_CLASSES: Set[str] = {
    "NiagaraNodeInput",
    "NiagaraNodeFunctionCall",
    "NiagaraNodeParameterMapGet",
    "NiagaraNodeParameterMapSet",
    "NiagaraNodeOp",
    "NiagaraNodeOutput",
    "NiagaraNodeReroute",
    "NiagaraNodeSelect",
    "NiagaraNodeStaticSwitch",
}

# Class-specific properties to project (beyond common ChangeId)
_CLASS_PROPERTIES: dict[str, list[str]] = {
    "NiagaraNodeInput": ["Input", "CallSortPriority"],
    "NiagaraNodeFunctionCall": ["FunctionScript", "CachedChangeId", "FunctionDisplayName"],
    "NiagaraNodeParameterMapGet": ["PinOutputToPinDefaultPersistentId"],
    "NiagaraNodeParameterMapSet": [],
    "NiagaraNodeOp": ["OpName"],
    "NiagaraNodeOutput": ["Outputs", "ScriptType"],
    "NiagaraNodeReroute": [],
    "NiagaraNodeSelect": ["SelectorPinType", "SelectorPinGuid", "OutputVars", "OutputVarGuids", "NumOptionsPerVariable"],
    "NiagaraNodeStaticSwitch": ["InputParameterName", "SwitchTypeData", "OutputVars", "OutputVarGuids", "NumOptionsPerVariable"],
}


class NiagaraNodeHandler(ClassHandler):
    """Generic handler for all NiagaraNode* classes."""

    def can_handle(self, class_name: str) -> bool:
        return class_name in _HANDLED_CLASSES

    @property
    def handler_name(self) -> str:
        return "NiagaraNodeHandler"

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

            # Determine class name from export (set by _try_asset_type_handler)
            class_name = getattr(export, "resolved_class_name", None) or ""
            if not class_name:
                class_name = getattr(export, "class_name", None) or ""

            # Project tagged properties
            tagged_properties: dict[str, Any] = {}

            # Common property: ChangeId
            if "ChangeId" in properties:
                tagged_properties["ChangeId"] = properties["ChangeId"]

            # Class-specific properties
            class_props = _CLASS_PROPERTIES.get(class_name, [])
            for prop_name in class_props:
                if prop_name in properties:
                    tagged_properties[prop_name] = properties[prop_name]

            # Calculate native tail offset/size
            tail_offset = archive.tell()
            serial_end = export.serial_offset + export.serial_size
            tail_size = max(0, serial_end - tail_offset)

            # Build result data
            data: dict[str, Any] = {
                "asset_type": class_name,
                "parse_status": validate_parse_status("partial_metadata"),
                "tagged_properties": tagged_properties,
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
            logger.warning("NiagaraNode parse error: %s", e)
            return HandlerResult(
                success=False,
                error_message=str(e),
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )
