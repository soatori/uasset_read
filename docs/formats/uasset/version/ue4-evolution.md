# UE4 版本演进历史

## 概述

UE4 版本演进通过 `EUnrealEngineObjectUE4Version` 枚举管理（`Runtime/Core/Public/UObject/ObjectVersion.h`）。版本号从 `VER_UE4_OLDEST_LOADABLE_PACKAGE = 214` 开始，最终版本为 `VER_UE4_AUTOMATIC_VERSION`（当前为 739）。版本低于 214 的包无法加载。

本文档覆盖 UE4 关键版本变更历史。版本判断机制详见 [version-compatibility.md](../serialization/version-compatibility.md)。

### 与 Phase 2 分工

| Phase | 覆盖内容 |
|-------|----------|
| Phase 2 | 版本判断机制、向后兼容处理、CustomVersion 机制 |
| Phase 7 | UE4/UE5 版本变更历史（具体枚举值、新增特性） |

## 完整版本表格

> **源码同步状态**: 基于 `ObjectVersion.h` 完整枚举（VER_UE4_OLDEST_LOADABLE_PACKAGE 至 VER_UE4_CORRECT_LICENSEE_FLAG，共约 125 个版本宏）。以下按资产类型分组选取关键版本。

### 核心版本（影响所有资产）

| 版本号 | 版本名 | 变更描述 | 影响资产 |
|-------|--------|---------|----------|
| 214 | VER_UE4_OLDEST_LOADABLE_PACKAGE | UE4 最低可加载版本 | 所有资产 |
| 286 | VER_UE4_CASE_PRESERVING_FNAME | FName 变为大小写保留 | 所有资产 |
| 337 | VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG | FPropertyTag 存储 Struct GUID | 所有资产 |
| 376 | VER_UE4_NAME_HASHES_SERIALIZED | 名称表哈希值序列化 | 所有资产 |
| 385 | VER_UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID | 文件头添加 LocalizationId | 所有资产 |
| 401 | VER_UE4_SERIALIZE_TEXT_IN_PACKAGES | 包内文本预收集优化 | 所有 Cooked |
| 426 | VER_UE4_ADDED_SOFT_OBJECT_PATH | FStringAssetReference → FSoftObjectPath | 所有资产 |
| 489 | VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS | Cooked 文件包含依赖图 | 所有 Cooked |
| 507 | VER_UE4_64BIT_EXPORTMAP_SERIALSIZES | Export 表 SerialSize/Offset 升为 64 位 | 所有资产 |
| 511 | VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT | FPropertyTag 支持 Set/Map 类型 | 所有资产 |
| 522 | VER_UE4_CORRECT_LICENSEE_FLAG | 修复 4.26 Licensee 标志损坏 | 所有资产 |

### 蓝图版本

