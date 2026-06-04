# IoStore 格式文档

## 概述

**IoStore 是 UE5 引入的新一代容器格式**，替代传统 Pak 文件，提供更高效的数据访问和更灵活的数据组织方式。

**文件组织：**
- `.utoc` — TOC（Table of Contents），存储所有数据块的元信息
- `.ucas` — 实际数据存储，可能有多个分区（`_s1.ucas`, `_s2.ucas`, ...）

**与 .uasset 关系：** 每个 .uasset 被拆分为多个 FIoChunkId（ExportBundleData、BulkData、OptionalBulkData 等），数据按 ChunkType 分散存储在 .ucas 文件中。

**替代传统 Pak 格式：** IoStore 提供更高效的数据访问（Perfect Hash 索引）、更好的分区支持、更紧凑的元数据存储。

---

## 文件结构图

### .utoc 文件结构

```
[FIoStoreTocHeader]              — 头部（魔数、版本、条目数量等）
[FIoChunkId 数组]                — 数据块标识列表（TocEntryCount 个）
[FIoOffsetAndLength 数组]        — 偏移和长度列表（TocEntryCount 个）
[FIoStoreTocCompressedBlockEntry 数组] — 压缩块条目（TocCompressedBlockEntryCount 个）
[CompressionMethods 数组]        — 压缩方法名称（CompressionMethodNameCount 个，每个 32 字节）
[DirectoryIndexBuffer]           — 目录索引数据（可选加密，DirectoryIndexSize 字节）
[TocChunkPerfectHashSeeds]       — Perfect Hash 种子（Version 4+）
[TocChunksWithoutPerfectHash]    — 无 Perfect Hash 条目（Version 5+）
[FIoStoreTocEntryMeta 数组]      — 条目元数据（哈希、标志）
[SignatureHash]                  — 签名哈希（Signed 标志时存在）
[ChunkBlockSignatures]           — 块签名数组（Signed 标志时存在）
```

### .ucas 文件结构

```
[压缩数据块1]                     — 按 FIoStoreTocCompressedBlockEntry 定位
[压缩数据块2]
...
（可能有多个分区文件 _s1.ucas, _s2.ucas）
```

---

## EIoStoreTocVersion 版本枚举

| 版本 | 值 | 说明 |
|------|-----|------|
| Invalid | 0 | 无效版本 |
| Initial | 1 | 初始版本 |
| DirectoryIndex | 2 | 添加目录索引（DirectoryIndexBuffer） |
| PartitionSize | 3 | 添加分区支持（PartitionCount、PartitionSize） |
| PerfectHash | 4 | 添加 Perfect Hash（TocChunkPerfectHashSeedsCount） |
| PerfectHashWithOverflow | 5 | Perfect Hash 溢出支持（TocChunksWithoutPerfectHashCount） |
| OnDemandMetaData | 6 | 按需元数据（已废弃） |
| RemovedOnDemandMetaData | 7 | 移除按需元数据 |
| ReplaceIoChunkHashWithIoHash | 8 | 使用 FIoHash 替代 FIoChunkHash（BLAKE3-160） |

**源码定义：** `enum class EIoStoreTocVersion : uint8`，位于 `Runtime/Core/Internal/IO/IoStore.h`

**辅助常量：** `LatestPlusOne`、`Latest = LatestPlusOne - 1`

---

