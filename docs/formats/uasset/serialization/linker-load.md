# LinkerLoad 加载流程

## 概述

LinkerLoad 是 .uasset 文件加载的核心类，负责将磁盘上的包文件完整加载到内存对象。它继承自 FLinker 和 FArchiveUObject，协调文件头解析、表结构加载、对象创建和后处理四个阶段，是 UObject 加载系统的关键组件。

加载流程从 FPackageFileSummary 开始，逐步构建 NameMap、Import/Export 表、依赖关系，最终创建 UObject 实例。

## 加载阶段

### Phase 1: 文件头解析

1. 读取文件魔数验证 (PACKAGE_FILE_TAG)
2. 读取 LegacyFileVersion 确定格式世代
3. 根据 LegacyFileVersion 读取对应的版本信息
4. 解析 FPackageFileSummary 全部字段
5. 验证 TotalHeaderSize 和文件完整性

### Phase 2: 名称表加载

1. 定位 NameOffset，读取 NameCount 个 FNameEntry
2. 构建 NameMap（名称到索引的映射）
3. 处理 NamesReferencedFromExportDataCount（UE5+）

### Phase 3: Import/Export 表加载

1. 定位 ImportOffset，读取 ImportCount 个 FObjectImport
2. 定位 ExportOffset，读取 ExportCount 个 FObjectExport
3. 解析 FPackageIndex 引用关系
4. 构建对象层级关系树

### Phase 4: 依赖映射加载

1. 定位 DependsOffset，读取依赖映射数据
2. 解析软包引用（UE4+）
3. 处理预加载依赖（Cooked 文件）

### Phase 5: 对象创建 (CreateExport)

1. 遍历 Export 表，为每个导出条目创建 UObject
2. 解析 Outer/Template 关系
3. 处理 ClassIndex 和 SuperIndex 引用

### Phase 6: 预加载 (Preload)

1. 根据 Export 表的 SerialOffset/SerialSize 定位序列化数据
2. 解析 FPropertyTag 和属性数据
3. 处理对象引用重定向

## 关键方法

| 方法 | 说明 |
|------|------|
| `operator<<` | 序列化文件头和各表数据 |
| `CreateExport` | 为 Export 条目创建 UObject 实例 |
| `Preload` | 预加载对象的序列化数据 |
| `FinalizeCreation` | 后处理，完成对象初始化 |

## 源码引用

- `Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp` — LinkerLoad 主实现
- `Runtime/CoreUObject/Public/UObject/Linker.h` — FLinker 基类定义
- `Runtime/CoreUObject/Public/UObject/LinkerLoad.h` — LinkerLoad 类定义