| 版本号 | 版本名 | 变更描述 |
|-------|--------|---------|
| 216 | VER_UE4_BLUEPRINT_VARS_NOT_READ_ONLY | Blueprint 变量不再强制只读 |
| 225 | VER_UE4_BLUEPRINT_SKEL_TEMPORARY_TRANSIENT | Skeleton 类临时瞬态化 |
| 227 | VER_UE4_BLUEPRINT_SKEL_SERIALIZED_AGAIN | Skeleton 类重新序列化 |
| 229 | VER_UE4_BLUEPRINT_SETS_REPLICATION | Blueprint 设置复制 |
| 250 | VER_UE4_ADDED_SKELETON_ARCHIVER_REMOVAL | Skeleton Archiver 移除 |
| 253 | VER_UE4_ADDED_SKELETON_ARCHIVER_REMOVAL_SECOND_TIME | Skeleton Archiver 移除第二次 |
| 256 | VER_UE4_BLUEPRINT_SKEL_CLASS_TRANSIENT_AGAIN | Skeleton 类瞬态化 |
| 311 | VER_UE4_K2NODE_REFERENCEGUIDS | Blueprint 节点引用 Guid |
| 323 | VER_UE4_BLUEPRINT_INPUT_BINDING_OVERRIDES | Blueprint 输入绑定覆盖 |
| 349 | VER_UE4_BP_ACTOR_VARIABLE_DEFAULT_PREVENTING | Blueprint Actor 变量默认值阻止 |
| 406 | VER_UE4_FIX_BLUEPRINT_VARIABLE_FLAGS | Blueprint 变量标志修复 |
| 430 | VER_UE4_POST_DUPLICATE_NODE_GUID | Blueprint 复制后节点 Guid |
| 466 | VER_UE4_BLUEPRINT_GENERATED_CLASS_COMPONENT_TEMPLATES_PUBLIC | Blueprint 生成类组件模板公开 |
| 477 | VER_UE4_ACTOR_COMPONENT_CREATION_METHOD | Blueprint Actor 组件创建方法 |
| 521 | VER_UE4_K2NODE_EVENT_MEMBER_REFERENCE | Blueprint 事件节点成员引用 |
| 533 | VER_UE4_BLUEPRINT_CUSTOM_EVENT_CONST_INPUT | Blueprint 自定义事件 Const 输入 |
| 547 | VER_UE4_DISABLED_SCRIPT_LIMIT_BYTECODE | Blueprint 脚本字节码限制禁用 |
| 563 | VER_UE4_K2NODE_VAR_REFERENCEGUIDS | Blueprint 变量引用 Guid |
| 621 | VER_UE4_SCS_STORES_ALLNODES_ARRAY | Blueprint SCS 存储 AllNodes 数组 |
| 634 | VER_UE4_BLUEPRINT_ENFORCE_CONST_IN_FUNCTION_OVERRIDES | Blueprint 常函数覆盖 Const |
| 669 | VER_UE4_INJECT_BLUEPRINT_STRUCT_PIN_CONVERSION_NODES | Blueprint 函数调参数转换注入 |

### 静态网格版本

| 版本号 | 版本名 | 变更描述 |
|-------|--------|---------|
| 217 | VER_UE4_STATIC_MESH_STORE_NAV_COLLISION | 静态网格预计算导航碰撞 |
| 225 | VER_UE4_SPEEDTREE_STATICMESH | 静态网格支持 SpeedTree |
| 236 | VER_UE4_SUPPORT_32BIT_STATIC_MESH_INDICES | 静态网格 32 位索引缓冲 |
| 242 | VER_UE4_REMOVE_ZERO_TRIANGLE_SECTIONS | 零三角截面移除 |
| 347 | VER_UE4_STATIC_MESH_SCREEN_SIZE_LODS | 静态网格屏幕尺寸 LOD |
| 447 | VER_UE4_STATIC_SHADOW_DEPTH_MAPS | 静态阴影深度图 |
| 482 | VER_UE4_LIGHTMAP_MESH_BUILD_SETTINGS | 光照贴图构建设置 |
| 492 | VER_UE4_STATIC_MESH_EXTENDED_BOUNDS | 静态网格扩展边界 |
| 503 | VER_UE4_MIKKTSPACE_IS_DEFAULT | MikkTSpace 默认切线空间 |
| 536 | VER_UE4_STATIC_MESH_ACTOR_COMPONENT | 静态网格 Actor 组件 |
| 553 | VER_UE4_STATIC_SHADOWMAP_PENUMBRA_SIZE | 静态阴影贴花 Penumbra 尺寸 |
| 568 | VER_UE4_DEPRECATED_STATIC_MESH_THUMBNAIL_PROPERTIES_REMOVED | 静态网格 thumbnail 属性移除 |

### 骨骼网格版本

