# 版本兼容机制 (Version Compatibility)

## 概述

版本兼容机制是 UE 序列化系统的核心组成部分，确保不同版本引擎保存的资产能够正确加载。UE 通过双版本号机制（UE4/UE5）和 CustomVersion 自定义版本机制实现向后兼容和模块级版本控制。

本阶段覆盖版本判断机制、向后兼容处理逻辑和 CustomVersion 机制。具体的版本变更历史（枚举值、新增特性、迁移指南）将在 Phase 7 详细覆盖。

### 与 Phase 7 分工

| Phase | 覆盖内容 |
|-------|----------|
| Phase 2 | 版本判断机制、向后兼容处理逻辑、CustomVersion 机制 |
| Phase 7 | 版本变更历史（具体枚举值、新增特性、迁移指南） |

## 版本号结构

### FPackageFileVersion 双版本机制

UE5 引入双版本号机制，将 UE4 和 UE5 版本号分离管理，确保 UE4/UE5 资产互操作性。

| 字段 | 类型 | 说明 |
|------|------|------|
| FileVersionUE4 | int32 | UE4 版本号 (EUnrealEngineObjectUE4Version) |
| FileVersionUE5 | int32 | UE5 版本号 (EUnrealEngineObjectUE5Version) |

### 双版本号机制说明

| 版本类型 | 说明 | 枚举起始 |
|----------|------|----------|
| UE4Version | UE4 版本号 | VER_UE4_OLDEST_LOADABLE_PACKAGE = 214 |
| UE5Version | UE5 版本号 | INITIAL_VERSION = 1000 |
| 分离点 | UE5 从 1000 开始 | 避免与 UE4 版本冲突 |

### 核心方法

| 方法 | 说明 |
|------|------|
| ToValue() | 返回最高有效版本（优先返回 UE5 版本） |
| IsCompatible() | 检查是否与指定版本兼容 |
| CreateUE4Version() | 创建仅包含 UE4 版本的版本对象 |

文件头版本字段详见 [package-summary.md](../package-summary.md) FileVersionUE 字段说明。

## 向后兼容处理

### 最低可加载版本

| 常量 | 值 | 说明 |
|------|-----|------|
| VER_UE4_OLDEST_LOADABLE_PACKAGE | 214 | UE4 最低可加载版本 |
| GOldestLoadablePackageFileUEVersion | — | 全局最低可加载版本对象 |

版本低于 VER_UE4_OLDEST_LOADABLE_PACKAGE (214) 的包无法加载。加载器在读取文件头后会检查版本号，若版本过低则拒绝加载。

### 兼容性检查

IsCompatible() 方法用于检查版本兼容性：

| 检查条件 | 说明 |
|----------|------|
| FileVersionUE4 >= Other.FileVersionUE4 | UE4 版本号达标 |
| FileVersionUE5 >= Other.FileVersionUE5 | UE5 版本号达标 |

两个版本号都必须达标才能判定为兼容。

## 版本判断流程

### 版本判断示例

```
FArchive& Ar = ...;
FPackageFileVersion Version = Ar.UEVer();

// UE4 版本判断
if (Version >= VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG) {
    // 支持 StructGuid 序列化
}

// UE5 版本判断
if (Version >= EUnrealEngineObjectUE5Version::PAYLOAD_TOC) {
    // 支持 PayloadTOC
}
```

### 加载流程中的版本检查

| 检查时机 | 检查内容 | 说明 |
|----------|----------|------|
| 文件头读取 | 验证版本号 >= 最低可加载版本 | 拒绝加载过旧资产 |
| 属性序列化 | 检查特定版本特性 | 如 StructGuid、PropertyGuid |
| BulkData 序列化 | 检查 PayloadTOC 版本 | UE5 PayloadTOC 支持 |

加载流程中的版本检查详见 [linker-load.md](linker-load.md) 各阶段说明。

## CustomVersion

### CustomVersion 机制概述

CustomVersion 提供模块级版本控制，允许各模块独立管理版本号而不影响全局版本。通过 FGuid 标识模块，实现灵活的版本管理。

### 组成部分

| 组成 | 类型 | 说明 |
|------|------|------|
| FCustomVersionContainer | 类 | 自定义版本容器，存储所有模块版本 |
| FCustomVersion | 结构 | 单个模块版本记录 |
| FGuid | 类型 | 模块唯一标识（GUID） |
| UsingCustomVersion() | 方法 | 注册模块版本 |
| Key | FGuid | 模块标识键 |
| Version | int32 | 模块版本号 |

### CustomVersion 使用示例

常见模块 CustomVersion：

| 模块 | 说明 |
|------|------|
| FBlueprintsObjectVersion | 蓝图模块版本 |
| FEditorObjectVersion | 编辑器模块版本 |
| FCoreObjectVersion | 核心模块版本 |
| FAnimObjectVersion | 动画模块版本 |

CustomVersion 注册通过 UsingCustomVersion() 方法在序列化前完成，确保模块版本信息被正确写入文件头。

### 序列化格式

| 格式 | 说明 |
|------|------|
| Guids | GUID 格式（UE4 早期） |
| Enums | 枚举格式 |
| Optimized | 优化格式（当前使用） |

## 源码引用

### 核心文件

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本号定义（FPackageFileVersion、枚举） |
| CustomVersion.h | Runtime/Core/Public/Serialization/ | CustomVersion 结构定义 |
| LinkerLoad.cpp | Runtime/CoreUObject/Private/UObject/ | 加载流程中的版本判断逻辑 |
| PackageFileSummary.h | Runtime/CoreUObject/Public/UObject/ | 文件头版本字段定义 |

### 版本判断相关方法

| 方法 | 文件 | 说明 |
|------|------|------|
| SerializePackageFileSummaryInternal() | LinkerLoad.cpp | 文件头版本读取 |
| IsCompatible() | ObjectVersion.h | 版本兼容检查 |
| ToValue() | ObjectVersion.h | 获取最高有效版本 |

## 版本差异

### UE5 新增特性

| 特性 | 说明 |
|------|------|
| FileVersionUE5 字段 | UE5 版本号独立管理 |
| EUnrealEngineObjectUE5Version 枚举 | UE5 专用版本枚举 |
| 版本起始值 1000 | 与 UE4 版本号分离，避免冲突 |
| PAYLOAD_TOC | PayloadTOC 支持 |
| DATA_RESOURCES | 数据资源表支持 |
| PROPERTY_TAG_EXTENSION | 属性标签扩展支持 |

### UE4/UE5 版本判断差异

| 版本类型 | 判断方式 | 示例 |
|----------|----------|------|
| UE4 特性 | 使用 EUnrealEngineObjectUE4Version | `Version >= VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG` |
| UE5 特性 | 使用 EUnrealEngineObjectUE5Version | `Version >= EUnrealEngineObjectUE5Version::PAYLOAD_TOC` |

### FPackageFileVersion.operator>=() 行为

| 操作符 | 检查字段 | 说明 |
|--------|----------|------|
| >= EUnrealEngineObjectUE4Version | FileVersionUE4 | 仅检查 UE4 版本 |
| >= EUnrealEngineObjectUE5Version | FileVersionUE5 | 仅检查 UE5 版本 |

---

*Phase: 02-序列化机制*
*Created: 2026-04-29*