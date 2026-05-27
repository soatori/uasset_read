# LinkerSave 保存流程

## 概述

FLinkerSave 是 .uasset 文件保存的核心类，负责将内存中的 UObject 对象序列化写入磁盘文件。与 [LinkerLoad 加载流程](linker-load.md)完全对称，保存流程执行加载流程的逆向操作。

保存流程将内存对象转换为磁盘数据，核心职责包括：构造文件头结构（FPackageFileSummary）、收集并序列化名称表（NameMap）、建立 Import/Export 对象映射、序列化对象属性数据、写入 BulkData 大数据块和 PackageTrailer 文件尾（UE5）。

FLinkerSave 继承自 FLinker 和 FArchiveUObject，通过 Saver（FArchive）成员完成实际的文件写入操作。核心映射方法 MapName() 和 MapObject() 将 FName 和 UObject 转换为文件中的索引值。

## 阶段划分

### Stage 1: 写入文件头

构造 FPackageFileSummary 结构，设置文件魔数和版本信息。

**关键步骤：**
- 设置魔数 `PACKAGE_FILE_TAG = 0x9E2A83C1`
- 设置最新版本号 `SetToLatestFileVersions()`
- 设置引擎版本 `SavedByEngineVersion`
- 设置包标志 `PackageFlags`
- 设置包名称和 ChunkIDs

**核心逻辑：** AssignSaverInternal() 设置 Summary.Tag = PACKAGE_FILE_TAG，调用 SetToLatestFileVersions() 设置版本，设置 SavedByEngineVersion 和 CompatibleWithEngineVersion，设置 PackageFlags。

**源码位置：** `Runtime/CoreUObject/Private/UObject/LinkerSave.cpp` — AssignSaverInternal()

**对应加载流程：** Stage 1 文件头读取（魔数验证、版本解析）

### Stage 2: 序列化表结构

收集并序列化 NameMap、ImportMap、ExportMap 表结构。

**关键步骤：**
- 收集所有 FName 并建立 NameIndices 映射
- 收集所有外部对象引用并建立 ImportMap
- 收集所有导出对象并建立 ExportMap
- 建立 ObjectIndicesMap 对象索引映射
- 建立 SoftObjectPathIndices 软对象路径映射

**核心映射方法：**

| 方法 | 用途 | 返回值 |
|------|------|--------|
| MapName(FNameEntryId) | FName 到名称表索引 | int32（名称表位置） |
| MapObject(UObject) | UObject 到 FPackageIndex | FPackageIndex（Import/Export索引） |
| MapSoftObjectPath(FSoftObjectPath) | 软对象路径到索引 | int32（路径表位置） |

**序列化运算符：**
- `operator<<(FName&)` — 通过 MapName() 写入名称索引
- `operator<<(UObject*&)` — 通过 MapObject() 写入 FPackageIndex
- `operator<<(FSoftObjectPath&)` — 写入软对象路径索引

**源码位置：** `Runtime/CoreUObject/Private/UObject/LinkerSave.cpp` — MapName(), MapObject()

**对应加载流程：** Stage 2 表结构加载（NameMap、ImportMap、ExportMap）

**相关文档：** [名称表结构](../name-table.md)、[Import/Export表结构](../import-export-tables.md)

### Stage 3: 序列化对象数据

对每个 Export 对象执行属性序列化，写入对象数据。

**关键步骤：**
- 遍历 ExportMap 中每个导出对象
- 设置 CurrentlySavingExport 标记当前序列化对象
- 调用对象的 Serialize() 方法写入属性数据
- 通过 FPropertyTag 写入属性元数据（名称、类型、大小）
- 记录 ScriptSerialization 偏移（蓝图脚本序列化）

**核心方法：**

| 方法 | 用途 |
|------|------|
| MarkScriptSerializationStart() | 标记脚本序列化起始偏移 |
| MarkScriptSerializationEnd() | 标记脚本序列化结束偏移 |
| ShouldSkipProperty() | 判断是否跳过属性（Transient 属性） |

**属性序列化流程：**
- 每个 FName 属性通过 `operator<<(FName)` 写入名称索引
- 每个 UObject 属性通过 `operator<<(UObject)` 写入 FPackageIndex
- 属性数据通过 FArchive 序列化接口写入

**源码位置：** `Runtime/CoreUObject/Private/UObject/LinkerSave.cpp` — operator<< 重载

**对应加载流程：** Stage 3 对象加载（CreateExport、Preload、属性反序列化）

**相关文档：** [属性标签序列化](property-tag.md)

### Stage 4: 写入数据区

写入 BulkData 数据和 PackageTrailer 文件尾（UE5）。

**关键步骤：**
- 序列化 BulkData 元数据（FBulkMetaResource）
- 确定数据存储位置（内联/末尾/分离文件）
- 写入 BulkData 压缩数据
- 构建 PackageTrailer（UE5）
- 写入 PayloadTOC 查找表
- 写入文件尾验证标记

**BulkData 存储策略：**

| 标志 | 存储位置 | 说明 |
|------|----------|------|
| BULKDATA_ForceInlinePayload | 内联数据 | 数据紧跟元数据 |
| BULKDATA_PayloadAtEndOfFile | 文件末尾 | 数据写入 BulkDataStartOffset 位置 |
| BULKDATA_PayloadInSeparateFile | 分离文件 | 数据写入 .ubulk 等文件 |
| BULKDATA_WorkspaceDomainPayload | 引用原文件 | EditorDomain 保留原数据位置 |

