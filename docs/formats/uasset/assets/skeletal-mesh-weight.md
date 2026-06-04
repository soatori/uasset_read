# 骨骼网格权重数据

## 概述

皮肤权重数据存储在 `FSkinWeightVertexBuffer` 中，每个顶点记录影响该顶点的骨骼索引和权重值。存在固定影响数（通常 4 骨骼）和可变影响数两种模式，由 `FAnimObjectVersion::UnlimitedBoneInfluences` 版本决定使用哪种。

> **关键架构**：`FSkinWeightVertexBuffer` 是运行时渲染使用的缓冲，内部组合了两个子缓冲：
> - `FSkinWeightDataVertexBuffer` — 存储实际骨骼索引和权重数据
> - `FSkinWeightLookupVertexBuffer` — 可变影响数模式下的查找表

## FSkinWeightVertexBuffer 皮肤权重缓冲

> 定义在 `SkinWeightVertexBuffer.h`，类共有 500 行。

| 字段名 | 访问权限 | 类型 | 用途 | 源码位置 |
|--------|----------|------|------|----------|
| DataVertexBuffer | private | FSkinWeightDataVertexBuffer | 权重数据缓冲 | SkinWeightVertexBuffer.h 第 496 行 |
| LookupVertexBuffer | private | FSkinWeightLookupVertexBuffer | 查找表缓冲（可变影响模式） | SkinWeightVertexBuffer.h 第 499 行 |

### 公共 API 方法

| 方法名 | 返回类型 | 用途 | 源码位置 |
|--------|----------|------|----------|
| GetNumVertices() | uint32 | 获取顶点数 | SkinWeightVertexBuffer.h 第 399 行 |
| GetVertexDataSize() | uint32 | 获取数据总大小 | SkinWeightVertexBuffer.h 第 403 行 |
| SetMaxBoneInfluences(uint32) | void | 设置最大骨骼影响数 | SkinWeightVertexBuffer.h 第 415 行 |
| GetMaxBoneInfluences() | uint32 | 获取最大骨骼影响数 | SkinWeightVertexBuffer.h 第 418 行 |
| SetUse16BitBoneIndex(bool) | void | 设置是否使用 16 位骨骼索引 | SkinWeightVertexBuffer.h 第 421 行 |
| Use16BitBoneIndex() | bool | 是否使用 16 位骨骼索引 | SkinWeightVertexBuffer.h 第 424 行 |
| SetUse16BitBoneWeight(bool) | void | 设置是否使用 16 位权重 | SkinWeightVertexBuffer.h 第 427 行 |
| Use16BitBoneWeight() | bool | 是否使用 16 位权重 | SkinWeightVertexBuffer.h 第 430 行 |
| GetBoneIndexByteSize() | uint32 | 获取骨骼索引字节大小 | SkinWeightVertexBuffer.h 第 433 行 |
| GetBoneWeightByteSize() | uint32 | 获取权重字节大小 | SkinWeightVertexBuffer.h 第 436 行 |
| GetVariableBonesPerVertex() | bool | 是否为可变影响数模式 | SkinWeightVertexBuffer.h 第 442 行 |
| GetDataVertexBuffer() | FSkinWeightDataVertexBuffer* | 获取数据缓冲指针 | SkinWeightVertexBuffer.h 第 451 行 |
| GetLookupVertexBuffer() | const FSkinWeightLookupVertexBuffer* | 获取查找表缓冲指针 | SkinWeightVertexBuffer.h 第 457 行 |
| GetBoneInfluenceType() | GPUSkinBoneInfluenceType | 获取骨骼影响类型 | SkinWeightVertexBuffer.h 第 462 行 |
| GetVertexInfluenceOffsetCount() | void | 获取顶点权重偏移和影响数 | SkinWeightVertexBuffer.h 第 463 行 |
| GetBoneIndex(uint32, uint32) | uint32 | 获取指定顶点的骨骼索引 | SkinWeightVertexBuffer.h 第 465 行 |
| GetBoneWeight(uint32, uint32) | uint16 | 获取指定顶点的骨骼权重 | SkinWeightVertexBuffer.h 第 467 行 |
| operator<<(FArchive&, FSkinWeightVertexBuffer&) | FArchive& | 序列化运算符 | SkinWeightVertexBuffer.h 第 393 行 |
| SerializeMetaData(FArchive&) | void | 序列化元数据 | SkinWeightVertexBuffer.h 第 395 行 |
| CopyMetaData() | void | 复制元数据 | SkinWeightVertexBuffer.h 第 396 行 |

