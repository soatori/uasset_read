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
| PackageName | FName | 包名 | UE5 WITH_EDITORONLY_DATA |
| SourceIndex | int32 | 源链接器导出索引（Transient） | — |
| bImportOptional | bool | 是否来自可选包 | — |

## FObjectExport 字段表

FObjectExport 继承自 FObjectResource，存储本包导出对象：

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| ObjectName | FName | 对象名称（继承自 FObjectResource） | — |
| OuterIndex | FPackageIndex | 外层对象引用（继承） | — |
| ClassIndex | FPackageIndex | 类引用 | — |
| SuperIndex | FPackageIndex | 父类引用（仅 UStruct） | — |
| TemplateIndex | FPackageIndex | 模板/原型引用 | — |
| ObjectFlags | EObjectFlags | 对象标志 | — |
| SerialSize | int64 | 序列化数据大小 | — |
| SerialOffset | int64 | 序列化数据偏移（文件位置） | — |
| ScriptSerializationStartOffset | int64 | 脚本序列化起始偏移 | UE5 新增 |
| ScriptSerializationEndOffset | int64 | 脚本序列化结束偏移 | UE5 新增 |
| bForcedExport | bool | 是否强制导出（跨包引用） | — |
| bNotForClient | bool | 客户端不加载 | — |
| bNotForServer | bool | 服务器不加载 | — |
| bIsAsset | bool | 是否为资产对象 | — |
| bIsInheritedInstance | bool | 是否为继承实例 | UE5 TRACK_OBJECT_EXPORT_IS_INHERITED |
| bGeneratePublicHash | bool | 是否生成公共哈希 | UE5 新增 |
| PackageFlags | uint32 | 强制导出的包标志 | — |
| FirstExportDependency | int32 | 依赖项起始索引 | — |
| SerializationBeforeSerializationDependencies | int32 | 序列化前依赖数量 | — |
| CreateBeforeSerializationDependencies | int32 | 创建前序列化依赖数量 | — |
| SerializationBeforeCreateDependencies | int32 | 序列化前创建依赖数量 | — |
| CreateBeforeCreateDependencies | int32 | 创建前创建依赖数量 | — |
| WeakReferences | int32 | 弱引用数量 | — |

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