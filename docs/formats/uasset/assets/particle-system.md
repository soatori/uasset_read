# UParticleSystem — Cascade 粒子系统顶层结构

## 概述

UParticleSystem 是 Cascade 粒子系统的顶层容器类，继承自 UFXSystemAsset（最终继承 UObject）。一个粒子系统效果可包含任意数量的 UParticleEmitter，每个发射器定义独立的粒子行为（生成、运动、渲染等）。

**层次关系：**
```
UParticleSystem (Export[0])
├── Emitters[0] (UParticleEmitter, Export[1])
│   ├── LODLevels[0] (UParticleLODLevel, Export[2])
│   │   ├── RequiredModule (UParticleModuleRequired, Export[3])
│   │   ├── TypeDataModule (UParticleModuleTypeDataBase, Export[4])
│   │   ├── SpawnModule (UParticleModuleSpawn, Export[5])
│   │   └── Modules[] (UParticleModule, Export[6..N])
│   └── LODLevels[1] ...
├── Emitters[1] (UParticleEmitter, Export[N+1])
│   └── ...
└── NamedMaterialSlots[] (FNamedEmitterMaterial, inline struct)
```

**文件内对象布局：**
- Export[0]: UParticleSystem 主对象
- Export[1..N]: UParticleEmitter 及其子对象（UParticleLODLevel、UParticleModule 等）
- 所有子对象通过 `instanced` 或 `export` UPROPERTY 标记序列化为内嵌导出

**Cascade vs Niagara：**
| 系统 | 版本 | 结构 | 状态 |
|------|------|------|------|
| Cascade | UE3 引入 | UParticleSystem → UParticleEmitter → UParticleLODLevel → UParticleModule | Deprecated但仍可用 |
| Niagara | UE4 引入，UE5 推荐 | UNiagaraSystem → UNiagaraEmitter → UNiagaraScript → UNiagaraModule | Active |

v1.1 仅覆盖 Cascade 格式。Niagara 为独立架构，不在本文档范围内。

**材质引用机制：**
UParticleSystem 通过 `NamedMaterialSlots` 提供命名材质槽，发射器可通过 `NamedMaterialOverrides` 引用这些槽。材质引用指向 UMaterialInterface，详见 [assets/material.md](material.md)。

## 字段表

### 核心字段

| 字段名 | 类型 | 默认值 | 用途 |
|--------|------|--------|------|
| UpdateTime_FPS | float | - | FixedTime 模式下的更新帧率 |
| UpdateTime_Delta | float | - | (internal) 内部计算的时间步长 |
| WarmupTime | float | - | 激活时预热时间（模拟运行，注意性能开销） |
| WarmupTickRate | float | - | 预热期间每帧的时间步长，0=使用默认值 |
| Emitters | TArray&lt;TObjectPtr&lt;UParticleEmitter&gt;&gt; | [] | 发射器数组，instanced 子对象 |
| LODDistanceCheckTime | float | - | LOD 距离检查间隔（秒） |
| LODDistances | TArray&lt;float&gt; | [] | 各 LOD 层级距离阈值数组 |
| LODSettings | TArray&lt;FParticleSystemLOD&gt; | [] | 各 LOD 层级设置（当前为空结构） |
| FixedRelativeBoundingBox | FBox | - | 固定相对包围盒 |
| SecondsBeforeInactive | float | - | 未渲染后变不活跃的超时秒数 |
| Delay | float | - | 激活延迟时间 |
| DelayLow | float | - | 延迟范围下限（配合 bUseDelayRange） |
| MacroUVRadius | float | - | ParticleMacroUV 材质节点的世界空间半径 |
| MacroUVPosition | FVector | - | ParticleMacroUV 材质节点的中心位置 |
| SystemUpdateMode | TEnumAsByte&lt;EParticleSystemUpdateMode&gt; | RealTime | 更新模式（RealTime/FixedTime） |
| LODMethod | TEnumAsByte&lt;ParticleSystemLODMethod&gt; | Automatic | LOD 判定方法（Automatic/DirectSet/ActivateAutomatic） |
| InsignificantReaction | EParticleSystemInsignificanceReaction | - | 全部发射器不活跃时的系统反应 |
| OcclusionBoundsMethod | TEnumAsByte&lt;EParticleSystemOcclusionBoundsMethod&gt; | ParticleBounds | 遮挡判定方法（None/ParticleBounds/CustomBounds） |
| MaxSignificanceLevel | EParticleSignificanceLevel | - | 最大显著性等级，限制发射器活跃判定 |
| MinTimeBetweenTicks | uint32 | - | Tick 最小间隔毫秒（33=30FPS, 16=60FPS, 8=120FPS） |
| InsignificanceDelay | float | - | 全部不活跃后触发反应的延迟 |
| CustomOcclusionBounds | FBox | - | 自定义遮挡包围盒（配合 OcclusionBoundsMethod） |

### 布尔标志字段

