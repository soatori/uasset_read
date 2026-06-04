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
- 收集所有 FName 并建立 NameIndices 映射（`TMap<FNameEntryId, int32>`）
- 收集所有外部对象引用并建立 ImportMap
- 收集所有导出对象并建立 ExportMap
- 建立 ObjectIndicesMap 对象索引映射（`TMap<TObjectPtr<UObject>, FPackageIndex>`）
- 建立 CellIndicesMap Verse VCell 索引映射（UE5 新增）
- 建立 SoftObjectPathIndices 软对象路径映射（`TMap<FSoftObjectPath, int32>`）
- 建立 SearchableNamesObjectMap 可搜索名称映射

**核心映射方法：**

| 方法 | 用途 | 返回值 |
|------|------|--------|
| MapName(FNameEntryId) | FName 到名称表索引 | int32（名称表位置） |
| MapObject(TObjectPtr<const UObject>) | UObject 到 FPackageIndex | FPackageIndex（Import/Export索引） |
| MapSoftObjectPath(FSoftObjectPath) | 软对象路径到索引 | int32（路径表位置） |

**序列化运算符：**
- `operator<<(FName&)` — 通过 MapName() 写入名称索引
- `operator<<(UObject*&)` — 通过 MapObject() 写入 FPackageIndex
- `operator<<(FSoftObjectPath&)` — 写入软对象路径索引
- `operator<<(FObjectPtr&)` — 写入对象指针
- `operator<<(FLazyObjectPtr&)` — 写入惰性对象指针

**源码位置：** `Runtime/CoreUObject/Private/UObject/LinkerSave.cpp` — MapName(), MapObject()

**对应加载流程：** Stage 2 表结构加载（NameMap、ImportMap、ExportMap）

**相关文档：** [名称表结构](../name-table.md)、[Import/Export表结构](../import-export-tables.md)

### Stage 3: 序列化对象数据

对每个 Export 对象执行属性序列化，写入对象数据。

**关键步骤：**
- 遍历 ExportMap 中每个导出对象
- 设置 CurrentlySavingExport 标记当前序列化对象
- 设置 CurrentlySavingExportObject 标记当前对象指针
- 调用对象的 Serialize() 方法写入属性数据
- 通过 FPropertyTag 写入属性元数据（名称、类型、大小）
- 记录 ScriptSerialization 偏移（蓝图脚本序列化）
- 处理 TransientPropertyOverrides 瞬态属性覆盖

**核心方法：**

| 方法 | 用途 |
|------|------|
| MarkScriptSerializationStart() | 标记脚本序列化起始偏移 |
| MarkScriptSerializationEnd() | 标记脚本序列化结束偏移 |
| ShouldSkipProperty() | 判断是否跳过属性（Transient 属性） |
| SetSerializedProperty() | 设置当前序列化的属性 |
| SetSerializedPropertyChain() | 设置属性链 |
| PushSerializedProperty() | 压入属性栈 |
| PopSerializedProperty() | 弹出属性栈 |

**属性序列化流程：**
- 每个 FName 属性通过 `operator<<(FName)` 写入名称索引
- 每个 UObject 属性通过 `operator<<(UObject)` 写入 FPackageIndex
- 属性数据通过 FArchive 序列化接口写入
- 使用 UsingCustomVersion() 注册模块版本

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

**BulkData 序列化方法：**

| 方法 | 用途 |
|------|------|
| SerializeBulkData(FBulkData&, const FBulkDataSerializationParams&) | 序列化 BulkData（FArchive 接口重写） |
| GetBulkDataArchive(FBulkDataCookedIndex) | 获取 BulkData 写入流 |
| GetOptionalBulkDataArchive(FBulkDataCookedIndex) | 获取可选 BulkData 写入流 |
| GetMemoryMappedBulkDataArchive(FBulkDataCookedIndex) | 获取内存映射 BulkData 写入流 |
| OnPostSaveBulkData() | BulkData 保存后更新偏移 |
| ForEachBulkDataCookedIndex() | 遍历所有 CookedIndex 的 BulkData |
| HasCookedIndexBulkData() | 检查是否存在 CookedIndex BulkData |