## FIoStoreTocHeader 字段表

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| TocMagic[16] | uint8[] | 魔数 "-==--==--==--==-" | 所有版本 |
| Version | uint8 | EIoStoreTocVersion 版本号 | 所有版本 |
| Reserved0 | uint8 | 保留（固定为 0） | 所有版本 |
| Reserved1 | uint16 | 保留（固定为 0） | 所有版本 |
| TocHeaderSize | uint32 | 头部大小（字节） | 所有版本 |
| TocEntryCount | uint32 | 数据块条目数量 | 所有版本 |
| TocCompressedBlockEntryCount | uint32 | 压缩块条目数量 | 所有版本 |
| TocCompressedBlockEntrySize | uint32 | 压缩块条目大小（用于校验） | 所有版本 |
| CompressionMethodNameCount | uint32 | 压缩方法数量 | 所有版本 |
| CompressionMethodNameLength | uint32 | 压缩方法名长度 | 所有版本 |
| CompressionBlockSize | uint32 | 压缩块大小 | 所有版本 |
| DirectoryIndexSize | uint32 | 目录索引大小 | Version 2+ |
| PartitionCount | uint32 | 分区数量 | Version 3+ |
| ContainerId | FIoContainerId | 容器 ID | 所有版本 |
| EncryptionKeyGuid | FGuid | 加密密钥 GUID | 所有版本 |
| ContainerFlags | EIoContainerFlags | 容器标志 | 所有版本 |
| Reserved3 | uint8 | 保留（固定为 0） | 所有版本 |
| Reserved4 | uint16 | 保留（固定为 0） | 所有版本 |
| TocChunkPerfectHashSeedsCount | uint32 | Perfect Hash 种子数量 | Version 4+ |
| PartitionSize | uint64 | 分区大小 | Version 3+ |
| TocChunksWithoutPerfectHashCount | uint32 | 无 Perfect Hash 条目数量 | Version 5+ |
| Reserved7 | uint32 | 保留（固定为 0） | 所有版本 |
| Reserved8[5] | uint64[] | 保留数组（固定为 0） | 所有版本 |

**源码定义：** `struct FIoStoreTocHeader`，位于 `Runtime/Core/Internal/IO/IoStore.h`

**注意：**
- 头部包含多个保留字段（Reserved0/1/3/4/7/8）用于对齐和未来扩展
- PartitionSize 字段位于 TocChunkPerfectHashSeedsCount 之后（Version 4+ 字段之间插入 Version 3+ 字段）
- 头部总大小由 `TocHeaderSize` 字段指定

---

## FIoOffsetAndLength 字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| OffsetAndLength[10] | uint8[] | 10 字节紧凑编码（5 字节偏移 + 5 字节长度） |

**编码说明：**
- 偏移：OffsetAndLength[0-4]，**大端序**，5 字节，可表示最大 1PB 偏移
- 长度：OffsetAndLength[5-9]，**大端序**，5 字节，可表示最大 1PB 长度

**解析方法：**
```
GetOffset() = OffsetAndLength[4]
            | (uint64(OffsetAndLength[3]) << 8)
            | (uint64(OffsetAndLength[2]) << 16)
            | (uint64(OffsetAndLength[1]) << 24)
            | (uint64(OffsetAndLength[0]) << 32)

GetLength() = OffsetAndLength[9]
            | (uint64(OffsetAndLength[8]) << 8)
            | (uint64(OffsetAndLength[7]) << 16)
            | (uint64(OffsetAndLength[6]) << 24)
            | (uint64(OffsetAndLength[5]) << 32)
```

**源码定义：** `struct FIoOffsetAndLength`，位于 `Runtime/Core/Internal/IO/IoOffsetLength.h`

---

## FIoStoreTocCompressedBlockEntry 字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Data[12] | uint8[] | 12 字节紧凑编码 |

**编码说明（位分布）：**
- Offset: 5 字节（位 0-39），数据块在 .ucas 文件中的偏移，最大约 1TB
- CompressedSize: 3 字节（位 40-63），压缩后大小，最大约 16MB
- UncompressedSize: 3 字节（位 64-87），原始大小，最大约 16MB
- CompressionMethodIndex: 1 字节（位 88-95），压缩方法索引

**解析方法：**
```
GetOffset():              读取 Data[0-4] 为 uint64，掩码 0xFFFFFFFFFF（40 位）
GetCompressedSize():      读取 Data[4-7] 为 uint32，右移 8 位，掩码 0xFFFFFF（24 位）
GetUncompressedSize():    读取 Data[8-11] 为 uint32，掩码 0xFFFFFF（24 位）
GetCompressionMethodIndex(): 读取 Data[8-11] 为 uint32，右移 24 位（取高 8 位）
```

**源码定义：** `struct FIoStoreTocCompressedBlockEntry`，位于 `Runtime/Core/Internal/IO/IoStore.h`

---

