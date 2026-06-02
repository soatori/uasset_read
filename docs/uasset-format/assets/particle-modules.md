# UParticleModule — Cascade 粒子模块类型目录

## 概述

UParticleModule 是 Cascade 粒子模块的基类，继承自 UObject，使用 `Within=ParticleSystem` 约束。所有粒子行为（位置、速度、颜色、大小、生命周期等）通过 Module 组合实现。

**模块执行时机：**
- Spawn: 粒子生成时调用（bSpawnModule=true）
- Update: 粒子更新时调用（bUpdateModule=true）
- FinalUpdate: 最终更新时调用（bFinalUpdateModule=true）

**模块类型标记（EModuleType）：**
决定模块适用的发射器类型。

**核心模块：**
每个 UParticleLODLevel 必需：
- RequiredModule (UParticleModuleRequired) — 必需模块
- SpawnModule (UParticleModuleSpawn) — 生成模块

本文档按类别列出 Module 类型目录，仅文档化基类和核心模块（per D-04）。详细字段表在各 Module 源码中查阅。

## UParticleModule 基类字段表

### 核心字段

| 字段名 | 类型 | 默认值 | 用途 | 源码行 |
|--------|------|--------|------|--------|
| bSpawnModule | uint8:1 | - | 在粒子生成时执行 | ParticleModule.h:154 |
| bUpdateModule | uint8:1 | - | 在粒子更新时执行 | ParticleModule.h:158 |
| bFinalUpdateModule | uint8:1 | - | 在最终更新时执行 | ParticleModule.h:162 |
| bUpdateForGPUEmitter | uint8:1 | - | 对 GPU 发射器执行 | ParticleModule.h:166 |
| bCurvesAsColor | uint8:1 | false | FVector 曲线显示为颜色 | ParticleModule.h:170 |
| b3DDrawMode | uint8:1 | false | 启用 3D 可视化绘制 | ParticleModule.h:174 |
| bSupported3DDrawMode | uint8:1 | - | 支持 3D 可视化 | ParticleModule.h:178 |
| bEnabled | uint8:1 | true | 模块是否启用 | ParticleModule.h:182 |
| bEditable | uint8:1 | true | 模块是否可编辑 | ParticleModule.h:186 |
| LODDuplicate | uint8:1 | - | LOD 自动生成时为精确副本 | ParticleModule.h:194 |
| bSupportsRandomSeed | uint8:1 | - | 支持随机种子设置 | ParticleModule.h:198 |
| bRequiresLoopingNotification | uint8:1 | - | 需要发射器循环通知 | ParticleModule.h:202 |
| LODValidity | uint8 | 0xFF | LOD 有效性位标志（(1&lt;&lt;Level) &amp; LODValidity != 0 表示在该 LOD 中有效） | ParticleModule.h:212 |

### WITH_EDITORONLY_DATA 字段

| 字段名 | 类型 | 用途 | 源码行 |
|--------|------|------|--------|
| ModuleEditorColor | FColor | 曲线编辑器颜色 | ParticleModule.h:219 |

### EModuleType 枚举

| 值 | 说明 |
|----|------|
| EPMT_General | 通用，所有发射器类型可用 |
| EPMT_TypeData | 类型数据模块 |
| EPMT_Beam | 仅光束发射器 |
| EPMT_Trail | 仅轨迹发射器 |
| EPMT_Spawn | 所有发射器必需 |
| EPMT_Required | 所有发射器必需 |
| EPMT_Event | 事件相关模块 |
| EPMT_Light | 光照相关模块 |
| EPMT_SubUV | SubUV 相关模块 |

### FParticleRandomSeedInfo 结构

_Seeded 后缀模块使用的随机种子信息结构：

| 字段名 | 类型 | 用途 | 源码行 |
|--------|------|------|--------|
| ParameterName | FName | 暴露给实例设置的种子参数名 | ParticleModule.h:93 |
| bGetSeedFromInstance | uint8:1 | 从所有者实例获取种子 | ParticleModule.h:100 |
| bInstanceSeedIsIndex | uint8:1 | 实例种子值为索引 | ParticleModule.h:108 |
| bResetSeedOnEmitterLooping | uint8:1 | 发射器循环时重置种子 | ParticleModule.h:116 |
| bRandomlySelectSeedArray | uint8:1 | 从种子数组随机选择 | ParticleModule.h:122 |
| RandomSeeds | TArray&lt;int32&gt; | 随机种子值数组 | ParticleModule.h:129 |

