"""Unversioned property header parsing (UE FUnversionedHeader)."""

from __future__ import annotations

import struct as _struct
from dataclasses import dataclass, field


@dataclass(frozen=True)
class UnversionedFragment:
    skip_num: int
    has_any_zeroes: bool
    is_last: bool
    value_num: int


@dataclass(frozen=True)
class UnversionedHeader:
    fragments: tuple[UnversionedFragment, ...] = field(default_factory=tuple)
    zero_bits: tuple[bool, ...] = field(default_factory=tuple)
    header_size: int = 0


def parse_unversioned_header(data: bytes) -> UnversionedHeader:
    """Pure UE FUnversionedHeader parser (UnversionedPropertySerialization.cpp).

    Fragment u16 layout: SkipNum bits 0-6, bHasAnyZeroes bit 7, bIsLast bit 8,
    ValueNum bits 9-15. After the fragments, when any fragment has
    bHasAnyZeroes, the zero mask is serialized directly as a compact bit array
    — uint8 for <=8 masked values, uint16 for <=16, else uint32 words — with no
    separate NumBits count byte.
    """
    fragments: list[UnversionedFragment] = []
    cursor = 0
    total = len(data)
    total_masked = 0
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
        if fragment.has_any_zeroes:
            total_masked += fragment.value_num
        if fragment.is_last:
            break
        if len(fragments) > 4096:
            raise ValueError("unversioned header fragment count exceeds bound")
    if not fragments:
        raise ValueError("empty unversioned header")
    if not fragments[-1].is_last:
        raise ValueError("unterminated unversioned header")

    zero_bits: list[bool] = []
    if total_masked > 0:
        if total_masked <= 8:
            if cursor >= total:
                raise ValueError("unversioned zero-mask truncated")
            word = data[cursor]
            cursor += 1
            zero_bits = [bool(word & (1 << bit)) for bit in range(total_masked)]
        elif total_masked <= 16:
            if cursor + 2 > total:
                raise ValueError("unversioned zero-mask truncated")
            word = _struct.unpack_from("<H", data, cursor)[0]
            cursor += 2
            zero_bits = [bool(word & (1 << bit)) for bit in range(total_masked)]
        else:
            num_words = (total_masked + 31) // 32
            if cursor + num_words * 4 > total:
                raise ValueError("unversioned zero-mask truncated")
            words = [_struct.unpack_from("<I", data, cursor + i * 4)[0] for i in range(num_words)]
            cursor += num_words * 4
            for word in words:
                zero_bits.extend(bool(word & (1 << bit)) for bit in range(32))
            zero_bits = zero_bits[:total_masked]

    return UnversionedHeader(
        fragments=tuple(fragments),
        zero_bits=tuple(zero_bits),
        header_size=cursor,
    )
