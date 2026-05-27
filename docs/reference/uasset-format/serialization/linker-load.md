# LinkerLoad 加载流程

## 概述

LinkerLoad 是 .uasset 文件加载的核心类，负责将磁盘上的包文件完整加载到内存对象。它继承自 FLinker，协调文件头解析、表结构加载、对象创建和后处理四个阶段，是 UObject 加载系统的关键组件。

加载流程从 FPackageFileSummary 开始，逐步构建 NameMap、ImportMap、ExportMap，然后按依赖顺序创建 UObject 并序列化属性，最后进行引用修复和蓝图再生等后处理。

## 阶段划分

### Stage 1: 文件头读取

验证文件类型并解析包文件摘要结构。

**职责:**
- 验证文件魔数 (PACKAGE_FILE_TAG = 0x9E2A83C1)
- 读取双版本号 (FileVersionUE4/UE5)
- 解析 FPackageFileSummary 各字段
- 获取各表的偏移和数量信息

**关键方法:**
| 方法名 | 职责 |
|--------|------|
| SerializePackageFileSummaryInternal() | 内部序列化文件头结构 |
| VerifyPackageFileSummary() | 验证文件头有效性 |

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
- UE5 新增: 解析 PayloadTOC 和软对象路径表

**关键方法:**
| 方法名 | 职责 |
|--------|------|
| SerializeNameMap() | 加载名称表，建立 FName 到字符串的映射 |
| SerializeImportMap() | 加载导入表，解析外部对象引用 |
| SerializeExportMap() | 加载导出表，记录本包对象元数据 |
| SerializeDependsMap() | 加载依赖图，建立对象间依赖关系 |

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

**关键方法:**
| 方法名 | 职责 |
|--------|------|
| CreateExport() | 创建导出对象实例 |
| Preload() | 预加载对象数据，触发属性序列化 |
| VerifyImport() | 验证导入对象有效性 |
| CreateClassAndStructExports() | 创建类和结构体导出 |

**源码位置:** Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp

**交叉引用:** 属性序列化机制见 [serialization/property-tag.md](property-tag.md)

---

### Stage 4: 后处理

完成引用修复和蓝图再生等延迟处理。

**职责:**
- 修复对象引用 (FixupExportMap)
- 验证所有导入对象 (VerifyImports)
- 蓝图类再生 (RegenerateBlueprintClass)
- 解析延迟依赖 (ResolveDeferredDependencies)
- UE5 新增: 处理 PackageTrailer

**关键方法:**
| 方法名 | 职责 |
|--------|------|
| FixupExportMap() | 修复导出对象引用 |
| VerifyImports() | 验证所有导入对象 |
| FinalizeBlueprint() | 完成蓝图加载 |
| ResolveDeferredDependencies() | 解析延迟依赖 |

**源码位置:** Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp

**交叉引用:** BulkData 加载机制见 [serialization/bulkdata.md](bulkdata.md)

---

## 源码引用

### 关键文件

| 文件路径 | 用途 |
|----------|------|
| Runtime/CoreUObject/Public/UObject/LinkerLoad.h | LinkerLoad 类定义 |
| Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp | 加载流程实现 |
| Runtime/CoreUObject/Public/UObject/Linker.h | FLinker 基类定义 |
| Runtime/CoreUObject/Public/UObject/PackageFileSummary.h | FPackageFileSummary 定义 |
| Runtime/CoreUObject/Public/UObject/ObjectResource.h | FObjectImport/Export 定义 |

### 流程入口

| 入口方法 | 说明 |
|----------|------|
| FLinkerLoad::CreateLinker() | 创建链接器入口 |
| FLinkerLoad::LoadPackage() | 包加载入口 |
| FLinkerLoad::GetExport() | 获取导出对象 |

---

## 版本差异

### UE5 新增流程

| 特性 | 说明 | 相关版本 |
|------|------|----------|
| PackageTrailer 处理 | Stage 4 新增 PackageTrailer 解析 | PAYLOAD_TOC |
| PayloadTOC 解析 | Stage 2 新增 PayloadTOC 表加载 | PAYLOAD_TOC |
| 软对象路径表 | Stage 2 新增 SoftObjectPaths 表序列化 | — |
| FPropertyTypeName | Stage 3 属性序列化使用完整类型名 | UE5.4+ |
| DataResource 表 | Stage 2 新增数据资源表加载 | DATA_RESOURCES |

### UE4 兼容处理

| 场景 | 处理方式 |
|------|----------|
| 旧版本魔数 | 支持 PACKAGE_FILE_TAG_SWAPPED (字节序交换) |
| UE4 版本号 | FileVersionUE4 字段单独处理 |
| 无 PackageTrailer | Stage 4 跳过 Trailer 处理 |
| 无 PayloadTOC | 使用 BulkDataStartOffset 定位数据 |

### 版本判断示例

加载流程中的版本判断使用 FPackageFileVersion:

```
FPackageFileVersion Version = Linker->Summary.GetFileVersionUE();

// UE4 版本判断
if (Version.GetUE4Version() >= VER_UE4_XXX) {
    // 处理 UE4 特定版本逻辑
}

// UE5 版本判断
if (Version.GetUE5Version() >= EUnrealEngineObjectUE5Version::PAYLOAD_TOC) {
    // 处理 UE5 PayloadTOC
}
```

详见 [serialization/version-compatibility.md](version-compatibility.md) 版本兼容机制。