## 核心模块详情

### UParticleModuleRequired（必需模块）

每个 UParticleLODLevel 必须有且仅有一个 RequiredModule。GetModuleType() 返回 EPMT_Required。

**源码：** Runtime/Engine/Classes/Particles/ParticleModuleRequired.h

**核心字段：**
| 字段名 | 类型 | 用途 |
|--------|------|------|
| Material | TObjectPtr&lt;UMaterialInterface&gt; | 粒子渲染材质 → 见 [assets/material.md](material.md) |
| SpawnRate | FRawDistributionFloat | 每秒生成粒子数 |
| BurstList | TArray&lt;FParticleBurst&gt; | 突发粒子列表 |
| EmitterOrigin | FVector | 发射器原点 |
| EmitterRotation | FRotator | 发射器旋转 |
| ScreenAlignment | EParticleScreenAlignment | 屏幕对齐方式 |
| SortMode | EParticleSortMode | 粒子排序模式 |
| bUseLocalSpace | uint8:1 | 使用本地空间 |
| bKillOnDeactivate | uint8:1 | 系统停用时销毁发射器 |
| bKillOnCompleted | uint8:1 | 发射器完成时销毁 |
| EmitterDuration | float | 发射器运行时长 |
| EmitterLoops | int32 | 循环次数（0=无限） |
| EmitterDelay | float | 发射器延迟 |
| InterpolationMethod | EParticleSubUVInterpMethod | SubUV 插值方法 |
| SubImages_Horizontal | int32 | 水平子图数量 |
| SubImages_Vertical | int32 | 垂直子图数量 |
| CutoutTexture | TObjectPtr&lt;UTexture2D&gt; | Cutout 纹理 |
| MaxDrawCount | int32 | 最大绘制粒子数 |
| NamedMaterialOverrides | TArray&lt;FName&gt; | 命名材质覆盖槽名列表 |
| EmitterNormalsMode | EEmitterNormalsMode | 法线生成模式 |
| UVFlippingMode | EParticleUVFlipMode | UV 翻转模式 |
| bSupportLargeWorldCoordinates | uint8:1 | 支持大世界坐标（GPU） |

### UParticleModuleTypeDataBase（类型数据模块基类）

定义发射器的粒子类型（Sprite、Mesh、Beam、Trail、GPU 等）。GetModuleType() 返回 EPMT_TypeData。

**子类：**
| Module | 说明 |
|--------|------|
| UParticleModuleTypeDataGpu | GPU 粒子发射器 |
| UParticleModuleTypeDataMesh | 网格粒子发射器 |
| UParticleModuleTypeDataBeam2 | 光束发射器 |
| UParticleModuleTypeDataRibbon | 轨迹带发射器 |
| UParticleModuleTypeDataAnimTrail | 动画轨迹发射器 |

### UParticleModuleSpawn（生成模块）

控制粒子的生成速率和突发行为。GetModuleType() 返回 EPMT_Spawn。所有发射器必需。

**核心字段：**
| 字段名 | 类型 | 用途 |
|--------|------|------|
| Rate | FRawDistributionFloat | 每秒生成粒子数 |
| RateScale | FRawDistributionFloat | 速率缩放因子 |
| BurstList | TArray&lt;FParticleBurst&gt; | 突发粒子配置 |
| bApplyGlobalScale | uint8:1 | 应用全局缩放 |

### UParticleModuleSpawnBase（生成模块基类）

| Module | 说明 |
|--------|------|
| UParticleModuleSpawn | 标准 Spawn 模块 |
| UParticleModuleSpawnPerUnit | 每单位长度生成粒子 |

## Module 类型目录

按类别列出所有 ParticleModule 子类。每个条目包含：Module 名称 + 2-3 个核心字段说明。

