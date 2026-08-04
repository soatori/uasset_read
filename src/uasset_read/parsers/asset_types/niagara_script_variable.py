"""NiagaraScriptVariable asset type handler

Projects verified tagged properties of UNiagaraScriptVariable exports and
captures the native tail. Mirrors the NiagaraGraph/NiagaraScript handler
precedent (OPAQUE_CLASS_PAYLOAD routing + handler projection).

Verified tagged properties (fixture NM_BPSystemEvent.uasset, all 11 exports):
- DefaultMode: EnumProperty
- Variable: StructProperty (NiagaraVariable) — decoded by B1/#515, opaque here
- Metadata: StructProperty (NiagaraVariableMetaData) — B1/#515
- DefaultValueVariant: StructProperty (NiagaraVariant) — B1/#515
- ChangeId: StructProperty (Guid)
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

_PROJECTED_PROPERTIES = (
    "DefaultMode", "Variable", "Metadata", "DefaultValueVariant", "ChangeId",
)


class NiagaraScriptVariableHandler(ClassHandler):
    """NiagaraScriptVariable handler — projects tagged properties."""

    def can_handle(self, class_name: str) -> bool:
        return class_name == "NiagaraScriptVariable"

    @property
    def handler_name(self) -> str:
        return "NiagaraScriptVariableHandler"

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

            tagged_properties: dict[str, Any] = {}
            for prop_name in _PROJECTED_PROPERTIES:
                if prop_name in properties:
                    tagged_properties[prop_name] = properties[prop_name]

            # Calculate native tail offset/size
            tail_offset = archive.tell()
            serial_end = export.serial_offset + export.serial_size
            tail_size = max(0, serial_end - tail_offset)

            data: dict[str, Any] = {
                "asset_type": "NiagaraScriptVariable",
                "parse_status": validate_parse_status("partial_metadata"),
                "variable_name": str(export.object_name),
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
            logger.warning("NiagaraScriptVariable parse error: %s", e)
            return HandlerResult(
                success=False,
                error_message=str(e),
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )
