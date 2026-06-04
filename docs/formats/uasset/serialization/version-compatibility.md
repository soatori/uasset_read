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
| LicenseeVersion | 许可方版本号 | VER_LIC_NONE = 0 |

### EUnrealEngineObjectUE5Version 枚举（完整）

| 版本 | 值 | 说明 |
|------|-----|------|
| INITIAL_VERSION | 1000 | UE5 初始版本 |
| NAMES_REFERENCED_FROM_EXPORT_DATA | 1001 | 支持剥离未从导出数据引用的名称 |
| PAYLOAD_TOC | 1002 | 添加载荷查找表到包摘要 |
| OPTIONAL_RESOURCES | 1003 | 添加可选包引用标识数据 |
| LARGE_WORLD_COORDINATES | 1004 | 大世界坐标（双精度） |
| REMOVE_OBJECT_EXPORT_PACKAGE_GUID | 1005 | 从 FObjectExport 移除包 GUID |
| TRACK_OBJECT_EXPORT_IS_INHERITED | 1006 | 添加 IsInherited 到 FObjectExport |
| FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES | 1007 | FSoftObjectPath 使用 FTopLevelAssetPath |
| ADD_SOFTOBJECTPATH_LIST | 1008 | 添加软对象路径列表用于快速重映射 |
| DATA_RESOURCES | 1009 | 添加 Bulk/Data 资源表 |
| SCRIPT_SERIALIZATION_OFFSET | 1010 | 添加脚本序列化偏移到导出表 |
| PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION | 1011 | 属性标签扩展和可覆盖序列化 |
| PROPERTY_TAG_COMPLETE_TYPE_NAME | 1012 | 属性标签完整类型名和序列化类型 |
| ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES | 1013 | AssetRegistry 包含 PackageBuildDependencies |
| METADATA_SERIALIZATION_OFFSET | 1014 | 添加元数据序列化偏移 |
| VERSE_CELLS | 1015 | 添加 VCells 到对象图 |
| PACKAGE_SAVED_HASH | 1016 | PackageSavedHash 从 FGuid 改为 FIoHash |
| OS_SUB_OBJECT_SHADOW_SERIALIZATION | 1017 | 子对象 OS 阴影序列化 |
| IMPORT_TYPE_HIERARCHIES | 1018 | 添加导入类型层次信息表 |

### 核心方法

| 方法 | 说明 |
|------|------|
| ToValue() | 返回最高有效版本（优先返回 UE5 版本） |
| IsCompatible(FPackageFileVersion) | 检查是否与指定版本兼容 |
| CreateUE4Version(int32) | 创建仅包含 UE4 版本的版本对象 |
| CreateUE4Version(EUnrealEngineObjectUE4Version) | 创建仅包含 UE4 版本的版本对象（枚举重载） |
| Reset() | 重置所有版本为默认状态（0） |

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

### FPackageFileVersion 比较运算符

| 运算符 | 参数类型 | 检查字段 | 说明 |
|--------|----------|----------|------|
| >= | EUnrealEngineObjectUE4Version | FileVersionUE4 | 仅检查 UE4 版本 |
| >= | EUnrealEngineObjectUE5Version | FileVersionUE5 | 仅检查 UE5 版本 |
| < | EUnrealEngineObjectUE4Version | FileVersionUE4 | 仅检查 UE4 版本 |
| < | EUnrealEngineObjectUE5Version | FileVersionUE5 | 仅检查 UE5 版本 |
| == | FPackageFileVersion | 两者都检查 | 完全相等 |
| != | EUnrealEngineObjectUE4Version | FileVersionUE4 | UE4 版本不等 |
| != | EUnrealEngineObjectUE5Version | FileVersionUE5 | UE5 版本不等 |

## 版本判断流程

### 版本判断示例

```cpp
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
| UsingCustomVersion() | 方法 | 注册模块版本（FArchive 接口） |
| Key | FGuid | 模块标识键 |
| Version | int32 | 模块版本号 |
| ReferenceCount | int32 | 注册引用计数 |
| Validator | CustomVersionValidatorFunc | 可选验证函数 |
| FriendlyName | FName | 友好名称（用于错误消息） |

### FCustomVersionContainer 方法

| 方法 | 说明 |
|------|------|
| GetAllVersions() | 获取所有版本列表 |
| GetVersion(FGuid) | 获取指定 GUID 的版本 |
| GetFriendlyName(FGuid) | 获取指定 GUID 的友好名称 |
| SetVersion(FGuid, int32, FName) | 设置指定版本 |
| SetVersionUsingRegistry(FGuid, ESetCustomVersionFlags) | 使用注册表设置版本 |
| Serialize(FArchive&, ECustomVersionSerializationFormat) | 序列化 |
| Empty() | 清空容器 |
| SortByKey() | 按键排序 |

### ECustomVersionSerializationFormat 序列化格式

| 格式 | 说明 |
|------|------|
| Unknown | 未知格式 |
| Guids | GUID 格式（UE4 早期） |
| Enums | 枚举格式 |
| Optimized | 优化格式（当前使用） |
| Latest | 最新格式（自动选择） |

### ESetCustomVersionFlags 标志

| 标志 | 说明 |
|------|------|
| None | 无标志 |
| SkipUpdateExistingVersion | 跳过更新已有版本（不从注册表查询） |

### CustomVersion 使用示例

常见模块 CustomVersion：

| 模块 | 说明 |
|------|------|
| FBlueprintsObjectVersion | 蓝图模块版本 |
| FEditorObjectVersion | 编辑器模块版本 |
| FCoreObjectVersion | 核心模块版本 |
| FAnimObjectVersion | 动画模块版本 |

CustomVersion 注册通过 `UsingCustomVersion(const FGuid&)` 方法在序列化前完成，确保模块版本信息被正确写入文件头。

### FCustomVersionRegistration

通过全局变量注册自定义版本：

```cpp
// 模块中定义
static FCustomVersionRegistration GMyCustomVersionRegistration(
    MyCustomVersionGuid,    // FGuid
    LATEST_VERSION,         // 最新版本号
    TEXT("MyCustomVersion") // 友好名称
);

// 序列化时使用
Ar.UsingCustomVersion(MyCustomVersionGuid);
```

### FCurrentCustomVersions 线程安全访问

| 方法 | 说明 |
|------|------|
| GetAll() | 获取所有已注册的版本 |
| Get(const FGuid&) | 获取指定 GUID 的版本 |
| Compare(const FCustomVersionArray&, const TCHAR*) | 比较版本差异 |

### 版本差异检测

| 差异类型 | 说明 |
|----------|------|
| Missing | 模块版本缺失 |
| Newer | 包版本比当前引擎新 |
| Older | 包版本比当前引擎旧 |
| Invalid | 版本无效 |

## 源码引用

### 核心文件

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ObjectVersion.h | 版本号定义（FPackageFileVersion、枚举） |
| CustomVersion.h | Runtime/Core/Public/Serialization/CustomVersion.h | CustomVersion 结构定义 |
| LinkerLoad.cpp | Runtime/CoreUObject/Private/UObject/ | 加载流程中的版本判断逻辑 |
| PackageFileSummary.h | Runtime/CoreUObject/Public/UObject/ | 文件头版本字段定义 |

### 版本判断相关方法

| 方法 | 文件 | 说明 |
|------|------|------|
| SerializePackageFileSummaryInternal() | LinkerLoad.cpp | 文件头版本读取 |
| IsCompatible() | ObjectVersion.h | 版本兼容检查 |
| ToValue() | ObjectVersion.h | 获取最高有效版本 |
| CreateUE4Version() | ObjectVersion.h | 创建 UE4 版本对象 |
| Reset() | ObjectVersion.h | 重置版本 |

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
| LARGE_WORLD_COORDINATES | 大世界坐标（双精度） |
| SCRIPT_SERIALIZATION_OFFSET | 脚本序列化偏移 |
| METADATA_SERIALIZATION_OFFSET | 元数据序列化偏移 |
| PACKAGE_SAVED_HASH | 包哈希从 FGuid 改为 FIoHash |
| VERSE_CELLS | Verse VCell 支持 |
| IMPORT_TYPE_HIERARCHIES | 导入类型层次信息 |

### UE4/UE5 版本判断差异

| 版本类型 | 判断方式 | 示例 |
|----------|----------|------|
| UE4 特性 | 使用 EUnrealEngineObjectUE4Version | `Version >= VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG` |
| UE5 特性 | 使用 EUnrealEngineObjectUE5Version | `Version >= EUnrealEngineObjectUE5Version::PAYLOAD_TOC` |

### EUnrealEngineObjectLicenseeUEVersion 许可方版本

| 常量 | 值 | 说明 |
|------|-----|------|
| VER_LIC_NONE | 0 | 无许可方版本 |
| VER_LIC_AUTOMATIC_VERSION | 1 | 自动版本号 |

许可方版本独立于 UE4/UE5 版本，用于第三方许可方的自定义版本控制。

---

*Phase: 02-序列化机制*
*Created: 2026-04-29*
*Updated: 2026-06-01 — 对照 UE 源码更新*
