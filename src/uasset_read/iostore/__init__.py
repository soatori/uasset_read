"""IoStore container system — UE5.3+ new format support"""
from uasset_read.iostore.structures import (
    FIoChunkId,
    FIoOffsetAndLength,
    FIoDirectoryIndexEntry,
    FIoStoreTocHeader,
    FIoStoreTocCompressedBlockEntry,
    EIoStoreTocVersion,
    EIoContainerFlags,
    EIoChunkType,
    EIoStoreTocReadOptions,
    TOC_MAGIC,
    TOC_HEADER_SIZE,
)
from uasset_read.iostore.reader import IoStoreReader, IoStoreInfo

__all__ = [
    # Structures
    "FIoChunkId",
    "FIoOffsetAndLength",
    "FIoDirectoryIndexEntry",
    "FIoStoreTocHeader",
    "FIoStoreTocCompressedBlockEntry",
    # Enums
    "EIoStoreTocVersion",
    "EIoContainerFlags",
    "EIoChunkType",
    "EIoStoreTocReadOptions",
    # Constants
    "TOC_MAGIC",
    "TOC_HEADER_SIZE",
    # Readers
    "IoStoreReader",
    "IoStoreInfo",
]