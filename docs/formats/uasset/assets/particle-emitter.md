# UParticleEmitter + UParticleLODLevel — Cascade 粒子发射器与 LOD 层次

## 概述

UParticleEmitter 是 Cascade 粒子发射器的核心单元，继承自 UObject。每个发射器定义独立的粒子生成、运动、渲染行为。一个发射器可包含多个 UParticleLODLevel，每个 LOD 层级包含独立的 Module 配置。

UParticleLODLevel 是单个发射器的单个 LOD 层级，包含 RequiredModule（必需）、TypeDataModule（类型定义）、SpawnModule（生成）、Modules 数组（行为模块）。

**层次关系：**
```
UParticleEmitter
├── LODLevels[0] (UParticleLODLevel, 最高精度)
│   ├── RequiredModule (UParticleModuleRequired, instanced)
│   ├── TypeDataModule (UParticleModuleTypeDataBase, export)
│   ├── SpawnModule (UParticleModuleSpawn, export)
│   ├── EventGenerator (UParticleModuleEventGenerator, export, optional)
│   └── Modules[] (UParticleModule[], instanced)
├── LODLevels[1] (UParticleLODLevel, 中等精度)
│   └── ...
└── LODLevels[N] (UParticleLODLevel, 最低精度)
```

**bCookedOut 标记：** Cooker 在烘焙时会剔除不必要的发射器（如编辑器-only 效果），但保留其在 Emitters 数组中的位置和索引，通过 `bCookedOut=true` 标记。运行时跳过这些发射器的初始化和 Tick，但其他系统（蓝图引用、材质覆盖）仍依赖固定索引。

## UParticleEmitter 字段表

### 核心字段

| 字段名 | 类型 | 默认值 | 用途 | 源码行 |
|--------|------|--------|------|--------|
| EmitterName | FName | NAME_None | 发射器名称 | ParticleEmitter.h:106 |
| SubUVDataOffset | int32 (transient) | - | SubUV 数据偏移，运行时计算 | ParticleEmitter.h:109 |
| EmitterRenderMode | EEmitterRenderMode | Normal | 渲染模式（Normal/Point/Cross/LightsOnly/None） | ParticleEmitter.h:119 |
| SignificanceLevel | EParticleSignificanceLevel | - | 显著性等级，决定发射器何时活跃 | ParticleEmitter.h:123 |
| LockAxisFlags | EParticleAxisLock | - | 轴锁定标志 | ParticleEmitter.h:125 |
| bUseLegacySpawningBehavior | uint8:1 | false | 使用旧版粒子生成行为 | ParticleEmitter.h:129 |
| bRequiresLoopNotification | uint8:1 | - | 需要循环通知（PostLoad/CacheEmitterModuleInfo 计算） | ParticleEmitter.h:134 |
| bAxisLockEnabled | uint8:1 | - | 轴锁定启用（PostLoad 计算） | ParticleEmitter.h:135 |
| bMeshRotationActive | uint8:1 | - | 网格旋转活跃（PostLoad 计算） | ParticleEmitter.h:136 |
| ConvertedModules | uint8:1 | - | 模块已转换标记 | ParticleEmitter.h:139 |
| bIsSoloing | uint8:1 (transient) | false | 编辑器独奏模式标记 | ParticleEmitter.h:143 |
| bCookedOut | uint8:1 | false | Cook 后剔除标记 — 详见下文 | ParticleEmitter.h:151 |
| bDisabledLODsKeepEmitterAlive | uint8:1 | false | 禁用 LOD 时是否保持发射器活跃 | ParticleEmitter.h:155 |
| bDisableWhenInsignficant | uint8:1 | false | 不活跃时立即禁用 Tick 和渲染 | ParticleEmitter.h:159 |
| bRemoveHMDRollInVR | uint8:1 | false | VR 中移除 HMD Roll | ParticleEmitter.h:162 |
| LODLevels | TArray&lt;TObjectPtr&lt;UParticleLODLevel&gt;&gt; (instanced) | [] | LOD 层级数组 | ParticleEmitter.h:181 |
| PeakActiveParticles | int32 | - | 峰值活跃粒子数（计算值） | ParticleEmitter.h:184 |
| InitialAllocationCount | int32 | - | 初始分配计数（覆盖峰值计算，&gt;0 时生效） | ParticleEmitter.h:194 |
| QualityLevelSpawnRateScale | float | - | 品质等级生成率缩放因子 | ParticleEmitter.h:197 |
| DetailModeBitmask | uint32 (bitmask: EParticleDetailMode) | - | 细节模式位掩码（Low/Medium/High/Epic） | ParticleEmitter.h:201 |