> **修正**：原 wiki 将 `MaxBoneInfluences` 描述为 `FSkinWeightVertexBuffer` 的直接字段，实际它是通过 `DataVertexBuffer.SetMaxBoneInfluences()/GetMaxBoneInfluences()` 管理的属性，不是直接存储的字段。

## FSkinWeightDataVertexBuffer 权重数据

`FSkinWeightDataVertexBuffer` 是内部数据缓冲，包含实际的骨骼索引和权重数据。

> 定义在 `SkinWeightVertexBuffer.h`。

| 属性/方法 | 类型 | 用途 | 源码位置 |
|-----------|------|------|----------|
| MaxBoneInfluences | uint32 | 最大骨骼影响数 | SkinWeightVertexBuffer.h（通过 getter/setter） |
| Use16BitBoneIndex | bool | 是否使用 16 位骨骼索引 | SkinWeightVertexBuffer.h |
| Use16BitBoneWeight | bool | 是否使用 16 位权重值 | SkinWeightVertexBuffer.h |
| VariableBonesPerVertex | bool | 是否为可变影响数模式 | SkinWeightVertexBuffer.h |
| GetConstantInfluencesVertexStride() | uint32 | 固定影响数模式的顶点步长 | SkinWeightVertexBuffer.h 第 445 行 |
| GetConstantInfluencesBoneWeightsOffset() | uint32 | 固定影响数模式的权重偏移 | SkinWeightVertexBuffer.h 第 448 行 |

### 骨骼索引类型

| 版本判断 | 索引类型 | 最大骨骼数 | 源码位置 |
|----------|----------|------------|----------|
| 旧版本 (< IncreaseBoneIndexLimitPerChunk) | uint8 | 255 | SkinWeightVertexBuffer.h |
| 新版本 (>= IncreaseBoneIndexLimitPerChunk) | uint8 或 uint16 | 65535 | FAnimObjectVersion |

说明：FBoneIndexType typedef 根据版本定义为 uint8 或 uint16。

### 骨骼权重类型

| 配置 | 权重类型 | 范围 |
|------|----------|------|
| Use16BitBoneWeight = false | uint8 | 0-255 |
| Use16BitBoneWeight = true | uint16 | 0-65535 |

## FSkinWeightLookupVertexBuffer 查找表

可变影响数模式下的查找表结构：

| 功能 | 说明 |
|------|------|
| 顶点偏移查找 | 通过 `GetVertexInfluenceOffsetCount()` 获取每顶点的权重数据偏移 |
| 影响数查找 | 通过 `GetVertexInfluenceOffsetCount()` 获取每顶点实际影响骨骼数 |
| 仅在可变模式使用 | 固定影响数模式下 LookupVertexBuffer 存在但数据紧凑 |

## 骨骼影响模式

### 固定影响数模式 (Fixed Mode)
- 每顶点固定影响骨骼数（通常 4 骨骼）
- 权重数据紧凑存储，使用 `GetConstantInfluencesVertexStride()` 计算步长
- 数据格式：每个顶点连续存储 N 个骨骼索引和 N 个权重值
- `GetVariableBonesPerVertex()` 返回 false
- 激活条件：`FAnimObjectVersion::UnlimitedBoneInfluences` 版本之前

