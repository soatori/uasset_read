# 骨骼网格版本差异

## 概述

骨骼网格结构随 UE 版本演进，特别是权重系统和骨骼索引类型发生重大变更。UE5 支持无限骨骼影响和 uint16 骨骼索引，突破了 UE4 的固定 4 骨骼影响和 255 骨骼限制。

## FAnimObjectVersion 动画相关版本

| 版本 | 说明 | 影响 | 源码位置 |
|------|------|------|----------|
| UnlimitedBoneInfluences | 支持可变骨骼影响数 | 权重系统重构 | ObjectVersion.h |
| IncreaseBoneIndexLimitPerChunk | 骨骼索引从 uint8 升级到 uint16 | 支持超过 255 骨骼 | ObjectVersion.h |
| AddVirtualBones | 支持虚拟骨骼 | FReferenceSkeleton 扩展 | ObjectVersion.h |

说明：这些版本属于 FAnimObjectVersion GUID，通过 CustomVer() 检查。

## UE5 新增特性

| 特性 | 说明 | 源码位置 |
|------|------|----------|
| TObjectPtr | 智能指针替代原始指针 | SkeletalMesh.h 第 900 行 |
| 可变骨骼影响 | LookupVertexBuffer 支持 | SkinWeightVertexBuffer.h |
| uint16 骨骼索引 | 支持超过 255 骨骼分段 | SkinWeightVertexBuffer.h |
| 虚拟骨骼 | FinalRefBoneInfo 扩展 | ReferenceSkeleton.h |
| CachedComposedRefPoseMatrices | 缓存参考姿势矩阵 | SkeletalMesh.h |
| Nanite 支持 | 骨骼网格 Nanite 实验性支持 | SkeletalMesh.h 第 943-944 行 |

## UE4 关键变更

| 特性 | 版本 | 说明 |
|------|------|------|
| 固定 4 骨骼影响 | UE4 默认 | 每顶点最多 4 骨骼影响 |
| uint8 骨骼索引 | UE4 默认 | 最多 255 骨骼索引 |
| Materials 数组 | UE4.22+ | 材质槽数组增强 |
| SkelMirrorTable | UE4.26 | 骨骼镜像表（已废弃） |

## 废弃字段

| 字段名 | 废弃版本 | 替代方案 | 源码位置 |
|--------|----------|----------|----------|
| FBoneMirrorInfo | UE5.0 | UMirrorDataTable | SkeletalMesh.h 第 152-195 行 |
| FBoneMirrorExport | UE5.0 | UMirrorDataTable | SkeletalMesh.h 第 174-195 行 |
| SkelMirrorTable | UE5.0 | UMirrorDataTable | SkeletalMesh.h 第 936-940 行 |
| bAlwaysFullAnimWeight_DEPRECATED | UE5.0 | — | BodySetup.h |
| Materials_DEPRECATED | UE5.0 | Materials (FSkeletalMaterial) | SkeletalMesh.h |

## 权重系统版本判断

SkinWeightVertexBuffer.cpp 中版本判断逻辑：

```
if (Ar.CustomVer(FAnimObjectVersion::GUID) >= FAnimObjectVersion::UnlimitedBoneInfluences)
{
    // 可变骨骼影响模式
    // 需要 LookupVertexBuffer
    // MaxBoneInfluences 可大于 4
}
else
{
    // 固定影响数模式（通常 4 骨骼）
    // 无 LookupVertexBuffer
    // InfluenceBones/Weights 固定长度
}

if (Ar.CustomVer(FAnimObjectVersion::GUID) >= FAnimObjectVersion::IncreaseBoneIndexLimitPerChunk)
{
    // 支持 uint16 骨骼索引
    // FBoneIndexType = uint16
    // 最大骨骼数 65535
}
else
{
    // uint8 骨骼索引
    // FBoneIndexType = uint8
    // 最大骨骼数 255
}
```

## 骨骼索引类型判断

| 版本判断 | 索引类型 | 最大骨骼数 |
|----------|----------|------------|
| < IncreaseBoneIndexLimitPerChunk | uint8 (FBoneIndexType) | 255 |
| >= IncreaseBoneIndexLimitPerChunk | uint8 或 uint16 (FBoneIndexType) | 65535 |

说明：骨骼索引类型由 FBoneIndexType typedef 决定，根据版本定义为不同类型。

## 源码引用

- Runtime/Core/Public/UObject/ObjectVersion.h — FAnimObjectVersion 定义
- Runtime/Engine/Private/Engine/SkeletalMesh.cpp — 版本判断代码
- Runtime/Engine/Public/Rendering/SkinWeightVertexBuffer.h — 权重版本判断
- Runtime/Engine/Private/Rendering/SkinWeightVertexBuffer.cpp — 权重序列化

## 版本兼容处理建议

解析骨骼网格时：
1. 检查 FAnimObjectVersion.CustomVer() 确定权重系统版本
2. 根据 UnlimitedBoneInfluences 选择固定/可变影响模式
3. 根据 IncreaseBoneIndexLimitPerChunk 选择骨骼索引类型 (uint8/uint16)
4. 处理虚拟骨骼：检查 FinalRefBoneInfo 是否存在
5. 忽略废弃字段：SkelMirrorTable、FBoneMirrorInfo 等
6. 使用替代方案：UMirrorDataTable 替代镜像表功能