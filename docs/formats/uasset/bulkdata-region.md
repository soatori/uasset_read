# 数据区结构

## 概述

数据区存储资产的大型二进制数据（如纹理像素、网格几何）。UE 提供三种数据存储方式：

- **BulkData**: 传统方式，数据可内联存储或存储在文件末尾/单独文件
- **PayloadTOC**: UE5 新增，通过 PackageTrailer 管理 Payload 数据
- **DataResource**: UE5 新增，数据资源表结构

PackageFileSummary 中的 BulkDataStartOffset（int64）、PayloadTocOffset（int64）、DataResourceOffset（int32）分别指定各数据区位置。

## BulkData 结构

### EBulkDataFlags 标志位

| 标志名 | 值 | 用途 |
|--------|-----|------|
| BULKDATA_None | 0 | 空标志 |
| BULKDATA_PayloadAtEndOfFile | 1 << 0 | 数据存储在文件末尾 |
| BULKDATA_SerializeCompressedZLIB | 1 << 1 | ZLIB 压缩 |
| BULKDATA_ForceSingleElementSerialization | 1 << 2 | 强制使用 SerializeElement 而非批量序列化 |
| BULKDATA_SingleUse | 1 << 3 | Lock/Unlock 后释放内存 |
| BULKDATA_Unused | 1 << 5 | 已废弃（5.3+） |
| BULKDATA_ForceInlinePayload | 1 << 6 | 强制内联存储 |
| BULKDATA_SerializeCompressed | = BULKDATA_SerializeCompressedZLIB | 压缩别名 |
| BULKDATA_ForceStreamPayload | 1 << 7 | 已废弃（5.3+） |
| BULKDATA_PayloadInSeparateFile | 1 << 8 | 数据存储在单独文件（.ubulk） |
| BULKDATA_SerializeCompressedBitWindow | 1 << 9 | 已废弃（5.3+） |
| BULKDATA_Force_NOT_InlinePayload | 1 << 10 | 强制非内联存储（Cook 时） |
| BULKDATA_OptionalPayload | 1 << 11 | 可选数据（.uptnl） |
| BULKDATA_MemoryMappedPayload | 1 << 12 | 内存映射文件（.m.ubulk） |
| BULKDATA_Size64Bit | 1 << 13 | 64位大小/偏移 |
| BULKDATA_DuplicateNonOptionalPayload | 1 << 14 | 复制非可选数据到 .ubulk 和 .uptnl |
| BULKDATA_BadDataVersion | 1 << 15 | 已废弃（5.3+） |
| BULKDATA_NoOffsetFixUp | 1 << 16 | 偏移值正确，无需修正 |
| BULKDATA_WorkspaceDomainPayload | 1 << 17 | 内部标志：负载存储在工作区文件 |
| BULKDATA_LazyLoadable | 1 << 18 | 内部标志：可随时从文件加载 |
| BULKDATA_AlwaysAllowDiscard | 1 << 28 | 运行时：允许丢弃（即使无法从磁盘加载） |
| BULKDATA_HasAsyncReadPending | 1 << 29 | 已废弃（5.5+） |
| BULKDATA_DataIsMemoryMapped | 1 << 30 | 运行时：数据为内存映射区域 |
| BULKDATA_UsesIoDispatcher | 1 << 31 | 运行时：使用 IoDispatcher 加载 |

**注意**：压缩格式（如 Oodle）通过 `StoreCompressedOnDisk(FName CompressionFormat)` 指定，使用 NAME_Oodle 等格式名，而非独立的标志位。源码中不存在 `BULKDATA_SerializeCompressedLZ4` 或 `BULKDATA_SerializeCompressedOodle` 标志。

### FBulkMetaData 结构

BulkMetaData 运行时紧凑存储在 16 字节，编辑器模式下 24 字节：

```
运行时 (16 字节):
[0 - 4]  [5 - 9]   [10]   [11]       [12 - 15]
[Size]   [Offset]  [未用]  [LockStatus] [BulkDataFlags]

编辑器 (24 字节):
[0 - 4]  [5 - 9]   [10]   [11]       [12 - 15]  [16 - 23]
[Size]   [Offset]  [未用]  [LockStatus] [BulkDataFlags] [SizeOnDisk]
```

