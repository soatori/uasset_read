# 静态网格基础结构

## 概述

UStaticMesh 是 UE 引擎中用于存储静态几何体的资产类型。静态网格包含：
- 渲染数据：顶点位置、法线、UV、索引缓冲
- LOD 系统：多级细节数据，通过 ScreenSize 自动切换
- 材质槽：材质引用和 UV 通道信息
- 碰撞数据：简单碰撞和复杂碰撞几何

静态网格不包含动画数据，适用于环境物体、建筑结构等静态场景元素。

## UStaticMesh 主类字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| RenderData | TUniquePtr&lt;FStaticMeshRenderData&gt; | 渲染数据容器 | StaticMesh.h 第 621-623 行 |
| BodySetup | TObjectPtr&lt;UBodySetup&gt; | 碰撞体定义 | StaticMesh.h (通过 IInterface_CollisionDataProvider) |
| StaticMaterials | TArray&lt;FStaticMaterial&gt; | 材质槽数组 | StaticMesh.h 第 506-523 行 (FStaticMaterial 结构) |
| LODGroup | FName | LOD 组设置 | StaticMesh.h 第 687-690 行 |
| MinLOD | FPerPlatformInt | 最小 LOD 级别 | StaticMesh.h (通过 FPerPlatformProperties) |
| NaniteSettings | FMeshNaniteSettings | Nanite 设置 | StaticMesh.h 第 735-736 行 |

说明：RenderData 是静态网格的核心渲染数据容器，包含所有 LOD 级别的顶点和索引数据。

## FStaticMeshRenderData 渲染数据容器字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| LODResources | FStaticMeshLODResourcesArray | LOD 资源数组 | StaticMeshResources.h 第 785 行 |
| LODVertexFactories | FStaticMeshVertexFactoriesArray | 顶点工厂数组 | StaticMeshResources.h 第 786 行 |
| ScreenSize | FPerPlatformFloat[MAX_STATIC_MESH_LODS] | LOD 切换阈值 | StaticMeshResources.h 第 789 行 |
| Bounds | FBoxSphereBounds | 包围盒 | StaticMeshResources.h 第 797 行 |
| NaniteResourcesPtr | TPimplPtr&lt;Nanite::FResources&gt; | Nanite 数据 | StaticMeshResources.h 第 791 行 |
| RayTracingProxy | FStaticMeshRayTracingProxy* | 光线追踪代理 | StaticMeshResources.h 第 794 行 |

说明：MAX_STATIC_MESH_LODS = 8（StaticMesh.h 第 59 行），最多支持 8 级 LOD。

## FStaticMaterial 材质槽结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialInterface | TObjectPtr&lt;UMaterialInterface&gt; | 材质对象引用 | StaticMesh.h 第 506-507 行 |
| MaterialSlotName | FName | 材质槽名称 | StaticMesh.h 第 510-511 行 |
| ImportedMaterialSlotName | FName | 导入时的材质槽名 | StaticMesh.h 第 514-515 行 |
| UVChannelData | FMeshUVChannelInfo | UV 通道信息 | StaticMesh.h 第 517-519 行 |

## 源码引用

- Runtime/Engine/Classes/Engine/StaticMesh.h — UStaticMesh 主类定义、FStaticMaterial 定义
- Runtime/Engine/Public/StaticMeshResources.h — FStaticMeshRenderData、FStaticMeshLODResources 定义
- Runtime/Engine/Private/Engine/StaticMesh.cpp — 序列化实现

## 版本差异

### UE5 新增特性
| 特性 | 说明 | 源码位置 |
|------|------|----------|
| NaniteResourcesPtr | Nanite 数据指针 | StaticMeshResources.h 第 791 行 |
| TObjectPtr | 智能指针替代原始指针 | StaticMesh.h 第 506-507 行 |
| FPerPlatformInt/FPerPlatformFloat | 平台相关 LOD 控制 | StaticMesh.h |
| ImportedMaterialSlotName | 材质重映射支持 | StaticMesh.h 第 514-515 行 |

### UE4 特性
- 使用简单 MinLOD 整数值
- Materials_DEPRECATED 旧版材质数组 (StaticMesh.h 第 729-731 行)