> **注意（UE5.5+）**: `GetBulkDataArchive()`、`GetOptionalBulkDataArchive()`、`GetMemoryMappedBulkDataArchive()` 无参重载已标记为废弃（UE_DEPRECATED(5.5)），请使用带 `FBulkDataCookedIndex` 参数的版本。

**PackageTrailer 构建（UE5）：**
- PackageTrailerBuilder（`TUniquePtr<UE::FPackageTrailerBuilder>`）收集所有 Payload 信息
- 构建 PayloadLookupTable 查找表
- 写入 Header + Payload Data + Footer 结构
- Footer 以 PACKAGE_FILE_TAG 结尾验证

**Sidecar 数据（实验性）：**
- SidecarDataToAppend 用于 FEditorBulkData 添加 sidecar 文件载荷

**源码位置：** `Runtime/CoreUObject/Private/UObject/LinkerSave.cpp` — SerializeBulkData()

**对应加载流程：** Stage 4 后处理（BulkData 按需加载、PackageTrailer 解析）

**相关文档：** [BulkData 存储结构](../bulkdata-region.md)、[PackageTrailer 文件尾](../package-trailer.md)

## FLinkerSave 成员变量

| 成员 | 类型 | 说明 |
|------|------|------|
| Saver | FArchive* | 实际写入数据的归档 |
| CurrentlySavingExport | FPackageIndex | 当前正在保存的 Export 索引 |
| CurrentlySavingExportObject | UObject* | 当前正在保存的对象 |
| DepListForErrorChecking | TArray<FPackageIndex> | 依赖列表用于错误检查 |
| ObjectIndicesMap | TMap<TObjectPtr<UObject>, FPackageIndex> | 对象到包索引映射 |
| CellIndicesMap | TMap<Verse::VCell*, FPackageIndex> | Verse VCell 到包索引映射 |
| SearchableNamesObjectMap | TMap<const UObject*, TArray<FName>> | 可搜索名称映射 |
| NameIndices | TMap<FNameEntryId, int32> | 名称到索引映射 |
| SoftObjectPathIndices | TMap<FSoftObjectPath, int32> | 软对象路径到索引映射 |
| bIsWritingHeaderSoftObjectPaths | bool | 是否正在写入头部软对象路径 |
| FileRegions | TArray<FFileRegion> | 文件区域列表 |
| AdditionalDataToAppend | TArray<AdditionalDataCallback> | 附加数据回调 |
| bProceduralSave | bool | 是否为程序化保存 |
| bUpdatingLoadedPath | bool | 是否正在更新 LoadedPath |
| bRehydratePayloads | bool | 是否重新水合虚拟化载荷 |
| SidecarDataToAppend | TArray<FSidecarStorageInfo> | Sidecar 数据（实验性） |
| PackageTrailerBuilder | TUniquePtr<UE::FPackageTrailerBuilder> | PackageTrailer 构建器 |
| PostSaveCallbacks | TArray<TUniqueFunction<...>> | 保存后回调 |
| BulkDataAr | TMap<FBulkDataCookedIndex, TUniquePtr<FFileRegionMemoryWriter>> | BulkData 归档 |
| OptionalBulkDataAr | TMap<FBulkDataCookedIndex, TUniquePtr<FFileRegionMemoryWriter>> | 可选 BulkData 归档 |
| MemoryMappedBulkDataAr | TMap<FBulkDataCookedIndex, TUniquePtr<FFileRegionMemoryWriter>> | 内存映射 BulkData 归档 |

## 源码引用

### 关键源码文件

| 文件 | 路径 | 说明 |
|------|------|------|
| LinkerSave.h | Runtime/CoreUObject/Public/UObject/LinkerSave.h | FLinkerSave 结构定义 |
| LinkerSave.cpp | Runtime/CoreUObject/Private/UObject/LinkerSave.cpp | 保存流程实现 |
| PackageFileSummary.h | Runtime/CoreUObject/Public/UObject/ | FPackageFileSummary 文件头结构 |
| ObjectResource.h | Runtime/CoreUObject/Public/UObject/ | FObjectExport/FObjectImport 结构 |
| BulkData.h | Runtime/CoreUObject/Public/Serialization/ | FBulkData 结构定义 |
| PackageTrailer.h | Runtime/CoreUObject/Public/UObject/ | PackageTrailer 结构（UE5） |