### Acceleration（加速度）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleAcceleration | Acceleration (UDistributionVector) — 加速度向量 |
| UParticleModuleAccelerationBase | 基类，无额外字段 |
| UParticleModuleAccelerationConstant | ConstantAcceleration (FVector) — 恒定加速度 |
| UParticleModuleAccelerationDrag | DragCoefficient (float) — 阻力系数 |
| UParticleModuleAccelerationDragScaleOverLife | DragScale (UCurveFloat) — 生命周期阻力曲线 |
| UParticleModuleAccelerationOverLifetime | AccelLife (UCurveVector) — 生命周期加速度曲线 |

### Attractor（吸引器）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleAttractorBase | 基类，无额外字段 |
| UParticleModuleAttractorLine | SourcePoint/TargetPoint (FVector) — 线段端点 |
| UParticleModuleAttractorParticle | MaxRange (float) — 最大作用范围 |
| UParticleModuleAttractorPoint | AttractorLocation (UDistributionVector) — 吸引点位置 |
| UParticleModuleAttractorPointGravity | GravityStrength (float) — 重力强度 |

### Beam（光束）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleBeamBase | 基类，无额外字段 |
| UParticleModuleBeamModifier | 光束属性修改器 |
| UParticleModuleBeamNoise | NoiseTangentStrength/NoiseFrequency — 噪声参数 |
| UParticleModuleBeamSource | Source 配置 — 源点设置 |
| UParticleModuleBeamTarget | Target 配置 — 目标点设置 |

### Camera（相机）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleCameraBase | 基类，无额外字段 |
| UParticleModuleCameraOffset | CameraOffset (float) — 沿视线方向偏移量 |

### Collision（碰撞）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleCollision | DampingFactor (FVector) — 碰撞阻尼，Lifetime (UDistributionFloat) — 碰撞后生命周期 |
| UParticleModuleCollisionBase | 基类，无额外字段 |
| UParticleModuleCollisionGPU | GPU 碰撞变体 |

### Color（颜色）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleColor | Color (UDistributionVector) — 颜色值，Alpha (UDistributionFloat) — 透明度 |
| UParticleModuleColorBase | 基类，无额外字段 |
| UParticleModuleColorOverLife | ColorOverLife (UCurveVector) — 生命周期颜色曲线 |
| UParticleModuleColorScaleOverLife | ColorScaleOverLife (UCurveVector) — 颜色缩放曲线 |
| UParticleModuleColor_Seeded | 带随机种子的颜色模块 |

### Event（事件）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleEventBase | 基类，无额外字段 |
| UParticleModuleEventGenerator | Events (TArray&lt;FParticleEvent_GenerateInfo&gt;) — 事件生成列表 |
| UParticleModuleEventReceiverBase | 事件接收基类 |
| UParticleModuleEventReceiverKillParticles | 事件触发销毁粒子 |
| UParticleModuleEventReceiverSpawn | 事件触发重新生成 |
| UParticleModuleEventSendToGame | 发送事件到 Game 线程 |

### Kill（粒子销毁）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleKillBase | 基类，无额外字段 |
| UParticleModuleKillBox | LowerLeft/UpperRight (FVector) — 销毁包围盒 |
| UParticleModuleKillHeight | Height (UDistributionFloat) — 超出高度销毁 |

### Lifetime（生命周期）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleLifetime | Lifetime (UDistributionFloat) — 生命周期 Distribution |
| UParticleModuleLifetimeBase | 基类，无额外字段 |
| UParticleModuleLifetime_Seeded | 带随机种子的生命周期 |

### Light（光照）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleLight | LightRadius (UDistributionFloat) — 光照半径，LightIntensity (UDistributionFloat) — 光照强度 |
| UParticleModuleLightBase | 基类，无额外字段 |
| UParticleModuleLight_Seeded | 带随机种子的光照 |