| 版本号 | 版本名 | 变更描述 |
|-------|--------|---------|
| 228 | VER_UE4_APEX_CLOTH | APEX 服装支持 |
| 243 | VER_UE4_KEEP_SKEL_MESH_INDEX_DATA | 骨骼网格索引数据内存保留 |
| 248 | VER_UE4_APEX_CLOTH_LOD | APEX 服装 LOD Info |
| 258 | VER_UE4_REFERENCE_SKELETON_REFACTOR | 骨骼层级重构为 FReferenceSkeleton |
| 264 | VER_UE4_SUPPORT_8_BONE_INFLUENCES_SKELETAL_MESHES | 8 骨骼影响支持（CPU） |
| 272 | VER_UE4_SUPPORT_GPUSKINNING_8_BONE_INFLUENCES | GPU 皮肤 8 骨骼影响 |
| 292 | VER_UE4_MOVE_SKELETALMESH_SHADOWCASTING | 骨骼网格阴影投射移至材质 |
| 311 | VER_UE4_SKELETON_GUID_SERIALIZATION | 骨骼 Guid 序列化 |
| 357 | VER_UE4_ANIM_SUPPORT_NONUNIFORM_SCALE_ANIMATION | 非均匀缩放动画支持 |
| 395 | VER_UE4_STORE_BONE_EXPORT_NAMES | 骨骼导出名称存储 |
| 453 | VER_UE4_FIXUP_ROOTBONE_PARENT | 根骨骼父骨骼索引修复 |
| 474 | VER_UE4_REMOVE_SKELETALMESH_COMPONENT_BODYSETUP_SERIALIZATION | 骨骼网格组件 BodySetup 移除 |
| 518 | VER_UE4_SKINWEIGHT_PROFILE_DATA_LAYOUT_CHANGES | 骨骼权重 Profile 数据布局变更 |
| 544 | VER_UE4_SORT_ACTIVE_BONE_INDICES | ActiveBoneIndices 排序 |
| 562 | VER_UE4_SKELETON_ASSET_PROPERTY_TYPE_CHANGE | 骨骼资产属性类型变更 |

### 材质版本

| 版本号 | 版本名 | 变更描述 |
|-------|--------|---------|
| 220 | VER_UE4_MATERIAL_ATTRIBUTES_REORDERING | 材质属性重排序 |
| 297 | VER_UE4_MATERIAL_INSTANCE_BASE_PROPERTY_OVERRIDES | 材质实例基础属性覆盖 |
| 321 | VER_UE4_MATERIAL_INSTANCE_BASE_PROPERTY_OVERRIDES_PHASE_2 | 材质实例基础属性覆盖 Phase 2 |
| 362 | VER_UE4_UNDO_BREAK_MATERIALATTRIBUTES_CHANGE | 材质属性序列化修复（撤销 BreakMaterialAttributes） |
| 376 | VER_UE4_FIX_REFRACTION_INPUT_MASKING | 材质遮罩输入修复 |
| 396 | VER_UE4_MATERIAL_INSTANCE_BASE_PROPERTY_OVERRIDES_DITHERED_LOD_TRANSITION | 材质实例抖动 LOD 过渡 |
| 421 | VER_UE4_FIX_MATERIAL_COMMENTS | 材质注释边界修复 |
| 428 | VER_UE4_FIX_MATERIAL_COORDS | 材质坐标修复 |
| 447 | VER_UE4_FIX_MATERIAL_PROPERTY_OVERRIDE_SERIALIZE | 材质属性覆盖序列化修复 |
| 474 | VER_UE4_ADD_LINEAR_COLOR_SAMPLER | 材质线性颜色采样器 |
| 537 | VER_UE4_REFRACTION_BIAS_TO_REFRACTION_DEPTH_BIAS | 材质折射深度偏移重命名 |
| 550 | VER_UE4_MATERIAL_MASKED_BLENDMODE_TIDY | 材质遮罩混合模式整理 |
| 633 | VER_UE4_REMOVED_MATERIAL_USED_WITH_UI_FLAG | 材质域 UI 使用标志移除 |

