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
    # UE zero-mask after fragments when any HasAnyZeroes:
    # NumBits as uint8 (<=8) or wider encoding, then packed mask bytes.
    # See UnversionedPropertySerialization.cpp FUnversionedHeader.
    if any(f.has_any_zeroes for f in fragments):
        if cursor >= total:
            raise ValueError("unversioned zero-mask truncated")
        nbits = data[cursor]
        cursor += 1
        if nbits == 0:
            pass
        elif nbits <= 8:
            cursor += (nbits + 7) // 8
        elif nbits <= 16:
            # NumBits stored as uint16 when >8 in some paths; re-read as LE u16
            # after the first count byte is incomplete — treat first byte as low
            # and require 2-byte count then mask (UE: SerializeNumBits).
            # Conservative bound: consume ceil(nbits/8) mask bytes from here.
            cursor += (nbits + 7) // 8
        else:
            cursor += ((nbits + 31) // 32) * 4
        if cursor > total:
            raise ValueError("unversioned zero-mask truncated")
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

        # Schema present: parse header (incl. zero-mask) to bound the stream.
        # Full field walk remains in property_parser._parse_unversioned_properties_from_mapping
        # (archive+export context); this reader never guesses field widths.
        try:
            raw = input.source.read_at(input.start, input.size)
            header = parse_unversioned_header(raw)
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

        # Header validated; field walk needs archive/export identity (production
        # path). Without it, bound the stream as opaque rather than invent layout.
        consumed = min(header.header_size, input.size)
        walk_region = region_from_source(
            input.source,
            input.start,
            input.size,
            status="opaque",
            reason="schema_walk_needs_export_context",
        )
        diag = Diagnostic(
            severity="warning",
            code="UNVERSIONED_SCHEMA_WALK_DEFERRED",
            message=(
                f"schema fields present for {input.class_name}; "
                "byte walk runs via property_parser with export context"
            ),
            stage="properties.unversioned",
            object_id=input.object_id,
            offset=input.start,
            size=input.size,
            effect="semantic_loss",
            reason="schema_required",
        )
        return PropertyReadResult(
            values=PropertyBag(),
            consumed=consumed,
            regions=[walk_region],
            diagnostics=[diag],
            status="opaque",
        )
