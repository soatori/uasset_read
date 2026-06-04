# LinkerLoad 加载流程

## 概述

LinkerLoad 是 .uasset 文件加载的核心类，负责将磁盘上的包文件完整加载到内存对象。它继承自 FLinker（进而继承 FLinkerTables），同时继承 FArchiveUObject，协调文件头解析、表结构加载、对象创建和后处理四个阶段，是 UObject 加载系统的关键组件。

加载流程从 FPackageFileSummary 开始，逐步构建 NameMap、ImportMap、ExportMap，然后按依赖顺序创建 UObject 并序列化属性，最后进行引用修复和蓝图再生等后处理。

> **继承链**: FLinkerLoad -> FLinker (管理 ImportMap/ExportMap/DependsMap 等表) -> FLinkerTables
> FLinkerLoad 同时继承 FArchiveUObject 以支持序列化接口。

## 阶段划分

### Stage 1: 文件头读取

验证文件类型并解析包文件摘要结构。此阶段在 FLinkerLoad 创建期间（Tick 流程中）完成。

**职责:**
- 验证文件魔数 (PACKAGE_FILE_TAG = 0x9E2A83C1)
- 读取双版本号 (FileVersionUE4/FileVersionUE5)
- 解析 FPackageFileSummary 各字段
- 获取各表的偏移和数量信息
- 序列化 PackageTrailer（UE5 PayloadTOC 机制）

**关键方法:**
| 方法名 | 职责 |
|--------|------|
| SerializePackageFileSummary() | 启动文件头序列化 |
| SerializePackageFileSummaryInternal() | 内部序列化文件头结构 |
| UpdateFromPackageFileSummary() | 将 Summary 数据更新到 Linker/Loader/RootPackage |
| SerializePackageTrailer() | 序列化包尾部（UE5 PayloadTOC，用于识别包的有效载荷） |
| ProcessPackageSummary() | 处理包摘要的完整流程 |

**验证逻辑**: 通过 FPackageFileSummary 自身方法实现：
- `IsFileVersionValid()` - 验证版本有效性
- `IsFileVersionTooOld()` - 检查版本是否过旧
- `IsFileVersionTooNew()` - 检查版本是否过新

**源码位置:** Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp

**交叉引用:** 文件头详细字段见 [package-summary.md](../package-summary.md)

---

### Stage 2: 表结构加载

按文件头记录的偏移加载名称表、导入表、导出表和依赖图。

**职责:**
- 序列化 NameMap (名称表)
- 序列化 ImportMap (导入表)
- 序列化 ExportMap (导出表)
- 序列化 DependsMap (依赖图)
- 序列化 PreloadDependencies (预加载依赖)
- 序列化 DataResourceMap (数据资源表)
- 序列化 GatherableTextDataMap (可收集文本数据)
- 序列化 ImportTypeHierarchies (导入类型层级)
- UE5 新增: 解析 PayloadTOC 和软对象路径表
- 修复 ImportMap、填充 InstancingContext、重定位引用

**关键方法:**
| 方法名 | 职责 |
|--------|------|
| SerializeNameMap() | 加载名称表，建立 FName 到字符串的映射 |
| SerializeImportMap() | 加载导入表，解析外部对象引用 |
| SerializeExportMap() | 加载导出表，记录本包对象元数据 |
| SerializeDependsMap() | 加载依赖图，建立对象间依赖关系 |
| SerializePreloadDependencies() | 加载预加载依赖列表 |
| SerializeDataResourceMap() | 加载数据资源表（UE5 DATA_RESOURCES） |
| SerializeSoftObjectPathList() | 加载软对象路径列表（UE5 ADD_SOFTOBJECTPATH_LIST） |
| SerializeGatherableTextDataMap() | 加载可收集文本数据 |
| SerializeMetaData() | 加载元数据（WITH_METADATA） |
| SerializeImportTypeHierarchies() | 加载导入类型层级（WITH_EDITORONLY_DATA，UE5 IMPORT_TYPE_HIERARCHIES） |
| SerializeThumbnails() | 加载缩略图 |
| FixupImportMap() | 修复导入映射（向后兼容重映射） |
| PopulateInstancingContext() | 生成实例化上下文重映射 |
| RelocateReferences() | 重定位引用 |
| ApplyInstancingContext() | 应用实例化上下文到软对象列表 |
| CreateExportHash() | 创建导出哈希表 |
| ConstructExportsReaders() | 创建导出读取器（WITH_TEXT_ARCHIVE_SUPPORT） |

**源码位置:** Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp

**交叉引用:** Import/Export 表结构见 [import-export-tables.md](../import-export-tables.md)

---

### Stage 3: 对象加载

创建 UObject 实例并序列化属性数据。

**职责:**
- 根据 ExportMap 创建 UObject 实例
- 加载对象依赖 (Preload)
- 序列化对象属性 (通过 FPropertyTag)
- 加载 BulkData 数据 (纹理、网格等)
- 查找已存在的导出对象（PIE/脚本编译场景）

**关键方法:**
| 方法名 | 职责 |
|--------|------|
| CreateExport() | 创建导出对象实例（private，按索引） |
| CreateExportAndPreload() | 创建导出对象并可选预加载（private） |
| Preload() | 预加载对象数据，触发属性序列化（public，override） |
| LoadAllObjects() | 加载包中所有对象（public） |
| FindExistingExport() | 在内存中查找已存在的导出对象（public） |
| FindExistingImport() | 在内存中查找已存在的导入对象（public） |
| GetExportLoadClass() | 获取导出的 UClass（private） |
| IndexToObject() | 将 FPackageIndex 解析为 UObject*（private） |

