# 骨骼网格基础结构

## 概述

USkeletalMesh 是 UE 引擎中用于存储可动画几何体的资产类型。骨骼网格包含：
- 渲染数据：顶点位置、法线、UV、索引缓冲
- 骨骼层级：骨骼树结构和参考姿势变换
- 皮肤权重：逐顶点骨骼影响和权重值
- LOD 系统：多级细节数据，支持可变骨骼影响
- 材质槽：材质引用和 UV 通道信息
- 变形目标：MorphTargets 支持网格变形

骨骼网格用于角色、动物等需要骨骼动画的物体。

## USkeletalMesh 主类字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Skeleton | TObjectPtr&lt;USkeleton&gt; | 骨骼资产引用 | SkeletalMesh.h 第 729-730 行 |
| Materials | TArray&lt;FSkeletalMaterial&gt; | 材质槽数组 | SkeletalMesh.h 第 902-903 行 |
| MorphTargets | TArray&lt;TObjectPtr&lt;UMorphTarget&gt;&gt; | 变形目标数组 | SkeletalMesh.h 第 915 行 |
| ImportedBounds | FBoxSphereBounds | 导入时包围盒 | SkeletalMesh.h 第 774-776 行 |
| ExtendedBounds | FBoxSphereBounds | 扩展包围盒 | SkeletalMesh.h 第 779-781 行 |
| PositiveBoundsExtension | FVector | 正向包围盒扩展 | SkeletalMesh.h 第 807-809 行 |
| NegativeBoundsExtension | FVector | 负向包围盒扩展 | SkeletalMesh.h 第 821-823 行 |
| NaniteSettings | FMeshNaniteSettings | Nanite 设置 | SkeletalMesh.h 第 943-944 行 |

说明：Skeleton 字段引用 USkeleton 资产，USkeleton 持有 FReferenceSkeleton 骨骼层级定义。

## FSkeletalMeshRenderData 渲染数据容器字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| LODRenderData | TIndirectArray&lt;FSkeletalMeshLODRenderData&gt; | LOD 渲染数据数组 | SkeletalMeshRenderData.h |
| NumInlinedLODs | int32 | 内联 LOD 数量 | SkeletalMeshRenderData.h |
| CurrentFirstLODIdx | int32 | 当前首个 LOD 索引 | SkeletalMeshRenderData.h |

## FSkeletalMeshLODRenderData 单 LOD 渲染数据字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| RenderSections | TArray&lt;FSkelMeshRenderSection&gt; | 渲染分段数组 | SkeletalMeshLODRenderData.h |
| StaticVertexBuffers | FStaticMeshVertexBuffers | 静态顶点缓冲 | SkeletalMeshLODRenderData.h |
| SkinWeightVertexBuffer | FSkinWeightVertexBuffer | 皮肤权重缓冲 | SkeletalMeshLODRenderData.h |
| MultiSizeIndexContainer | FRawStaticIndexBuffer | 索引缓冲容器 | SkeletalMeshLODRenderData.h |
| ActiveBoneIndices | TArray&lt;FBoneIndexType&gt; | 活跃骨骼列表 | SkeletalMeshLODRenderData.h |

## FSkeletalMaterial 骨骼网格材质槽

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialInterface | TObjectPtr&lt;UMaterialInterface&gt; | 材质对象引用 | SkeletalMesh.h 第 900 行 |
| MaterialSlotName | FName | 材质槽名称 | SkeletalMesh.h 第 902 行 |
| UVChannelData | FMeshUVChannelInfo | UV 通道信息 | SkeletalMesh.h 第 904 行 |

详细材质槽结构见 [skeletal-mesh-material.md](skeletal-mesh-material.md)。

## 骨骼网格与静态网格的关系

骨骼网格复用静态网格的顶点缓冲结构（FStaticMeshVertexBuffers），但额外包含：
- SkinWeightVertexBuffer: 皮肤权重数据
- ActiveBoneIndices: 该 LOD 活跃骨骼列表
- MorphTargets: 变形目标数组

## 源码引用

- Runtime/Engine/Classes/Engine/SkeletalMesh.h — USkeletalMesh 主类定义
- Runtime/Engine/Public/Rendering/SkeletalMeshRenderData.h — FSkeletalMeshRenderData 定义
- Runtime/Engine/Public/Rendering/SkeletalMeshLODRenderData.h — FSkeletalMeshLODRenderData 定义
- Runtime/Engine/Private/Engine/SkeletalMesh.cpp — 序列化实现

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| TObjectPtr | 智能指针替代原始指针 |
| MorphTargets 增强 | 更多变形目标支持 |
| Nanite 支持 | 骨骼网格 Nanite 实验性支持 |
| CachedComposedRefPoseMatrices | 缓存参考姿势矩阵 |

### UE4 特性
| 特性 | 说明 |
|------|------|
| 原始指针 | USkeleton* 直接引用 |
| Materials 数组 | 简单材质槽数组 |
| SkelMirrorTable | 骨骼镜像表（已废弃） |