# 文件头结构 (FPackageFileSummary)

## 概述

FPackageFileSummary 是 .uasset 文件的"目录"，位于文件开头。它包含文件版本、名称表位置、Import/Export 表位置、数据区位置等关键信息。文件魔数 PACKAGE_FILE_TAG = 0x9E2A83C1 用于验证文件类型，如果字节序交换则为 0xC1832A9E。

文件头作为索引表，指向文件中各个数据区的起始位置，加载器首先读取 FPackageFileSummary，再根据其中记录的偏移量定位各表数据。

## 字段表

以下是 FPackageFileSummary **结构体成员**，按序列化顺序排列。标注条件的字段仅在满足版本/标志条件时才出现在文件中。

### 版本与元信息

| 字段名 | 类型 | 用途 | 版本条件 |
|--------|------|------|----------|
| Tag | int32 | 魔数验证，应为 PACKAGE_FILE_TAG (0x9E2A83C1) | 固定 |
| LegacyFileVersion | int32 | 序列化格式标识：-8 表示 UE5，-9 表示 UE5.6+ 新格式 | 固定（序列化用，非结构体成员） |
| LegacyUE3Version | int32 | 遗留 UE3 版本号，固定写入 864 | LegacyFileVersion != -4 |
| FileVersionUE4 | int32 | UE4 文件版本号（EUnrealEngineObjectUE4Version） | 固定 |
| FileVersionUE5 | int32 | UE5 文件版本号（EUnrealEngineObjectUE5Version），初始值 1000 | LegacyFileVersion <= -8 |
| FileVersionLicenseeUE | int32 | 许可方自定义版本号 | 固定 |
| SavedHash | FIoHash (20 bytes) | 保存时的包哈希值（SHA-1），用于 IoStore/IAS 验证 | UE5 >= PACKAGE_SAVED_HASH (1017)；旧版写 FGuid (16 bytes) |
| TotalHeaderSize | int32 | 文件头总大小（包含 Summary 和各表），供 LinkerLoad 确定读取范围 | UE5 >= PACKAGE_SAVED_HASH 时在 SavedHash 之后；否则在 CustomVersion 之后 |
| CustomVersionContainer | FCustomVersionContainer | 自定义版本容器，格式取决于 LegacyFileVersion | LegacyFileVersion <= -2 |

### 包标识与标志

| 字段名 | 类型 | 用途 | 版本条件 |
|--------|------|------|----------|
| PackageName | FString | 包名称（int32 Length + UTF-8 字节） | 固定 |
| PackageFlags | uint32 | 包标志位（如 PKG_FilterEditorOnly、PKG_Cooked） | 固定 |
| bUnversioned | bool | 是否为无版本标记的包（仅用于 full cooks 分发） | 固定（结构体成员，非序列化字段） |

### 名称表

| 字段名 | 类型 | 用途 | 版本条件 |
|--------|------|------|----------|
| NameCount | int32 | 名称表条目数量 | 固定 |
| NameOffset | int32 | 名称表在文件中的偏移 | 固定 |
| NamesReferencedFromExportDataCount | int32 | 从导出数据引用的名称数量（排序在名称表前端） | UE5 >= NAMES_REFERENCED_FROM_EXPORT_DATA (1001) |

### 软对象路径

| 字段名 | 类型 | 用途 | 版本条件 |
|--------|------|------|----------|
| SoftObjectPathsCount | int32 | 软对象路径数量 | UE5 >= ADD_SOFTOBJECTPATH_LIST (1009) |
| SoftObjectPathsOffset | int32 | 软对象路径在文件中的偏移 | UE5 >= ADD_SOFTOBJECTPATH_LIST (1009) |

### 本地化与文本

| 字段名 | 类型 | 用途 | 版本条件 |
|--------|------|------|----------|
| LocalizationId | FString | 本地化 ID（仅非 FilterEditorOnly 模式） | UE4 >= VER_UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID |
| GatherableTextDataCount | int32 | 可收集文本数据条目数量 | UE4 >= VER_UE4_SERIALIZE_TEXT_IN_PACKAGES (517) |
| GatherableTextDataOffset | int32 | 可收集文本数据在文件中的偏移 | UE4 >= VER_UE4_SERIALIZE_TEXT_IN_PACKAGES (517) |

### Import / Export 表

| 字段名 | 类型 | 用途 | 版本条件 |
|--------|------|------|----------|
| ExportCount | int32 | 导出表条目数量 | 固定 |
| ExportOffset | int32 | 导出表在文件中的偏移 | 固定 |
| ImportCount | int32 | 导入表条目数量 | 固定 |
| ImportOffset | int32 | 导入表在文件中的偏移 | 固定 |