**核心方法：**

| 方法 | 用途 |
|------|------|
| SerializeBulkData() | 序列化 BulkData 元数据和数据 |
| GetBulkDataArchive() | 获取 BulkData 数据写入流 |
| GetOptionalBulkDataArchive() | 获取可选 BulkData 写入流 |
| GetMemoryMappedBulkDataArchive() | 获取内存映射 BulkData 写入流 |
| OnPostSaveBulkData() | BulkData 保存后更新偏移 |

**PackageTrailer 构建（UE5）：**
- PackageTrailerBuilder 收集所有 Payload 信息
- 构建 PayloadLookupTable 查找表
- 写入 Header + Payload Data + Footer 结构
- Footer 以 PACKAGE_FILE_TAG 结尾验证

**源码位置：** `Runtime/CoreUObject/Private/UObject/LinkerSave.cpp` — SerializeBulkData()

**对应加载流程：** Stage 4 后处理（BulkData 按需加载、PackageTrailer 解析）

**相关文档：** [BulkData 存储结构](../bulkdata-region.md)、[PackageTrailer 文件尾](../package-trailer.md)

## 源码引用

### 关键源码文件

| 文件 | 路径 | 说明 |
|------|------|------|
| LinkerSave.h | Runtime/CoreUObject/Public/UObject/ | FLinkerSave 结构定义 |
| LinkerSave.cpp | Runtime/CoreUObject/Private/UObject/ | 保存流程实现 |
| PackageFileSummary.h | Runtime/CoreUObject/Public/UObject/ | FPackageFileSummary 文件头结构 |
| ObjectResource.h | Runtime/CoreUObject/Public/UObject/ | FObjectExport/FObjectImport 结构 |
| BulkData.h | Runtime/CoreUObject/Public/Serialization/ | FBulkData 结构定义 |
| PackageTrailer.h | Runtime/CoreUObject/Public/UObject/ | PackageTrailer 结构（UE5） |

### 关键方法速查

| 流程阶段 | 方法名 | 用途 |
|----------|--------|------|
| 文件头 | AssignSaverInternal() | 初始化 Summary，设置魔数和版本 |
| 文件头 | SetToLatestFileVersions() | 设置最新版本号 |
| 名称映射 | MapName() | FName 到名称索引转换 |
| 对象映射 | MapObject() | UObject 到 FPackageIndex 转换 |
| 软路径映射 | MapSoftObjectPath() | FSoftObjectPath 到索引转换 |
| FName序列化 | operator<<(FName&) | 写入名称索引和编号 |
| 对象序列化 | operator<<(UObject*&) | 写入 FPackageIndex |
| 软路径序列化 | operator<<(FSoftObjectPath&) | 写入软对象路径索引 |
| 脚本序列化 | MarkScriptSerializationStart/End() | 记录蓝图脚本序列化偏移 |
| BulkData | SerializeBulkData() | 序列化 BulkData 元数据和数据 |
| BulkData | GetBulkDataArchive() | 获取 BulkData 写入流 |
| 后处理 | OnPostSaveBulkData() | BulkData 保存后更新内存偏移 |

## 版本差异

### UE5 新增功能

**文件头变更：**
- 双版本号机制：FileVersionUE4 + FileVersionUE5
- 新增 PayloadTocOffset 指向 PackageTrailer
- 新增 DataResourceOffset 数据资源表偏移
- 新增 NamesReferencedFromExportDataCount
- 新增 SoftObjectPathsCount/Offset 软对象路径表
- SavedHash 从 FGuid 改为 FIoHash

**PackageTrailer（UE5 特有）：**
- 新增 PackageTrailerBuilder 构建 PayloadTOC
- 文件末尾结构：Header + Payload Data + Footer
- Footer 以 PACKAGE_FILE_TAG 双重验证
- 支持 Payload 分离存储和虚拟化

**Export 表变更：**
- 新增 ScriptSerializationStartOffset/EndOffset（SCRIPT_SERIALIZATION_OFFSET 版本）
- 新增 bIsInheritedInstance（TRACK_OBJECT_EXPORT_IS_INHERITED 版本）
- 新增 bGeneratePublicHash

**属性序列化变更：**
- FPropertyTypeName 替代部分类型字段（UE5.4+）
- 废弃 StructName/EnumName/InnerType/ValueType（使用 TypeName）
- 废弃 Prop 指针（使用 GetProperty()/SetProperty()）

### UE4 特性

- 无 PackageTrailer，文件末尾直接以 BulkData 或其他数据结束
- 单版本号（GPackageFileUE4Version）
- PackageGuid 字段（已移除）
- 部分 BulkData 标志不同（如 LZ4 压缩已废弃）

### 兼容处理

| 版本检查 | 处理方式 |
|----------|----------|
| FileVersionUE4 | UE4 资产兼容读取 |
| FileVersionUE5 | UE5 新特性检查 |
| CustomVersion | 模块特定版本控制 |
| bInSaveUnversioned | Cooked 包移除版本号 |

详见 [文件头结构](../package-summary.md) 版本差异章节。