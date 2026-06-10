"""UnversionedProperties 解析模块

按 UE FUnversionedHeader/Schema 语义解析 unversioned 属性。
UE 源码基准：UnversionedPropertySerialization.cpp
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Literal

logger = logging.getLogger(__name__)


@dataclass
class UnversionedFragment:
    """FUnversionedHeader 片段

    UE 源码：UnversionedPropertySerialization.cpp:610
    每个片段描述一段 skip/keep 序列。
    """
    skip_count: int = 0
    keep_count: int = 0
    is_zero: bool = False


@dataclass
class UnversionedHeader:
    """FUnversionedHeader 完整结构

    UE 源码：UnversionedPropertySerialization.cpp:978-1009
    """
    fragments: List[UnversionedFragment] = field(default_factory=list)
    zero_mask: int = 0  # bitfield: 1 = skip (zero), 0 = keep
    validity_mask: int = 0


@dataclass
class UnversionedPropertyResult:
    """Unversioned 解析结果"""
    properties: List[dict] = field(default_factory=list)
    fidelity: Literal["schema_backed", "opaque_missing_mapping", "partial_size_inferred"] = "schema_backed"
    unparsed_bytes: int = 0
    diagnostics: List[str] = field(default_factory=list)


def read_unversioned_header(archive) -> UnversionedHeader:
    """读取 FUnversionedHeader

    UE 源码：UnversionedPropertySerialization.cpp:978-1009

    Header 结构：
    - validity_mask: uint16 (bitfield)
    - fragments: 以终止片段结束的 fragment 列表
      - 每个 fragment: uint16
        - bit 0: is_zero (1 = skip/zero)
        - bits 1-4: keep_count (4-bit)
        - bits 5-15: skip_count (12-bit)
    - 终止条件: keep_count == 0 && skip_count == 0
    """
    validity_mask = archive.read_uint16()
    fragments: List[UnversionedFragment] = []

    while True:
        raw = archive.read_uint16()
        is_zero = bool(raw & 1)
        keep_count = (raw >> 1) & 0xF
        skip_count = (raw >> 5) & 0xFFF

        fragments.append(UnversionedFragment(
            skip_count=skip_count,
            keep_count=keep_count,
            is_zero=is_zero,
        ))

        # 终止条件
        if keep_count == 0 and skip_count == 0:
            break

    return UnversionedHeader(
        fragments=fragments,
        zero_mask=validity_mask,
        validity_mask=validity_mask,
    )


def parse_unversioned_properties(
    archive,
    header: UnversionedHeader,
    mapping: dict,
    schema_order: list,
) -> UnversionedPropertyResult:
    """按 schema 顺序解析 unversioned 属性

    UE 源码：UnversionedPropertySerialization.cpp:978-1009

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

    for fragment in header.fragments:
        # Skip 片段：跳过 skip_count 个属性
        schema_idx += fragment.skip_count

        # Zero 片段：标记为零值
        if fragment.is_zero:
            for i in range(fragment.keep_count):
                if schema_idx < len(schema_order):
                    prop_name = schema_order[schema_idx]
                    properties.append({
                        "name": prop_name,
                        "value": None,
                        "is_zero": True,
                    })
                    schema_idx += 1
            continue

        # Keep 片段：需要从 archive 读取
        for i in range(fragment.keep_count):
            if schema_idx >= len(schema_order):
                fidelity = "opaque_missing_mapping"
                diagnostics.append(
                    f"Schema index {schema_idx} >= schema_order length {len(schema_order)}"
                )
                break

            prop_name = schema_order[schema_idx]
            prop_size = mapping.get(prop_name)

            if prop_size is None:
                fidelity = "opaque_missing_mapping"
                diagnostics.append(f"Missing mapping for property '{prop_name}'")
                properties.append({
                    "name": prop_name,
                    "value": None,
                    "missing_mapping": True,
                })
            elif archive is not None:
                # 读取属性数据
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
