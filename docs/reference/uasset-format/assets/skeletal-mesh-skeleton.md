# 骨骼网格骨骼层级

## 概述

骨骼层级存储在 USkeleton 资产的 FReferenceSkeleton 结构中，包含骨骼树信息和参考姿势变换。骨骼按深度优先顺序存储，子骨骼索引大于父骨骼索引。

## FReferenceSkeleton 骨骼层级结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| RawRefBoneInfo | TArray&lt;FMeshBoneInfo&gt; | 骨骼信息数组（名称+父索引） | ReferenceSkeleton.h 第 108 行 |
| RawRefBonePose | TArray&lt;FTransform&gt; | 骨骼参考姿势变换数组 | ReferenceSkeleton.h 第 110 行 |
| RawNameToIndexMap | TMap&lt;FName, int32&gt; | 骨骼名称到索引映射 | ReferenceSkeleton.h 第 119 行 |
| FinalRefBoneInfo | TArray&lt;FMeshBoneInfo&gt; | 含虚拟骨骼的信息数组 | ReferenceSkeleton.h 第 114 行 |
| FinalRefBonePose | TArray&lt;FTransform&gt; | 含虚拟骨骼的姿势数组 | ReferenceSkeleton.h 第 116 行 |
| FinalNameToIndexMap | TMap&lt;FName, int32&gt; | 含虚拟骨骼的名称映射 | ReferenceSkeleton.h 第 120 行 |

说明：RawRefBoneInfo 和 FinalRefBoneInfo 区别在于后者包含虚拟骨骼（Virtual Bones）。

## FMeshBoneInfo 单骨骼信息

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Name | FName | 骨骼名称 | ReferenceSkeleton.h 第 16 行 |
| ParentIndex | int32 | 父骨骼索引（根骨骼为 INDEX_NONE） | ReferenceSkeleton.h 第 19 行 |
| ExportName | FString (EditorOnly) | 导出名称 | ReferenceSkeleton.h 第 23 行 |

说明：
- ParentIndex = -1 (INDEX_NONE) 表示根骨骼
- 其他骨骼的 ParentIndex 指向数组中的父骨骼
- ParentIndex 必须小于当前骨骼索引（深度优先顺序）

## FTransform 骨骼变换

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Translation | FVector | 骨骼位置 | Core/Public/Math/Transform.h |
| Rotation | FQuat | 骨骼旋转（四元数） | Core/Public/Math/Transform.h |
| Scale3D | FVector | 骨骼缩放 | Core/Public/Math/Transform.h |

说明：骨骼变换为相对于父骨骼的局部变换，根骨骼变换相对于世界原点。

## 骨骼层级存储规则

- **深度优先顺序**: 子骨骼索引大于父骨骼索引，保证遍历时父骨骼先于子骨骼
- **根骨骼索引**: ParentIndex = INDEX_NONE (-1)，通常为数组第一个元素
- **骨骼数量约束**: RawRefBoneInfo.Num() == RawRefBonePose.Num()

### 示例结构

```
骨骼索引  名称         ParentIndex
[0]      Root         -1 (根)
[1]      Spine        0
[2]      Spine1       1
[3]      Head         2
[4]      L_Shoulder   2
[5]      L_Arm        4
[6]      L_Hand       5
[7]      R_Shoulder   2
...
```

## 骨骼索引查找

- **通过名称查找**: 使用 RawNameToIndexMap 或 FinalNameToIndexMap
- **通过索引获取名称**: RawRefBoneInfo[BoneIndex].Name
- **获取父骨骼**: GetParentIndex(BoneIndex) 返回 ParentIndex
- **向上遍历祖先**: 循环调用 GetParentIndex 直到到达根骨骼

## 虚拟骨骼 (Virtual Bones)

UE5 支持虚拟骨骼，用于 IK 和动画控制：
- FinalRefBoneInfo 包含原始骨骼 + 虚拟骨骼
- RequiredVirtualBones 存储虚拟骨骼需求列表
- UsedVirtualBoneData 存储虚拟骨骼引用数据

## 源码引用

- Runtime/Engine/Public/ReferenceSkeleton.h — FReferenceSkeleton 定义、FMeshBoneInfo 定义
- Runtime/Engine/Classes/Engine/Skeleton.h — USkeleton 定义
- Runtime/Engine/Private/Engine/Skeleton.cpp — 骨骼层级序列化

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| 虚拟骨骼支持 | FinalRefBoneInfo/FinalRefBonePose 包含虚拟骨骼 |
| FVirtualBoneRefData | 虚拟骨骼引用数据结构 |
| 多根骨骼支持 | bOnlyOneRootAllowed 可设为 false |

### UE4 特性
| 特性 | 说明 |
|------|------|
| 仅原始骨骼 | RawRefBoneInfo/RawRefBonePose |
| 单根骨骼限制 | bOnlyOneRootAllowed 默认 true |
| 无虚拟骨骼 | 不支持 IK 驱动虚拟骨骼 |