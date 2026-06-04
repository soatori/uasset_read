# 纹理资产版本差异

## 概述

纹理资产 (UTexture/UTexture2D/UTextureCube) 在 UE4 至 UE5 演进过程中经历多项格式变更，涉及纹理坐标数量增加、纹理流式加载优化、BulkData 存储变更、纹理压缩格式等变更。本文档汇总纹理相关关键版本差异。

> **源码同步状态**: 基于 `ObjectVersion.h` EUnrealEngineObjectUE4Version 枚举。

## UE4 版本差异表格

| 版本号 | 版本名 | 变更描述 | 影响字段/结构 |
|-------|--------|----------|---------------|
| 226 | VER_UE4_MAX_TEXCOORD_INCREASED | 最大纹理坐标从 4 增至 8 | TexCoord 数量 |
| 236 | VER_UE4_SUPPORT_32BIT_STATIC_MESH_INDICES | 32 位静态网格索引支持 | 纹理采样索引 |
| 362 | VER_UE4_REBUILD_TEXTURE_STREAMING_DATA_ON_LOAD | 纹理流式数据重建 | StreamingData |
| 447 | VER_UE4_STATIC_SHADOW_DEPTH_MAPS | BulkData 压缩 | 纹理 Mip 数据 BulkData |
| 461 | VER_UE4_STREAMABLE_TEXTURE_AABB | 纹理流式加载 AABB | StreamableTexture AABB |
| 469 | VER_UE4_STREAMABLE_TEXTURE_MIN_MAX_DISTANCE | 纹理流式加载距离范围 | MinMaxDistance |
| 536 | VER_UE4_TEXTURE_LEGACY_GAMMA | 纹理 Gamma 遗留支持 | SRGB/Gamma |
| 553 | VER_UE4_STATIC_SHADOWMAP_PENUMBRA_SIZE | 纹理阴影 Penumbra 尺寸 | StaticShadowmapPenumbraSize |
| 622 | VER_UE4_ASSET_IMPORT_DATA_AS_JSON | 纹理资产导入数据 JSON | AssetImportData |
| 647 | VER_UE4_COMPRESSED_SHADER_RESOURCES | 纹理压缩 Shader 资源 | ShaderResource 压缩 |

## UE5 纹理变更

| 特性 | 版本 | 说明 |
|------|------|------|
| PayloadTOC | 1002 | 纹理 BulkData 通过 PayloadTOC 管理 |
| Data Resources | 1009 | 纹理大数据通过 Data Resources 表管理 |
| EditorBulkData | UE5.0+ | FTextureSource 使用 EditorBulkData |

## 关键变更详细说明

### VER_UE4_MAX_TEXCOORD_INCREASED (226)

纹理坐标数量增加：
- 版本 < 226：最多 4 个纹理坐标 (MAX_TEXCOORDS = 4)
- 版本 >= 226：最多 8 个纹理坐标 (MAX_TEXCOORDS = 8)
- 影响材质和网格资产的 UV 通道数量

### VER_UE4_TEXTURE_LEGACY_GAMMA (536)

纹理 Gamma 处理变更：
- 版本 < 536：使用旧版 Gamma 计算
- 版本 >= 536：引入遗留 Gamma 支持标志
- 影响 SRGB 纹理的颜色空间转换

### VER_UE4_ASSET_IMPORT_DATA_AS_JSON (622)

资产导入数据转为 JSON 格式：
- 版本 < 622：导入数据为原生结构
- 版本 >= 622：导入数据以 JSON 格式序列化
- 包括文件路径、时间戳、导入设置等

### VER_UE4_COMPRESSED_SHADER_RESOURCES (647)

Shader 资源压缩：
- 版本 < 647：Shader 资源未压缩
- 版本 >= 647：Shader 资源压缩以节省内存
- 影响纹理的 ShaderResource 数据块

## 序列化注意事项

### BulkData 存储

纹理 Mip 数据存储在不同版本中有不同的存储方式：
- UE4 早期：直接使用 BulkData 偏移
- UE4 后期：压缩 BulkData
- UE5：通过 PayloadTOC/Data Resources 管理

### 流式加载

纹理流式加载数据在多个版本中演进：
- VER_UE4_REBUILD_TEXTURE_STREAMING_DATA_ON_LOAD (362)：加载时重建
- VER_UE4_STREAMABLE_TEXTURE_MIN_MAX_DISTANCE (469)：距离范围
- VER_UE4_STREAMABLE_TEXTURE_AABB (461)：AABB 流式加载

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| Texture.h | Runtime/Engine/Classes/Engine/ | 纹理类定义 |
| Texture2D.h | Runtime/Engine/Classes/Engine/ | 2D 纹理类定义 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*
*Updated: 2026-06-01 — 基于 UE ObjectVersion.h 完整枚举同步版本号与版本名*