### Cell 导入/导出（Verse）

| 字段名 | 类型 | 用途 | 版本条件 |
|--------|------|------|----------|
| CellExportCount | int32 | Cell 导出数量 | UE5 >= VERSE_CELLS (1015) |
| CellExportOffset | int32 | Cell 导出表偏移 | UE5 >= VERSE_CELLS (1015) |
| CellImportCount | int32 | Cell 导入数量 | UE5 >= VERSE_CELLS (1015) |
| CellImportOffset | int32 | Cell 导入表偏移 | UE5 >= VERSE_CELLS (1015) |

### 元数据与依赖

| 字段名 | 类型 | 用途 | 版本条件 |
|--------|------|------|----------|
| MetaDataOffset | int32 | 元数据在文件中的偏移 | UE5 >= METADATA_SERIALIZATION_OFFSET (1014) |
| DependsOffset | int32 | 依赖映射表在文件中的偏移 | 固定 |
| SoftPackageReferencesCount | int32 | 软包引用数量 | UE4 >= VER_UE4_ADD_STRING_ASSET_REFERENCES_MAP (516) |
| SoftPackageReferencesOffset | int32 | 软包引用表偏移 | UE4 >= VER_UE4_ADD_STRING_ASSET_REFERENCES_MAP (516) |
| SearchableNamesOffset | int32 | 可搜索名称映射表偏移 | UE4 >= VER_UE4_ADDED_SEARCHABLE_NAMES (518) |
| ThumbnailTableOffset | int32 | 缩略图表偏移 | 固定 |

### 类型层级

| 字段名 | 类型 | 用途 | 版本条件 |
|--------|------|------|----------|
| ImportTypeHierarchiesCount | int32 | 导入类型层级条目数量 | UE5 >= IMPORT_TYPE_HIERARCHIES (1018) |
| ImportTypeHierarchiesOffset | int32 | 导入类型层级映射表偏移 | UE5 >= IMPORT_TYPE_HIERARCHIES (1018) |

### GUID 与版本信息

| 字段名 | 类型 | 用途 | 版本条件 |
|--------|------|------|----------|
| LegacyGuid | FGuid (16 bytes) | 旧版包 GUID（PACKAGE_SAVED_HASH 之前使用） | UE5 < PACKAGE_SAVED_HASH (1017) |
| PersistentGuid | FGuid | 当前包的持久标识（仅非 FilterEditorOnly 模式） | WITH_EDITORONLY_DATA 且 UE4 >= VER_UE4_ADDED_PACKAGE_OWNER (519) |
| OwnerPersistentGuid | FGuid | 包所有者持久标识（已废弃，仅特定版本范围存在） | WITH_EDITORONLY_DATA 且 VER_UE4_ADDED_PACKAGE_OWNER <= UE4 < VER_UE4_NON_OUTER_PACKAGE_IMPORT |
| Generations | TArray<FGenerationInfo> | 版本世代信息（编辑器保存历史），每个元素为 (int32 ExportCount, int32 NameCount) | 固定 |
| SavedByEngineVersion | FEngineVersion | 保存时的引擎版本（uint16 Major, uint16 Minor, uint16 Patch, uint32 Changelist, FString Branch） | UE4 >= VER_UE4_ENGINE_VERSION_OBJECT (522) |
| CompatibleWithEngineVersion | FEngineVersion | 兼容的引擎版本 | UE4 >= VER_UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION (519) |

### 压缩与源信息

| 字段名 | 类型 | 用途 | 版本条件 |
|--------|------|------|----------|
| CompressionFlags | uint32 | 压缩标志（Zlib、Gzip 等） | 固定 |
| CompressedChunks | TArray<FCompressedChunk> | 压缩块信息，每个元素为 (int32 UncompressedOffset, int32 UncompressedSize, int32 CompressedOffset, int32 CompressedSize) | 固定序列化（通常 Count=0，非零则拒绝加载） |
| PackageSource | uint32 | 包来源标识（区分 Epic/被许可方/Modder） | 固定 |
| AdditionalPackagesToCook | TArray<FString> | 额外需要 cook 的包列表（已废弃，始终 Count=0） | 固定序列化 |

### 数据区偏移

