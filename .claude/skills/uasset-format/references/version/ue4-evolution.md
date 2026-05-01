# UE4 版本演进历史

## 概述

UE4 版本演进通过 `EUnrealEngineObjectUE4Version` 枚举管理，每个版本号对应一个特定的格式变更。版本号从 `VER_UE4_OLDEST_LOADABLE_PACKAGE = 214` 开始，最终版本为 `VER_UE4_AUTOMATIC_VERSION`。版本低于 214 的包无法加载。

本文档覆盖 UE4 关键版本变更历史。版本判断机制详见 [version-compatibility.md](../serialization/version-compatibility.md)。

### 与 Phase 2 分工

| Phase | 覆盖内容 |
|-------|----------|
| Phase 2 | 版本判断机制、向后兼容处理、CustomVersion 机制 |
| Phase 7 | UE4/UE5 版本变更历史（具体枚举值、新增特性） |

## 关键版本表格

以下选取约 20 个关键版本，标注变更描述和影响的资产类型。

| 版本号 | 版本名 | 变更描述 | 影响资产 |
|-------|--------|---------|----------|
| 214 | VER_UE4_OLDEST_LOADABLE_PACKAGE | UE4 最低可加载版本 | 所有资产 |
| 216 | VER_UE4_BLUEPRINT_VARS_NOT_READ_ONLY | Blueprint 变量不再强制只读 | 蓝图 |
| 217 | VER_UE4_STATIC_MESH_STORE_NAV_COLLISION | 静态网格预计算导航碰撞 | 静态网格 |
| 220 | VER_UE4_MATERIAL_ATTRIBUTES_REORDERING | 材质属性重排序 | 材质 |
| 225 | VER_UE4_SPEEDTREE_STATICMESH | 静态网格支持 SpeedTree | 静态网格 |
| 226 | VER_UE4_MAX_TEXCOORD_INCREASED | 最大纹理坐标从 4 增至 8 | 网格、材质 |
| 228 | VER_UE4_APEX_CLOTH | APEX 服装支持 | 骨骼网格 |
| 236 | VER_UE4_SUPPORT_32BIT_STATIC_MESH_INDICES | 静态网格 32 位索引缓冲 | 静态网格 |
| 243 | VER_UE4_KEEP_SKEL_MESH_INDEX_DATA | 骨骼网格索引数据在内存中保留 | 骨骼网格 |
| 258 | VER_UE4_REFERENCE_SKELETON_REFACTOR | 骨骼层级重构为 FReferenceSkeleton | 骨骼网格 |
| 264 | VER_UE4_SUPPORT_8_BONE_INFLUENCES_SKELETAL_MESHES | 骨骼网格支持 8 骨骼影响 | 骨骼网格 |
| 286 | VER_UE4_CASE_PRESERVING_FNAME | FName 变为大小写保留 | 所有资产 |
| 337 | VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG | FPropertyTag 存储 Struct GUID | 所有资产 |
| 376 | VER_UE4_NAME_HASHES_SERIALIZED | 名称表哈希值序列化 | 所有资产 |
| 385 | VER_UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID | 文件头添加 LocalizationId | 所有资产 |
| 401 | VER_UE4_SERIALIZE_TEXT_IN_PACKAGES | 包内文本预收集优化 | 所有资产 |
| 426 | VER_UE4_ADDED_SOFT_OBJECT_PATH | FStringAssetReference → FSoftObjectPath | 所有资产 |
| 489 | VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS | Cooked 文件包含依赖图 | 所有 Cooked |
| 507 | VER_UE4_64BIT_EXPORTMAP_SERIALSIZES | Export 表 SerialSize/Offset 升为 64 位 | 所有资产 |
| 511 | VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT | FPropertyTag 支持 Set/Map 类型 | 所有资产 |
| 522 | VER_UE4_CORRECT_LICENSEE_FLAG | 修复 4.26 Licensee 标志损坏 | 所有资产 |

### 版本分组说明

| 版本范围 | 主要变更类型 |
|----------|-------------|
| 214-230 | Blueprint、静态网格、材质基础变更 |
| 231-260 | 骨骼网格、服装、物理重构 |
| 261-300 | 动画、地形、FName、文本变更 |
| 301-350 | Cooked、属性序列化、UMG 变更 |
| 351-400 | Localization、导航、软引用变更 |
| 401-500 | SoftObjectPath、纹理流式加载变更 |
| 501-522 | 64 位导出表、Set/Map 属性支持 |

## 源码引用

### 版本定义文件

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | UE4/UE5 版本枚举定义、FPackageFileVersion |

### 相关文件

| 文件 | 路径 | 说明 |
|------|------|------|
| PackageFileSummary.h | Runtime/CoreUObject/Public/UObject/ | 文件头版本字段 |
| LinkerLoad.cpp | Runtime/CoreUObject/Private/UObject/ | 加载流程版本判断 |
| version-compatibility.md | docs/serialization/ | 版本判断机制文档 |

## 与 Phase 2 的分工

Phase 2 的 [version-compatibility.md](../serialization/version-compatibility.md) 覆盖：
- 版本判断机制 (IsCompatible、ToValue)
- 向后兼容处理 (最低可加载版本)
- CustomVersion 自定义版本机制

本阶段覆盖：
- UE4 关键版本变更历史（具体枚举值）
- 每个版本变更的具体内容
- 影响的资产类型

---

*Phase: 07-版本演进历史*
*Created: 2026-04-29*