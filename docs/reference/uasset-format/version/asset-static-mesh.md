# 静态网格版本差异

## 概述

静态网格资产 (UStaticMesh) 在 UE4 演进过程中经历多项格式变更，涉及 LOD 格式变更、索引缓冲扩展、顶点数据结构变更、碰撞数据序列化等变更。本文档汇总静态网格相关关键版本差异。

## 版本差异表格

| 版本号 | 变更描述 | 影响字段/结构 |
|-------|----------|---------------|
| 217 | 静态网格预计算导航碰撞 (VER_UE4_STATIC_MESH_STORE_NAV_COLLISION) | NavCollision |
| 225 | SpeedTree 静态网格支持 (VER_UE4_SPEEDTREE_STATICMESH) | SpeedTree 数据 |
| 236 | 32 位索引缓冲支持 (VER_UE4_SUPPORT_32BIT_STATIC_MESH_INDICES) | IndexBuffer |
| 242 | 零三角截面移除 | Sections 数组 |
| 279 | 静态/骨骼网格序列化修复 | 序列化逻辑 |
| 347 | 静态网格屏幕尺寸 LOD (VER_UE4_STATIC_MESH_SCREEN_SIZE_LODS) | LOD ScreenSize |
| 447 | 静态阴影深度图 | StaticShadowDepthMaps |
| 482 | 光照贴图构建设置 | LightmapMeshBuildSettings |
| 492 | 静态网格扩展边界 | ExtendedBounds |
| 503 | MikkTSpace 默认切线空间 | TangentSpace 计算 |
| 536 | 静态网格 Actor 组件创建方法 | CreationMethod |
| 553 | 静态阴影贴花 Penumbra 尺寸 | StaticShadowmapPenumbraSize |
| 568 | 静态网格 thumbnail 属性移除 | Thumbnail 属性废弃 |

## UE5 静态网格变更

| 特性 | 说明 |
|------|------|
| Large World Coordinates | 网格坐标转为 double |
| Nanite 渲染 | 静态网格 Nanite 替代渲染 |
| PayloadTOC | 网格大数据通过 PayloadTOC 管理 |

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| StaticMesh.h | Runtime/Engine/Classes/Engine/ | 静态网格类定义 |
| StaticMeshResources.h | Runtime/Engine/Public/ | 静态网格资源结构 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*