## FIoStoreTocEntryMeta 字段表

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| ChunkHash | FIoHash | 数据块哈希（BLAKE3-160，20 字节） | Version 8+ 使用 FIoHash |
| Flags | FIoStoreTocEntryMetaFlags | 标志（Compressed/MemoryMapped） | 所有版本 |
| Pad[3] | uint8[] | 对齐填充（24 字节对齐） | 所有版本 |

**源码定义：** `struct FIoStoreTocEntryMeta`，位于 `Runtime/Core/Internal/IO/IoStore.h`

**FIoStoreTocEntryMetaFlags 标志：**
- None = 0
- Compressed = 1 << 0 — 数据块已压缩
- MemoryMapped = 1 << 1 — 数据块可内存映射

**版本差异：**
- Version 7 及之前：使用 FIoChunkHash（类型已废弃）
- Version 8+：使用 FIoHash（BLAKE3-160，20 字节）
- 旧版本的元数据存储在 `LegacyChunkMetas` 数组中

---

## FIoChunkId 字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Id[12] | uint8[] | 12 字节标识符 |

**通用编码（CreateIoChunkId）：**
- Id[0-7]: uint64 ChunkId（通常是 FPackageId），小端序
- Id[8-9]: uint16 ChunkIndex（网络字节序/大端序）
- Id[10]: 未使用（仅 BulkData 类型使用）
- Id[11]: uint8 ChunkType（EIoChunkType）

**BulkData 特殊编码（CreateBulkDataIoChunkId）：**
- Id[0-7]: uint64 ChunkId（FPackageId），小端序
- Id[8-9]: uint16 ChunkIndex（网络字节序/大端序）
- Id[10]: uint8 ChunkGroup（FBulkDataCookedIndex，区分同一资产的不同 BulkData）
- Id[11]: uint8 ChunkType（EIoChunkType）

**获取类型：** `GetChunkType()` 返回 `static_cast<EIoChunkType>(Id[11])`

**源码定义：** `class FIoChunkId`，位于 `Runtime/Core/Public/IO/IoChunkId.h`

---

## EIoChunkType 数据块类型枚举

| 类型 | 值 | 说明 |
|------|-----|------|
| Invalid | 0 | 无效类型 |
| ExportBundleData | 1 | 导出包数据（主 .uasset 数据） |
| BulkData | 2 | BulkData 数据块 |
| OptionalBulkData | 3 | 可选 BulkData（如高清纹理） |
| MemoryMappedBulkData | 4 | 内存映射 BulkData |
| ScriptObjects | 5 | 脚本对象数据 |
| ContainerHeader | 6 | 容器头部 |
| ExternalFile | 7 | 外部文件 |
| ShaderCodeLibrary | 8 | Shader 代码库 |
| ShaderCode | 9 | Shader 代码 |
| PackageStoreEntry | 10 | Package Store 条目 |
| DerivedData | 11 | 派生数据 |
| EditorDerivedData | 12 | 编辑器派生数据 |
| PackageResource | 13 | Package 资源 |

**源码定义：** `enum class EIoChunkType : uint8`，位于 `Runtime/Core/Public/IO/IoChunkId.h`

**辅助函数：** `IsBulkDataType(type)` 判断是否为 BulkData/OptionalBulkData/MemoryMappedBulkData

---

## EIoContainerFlags 容器标志枚举

| 标志 | 值 | 说明 |
|------|-----|------|
| None | 0 | 无标志 |
| Compressed | 1 << 0 (1) | 容器使用压缩 |
| Encrypted | 1 << 1 (2) | 容器使用加密 |
| Signed | 1 << 2 (4) | 容器使用签名 |
| Indexed | 1 << 3 (8) | 容器包含目录索引 |
| OnDemand | 1 << 4 (16) | 按需加载容器 |

**源码定义：** `enum class EIoContainerFlags : uint8`，位于 `Runtime/Core/Public/IO/IoDispatcher.h`

**标志组合说明：**
- Compressed + Encrypted：数据先压缩后加密
- Signed：包含 SignatureHash 和 ChunkBlockSignatures，用于验证完整性
- Indexed：包含 DirectoryIndexBuffer，用于按路径查找文件

---

## DirectoryIndexBuffer 结构

**存储目录树结构，用于按路径查找文件。**