| 字段名 | 类型 | 默认值 | 用途 |
|--------|------|--------|------|
| bOrientZAxisTowardCamera | uint8:1 | false | Z轴朝向相机 |
| bUseFixedRelativeBoundingBox | uint8:1 | false | 使用固定包围盒而非每帧计算 |
| bHasPhysics | uint8:1 | false | (transient) 加载时标记是否使用物理 |
| bUseDelayRange | uint8:1 | false | 使用 [DelayLow..Delay] 范围随机延迟 |
| bAllowManagedTicking | uint8:1 | - | 允许托管 Tick（性能优化） |
| bAutoDeactivate | uint8:1 | - | 全部发射器不再生成时自动停用 |
| bRegenerateLODDuplicate | uint8:1 | - | 自动生成 LOD 时为精确副本 |
| bShouldResetPeakCounts | uint8:1 | - | 编辑器请求重置峰值计数 |
| bUseRealtimeThumbnail | uint8:1 | - | 使用实时缩略图渲染 |
| ThumbnailImageOutOfDate | uint8:1 | - | 缩略图已过期标记 |
| bIsElligibleForAsyncTick | uint8:1 | - | 是否可异步 Tick（计算值，private） |
| bIsElligibleForAsyncTickComputed | uint8:1 | - | bIsElligibleForAsyncTick 是否已计算（private） |
| bAnyEmitterLoopsForever | uint8:1 | - | 是否有发射器无限循环（private） |
| bIsImmortal | uint8:1 | - | 是否有发射器永不消亡（private） |
| bWillBecomeZombie | uint8:1 | - | 是否有发射器会变成僵尸（private） |
| bShouldManageSignificance | uint8:1 | - | 是否管理显著性（private） |

### 材质引用字段

| 字段名 | 类型 | 默认值 | 用途 |
|--------|------|--------|------|
| NamedMaterialSlots | TArray&lt;FNamedEmitterMaterial&gt; | [] | 命名材质槽数组 |

**FNamedEmitterMaterial 结构：**
| 字段名 | 类型 | 默认值 | 用途 |
|--------|------|--------|------|
| Name | FName | NAME_None | 材质槽名称 |
| Material | TObjectPtr&lt;UMaterialInterface&gt; | nullptr | 材质引用 → 见 [assets/material.md](material.md) |

### UFXSystemAsset 基类字段

| 字段名 | 类型 | 默认值 | 用途 |
|--------|------|--------|------|
| MaxPoolSize | uint32 | - | 组件池最大容量 |
| PoolPrimeSize | uint32 | 0 | 组件池初始预分配数量 |

### WITH_EDITORONLY_DATA 字段

以下字段仅在编辑器构建中存在，磁盘序列化时随构建配置变化：

| 字段名 | 类型 | 用途 |
|--------|------|------|
| ThumbnailAngle | FRotator | 缩略图渲染角度 |
| ThumbnailDistance | float | 缩略图渲染距离 |
| ThumbnailWarmup | float | 缩略图预热时间 |
| EditorLODSetting | int32 | 编辑器 LOD 设置（0-100） |
| FloorMesh | FString | Cascade 编辑器地板网格路径 |
| FloorPosition | FVector | 地板位置 |
| FloorRotation | FRotator | 地板旋转 |
| FloorScale | float | 地板缩放 |
| FloorScale3D | FVector | 地板 3D 缩放 |
| BackgroundColor | FColor | Cascade 编辑器背景色 |
| bShouldResetPeakCounts | uint8:1 | 编辑器请求重置峰值计数 |
| bUseRealtimeThumbnail | uint8:1 | 使用实时缩略图渲染 |
| ThumbnailImageOutOfDate | uint8:1 | 缩略图已过期标记 |
| ThumbnailImage | TObjectPtr&lt;UTexture2D&gt; | 缩略图纹理 |
| CurveEdSetup | TObjectPtr&lt;UInterpCurveEdSetup&gt; | 曲线编辑器配置（export） |

### Transient 字段（磁盘上不序列化）

| 字段名 | 类型 | 用途 |
|--------|------|------|
| PreviewComponent | TObjectPtr&lt;UParticleSystemComponent&gt; | 编辑器预览组件 |
| SoloTracking | TArray&lt;FLODSoloTrack&gt; | 独奏模式追踪数组 |
| bIsElligibleForAsyncTick | uint8:1 | 是否可异步 Tick（计算值，private） |
| bIsElligibleForAsyncTickComputed | uint8:1 | bIsElligibleForAsyncTick 是否已计算（private） |

### 私有字段（源码中存在但文档未覆盖）

| 字段名 | 类型 | 用途 |
|--------|------|------|
| bAnyEmitterLoopsForever | uint8:1 | 是否有发射器无限循环 |
| bIsImmortal | uint8:1 | 是否有发射器永不消亡（无限循环+不定持续时间） |
| bWillBecomeZombie | uint8:1 | 是否有发射器会变成僵尸（不朽但停止生成） |
| HighestSignificance | EParticleSignificanceLevel | 最高显著性（被 MaxSignificanceLevel 限制） |
| LowestSignificance | EParticleSignificanceLevel | 最低显著性（被 MaxSignificanceLevel 限制） |
| bShouldManageSignificance | uint8:1 | 是否管理显著性 |

### 枚举类型定义

