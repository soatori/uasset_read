"""Schema-backed unversioned property reader (never guesses field widths)."""

from __future__ import annotations

import struct as _struct
from dataclasses import dataclass, field

from uasset_read.models.byte_ranges import region_from_source
from uasset_read.models.diagnostics import Diagnostic
from uasset_read.models.properties import PropertyBag
from uasset_read.parsers.properties import PropertyInput, PropertyReadResult
from uasset_read.parsers.properties.schema import SchemaProvider


@dataclass(frozen=True)
class UnversionedFragment:
    skip_num: int
    has_any_zeroes: bool
    is_last: bool
    value_num: int


@dataclass(frozen=True)
class UnversionedHeader:
    fragments: tuple[UnversionedFragment, ...] = field(default_factory=tuple)
    header_size: int = 0


def parse_unversioned_header(data: bytes) -> UnversionedHeader:
    """Pure UE FUnversionedHeader fragment parser (UnversionedPropertySerialization.cpp)."""
    fragments: list[UnversionedFragment] = []
    cursor = 0
    total = len(data)
    while cursor + 2 <= total:
        packed = _struct.unpack_from("<H", data, cursor)[0]
        cursor += 2
        fragment = UnversionedFragment(
            skip_num=packed & 0x007F,
            has_any_zeroes=bool(packed & 0x0080),
            is_last=bool(packed & 0x0100),
            value_num=packed >> 9,
        )
        fragments.append(fragment)
        if fragment.is_last:
            break
        if len(fragments) > 4096:
            raise ValueError("unversioned header fragment count exceeds bound")
    if not fragments:
        raise ValueError("empty unversioned header")
    if not fragments[-1].is_last:
        raise ValueError("unterminated unversioned header")
    # zero-mask is omitted from the pure header when only fragments are asserted;
    # consumers that need the mask read past header_size.
    return UnversionedHeader(fragments=tuple(fragments), header_size=cursor)


class UnversionedPropertyReader:
    """Never infers field width without an explicit SchemaProvider."""

    def __init__(self, schema: SchemaProvider | None) -> None:
        self._schema = schema

    def read(self, input: PropertyInput) -> PropertyReadResult:
        region = region_from_source(
            input.source,
            input.start,
            input.size,
            status="opaque",
            reason="schema_required",
        )
        if self._schema is None:
            diag = Diagnostic(
                severity="warning",
                code="UNVERSIONED_SCHEMA_REQUIRED",
                message=f"no schema for {input.class_name}",
                stage="properties.unversioned",
                object_id=input.object_id,
                offset=input.start,
                size=input.size,
                effect="semantic_loss",
                reason="schema_required",
            )
            return PropertyReadResult(
                values=PropertyBag(),
                consumed=input.size,
                regions=[region],
                diagnostics=[diag],
                status="opaque",
            )

        fields = self._schema.fields_for(input.class_name, input.context)
        if fields is None:
            diag = Diagnostic(
                severity="warning",
                code="UNVERSIONED_SCHEMA_REQUIRED",
                message=f"unmapped class {input.class_name}",
                stage="properties.unversioned",
                object_id=input.object_id,
                offset=input.start,
                size=input.size,
                effect="semantic_loss",
                reason="schema_required",
            )
            return PropertyReadResult(
                values=PropertyBag(),
                consumed=input.size,
                regions=[region],
                diagnostics=[diag],
                status="opaque",
            )

        # Schema present: parse header only to bound the stream; full field walk
        # stays in the legacy mapping path for cooked fixtures. Without a proven
        # byte layout for every mapping type here, remain opaque rather than guess.
        try:
            raw = input.source.read_at(input.start, input.size)
            parse_unversioned_header(raw)
        except (ValueError, _struct.error, OSError) as exc:
            diag = Diagnostic(
                severity="warning",
                code="UNVERSIONED_HEADER_INVALID",
                message=str(exc),
                stage="properties.unversioned",
                object_id=input.object_id,
                offset=input.start,
                size=input.size,
                effect="semantic_loss",
                reason="unexpected",
            )
            return PropertyReadResult(
                values=PropertyBag(),
                consumed=input.size,
                regions=[region],
                diagnostics=[diag],
                status="opaque",
            )

        diag = Diagnostic(
            severity="warning",
            code="UNVERSIONED_SCHEMA_REQUIRED",
            message=f"schema fields present but bounded walk not applied for {input.class_name}",
            stage="properties.unversioned",
            object_id=input.object_id,
            offset=input.start,
            size=input.size,
            effect="semantic_loss",
            reason="schema_required",
        )
        return PropertyReadResult(
            values=PropertyBag(),
            consumed=input.size,
            regions=[region],
            diagnostics=[diag],
            status="opaque",
        )
