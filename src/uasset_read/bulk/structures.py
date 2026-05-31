"""Bulk Data 结构 — 镜像 TBulkData

用于处理大型数据块（纹理、网格体等）的存储和加载。
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntFlag
from typing import Optional


class BulkDataFlags(IntFlag):
    """Bulk Data 标志"""
    NONE = 0
    DATA_IN_INLINE = 0x01  # 数据内联存储
    DATA_SEPARATE_FILE = 0x02  # 数据存储在单独文件（.ubulk）
    DATA_LAZY = 0x04  # 延迟加载
    DATA_EMPTY = 0x08  # 空数据
    DATA_SINGLE_MIP = 0x10  # 仅单 Mip
    DATA_SHORT_INLINED = 0x20  # 短数据内联
    DATA_IN_NEW_UNIVERSAL_CONTAINER = 0x40
    DATA_IN_NEW_OODLE_CONTAINER = 0x80
    DATA_IN_ICO_CONTAINER = 0x100


@dataclass
class FBulkDataHeader:
    """Bulk Data 头部"""
    flags: int
    element_count: int = 0
    element_size: int = 0
    offset_in_file: int = 0
    size_on_disk: int = 0

    # 压缩信息
    compression_flags: int = 0
    compression_block_count: int = 0

    @property
    def is_data_stored_inline(self) -> bool:
        """数据是否内联存储"""
        return bool(self.flags & BulkDataFlags.DATA_IN_INLINE)

    @property
    def is_data_in_separate_file(self) -> bool:
        """数据是否在单独文件中"""
        return bool(self.flags & BulkDataFlags.DATA_SEPARATE_FILE)

    @property
    def is_lazy(self) -> bool:
        """是否延迟加载"""
        return bool(self.flags & BulkDataFlags.DATA_LAZY)

    @property
    def is_empty(self) -> bool:
        """是否为空数据"""
        return bool(self.flags & BulkDataFlags.DATA_EMPTY)

    @property
    def data_size(self) -> int:
        """数据总大小"""
        return self.element_count * self.element_size