**源码位置:** Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp

**交叉引用:** 属性序列化机制见 [serialization/property-tag.md](property-tag.md)

---

### Stage 4: 后处理

完成引用修复和蓝图再生等延迟处理。

**职责:**
- 修复对象引用 (FixupExportMap)
- 解析所有导入 (ResolveAllImports)
- 蓝图类再生 (RegenerateBlueprintClass)
- 解析延迟依赖 (ResolveDeferredDependencies)
- 完成蓝图最终化 (FinalizeBlueprint)
- 完成链接器创建 (FinalizeCreation)

**关键方法:**
| 方法名 | 职责 |
|--------|------|
| FixupExportMap() | 修复导出对象引用（public） |
| ResolveAllImports() | 遍历 ImportMap 逐个创建/解析导入（private） |
| VerifyImport() | 验证单个导入对象有效性（public，含重定向处理） |
| VerifyImportInner() | 导入验证内部实现（private） |
| FinalizeBlueprint() | 完成蓝图加载（private，参数 UClass*） |
| RegenerateBlueprintClass() | 再生蓝图类（private） |
| ResolveDeferredDependencies() | 解析延迟依赖（private，参数 UStruct*） |
| ResolveDeferredExports() | 解析延迟导出（private） |
| FindExistingExports() | 匹配已有导出（PIE/脚本编译）（private） |
| FinalizeCreation() | 最终完成链接器创建（private） |

**源码位置:** Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp

**交叉引用:** BulkData 加载机制见 [serialization/bulkdata.md](bulkdata.md)

---

## 源码引用

### 关键文件

| 文件路径 | 用途 |
|----------|------|
| Runtime/CoreUObject/Public/UObject/LinkerLoad.h | FLinkerLoad 类定义 |
| Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp | 加载流程实现 |
| Runtime/CoreUObject/Public/UObject/Linker.h | FLinker 基类定义 + FLinkerTables + FCompressedChunk |
| Runtime/CoreUObject/Public/UObject/PackageFileSummary.h | FPackageFileSummary 定义 |
| Runtime/CoreUObject/Public/UObject/ObjectResource.h | FObjectImport/Export/FPackageIndex/FObjectDataResource 定义 |
| Runtime/Core/Public/UObject/ObjectVersion.h | FPackageFileVersion + 版本枚举 |

### 流程入口

| 入口方法 | 说明 |
|----------|------|
| GetPackageLinker() | 全局函数，包加载主入口（Linker.h） |
| FLinkerLoad::CreateLinker() | 同步创建链接器（static） |
| FLinkerLoad::CreateLinkerAsync() | 异步创建链接器（static） |
| FLinkerLoad::FindExistingExport() | 查找内存中已存在的导出对象 |
| FLinkerLoad::IndexToObject() | 将 FPackageIndex 解析为 UObject* |
| FLinkerLoad::Preload() | 预加载对象（触发属性序列化） |

---

## 版本差异

### UE5 新增流程

| 特性 | 说明 | 相关版本 |
|------|------|----------|
| PackageTrailer 处理 | Stage 1 新增 PackageTrailer 序列化（链接器创建阶段） | PAYLOAD_TOC |
| PayloadTOC 解析 | Stage 1 新增 PayloadTOC 表加载 | PAYLOAD_TOC |
| 软对象路径表 | Stage 2 新增 SoftObjectPathList 序列化 | ADD_SOFTOBJECTPATH_LIST |
| FPropertyTypeName | Stage 3 属性序列化使用完整类型名 | PROPERTY_TAG_COMPLETE_TYPE_NAME |
| DataResource 表 | Stage 2 新增数据资源表加载 | DATA_RESOURCES |
| Verse Cell 表 | Stage 2 新增 Cell 导入/导出表 | VERSE_CELLS |
| 导入类型层级 | Stage 2 新增导入类型层级表 | IMPORT_TYPE_HIERARCHIES |
| 脚本序列化偏移 | FObjectExport 新增 ScriptSerializationStartOffset/EndOffset | SCRIPT_SERIALIZATION_OFFSET |
| 元数据序列化偏移 | Stage 2 新增元数据偏移支持 | METADATA_SERIALIZATION_OFFSET |

### UE4 兼容处理

| 场景 | 处理方式 |
|------|----------|
| 旧版本魔数 | 支持 PACKAGE_FILE_TAG_SWAPPED (字节序交换) |
| UE4 版本号 | FileVersionUE4 字段单独处理 |
| 无 PackageTrailer | Stage 1 跳过 Trailer 处理 |
| 无 PayloadTOC | 使用 BulkDataStartOffset 定位数据 |

### 版本判断示例

加载流程中的版本判断使用 FPackageFileVersion（注意：无 GetUE4Version()/GetUE5Version() getter，直接访问公有成员或使用运算符重载）：

```cpp
FPackageFileVersion Version = Linker->Summary.GetFileVersionUE();

// UE4 版本判断（直接访问公有成员）
if (Version.FileVersionUE4 >= VER_UE4_XXX) {
    // 处理 UE4 特定版本逻辑
}

// UE5 版本判断（使用运算符重载与枚举直接比较）
if (Version >= EUnrealEngineObjectUE5Version::PAYLOAD_TOC) {
    // 处理 UE5 PayloadTOC
}
```

详见 [serialization/version-compatibility.md](version-compatibility.md) 版本兼容机制。