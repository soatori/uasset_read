"""IoStore 容器系统 — UE5.3+ 新格式支持"""
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
    # 结构
    "FIoChunkId",
    "FIoOffsetAndSize",
    "FIoOffsetAndLength",
    "FIoDirectoryIndexEntry",
    "FIoStoreTocHeader",
    "FIoStoreTocCompressedBlockEntry",
    "FIoStoreTocEntryMeta",
    "FIoContainerHeader",
    # 枚举
    "EIoStoreTocVersion",
    "EIoContainerFlags",
    "EIoChunkType",
    "EIoStoreTocEntryMetaFlags",
    "EIoStoreTocReadOptions",
    # 常量
    "TOC_MAGIC",
    "TOC_HEADER_SIZE",
    # 读取器
    "IoStoreReader",
    "IoStoreInfo",
]