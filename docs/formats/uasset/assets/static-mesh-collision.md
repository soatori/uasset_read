# 静态网格碰撞数据

## 概述

静态网格通过 UBodySetup 存储碰撞定义，包含简单碰撞几何（球/盒/胶囊/凸包/锥形胶囊/LevelSet）和烘焙物理数据。碰撞数据用于物理模拟、射线检测和导航生成。

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
| SphereElems | TArray&lt;FKSphereElem&gt; | 球形碰撞体数组 | AggregateGeom.h 第 28 行 |
| BoxElems | TArray&lt;FKBoxElem&gt; | 盒形碰撞体数组 | AggregateGeom.h 第 31 行 |
| SphylElems | TArray&lt;FKSphylElem&gt; | 胶囊碰撞体数组 | AggregateGeom.h 第 34 行 |
| ConvexElems | TArray&lt;FKConvexElem&gt; | 凸包碰撞体数组 | AggregateGeom.h 第 37 行 |
| TaperedCapsuleElems | TArray&lt;FKTaperedCapsuleElem&gt; | 锥形胶囊数组 | AggregateGeom.h 第 40 行 |
| LevelSetElems | TArray&lt;FKLevelSetElem&gt; | LevelSet 碰撞数组 | AggregateGeom.h 第 43 行 |
| SkinnedLevelSetElems | TArray&lt;FKSkinnedLevelSetElem&gt; | （实验性）骨骼 LevelSet 碰撞 | AggregateGeom.h 第 46 行 |
| MLLevelSetElems | TArray&lt;FKMLLevelSetElem&gt; | （实验性）ML LevelSet 碰撞 | AggregateGeom.h 第 49 行 |
| SkinnedTriangleMeshElems | TArray&lt;FKSkinnedTriangleMeshElem&gt; | （实验性）骨骼三角面网格碰撞 | AggregateGeom.h 第 52 行 |

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

FKConvexElem 继承自 FKShapeElem，是用于简化碰撞的凸包结构。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| VertexData | TArray&lt;FVector&gt; | 凸包顶点数组 | ConvexElem.h 第 36-37 行 |
| IndexData | TArray&lt;int32&gt; | 凸包索引数组 | ConvexElem.h 第 39-40 行 |
| ElemBox | FBox | 凸包包围盒 | ConvexElem.h 第 43-44 行 |
| Transform | FTransform（私有） | 应用于凸包顶点的变换 | ConvexElem.h 第 48-49 行 |
| ChaosConvex | Chaos::FConvexPtr（私有） | Chaos 物理凸包网格对象 | ConvexElem.h 第 51 行 |

说明：
- 凸包碰撞由外部工具生成，通常用于复杂形状的简化碰撞
- ChaosConvex 是 UE5 Chaos 物理引擎的内部表示，通过 SetConvexMeshObject / ResetChaosConvexMesh 管理
- Transform 为私有字段，通过 GetTransform() / SetTransform() 访问
- IndexData 由 Chaos 引擎计算或手动设置，用于渲染和碰撞检测
- UE5.1 起 GetVolume() 标记为废弃，改用 GetScaledVolume()（含非均匀缩放）
- UE5.4 起 SetChaosConvexMesh() 标记为废弃，改用 SetConvexMeshObject()

## 碰撞数据存储

### 简单碰撞
- 直接存储几何参数（球/盒/胶囊）
- 在 Editor 中手动添加或自动生成
- 序列化为 FKAggregateGeom 结构

### 复杂碰撞
- **凸包**: ConvexElems 存储凸包顶点和索引，同时维护 ChaosConvex 物理网格
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
- Runtime/Engine/Private/Collision/KAggregateGeom.cpp — FKConvexElem 序列化实现

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| ChaosConvex | Chaos 物理引擎凸包网格内部表示 |
| Transform 字段 | FKConvexElem 增加独立的 Transform 管理 |
| LevelSetElems | LevelSet 碰撞支持 |
| SkinnedLevelSetElems | （实验性）骨骼网格 LevelSet 碰撞 |
| MLLevelSetElems | （实验性）ML LevelSet 碰撞 |
| SkinnedTriangleMeshElems | （实验性）骨骼三角面网格碰撞 |
| TaperedCapsuleElems | 锥形胶囊碰撞支持 |
| GetScaledVolume | 替代 GetVolume，支持非均匀缩放体积计算 |
| SetConvexMeshObject | 替代 SetChaosConvexMesh 的新 API |
| EConvexDataUpdateMethod | 凸包数据更新策略枚举 |

### UE4 特性
| 特性 | 说明 |
|------|------|
| 简单碰撞数据 | 球/盒/胶囊/凸包基础支持 |
| CookedFormatData | 物理烘焙数据基础格式 |
| PhysX 物理引擎 | 使用 PhysX 而非 Chaos |
| 无 Transform 字段 | FKConvexElem 无独立变换管理 |
