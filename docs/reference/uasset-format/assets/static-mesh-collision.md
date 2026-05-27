# 静态网格碰撞数据

## 概述

静态网格通过 UBodySetup 存储碰撞定义，包含简单碰撞几何（球/盒/胶囊/凸包）和烘焙物理数据。碰撞数据用于物理模拟、射线检测和导航生成。

## UBodySetup 碰撞体定义

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| AggGeom | FKAggregateGeom | 简单碰撞几何聚合容器 | BodySetup.h |
| CookedFormatData | FKCollisionCookingData | 烘焙物理数据 | BodySetup.h |
| PhysMaterial | TObjectPtr&lt;UPhysicalMaterial&gt; | 物理材质引用 | BodySetup.h |
| CollisionResponse | FCollisionResponseContainer | 碰撞响应设置 | BodySetup.h |
| CollisionTraceFlag | ECollisionTraceFlag | 碰撞追踪类型 | BodySetup.h |

### ECollisionTraceFlag 碰撞追踪类型
| 值 | 说明 |
|-----|------|
| CTF_UseDefault | 使用默认设置 |
| CTF_UseSimpleAndComplex | 使用简单和复杂碰撞 |
| CTF_UseSimpleOnly | 仅使用简单碰撞 |
| CTF_UseComplexOnly | 仅使用复杂碰撞（网格三角面） |

## FKAggregateGeom 碰撞几何聚合

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| SphereElems | TArray&lt;FKSphereElem&gt; | 球形碰撞体数组 | AggregateGeom.h |
| BoxElems | TArray&lt;FKBoxElem&gt; | 盒形碰撞体数组 | AggregateGeom.h |
| SphylElems | TArray&lt;FKSphylElem&gt; | 胶囊碰撞体数组 | AggregateGeom.h |
| ConvexElems | TArray&lt;FKConvexElem&gt; | 凸包碰撞体数组 | AggregateGeom.h |
| TaperedCapsuleElems | TArray&lt;FKTaperedCapsuleElem&gt; | 锥形胶囊数组 | AggregateGeom.h |

## FKSphereElem 球形碰撞

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Center | FVector | 球心位置 | SphereElem.h |
| Radius | float | 球半径 | SphereElem.h |

## FKBoxElem 盒形碰撞

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Center | FVector | 盒中心位置 | BoxElem.h |
| Rotation | FRotator | 盒旋转 | BoxElem.h |
| X | float | 盒 X 轴尺寸 | BoxElem.h |
| Y | float | 盒 Y 轴尺寸 | BoxElem.h |
| Z | float | 盒 Z 轴尺寸 | BoxElem.h |

## FKSphylElem 胶囊碰撞

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Center | FVector | 胶囊中心 | SphylElem.h |
| Rotation | FRotator | 胶囊旋转 | SphylElem.h |
| Radius | float | 胶囊半径 | SphylElem.h |
| Length | float | 胶囊长度（不含端盖） | SphylElem.h |

## FKConvexElem 凸包碰撞

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| VertexData | TArray&lt;FVector&gt; | 凸包顶点 | ConvexElem.h |
| IndexData | TArray&lt;int32&gt; | 凸包索引 | ConvexElem.h |
| BoundingBox | FBox | 凸包包围盒 | ConvexElem.h |

说明：凸包碰撞由外部工具生成，通常用于复杂形状的简化碰撞。

## 碰撞数据存储

### 简单碰撞
- 直接存储几何参数（球/盒/胶囊）
- 在 Editor 中手动添加或自动生成
- 序列化为 FKAggregateGeom 结构

### 复杂碰撞
- **凸包**: ConvexElems 存储凸包顶点和索引
- **烘焙数据**: CookedFormatData 存储物理引擎烘焙数据
- **网格碰撞**: 使用静态网格三角形作为碰撞面（CTF_UseComplexOnly）

### 物理材质
- PhysMaterial 引用 UPhysicalMaterial 资产
- 定义摩擦、弹性等物理属性
- 存储在 Import 表或 Export 表中

## 碰撞与分段关联

FStaticMeshSection 的 bEnableCollision 标志控制该分段是否参与碰撞：
- bEnableCollision = true: 该分段三角形参与复杂碰撞
- bEnableCollision = false: 该分段仅用于渲染

## 源码引用

- Runtime/Engine/Classes/PhysicsEngine/BodySetup.h — UBodySetup 定义
- Runtime/Engine/Classes/PhysicsEngine/AggregateGeom.h — FKAggregateGeom 定义
- Runtime/Engine/Classes/PhysicsEngine/SphereElem.h — FKSphereElem 定义
- Runtime/Engine/Classes/PhysicsEngine/BoxElem.h — FKBoxElem 定义
- Runtime/Engine/Classes/PhysicsEngine/SphylElem.h — FKSphylElem 定义
- Runtime/Engine/Classes/PhysicsEngine/ConvexElem.h — FKConvexElem 定义
- Runtime/Engine/Private/PhysicsEngine/BodySetup.cpp — 碰撞序列化

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| CookedFormatData 增强 | 物理烘焙数据格式升级 |
| LevelSetElems | 实验性 LevelSet 碰撞支持 |
| SkinnedLevelSetElems | 骨骼网格 LevelSet 碰撞 |

### UE4 特性
| 特性 | 说明 |
|------|------|
| 简单碰撞数据 | 球/盒/胶囊/凸包基础支持 |
| CookedFormatData | 物理烘焙数据基础格式 |