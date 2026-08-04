"""NiagaraScript asset type handler

Parse UNiagaraScript export data:
- Project tagged properties (Usage, ExposedVersion, etc.)
- Capture native tail offset/size for opaque payload (bytecode)
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


class NiagaraScriptHandler(ClassHandler):
    """NiagaraScript handler — projects tagged properties and captures native tail."""

    def can_handle(self, class_name: str) -> bool:
        return class_name == "NiagaraScript"

    @property
    def handler_name(self) -> str:
        return "NiagaraScriptHandler"

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
                "Usage", "ExposedVersion", "VersionData",
                "RapidIterationParameters",
            ):
                if prop_name in properties:
                    tagged_properties[prop_name] = properties[prop_name]

            # Project script_usage from the Usage enum property
            script_usage: Optional[str] = None
            usage = properties.get("Usage")
            if isinstance(usage, dict) and usage.get("value_name"):
                script_usage = str(usage["value_name"])
            elif isinstance(usage, str):
                script_usage = usage

            # Calculate native tail offset/size
            tail_offset = archive.tell()
            serial_end = export.serial_offset + export.serial_size
            tail_size = max(0, serial_end - tail_offset)

            # Build result data
            data: dict[str, Any] = {
                "asset_type": "NiagaraScript",
                "parse_status": validate_parse_status("partial_metadata"),
                "script_name": str(export.object_name),
                "tagged_properties": tagged_properties,
                "native_tail": {
                    "offset": tail_offset,
                    "size": tail_size,
                    "status": "opaque",
                },
            }
            if script_usage is not None:
                data["script_usage"] = script_usage

            return HandlerResult(
                success=True,
                data=data,
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )

        except (KeyError, TypeError, ValueError) as e:
            logger.warning("NiagaraScript parse error: %s", e)
            return HandlerResult(
                success=False,
                error_message=str(e),
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )
