---
title: UE 源码对照
section: ue-reference
---

# UE 源码对照

本文档建立 uasset_read 模块与 Unreal Engine C++ 源码的对应关系，确保每个解析逻辑都能追溯到 UE 源码定义。

## 核心原则

```
禁止直接读取/猜测二进制格式
├── ❌ 错误：读二进制 → 猜字段含义 → 实现
└── ✅ 正确：查 UE 源码 → 理解结构定义 → 实现

输出必须可追溯到 C++ 定义
├── 每个解析字段必须对应 UE 源码字段
└── 文档必须标注源码位置
```

## UE 类对应关系

| UE 类 | 源码位置 | 本包对应模块 |
|-------|----------|--------------|
| `FArchive` | `Runtime/Core/Public/Serialization/Archive.h` | `archive.py` |
| `FPackageFileSummary` | `Runtime/CoreUObject/Public/UObject/PackageFileSummary.h` | `serializers/package_file_summary.py` |
| `FLinkerLoad` | `Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp` | `link/linker.py` |
| `UPackage` | `Runtime/CoreUObject/Public/UObject/Package.h` | `package.py` |
| `UObject` | `Runtime/CoreUObject/Public/UObject/Object.h` | `link/` — `UObjectInstance` |
| `FName` | `Runtime/Core/Public/UObject/Name.h` | `archive.py` — `read_fstring()` / NameMap |
| `FPropertyTag` | `Runtime/CoreUObject/Public/UObject/PropertyTag.h` | `serializers/property_tag.py` |
| `UBlueprint` | `Engine/Classes/Engine/Blueprint.h` | `blueprint/` |
| `UEdGraph` | `Engine/Classes/EdGraph/EdGraph.h` | `graph/` |
| `UEdGraphNode` | `Engine/Classes/EdGraph/EdGraphNode.h` | `models/node.py` |
| `UEdGraphPin` | `Engine/Classes/EdGraph/EdGraphPin.h` | `models/pin.py` |
| `Kismet VM` | `Engine/Private/Kismet/ScriptStack.cpp` | `kismet/` |
| `FBlueprintCompileReinstancer` | `Engine/Private/Kismet2/KismetReinstanceUtilities.cpp` | `blueprint/` |
| `FPakFile` | `Runtime/PakFile/Public/IPlatformFilePak.h` | `pak/` |
| `FIoStoreReader` | `Runtime/Core/Public/Serialization/IoStoreReader.h` | `iostore/` |
| `FPackageFileVersion` | `Runtime/CoreUObject/Public/UObject/PackageFileSummary.h` | `versioning.py` — `FPackageFileVersion` |
| `FCustomVersion` | `Runtime/Core/Public/Serialization/CustomVersion.h` | `versioning.py` — `VersionContainer` |
| `FObjectExport` | `Runtime/CoreUObject/Public/UObject/ObjectResource.h` | `serializers/export_map.py` |
| `FObjectImport` | `Runtime/CoreUObject/Public/UObject/ObjectResource.h` | `serializers/import_map.py` |
| `FNameMap` | `Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp` | `parse_uasset.py` — 内置 NameMap |

## 版本对应关系

### UE5 文件版本（FileVersionUE5）

| 版本值 | UE 版本 | 关键特性 | 常量名 |
|--------|---------|----------|--------|
| 1000 | UE 5.0 | 大世界坐标（LWC）基础 | `UE5_VERSION_MIN` |
| 1001 | UE 5.1 | SoftObjectPath 列表、名称引用 | `UE5_NAMES_REFERENCED_FROM_EXPORT_DATA` |
| 1002 | UE 5.2 | PayloadTOC 支持 | `UE5_PAYLOAD_TOC` |
| 1003 | UE 5.3 | 可选资源 | `UE5_OPTIONAL_RESOURCES` |
| 1004 | UE 5.4 | 大世界坐标完全体 | `UE5_LARGE_WORLD_COORDINATES` |
| 1005 | UE 5.5 | 移除 ObjectExport PackageGuid | `UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID` |
| 1006 | UE 5.5+ | Track ObjectExport IsInherited | `UE5_TRACK_OBJECT_EXPORT_IS_INHERITED` |
| 1007 | UE 5.5+ | FSoftObjectPath 移除 AssetPath FNames | `UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES` |
| 1008 | UE 5.5+ | Add SoftObjectPath List 完全体 | `UE5_ADD_SOFTOBJECTPATH_LIST` |
| 1009 | UE 5.4+ | 数据资源 | `UE5_DATA_RESOURCES` |
| 1010 | UE 5.4+ | 脚本序列化偏移 | `UE5_SCRIPT_SERIALIZATION_OFFSET` |
| 1011 | UE 5.4+ | PropertyTag 扩展 | `UE5_PROPERTY_TAG_EXTENSION` |
| 1012 | UE 5.5+ | PropertyTag 完整类型名 | `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME` |
| 1013 | UE 5.5+ | AssetRegistry PackageBuildDependencies | `UE5_ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES` |
| 1014 | UE 5.5+ | 元数据序列化偏移 | `UE5_METADATA_SERIALIZATION_OFFSET` |
| 1015 | UE 5.6 | Verse Cells | `UE5_VERSE_CELLS` |
| 1016 | UE 5.6+ | Package Saved Hash | `UE5_PACKAGE_SAVED_HASH` |
| 1017 | UE 5.6+ | OS Sub-Object Shadow Serialization | `UE5_OS_SUB_OBJECT_SHADOW_SERIALIZATION` |
| 1018 | UE 5.6+ | Import Type Hierarchies | `UE5_IMPORT_TYPE_HIERARCHIES` |

### UE4 文件版本（FileVersionUE4）

| 版本值 | UE 版本 | 关键特性 | 常量名 |
|--------|---------|----------|--------|
| 516 | UE 4.23 | 包摘要本地化 ID、字符串资产引用映射 | `UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID` |
| 517 | UE 4.24 | 包内文本序列化 | `UE4_SERIALIZE_TEXT_IN_PACKAGES` |
| 518 | UE 4.25 | 可搜索名称 | `UE4_ADDED_SEARCHABLE_NAMES` |
| 519 | UE 4.26 | 包所有者 | `UE4_ADDED_PACKAGE_OWNER` |
| 520 | UE 4.27 | 非外部包导入 | `UE4_NON_OUTER_PACKAGE_IMPORT` |

### CustomVersion 版本流

| 版本流 | GUID | 说明 |
|--------|------|------|
| Framework | `CFFC743F-43B04480-939114DF-171D2073` | 图/引脚序列化版本 |
| UE5 Mainstream | `697DD581-E64F41AB-AA4A51EC-BEB7B628` | UE5 主流程版本 |
| Release | `9C54D522-A8264FBE-94210746-61B482D0` | 发布版本流 |
| UE5 Release Stream | `D89B5E42-24BD4D46-8412ACA8-DF641779` | UE5 发布流 |
| Blueprints | `B0D832E4-1F89-4D06-B39A-8F1B5E1B2A4B` | 蓝图子系统版本 |
| Core | `371EC2EE-4CD7-4C38-AEB1-B7D6F539A54B` | 核心子系统版本 |
| Editor | `E4B068ED-F494-42E9-A231-DA0B0E4C5E56` | 编辑器版本 |
| Anim | `29E575DD-E0A3-4682-9C20-D1CF1B5E8DEF` | 动画子系统版本 |
| Physics | `78F01B33-BEA0-46A0-8BAF-6C4F4E23F8C1` | 物理子系统版本 |
| Rendering | `645F75DB-7F54-4C64-A1E2-2F6F3B4B8A5E` | 渲染子系统版本 |

### 关键版本阈值

| 常量 | 值 | 说明 |
|------|-----|------|
| `UE5_LEGACY_VERSION` | -9 | UE5.6+ 文件的 LegacyFileVersion 固定值 |
| `PROPERTY_TAG_COMPLETE_TYPE_NAME` | 1012 | PropertyTag 使用完整类型名的切换阈值 |
| `FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE` | 15 | 引脚容器类型序列化版本 |
| `FFRAMEWORK_VERSION_PINS_STORE_FNAME` | 19 | 引脚存储 FName 版本 |
| `FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX` | 50 | 引脚 SourceIndex 版本 |
| `FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER` | 10 | 引脚类型 UObjectWrapper 版本 |

## 包标志（Package Flags）

| 标志 | 值 | UE 源码 | 说明 |
|------|-----|---------|------|
| `PKG_Cooked` | `0x200` | `EPackageFlags::PKG_Cooked` | 已烘焙包（数据已被剥离） |
| `PKG_UnversionedProperties` | `0x2000` | `EPackageFlags::PKG_UnversionedProperties` | 使用无版本属性序列化 |
| `PKG_FilterEditorOnly` | `0x80000000` | `EPackageFlags::PKG_FilterEditorOnly` | 过滤编辑器专属对象 |

## PropertyTag 标志

| 标志 | 值 | 说明 |
|------|-----|------|
| `PROP_TAG_NONE` | `0x00` | 无标志 |
| `PROP_TAG_HAS_ARRAY_INDEX` | `0x01` | ArrayIndex 字段存在 |
| `PROP_TAG_HAS_PROPERTY_GUID` | `0x02` | PropertyGuid 字段存在 |
| `PROP_TAG_HAS_EXTENSIONS` | `0x04` | 扩展数据存在 |
| `PROP_TAG_HAS_BINARY_OR_NATIVE` | `0x08` | 二进制/原生序列化 |
| `PROP_TAG_BOOL_TRUE` | `0x10` | Bool 值为 true |
| `PROP_TAG_SKIPPED_SERIALIZE` | `0x20` | 跳过序列化 |

## 文件魔术标签

| 常量 | 值 | 说明 |
|------|-----|------|
| `PACKAGE_FILE_TAG` | `0x9E2A83C1` | 正确字节序魔术标签 |
| `PACKAGE_FILE_TAG_SWAPPED` | `0xC1832A9E` | 字节序交换后的魔术标签 |

## UE 加载流程

```
用户双击 Content Browser 中的资产
        │
        ▼
SContentBrowser::OnItemsActivated()
        │
        ▼
IAssetTypeActions::OpenAssetEditor() / AssetDefinition::OpenAssets()
        │
        ▼
FAssetData::GetAsset() 或 LoadPackage()
        │
        ▼
LoadPackageInternal() → FLinkerLoad::CreateLinkerAsync()
        │
        ▼
FLinkerLoad::ProcessPackageSummary()  ← 读取文件头、验证版本
        │
        ▼
FLinkerLoad::Tick() → LoadAllObjects() → 序列化导出表
        │
        ▼
FinalizeCreation() → PostLoad() → 资产就绪
```

### 加载阶段详解

| 阶段 | UE 函数 | 说明 |
|------|---------|------|
| 1. 包摘要处理 | `ProcessPackageSummary()` | 读取并验证包文件头、引擎版本、文件格式 |
| 2. 导入表加载 | — | 加载所有导入表条目（引用的外部对象） |
| 3. 导出表处理 | — | 读取导出表条目（本包内存储的对象），创建 UObject 实例 |
| 4. 对象序列化 | `Tick()` / `LoadAllObjects()` | 序列化所有对象数据，调用 `Preload()` 序列化属性 |
| 5. 创建完成 | `FinalizeCreation()` | 连接对象图，标记包为完全加载 |

## 关键源码路径索引

| 文件 | UE 源码路径 | 说明 |
|------|-------------|------|
| PackageFileSummary.h | `Runtime/CoreUObject/Public/UObject/` | 文件头结构 |
| ObjectVersion.h | `Runtime/Core/Public/UObject/` | 版本号定义 |
| ObjectResource.h | `Runtime/CoreUObject/Public/UObject/` | Import/Export 表结构 |
| LinkerLoad.h | `Runtime/CoreUObject/Public/UObject/` | 加载逻辑 |
| LinkerLoad.cpp | `Runtime/CoreUObject/Private/UObject/` | 274KB 核心实现 |
| PropertyTag.h | `Runtime/CoreUObject/Public/UObject/` | 属性标签 |
| BulkData.h | `Runtime/CoreUObject/Public/Serialization/` | BulkData 结构 |
| Archive.h | `Runtime/Core/Public/Serialization/` | FArchive 基类 |
| CustomVersion.h | `Runtime/Core/Public/Serialization/` | 自定义版本系统 |
| Package.h | `Runtime/CoreUObject/Public/UObject/` | UPackage 定义 |
| Blueprint.h | `Engine/Classes/Engine/` | UBlueprint 定义 |
| EdGraph.h | `Engine/Classes/EdGraph/` | UEdGraph 定义 |
| EdGraphPin.h | `Engine/Classes/EdGraph/` | UEdGraphPin 定义 |
| ScriptStack.cpp | `Engine/Private/Kismet/` | Kismet VM 执行 |

## 安全边界常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `MAX_NAME_COUNT` | 10,000,000 | 名称表最大条目数 |
| `MAX_IMPORT_COUNT` | 1,000,000 | 导入表最大条目数 |
| `MAX_EXPORT_COUNT` | 1,000,000 | 导出表最大条目数 |
| `MAX_CUSTOM_VERSIONS` | 10,000 | 自定义版本最大条目数 |
| `MAX_PROPERTY_COUNT` | 10,000 | 属性循环上限 |
| `MAX_ARRAY_COUNT` | 1,000,000 | ArrayProperty 最大元素数 |
| `MAX_FSTRING_LENGTH` | 10 MB | FString 最大长度 |
| `MAX_PINS_PER_NODE` | 1,000 | 单节点最大引脚数 |
| `MAX_NODES_PER_GRAPH` | 5,000 | 单图最大节点数 |
| `MAX_LINKEDTO_PER_PIN` | 100 | 单引脚最大连接数 |
| `MAX_TYPENODE_NODES` | 20 | FPropertyTypeName 最大节点数 |

## 外部参考

- `docs/formats/uasset/` — UE .uasset 格式文档（60+ Markdown 文件），`Index.md` 为主索引
- `docs/formats/uasset/serialization/` — 序列化机制参考
- `docs/formats/uasset/cooked/` — Cooked 格式参考
- `docs/formats/uasset/version/` — 版本演进参考
- `docs/formats/uasset/assets/` — 资产类型参考
- `docs/reference/` — 蓝图节点文本参考、UE 加载流程、蓝图转 C++ 指南
- `external/CUE4Parse/` — C# 参考实现，用于交叉验证解析逻辑
