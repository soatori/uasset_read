"""SchemaProvider — Protocol for unversioned property schema lookup.

Phase 2 stub — provides the interface for unversioned property reading.
Schema sources: .usmap files, loaded packages, built-in UE type descriptions,
or caller injection.

No schema available → return opaque property region, never guess field order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class FieldSchema:
    """Schema for a single property field in an unversioned struct."""

    name: str
    type_name: str  # "IntProperty", "StructProperty", etc.
    size: int = 0  # Serialized size hint (0 = variable)
    struct_type: str | None = None  # For StructProperty inner type
    enum_type: str | None = None  # For EnumProperty/ByteProperty
    array_inner: str | None = None  # For ArrayProperty inner type
    is_weak_pointer: bool = False
    is_optional: bool = False


@runtime_checkable
class SchemaProvider(Protocol):
    """Protocol for providing unversioned property schemas.

    Implementations:
    - UsmapSchemaProvider: reads .usmap schema files
    - PackageSchemaProvider: extracts schemas from loaded packages
    - BuiltInSchemaProvider: hardcoded UE built-in type schemas
    - CompositeSchemaProvider: chains multiple providers
    """

    def fields_for(self, class_path: str, context: Any = None) -> Sequence[FieldSchema] | None:
        """Return field schemas for a class, or None if unknown.

        Args:
            class_path: UE class path (e.g. "/Script/Engine.StaticMesh")
            context: Optional VersionContext or other context

        Returns:
            Sequence of FieldSchema if known, None if no schema available.
            Never returns empty — None means "unknown class".
        """
        ...


class UsmapSchemaProvider:
    """Schema provider that reads .usmap files.

    .usmap is the cooked schema format produced by UE's
    USchemaGenerator or third-party tools.

    Phase 2 stub — parsing not yet implemented.
    """

    def __init__(self, usmap_path: str | None = None):
        self._path = usmap_path
        self._schemas: dict[str, list[FieldSchema]] = {}

    def load(self) -> None:
        """Load and parse the .usmap file.

        TODO: Implement .usmap binary parsing.
        Format: magic + version + name_map + struct_count + struct_entries
        """
        raise NotImplementedError(
            "UsmapSchemaProvider.load requires .usmap file parsing implementation"
        )

    def fields_for(self, class_path: str, context: Any = None) -> Sequence[FieldSchema] | None:
        return self._schemas.get(class_path)


class CompositeSchemaProvider:
    """Chain multiple schema providers, first match wins."""

    def __init__(self, providers: list[SchemaProvider] | None = None):
        self._providers = list(providers or [])

    def add(self, provider: SchemaProvider) -> None:
        self._providers.append(provider)

    def fields_for(self, class_path: str, context: Any = None) -> Sequence[FieldSchema] | None:
        for provider in self._providers:
            result = provider.fields_for(class_path, context)
            if result is not None:
                return result
        return None


# Built-in schemas for common UE types (minimal set)
_BUILTIN_SCHEMAS: dict[str, list[FieldSchema]] = {}


def register_builtin_schema(class_path: str, fields: list[FieldSchema]) -> None:
    """Register a built-in schema for a UE class."""
    _BUILTIN_SCHEMAS[class_path] = fields


class BuiltInSchemaProvider:
    """Schema provider using hardcoded UE built-in types."""

    def fields_for(self, class_path: str, context: Any = None) -> Sequence[FieldSchema] | None:
        return _BUILTIN_SCHEMAS.get(class_path)