### Location（位置）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleLocation | PositionOffset (UDistributionVector) — 位置偏移 |
| UParticleModuleLocationBase | 基类，无额外字段 |
| UParticleModuleLocationBoneSocket | 骨骼 Socket 位置 |
| UParticleModuleLocationDirect | Position (UDistributionVector) — 直接指定位置 |
| UParticleModuleLocationEmitter | 从其他发射器获取位置 |
| UParticleModuleLocationEmitterDirect | 直接从指定发射器原点 |
| UParticleModuleLocationPrimitiveBase | 几何体位置基类 |
| UParticleModuleLocationPrimitiveCylinder | 圆柱体内位置 |
| UParticleModuleLocationPrimitiveSphere | 球体内位置 |
| UParticleModuleLocationPrimitiveTriangle | 三角形内位置 |
| UParticleModuleLocationSkelVertSurface | 骨骼顶点/表面位置 |
| UParticleModuleLocationWorldOffset | 世界空间偏移 |
| UParticleModuleLocation_Seeded | 带随机种子的位置 |
| UParticleModuleSourceMovement | 源粒子运动方向 |

### Material（材质引用）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleMaterialBase | 材质引用基类 |
| UParticleModuleMeshMaterial | 网格粒子材质数组 |

### Orbit（轨道）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleOrbit | OffsetBase (UDistributionVector) — 轨道偏移基础 |
| UParticleModuleOrbitBase | 轨道基类 |

### Orientation（朝向）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleOrientationAxisLock | LockAxisFlags (EParticleAxisLock) — 锁定轴标志 |
| UParticleModuleOrientationBase | 朝向基类 |

### Parameter（动态参数）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleParameterBase | 参数基类 |
| UParticleModuleParameterDynamic | DynamicParams (TArray&lt;FParticleDynamicParameter&gt;) — 动态参数列表 |
| UParticleModuleParameterDynamic_Seeded | 带随机种子的动态参数 |

### Rotation（旋转）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleRotation | StartRotation (UDistributionFloat) — 初始旋转 |
| UParticleModuleRotationBase | 旋转基类 |
| UParticleModuleRotationOverLifetime | RotationRate (UCurveFloat) — 生命周期旋转率 |
| UParticleModuleRotation_Seeded | 带随机种子的旋转 |

### RotationRate（旋转速率）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleRotationRate | RotationRate (UDistributionFloat) — 旋转速率 |
| UParticleModuleRotationRateBase | 旋转速率基类 |
| UParticleModuleRotationRateMultiplyLife | 生命周期乘法 |
| UParticleModuleRotationRate_Seeded | 带随机种子的旋转速率 |

### Mesh Rotation（网格旋转）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleMeshRotation | 网格粒子旋转 |
| UParticleModuleMeshRotation_Seeded | 带随机种子的网格旋转 |
| UParticleModuleMeshRotationRate | 网格旋转速率 |
| UParticleModuleMeshRotationRateMultiplyLife | 生命周期乘法 |
| UParticleModuleMeshRotationRateOverLife | 生命周期内旋转率 |
| UParticleModuleMeshRotationRate_Seeded | 带随机种子的网格旋转速率 |

### Size（大小）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleSize | StartSize (UDistributionVector) — 初始大小 |
| UParticleModuleSizeBase | 大小基类 |
| UParticleModuleSizeMultiplyLife | 生命周期大小乘法 |
| UParticleModuleSizeScale | 大小缩放 |
| UParticleModuleSizeScaleBySpeed | 速度缩放大小 |
| UParticleModuleSize_Seeded | 带随机种子的大小 |

### SubUV（子纹理动画）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleSubUV | 子纹理动画模块 |
| UParticleModuleSubUVBase | 子纹理基类 |
| UParticleModuleSubUVMovie | SubUV 电影模式 |

### Trail（轨迹）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleTrailBase | 轨迹基类 |
| UParticleModuleTrailSource | 轨迹源设置 |

### TypeData（类型数据）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleTypeDataBase | 类型数据基类 |
| UParticleModuleTypeDataGpu | GPU 类型数据 |
| UParticleModuleTypeDataMesh | 网格类型数据 |
| UParticleModuleTypeDataBeam2 | Beam2 类型数据 |
| UParticleModuleTypeDataRibbon | Ribbon 类型数据 |
| UParticleModuleTypeDataAnimTrail | 动画轨迹类型数据 |

### Spawn（生成）

