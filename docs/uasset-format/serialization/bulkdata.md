# BulkData 运行时机制

## 概述

本文档覆盖 BulkData 的运行时机制，包括加载触发时机、压缩策略和内存管理。存储结构（FBulkMetaData、Flags、文件位置）已在 Phase 1 文档中覆盖。

### 与 Phase 1 分工

| Phase | 覆盖内容 | 文件 |
|-------|----------|------|
| Phase 1 | BulkData 存储结构（FBulkMetaData、Flags、文件位置） | [bulkdata-region.md](../bulkdata-region.md) |
| Phase 2 | BulkData 运行时机制（加载触发、压缩、内存管理） | 本文档 |

BulkData 采用按需加载策略：序列化时仅读取元数据（Flags、Offset、Size），实际数据加载延迟到 Lock() 调用时触发。这种设计减少内存占用，支持大型资产（纹理、网格等）的流式加载。

## 加载触发时机

BulkData 的加载分为三个阶段：

| 时机 | 操作 | 说明 |
|------|------|------|
| 序列化 FBulkMetaData | 读取元数据 | 仅读取 Flags、Offset、Size，不加载实际数据 |
| Lock() 调用 | 实际加载 | 触发数据从磁盘加载到内存 |
| Unlock() 调用 | 释放锁 | 释放数据访问权（数据可能仍在内存） |

### 序列化 FBulkMetaData

加载 .uasset 文件时，LinkerLoad 序列化 FBulkMetaData 结构：

1. 读取 Size（数据大小）
2. 读取 OffsetInFile（文件偏移）
3. 读取 Flags（标志位组合）

此时实际数据仍存储在磁盘，未加载到内存。详见 [serialization/linker-load.md](linker-load.md) 加载流程。

### Lock() 实际加载

当需要访问数据时，调用 Lock() 触发实际加载：

1. 检查是否已加载（IsBulkDataLoaded()）
2. 若未加载，从磁盘读取数据到内存
3. 若数据压缩，执行解压缩
4. 设置锁定状态（LOCKSTATUS_ReadOnlyLock 或 LOCKSTATUS_ReadWriteLock）
5. 返回数据指针

### Unlock() 释放锁

数据访问完成后，调用 Unlock() 释放锁定：

1. 清除锁定状态
2. 根据内存管理策略决定是否释放内存（SingleUse 标志）
3. 内存映射数据保持映射状态

### 关键方法

| 方法 | 用途 | 源码位置 |
|------|------|----------|
| Lock(uint32 LockFlags) | 锁定数据，返回指针 | BulkData.cpp |
| Unlock() | 解锁数据 | BulkData.cpp |
| MakeSureBulkDataIsLoaded() | 确保数据已加载 | BulkData.cpp |
| IsBulkDataLoaded() | 检查数据是否已加载 | BulkData.h |
| TryLoadDataIntoMemory(FIoBuffer Dest) | 从磁盘加载数据到指定内存 | BulkData.cpp |

## 压缩策略

BulkData 的压缩通过 `StoreCompressedOnDisk(FName CompressionFormat)` 方法设置压缩格式，而非直接使用标志位。`EBulkDataFlags` 中仅保留 `BULKDATA_SerializeCompressedZLIB` 作为通用压缩标志，实际压缩格式（如 Oodle）通过 `GetDecompressionFormat()` 在运行时从 Flags 推导。

### 压缩标志

| 标志 | 压缩格式 | 说明 |
|------|----------|------|
| BULKDATA_SerializeCompressedZLIB | ZLIB | 标准 ZLIB 压缩，通用性好 |
| BULKDATA_SerializeCompressed | (ZLIB) | 别名，等于 BULKDATA_SerializeCompressedZLIB |

### 压缩处理流程

1. **保存时**：调用 `StoreCompressedOnDisk(FName CompressionFormat)` 设置压缩格式（如 `NAME_None`、`NAME_Oodle`），压缩数据后写入文件
2. **加载时**：Lock() 时检测压缩标志，调用 `GetDecompressionFormat()` 获取压缩格式，调用对应解压器解压数据

### 压缩格式说明

- **ZLIB**: 最通用的压缩格式，所有平台支持，压缩率较高，解压速度中等
- **Oodle**: UE5 推荐格式，Cooked 资产默认使用，压缩率和解压速度均优秀，需要平台支持 Oodle 库
- **LZ4**: 旧版本资产可能使用，当前源码中已无专用标志位

## 内存管理

BulkData 提供多种内存管理策略，通过 EBulkDataFlags 标志位控制：