### 运行时计算字段（磁盘上不序列化，非 UPROPERTY）

| 字段名 | 类型 | 用途 |
|--------|------|------|
| ModuleOffsetMap | TMap&lt;UParticleModule*, uint32&gt; | 模块指针到粒子数据偏移的映射 |
| ModuleInstanceOffsetMap | TMap&lt;UParticleModule*, uint32&gt; | 模块指针到实例数据偏移的映射 |
| ModuleRandomSeedInstanceOffsetMap | TMap&lt;UParticleModule*, uint32&gt; | 模块指针到随机种子实例偏移的映射 |
| MeshMaterials | TArray&lt;UMaterialInterface*&gt; | 从 MeshMaterial 模块收集的资源 |
| DynamicParameterDataOffset | int32 | 动态参数数据偏移 |
| LightDataOffset | int32 | 光照数据偏移 |
| LightVolumetricScatteringIntensity | float | 光照体积散射强度 |
| CameraPayloadOffset | int32 | 相机载荷偏移 |
| ParticleSize | int32 | 粒子数据大小 |
| ReqInstanceBytes | int32 | 所需实例字节数 |
| PivotOffset | FVector2D | 枢轴偏移 |
| TypeDataOffset | int32 | 类型数据偏移 |
| TypeDataInstanceOffset | int32 | 类型数据实例偏移 |
| MinFacingCameraBlendDistance | float | 最小面向相机混合距离 |
| MaxFacingCameraBlendDistance | float | 最大面向相机混合距离 |
| ModulesNeedingInstanceData | TArray&lt;UParticleModule*&gt; | 需要实例数据的模块 |
| ModulesNeedingRandomSeedInstanceData | TArray&lt;UParticleModule*&gt; | 需要随机种子实例数据的模块 |
| SubUVAnimation | USubUVAnimation* | SubUV 动画资源 |

### WITH_EDITORONLY_DATA 字段

| 字段名 | 类型 | 用途 | 源码行 |
|--------|------|------|--------|
| bCollapsed | uint8:1 | Cascade 编辑器中折叠显示 | ParticleEmitter.h:168 |
| EmitterEditorColor | FColor | 曲线编辑器和调试渲染颜色 | ParticleEmitter.h:174 |
| DetailModeDisplay | FString (Transient) | 当前细节模式显示字符串 | ParticleEmitter.h:205 |

### 枚举类型定义

**EEmitterRenderMode：**
| 值 | 说明 |
|----|------|
| ERM_Normal | 正常渲染（Sprite/Mesh） |
| ERM_Point | 2x2 像素块，无缩放 |
| ERM_Cross | 十字线，按粒子大小缩放 |
| ERM_LightsOnly | 仅渲染光照 |
| ERM_None | 不渲染 |

**EParticleBurstMethod：**
| 值 | 说明 |
|----|------|
| EPBM_Instant | 立即爆发 |
| EPBM_Interpolated | 插值爆发 |

**EParticleSubUVInterpMethod：**
| 值 | 说明 |
|----|------|
| PSUVIM_None | 不使用 SubUV |
| PSUVIM_Linear | 线性顺序过渡，无混合 |
| PSUVIM_Linear_Blend | 线性顺序过渡，有混合 |
| PSUVIM_Random | 随机选择，无混合 |
| PSUVIM_Random_Blend | 随机选择，有混合 |

