"""Schema providers for unversioned property field layouts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from uasset_read.versioning import VersionContext


@dataclass(frozen=True)
class SchemaField:
    name: str
    type_name: str
    mapping_type: object | None = None


class SchemaProvider(Protocol):
    def fields_for(self, class_path: str, context: VersionContext) -> list[SchemaField] | None: ...


class UsmapSchemaProvider:
    """First real implementation; wraps the existing usmap/mappings path."""

    def __init__(self, mappings: object | None = None) -> None:
        self._mappings = mappings

    def fields_for(self, class_path: str, context: VersionContext) -> list[SchemaField] | None:
        mappings = self._mappings
        if mappings is None:
            return None
        struct = mappings.get_struct(class_path)
        if struct is None:
            return None
        fields = getattr(struct, "properties", None)
        if fields is None:
            return None
        ordered = [fields[index] for index in sorted(fields)]
        out: list[SchemaField] = []
        for info in ordered:
            name = getattr(info, "name", None) or getattr(info, "property_name", "")
            mapping_type = getattr(info, "mapping_type", None)
            type_name = getattr(mapping_type, "type", None) or str(mapping_type)
            out.append(SchemaField(name=name, type_name=type_name, mapping_type=mapping_type))
        return out or None
