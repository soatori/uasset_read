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
[FIoStoreTocHeader]           — 头部（魔数、版本、条目数量等）
[FIoChunkId 数组]             — 数据块标识列表（TocEntryCount 个）
[FIoOffsetAndLength 数组]     — 偏移和长度列表（TocEntryCount 个）
[FIoStoreTocCompressedBlockEntry 数组] — 压缩块条目（TocCompressedBlockEntryCount 个）
[CompressionMethods 数组]     — 压缩方法名称（CompressionMethodNameCount 个）
[DirectoryIndexBuffer]        — 目录索引数据（可选加密，DirectoryIndexSize 字节）
[TocChunkPerfectHashSeeds]    — Perfect Hash 种子（Version 4+）
[TocChunksWithoutPerfectHash] — 无 Perfect Hash 条目（Version 5+）
[FIoStoreTocEntryMeta 数组]   — 条目元数据（哈希、标志）
[SignatureHash]               — 签名哈希（Signed 标志时存在）
[ChunkBlockSignatures]        — 块签名数组（Signed 标志时存在）
```

### .ucas 文件结构

```
[压缩数据块1]                  — 按 FIoStoreTocCompressedBlockEntry 定位
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

---

## FIoStoreTocHeader 字段表

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| TocMagic[16] | uint8[] | 魔数 "-==--==--==--==-" | 所有版本 |
| Version | uint8 | EIoStoreTocVersion 版本号 | 所有版本 |
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
| TocChunkPerfectHashSeedsCount | uint32 | Perfect Hash 种子数量 | Version 4+ |
| PartitionSize | uint64 | 分区大小 | Version 3+ |
| TocChunksWithoutPerfectHashCount | uint32 | 无 Perfect Hash 条目数量 | Version 5+ |

---

## FIoOffsetAndLength 字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| OffsetAndLength[10] | uint8[] | 10 字节紧凑编码 |

**编码说明：**
- 偏移：OffsetAndLength[0-4]，大端序，5 字节，可表示最大 1PB 偏移
- 长度：OffsetAndLength[5-9]，大端序，5 字节，可表示最大 1PB 长度

**解析方法：** GetOffset() 从 OffsetAndLength[0-4] 提取偏移，GetLength() 从 OffsetAndLength[5-9] 提取长度。

---

## FIoStoreTocCompressedBlockEntry 字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Data[12] | uint8[] | 12 字节紧凑编码 |

**编码说明（位分布）：**
- Offset: 5 字节（位 0-39），数据块在 .ucas 文件中的偏移
- CompressedSize: 3 字节（位 40-63），压缩后大小
- UncompressedSize: 3 字节（位 64-87），原始大小
- CompressionMethodIndex: 1 字节（位 88-95），压缩方法索引

**解析方法：** GetOffset() 从 Data[0-4] 提取偏移，GetCompressedSize() 从 Data[5-7] 提取压缩大小，GetUncompressedSize() 从 Data[8-10] 提取原始大小，GetCompressionMethodIndex() 从 Data[11] 提取压缩方法索引。

---

## FIoStoreTocEntryMeta 字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| ChunkHash | FIoHash | 数据块哈希（BLAKE3-160，20 字节） |
| Flags | FIoStoreTocEntryMetaFlags | 标志（Compressed/MemoryMapped） |
| Pad[3] | uint8[] | 对齐填充 |

**FIoStoreTocEntryMetaFlags 标志：**
- None = 0
- Compressed = 1 << 0 — 数据块已压缩
- MemoryMapped = 1 << 1 — 数据块可内存映射

---

## FIoChunkId 字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Id[12] | uint8[] | 12 字节标识符 |

**通用编码说明：**
- Id[0-7]: uint64 ChunkId（通常是 FPackageId）
- Id[8-9]: uint16 ChunkIndex（网络字节序）
- Id[10]: uint8 ChunkGroup（仅 BulkData 类型使用）
- Id[11]: uint8 ChunkType（EIoChunkType）

**BulkData 特殊编码：**
- ChunkId: FPackageId
- ChunkIndex: BulkData 索引
- ChunkGroup: 0-255，用于区分同一资产的不同 BulkData
- ChunkType: EIoChunkType::BulkData (2)

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

---

## EIoContainerFlags 容器标志枚举

| 标志 | 值 | 说明 |
|------|-----|------|
| Compressed | 1 << 0 | 容器使用压缩 |
| Encrypted | 1 << 1 | 容器使用加密 |
| Signed | 1 << 2 | 容器使用签名 |
| Indexed | 1 << 3 | 容器包含目录索引 |
| OnDemand | 1 << 4 | 按需加载容器 |

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
- Version 8+：使用 FIoHash（BLAKE3-160）

---

## FIoContainerId 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Id | uint64 | 容器唯一标识符 |

**生成方式：** 基于容器名称生成唯一 ID

---

## 源码引用

| 结构 | 文件路径 |
|------|----------|
| FIoStoreTocHeader | Runtime/Core/Internal/IO/IoStore.h |
| FIoOffsetAndLength | Runtime/Core/Internal/IO/IoOffsetLength.h |
| FIoStoreTocCompressedBlockEntry | Runtime/Core/Internal/IO/IoStore.h |
| FIoStoreTocEntryMeta | Runtime/Core/Internal/IO/IoStore.h |
| FIoChunkId | Runtime/Core/Public/IO/IoChunkId.h |
| EIoChunkType | Runtime/Core/Public/IO/IoChunkId.h |
| EIoContainerFlags | Runtime/Core/Public/IO/IoDispatcher.h |
| FIoHash | Runtime/Core/Public/IO/IoHash.h |
| FIoContainerId | Runtime/Core/Public/IO/IoContainerId.h |
| FIoStoreReader | Runtime/Core/Public/IO/IoDispatcher.h |
| FIoDirectoryIndexReader | Runtime/Core/Private/IO/IoDirectoryIndexReader.h |

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