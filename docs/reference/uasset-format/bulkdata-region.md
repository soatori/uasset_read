# 数据区结构

## 概述

数据区存储资产的大型二进制数据（如纹理像素、网格几何）。UE 提供三种数据存储方式：

- **BulkData**: 传统方式，数据可内联存储或存储在文件末尾/单独文件
- **PayloadTOC**: UE5 新增，通过 PackageTrailer 管理 Payload 数据
- **DataResource**: UE5 新增，数据资源表结构

PackageFileSummary 中的 BulkDataStartOffset、PayloadTocOffset、DataResourceOffset 分别指定各数据区位置。

## BulkData 结构

### EBulkDataFlags 标志位

| 标志名 | 用途 |
|--------|------|
| BULKDATA_PayloadAtEndOfFile | 数据存储在文件末尾 |
| BULKDATA_PayloadInSeparateFile | 数据存储在单独文件（.ubulk） |
| BULKDATA_OptionalPayload | 可选数据（.uptnl） |
| BULKDATA_MemoryMappedPayload | 内存映射文件（.m.ubulk） |
| BULKDATA_SerializeCompressedZLIB | ZLIB 压缩 |
| BULKDATA_SerializeCompressedLZ4 | LZ4 压缩 |
| BULKDATA_ForceInlinePayload | 强制内联存储 |
| BULKDATA_Size64Bit | 64位大小/偏移 |
| BULKDATA_DuplicateNonOptionalPayload | 复制非可选数据 |

### FBulkMetaData 结构

BulkMetaData 紧凑存储在 16 字节中：
- Size: 数据大小（压缩后）
- OffsetInFile: 文件偏移
- Flags: EBulkDataFlags 组合

### FBulkData 关键方法

| 方法 | 用途 |
|------|------|
| GetBulkDataSize() | 获取数据大小 |
| GetBulkDataOffsetInFile() | 获取文件偏移 |
| Lock() | 锁定数据，返回指针 |
| Unlock() | 解锁数据 |

## PayloadTOC 结构

### FLookupTableEntry 字段表

PayloadTOC 通过 PackageTrailer 的 PayloadLookupTable 管理：

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Identifier | FIoHash | Payload 标识符（内容哈希） |
| OffsetInFile | int64 | 文件偏移 |
| CompressedSize | uint64 | 压缩后大小 |
| RawSize | uint64 | 原始大小 |
| Flags | uint32 | Payload 标志 |
| FilterFlags | uint8 | 过滤标志 |

### EPayloadAccessMode 访问模式

| 模式 | 说明 |
|------|------|
| Local | 存储在当前 PackageTrailer |
| Referenced | 存储在工作区 Trailer（引用其他包） |
| Virtualized | 存储在虚拟化后端（IAS） |

## DataResource 结构

### FObjectDataResource 字段表

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| Flags | EObjectDataResourceFlags | 资源标志 | UE5 新增 |
| CookedIndex | FBulkDataCookedIndex | Cooked 索引 | UE5 新增 |
| SerialOffset | int64 | 序列化偏移 | — |
| SerialSize | int64 | 序列化大小 | — |
| RawSize | int64 | 原始大小 | — |
| OuterIndex | FPackageIndex | 所属对象引用 | — |
| LegacyBulkDataFlags | uint32 | 传统 BulkData 标志（兼容） | — |

### EObjectDataResourceFlags 资源标志

| 标志名 | 说明 |
|--------|------|
| Inline | 内联存储 |
| Streaming | 流式加载 |
| Optional | 可选数据 |
| MemoryMapped | 内存映射 |
| DerivedDataReference | 派生数据引用 |

## 源码引用

- Runtime/CoreUObject/Public/Serialization/BulkData.h
- Runtime/CoreUObject/Public/UObject/PackageTrailer.h
- Runtime/CoreUObject/Public/UObject/ObjectResource.h
- Runtime/CoreUObject/Public/UObject/PackageFileSummary.h

## 版本差异

### UE5 新增
- **PayloadTocOffset**: PAYLOAD_TOC 版本新增，指向 PackageTrailer
- **DataResourceOffset**: DATA_RESOURCES 版本新增
- **FLookupTableEntry**: Payload 查找表机制
- **FObjectDataResource**: 数据资源表结构
- **BULKDATA_MemoryMappedPayload**: 内存映射标志扩展

### UE4 vs UE5
- UE4 主要使用 BulkData 机制（内联/末尾/单独文件）
- UE5 引入 PayloadTOC 和 DataResource，支持更灵活的数据管理
- Payload 虚拟化机制（IAS）为 UE5 特性

详见 [package-trailer.md](package-trailer.md) PackageTrailer 结构。
详见 [file-structure.md](file-structure.md) 整体结构概述。