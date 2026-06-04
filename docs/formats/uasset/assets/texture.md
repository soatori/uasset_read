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
| LODBias | int32 | LOD 偏移（Cook 时丢弃的 Mip 级数） |
| CompressionSettings | TEnumAsByte<TextureCompressionSettings> | 纹理压缩设置 |
| Filter | TEnumAsByte<TextureFilter> | 纹理过滤模式 |
| MipLoadOptions | ETextureMipLoadOptions | Mip 加载选项 |
| LODGroup | TEnumAsByte<TextureGroup> | 纹理 LOD 组 |
| SRGB | uint8:1 | 是否使用 sRGB Gamma 空间 |
| VirtualTextureStreaming | uint8:1 | 使用虚拟纹理流式加载 |
| bUseVirtualTextureStreamingPriority | uint32:1 | 是否覆盖 LOD 组的 VT 流式优先级 |
| VirtualTextureStreamingPriority | EVTProducerPriority | 虚拟纹理流式加载优先级 |
| VirtualTexturePrefetchMips | uint8 | VT 可使用传统 CPU 纹理流式系统预取的 Mip 数量，默认 0 |
| CookPlatformTilingSettings | TEnumAsByte<TextureCookPlatformTilingSettings> | Cook 时的平台 Tiling 设置 |
| bOodlePreserveExtremes | bool | Oodle 编码器是否保留 alpha 通道中的 0/255 精确值 |
| bNoTiling | uint8:1 | 使用 TexCreate_NoTiling 创建 RHI 纹理 |
| CompressionYCoCg | uint8:1 | 纹理是否存储 YCoCg 格式（压缩时蓝通道填充精度缩放） |
| bNotOfflineProcessed | uint8:1 | RHI 纹理是否不使用 TexCreate_OfflineProcessed 创建 |
| Downscale | FPerPlatformFloat | 源纹理降采样比例（仅适用于无 Mip 的 2D 纹理） |
| DownscaleOptions | ETextureDownscaleOptions | 纹理降采样选项 |
| Availability | ETextureAvailability | 纹理可用性（GPU 编码上传 / CPU 保留访问） |
| LevelIndex | int32 | 纹理在关卡中的作用域索引，用于纹理流式构建，默认 INDEX_NONE |

#### 纹理源数据

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Source | FTextureSource | 编辑器源数据（WITH_EDITORONLY_DATA） |

FTextureSource 包含：源图像像素数据（FEditorBulkData）、尺寸参数（SizeX/SizeY/NumSlices/NumMips/NumLayers）、格式参数（Format/LayerFormat）、压缩格式（CompressionFormat）、UDIM 多 Block 支持（Blocks/BaseBlockX/BaseBlockY）、长经纬立方图标记（bLongLatCubemap）等。

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
| PackedData | uint32 | 打包数据位域，详见下方位布局 |
| PixelFormat | EPixelFormat | 纹理像素格式 |

**PackedData 位布局**（从源码 BitMask 常量推导）：

| 位 | 掩码常量 | 用途 |
|----|----------|------|
| b31 | BitMask_CubeMap (1u << 31) | 是否为立方体贴图 |
| b30 | BitMask_HasOptData (1u << 30) | 是否包含 OptData |
| b29 | BitMask_HasCpuCopy (1u << 29) | 是否包含 CPU 副本（set 时标记，get 时检查） |
| b0-28 | BitMask_NumSlices (0x1FFFFFFF) | 切片数量（数组纹理的数组大小 / 体积纹理的深度） |

注意：BitMask_NumSlices 定义为 `BitMask_HasCpuCopy - 1u`，即 0x1FFFFFFF（29 位）。SetPackedData 将 HasCpuCopy 和 NumSlices 分别设置到对应位域；GetNumSlices 仅掩码 b0-28。

#### 扩展字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| OptData | FOptTexturePlatformData | 可选扩展数据（ExtData、NumMipsInTail） |
| Mips | TIndirectArray<FTexture2DMipMap> | Mip 数据数组（非 VT 纹理使用） |
| VTData | FVirtualTextureBuiltData* | 虚拟纹理数据（VT 纹理使用，与 Mips 互斥） |
| CPUCopy | TRefCountPtr<const FSharedImage> | CPU 可访问的纹理副本（仅当 Availability 为 CPU only 时有效） |

### FTexture2DMipMap 结构字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| DerivedData | UE::FDerivedData | 可流式化的 Mip 数据引用（DDC 键） |
| BulkData | FByteBulkData | 加载时存储的 Mip 数据 |
| SizeX | uint16 | Mip 宽度 |
| SizeY | uint16 | Mip 高度 |
| SizeZ | uint16 | Mip 深度（持有数组大小，通过 FStreamableTextureResource::SizeZ 传递；Cubemap 数组和 Cubemap 不使用此字段） |

Mip 数据通过 BulkData 存储于包数据区，高分辨率 Mip 可标记为流式加载。

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
| ImportedSize | FIntPoint | 导入尺寸（仅 Cooked 构建有效，当纹理源不可用时通过 GetImportedSize() 访问） |
| bTemporarilyDisableStreaming | uint8:1 | 暂时禁用流式加载（transient，保存前自动清除） |
| PrivatePlatformData | FTexturePlatformData* | 平台数据指针 |

### UTextureCube 特有字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| PrivatePlatformData | FTexturePlatformData* | 平台数据指针（立方体纹理共用结构） |

WITH_EDITORONLY_DATA 相关字段统一列出。

## 源码引用

- Runtime/Engine/Classes/Engine/Texture.h — UTexture、FTexturePlatformData、FTextureSource、FOptTexturePlatformData、FTextureFormatSettings、FTextureSourceColorSettings 结构
- Runtime/Engine/Classes/Engine/Texture2D.h — UTexture2D 类定义
- Runtime/Engine/Classes/Engine/TextureCube.h — UTextureCube 类定义
- Runtime/Engine/Public/TextureResource.h — FTexture2DMipMap 结构、FTextureResource 基类及各派生资源类

## 版本差异

| 变更 | 版本 | 说明 |
|------|------|------|
| VTData 字段 | UE4.23+ | FTexturePlatformData 同时包含 Mips 和 VTData，VirtualTextureStreaming 标志决定使用哪个（互斥共存，非替代关系） |
| UE::FDerivedData | UE5 | FTexture2DMipMap 使用 UE::FDerivedData 替代旧的 DDC 引用方式（BulkData 仍保留用于加载时数据） |
| PackedData HasCpuCopy 位 | UE5 | PackedData 新增 b29 HasCpuCopy 位，配合 CPUCopy (FSharedImage) 成员使用 |
| ImportedSize 字段 | UE4.17+ | Cooked 版本可用的导入尺寸，非 UE5 新增 |

---
*文档创建: Phase 3 - 材质与纹理资产*
*源码路径: 相对引用 UE Engine 目录*
*最后校验: 基于 UE5 源码 (Engine/Source/Runtime/Engine)*