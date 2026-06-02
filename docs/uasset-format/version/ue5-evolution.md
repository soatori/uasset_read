# UE5 版本演进历史

## 概述

UE5 版本演进通过独立的 `EUnrealEngineObjectUE5Version` 枚举管理（`Runtime/Core/Public/UObject/ObjectVersion.h:40-109`），版本号从 `INITIAL_VERSION = 1000` 开始，与 UE4 版本号分离，避免冲突。双版本机制允许 UE4 代码库变更与 UE5 代码库独立演进，同时保持包文件互操作性。

本文档覆盖 UE5 关键版本变更历史。版本判断机制详见 [version-compatibility.md](../serialization/version-compatibility.md)。

### UE4 vs UE5 版本机制对比

| 特性 | UE4 | UE5 |
|------|-----|-----|
| 版本枚举 | EUnrealEngineObjectUE4Version | EUnrealEngineObjectUE5Version |
| 版本起始值 | 214 (最低可加载) | 1000 (INITIAL_VERSION) |
| 文件头字段 | FileVersionUE4 | FileVersionUE5 |
| 版本判断 | `Version >= VER_UE4_*` | `Version >= EUnrealEngineObjectUE5Version::*` |
| 自动版本 | VER_UE4_AUTOMATIC_VERSION (739) | AUTOMATIC_VERSION (1018) |

## 完整版本表格

> **源码同步状态**: 基于 `ObjectVersion.h` `EUnrealEngineObjectUE5Version` 枚举（INITIAL_VERSION 至 IMPORT_TYPE_HIERARCHIES）。

| 版本号 | 版本名 | 变更描述 | 影响资产 |
|-------|--------|---------|----------|
| 1000 | INITIAL_VERSION | UE5 初始版本，从 1000 开始避免冲突 | 所有资产 |
| 1001 | NAMES_REFERENCED_FROM_EXPORT_DATA | 支持剥离未引用的名称 | 所有资产 |
| 1002 | PAYLOAD_TOC | 文件头添加 PayloadTOC 表 | 所有资产 |
| 1003 | OPTIONAL_RESOURCES | 可选包引用追踪数据 | 所有资产 |
| 1004 | LARGE_WORLD_COORDINATES | 大世界坐标，核心类型转为 double | 网格、动画 |
| 1005 | REMOVE_OBJECT_EXPORT_PACKAGE_GUID | FObjectExport 移除 Package GUID | 所有资产 |
| 1006 | TRACK_OBJECT_EXPORT_IS_INHERITED | FObjectExport 添加 IsInherited 标志 | 所有资产 |
| 1007 | FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES | FSoftObjectPath 移除 FName 资产路径 | 所有资产 |
| 1008 | ADD_SOFTOBJECTPATH_LIST | 文件头添加软引用列表 | 所有资产 |
| 1009 | DATA_RESOURCES | 大数据资源表支持 | 所有资产 |
| 1010 | SCRIPT_SERIALIZATION_OFFSET | Export 表添加脚本序列化偏移 | 蓝图 |
| 1011 | PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION | 属性标签扩展、可覆盖序列化 | 所有资产 |
| 1012 | PROPERTY_TAG_COMPLETE_TYPE_NAME | 属性标签完整类型名称 | 所有资产 |
| 1013 | ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES | AssetRegistry 添加包构建依赖 | 所有资产 |
| 1014 | METADATA_SERIALIZATION_OFFSET | 元数据序列化偏移 | 所有资产 |
| 1015 | VERSE_CELLS | Verse VCells 支持 | 所有资产 |
| 1016 | PACKAGE_SAVED_HASH | 文件头使用 FIoHash 替代 FGuid | 所有资产 |
| 1017 | OS_SUB_OBJECT_SHADOW_SERIALIZATION | 子对象阴影序列化 | 蓝图 |
| 1018 | IMPORT_TYPE_HIERARCHIES | Import 表添加类型层级信息 | 所有资产 |

### UE5 新增特性说明

| 特性 | 版本 | 说明 |
|------|------|------|
| Large World Coordinates | 1004 | FVector 组件转为 double，支持大世界场景 |
| PayloadTOC | 1002 | 文件头 Payload 表，替代 BulkDataStartOffset |
| Data Resources | 1009 | 数据资源表，统一管理大数据块 |
| Property Tag Extension | 1011 | FPropertyTag 扩展字段，支持可覆盖序列化 |
| Import Type Hierarchies | 1018 | Import 表类型层级，加速类型查找 |
| Package Saved Hash | 1016 | FIoHash 替代 FGuid，支持 IoStore |
| Verse Cells | 1015 | Verse 单元格系统集成 |
| OS Sub-Object Shadow | 1017 | 操作系统子对象阴影序列化 |

### 版本分组说明

| 版本范围 | 主要变更类型 |
|----------|-------------|
| 1000-1004 | 初始化、名称剥离、PayloadTOC、大世界坐标 |
| 1005-1009 | Export 表重构、软引用优化、数据资源表 |
| 1010-1014 | 序列化偏移、属性标签扩展、AssetRegistry |
| 1015-1018 | Verse、Hash、阴影序列化、类型层级 |

## 源码引用

### 版本定义文件

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | UE5 版本枚举定义、FPackageFileVersion |

### 相关文件

| 文件 | 路径 | 说明 |
|------|------|------|
| PackageFileSummary.h | Runtime/CoreUObject/Public/UObject/ | 文件头版本字段、PayloadTOC |
| PackageTrailer.h | Runtime/CoreUObject/Public/UObject/ | UE5 文件尾结构 |
| version-compatibility.md | docs/serialization/ | 版本判断机制文档 |
| ue4-evolution.md | docs/version/ | UE4 版本演进文档 |

## 与 UE4 版本判断差异

### operator>=() 行为

| 操作数类型 | 检查字段 | 说明 |
|-----------|----------|------|
| EUnrealEngineObjectUE4Version | FileVersionUE4 | 仅检查 UE4 版本号 |
| EUnrealEngineObjectUE5Version | FileVersionUE5 | 仅检查 UE5 版本号 |

### 版本判断示例

```cpp
// UE5 特性判断
if (Version >= EUnrealEngineObjectUE5Version::PAYLOAD_TOC) {
    // 支持 PayloadTOC
}

if (Version >= EUnrealEngineObjectUE5Version::LARGE_WORLD_COORDINATES) {
    // 大世界坐标支持
}
```

## 自定义版本 (CustomVersion)

UE5 除全局版本外，还使用基于 GUID 的 CustomVersion 系统管理模块级版本变更：

| CustomVersion | GUID 关联文件 | 说明 |
|---------------|--------------|------|
| FAnimObjectVersion | AnimObjectVersion.h | 动画系统版本（骨骼索引、Groom、RigVM 等） |
| FBlueprintsObjectVersion | BlueprintsObjectVersion.h | 蓝图系统版本（函数标志、容器支持等） |
| FCoreObjectVersion | CoreObjectVersion.h | 核心版本（材质输入、属性系统等） |

---

*Phase: 07-版本演进历史*
*Created: 2026-04-29*
*Updated: 2026-06-01 — 基于 UE ObjectVersion.h EUnrealEngineObjectUE5Version 枚举同步，确认全部 18 个版本条目*
