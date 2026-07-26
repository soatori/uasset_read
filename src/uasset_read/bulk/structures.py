"""Bulk Data structures — mirrors TBulkData.

Handles storage and loading of large data blocks (textures, meshes, etc.).
"""
from dataclasses import dataclass
from enum import IntFlag


class BulkDataFlags(IntFlag):
    """Bulk Data flags"""
    NONE = 0
    DATA_IN_INLINE = 0x01  # Data stored inline
    DATA_SEPARATE_FILE = 0x02  # Data stored in a separate file (.ubulk)
    DATA_LAZY = 0x04  # Lazy loading
    DATA_EMPTY = 0x08  # Empty data
    DATA_SINGLE_MIP = 0x10  # Single Mip only
    DATA_SHORT_INLINED = 0x20  # Short data stored inline
    DATA_IN_NEW_UNIVERSAL_CONTAINER = 0x40
    DATA_IN_NEW_OODLE_CONTAINER = 0x80
    DATA_IN_ICO_CONTAINER = 0x100


@dataclass
class FBulkDataHeader:
    """Bulk Data header"""
    flags: int
    element_count: int = 0
    element_size: int = 0
    offset_in_file: int = 0
    size_on_disk: int = 0

    # Compression info
    compression_flags: int = 0
    compression_block_count: int = 0

    @property
    def is_data_stored_inline(self) -> bool:
        """Whether data is stored inline"""
        return bool(self.flags & BulkDataFlags.DATA_IN_INLINE)

    @property
    def is_data_in_separate_file(self) -> bool:
        """Whether data is stored in a separate file"""
        return bool(self.flags & BulkDataFlags.DATA_SEPARATE_FILE)

    @property
    def is_lazy(self) -> bool:
        """Whether data uses lazy loading"""
        return bool(self.flags & BulkDataFlags.DATA_LAZY)

    @property
    def is_empty(self) -> bool:
        """Whether data is empty"""
        return bool(self.flags & BulkDataFlags.DATA_EMPTY)

    @property
    def data_size(self) -> int:
        """Total data size"""
        return self.element_count * self.element_size
