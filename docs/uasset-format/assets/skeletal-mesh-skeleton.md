# 骨骼网格骨骼层级

## 概述

骨骼层级存储在 `FReferenceSkeleton` 结构中，该结构存在于 `USkeletalMesh`（通过 `RefSkeleton` 字段）和 `USkeleton` 资产中。`FReferenceSkeleton` 包含骨骼树信息和参考姿势变换。骨骼按深度优先顺序存储，子骨骼索引大于父骨骼索引。

## FReferenceSkeleton 骨骼层级结构

> 定义在 `ReferenceSkeleton.h`，结构体共有 476 行。

| 字段名 | 访问权限 | 类型 | 用途 | 源码位置 |
|--------|----------|------|------|----------|
| RawRefBoneInfo | private | TArray&lt;FMeshBoneInfo&gt; | 原始骨骼信息数组（名称+父索引） | ReferenceSkeleton.h 第 108 行 |
| RawRefBonePose | private | TArray&lt;FTransform&gt; | 原始骨骼参考姿势变换数组 | ReferenceSkeleton.h 第 110 行 |
| RawNameToIndexMap | private | TMap&lt;FName, int32&gt; | 原始骨骼名称到索引映射 | ReferenceSkeleton.h 第 119 行 |
| FinalRefBoneInfo | private | TArray&lt;FMeshBoneInfo&gt; | 含虚拟骨骼的最终骨骼信息数组 | ReferenceSkeleton.h 第 114 行 |
| FinalRefBonePose | private | TArray&lt;FTransform&gt; | 含虚拟骨骼的最终姿势数组 | ReferenceSkeleton.h 第 116 行 |
| FinalNameToIndexMap | private | TMap&lt;FName, int32&gt; | 含虚拟骨骼的最终名称映射 | ReferenceSkeleton.h 第 120 行 |
| RequiredVirtualBones | private | TArray&lt;FBoneIndexType&gt; | 需要的虚拟骨骼列表 | ReferenceSkeleton.h 第 123 行 |
| UsedVirtualBoneData | private | TArray&lt;FVirtualBoneRefData&gt; | 已使用的虚拟骨骼引用数据 | ReferenceSkeleton.h 第 124 行 |
| bOnlyOneRootAllowed | private | bool | 是否仅允许一个根骨骼 | ReferenceSkeleton.h 第 132 行 |
| CachedEndOfBranchIndicesRaw | private (mutable) | TArray&lt;int32&gt; | 缓存的分支末端索引 | ReferenceSkeleton.h 第 136 行 |

> **修正**：原 wiki 中"源码位置"写为"ReferenceSkeleton.h 第 108 行"等，实际行号已确认。原 wiki 描述为"public"字段，实际这些字段为 `private`，通过公共 getter 方法访问。

### 公共访问方法

| 方法名 | 返回类型 | 用途 | 源码位置 |
|--------|----------|------|----------|
| GetRefBoneInfo() | const TArray&lt;FMeshBoneInfo&gt;& | 获取最终骨骼信息（含虚拟骨骼） | ReferenceSkeleton.h 第 257 行 |
| GetRefBonePose() | const TArray&lt;FTransform&gt;& | 获取最终骨骼姿势（含虚拟骨骼） | ReferenceSkeleton.h 第 263 行 |
| GetRawRefBoneInfo() | const TArray&lt;FMeshBoneInfo&gt;& | 获取原始骨骼信息 | ReferenceSkeleton.h 第 269 行 |
| GetRawRefBonePose() | const TArray&lt;FTransform&gt;& | 获取原始骨骼姿势 | ReferenceSkeleton.h 第 275 行 |
| GetRawNameToIndexMap() | const TMap&lt;FName, int32&gt;& | 获取原始名称映射 | ReferenceSkeleton.h 第 280 行 |
| GetNum() | int32 | 获取最终骨骼总数 | ReferenceSkeleton.h 第 241 行 |
| GetRawBoneNum() | int32 | 获取原始骨骼总数 | ReferenceSkeleton.h 第 247 行 |
| FindBoneIndex(FName) | int32 | 通过名称查找最终骨骼索引 | ReferenceSkeleton.h 第 311 行 |
| FindRawBoneIndex(FName) | int32 | 通过名称查找原始骨骼索引 | ReferenceSkeleton.h 第 327 行 |
| GetParentIndex(int32) | int32 | 获取父骨骼索引（最终） | ReferenceSkeleton.h 第 347 行 |
| GetRawParentIndex(int32) | int32 | 获取父骨骼索引（原始） | ReferenceSkeleton.h 第 352 行 |
| GetBoneName(int32) | FName | 获取骨骼名称 | ReferenceSkeleton.h 第 342 行 |
| GetRequiredVirtualBones() | const TArray&lt;FBoneIndexType&gt;& | 获取需要的虚拟骨骼 | ReferenceSkeleton.h 第 252 行 |
| GetVirtualBoneRefData() | const TArray&lt;FVirtualBoneRefData&gt;& | 获取虚拟骨骼引用数据 | ReferenceSkeleton.h 第 254 行 |