| 字段 | 字节位置 | 类型 | 说明 |
|------|----------|------|------|
| Size | 0-4 | 40bit int | 数据大小（字节），最大 MaxSize = 0xFFffFFffFF |
| Offset | 5-9 | 40bit int | 文件偏移，最大 MaxOffset = 0xFFffFFffFE |
| LockStatus | 11 | uint8 | 锁定状态（EBulkDataLockStatus） |
| Flags | 12-15 | uint32 | EBulkDataFlags 组合 |
| SizeOnDisk | 16-23 | int64 | 磁盘上的实际大小（仅编辑器模式） |

**EBulkDataLockStatus 枚举**：
- LOCKSTATUS_Unlocked (0) — 未锁定
- LOCKSTATUS_ReadOnlyLock (1) — 只读锁定
- LOCKSTATUS_ReadWriteLock (2) — 读写锁定

**序列化格式**：运行时序列化 FBulkMetaResource 结构（包含 Flags、ElementCount、SizeOnDisk、Offset、DuplicateFlags、DuplicateSizeOnDisk、DuplicateOffset），然后转换为紧凑的 FBulkMetaData。

### FBulkData 类成员

| 成员 | 类型 | 可见性 | 说明 |
|------|------|--------|------|
| DataAllocation | FAllocatedPtr | private | 内部内存分配（原始数据或内存映射） |
| BulkMeta | FBulkMetaData | public | 紧凑元数据（大小、偏移、标志） |
| BulkChunkId | FIoChunkId | public | IoStore Chunk ID（默认 InvalidChunkId） |
| AttachedAr | FArchive* | protected | 关联的归档（仅 WITH_EDITOR） |
| Linker | FLinkerLoad* | protected | 链接器引用（仅 WITH_EDITOR） |
| CookedIndex | FBulkDataCookedIndex | protected | Cooked 索引（仅 WITH_EDITOR） |
| SerializeBulkDataElements | FSerializeBulkDataElements* | protected | 自定义序列化钩子（仅非运行时） |

### FBulkData 关键方法

| 方法 | 返回类型 | 用途 |
|------|----------|------|
| GetBulkDataSize() | int64 | 获取数据大小（字节） |
| GetBulkDataSizeOnDisk() | int64 | 获取磁盘上的大小（可能压缩） |
| GetBulkDataOffsetInFile() | int64 | 获取文件偏移 |
| GetBulkDataFlags() | uint32 | 获取标志位 |
| IsStoredCompressedOnDisk() | bool | 是否压缩存储 |
| IsBulkDataLoaded() | bool | 是否已加载到内存 |
| IsOptional() | bool | 是否为可选数据 |
| IsInlined() | bool | 是否内联存储 |
| IsInSeparateFile() | bool | 是否在单独文件中 |
| CanLoadFromDisk() | bool | 是否可从磁盘加载 |
| DoesExist() | bool | 引用的文件是否存在 |
| GetDecompressionFormat() | FName | 获取解压格式名 |
| Lock(uint32) | void* | 锁定数据，返回指针 |
| LockReadOnly() | const void* | 只读锁定（const 版本） |
| Unlock() | void | 解锁数据 |
| IsLocked() | bool | 是否已锁定 |
| IsUnlocked() | bool | 是否未锁定 |
| GetCopy(void**, bool) | void | 获取数据副本 |
| StoreCompressedOnDisk(FName) | void | 设置压缩格式 |
| UnloadBulkData() | bool | 卸载数据（仅编辑器） |
| ForceBulkDataResident() | void | 强制数据驻留内存 |
| OpenAsyncReadHandle() | IAsyncReadFileHandle* | 打开异步读取句柄 |
| StealFileMapping() | FOwnedBulkDataPtr* | 窃取文件映射所有权 |

## PayloadTOC 结构

### FLookupTableEntry 字段表

PayloadTOC 通过 PackageTrailer 的 PayloadLookupTable 管理，每个条目 49 字节：