### 可变影响数模式 (Unlimited Mode)
- 每顶点影响骨骼数可变（由 `MaxBoneInfluences` 决定上限）
- 需要 `LookupVertexBuffer` 存储每顶点偏移和影响数
- `GetVariableBonesPerVertex()` 返回 true
- 通过 `GetVertexInfluenceOffsetCount()` 获取每个顶点的偏移和数量
- 激活条件：`FAnimObjectVersion::UnlimitedBoneInfluences` 版本后

## FSkelMeshSection / FSkelMeshRenderSection 骨骼影响信息

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| BoneMap | TArray&lt;FBoneIndexType&gt; | 该分段影响骨骼列表 | SkeletalMeshLODModel.h 第 75 行 / SkeletalMeshLODRenderData.h 第 68 行 |
| MaxBoneInfluences | int32 | 该分段最大骨骼影响数 | SkeletalMeshLODModel.h 第 81 行 / SkeletalMeshLODRenderData.h 第 74 行 |
| bUse16BitBoneIndex | bool | 是否使用 16 位骨骼索引 | SkeletalMeshLODModel.h 第 84 行 |

说明：BoneMap 用于将全局骨骼索引映射到分段局部骨骼索引，减少 GPU shader 中的骨骼矩阵查找开销。

## FSoftSkinVertex 中的骨骼权重（编辑器模式）

在编辑器模式下，每个 `FSoftSkinVertex` 直接存储骨骼权重：

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| InfluenceBones | uint16[MAX_TOTAL_INFLUENCES] | 影响骨骼索引 | SkeletalMeshTypes.h 第 71 行 |
| InfluenceWeights | uint16[MAX_TOTAL_INFLUENCES] | 骨骼权重 | SkeletalMeshTypes.h 第 72 行 |

> **说明**：`FSoftSkinVertex` 中的 `InfluenceBones`/`InfluenceWeights` 类型为 `uint16`，与运行时 `FSkinWeightVertexBuffer` 的 `uint8/uint16` 可变类型不同。编辑器模式始终使用 uint16。

## 权重归一化

权重存储规则：
- 权重值存储为 uint8 (0-255) 或 uint16 (0-65535)（由 `Use16BitBoneWeight` 决定）
- GPU 渲染时归一化为 float (0.0-1.0)
- 所有影响骨骼权重之和为 1.0
- 零权重骨骼索引通常不存储（可变模式）或填充为第一个骨骼（固定模式）

## 源码引用

- Runtime/Engine/Public/Rendering/SkinWeightVertexBuffer.h — FSkinWeightVertexBuffer 定义（500 行）
- Runtime/Engine/Public/Rendering/SkinWeightVertexBuffer.h — FSkinWeightDataVertexBuffer 定义
- Runtime/Engine/Public/Rendering/SkinWeightVertexBuffer.h — FSkinWeightLookupVertexBuffer 定义
- Runtime/Engine/Public/SkeletalMeshTypes.h — FSoftSkinVertex 定义（编辑器模式权重）
- Runtime/Engine/Private/Rendering/SkinWeightVertexBuffer.cpp — 权重序列化
- Runtime/Core/Public/UObject/ObjectVersion.h — FAnimObjectVersion 版本判断

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| UnlimitedBoneInfluences | 支持可变影响数，突破 4 骨骼限制 |
| IncreaseBoneIndexLimitPerChunk | uint16 骨骼索引，支持超过 255 骨骼 |
| LookupVertexBuffer | 可变影响数查找表 |
| Use16BitBoneWeight | 支持 16 位权重值（0-65535 精度） |
| SerializeMetaData | 元数据序列化支持 |
| CopyMetaData | 元数据复制支持 |
| GPUSkinBoneInfluenceType | GPU 骨骼影响类型枚举 |

### UE4 特性
| 特性 | 说明 |
|------|------|
| 固定 4 骨骼影响 | 每顶点最多 4 骨骼影响 |
| uint8 骨骼索引 | 最多 255 骨骼索引 |
| 无 LookupVertexBuffer | 固定模式无查找表 |
| uint8 权重值 | 权重范围为 0-255 |