| 字段名 | 类型 | 用途 | 版本条件 |
|--------|------|------|----------|
| AssetRegistryDataOffset | int32 | 资产注册数据偏移 | 固定 |
| BulkDataStartOffset | int64 | BulkData 数据区起始位置 | 固定 |
| WorldTileInfoDataOffset | int32 | World Tile Info 数据偏移 | UE4 >= VER_UE4_WORLD_LEVEL_INFO |
| ChunkIDs | TArray&lt;int32&gt; | 流式安装 Chunk ID 数组 | UE4 >= VER_UE4_CHANGED_CHUNKID_TO_BE_AN_ARRAY_OF_CHUNKIDS |
| PreloadDependencyCount | int32 | 预加载依赖数量 | UE4 >= VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS |
| PreloadDependencyOffset | int32 | 预加载依赖数据偏移 | UE4 >= VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS |
| PayloadTocOffset | int64 | Payload TOC 偏移（指向 PackageTrailer） | UE5 >= PAYLOAD_TOC (1002) |
| DataResourceOffset | int32 | 数据资源表偏移 | UE5 >= DATA_RESOURCES (1009) |

## 源码引用

- `Runtime/CoreUObject/Public/UObject/PackageFileSummary.h` — 结构体定义（56 行起）
- `Runtime/CoreUObject/Private/UObject/PackageFileSummary.cpp` — 序列化实现（`operator<<`）
- `Runtime/Core/Public/UObject/ObjectVersion.h` — `EUnrealEngineObjectUE4Version`、`EUnrealEngineObjectUE5Version`、`FPackageFileVersion` 定义
- `Runtime/CoreUObject/Public/UObject/Linker.h` — `FCompressedChunk` 定义（44 行起）
- `Runtime/CoreUObject/Public/UObject/ObjectResource.h` — `FObjectExport`、`FObjectImport`、`FPackageIndex` 定义

## 版本差异

### UE5 版本枚举（EUnrealEngineObjectUE5Version）

| 枚举值 | 整数值 | 新增字段 |
|--------|--------|----------|
| INITIAL_VERSION | 1000 | — |
| NAMES_REFERENCED_FROM_EXPORT_DATA | 1001 | NamesReferencedFromExportDataCount |
| PAYLOAD_TOC | 1002 | PayloadTocOffset |
| OPTIONAL_RESOURCES | 1003 | — |
| LARGE_WORLD_COORDINATES | 1004 | — |
| REMOVE_OBJECT_EXPORT_PACKAGE_GUID | 1005 | — |
| TRACK_OBJECT_EXPORT_IS_INHERITED | 1006 | — |
| FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES | 1007 | — |
| ADD_SOFTOBJECTPATH_LIST | 1008 | SoftObjectPathsCount/Offset |
| DATA_RESOURCES | 1009 | DataResourceOffset |
| SCRIPT_SERIALIZATION_OFFSET | 1010 | — |
| PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION | 1011 | — |
| PROPERTY_TAG_COMPLETE_TYPE_NAME | 1012 | — |
| ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES | 1013 | — |
| METADATA_SERIALIZATION_OFFSET | 1014 | MetaDataOffset |
| VERSE_CELLS | 1015 | CellExportCount/Offset, CellImportCount/Offset |
| PACKAGE_SAVED_HASH | 1016 | SavedHash 位置变更（从 FGuid 改为 FIoHash），TotalHeaderSize 位置变更 |
| OS_SUB_OBJECT_SHADOW_SERIALIZATION | 1017 | — |
| IMPORT_TYPE_HIERARCHIES | 1018 | ImportTypeHierarchiesCount/Offset |

### 版本号结构变更

- UE5.0 起，FileVersionUE 从单一 int32 改为 FPackageFileVersion 结构（ObjectVersion.h:761）
- 包含两个独立 int32：`FileVersionUE4`（EUnrealEngineObjectUE4Version）和 `FileVersionUE5`（EUnrealEngineObjectUE5Version）
- 序列化顺序：先写 FileVersionUE4，再写 FileVersionUE5
- 版本比较通过 `FPackageFileVersion::operator>=()` 重载实现，根据比较目标的类型选择对应字段

### LegacyFileVersion 语义

序列化中 Tag 之后的 int32 为 LegacyFileVersion，标识文件格式世代：

| LegacyFileVersion | 含义 |
|-------------------|------|
| -2 | 枚举格式自定义版本 |
| -3 ~ -5 | GUID 格式自定义版本 |
| -6 | 优化的自定义版本序列化 |
| -7 | 移除纹理分配信息 |
| -8 | 添加 UE5 版本号 |
| -9 | 新序列化格式（UE5.6+），支持条件性格式变更 |

### TotalHeaderSize 位置变更

TotalHeaderSize 的序列化位置取决于版本：

