# 骨骼网格权重数据

## 概述

皮肤权重数据存储在 FSkinWeightVertexBuffer 中，每个顶点记录影响该顶点的骨骼索引和权重值。存在固定影响数（通常 4 骨骼）和可变影响数两种模式，由版本决定使用哪种。

## FSkinWeightVertexBuffer 皮肤权重缓冲

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| DataVertexBuffer | FSkinWeightDataVertexBuffer | 权重数据缓冲 | SkinWeightVertexBuffer.h 第 495 行 |
| LookupVertexBuffer | FSkinWeightLookupVertexBuffer | 查找表缓冲（可变影响模式） | SkinWeightVertexBuffer.h 第 496 行 |
| MaxBoneInfluences | uint32 | 最大骨骼影响数 | SkinWeightVertexBuffer.h 第 418 行 |

## FSkinWeightDataVertexBuffer 权重数据

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| InfluenceBones | TArray&lt;FBoneIndexType&gt; | 影响骨骼索引数组 | SkinWeightVertexBuffer.h |
| InfluenceWeights | TArray&lt;uint8&gt; | 骨骼权重数组（归一化） | SkinWeightVertexBuffer.h |

说明：
- InfluenceBones 元素类型可为 uint8 或 uint16（由版本决定）
- InfluenceWeights 为 uint8，范围 0-255，GPU 归一化后为 0.0-1.0

## 骨骼影响模式

### 固定影响数模式 (Fixed Mode)
- 每顶点固定影响骨骼数（通常 4 骨骼）
- 权重数据紧凑存储，无 LookupVertexBuffer
- 数据格式：每个顶点连续存储 N 个骨骼索引和 N 个权重值
- 激活条件：FAnimObjectVersion::UnlimitedBoneInfluences 版本之前

### 可变影响数模式 (Unlimited Mode)
- 每顶点影响骨骼数可变（由 MaxBoneInfluences 决定上限）
- 需要 LookupVertexBuffer 存储每顶点偏移和影响数
- 激活条件：FAnimObjectVersion::UnlimitedBoneInfluences 版本后

## 骨骼索引类型

| 版本判断 | 索引类型 | 最大骨骼数 | 源码位置 |
|----------|----------|------------|----------|
| 旧版本 (< IncreaseBoneIndexLimitPerChunk) | uint8 | 255 | SkinWeightVertexBuffer.h |
| 新版本 (>= IncreaseBoneIndexLimitPerChunk) | uint16 | 65535 | FAnimObjectVersion |

说明：FBoneIndexType typedef 根据版本定义为 uint8 或 uint16。

## FSkinWeightLookupVertexBuffer 查找表

可变影响数模式下的查找表结构：

| 字段名 | 类型 | 用途 |
|--------|------|------|
| VertexOffset | TArray&lt;uint32&gt; | 每顶点权重数据偏移 |
| VertexInfluenceCount | TArray&lt;uint8&gt; | 每顶点实际影响骨骼数 |

## FSkelMeshRenderSection 骨骼影响信息

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| BoneMap | TArray&lt;FBoneIndexType&gt; | 该分段影响骨骼列表 | SkeletalMeshLODRenderData.h |
| MaxBoneInfluences | int32 | 该分段最大骨骼影响数 | SkeletalMeshLODRenderData.h |

说明：BoneMap 用于将全局骨骼索引映射到分段局部骨骼索引，减少 GPU shader 中的骨骼矩阵查找开销。

## 权重归一化

权重存储规则：
- 权重值存储为 uint8 (0-255)
- GPU 渲染时归一化为 float (0.0-1.0)
- 所有影响骨骼权重之和为 1.0
- 零权重骨骼索引通常不存储（可变模式）或填充为第一个骨骼（固定模式）

## 源码引用

- Runtime/Engine/Public/Rendering/SkinWeightVertexBuffer.h — FSkinWeightVertexBuffer 定义
- Runtime/Engine/Private/Rendering/SkinWeightVertexBuffer.cpp — 权重序列化
- Runtime/Core/Public/UObject/ObjectVersion.h — FAnimObjectVersion 版本判断

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| UnlimitedBoneInfluences | 支持可变影响数，突破 4 骨骼限制 |
| IncreaseBoneIndexLimitPerChunk | uint16 骨骼索引，支持超过 255 骨骼 |
| LookupVertexBuffer | 可变影响数查找表 |

### UE4 特性
| 特性 | 说明 |
|------|------|
| 固定 4 骨骼影响 | 每顶点最多 4 骨骼影响 |
| uint8 骨骼索引 | 最多 255 骨骼索引 |
| 无 LookupVertexBuffer | 固定模式无查找表 |