**EParticleSystemUpdateMode：**
| 值 | 说明 |
|----|------|
| EPSUM_RealTime | 使用传入的 DeltaTime 更新 |
| EPSUM_FixedTime | 使用固定帧率（UpdateTime_FPS）更新 |

**ParticleSystemLODMethod：**
| 值 | 说明 |
|----|------|
| PARTICLESYSTEMLODMETHOD_Automatic | 自动 LOD，按 LODDistanceCheckTime 间隔检查 |
| PARTICLESYSTEMLODMETHOD_DirectSet | 由游戏代码直接设置 LOD |
| PARTICLESYSTEMLODMETHOD_ActivateAutomatic | 激活时确定 LOD，之后不变 |

**EParticleSystemOcclusionBoundsMethod：**
| 值 | 说明 |
|----|------|
| EPSOBM_None | 不进行遮挡判定 |
| EPSOBM_ParticleBounds | 使用粒子系统组件包围盒 |
| EPSOBM_CustomBounds | 使用 CustomOcclusionBounds |

## 层次关系

### 导出对象结构

UParticleSystem 采用嵌套 instanced 子对象序列化：

```
Package Export Map:
├── Export[0]: UParticleSystem
│   ├── Emitters[0] → Export[1] (UParticleEmitter)
│   │   ├── LODLevels[0] → Export[2] (UParticleLODLevel)
│   │   │   ├── RequiredModule → Export[3] (UParticleModuleRequired, instanced)
│   │   │   ├── TypeDataModule → Export[4] (UParticleModuleTypeDataBase, export)
│   │   │   ├── SpawnModule → Export[5] (UParticleModuleSpawn, export)
│   │   │   ├── EventGenerator → Export[6] (UParticleModuleEventGenerator, export, optional)
│   │   │   └── Modules[0] → Export[7] (UParticleModule, instanced)
│   │   │       └── Modules[1] → Export[8] ...
│   │   └── LODLevels[1] → Export[N] ...
│   ├── Emitters[1] → Export[M] (UParticleEmitter)
│   │   └── ...
│   └── NamedMaterialSlots (inline struct array, 无独立 Export)
```

### 子对象引用方式

| 字段 | 引用方式 | 说明 |
|------|----------|------|
| Emitters | instanced | 内嵌子对象，作为 Export 序列化 |
| LODLevels | instanced | 内嵌子对象 |
| RequiredModule | instanced | 每个 LODLevel 必需 |
| TypeDataModule | export | 可被其他对象引用 |
| SpawnModule | export | 可被其他对象引用 |
| Modules | instanced | 内嵌子对象数组 |
| NamedMaterialSlots.Material | TObjectPtr | 外部材质引用（Import 表或 Export） |

## 源码引用

| 结构 | 源码路径 |
|------|----------|
| UParticleSystem | Runtime/Engine/Classes/Particles/ParticleSystem.h |
| UFXSystemAsset | Runtime/Engine/Classes/Particles/ParticleSystem.h (同一文件) |
| FNamedEmitterMaterial | Runtime/Engine/Classes/Particles/ParticleSystem.h |
| FParticleSystemLOD | Runtime/Engine/Classes/Particles/ParticleSystem.h |
| FLODSoloTrack | Runtime/Engine/Classes/Particles/ParticleSystem.h |
| Serialize/PostLoad | Runtime/Engine/Private/Particles/ParticleSystem.cpp |

## 版本差异

### UE4 → UE5 变化

| 变化点 | UE4 | UE5 |
|--------|-----|-----|
| 默认粒子系统 | Cascade | Niagara（Cascade Deprecated） |
| 编辑器支持 | Cascade 完整支持 | Cascade 维护模式，新建推荐 Niagara |
| EParticleSignificanceLevel | 基础枚举 | 更细粒度控制 |
| MinTimeBetweenTicks | 无 | 新增，性能控制 |
| PoolPrimeSize | 无 | 新增，预分配优化 |
| bSupportLargeWorldCoordinates | 无 | 新增于 RequiredModule |
| bIsElligibleForAsyncTick | 无 | 新增，异步 Tick 优化 |
| bAutoDeactivate | 无 | 新增，自动停用优化 |
| bAllowManagedTicking | 无 | 新增，托管 Tick 优化 |

### 版本兼容性

- Cascade 粒子系统的序列化格式在 UE4 → UE5 间无破坏性变更
- 现有 Cascade 资产可直接加载和运行
- 编辑器新建 Cascade 资产的能力保留，但默认推荐 Niagara

### Niagara 边界说明

Niagara 系统与 Cascade 完全独立：
- **架构独立：** UNiagaraSystem / UNiagaraEmitter / UNiagaraScript / UNiagaraModule
- **序列化独立：** Niagara 使用不同的类层次和序列化逻辑
- **编辑器独立：** Niagara 编辑器界面和模块系统与 Cascade 不同
- **互不引用：** Cascade 和 Niagara 资产之间无交叉引用

Niagara 格式文档将在 v1.2 阶段覆盖。

---

*文档版本: v1.2 | 最后更新: 2026-06-01*
*源码对照: UE5.x Engine/Source/Runtime/Engine/Classes/Particles/ParticleSystem.h*
