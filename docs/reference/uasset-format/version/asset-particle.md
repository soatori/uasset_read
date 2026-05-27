# Cascade 粒子系统版本差异

## 概述

本文档追踪 Cascade 粒子系统（UParticleSystem、UParticleEmitter、UParticleLODLevel、UParticleModule）在 UE4 → UE5 版本演进中的结构变更。

**覆盖范围：**
- Cascade 粒子系统相关类的序列化格式变更
- 版本宏和条件编译影响
- UE4 → UE5 架构变化

**不包含：**
- Niagara 系统版本历史（独立架构，留给 v1.2）

## UE4 版本变更

### 序列化版本宏

以下版本宏影响粒子系统序列化：

| 版本宏 | 说明 |
|--------|------|
| VER_UE4_PARTICLE_SIGNIFICANCE | 引入粒子显著性系统 |
| VER_UE4_SERIALIZE_PARTICLE_SYSTEM | 粒子系统序列化格式调整 |
| VER_UE4_PARTICLE_MODULE_LOD_VALIDITY | Module LODValidity 字段变更 |

### 关键变更点

**VER_UE4_PARTICLE_SIGNIFICANCE：**
- 引入 EParticleSignificanceLevel 枚举
- 发射器新增 SignificanceLevel 字段
- 系统新增 MaxSignificanceLevel、InsignificantReaction、InsignificanceDelay 字段
- 影响：发射器可根据显著性决定是否活跃

**VER_UE4_SERIALIZE_PARTICLE_SYSTEM：**
- 粒子系统序列化格式标准化
- 新增 NamedMaterialSlots 材质槽系统
- 影响：材质引用方式变化

## UE5 版本变更

### 新增字段

| 字段 | 类 | 说明 |
|------|-----|------|
| MinTimeBetweenTicks | UParticleSystem | Tick 最小间隔毫秒（性能控制） |
| PoolPrimeSize | UFXSystemAsset | 组件池预分配数量 |
| bDisableWhenInsignficant | UParticleEmitter | 不活跃时立即禁用 |
| bRemoveHMDRollInVR | UParticleEmitter | VR 中移除 HMD Roll |
| bSupportLargeWorldCoordinates | UParticleModuleRequired | 支持大世界坐标（GPU） |
| UVFlippingMode | UParticleModuleRequired | UV 翻转模式扩展 |

### 枚举扩展

**EParticleUVFlipMode（新增）：**
| 值 | 说明 |
|----|------|
| None | 不翻转 |
| FlipUV | 翻转 UV |
| FlipUOnly | 仅翻转 U |
| FlipVOnly | 仅翻转 V |
| RandomFlipUV | 随机翻转 UV |
| RandomFlipUOnly | 随机翻转 U |
| RandomFlipVOnly | 随机翻转 V |
| RandomFlipUVIndependent | U/V 独立随机翻转 |

**EEmitterNormalsMode（扩展）：**
| 值 | 说明 |
|----|------|
| ENM_CameraFacing | 相机朝向（默认） |
| ENM_Spherical | 球形法线 |
| ENM_Cylindrical | 圆柱形法线 |

### Deprecated 标记

以下在 UE5 中标记为 Deprecated：
- Cascade 编辑器部分功能
- 部分旧版 Module（仍运行时兼容）
- 旧版 Spawn 行为（bUseLegacySpawningBehavior）

## 版本对比表

| 特性 | UE4.x | UE5.x | 说明 |
|------|-------|-------|------|
| 默认粒子系统 | Cascade | Niagara | Cascade 仍可用但非默认 |
| 显著性系统 | 基础 | 增强 | 更细粒度控制 |
| GPU 粒子 | 有限支持 | 增强 | 更多 GPU 模块 |
| 编辑器支持 | 完整 | 维护模式 | Cascade 编辑器功能减少 |
| 序列化格式 | 兼容 | 兼容 | 无破坏性变更 |
| 大世界坐标 | 无 | 支持 | GPU 粒子支持 LWC |
| HMD Roll 处理 | 无 | 可选移除 | VR 优化 |
| 性能控制 | 基础 | 增强 | MinTimeBetweenTicks 等 |

## Cascade vs Niagara 架构区分

### 结构对比

| Cascade | Niagara | 说明 |
|---------|---------|------|
| UParticleSystem | UNiagaraSystem | 顶层容器 |
| UParticleEmitter | UNiagaraEmitter | 发射器 |
| UParticleLODLevel | — | Niagara 无 LODLevel 概念 |
| UParticleModule | UNiagaraModule | 行为模块 |
| Distribution | Niagara Parameter | 参数化方式不同 |
| bCookedOut | — | Niagara 使用不同剔除机制 |

### 关键差异

| 方面 | Cascade | Niagara |
|------|---------|---------|
| 模块组合 | 固定 Module 数组 | 脚本化 ModuleStack |
| 参数化 | Distribution 对象 | Niagara Parameter +
| GPU 支持 | 部分 Module | 全 GPU 模拟可选 |
| 编辑器 | Cascade 编辑器 | Niagara 编辑器 |
| 版本状态 | Deprecated | Active |

### 迁移说明

UE 提供 Cascade → Niagara 迁移工具，但：
- 迁移不完全自动
- 部分 Cascade Module 无 Niagara 对应
- 迁移后需手动调整参数

v1.1 仅覆盖 Cascade。Niagara 格式文档在 v1.2 阶段规划。

## 序列化兼容性

### 向后兼容

- UE5 可加载 UE4 创建的 Cascade 资产
- 无破坏性序列化变更
- 新字段有默认值，旧资产自动填充

### 向前兼容

- UE4 无法加载 UE5 特有字段
- 但核心结构兼容
- 新字段在 UE4 中忽略

## 源码引用

| 文件 | 说明 |
|------|------|
| Runtime/Engine/Classes/Particles/ParticleSystem.h | 版本宏条件编译 |
| Runtime/Engine/Classes/Particles/ParticleEmitter.h | SignificanceLevel 相关字段 |
| Runtime/Engine/Classes/Particles/ParticleModuleRequired.h | UVFlippingMode/LWC 字段 |
| Runtime/Engine/Private/Particles/ParticleSystem.cpp | Serialize 版本处理 |
| docs/version/ue4-evolution.md | UE4 版本演进主文档 |
| docs/version/ue5-evolution.md | UE5 版本演进主文档 |

---

*文档版本: v1.1 | 最后更新: 2026-04-30*