"""UnversionedProperties 解析模块

按 UE FUnversionedHeader/Schema 语义解析 unversioned 属性。
UE 源码基准：UnversionedPropertySerialization.cpp
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Literal

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)

# 内存安全常量
MAX_UNVERSIONED_FRAGMENTS = 10_000  # FUnversionedHeader 最大 fragment 数量


@dataclass
class UnversionedFragment:
    """FUnversionedHeader 片段

    UE 源码：UnversionedPropertySerialization.cpp:667-696

    FFragment bit layout (uint16):
      - bits 0-6:  SkipNum (7 bits, mask 0x007F) — 跳过的属性数
      - bit 7:     bHasAnyZeroes (mask 0x0080) — 此片段是否包含零值属性
      - bit 8:     bIsLast (mask 0x0100) — 是否为最后一个片段
      - bits 9-15: ValueNum (7 bits, shift 9) — 存储的属性值数量
    """
    skip_count: int = 0
    keep_count: int = 0
    has_any_zeroes: bool = False
    is_last: bool = False


@dataclass
class UnversionedHeader:
    """FUnversionedHeader 完整结构

    UE 源码：UnversionedPropertySerialization.cpp:610-654

    结构：
    - fragments: FFragment 列表，以 bIsLast=true 的片段终止
    - zero_mask: 零值掩码（仅当任何片段的 bHasAnyZeroes=true 时存在）
      每个 bit 表示对应 keep 属性是否为零值
    """
    fragments: List[UnversionedFragment] = field(default_factory=list)
    zero_mask: int = 0  # bitfield: 1 = zero, 0 = has value
    num_zero_bits: int = 0  # zero_mask 中的有效位数


@dataclass
class UnversionedPropertyResult:
    """Unversioned 解析结果"""
    properties: List[dict] = field(default_factory=list)
    fidelity: Literal["schema_backed", "opaque_missing_mapping", "partial_size_inferred"] = "schema_backed"
    unparsed_bytes: int = 0
    diagnostics: List[str] = field(default_factory=list)


def read_unversioned_header(archive) -> UnversionedHeader:
    """读取 FUnversionedHeader

    UE 源码：UnversionedPropertySerialization.cpp:627-654

    Header 结构：
    1. fragments: 连续读取 FFragment（uint16），直到 bIsLast=true
       FFragment bit layout:
         - bits 0-6:  SkipNum (7 bits, mask 0x007F)
         - bit 7:     bHasAnyZeroes (mask 0x0080)
         - bit 8:     bIsLast (mask 0x0100)
         - bits 9-15: ValueNum (7 bits, shift 9)
    2. zero_mask: 仅当任意片段 bHasAnyZeroes=true 时存在
       格式取决于总零值位数：<=8 用 uint8，<=16 用 uint16，<=32 用 uint32

    Raises:
        ParseError: 超过 MAX_UNVERSIONED_FRAGMENTS 上限（防止损坏数据无限循环）。
    """
    fragments: List[UnversionedFragment] = []
    total_zero_bits = 0  # 需要从零掩码读取的位数
    iterations = 0

    while True:
        iterations += 1
        if iterations > MAX_UNVERSIONED_FRAGMENTS:
            raise ParseError(
                f"read_unversioned_header exceeded fragment limit ({MAX_UNVERSIONED_FRAGMENTS}) "
                f"at offset {archive.tell()}"
            )
        raw = archive.read_u16()
        skip_num = raw & 0x007F             # bits 0-6
        has_any_zeroes = bool(raw & 0x0080) # bit 7
        is_last = bool(raw & 0x0100)        # bit 8
        value_num = (raw >> 9) & 0x007F     # bits 9-15

        fragments.append(UnversionedFragment(
            skip_count=skip_num,
            keep_count=value_num,
            has_any_zeroes=has_any_zeroes,
            is_last=is_last,
        ))

        # 累计需要零掩码的位数
        if has_any_zeroes:
            total_zero_bits += value_num

        if is_last:
            break

    # 读取零掩码（仅当有零值属性时）
    zero_mask = 0
    if total_zero_bits > 0:
        if total_zero_bits <= 8:
            zero_mask = archive.read_u8()
        elif total_zero_bits <= 16:
            zero_mask = archive.read_u16()
        else:
            zero_mask = archive.read_u32()

    return UnversionedHeader(
        fragments=fragments,
        zero_mask=zero_mask,
        num_zero_bits=total_zero_bits,
    )


def parse_unversioned_properties(
    archive,
    header: UnversionedHeader,
    mapping: dict,
    schema_order: list,
) -> UnversionedPropertyResult:
    """按 schema 顺序解析 unversioned 属性

    UE 源码：UnversionedPropertySerialization.cpp:770-850

    解析逻辑：
    1. 遍历每个 fragment
    2. 先跳过 skip_count 个属性（schema_idx += skip_count）
    3. 对于 keep_count 个属性：
       - 如果 fragment.has_any_zeroes=true，检查 zero_mask 对应位
         - bit=1: 属性为零值，不从 archive 读取
         - bit=0: 从 archive 读取属性值
       - 如果 fragment.has_any_zeroes=false，所有 keep 属性都从 archive 读取

    Args:
        archive: FArchive 实例（可为 None，用于测试）
        header: 解析后的 header
        mapping: property name → size 映射
        schema_order: schema 定义的属性顺序（属性索引映射）

    Returns:
        UnversionedPropertyResult: 解析结果，含 fidelity 诊断
    """
    properties = []
    diagnostics = []
    fidelity = "schema_backed"
    schema_idx = 0  # 在 schema_order 中的当前位置
    zero_bit_idx = 0  # 在 zero_mask 中的当前位位置

    for fragment in header.fragments:
        # Skip 片段：跳过 skip_count 个属性
        schema_idx += fragment.skip_count

        # Keep 片段：处理 keep_count 个属性
        for i in range(fragment.keep_count):
            if schema_idx >= len(schema_order):
                fidelity = "opaque_missing_mapping"
                diagnostics.append(
                    f"Schema index {schema_idx} >= schema_order length {len(schema_order)}"
                )
                break

            prop_name = schema_order[schema_idx]
            prop_size = mapping.get(prop_name)

            # 检查是否为零值属性
            is_zero = False
            if fragment.has_any_zeroes:
                # 从 zero_mask 中读取对应位
                is_zero = bool(header.zero_mask & (1 << zero_bit_idx))
                zero_bit_idx += 1

            if is_zero:
                # 零值属性：不从 archive 读取
                properties.append({
                    "name": prop_name,
                    "value": None,
                    "is_zero": True,
                })
            elif prop_size is None:
                fidelity = "opaque_missing_mapping"
                diagnostics.append(f"Missing mapping for property '{prop_name}'")
                properties.append({
                    "name": prop_name,
                    "value": None,
                    "missing_mapping": True,
                })
            elif archive is not None:
                # 从 archive 读取属性数据
                raw_bytes = archive.read_bytes(prop_size)
                properties.append({
                    "name": prop_name,
                    "raw_bytes": raw_bytes.hex(),
                    "size": prop_size,
                })
            else:
                fidelity = "partial_size_inferred"
                properties.append({
                    "name": prop_name,
                    "size": prop_size,
                    "no_archive": True,
                })

            schema_idx += 1

    return UnversionedPropertyResult(
        properties=properties,
        fidelity=fidelity,
        diagnostics=diagnostics,
    )
