# 静态网格版本差异

## 概述

静态网格资产 (UStaticMesh) 在 UE4 至 UE5 演进过程中经历多项格式变更，涉及 LOD 格式变更、索引缓冲扩展、顶点数据结构变更、碰撞数据序列化等变更。本文档汇总静态网格相关关键版本差异。

> **源码同步状态**: 基于 `ObjectVersion.h` EUnrealEngineObjectUE4Version 枚举中静态网格相关版本宏。

## UE4 版本差异表格

| 版本号 | 版本名 | 变更描述 | 影响字段/结构 |
|-------|--------|----------|---------------|
| 217 | VER_UE4_STATIC_MESH_STORE_NAV_COLLISION | 静态网格预计算导航碰撞 | NavCollision |
| 225 | VER_UE4_SPEEDTREE_STATICMESH | SpeedTree 静态网格支持 | SpeedTree 数据 |
| 236 | VER_UE4_SUPPORT_32BIT_STATIC_MESH_INDICES | 32 位索引缓冲支持 | IndexBuffer |
| 242 | VER_UE4_REMOVE_ZERO_TRIANGLE_SECTIONS | 零三角截面移除、材质索引紧凑化 | Sections 数组 |
| 279 | VER_UE4_STATIC_SKELETAL_MESH_SERIALIZATION_FIX | 静态/骨骼网格序列化修复 | 序列化逻辑 |
| 347 | VER_UE4_STATIC_MESH_SCREEN_SIZE_LODS | 屏幕尺寸 LOD（替代 LOD 距离） | LOD ScreenSize |
| 447 | VER_UE4_STATIC_SHADOW_DEPTH_MAPS | 静态阴影深度图序列化 | StaticShadowDepthMaps |
| 482 | VER_UE4_LIGHTMAP_MESH_BUILD_SETTINGS | 光照贴图构建设置 | LightmapMeshBuildSettings |
| 492 | VER_UE4_STATIC_MESH_EXTENDED_BOUNDS | 扩展边界（用于 GPU 剔除） | ExtendedBounds |
| 503 | VER_UE4_MIKKTSPACE_IS_DEFAULT | MikkTSpace 作为默认切线空间计算 | TangentSpace 计算 |
| 536 | VER_UE4_STATIC_SHADOWMAP_PENUMBRA_SIZE | 静态阴影贴花 Penumbra 尺寸 | StaticShadowmapPenumbraSize |
| 568 | VER_UE4_DEPRECATED_STATIC_MESH_THUMBNAIL_PROPERTIES_REMOVED | 缩略图属性废弃移除 | Thumbnail 属性 |

## UE5 静态网格变更

| 特性 | 版本 | 说明 |
|------|------|------|
| Large World Coordinates | 1004 | 网格坐标转为 double |
| PayloadTOC | 1002 | 网格大数据通过 PayloadTOC 管理 |
| DATA_RESOURCES | 1009 | 大数据资源表统一管理 |
| Nanite 渲染 | UE5.0+ | 静态网格 Nanite 替代渲染（FStaticMeshSourceData 变更） |

## 关键变更详细说明

### VER_UE4_SUPPORT_32BIT_STATIC_MESH_INDICES (236)

索引缓冲从 16 位升级到支持 32 位：
- 版本 < 236：仅支持 16 位索引（最多 65535 顶点）
- 版本 >= 236：支持 32 位索引（最多 4294967295 顶点）

### VER_UE4_STATIC_MESH_SCREEN_SIZE_LODS (347)

LOD 切换从距离改为屏幕尺寸因子：
- 版本 < 347：使用固定 LOD 距离值
- 版本 >= 347：使用 ScreenSize 因子（0.0-1.0）

### VER_UE4_STATIC_MESH_EXTENDED_BOUNDS (492)

新增 ExtendedBounds 字段：
- 用于 GPU 驱动的剔除优化
- 考虑变形动画的额外边界
- 版本 < 492：仅有 RegularBounds

### VER_UE4_MIKKTSPACE_IS_DEFAULT (503)

切线空间计算方式变更：
- 版本 < 503：默认使用 UE 原生切线计算
- 版本 >= 503：默认使用 MikkTSpace 标准计算

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| StaticMesh.h | Runtime/Engine/Classes/Engine/ | 静态网格类定义 |
| StaticMeshResources.h | Runtime/Engine/Public/ | 静态网格资源结构 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*
*Updated: 2026-06-01 — 基于 UE ObjectVersion.h 完整枚举同步版本号与版本名*
