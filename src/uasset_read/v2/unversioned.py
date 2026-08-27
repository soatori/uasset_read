"""Unversioned property reader — Phase 2 stub.

Reads properties without FPropertyTag headers, using schema-based
field ordering. Used for cooked packages where versioning info is stripped.

UE Source Reference:
- Engine/Source/Runtime/CoreUObject/Private/Serialization/PropertyTag.cpp
- UnversionedPropertySerialization in Engine/Source/Runtime/CoreUObject/

Blocked on: real unversioned property fixtures + SchemaProvider schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .properties import FieldSchema, SchemaProvider
from .source import SliceReader
from .version import VersionContext


@dataclass(frozen=True)
class UnversionedPropertyHeader:
    """Header for a single unversioned property entry."""

    schema_index: int = 0  # Index into the schema's field list
    array_index: int = 0  # Array element index (0 for non-array)
    has_data: bool = True  # Whether this entry has serialized data


@dataclass(frozen=True)
class UnversionedPropertyBatch:
    """A batch of unversioned properties with shared schema."""

    class_path: str
    fields: Sequence[FieldSchema]
    properties: list[UnversionedPropertyHeader]


class UnversionedPropertyReader:
    """Read unversioned properties from a SliceReader using a SchemaProvider.

    Phase 2 stub — requires real unversioned property fixtures.

    Implementation plan:
    1. Read the UnversionedPropertyBatch header (schema index + field count)
    2. For each field in the schema, read the property value
    3. Use FieldSchema.type_name to dispatch to the correct value reader
    4. Return a PropertyBag (dict[str, Any]) of parsed values

    Key constraint: never guess field order. Without a schema, return
    an opaque region descriptor and a diagnostic.
    """

    def __init__(
        self,
        schema_provider: SchemaProvider,
        context: VersionContext,
    ):
        self._schema_provider = schema_provider
        self._context = context

    def read_properties(
        self,
        reader: SliceReader,
        class_path: str,
    ) -> tuple[dict[str, Any] | None, list[Any]]:
        """Read unversioned properties from a reader.

        Returns:
            (properties_dict, diagnostics) where properties_dict is None
            if no schema is available (opaque region).
        """
        schema = self._schema_provider.fields_for(class_path, self._context)
        if schema is None:
            # No schema available — return opaque region
            from .diagnostics import Diagnostic, CODE_UNKNOWN_PROPERTY_TYPE

            diag = Diagnostic(
                severity="warning",
                code=CODE_UNKNOWN_PROPERTY_TYPE,
                message=f"No schema available for '{class_path}', returning opaque region",
                stage="properties.unversioned",
                offset=reader.tell(),
                size=reader.remaining(),
                effect="semantic_loss",
                recoverable=True,
            )
            return None, [diag]

        # TODO: Implement actual unversioned property reading
        # This requires real fixtures to validate the binary format
        raise NotImplementedError(
            f"UnversionedPropertyReader.read_properties for '{class_path}' "
            "requires real unversioned property fixtures. "
            "See: Engine/Source/Runtime/CoreUObject/Private/Serialization/PropertyTag.cpp"
        )