**解析接口：**
- `FIoDirectoryIndexReader` — 解析 DirectoryIndexBuffer
- 按路径查找：`FindFileEntry(FIoChunkId)` 返回 FIoOffsetAndLength

**加密说明：**
- 当 ContainerFlags 包含 Encrypted 时，DirectoryIndexBuffer 被加密
- 需要使用 EncryptionKeyGuid 对应的密钥解密后才能解析

---

## SignatureHash 机制

**签名验证数据：**
- SignatureHash: 整个 TOC 的签名哈希
- ChunkBlockSignatures: 每个压缩块的签名哈希数组

**用途：**
- 验证 TOC 数据完整性
- 验证每个数据块的完整性
- 防止数据篡改

**条件：**
- 仅当 ContainerFlags 包含 Signed 时存在

---

## FIoHash 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Hash[20] | uint8[] | BLAKE3-160 哈希值 |

**算法：** BLAKE3 哈希算法，截取前 20 字节（160 位）

**版本差异：**
- Version 7 及之前：使用 FIoChunkHash
- Version 8+：使用 FIoHash（BLAKE3-160），旧版本元数据存储在 LegacyChunkMetas 中

---

## FIoContainerId 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Id | uint64 | 容器唯一标识符 |

**生成方式：** 基于容器名称生成唯一 ID

**源码定义：** `struct FIoContainerId`，位于 `Runtime/Core/Public/IO/IoContainerId.h`

---

## 源码引用

| 结构 | 文件路径 |
|------|----------|
| FIoStoreTocHeader | Runtime/Core/Internal/IO/IoStore.h |
| FIoOffsetAndLength | Runtime/Core/Internal/IO/IoOffsetLength.h |
| FIoStoreTocCompressedBlockEntry | Runtime/Core/Internal/IO/IoStore.h |
| FIoStoreTocEntryMeta | Runtime/Core/Internal/IO/IoStore.h |
| FIoStoreTocResource | Runtime/Core/Internal/IO/IoStore.h |
| FIoChunkId | Runtime/Core/Public/IO/IoChunkId.h |
| EIoChunkType | Runtime/Core/Public/IO/IoChunkId.h |
| EIoContainerFlags | Runtime/Core/Public/IO/IoDispatcher.h |
| FIoContainerSettings | Runtime/Core/Public/IO/IoDispatcher.h |
| FIoHash | Runtime/Core/Public/IO/IoHash.h |
| FIoContainerId | Runtime/Core/Public/IO/IoContainerId.h |
| EIoStoreTocVersion | Runtime/Core/Internal/IO/IoStore.h |

---

## 版本差异

**Version 3+：**
- 添加 PartitionCount 和 PartitionSize 字段
- 支持分区，单个容器可跨多个 .ucas 文件

**Version 4+：**
- 添加 PerfectHash 机制
- 优化目录索引查询性能（O(1) 查询）

**Version 5+：**
- 添加 TocChunksWithoutPerfectHashCount
- 支持溢出条目，部分数据块不使用 Perfect Hash

**Version 8+：**
- 使用 FIoHash（BLAKE3-160）替代 FIoChunkHash
- 哈希算法统一为 BLAKE3
- 旧版本元数据通过 LegacyChunkMetas 存储

---

## IoStore 加载流程

1. **FIoStoreReader 初始化：** 读取 .utoc 文件
2. **解析 FIoStoreTocHeader：** 验证魔数和版本
3. **加载 ChunkId 和 OffsetLengths：** 构建数据块索引
4. **加载 DirectoryIndexBuffer：** 构建目录索引（可选解密）
5. **Perfect Hash 构建：** Version 4+ 使用 Perfect Hash 优化
6. **数据请求处理：** 通过 FIoChunkId 定位数据块
7. **解压/解密：** 根据 CompressionBlocks 和 Flags 处理

---

## 交叉引用

- Cooked vs Uncooked 对比见 [cooked/cooked-vs-uncooked.md](cooked-vs-uncooked.md)
- Pak 格式见 [cooked/pak.md](pak.md)
- 文件头结构见 [package-summary.md](../package-summary.md)
- 序列化机制见 [serialization/linker-load.md](../serialization/linker-load.md)
