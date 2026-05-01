# 文件头结构 (FPackageFileSummary)

## 概述

FPackageFileSummary 是 .uasset 文件的"目录"，位于文件开头。它包含文件版本、名称表位置、Import/Export 表位置、数据区位置等关键信息。文件魔数 PACKAGE_FILE_TAG = 0x9E2A83C1 用于验证文件类型，如果字节序交换则为 0xC1832A9E。

文件头作为索引表，指向文件中各个数据区的起始位置，加载器首先读取 FPackageFileSummary，再根据其中记录的偏移量定位各表数据。

## 字段表

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| Tag | int32 | 魔数验证，应为 PACKAGE_FILE_TAG (0x9E2A83C1) | — |
| FileVersionUE | FPackageFileVersion | UE 文件版本号，包含 UE4/UE5 双版本 | UE5.0 起改为双版本结构 |
| FileVersionLicenseeUE | int32 | 许可方自定义版本号 | — |
| PackageFlags | uint32 | 包标志位（如 PKG_FilterEditorOnly） | — |
| TotalHeaderSize | int32 | 文件头总大小（包含 Summary 和各表） | — |
| PackageName | FString | 包名称 | — |
| NameCount | int32 | 名称表条目数量 | — |
| NameOffset | int32 | 名称表在文件中的偏移 | — |
| NamesReferencedFromExportDataCount | int32 | 从导出数据引用的名称数量 | UE5 新增 |
| ExportCount | int32 | 导出表条目数量 | — |
| ExportOffset | int32 | 导出表在文件中的偏移 | — |
| ImportCount | int32 | 导入表条目数量 | — |
| ImportOffset | int32 | 导入表在文件中的偏移 | — |
| SoftObjectPathsCount | int32 | 软对象路径数量 | UE5 新增 |
| SoftObjectPathsOffset | int32 | 软对象路径偏移 | UE5 新增 |
| BulkDataStartOffset | int64 | BulkData 数据区起始位置 | — |
| PayloadTocOffset | int64 | Payload TOC 偏移（指向 PackageTrailer） | UE5 新增 |
| DataResourceOffset | int32 | 数据资源表偏移 | UE5 新增 |
| Generations | TArray<FGenerationInfo> | 版本世代信息（编辑器保存历史） | — |
| SavedByEngineVersion | FEngineVersion | 保存时的引擎版本 | — |
| SavedByEngineNetVersion | FEngineVersion | 保存时的网络版本 | UE5.4 新增 |
| CompressionFlags | uint32 | 压缩标志 | — |
| CompressedChunks | TArray<FCompressedChunk> | 压缩块信息（已弃用） | — |
| AssetRegistryDataOffset | int32 | 资产注册数据偏移 | — |
| ChunkIDs | TArray<FGuid> | Pak 文件 Chunk ID | UE5 PACKAGE_CHUNK_ID 版本 |
| SavedHash | FIoHash | 保存时的哈希值（用于 IAS） | UE5 改为 FIoHash（原 FGuid） |

## 源码引用

- Runtime/CoreUObject/Public/UObject/PackageFileSummary.h
- Runtime/Core/Public/UObject/ObjectVersion.h

## 版本差异

### UE5 新增字段
- **PayloadTocOffset**: PAYLOAD_TOC 版本新增，指向 PackageTrailer
- **DataResourceOffset**: DATA_RESOURCES 版本新增
- **NamesReferencedFromExportDataCount**: NAMES_REFERENCED_FROM_EXPORT_DATA 版本新增
- **SoftObjectPathsCount/Offset**: 软对象路径机制
- **SavedHash**: 从 FGuid 改为 FIoHash（PACKAGE_SAVED_HASH 版本）
- **ChunkIDs**: PACKAGE_CHUNK_ID 版本新增
- **SavedByEngineNetVersion**: UE5.4 新增网络版本记录

### 版本号结构变更
- UE5.0 起，FileVersionUE 从单一 int32 改为 FPackageFileVersion 结构
- 包含 UE4 版本号（EUnrealEngineObjectUE4Version）和 UE5 版本号（EUnrealEngineObjectUE5Version）
- 双版本号机制确保 UE4/UE5 资产互操作性

详见 [file-structure.md](file-structure.md) 整体结构概述。