**FParticleBurst 结构：**
| 字段名 | 类型 | 用途 |
|--------|------|------|
| Count | int32 | 爆发粒子数量 |
| CountLow | int32 | 爆发粒子数量下限（&gt;=0 时启用范围 [CountLow..Count]） |
| Time | float | 爆发时间（0..1：发射器生命周期比例） |

## UParticleLODLevel 字段表

### 持久化字段（磁盘序列化）

| 字段名 | 类型 | 默认值 | 用途 | 源码行 |
|--------|------|--------|------|--------|
| Level | int32 | - | LOD 层级索引（0=最高精度） | ParticleLODLevel.h:27 |
| bEnabled | uint32:1 | true | 是否启用此 LOD 层级 | ParticleLODLevel.h:31 |
| RequiredModule | TObjectPtr&lt;UParticleModuleRequired&gt; (instanced) | - | 必需模块，每个 LODLevel 必须有 | ParticleLODLevel.h:35 |
| Modules | TArray&lt;TObjectPtr&lt;UParticleModule&gt;&gt; (instanced) | [] | 模块数组，包含所有行为模块 | ParticleLODLevel.h:39 |
| TypeDataModule | TObjectPtr&lt;UParticleModuleTypeDataBase&gt; (export) | - | 类型数据模块 | ParticleLODLevel.h:43 |
| SpawnModule | TObjectPtr&lt;UParticleModuleSpawn&gt; (export) | - | 生成模块，所有发射器必需 | ParticleLODLevel.h:47 |
| EventGenerator | TObjectPtr&lt;UParticleModuleEventGenerator&gt; (export) | - | 事件生成模块（可选） | ParticleLODLevel.h:51 |
| ConvertedModules | uint32:1 | - | 模块已转换标记 | ParticleLODLevel.h:76 |
| PeakActiveParticles | int32 | - | 此 LOD 的峰值活跃粒子数 | ParticleLODLevel.h:79 |

### Transient 数组（PostLoad 时从 Modules 重建）

以下数组标记为 `transient, duplicatetransient`，在磁盘上不序列化，PostLoad 时从 Modules 数组重建：

| 字段名 | 类型 | 用途 | 源码行 |
|--------|------|------|--------|
| SpawningModules | TArray&lt;TObjectPtr&lt;UParticleModuleSpawnBase&gt;&gt; | 决定生成多少粒子 | ParticleLODLevel.h:55 |
| SpawnModules | TArray&lt;TObjectPtr&lt;UParticleModule&gt;&gt; | 粒子生成时调用 | ParticleLODLevel.h:59 |
| UpdateModules | TArray&lt;TObjectPtr&lt;UParticleModule&gt;&gt; | 粒子更新时调用 | ParticleLODLevel.h:63 |
| OrbitModules | TArray&lt;TObjectPtr&lt;UParticleModuleOrbit&gt;&gt; | 轨道偏移模块 | ParticleLODLevel.h:69 |
| EventReceiverModules | TArray&lt;TObjectPtr&lt;UParticleModuleEventReceiverBase&gt;&gt; | 事件接收模块 | ParticleLODLevel.h:73 |

**重建逻辑（PostLoad / UpdateModuleLists）：**
```cpp
// 遍历 Modules 数组，根据模块的 bSpawnModule/bUpdateModule 等标志分类
for (UParticleModule* Module : Modules) {
    if (Module->bSpawnModule) SpawnModules.Add(Module);
    if (Module->bUpdateModule) UpdateModules.Add(Module);
    // OrbitModules/EventReceiverModules 检查模块类型
}
```

## bCookedOut 行为说明

### Cooked vs Uncooked 对比

| 特性 | Uncooked 资产 | Cooked 资产 |
|------|---------------|-------------|
| bCookedOut 值 | 全部 false | 被剔除发射器为 true |
| Emitters 数组长度 | 原始长度 | 不变（保留索引） |
| 有效发射器数量 | 全部活跃 | 仅 bCookedOut=false 者活跃 |
| LOD 索引 | 正常 | 不受影响 |