| 字段名 | 类型 | 大小 | 用途 |
|--------|------|------|------|
| Identifier | FIoHash | 20 字节 | Payload 标识符（内容哈希） |
| OffsetInFile | int64 | 8 字节 | 文件偏移（虚拟化时为 INDEX_NONE） |
| CompressedSize | uint64 | 8 字节 | 压缩后大小（未压缩时等于 RawSize） |
| RawSize | uint64 | 8 字节 | 原始大小 |
| Flags | EPayloadFlags | 4 字节 | Payload 标志（当前仅 None） |
| FilterFlags | EPayloadFilterReason | - | 虚拟化过滤原因 |
| AccessMode | EPayloadAccessMode | 1 字节 | 存储访问模式 |

### EPayloadAccessMode 访问模式

| 模式 | 值 | 说明 |
|------|-----|------|
| Local | 0 | 存储在当前 PackageTrailer 的 Payload Data 段 |
| Referenced | 1 | 存储在工作区 Trailer（引用其他包），偏移为绝对偏移 |
| Virtualized | 2 | 存储在虚拟化后端（IVirtualizationSystem） |

### EPayloadStorageType 存储类型（用于过滤请求）

| 类型 | 说明 |
|------|------|
| Any | 所有负载 |
| Local | 本地存储的负载 |
| Referenced | 引用的负载 |
| Virtualized | 虚拟化的负载 |

### EPayloadStatus 负载状态

| 状态 | 说明 |
|------|------|
| NotFound | 未在 trailer 中注册 |
| StoredLocally | 存储在当前 trailer |
| StoredAsReference | 存储在工作区 trailer |
| StoredVirtualized | 已虚拟化 |

### EPayloadFlags 负载标志

| 标志 | 值 | 说明 |
|------|-----|------|
| None | 0 | 无标志 |

## DataResource 结构

### FObjectDataResource 字段表

**注意**：整个 FObjectDataResource 结构为 UE5 新增（DATA_RESOURCES 版本）。

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| Flags | EObjectDataResourceFlags | 资源标志 | UE5 新增 |
| CookedIndex | FBulkDataCookedIndex | Cooked 索引 | UE5 AddedCookedIndex 版本 |
| SerialOffset | int64 | 序列化偏移 | UE5 新增 |
| DuplicateSerialOffset | int64 | 重复数据的序列化偏移 | UE5 新增 |
| SerialSize | int64 | 序列化大小 | UE5 新增 |
| RawSize | int64 | 原始大小（未压缩） | UE5 新增 |
| OuterIndex | FPackageIndex | 所属对象引用 | UE5 新增 |
| LegacyBulkDataFlags | uint32 | 传统 BulkData 标志（兼容） | UE5 新增 |

### FObjectDataResource.EVersion 内部版本

| 版本 | 说明 |
|------|------|
| Invalid | 无效版本 |
| Initial | 初始版本 |
| AddedCookedIndex | 添加 CookedIndex 字段 |
| LatestPlusOne | 最新版本+1 |
| Latest | 最新版本 |

### EObjectDataResourceFlags 资源标志

| 标志名 | 值 | 说明 |
|--------|-----|------|
| None | 0 | 无标志 |
| Inline | 1 << 0 | 内联存储 |
| Streaming | 1 << 1 | 流式加载 |
| Optional | 1 << 2 | 可选数据 |
| Duplicate | 1 << 3 | 重复数据 |
| MemoryMapped | 1 << 4 | 内存映射 |
| DerivedDataReference | 1 << 5 | 派生数据引用 |

## FPackageTrailer 结构

### 整体布局

```
[Header]                    | 28 字节静态 + PayloadLookupTable
[Payload Data]              | FCompressedBuffer 数组
[Footer]                    | 20 字节
```

### FHeader 结构

| 字段 | 类型 | 大小 | 说明 |
|------|------|------|------|
| Tag | uint64 | 8 字节 | HeaderTag = 0xD1C43B2E80A5F697 |
| Version | int32 | 4 字节 | 格式版本（EPackageTrailerVersion） |
| HeaderLength | uint32 | 4 字节 | Header 总大小（字节） |
| PayloadsDataLength | uint64 | 8 字节 | Payload 数据总大小（字节） |
| NumPayloads | int32 | 4 字节 | PayloadLookupTable 条目数 |
| PayloadLookupTable | FLookupTableEntry[] | 49 × N 字节 | Payload 查找表 |

StaticHeaderSizeOnDisk = 28 字节（不含 PayloadLookupTable）