| 标志 | 位 | 策略 | 说明 |
|------|-----|------|------|
| BULKDATA_SingleUse | 1<<3 | 单次使用 | Unlock 后释放内存 |
| BULKDATA_MemoryMappedPayload | 1<<12 | 内存映射 | 使用文件映射而非 malloc |
| BULKDATA_DataIsMemoryMapped | 1<<30 | 运行时标记 | 表示当前数据是内存映射 |
| BULKDATA_UsesIoDispatcher | 1<<31 | IoDispatcher | 使用 IoDispatcher 加载而非文件路径 |
| BULKDATA_AlwaysAllowDiscard | 1<<28 | 允许丢弃 | 即使无法从磁盘加载也考虑丢弃 |

### 完整 EBulkDataFlags 标志列表

| 标志 | 位 | 说明 |
|------|-----|------|
| BULKDATA_None | 0 | 空标志 |
| BULKDATA_PayloadAtEndOfFile | 1<<0 | 数据存储在文件末尾 |
| BULKDATA_SerializeCompressedZLIB | 1<<1 | ZLIB 压缩 |
| BULKDATA_ForceSingleElementSerialization | 1<<2 | 强制逐元素序列化 |
| BULKDATA_SingleUse | 1<<3 | 单次使用后释放 |
| BULKDATA_Unused | 1<<5 | **已废弃 (UE5.3)** |
| BULKDATA_ForceInlinePayload | 1<<6 | 强制内联存储 |
| BULKDATA_ForceStreamPayload | 1<<7 | **已废弃 (UE5.3)** |
| BULKDATA_PayloadInSeparateFile | 1<<8 | 数据存储在独立文件（.ubulk/.uptnl/.m.ubulk） |
| BULKDATA_SerializeCompressedBitWindow | 1<<9 | **已废弃 (UE5.3)** |
| BULKDATA_Force_NOT_InlinePayload | 1<<10 | 强制非内联存储 |
| BULKDATA_OptionalPayload | 1<<11 | 可选载荷（存储在 .uptnl） |
| BULKDATA_MemoryMappedPayload | 1<<12 | 内存映射载荷（存储在 .m.ubulk） |
| BULKDATA_Size64Bit | 1<<13 | 大小和偏移使用 int64 序列化 |
| BULKDATA_DuplicateNonOptionalPayload | 1<<14 | 重复非可选载荷 |
| BULKDATA_BadDataVersion | 1<<15 | **已废弃 (UE5.3)** |
| BULKDATA_NoOffsetFixUp | 1<<16 | 偏移值正确，无需 Linker 修正 |
| BULKDATA_WorkspaceDomainPayload | 1<<17 | 工作域载荷（内部标志） |
| BULKDATA_LazyLoadable | 1<<18 | 可随时从文件加载 |
| BULKDATA_HasAsyncReadPending | 1<<29 | **已废弃 (UE5.5)** |
| BULKDATA_DataIsMemoryMapped | 1<<30 | 运行时：数据是内存映射 |
| BULKDATA_AlwaysAllowDiscard | 1<<28 | 运行时：始终允许丢弃 |
| BULKDATA_UsesIoDispatcher | 1<<31 | 运行时：使用 IoDispatcher |

### 单次使用（SingleUse）

适用于只访问一次的数据：

- Lock() 时加载数据到内存
- Unlock() 时立即释放内存
- 减少内存占用
- 适合纹理 mip 级别、临时网格数据

### 内存映射（MemoryMappedPayload）

适用于频繁访问的大型数据：

- 使用操作系统文件映射机制
- 数据不复制到堆内存
- 支持流式加载
- 对应 `.m.ubulk` 文件

### 内存映射运行时标记（DataIsMemoryMapped）

运行时状态标记：

- 表示当前数据实际是内存映射
- 由系统自动设置
- 用于优化内存访问

### 内存管理策略选择

| 场景 | 推荐策略 | 原因 |
|------|----------|------|
| 纹理像素数据 | MemoryMappedPayload | 大型数据，频繁访问 |
| 网格顶点数据 | MemoryMappedPayload | 大型数据，GPU 访问 |
| 临时处理数据 | SingleUse | 使用后立即释放 |
| 小型数据 | 默认（malloc） | 内存映射开销不划算 |

## FBulkMetaData 结构

FBulkMetaData 是 BulkData 的序列化元数据，大小 16 字节（运行时）或 24 字节（编辑器）：

| 字节偏移 | 内容 | 大小 |
|----------|------|------|
| 0-4 | Size（最大 40 位） | 5 字节 |
| 5-9 | Offset（最大 39 位 + 1 位 INDEX_NONE 标识） | 5 字节 |
| 10 | 未使用 | 1 字节 |
| 11 | LockStatus（EBulkDataLockStatus） | 1 字节 |
| 12-15 | Flags（EBulkDataFlags） | 4 字节 |
| 16-23 | SizeOnDisk（仅编辑器模式） | 8 字节 |