| 版本条件 | 位置 |
|----------|------|
| UE5 >= PACKAGE_SAVED_HASH (1016) | SavedHash 之后、CustomVersionContainer 之前 |
| UE5 < PACKAGE_SAVED_HASH | CustomVersionContainer 之后 |

### 序列化顺序总览

完整序列化顺序（按字节排列）：

```
Tag (int32)
LegacyFileVersion (int32)
[LegacyUE3Version (int32) — 当 LegacyFileVersion != -4]
FileVersionUE4 (int32)
[FileVersionUE5 (int32) — 当 LegacyFileVersion <= -8]
FileVersionLicenseeUE (int32)
[SavedHash (20 bytes) — 当 UE5 >= 1016]
[TotalHeaderSize (int32) — 当 UE5 >= 1016，在 SavedHash 之后]
[CustomVersionContainer — 当 LegacyFileVersion <= -2]
[TotalHeaderSize (int32) — 当 UE5 < 1016，在 CustomVersion 之后]
PackageName (FString)
PackageFlags (uint32)
NameCount (int32) + NameOffset (int32)
[SoftObjectPathsCount (int32) + SoftObjectPathsOffset (int32) — 当 UE5 >= 1008]
[LocalizationId (FString) — 非 FilterEditorOnly 且 UE4 >= 527]
[GatherableTextDataCount (int32) + GatherableTextDataOffset (int32) — UE4 >= 517]
ExportCount (int32) + ExportOffset (int32)
ImportCount (int32) + ImportOffset (int32)
[CellExportCount + CellExportOffset + CellImportCount + CellImportOffset — UE5 >= 1015]
[MetaDataOffset (int32) — UE5 >= 1014]
DependsOffset (int32)
[SoftPackageReferencesCount + SoftPackageReferencesOffset — UE4 >= 516]
[SearchableNamesOffset (int32) — UE4 >= 518]
ThumbnailTableOffset (int32)
[ImportTypeHierarchiesCount + ImportTypeHierarchiesOffset — UE5 >= 1018]
[LegacyGuid (FGuid, 16 bytes) — UE5 < 1016]
[PersistentGuid (FGuid) — WITH_EDITORONLY_DATA 且 UE4 >= 519]
[OwnerPersistentGuid (FGuid) — WITH_EDITORONLY_DATA 且 519 <= UE4 < 735]
GenerationCount (int32)
Generations[GenerationCount] — 每个 (int32 ExportCount, int32 NameCount)
SavedByEngineVersion (FEngineVersion) — 当 UE4 >= 522
CompatibleWithEngineVersion (FEngineVersion) — 当 UE4 >= 519
CompressionFlags (uint32)
CompressedChunks (TArray<FCompressedChunk>) — 固定序列化，通常 Count=0
PackageSource (uint32)
AdditionalPackagesToCook (TArray<FString>) — 固定序列化，通常 Count=0
AssetRegistryDataOffset (int32)
BulkDataStartOffset (int64)
WorldTileInfoDataOffset (int32) — 当 UE4 >= VER_UE4_WORLD_LEVEL_INFO
ChunkIDs (TArray<int32>) — 当 UE4 >= VER_UE4_CHANGED_CHUNKID_TO_BE_AN_ARRAY_OF_CHUNKIDS
PreloadDependencyCount (int32) + PreloadDependencyOffset (int32) — 当 UE4 >= 709
NamesReferencedFromExportDataCount (int32) — 当 UE5 >= 1001
PayloadTocOffset (int64) — 当 UE5 >= 1002
DataResourceOffset (int32) — 当 UE5 >= 1009
```

## 辅助结构

### FGenerationInfo

```cpp
struct FGenerationInfo {
    int32 ExportCount;  // 该世代的导出数量
    int32 NameCount;    // 该世代的名称数量
};
```

### FCompressedChunk（已废弃）

```cpp
struct FCompressedChunk {
    int32 UncompressedOffset;  // 未压缩文件中的原始偏移
    int32 UncompressedSize;    // 未压缩大小（字节）
    int32 CompressedOffset;    // 压缩文件中的偏移
    int32 CompressedSize;      // 压缩后大小（字节）
};
```

> **注意**：FCompressedChunk 在当前 UE 版本中已废弃。若 CompressedChunks 数组非空，加载器将拒绝加载该文件。

### FPackageFileVersion

```cpp
struct FPackageFileVersion {
    int32 FileVersionUE4 = 0;  // UE4 版本号
    int32 FileVersionUE5 = 0;  // UE5 版本号
};
```

### FEngineVersion

```
uint16 Major + uint16 Minor + uint16 Patch + uint32 Changelist + FString Branch
```

详见 [file-structure.md](file-structure.md) 整体结构概述。