### 纹理版本

| 版本号 | 版本名 | 变更描述 |
|-------|--------|---------|
| 226 | VER_UE4_MAX_TEXCOORD_INCREASED | 最大纹理坐标从 4 增至 8 |
| 447 | VER_UE4_STATIC_SHADOW_DEPTH_MAPS | BulkData 压缩相关 |
| 461 | VER_UE4_LEVEL_STREAMING_DRAW_COLOR_TYPE_CHANGE | 纹理流式加载 AABB |
| 469 | VER_UE4_STREAMABLE_TEXTURE_MIN_MAX_DISTANCE | 纹理流式加载距离范围 |
| 536 | VER_UE4_TEXTURE_LEGACY_GAMMA | 纹理 Gamma 遗留支持 |
| 553 | VER_UE4_STATIC_SHADOWMAP_PENUMBRA_SIZE | 纹理阴影 Penumbra 尺寸 |
| 622 | VER_UE4_ASSET_IMPORT_DATA_AS_JSON | 纹理资产导入数据 JSON |
| 647 | VER_UE4_COMPRESSED_SHADER_RESOURCES | 纹理压缩 Shader 资源 |

### 动画版本

| 版本号 | 版本名 | 变更描述 |
|-------|--------|---------|
| 272 | VER_UE4_ANIMATION_REMOVE_NANS | 动画 NaN 移除 |
| 357 | VER_UE4_ANIM_SUPPORT_NONUNIFORM_SCALE_ANIMATION | 非均匀缩放动画支持 |
| 380 | VER_UE4_ANIMATION_ADD_TRACKCURVES | 动画曲线数据添加 |
| 388 | VER_UE4_MONTAGE_BRANCHING_POINT_REMOVAL | 动画蒙塔奇分支点移除 |
| 395 | VER_UE4_SKELETON_ADD_SMARTNAMES | 骨骼 SmartNames 添加 |
| 423 | VER_UE4_CLEAR_NOTIFY_TRIGGERS | 动画通知触发器清除 |
| 440 | VER_UE4_FIX_ANIMATIONBASEPOSE_SERIALIZATION | 动画基础姿势序列化修复 |
| 453 | VER_UE4_FIXUP_ROOTBONE_PARENT | 根骨骼父骨骼索引修复 |
| 475 | VER_UE4_SERIALIZE_RICH_CURVE_KEY | 动画组件 RichCurveKey 序列化 |
| 486 | VER_UE4_ADDED_NON_LINEAR_TRANSITION_BLENDS | 动画过渡非线性混合 |
| 518 | VER_UE4_FIX_SLOT_NAME_DUPLICATION | 动画插槽名称重复修复 |
| 544 | VER_UE4_SKINWEIGHT_PROFILE_DATA_LAYOUT_CHANGES | 动画骨骼权重 Profile 数据布局 |
| 562 | VER_UE4_SKELETON_ASSET_PROPERTY_TYPE_CHANGE | 动画骨骼资产属性类型变更 |

### 音频版本

| 版本号 | 版本名 | 变更描述 |
|-------|--------|---------|
| 233 | VER_UE4_REVERB_EFFECT_ASSET_TYPE | ReverbEffect 资产类型 |
| 234 | VER_UE4_SOUND_CLASS_GRAPH_EDITOR | 音频 SoundClass 图表编辑器 |
| 251 | VER_UE4_ATMOSPHERIC_FOG_CACHE_DATA | Atmospheric Fog 缓存数据 |
| 281 | VER_UE4_SOUND_NODE_ENVELOPER_CURVE_CHANGE | SoundNodeEnveloper 曲线变更 |
| 318 | VER_UE4_SOUND_COMPRESSION_TYPE_ADDED | 音频压缩类型添加 |
| 361 | VER_UE4_FSLATESOUND_CONVERSION | 音频 SlateSound 转换 |
| 409 | VER_UE4_SOUND_CONCURRENCY_PACKAGE | 音频并发包 |
| 447 | VER_UE4_USE_LOW_PASS_FILTER_FREQ | 音频低通滤波频率 |
| 511 | VER_UE4_ENGINE_VERSION_OBJECT | 音频引擎版本对象 |
| 518 | VER_UE4_SOUND_COMPRESSION_TYPE_ADDED | 音频 BulkData 存储变更 |
| 536 | VER_UE4_ASSET_IMPORT_DATA_AS_JSON | 音频资产导入数据 JSON |