### 剔除原因

Cooker 可能剔除发射器的原因：
- 平台特定效果（某些平台不需要）
- 编辑器-only 效果（调试/预览用途）
- 性能优化（低显著性效果在目标平台跳过）

### 运行时处理

```cpp
// 初始化时检查
if (Emitter->bCookedOut) {
    // 跳过发射器初始化
    // 不创建粒子实例
    // 不参与 Tick 和渲染
}

// 索引保持不变的原因：
// - 蓝图引用可能使用 Emitter 索引
// - NamedMaterialOverrides 通过索引关联
// - External 参数可能引用特定发射器
```

### 验证方法

对比同一粒子系统的 Uncooked 和 Cooked 版本：
1. 观察 Emitters 数组长度是否相同
2. 检查每个发射器的 bCookedOut 标记
3. 确认被剔除发射器的 LODLevels/Modules 结构是否仍完整（通常被简化）

**交叉引用：** 通用 Cooked vs Uncooked 机制见 [cooked/cooked-vs-uncooked.md](../cooked/cooked-vs-uncooked.md)

## Distribution 对象简要说明

粒子模块广泛使用 Distribution 对象实现参数变化：

| Distribution 类型 | 基类 | 用途 |
|-------------------|------|------|
| UDistributionFloat | UDistribution | 浮点数分布（常量/曲线/参数） |
| UDistributionVector | UDistribution | 向量分布（常量/曲线/参数） |

**使用方式：**
- Module 通过 TObjectPtr&lt;UDistributionFloat/Vector&gt; 引用 Distribution 对象
- Distribution 作为独立的 UObject 子对象序列化（Export 表条目）
- 运行时通过 Distribution.GetValue() 获取当前值

**典型使用场景：**
- ParticleModuleLifetime.Lifetime → UDistributionFloat（生命周期）
- ParticleModuleLocation.PositionOffset → UDistributionVector（位置偏移）
- ParticleModuleColor.Color → UDistributionVector（颜色）
- ParticleModuleSize.StartSize → UDistributionVector（初始大小）

Distribution 详细序列化结构在 serialization 章节描述，不在此展开。

## 源码引用

| 结构 | 源码路径 |
|------|----------|
| UParticleEmitter | Runtime/Engine/Classes/Particles/ParticleEmitter.h |
| UParticleLODLevel | Runtime/Engine/Classes/Particles/ParticleLODLevel.h |
| FParticleBurst | Runtime/Engine/Classes/Particles/ParticleEmitter.h |
| EParticleBurstMethod | Runtime/Engine/Classes/Particles/ParticleEmitter.h |
| EParticleSubUVInterpMethod | Runtime/Engine/Classes/Particles/ParticleEmitter.h |
| EEmitterRenderMode | Runtime/Engine/Classes/Particles/ParticleEmitter.h |
| Serialize/PostLoad | Runtime/Engine/Private/Particles/ParticleEmitter.cpp |
| UpdateModuleLists | Runtime/Engine/Private/Particles/ParticleLODLevel.cpp |

## 版本差异

### UE4 → UE5 变化

| 变化点 | UE4 | UE5 |
|--------|-----|-----|
| EParticleSignificanceLevel | 基础枚举 | 更细粒度值 |
| bDisableWhenInsignficant | 无 | 新增，立即禁用不活跃发射器 |
| bRemoveHMDRollInVR | 无 | 新增，VR 优化 |
| DetailModeBitmask | 无枚举关联 | 关联 EParticleDetailMode 枚举 (bitmask meta) |

### 序列化兼容性

- UParticleEmitter 和 UParticleLODLevel 的序列化格式无破坏性变更
- 现有资产可直接加载
- ConvertedModules 标记处理旧版模块转换

---

*文档版本: v1.2 | 最后更新: 2026-06-01 | 源码验证: UE5 源码 (ParticleEmitter.h / ParticleLODLevel.h)*