### FFooter 结构

| 字段 | 类型 | 大小 | 说明 |
|------|------|------|------|
| Tag | uint64 | 8 字节 | FooterTag = 0x29BFCA045138DE76 |
| TrailerLength | uint64 | 8 字节 | Trailer 总大小（字节），用于反向查找 |
| PackageTag | uint32 | 4 字节 | PACKAGE_FILE_TAG，用于验证文件完整性 |

SizeOnDisk = 20 字节

### FPackageTrailer 成员

| 成员 | 类型 | 说明 |
|------|------|------|
| TrailerPositionInFile | int64 | Trailer 在工作区文件中的位置 |
| Header | FHeader | Header 结构（含 PayloadLookupTable） |

**注意**：Footer 不保留在内存中，仅用于查找和验证。

## 源码引用

- Runtime/CoreUObject/Public/Serialization/BulkData.h — FBulkData、FBulkMetaData、EBulkDataFlags 定义
- Runtime/CoreUObject/Public/UObject/PackageTrailer.h — FPackageTrailer、FLookupTableEntry、EPayloadAccessMode 定义
- Runtime/CoreUObject/Public/UObject/ObjectResource.h — FObjectDataResource、EObjectDataResourceFlags、FPackageIndex 定义
- Runtime/CoreUObject/Public/UObject/PackageFileSummary.h — FPackageFileSummary 定义

## 版本差异

### UE5 新增
- **PayloadTocOffset**: PAYLOAD_TOC 版本新增，指向 PackageTrailer
- **DataResourceOffset**: DATA_RESOURCES 版本新增
- **FLookupTableEntry**: Payload 查找表机制（49 字节/条目）
- **FObjectDataResource**: 数据资源表结构（含 EVersion 内部版本控制）
- **BULKDATA_MemoryMappedPayload**: 内存映射标志扩展
- **BULKDATA_WorkspaceDomainPayload**: 工作区域负载标志
- **BULKDATA_LazyLoadable**: 可延迟加载标志
- **EPayloadAccessMode**: Local/Referenced/Virtualized 三种访问模式
- **EPayloadStorageType/EPayloadStatus**: 负载过滤和状态查询

### UE4 vs UE5
- UE4 主要使用 BulkData 机制（内联/末尾/单独文件）
- UE5 引入 PayloadTOC 和 DataResource，支持更灵活的数据管理
- Payload 虚拟化机制（IVirtualizationSystem）为 UE5 特性
- UE5 压缩推荐使用 Oodle（通过 FName 指定），而非独立标志位
- BULKDATA_Unused（1<<5）在 5.3 废弃
- BULKDATA_ForceStreamPayload（1<<7）在 5.3 废弃
- BULKDATA_SerializeCompressedBitWindow（1<<9）在 5.3 废弃
- BULKDATA_BadDataVersion（1<<15）在 5.3 废弃
- BULKDATA_HasAsyncReadPending（1<<29）在 5.5 废弃
- BULKDATA_PayloadInSeperateFile 拼写更正为 BULKDATA_PayloadInSeparateFile（5.7）

### 废弃标志

| 标志 | 状态 | 替代方案 |
|------|------|----------|
| BULKDATA_Unused | 5.3 废弃 | 假设所有 BulkData 可用 |
| BULKDATA_ForceStreamPayload | 5.3 废弃 | 已无实际用途 |
| BULKDATA_SerializeCompressedBitWindow | 5.3 废弃 | 已无实际用途 |
| BULKDATA_BadDataVersion | 5.3 废弃 | 已无实际用途 |
| BULKDATA_HasAsyncReadPending | 5.5 废弃 | 已无实际用途 |
| BULKDATA_PayloadInSeperateFile | 5.7 重命名 | 使用 BULKDATA_PayloadInSeparateFile |

### 版本判断

版本判断通过 Ar.UEVer() 检查 EUnrealEngineObjectUE5Version::PAYLOAD_TOC 支持 PayloadTOC 和 PackageTrailer，检查 EUnrealEngineObjectUE5Version::DATA_RESOURCES 支持 DataResource 表。

详见 [package-trailer.md](package-trailer.md) PackageTrailer 结构。
详见 [file-structure.md](file-structure.md) 整体结构概述。