### UMG/Widget 版本

| 版本号 | 版本名 | 变更描述 |
|-------|--------|---------|
| 464 | VER_UE4_LEVEL_STREAMING_DRAW_COLOR_TYPE_CHANGE | Level Streaming 绘制颜色类型变更 |
| 486 | VER_UE4_DEPRECATE_UMG_STYLE_ASSETS | UMG 样式资产废弃 |
| 523 | VER_UE4_GRAPH_INTERACTIVE_COMMENTBUBBLES | 图表交互注释气泡 |
| 527 | VER_UE4_RENAME_WIDGET_VISIBILITY | Widget 可见性重命名 |
| 533 | VER_UE4_ADD_PIVOT_TO_WIDGET_COMPONENT | Widget 组件 Pivot |
| 534 | VER_UE4_PAWN_AUTO_POSSESS_AI | Pawn 自动拥有 AI |
| 577 | VER_UE4_DEPRECATE_UMG_STYLE_OVERRIDES | UMG 样式覆盖废弃 |

### 粒子版本

| 版本号 | 版本名 | 变更描述 |
|-------|--------|---------|
| 499 | VER_UE4_GLOBAL_EMITTER_SPAWN_RATE_SCALE | 全局发射器生成率缩放 |
| 549 | VER_UE4_FIX_SKEL_VERT_ORIENT_MESH_PARTICLES | 骨骼顶点定向网格粒子修复 |
| 566 | VER_UE4_OPTIONALLY_CLEAR_GPU_EMITTERS_ON_INIT | GPU 发射器初始化时可选清除 |

### 关卡/World 版本

| 版本号 | 版本名 | 变更描述 |
|-------|--------|---------|
| 135 | VER_UE4_WORLD_LEVEL_INFO | World Level Info 引入 |
| 225 | VER_UE4_WORLD_LEVEL_INFO_UPDATED | World Level Info 更新（父级引用、流送距离） |
| 321 | VER_UE4_WORLD_LEVEL_INFO_LOD_LIST | World Level Info LOD 列表 |
| 327 | VER_UE4_WORLD_LEVEL_INFO_ZORDER | World Level Info ZOrder |
| 343 | VER_UE4_WORLD_NAMED_AFTER_PACKAGE | World 命名跟随包名 |
| 347 | VER_UE4_WORLD_LAYER_ENABLE_DISTANCE_STREAMING | World Layer 启用距离流送 |
| 464 | VER_UE4_LEVEL_STREAMING_DRAW_COLOR_TYPE_CHANGE | Level Streaming 绘制颜色类型变更 |

## 版本分组说明

| 版本范围 | 主要变更类型 |
|----------|-------------|
| 214-230 | Blueprint、静态网格、材质基础变更 |
| 231-260 | 骨骼网格、服装、物理重构 |
| 261-300 | 动画、地形、FName、文本变更 |
| 301-350 | Cooked、属性序列化、UMG 变更 |
| 351-400 | Localization、导航、软引用变更 |
| 401-500 | SoftObjectPath、纹理流式加载变更 |
| 501-600 | 64 位导出表、Set/Map 属性支持、UMG 增强 |
| 601-739 | 高级特性、性能优化、资产引用改进 |

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
*Updated: 2026-06-01 — 基于 UE ObjectVersion.h 完整枚举同步*
