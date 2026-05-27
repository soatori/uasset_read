# 纹理资产 (UTexture/UTexture2D/UTextureCube)

## 概述

### UTexture 基类

UTexture 类继承自 UStreamableRenderAsset，为所有纹理类型提供基类功能。核心用途：定义纹理的基本属性（压缩设置、过滤模式、LOD 组等）和管理纹理源数据。

### UTexture2D

UTexture2D 类继承自 UTexture，实现 2D 纹理。核心用途：存储和处理 2D 纹理数据，包括 Mip 数据和平台编译数据。

### UTextureCube

UTextureCube 类继承自 UTexture，实现立方体纹理（环境贴图）。核心用途：存储六个面的环境贴图数据，用于反射和天空盒渲染。

说明：UTextureCube 使用与 UTexture2D 相同的 FTexturePlatformData 结构，通过 PackedData 的 b31 位标记为 Cubemap。GetSurfaceArraySize() 返回 6（六个面）。

## 字段表

### UTexture 基类字段表

#### 核心属性字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| LightingGuid | FGuid | 纹理唯一 ID，用于光照构建和纹理流式器 |
| LODBias | int32 | LOD 偏移（Cook 时丢弃的 Mip 级数）（per D-11） |
| CompressionSettings | TEnumAsByte<TextureCompressionSettings> | 纹理压缩设置（per D-10，简要枚举说明） |
| Filter | TEnumAsByte<TextureFilter> | 纹理过滤模式 |
| LODGroup | TEnumAsByte<TextureGroup> | 纹理 LOD 组 |
| SRGB | uint8:1 | 是否使用 sRGB Gamma 空间 |
| VirtualTextureStreaming | uint8:1 | 使用虚拟纹理流式加载（per D-11） |
| bNoTiling | uint8:1 | 使用 TexCreate_NoTiling 创建 RHI 纹理 |

#### 纹理源数据

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Source | FTextureSource | 编辑器源数据（per D-12，只说明存在） |

FTextureSource 包含：源图像像素数据（BulkData）、尺寸参数（SizeX/SizeY/NumSlices/NumMips）、格式参数。

#### 运行时资源

| 字段名 | 类型 | 用途 |
|--------|------|------|
| PrivateResource | FTextureResource* | 纹理渲染资源指针 |

### FTexturePlatformData 结构字段表

#### 基本字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| SizeX | int32 | 纹理宽度 |
| SizeY | int32 | 纹理高度 |
| PackedData | uint32 | 打包数据：[b31:Cubemap][b30:HasOptData][b29:HasCpuCopy][b0-28:NumSlices] |
| PixelFormat | EPixelFormat | 纹理像素格式（per D-10，简要枚举说明） |

#### 扩展字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| OptData | FOptTexturePlatformData | 可选扩展数据（ExtData、NumMipsInTail） |
| Mips | TIndirectArray<FTexture2DMipMap> | Mip 数据数组 |
| VTData | FVirtualTextureBuiltData* | 虚拟纹理数据（per D-08，简要说明存在） |

### FTexture2DMipMap 结构字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| DerivedData | UE::FDerivedData | 可流式化的 Mip 数据引用（DDC） |
| BulkData | FByteBulkData | 加载时存储的 Mip 数据 |
| SizeX | uint16 | Mip 宽度 |
| SizeY | uint16 | Mip 高度 |
| SizeZ | uint16 | Mip 深度（数组纹理/体积纹理时使用） |

简要说明 BulkData 关系（per D-09）：Mip 数据通过 BulkData 存储于包数据区，高分辨率 Mip 可标记为流式加载。详见 `docs/bulkdata-region.md` 和 `docs/serialization/bulkdata.md`。

### FOptTexturePlatformData 子结构字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| ExtData | uint32 | 平台额外数据 |
| NumMipsInTail | uint32 | Mip Tail 中必须常驻的 Mip 数量 |

### UTexture2D 特有字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| AddressX | TEnumAsByte<TextureAddress> | X 轴寻址模式（Wrap/Clamp/Mirror） |
| AddressY | TEnumAsByte<TextureAddress> | Y 轴寻址模式 |
| FirstResourceMemMip | int32 | ResourceMem 创建时使用的首个 Mip |
| ImportedSize | FIntPoint | 导入尺寸（Cooked 版本可用） |
| bTemporarilyDisableStreaming | uint8:1 | 暂时禁用流式加载 |
| PrivatePlatformData | FTexturePlatformData* | 平台数据指针 |

### UTextureCube 特有字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| PrivatePlatformData | FTexturePlatformData* | 平台数据指针（立方体纹理共用结构） |

WITH_EDITORONLY_DATA 相关字段统一列出（per D-20）。

## 源码引用

- Runtime/Engine/Classes/Engine/Texture.h — UTexture 及 FTexturePlatformData/FTextureSource 结构
- Runtime/Engine/Classes/Engine/Texture2D.h — UTexture2D 类定义
- Runtime/Engine/Classes/Engine/TextureCube.h — UTextureCube 类定义
- Runtime/Engine/Public/TextureResource.h — FTexture2DMipMap 结构

## 版本差异

| 变更 | 版本 | 说明 |
|------|------|------|
| VirtualTextureStreaming | UE5 | VTData 替代 Mips 数组 |
| DerivedData | UE5 | FTexture2DMipMap 使用 UE::FDerivedData 替代旧的 BulkData 引用 |
| PackedData 结构扩展 | UE5 | 新增 HasOptData、HasCpuCopy 位 |
| ImportedSize 字段 | UE5 | Cooked 版本可用的导入尺寸 |

---
*文档创建: Phase 3 - 材质与纹理资产*
*源码路径: 相对引用 UE Engine 目录*