### 关键方法速查

| 流程阶段 | 方法名 | 用途 |
|----------|--------|------|
| 构造 | FLinkerSave(UPackage*) | 部分构造，需后续调用 AssignSaver |
| 构造 | AssignSaver(FArchive*, bool, bool) | 分配归档并设置字节交换和版本标志 |
| 构造 | AssignMemorySaver(bool, bool) | 构造内存写入归档 |
| 构造 | TryAssignFileSaver(FStringView, bool, bool) | 构造文件写入归档 |
| 文件头 | AssignSaverInternal() | 初始化 Summary，设置魔数和版本 |
| 名称映射 | MapName() | FName 到名称索引转换 |
| 对象映射 | MapObject() | UObject 到 FPackageIndex 转换 |
| 软路径映射 | MapSoftObjectPath() | FSoftObjectPath 到索引转换 |
| FName序列化 | operator<<(FName&) | 写入名称索引和编号 |
| 对象序列化 | operator<<(UObject*&) | 写入 FPackageIndex |
| 软路径序列化 | operator<<(FSoftObjectPath&) | 写入软对象路径索引 |
| 脚本序列化 | MarkScriptSerializationStart/End() | 记录蓝图脚本序列化偏移 |
| BulkData | SerializeBulkData() | 序列化 BulkData（FArchive 接口重写） |
| BulkData | GetBulkDataArchive(FBulkDataCookedIndex) | 获取 BulkData 写入流 |
| BulkData | ForEachBulkDataCookedIndex() | 遍历所有 CookedIndex |
| 后处理 | OnPostSaveBulkData() | BulkData 保存后更新内存偏移 |
| 版本 | UsingCustomVersion(const FGuid&) | 注册自定义版本 |
| 清理 | CloseAndDestroySaver() | 关闭并删除归档 |

## 版本差异

### UE5 新增功能

**文件头变更：**
- 双版本号机制：FileVersionUE4 + FileVersionUE5
- 新增 PayloadTocOffset 指向 PackageTrailer
- 新增 DataResourceOffset 数据资源表偏移
- 新增 NamesReferencedFromExportDataCount
- 新增 SoftObjectPathsCount/Offset 软对象路径表
- SavedHash 从 FGuid 改为 FIoHash（PACKAGE_SAVED_HASH 版本）

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
- 新增 EPropertyTagSerializeType 枚举
- 新增 PropertyGuid 和 HasPropertyGuid 字段
- 新增 OverrideOperation 和 bExperimentalOverridableLogic 字段

**BulkData 变更：**
- GetBulkDataArchive 等方法现在使用 FBulkDataCookedIndex 参数（UE5.5+）
- 新增 ForEachBulkDataCookedIndex 和 HasCookedIndexBulkData
- 新增 SidecarDataToAppend 实验性 sidecar 支持
- 新增 bRehydratePayloads 水合虚拟化载荷支持
- 新增 Verse VCell 支持（CellIndicesMap）

**Verse 支持（VERSE_CELLS 版本）：**
- 新增 CellIndicesMap 映射
- 新增 operator<<(Verse::VCell*&) 序列化

### UE4 特性

- 无 PackageTrailer，文件末尾直接以 BulkData 或其他数据结束
- 单版本号（GPackageFileUE4Version）
- PackageGuid 字段（已移除）
- 部分 BulkData 标志不同

### 兼容处理

| 版本检查 | 处理方式 |
|----------|----------|
| FileVersionUE4 | UE4 资产兼容读取 |
| FileVersionUE5 | UE5 新特性检查 |
| CustomVersion | 模块特定版本控制 |
| bInSaveUnversioned | Cooked 包移除版本号 |

详见 [文件头结构](../package-summary.md) 版本差异章节。
