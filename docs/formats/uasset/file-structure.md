# .uasset 文件整体结构

## 概述

.uasset 是 Unreal Engine 的资产文件格式，存储单个 UPackage 的内容，包括导出对象和引用的外部对象。文件结构由 Header + Tables + Data + Trailer 组成，文件头 FPackageFileSummary 作为"目录"指向各数据区。文件以 PACKAGE_FILE_TAG (0x9E2A83C1) 验证。

.uasset 文件是 Unreal Engine 资产存储的基本单元，所有资产（材质、纹理、网格、蓝图等）均以 .uasset 格式保存。加载时，引擎首先读取文件头，根据偏移量定位各表，建立对象引用网络后按需加载对象数据。

## 文件布局示意图

```
┌─────────────────────────────────────────────┐
│ FPackageFileSummary (文件头)                │
│   - Tag, Version, Flags                     │
│   - NameOffset/Count, ExportOffset/Count... │
├─────────────────────────────────────────────┤
│ Name Table (名称表)                         │
│   - FName 条目序列                          │
├─────────────────────────────────────────────┤
│ Import Map (导入表)                         │
│   - FObjectImport 条目序列                  │
├─────────────────────────────────────────────┤
│ Export Map (导出表)                         │
│   - FObjectExport 条目序列                  │
├─────────────────────────────────────────────┤
│ Export Data (导出对象数据)                  │
│   - 各 Export 的序列化数据                  │
├─────────────────────────────────────────────┤
│ Bulk Data / Payload Data (数据区)           │
│   - 大型二进制数据                          │
├─────────────────────────────────────────────┤
│ PackageTrailer (文件尾，UE5新增)            │
│   - Header + Payload Data + Footer          │
│   - Footer 以 PACKAGE_FILE_TAG 结尾        │
└─────────────────────────────────────────────┘
```

## 各结构章节

### 文件头

详见 [package-summary.md](package-summary.md)

FPackageFileSummary 包含版本、表位置、数据位置等关键信息。文件头作为索引表，指向文件中各数据区的起始位置。

### 名称表

详见 [name-table.md](name-table.md)

存储包内所有 FName，由 NameOffset/NameCount 定位。FName 由 ComparisonIndex（入口编号）、Number（实例编号）和 DisplayIndex（显示索引，UE5新增）组成，通过 SerializeName 机制序列化。

### 导入表

