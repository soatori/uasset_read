"""IoStore container system — UE5.3+ new format support"""
from uasset_read.iostore.structures import (
    FIoChunkId,
    FIoOffsetAndSize,
    FIoOffsetAndLength,
    FIoDirectoryIndexEntry,
    FIoStoreTocHeader,
    FIoStoreTocCompressedBlockEntry,
    FIoStoreTocEntryMeta,
    FIoContainerHeader,
    EIoStoreTocVersion,
    EIoContainerFlags,
    EIoChunkType,
    EIoStoreTocEntryMetaFlags,
    EIoStoreTocReadOptions,
    TOC_MAGIC,
    TOC_HEADER_SIZE,
)
from uasset_read.iostore.reader import IoStoreReader, IoStoreInfo

__all__ = [
    # Structures
    "FIoChunkId",
    "FIoOffsetAndSize",
    "FIoOffsetAndLength",
    "FIoDirectoryIndexEntry",
    "FIoStoreTocHeader",
    "FIoStoreTocCompressedBlockEntry",
    "FIoStoreTocEntryMeta",
    "FIoContainerHeader",
    # Enums
    "EIoStoreTocVersion",
    "EIoContainerFlags",
    "EIoChunkType",
    "EIoStoreTocEntryMetaFlags",
    "EIoStoreTocReadOptions",
    # Constants
    "TOC_MAGIC",
    "TOC_HEADER_SIZE",
    # Readers
    "IoStoreReader",
    "IoStoreInfo",
]