### FBulkMetaResource（序列化结构）

| 字段 | 类型 | 说明 |
|------|------|------|
| Flags | EBulkDataFlags | BulkData 标志 |
| ElementCount | int64 | 元素数量 |
| SizeOnDisk | int64 | 磁盘大小（压缩后可能不同） |
| Offset | int64 | 在 BulkData 块中的偏移 |
| DuplicateFlags | EBulkDataFlags | 重复数据的标志 |
| DuplicateSizeOnDisk | int64 | 重复数据的磁盘大小 |
| DuplicateOffset | int64 | 重复数据的偏移 |

## 源码引用

### 关键源码文件

| 文件 | 路径 | 说明 |
|------|------|------|
| BulkData.h | Runtime/CoreUObject/Public/Serialization/BulkData.h | BulkData 结构定义 |
| BulkData.cpp | Runtime/CoreUObject/Private/Serialization/BulkData.cpp | BulkData 实现细节 |

### 关键方法

| 方法 | 文件 | 用途 |
|------|------|------|
| Lock(uint32) | BulkData.cpp | 锁定数据，返回指针，触发按需加载 |
| Unlock() | BulkData.cpp | 解锁数据，可能释放内存 |
| MakeSureBulkDataIsLoaded() | BulkData.cpp | 确保数据已加载到内存 |
| IsBulkDataLoaded() | BulkData.h | 检查数据是否已在内存 |
| TryLoadDataIntoMemory(FIoBuffer) | BulkData.cpp | 从磁盘加载数据到指定内存 |
| StoreCompressedOnDisk(FName) | BulkData.cpp | 设置磁盘压缩格式 |
| GetDecompressionFormat() | BulkData.cpp | 获取解压格式 |
| Serialize(FArchive&, UObject*, ...) | BulkData.cpp | 序列化 BulkData |

### 相关文档

- [bulkdata-region.md](../bulkdata-region.md) — Phase 1 BulkData 存储结构
- [serialization/linker-load.md](linker-load.md) — 加载流程（Lock 调用）
- [serialization/linker-save.md](linker-save.md) — 保存流程（BulkData 序列化）

## 版本差异

### UE5 新增特性

| 特性 | 说明 |
|------|------|
| PayloadTOC 支持 | 大数据分离存储，通过 PackageTrailer 管理（PAYLOAD_TOC 版本） |
| Oodle 压缩优化 | Cooked 资产默认使用 Oodle 压缩 |
| 内存映射优化 | 新增内存映射相关标志优化 |
| DataResource 表 | 数据资源表支持（DATA_RESOURCES 版本） |
| IoDispatcher 支持 | BULKDATA_UsesIoDispatcher 运行时标志 |
| 可选载荷 | BULKDATA_OptionalPayload（.uptnl 文件） |
| 重复非可选载荷 | BULKDATA_DuplicateNonOptionalPayload |
| FBulkMetaResource 扩展 | 新增 ElementCount、DuplicateFlags、DuplicateSizeOnDisk、DuplicateOffset 字段 |

### UE4 vs UE5

| 特性 | UE4 | UE5 |
|------|-----|-----|
| 主要存储方式 | BulkData（内联/末尾/单独文件） | BulkData + PayloadTOC + DataResource |
| 推荐压缩格式 | ZLIB | Oodle |
| 内存映射 | 基本支持 | 优化标志扩展 |
| Payload 虚拟化 | 无 | IAS（Install Analysis Service）支持 |
| IoDispatcher | 无 | 支持（BULKDATA_UsesIoDispatcher） |

### 废弃标志

| 标志 | 状态 | 替代方案 |
|------|------|----------|
| BULKDATA_Unused | UE5.3 废弃 | 假设所有 BulkData 可用 |
| BULKDATA_ForceStreamPayload | UE5.3 废弃 | 已无实际用途 |
| BULKDATA_SerializeCompressedBitWindow | UE5.3 废弃 | 已无实际用途 |
| BULKDATA_BadDataVersion | UE5.3 废弃 | 已无实际用途 |
| BULKDATA_HasAsyncReadPending | UE5.5 废弃 | StartAsyncLoading 已移除 |

### 版本判断

版本判断通过 Ar.UEVer() 检查 EUnrealEngineObjectUE5Version::PAYLOAD_TOC 支持 PayloadTOC 和 PackageTrailer，检查 EUnrealEngineObjectUE5Version::DATA_RESOURCES 支持 DataResource 表。

详见 [serialization/version-compatibility.md](version-compatibility.md) 版本兼容机制。