详见 [import-export-tables.md](import-export-tables.md#import)

FObjectImport 序列，存储外部对象引用。每个 Import 条目记录对象名称、所属包、类名、旧类名等信息。

### 导出表

详见 [import-export-tables.md](import-export-tables.md#export)

FObjectExport 序列，存储本包导出对象。每个 Export 条目记录对象名称、类引用、序列化数据位置、依赖关系等。

### 数据区

详见 [bulkdata-region.md](bulkdata-region.md)

三种数据存储方式：BulkData（传统）、PayloadTOC（UE5）、DataResource（UE5）。存储纹理像素、网格几何等大型二进制数据。

### 文件尾

详见 [package-trailer.md](package-trailer.md)

PackageTrailer (UE5新增)，以 PACKAGE_FILE_TAG 结尾。Header + Payload Data + Footer 结构，管理 Payload 数据。

## 加载流程概述

1. 读取 FPackageFileSummary，验证 PACKAGE_FILE_TAG
2. 根据版本号判断 UE4/UE5，选择对应解析策略
3. 读取 Name Table，建立名称映射（NameMap）
4. 读取 Import/Export Map，建立对象引用表
5. 按需加载 Export 数据和 Bulk Data（延迟加载）
6. UE5 文件还需解析 PackageTrailer 和 PayloadTOC

## 源码引用

- Runtime/CoreUObject/Public/UObject/PackageFileSummary.h
- Runtime/CoreUObject/Public/UObject/ObjectResource.h
- Runtime/CoreUObject/Public/UObject/PackageTrailer.h
- Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp（加载流程）

---

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
| CustomVersionContainer | FCustomVersionContainer | 自定义版本容器，存储各插件/模块的版本信息 | — |
| PackageFlags | uint32 | 包标志位（如 PKG_FilterEditorOnly） | — |
| TotalHeaderSize | int32 | 文件头总大小（包含 Summary 和各表） | — |
| PackageName | FString | 包名称 | — |
| NameCount | int32 | 名称表条目数量 | — |
| NameOffset | int32 | 名称表在文件中的偏移 | — |
| SoftObjectPathsCount | int32 | 软对象路径数量 | UE5 新增 |
| SoftObjectPathsOffset | int32 | 软对象路径偏移 | UE5 新增 |
| LocalizationId | FString | 本地化标识符 | — |
| GatherableTextDataCount | int32 | 可收集文本数据数量 | — |
| GatherableTextDataOffset | int32 | 可收集文本数据偏移 | — |
| MetaDataOffset | int32 | 元数据偏移 | UE5 METADATA_SERIALIZATION_OFFSET |
| ExportCount | int32 | 导出表条目数量 | — |
| ExportOffset | int32 | 导出表在文件中的偏移 | — |
| ImportCount | int32 | 导入表条目数量 | — |
| ImportOffset | int32 | 导入表在文件中的偏移 | — |
| CellExportCount | int32 | Cell 导出数量 | UE5 VERSE_CELLS |
| CellExportOffset | int32 | Cell 导出偏移 | UE5 VERSE_CELLS |
| CellImportCount | int32 | Cell 导入数量 | UE5 VERSE_CELLS |
| CellImportOffset | int32 | Cell 导入偏移 | UE5 VERSE_CELLS |
| DependsOffset | int32 | 依赖表偏移 | — |
| SoftPackageReferencesCount | int32 | 软包引用数量 | — |
| SoftPackageReferencesOffset | int32 | 软包引用偏移 | — |
| SearchableNamesOffset | int32 | 可搜索名称偏移 | — |
| ThumbnailTableOffset | int32 | 缩略图表偏移 | — |
| ImportTypeHierarchiesCount | int32 | 导入类型层次数量 | UE5 IMPORT_TYPE_HIERARCHIES |
| ImportTypeHierarchiesOffset | int32 | 导入类型层次偏移 | UE5 IMPORT_TYPE_HIERARCHIES |
| SavedHash | FIoHash | 保存时的哈希值（用于 IAS） | UE5 PACKAGE_SAVED_HASH |
| PersistentGuid | FGuid | 持久化 GUID | — |
| Generations | TArray<FGenerationInfo> | 版本世代信息（编辑器保存历史） | — |
| SavedByEngineVersion | FEngineVersion | 保存时的引擎版本 | — |
| CompatibleWithEngineVersion | FEngineVersion | 兼容的引擎版本 | UE4 PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION |
| CompressionFlags | uint32 | 压缩标志 | — |
| PackageSource | uint32 | 包来源（编译/编辑器等） | — |
| bUnversioned | bool | 是否无版本号 | — |
| AssetRegistryDataOffset | int32 | 资产注册数据偏移 | — |
| BulkDataStartOffset | int64 | BulkData 数据区起始位置 | — |
| WorldTileInfoDataOffset | int32 | 世界瓦片信息偏移 | — |
| ChunkIDs | TArray<int32> | Pak 文件 Chunk ID | UE5 PACKAGE_CHUNK_ID |
| PreloadDependencyCount | int32 | 预加载依赖数量 | — |
| PreloadDependencyOffset | int32 | 预加载依赖偏移 | — |
| NamesReferencedFromExportDataCount | int32 | 从导出数据引用的名称数量 | UE5 NAMES_REFERENCED_FROM_EXPORT_DATA |
| PayloadTocOffset | int64 | Payload TOC 偏移（指向 PackageTrailer） | UE5 PAYLOAD_TOC |
| DataResourceOffset | int32 | 数据资源表偏移 | UE5 DATA_RESOURCES |

## FPackageFileVersion 结构

UE5.0 起，FileVersionUE 从单一 int32 改为 FPackageFileVersion 结构：

| 字段名 | 类型 | 用途 |
|--------|------|------|
| FileVersionUE4 | int32 | UE4 版本号（EUnrealEngineObjectUE4Version） |
| FileVersionUE5 | int32 | UE5 版本号（EUnrealEngineObjectUE5Version） |

双版本号机制确保 UE4/UE5 资产互操作性。

## FEngineVersion 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Major | uint16 | 主版本号 |
| Minor | uint16 | 次版本号 |
| Patch | uint16 | 补丁版本号 |
| Changelist | uint32 | 变更列表号 |
| Branch | FString | 分支名称 |

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
- **ChunkIDs**: PACKAGE_CHUNK_ID 版本新增，类型为 TArray<int32>
- **CellExportCount/Offset/CellImportCount/Offset**: VERSE_CELLS 版本新增
- **ImportTypeHierarchiesCount/Offset**: IMPORT_TYPE_HIERARCHIES 版本新增
- **MetaDataOffset**: METADATA_SERIALIZATION_OFFSET 版本新增

### 版本号结构变更
- UE5.0 起，FileVersionUE 从单一 int32 改为 FPackageFileVersion 结构
- 包含 UE4 版本号（EUnrealEngineObjectUE4Version）和 UE5 版本号（EUnrealEngineObjectUE5Version）
- 双版本号机制确保 UE4/UE5 资产互操作性

详见 [file-structure.md](file-structure.md) 整体结构概述。

---

# Import/Export 表结构

## 概述

Import 表存储本包引用的外部对象（其他包中的对象），Export 表存储本包导出的对象（可以被其他包引用）。FPackageIndex 是引用的统一表示：正数指向 Export，负数指向 Import，0 表示空引用。

ImportCount/ImportOffset 和 ExportCount/ExportOffset 在 PackageFileSummary 中定义表位置。加载时，Import/Export 表用于建立对象引用网络，确定对象间的依赖关系。

## FPackageIndex 引用机制

FPackageIndex 封装导入导出表索引，实现统一的对象引用表示：

| 属性/方法 | 说明 |
|-----------|------|
| Index | int32 内部索引值 |
| IsExport() | Index > 0 表示导出对象引用 |
| IsImport() | Index < 0 表示导入对象引用 |
| IsNull() | Index == 0 表示空引用 |
| ToExport() | Index - 1（导出表索引从 0 开始） |
| ToImport() | -Index - 1（导入表索引从 0 开始） |
| FromExport(int) | 导出索引转 FPackageIndex：Index = i + 1 |
| FromImport(int) | 导入索引转 FPackageIndex：Index = -i - 1 |

**引用规则**: Export 索引用正数（从 1 开始），Import 索引用负数（从 -1 开始），避免混淆。

## FObjectImport 字段表

FObjectImport 继承自 FObjectResource，存储外部对象引用：

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| ObjectName | FName | 对象名称（继承自 FObjectResource） | — |
| OuterIndex | FPackageIndex | 外层对象引用（继承） | — |
| ClassPackage | FName | 类所在包名 | — |
| ClassName | FName | 类名 | — |
| OldClassName | FName | 旧类名（用于类重定向） | — |
| PackageName | FName | 包名 | UE5 WITH_EDITORONLY_DATA |
| SourceIndex | int32 | 源链接器导出索引（Transient） | — |
| bImportOptional | bool | 是否来自可选包 | — |
| bImportPackageHandled | bool | 包是否已处理（Transient） | — |
| bImportSearchedFor | bool | 是否已搜索（Transient） | — |
| bImportFailed | bool | 是否导入失败（Transient） | — |

**运行时字段（Transient）：**
- XObject: UObject* — 运行时对象指针
- SourceLinker: FLinkerLoad* — 源链接器指针

## FObjectExport 字段表

FObjectExport 继承自 FObjectResource，存储本包导出对象：

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| ObjectName | FName | 对象名称（继承自 FObjectResource） | — |
| OuterIndex | FPackageIndex | 外层对象引用（继承） | — |
| ClassIndex | FPackageIndex | 类引用 | — |
| SuperIndex | FPackageIndex | 父类引用（仅 UStruct） | — |
| TemplateIndex | FPackageIndex | 模板/原型引用 | — |
| ThisIndex | FPackageIndex | 自身索引 | — |
| ObjectFlags | EObjectFlags | 对象标志 | — |
| SerialSize | int64 | 序列化数据大小 | — |
| SerialOffset | int64 | 序列化数据偏移（文件位置） | — |
| ScriptSerializationStartOffset | int64 | 脚本序列化起始偏移 | UE5 SCRIPT_SERIALIZATION_OFFSET |
| ScriptSerializationEndOffset | int64 | 脚本序列化结束偏移 | UE5 SCRIPT_SERIALIZATION_OFFSET |
| bForcedExport | bool:1 | 是否强制导出（跨包引用） | — |
| bNotForClient | bool:1 | 客户端不加载 | — |
| bNotForServer | bool:1 | 服务器不加载 | — |
| bNotAlwaysLoadedForEditorGame | bool:1 | 编辑器游戏不总是加载 | — |
| bIsAsset | bool:1 | 是否为资产对象 | — |
| bIsInheritedInstance | bool:1 | 是否为继承实例 | UE5 TRACK_OBJECT_EXPORT_IS_INHERITED |
| bGeneratePublicHash | bool:1 | 是否生成公共哈希 | UE5 新增 |
| bExportLoadFailed | bool:1 | 导出加载失败标记 | — |
| bWasFiltered | bool:1 | 是否被过滤 | — |
| PackageFlags | uint32 | 强制导出的包标志 | — |
| FirstExportDependency | int32 | 依赖项起始索引 | — |
| SerializationBeforeSerializationDependencies | int32 | 序列化前依赖数量 | — |
| CreateBeforeSerializationDependencies | int32 | 创建前序列化依赖数量 | — |
| SerializationBeforeCreateDependencies | int32 | 序列化前创建依赖数量 | — |
| CreateBeforeCreateDependencies | int32 | 创建前创建依赖数量 | — |

**运行时字段（Transient）：**
- Object: UObject* — 运行时对象指针
- HashNext: int32 — 哈希链下一个索引

## 源码引用

- Runtime/CoreUObject/Public/UObject/ObjectResource.h
- Runtime/CoreUObject/Public/UObject/PackageFileSummary.h

## 版本差异

### UE5 新增字段
- **ScriptSerializationStartOffset/EndOffset**: SCRIPT_SERIALIZATION_OFFSET 版本新增，用于蓝图脚本序列化
- **bIsInheritedInstance**: TRACK_OBJECT_EXPORT_IS_INHERITED 版本新增
- **bGeneratePublicHash**: 新增，用于公共哈希生成

### UE4 已移除字段
- **PackageGuid**: REMOVE_OBJECT_EXPORT_PACKAGE_GUID 版本已移除

### 依赖项机制
- FirstExportDependency + 5 个计数字段定义对象加载依赖顺序
- 用于确保对象按正确顺序加载（先创建依赖对象）

详见 [file-structure.md](file-structure.md) 整体结构概述。

---

# 文件尾结构 (PackageTrailer)

## 概述

PackageTrailer 是 UE5 新增的文件尾结构，存储在 .uasset 文件末尾，用于管理 Payload 数据。结构为：[Header] + [Payload Data] + [Footer]。Footer 以 PACKAGE_FILE_TAG 结尾，用于文件验证。

PackageTrailer 的详细内容（版本演进、虚拟化机制）在 Phase 7（版本演进历史）处理，此处仅简要说明存在和位置。

## 结构字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| TrailerPositionInFile | int64 | Trailer 在文件中的位置 |
| Header.Tag | uint64 | 魔数 0xD1C43B2E80A5F697 |
| Header.Version | int32 | Trailer 版本号 |
| Header.HeaderLength | uint32 | Header 大小 |
| Header.PayloadsDataLength | uint64 | Payload 数据总大小 |
| Header.PayloadLookupTable | TArray<FLookupTableEntry> | Payload 查找表 |
| Footer.Tag | uint64 | 魔数 0x29BFCA045138DE76 |
| Footer.TrailerLength | uint64 | Trailer 总大小 |
| Footer.PackageTag | uint32 | PACKAGE_FILE_TAG (0x9E2A83C1) |

**PayloadLookupTable**: 详见 [bulkdata-region.md](bulkdata-region.md) FLookupTableEntry 结构。

**PACKAGE_FILE_TAG**: Footer 以文件魔数结尾，形成双重验证。

## 源码引用

- Runtime/CoreUObject/Public/UObject/PackageTrailer.h
- Runtime/Core/Public/UObject/ObjectVersion.h

## 版本差异

### UE5 新增
- PackageTrailer 为 UE5 特有结构
- UE4 文件无 Trailer，文件末尾直接以 PACKAGE_FILE_TAG 结尾
- PAYLOAD_TOC 版本引入 Trailer 机制

### 与 BulkData 关系
- PayloadLookupTable 承载 PayloadTOC 数据
- 详见 [bulkdata-region.md](bulkdata-region.md) PayloadTOC 结构

详见 [file-structure.md](file-structure.md) 整体结构概述。

---

# 名称表结构

## 概述

名称表存储包内所有 FName 字符串的唯一标识。NameCount 指定名称数量，NameOffset 指定名称数据在文件中的起始位置。FName 由三部分组成：ComparisonIndex（名称入口编号）、Number（实例编号）和 DisplayIndex（显示索引，UE5新增），名称表按顺序编号，从 0 开始。

名称序列化通过 SerializeName 函数完成，读取 NameIndex 和 Number 两个值，通过 NameMap 映射到实际字符串。

## 字段表

### PackageFileSummary 中名称表定位字段

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| NameCount | int32 | 名称表条目数量 | — |
| NameOffset | int32 | 名称数据在文件中的偏移 | — |
| NamesReferencedFromExportDataCount | int32 | 从导出数据引用的名称数量 | UE5 新增 |

### FName 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| ComparisonIndex | FNameEntryId | 名称入口编号（指向名称表中第几个条目） |
| Number | uint32 | 实例编号（用于区分同名不同实例，如 Material_0, Material_1） |
| DisplayIndex | FNameEntryId | 显示索引（UE5新增，用于区分大小写显示） |

### 名称表条目序列化格式

每个名称条目序列化为：
- NameString (FString) - 名称字符串
- NonCasePreservingHash (uint16) - 非大小写保留哈希（旧版本）
- CasePreservingHash (uint16) - 大小写保留哈希

## 序列化机制

名称通过 `operator<<(FArchive& Ar, FName& Name)` 序列化：
1. 读取 NameIndex (int32)
2. 读取 Number (int32)
3. NameIndex 指向 NameMap 中的条目，获取实际字符串
4. Number 用于区分同名的不同实例

**NameMap**: 加载时建立，TMap<FName, int32> 类型，将 FName 映射到名称表索引。

**入口编号规则**: 名称表按文件顺序编号，Index 值直接对应条目位置（从 0 开始）。

## 源码引用

- Runtime/CoreUObject/Public/UObject/PackageFileSummary.h (NameCount/NameOffset)
- Runtime/CoreUObject/Public/UObject/LinkerLoad.h (NameMap)
- Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp (SerializeName 实现)
- Runtime/Core/Public/UObject/NameTypes.h (FName 定义)

## 版本差异

### UE5 新增
- **NamesReferencedFromExportDataCount**: NAMES_REFERENCED_FROM_EXPORT_DATA 版本新增，用于优化加载，仅加载必要的名称
- **DisplayIndex**: FName 新增字段，用于区分大小写显示

### 历史变更
- VER_UE4_NAME_HASHES_SERIALIZED: 名称哈希序列化版本
- VER_UE4_SERIALIZE_NAME_IN_UNICODE: Unicode 名称序列化
- 名称条目格式随版本扩展

详见 [file-structure.md](file-structure.md) 整体结构概述。