| Module | 核心字段 |
|--------|----------|
| UParticleModuleSpawn | Rate/BurstList — 生成配置 |
| UParticleModuleSpawnBase | 生成基类 |
| UParticleModuleSpawnPerUnit | 每单位长度生成 |

## 模块总数统计

| 类别 | Module 数量 |
|------|-------------|
| Acceleration | 6 |
| Attractor | 5 |
| Beam | 5 |
| Camera | 2 |
| Collision | 3 |
| Color | 5 |
| Event | 6 |
| Kill | 3 |
| Lifetime | 3 |
| Light | 3 |
| Location | 12 |
| Material | 2 |
| Orbit | 2 |
| Orientation | 2 |
| Parameter | 3 |
| Rotation | 4 |
| RotationRate | 4 |
| MeshRotation | 6 |
| Size | 6 |
| SubUV | 3 |
| Trail | 2 |
| TypeData | 6 |
| Spawn | 3 |
| **总计** | **~80+** |

注：部分 Module 有带 _Seeded 后缀的变体（支持随机种子），实际总数接近 100。

## 源码引用

| 结构 | 源码路径 |
|------|----------|
| UParticleModule | Runtime/Engine/Classes/Particles/ParticleModule.h |
| FParticleRandomSeedInfo | Runtime/Engine/Classes/Particles/ParticleModule.h |
| EModuleType | Runtime/Engine/Classes/Particles/ParticleModule.h |
| UParticleModuleRequired | Runtime/Engine/Classes/Particles/ParticleModuleRequired.h |
| Acceleration 目录 | Runtime/Engine/Classes/Particles/Acceleration/ |
| Attractor 目录 | Runtime/Engine/Classes/Particles/Attractor/ |
| Beam 目录 | Runtime/Engine/Classes/Particles/Beam/ |
| Camera 目录 | Runtime/Engine/Classes/Particles/Camera/ |
| Collision 目录 | Runtime/Engine/Classes/Particles/Collision/ |
| Color 目录 | Runtime/Engine/Classes/Particles/Color/ |
| Event 目录 | Runtime/Engine/Classes/Particles/Event/ |
| Kill 目录 | Runtime/Engine/Classes/Particles/Kill/ |
| Lifetime 目录 | Runtime/Engine/Classes/Particles/Lifetime/ |
| Light 目录 | Runtime/Engine/Classes/Particles/Light/ |
| Location 目录 | Runtime/Engine/Classes/Particles/Location/ |
| Material 目录 | Runtime/Engine/Classes/Particles/Material/ |
| Orbit 目录 | Runtime/Engine/Classes/Particles/Orbit/ |
| Orientation 目录 | Runtime/Engine/Classes/Particles/Orientation/ |
| Parameter 目录 | Runtime/Engine/Classes/Particles/Parameter/ |
| Rotation 目录 | Runtime/Engine/Classes/Particles/Rotation/ |
| RotationRate 目录 | Runtime/Engine/Classes/Particles/RotationRate/ |
| Size 目录 | Runtime/Engine/Classes/Particles/Size/ |
| SubUV 目录 | Runtime/Engine/Classes/Particles/SubUV/ |
| Trail 目录 | Runtime/Engine/Classes/Particles/Trail/ |
| TypeData 目录 | Runtime/Engine/Classes/Particles/TypeData/ |
| Spawn 目录 | Runtime/Engine/Classes/Particles/Modules/ |

## 版本差异

### UE4 → UE5 变化

| 变化点 | UE4 | UE5 |
|--------|-----|-----|
| GPU 碰撞模块 | 基础支持 | 增强（ParticleModuleCollisionGPU） |
| 大世界坐标支持 | 无 | bSupportLargeWorldCoordinates（RequiredModule） |
| UV 翻转模式 | 基础 | EParticleUVFlipMode 扩展 |
| 模块 Deprecated | 无 | 部分 Cascade 模块标记 Deprecated |

### 模块演进趋势

- GPU 模块在 UE5 中更受重视
- Cascade 模块标记 Deprecated 但运行时兼容
- Niagara 使用完全不同的模块系统（不在 Cascade 范围内）

---

*文档版本: v1.2 | 最后更新: 2026-06-01 | 源码验证: UE5 源码 (ParticleModule.h)*