## FMeshBoneInfo 单骨骼信息

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Name | FName | 骨骼名称 | ReferenceSkeleton.h 第 16 行 |
| ParentIndex | int32 | 父骨骼索引（根骨骼为 INDEX_NONE） | ReferenceSkeleton.h 第 19 行 |
| ExportName | FString (EditorOnly) | 导出名称（精确大小写） | ReferenceSkeleton.h 第 23 行 |

说明：
- ParentIndex = -1 (INDEX_NONE) 表示根骨骼
- 其他骨骼的 ParentIndex 指向数组中的父骨骼
- ParentIndex 必须小于当前骨骼索引（深度优先顺序）
- ExportName 仅在 `WITH_EDITORONLY_DATA` 下存在

## FVirtualBoneRefData 虚拟骨骼引用数据

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| VBRefSkelIndex | int32 | 虚拟骨骼在 ReferenceSkeleton 中的索引 | ReferenceSkeleton.h 第 47 行 |
| SourceRefSkelIndex | int32 | 虚拟骨骼源骨骼索引 | ReferenceSkeleton.h 第 48 行 |
| TargetRefSkelIndex | int32 | 虚拟骨骼目标骨骼索引 | ReferenceSkeleton.h 第 49 行 |

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
- **严格递增顺序**: 骨骼数组严格递增，子骨骼索引始终大于父骨骼索引

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

- **通过名称查找**: 使用 FindBoneIndex()（最终）或 FindRawBoneIndex()（原始），内部通过 TMap 查找
- **通过索引获取名称**: GetBoneName(BoneIndex) 或 FinalRefBoneInfo[BoneIndex].Name
- **获取父骨骼**: GetParentIndex(BoneIndex) 返回 Final 的 ParentIndex，GetRawParentIndex() 返回 Raw 的
- **向上遍历祖先**: 循环调用 GetParentIndex 直到到达根骨骼
- **判断子关系**: BoneIsChildOf(ChildBoneIndex, ParentBoneIndex) 判断是否为子孙骨骼
- **获取深度**: GetDepthBetweenBones(BoneIndex, ParentBoneIndex) 获取层级深度

## 虚拟骨骼 (Virtual Bones)

UE5 支持虚拟骨骼，用于 IK 和动画控制：
- FinalRefBoneInfo 包含原始骨骼 + 虚拟骨骼
- RequiredVirtualBones (TArray<FBoneIndexType>) 存储虚拟骨骼需求列表
- UsedVirtualBoneData (TArray<FVirtualBoneRefData>) 存储虚拟骨骼引用数据
- FVirtualBoneRefData 包含三个字段：VBRefSkelIndex、SourceRefSkelIndex、TargetRefSkelIndex
- FReferenceSkeletonModifier 类用于安全修改骨骼层级并保证虚拟骨骼有效性
- bOnlyOneRootAllowed 控制是否允许多根骨骼（默认 true，ControlRig 等可设为 false）

## 源码引用

- Runtime/Engine/Public/ReferenceSkeleton.h — FReferenceSkeleton 定义（476 行）、FMeshBoneInfo 定义、FVirtualBoneRefData 定义、FReferenceSkeletonModifier 定义
- Runtime/Engine/Classes/Engine/Skeleton.h — USkeleton 定义
- Runtime/Engine/Private/Animation/ReferenceSkeleton.cpp — 骨骼层级序列化
- Runtime/Engine/Classes/Engine/SkeletalMesh.h — USkeletalMesh::RefSkeleton（第 2022 行）

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| 虚拟骨骼支持 | FinalRefBoneInfo/FinalRefBonePose 包含虚拟骨骼 |
| FVirtualBoneRefData | 虚拟骨骼引用数据结构 |
| 多根骨骼支持 | bOnlyOneRootAllowed 可设为 false |
| FReferenceSkeletonModifier | 安全的骨骼层级修改器 |
| CachedEndOfBranchIndices | 缓存的分支末端索引，加速子骨骼遍历 |

### UE4 特性
| 特性 | 说明 |
|------|------|
| 仅原始骨骼 | RawRefBoneInfo/RawRefBonePose |
| 单根骨骼限制 | bOnlyOneRootAllowed 默认 true |
| 无虚拟骨骼 | 不支持 IK 驱动虚拟骨骼 |
| 无分支缓存 | 无 CachedEndOfBranchIndices 优化 |
