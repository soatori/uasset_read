# 纹理资产版本差异

## 概述

纹理资产 (UTexture/UTexture2D/UTextureCube) 在 UE4 演进过程中经历多项格式变更，涉及纹理坐标数量增加、纹理流式加载优化、BulkData 存储变更、纹理压缩格式等变更。本文档汇总纹理相关关键版本差异。

## 版本差异表格

| 版本号 | 变更描述 | 影响字段/结构 |
|-------|----------|---------------|
| 226 | 最大纹理坐标从 4 增至 8 (VER_UE4_MAX_TEXCOORD_INCREASED) | TexCoord 数量 |
| 236 | 32 位静态网格索引支持 | 纹理采样索引 |
| 362 | 纹理流式数据重建 | StreamingData |
| 363 | 32 位索引缓冲支持 (VER_UE4_SUPPORT_32BIT_STATIC_MESH_INDICES) | 纹理索引缓冲 |
| 447 | BulkData 压缩 | 纹理 Mip 数据 BulkData |
| 461 | 纹理流式加载 AABB | StreamableTexture AABB |
| 469 | 纹理流式加载距离范围 | MinMaxDistance |
| 536 | 纹理 Gamma 遗留支持 (VER_UE4_TEXTURE_LEGACY_GAMMA) | SRGB/Gamma |
| 553 | 纹理阴影 Penumbra 尺寸 | StaticShadowmapPenumbraSize |
| 622 | 纹理资产导入数据 JSON | AssetImportData |
| 647 | 纹理压缩 Shader 资源 | ShaderResource 压缩 |

## UE5 纹理变更

| 特性 | 说明 |
|------|------|
| PayloadTOC | 纹理 BulkData 通过 PayloadTOC 管理 |
| Data Resources | 纹理大数据通过 Data Resources 表管理 |
| EditorBulkData | FTextureSource 使用 EditorBulkData |

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| Texture.h | Runtime/Engine/Classes/Engine/ | 纹理类定义 |
| Texture2D.h | Runtime/Engine/Classes/Engine/ | 2D 纹理类定义 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*