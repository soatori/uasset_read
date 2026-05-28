# Unreal Engine 真实资产测试索引

> 基于 `E:\Develop\lib\UnrealEngine\Samples` 目录中的真实 .uasset 文件整理
> 命名规范参考: [Epic 官方文档](https://dev.epicgames.com/documentation/unreal-engine/recommended-asset-naming-conventions-in-unreal-engine-projects?application_version=5.5)
> 扩展类型来源: Unreal Engine 5.5 引擎源码及插件

---

## 一、核心资产类型 (Core Asset Types)

### 1. Static Mesh (静态网格体)

| 字段 | 内容 |
|------|------|
| **前缀** | `SM_` |
| **引擎类** | `UStaticMesh` |
| **内部类型字符串** | `StaticMesh` |
| **描述** | 非变形3D网格，场景中最常见资产 |

**测试文件示例:**

| 文件路径 (相对 Samples/) | 大小 | 来源项目 | 适合测试 |
|--------------------------|------|----------|----------|
| `StarterContent/Content/StarterContent/Props/SM_Bush.uasset` | ~66 KB | StarterContent | 简单低面数模型 |
| `StarterContent/Content/StarterContent/Props/SM_Statue.uasset` | ~192 KB | StarterContent | 复杂模型 |
| `StarterContent/Content/StarterContent/Architecture/SM_Door.uasset` | ~64 KB | StarterContent | 建筑构件 |
| `StarterContent/Content/StarterContent/Props/SM_Rock.uasset` | ~71 KB | StarterContent | 有机形状 |
| `ThirtPerson/Content/ThirdPerson/Mannequins/LOD0/SM_Template_Manquin_Skin_01.uasset` | - | ThirdPerson | 人形网格 |
| `Games/LyraStarterGame/Content/Tools/SM_StairStep.uasset` | ~15 KB | Lyra | 建筑工具生成 |
| `StarterContent/Content/StarterContent/Architecture/SM_AssetPlatform.uasset` | - | StarterContent | 平台/地板 |

### 2. Skeletal Mesh (骨骼网格体)

| 字段 | 内容 |
|------|------|
| **前缀** | `SK_` |
| **引擎类** | `USkeletalMesh` |
| **内部类型字符串** | `SkeletalMesh` |
| **描述** | 带骨骼层级、支持动画变形的3D网格 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `Games/LyraStarterGame/Content/Characters/Heroes/Mannequin/Meshes/SK_Mannequin.uasset` | ~138 KB | Lyra | 完整角色模型 |
| `Games/LyraStarterGame/Content/Weapons/Pistol/Mesh/SK_Pistol.uasset` | - | Lyra | 武器模型 |
| `Games/LyraStarterGame/Content/Weapons/Rifle/Mesh/SK_Rifle.uasset` | - | Lyra | 武器模型 |
| `Games/LyraStarterGame/Content/Weapons/Pistol/Mesh/SK_Pistol_Skeleton.uasset` | - | Lyra | 纯骨骼定义 |

### 3. Texture (纹理)

| 字段 | 内容 |
|------|------|
| **前缀** | `T_` |
| **引擎类** | `UTexture2D` / `UTextureCube` |
| **内部类型字符串** | `Texture2D` |
| **描述** | 贴图资源，包括漫反射(D)、法线(N)、遮罩(M)等 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `StarterContent/Content/StarterContent/Textures/T_Brick_Clay_Beveled_D.uasset` | ~7.6 MB | StarterContent | 大尺寸砖纹理 |
| `StarterContent/Content/StarterContent/Textures/T_Metal_Steel_N.uasset` | ~83 KB | StarterContent | 法线贴图 |
| `StarterContent/Content/StarterContent/Textures/T_Wood_Oak_D.uasset` | ~7.5 MB | StarterContent | 木纹漫反射 |
| `StarterContent/Content/StarterContent/Textures/T_Fire_Tiled_D.uasset` | ~12.1 MB | StarterContent | 超大纹理 |
| `Games/LyraStarterGame/Content/Weapons/Pistol/Textures/T_Pistol_AORM.uasset` | ~20.8 MB | Lyra | 合并贴图(AORM) |
| `StarterContent/Content/StarterContent/Textures/T_RockMesh_M.uasset` | ~52 KB | StarterContent | 小型遮罩纹理 |

### 4. Material (材质)

| 字段 | 内容 |
|------|------|
| **前缀** | `M_` |
| **引擎类** | `UMaterial` |
| **内部类型字符串** | `Material` |
| **描述** | 材质图，定义表面渲染逻辑 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `StarterContent/Content/StarterContent/Materials/M_Wood_Oak.uasset` | ~24 KB | StarterContent | 简单材质 |
| `StarterContent/Content/StarterContent/Materials/M_Water_Ocean.uasset` | ~88 KB | StarterContent | 水材质(复杂) |
| `StarterContent/Content/StarterContent/Materials/M_Tech_Hex_Tile.uasset` | ~25 KB | StarterContent | 科技风格 |
| `Games/LyraStarterGame/Content/Characters/Heroes/Mannequin/Materials/M_Mannequin.uasset` | ~159 KB | Lyra | 角色皮肤材质 |

### 5. Material Instance (材质实例)

| 字段 | 内容 |
|------|------|
| **前缀** | `MI_` |
| **引擎类** | `UMaterialInstanceConstant` |
| **内部类型字符串** | `MaterialInstanceConstant` |
| **描述** | 基于父材质的参数化实例 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `Games/LyraStarterGame/Content/UI/Menu/MI_UI_TitleMaterial.uasset` | ~7.4 KB | Lyra | UI材质实例 |
| `StarterContent/Content/StarterContent/Materials/MI_Rock_Marble.uasset` | - | StarterContent | 石材质实例 |

### 6. Blueprint (蓝图)

| 字段 | 内容 |
|------|------|
| **前缀** | `BP_` / `B_` |
| **引擎类** | `UBlueprint` / `UBlueprintGeneratedClass` |
| **内部类型字符串** | `Blueprint` |
| **描述** | 可视化脚本资产，可定义Actor、ActorComponent等 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset` | ~514 KB | FirstPerson | 角色蓝图(复杂) |
| `FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonGameMode.uasset` | ~22 KB | FirstPerson | 游戏模式 |
| `Games/LyraStarterGame/Content/B_LyraGameInstance.uasset` | ~9.6 KB | Lyra | 游戏实例(短前缀) |
| `Games/LyraStarterGame/Content/B_Weapon.uasset` | ~432 KB | Lyra | 武器基类蓝图 |
| `ThirtPerson/Content/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.uasset` | ~507 KB | ThirdPerson | 第三人称游戏模式 |

### 7. Widget Blueprint (UI控件蓝图)

| 字段 | 内容 |
|------|------|
| **前缀** | `WBP_` / `W_` / `UI_` |
| **引擎类** | `UWidgetBlueprint` |
| **内部类型字符串** | `WidgetBlueprint` |
| **描述** | UMG UI界面 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `FirstPersonC/Content/Variant_Horror/UI/UI_Horror.uasset` | ~13 KB | FirstPersonC | HUD界面 |
| `Games/LyraStarterGame/Content/UI/Menu/W_CommonInputData.uasset` | ~5 KB | Lyra | 输入数据UI |
| `Games/LyraStarterGame/Content/UI/W_OverallUILayout.uasset` | ~48 KB | Lyra | 布局UI |

### 8. Physics Material (物理材质)

| 字段 | 内容 |
|------|------|
| **前缀** | `PM_` |
| **引擎类** | `UPhysicalMaterial` |
| **内部类型字符串** | `PhysicalMaterial` |
| **描述** | 定义表面物理属性(摩擦、反弹等) |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `Games/LyraStarterGame/Content/PhysicsMaterials/PM_Character.uasset` | ~1.3 KB | Lyra | 角色物理 |
| `Games/LyraStarterGame/Content/PhysicsMaterials/PM_Concrete.uasset` | ~1.3 KB | Lyra | 混凝土物理 |
| `Games/LyraStarterGame/Content/PhysicsMaterials/PM_Glass.uasset` | ~1.3 KB | Lyra | 玻璃物理 |

### 9. Physics Asset (物理资产)

| 字段 | 内容 |
|------|------|
| **前缀** | `PHYS_` / `PA_` |
| **引擎类** | `UPhysicsAsset` |
| **内部类型字符串** | `PhysicsAsset` |
| **描述** | 骨骼物理碰撞体定义 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `Games/LyraStarterGame/Content/Characters/Heroes/Mannequin/Rig/PA_Mannequin.uasset` | - | Lyra | 角色物理碰撞 |
| `FirstPerson/Content/Weapons/Pistol/Meshes/PA_Pistol.uasset` | - | FirstPerson | 手枪物理碰撞 |
| `FirstPerson/Content/Weapons/Rifle/Meshes/PA_Rifle.uasset` | - | FirstPerson | 步枪物理碰撞 |
| `FirstPerson/Content/Weapons/GrenadeLauncher/Meshes/PA_GrenadeLauncher.uasset` | - | FirstPerson | 榴弹发射器物理 |
| `ThirtPerson/Content/Characters/Mannequins/Rigs/PA_Mannequin.uasset` | - | ThirdPerson | 第三人称角色物理 |
| `Games/LyraStarterGame/Content/Weapons/Pistol/Mesh/SK_Pistol_PhysicsAsset.uasset` | - | Lyra | 武器物理(命名变体) |

---

## 二、动画资产 (Animation Assets)

### 10. Animation Blueprint (动画蓝图)

| 字段 | 内容 |
|------|------|
| **前缀** | `ABP_` |
| **引擎类** | `UAnimBlueprint` |
| **内部类型字符串** | `AnimBlueprint` |
| **描述** | 控制骨骼动画状态机 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `Games/LyraStarterGame/Content/Characters/Heroes/Mannequin/Animations/ABP_Mannequin_Base.uasset` | ~1.8 MB | Lyra | 角色动画蓝图 |
| `FirstPerson/Content/FirstPerson/Anims/ABP_FP_Copy.uasset` | ~57 KB | FirstPerson | 简化版动画蓝图 |
| `FirstPersonC/Content/Variant_Shooter/Anims/ABP_FP_Pistol.uasset` | ~57 KB | FirstPersonC | 手枪动画 |
| `FirstPersonC/Content/Variant_Shooter/Anims/ABP_TP_Rifle.uasset` | ~400 KB | FirstPersonC | 步枪动画(复杂) |

### 11. Animation Montage (动画蒙太奇)

| 字段 | 内容 |
|------|------|
| **前缀** | `AM_` |
| **引擎类** | `UAnimMontage` |
| **内部类型字符串** | `AnimMontage` |
| **描述** | 可动态播放的动画片段 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `Games/LyraStarterGame/Content/Weapons/Pistol/Animations/AM_Weap_Pistol_Fire.uasset` | ~8.7 KB | Lyra | 手枪射击 |
| `FirstPersonC/Content/Variant_Shooter/Anims/FP_Rifle_Shoot_Montage.uasset` | ~11 KB | FirstPersonC | 步枪射击 |
| `FirstPerson/Content/Characters/Mannequins/Anims/MM_Death_Back_01.uasset` | - | FirstPerson | 死亡动画 |
| `FirstPerson/Content/Characters/Mannequins/Anims/MM_Pistol_Fire.uasset` | - | FirstPerson | 手枪动画 |
| `FirstPerson/Content/Characters/Mannequins/Anims/MM_Idle.uasset` | - | FirstPerson | 待机动画 |

### 12. Animation Sequence (动画序列)

| 字段 | 内容 |
|------|------|
| **前缀** | `AS_` |
| **引擎类** | `UAnimSequence` |
| **内部类型字符串** | `AnimSequence` |
| **描述** | 基础关键帧动画数据 |

> Samples 中动画序列多嵌入在动画蓝图或蒙太奇内。独立 AS_ 资产在 Lyra 动画目录中查找。

### 13. Blend Space (混合空间)

| 字段 | 内容 |
|------|------|
| **前缀** | `BS_` |
| **引擎类** | `UBlendSpace` |
| **内部类型字符串** | `BlendSpace` |
| **描述** | 基于输入参数混合多个动画 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `FirstPerson/Content/Characters/Mannequins/Anims/BS_Idle_Walk_Run.uasset` | - | FirstPerson | 走跑混合空间 |

### 14. ControlRig (控制绑定)

| 字段 | 内容 |
|------|------|
| **前缀** | `CtrlRig_` / `Ctrl_` / `CR_` |
| **引擎类** | `UControlRig` |
| **描述** | 程序化骨骼控制 |
| **插件** | ControlRig |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `FirstPerson/Content/FirstPerson/Anims/CtrlRig_FPWarp.uasset` | ~243 KB | FirstPerson | 第一人称扭曲Rig |
| `FirstPersonC/Content/Variant_Shooter/Anims/Ctrl_HandAdjusment.uasset` | ~502 KB | FirstPersonC | 手部调整Rig |

### 15. Skeleton (骨架)

| 字段 | 内容 |
|------|------|
| **前缀** | `SKEL_` |
| **引擎类** | `USkeleton` |
| **内部类型字符串** | `Skeleton` |
| **描述** | 骨骼层级定义，动画共享基础 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `Games/LyraStarterGame/Content/Weapons/Pistol/Mesh/SK_Pistol_Skeleton.uasset` | - | Lyra | 手枪骨架 |
| `Games/LyraStarterGame/Content/Weapons/Rifle/Mesh/SK_Rifle_Skeleton.uasset` | - | Lyra | 步枪骨架 |

---

## 三、Niagara / 粒子系统 (Particle Effects)

### 16. Niagara System (Niagara系统)

| 字段 | 内容 |
|------|------|
| **前缀** | `NS_` (实际使用) / `FXS_` (官方推荐) |
| **引擎类** | `UNiagaraSystem` |
| **描述** | 完整的粒子效果系统 |
| **插件** | Niagara |

**测试文件示例:**

| 文件路径 | 来源项目 | 适合测试 |
|----------|----------|----------|
| `Games/LyraStarterGame/Content/Effects/Particles/Explosion/NS_Grenade_Explosion.uasset` | Lyra | 爆炸效果 |
| `Games/LyraStarterGame/Content/Effects/Particles/Impacts/NS_ImpactConcrete.uasset` | Lyra | 命中效果 |
| `Games/LyraStarterGame/Content/Effects/Particles/Environmental/NS_JumpPad.uasset` | Lyra | 跳板效果 |
| `Games/LyraStarterGame/Content/Effects/Particles/Footsteps/NS_Footsteps.uasset` | Lyra | 脚步粒子 |
| `Games/LyraStarterGame/Content/Effects/Particles/Weapons/NS_WeaponFire.uasset` | Lyra | 武器开火 |
| `Games/LyraStarterGame/Content/Effects/Camera/Damage/NS_Screen_DamageDirection.uasset` | Lyra | 屏幕空间效果 |
| `ThirtPerson/Content/LevelPrototyping/Interactable/JumpPad/Assets/NS_JumpPad.uasset` | ThirdPerson | 跳板 |
| `FirstPerson/Content/Variant_Horror/Blueprints/Light/Assets/NS_DustMote.uasset` | FirstPerson | 灰尘粒子 |

### 17. Niagara Emitter (Niagara发射器)

| 字段 | 内容 |
|------|------|
| **前缀** | `FXE_` |
| **引擎类** | `UNiagaraEmitter` |
| **描述** | 粒子发射器定义 |

### 18. Legacy Particle System (传统粒子系统 - Cascade)

| 字段 | 内容 |
|------|------|
| **前缀** | `P_` |
| **引擎类** | `UParticleSystem` |
| **内部类型字符串** | `ParticleSystem` |
| **描述** | 旧版Cascade粒子系统 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `StarterContent/Content/StarterContent/Particles/P_Explosion.uasset` | ~273 KB | StarterContent | 爆炸粒子 |
| `StarterContent/Content/StarterContent/Particles/P_Fire.uasset` | ~253 KB | StarterContent | 火焰粒子 |
| `StarterContent/Content/StarterContent/Particles/P_Sparks.uasset` | ~168 KB | StarterContent | 火花粒子 |
| `StarterContent/Content/StarterContent/Particles/P_Smoke.uasset` | ~65 KB | StarterContent | 烟雾粒子 |

### 19. Shape (粒子碰撞形状)

| 字段 | 内容 |
|------|------|
| **前缀** | `Shape_` |
| **引擎类** | `UStaticMesh` (用作粒子碰撞) |
| **描述** | 粒子碰撞用的基本几何体 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `StarterContent/Content/StarterContent/Shapes/Shape_Cube.uasset` | ~16 KB | StarterContent | 立方体 |
| `StarterContent/Content/StarterContent/Shapes/Shape_Sphere.uasset` | ~37 KB | StarterContent | 球体 |
| `StarterContent/Content/StarterContent/Shapes/Shape_Cylinder.uasset` | ~30 KB | StarterContent | 圆柱体 |

---

## 四、音频资产 (Audio Assets)

### 20. Sound Wave (声波)

| 字段 | 内容 |
|------|------|
| **前缀** | 无固定前缀，常用 `A_` / `SFX_` / `Music_` |
| **引擎类** | `USoundWave` |
| **内部类型字符串** | `SoundWave` |
| **描述** | 实际音频波形数据 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `StarterContent/Content/StarterContent/Audio/Starter_Music01.uasset` | ~8.2 MB | StarterContent | 音乐文件(大) |
| `StarterContent/Content/StarterContent/Audio/Starter_Birds01.uasset` | ~2.6 MB | StarterContent | 环境音效 |
| `StarterContent/Content/StarterContent/Audio/Fire01.uasset` | ~537 KB | StarterContent | 火焰音效 |
| `StarterContent/Content/StarterContent/Audio/Explosion01.uasset` | ~275 KB | StarterContent | 爆炸音效 |
| `Games/LyraStarterGame/Content/Audio/DYN_LowMultibandDynamics.uasset` | ~1 MB | Lyra | 动态音频处理 |

### 21. Sound Cue (音效提示)

| 字段 | 内容 |
|------|------|
| **前缀** | 无固定前缀 |
| **引擎类** | `USoundCue` |
| **内部类型字符串** | `SoundCue` |
| **描述** | 音效逻辑图(混音、随机化等) |

### 22. MetaSound (元音效)

| 字段 | 内容 |
|------|------|
| **前缀** | 无标准前缀 |
| **引擎类** | `UMetaSoundSource` / `UMetaSoundPatch` |
| **描述** | 新一代程序化音频系统 |
| **插件** | MetaSound |

---

## 五、Gameplay 能力系统资产 (Gameplay Ability System)

### 23. Gameplay Ability (游戏能力)

| 字段 | 内容 |
|------|------|
| **前缀** | `GA_` |
| **引擎类** | `UGameplayAbility` |
| **描述** | 可触发的游戏能力(攻击、闪避等) |
| **插件** | GameplayAbilities |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `Games/LyraStarterGame/Content/Weapons/GA_Weapon_Fire.uasset` | ~332 KB | Lyra | 武器射击能力 |
| `Games/LyraStarterGame/Content/Weapons/GA_Weapon_ReloadMagazine.uasset` | ~200 KB | Lyra | 换弹能力 |
| `Games/LyraStarterGame/Content/Weapons/GA_Weapon_AutoReload.uasset` | ~100 KB | Lyra | 自动换弹 |

### 24. Gameplay Effect (游戏效果)

| 字段 | 内容 |
|------|------|
| **前缀** | `GE_` |
| **引擎类** | `UGameplayEffect` |
| **描述** | 属性修改效果(伤害、治疗、Buff等) |
| **插件** | GameplayAbilities |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `Games/LyraStarterGame/Content/GameplayEffects/GE_HeroDash_Cooldown.uasset` | ~7 KB | Lyra | 冷却效果 |
| `Games/LyraStarterGame/Content/GameplayEffects/Damage/GE_Damage_Basic_Instant.uasset` | - | Lyra | 瞬时伤害 |
| `Games/LyraStarterGame/Content/GameplayEffects/Damage/GE_Damage_Basic_Periodic.uasset` | - | Lyra | 周期伤害(DoT) |
| `Games/LyraStarterGame/Content/GameplayEffects/Damage/GE_Damage_Basic_SetByCaller.uasset` | - | Lyra | 动态伤害(SetByCaller) |
| `Games/LyraStarterGame/Content/GameplayEffects/Heal/GE_Heal_Instant.uasset` | - | Lyra | 瞬时治疗 |
| `Games/LyraStarterGame/Content/GameplayEffects/Heal/GE_Heal_Periodic.uasset` | - | Lyra | 周期治疗(HoT) |
| `Games/LyraStarterGame/Content/GameplayEffects/GE_BlockAbilityInput.uasset` | - | Lyra | 封锁能力输入 |
| `Games/LyraStarterGame/Content/GameplayEffects/GE_DynamicTag.uasset` | - | Lyra | 动态标签效果 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Weapons/GE_Damage_Melee.uasset` | - | Lyra | 近战伤害 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Weapons/Rifle/GE_Damage_RifleAuto.uasset` | - | Lyra | 步枪伤害 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Weapons/Shotgun/GE_Damage_Shotgun.uasset` | - | Lyra | 霰弹枪伤害 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Items/HealthPickup/GE_InstantHeal_Pickup.uasset` | - | Lyra | 生命拾取效果 |
| `Games/LyraStarterGame/Plugins/GameFeatures/TopDownArena/Content/Game/Powerups/GE_Stat_MoveSpeed.uasset` | - | Lyra | 移速增益 |

### 25. Gameplay Cue Notify (游戏通知)

| 字段 | 内容 |
|------|------|
| **前缀** | `GCN_` / `GCNL_` |
| **引擎类** | `UGameplayCueNotify` |
| **描述** | 游戏能力触发时的视觉/音效通知 |
| **插件** | GameplayAbilities |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `Games/LyraStarterGame/Content/GameplayCueNotifies/GCNL_Character_DamageTaken.uasset` | ~6 KB | Lyra | 受击通知(Looping) |
| `Games/LyraStarterGame/Content/GameplayCueNotifies/GCN_Weapon_Impact.uasset` | ~6 KB | Lyra | 武器命中(Burst) |
| `Games/LyraStarterGame/Content/GameplayCueNotifies/GCN_Character_Heal.uasset` | ~6 KB | Lyra | 治疗通知 |
| `Games/LyraStarterGame/Content/GameplayCueNotifies/GCNL_Test_Looping.uasset` | - | Lyra | 循环通知测试 |
| `Games/LyraStarterGame/Content/GameplayCueNotifies/GCN_Test_Burst.uasset` | - | Lyra | 爆发通知测试 |
| `Games/LyraStarterGame/Content/GameplayCueNotifies/GCN_Test_BurstLatent.uasset` | - | Lyra | 延迟爆发测试 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Weapons/Pistol/GCN_Weapon_Pistol_Fire.uasset` | - | Lyra | 手枪开火通知 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Weapons/Rifle/GCN_Weapon_Rifle_Fire.uasset` | - | Lyra | 步枪开火通知 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Weapons/Shotgun/GCN_Weapon_Shotgun_Fire.uasset` | - | Lyra | 霰弹枪开火通知 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Weapons/Grenade/GCN_Grenade_Detonate.uasset` | - | Lyra | 手榴弹爆炸通知 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/GameplayCues/GCNL_Dash.uasset` | - | Lyra | 冲刺通知 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/GameplayCues/GCNL_Death.uasset` | - | Lyra | 死亡通知 |

---

## 六、输入资产 (Input Assets) - Enhanced Input

### 26. Input Action (输入动作)

| 字段 | 内容 |
|------|------|
| **前缀** | `IA_` |
| **引擎类** | `UInputAction` |
| **内部类型字符串** | `InputAction` |
| **描述** | 定义单个输入行为(跳跃、移动、射击等) |

**测试文件示例:**

| 文件路径 | 来源项目 | 适合测试 |
|----------|----------|----------|
| `Games/LyraStarterGame/Content/Input/Actions/IA_Jump.uasset` | Lyra | 跳跃动作 |
| `Games/LyraStarterGame/Content/Input/Actions/IA_Move.uasset` | Lyra | 移动输入 |
| `Games/LyraStarterGame/Content/Input/Actions/IA_Look_Mouse.uasset` | Lyra | 鼠标视角 |
| `Games/LyraStarterGame/Content/Input/Actions/IA_Ability_Dash.uasset` | Lyra | 冲刺能力输入 |
| `Games/LyraStarterGame/Content/Input/Actions/IA_Weapon_Fire.uasset` | Lyra | 武器射击 |
| `Games/LyraStarterGame/Content/Input/Actions/IA_Weapon_Reload.uasset` | Lyra | 武器换弹 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Input/Actions/IA_ADS.uasset` | Lyra | 瞄准输入 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Input/Actions/IA_Grenade.uasset` | Lyra | 手榴弹输入 |
| `FirstPerson/Content/Variant_Horror/Input/IA_Sprint.uasset` | FirstPerson | 疾跑输入 |
| `ThirtPerson/Content/Variant_Combat/Input/Actions/IA_ChargedAttack.uasset` | ThirdPerson | 蓄力攻击 |
| `ThirtPerson/Content/Variant_Platforming/Input/Actions/IA_Dash.uasset` | ThirdPerson | 冲刺输入 |

### 27. Input Mapping Context (输入映射上下文)

| 字段 | 内容 |
|------|------|
| **前缀** | `IMC_` |
| **引擎类** | `UInputMappingContext` |
| **内部类型字符串** | `InputMappingContext` |
| **描述** | 将InputAction映射到实际键/轴 |

**测试文件示例:**

| 文件路径 | 来源项目 | 适合测试 |
|----------|----------|----------|
| `Games/LyraStarterGame/Content/Input/Mappings/IMC_Default.uasset` | Lyra | 默认输入映射 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Input/Mappings/IMC_ShooterGame.uasset` | Lyra | 射击游戏输入 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Input/Mappings/IMC_ShooterGame_KBM.uasset` | Lyra | 键盘鼠标输入 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Input/Mappings/IMC_ADS_Speed.uasset` | Lyra | 瞄准速度修改 |
| `FirstPerson/Content/Input/IMC_Default.uasset` | FirstPerson | 默认输入 |
| `FirstPerson/Content/Input/IMC_MouseLook.uasset` | FirstPerson | 鼠标视角 |
| `FirstPerson/Content/Variant_Horror/Input/IMC_Horror.uasset` | FirstPerson | 恐怖模式输入 |
| `ThirtPerson/Content/Variant_Combat/Input/IMC_Combat.uasset` | ThirdPerson | 战斗输入 |
| `ThirtPerson/Content/Variant_Platforming/Input/IMC_Platforming.uasset` | ThirdPerson | 平台跳跃输入 |

---

## 七、AI 资产 (AI Assets)

### 28. Behavior Tree (行为树)

| 字段 | 内容 |
|------|------|
| **前缀** | `BT_` |
| **引擎类** | `UBehaviorTree` |
| **内部类型字符串** | `BehaviorTree` |
| **描述** | AI行为决策树 |

### 27. Blackboard Data (黑板数据)

| 字段 | 内容 |
|------|------|
| **前缀** | `BB_` |
| **引擎类** | `UBlackboardData` |
| **内部类型字符串** | `BlackboardData` |
| **描述** | AI共享内存黑板 |

### 28. Environment Query (环境查询 - EQS)

| 字段 | 内容 |
|------|------|
| **前缀** | `EQS_` |
| **引擎类** | `UEnvQuery` |
| **内部类型字符串** | `EnvQuery` |
| **描述** | 环境评分查询模板 |

---

## 八、数据资产 (Data Assets)

### 32. Data Table (数据表)

| 字段 | 内容 |
|------|------|
| **前缀** | `DT_` |
| **引擎类** | `UDataTable` |
| **内部类型字符串** | `DataTable` |
| **描述** | 表格数据(Row-based) |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `Games/LyraStarterGame/Content/ContextEffects/DT_AnimEffectTags.uasset` | - | Lyra | 动画效果标签表 |
| `Games/LyraStarterGame/Content/ContextEffects/DT_SurfaceTypes.uasset` | - | Lyra | 表面类型表 |
| `Games/LyraStarterGame/Content/UI/DT_UniversalActions.uasset` | ~44 KB | Lyra | 通用动作表 |
| `Games/LyraStarterGame/Content/UI/Settings/DT_SaveActions.uasset` | - | Lyra | 存档动作表 |
| `FirstPerson/Content/Variant_Shooter/Blueprints/Pickups/DT_WeaponList.uasset` | - | FirstPerson | 武器列表表 |
| `FirstPersonC/Content/Variant_Shooter/Blueprints/Pickups/DT_WeaponData.uasset` | - | FirstPersonC | 武器数据表 |
| `Games/LyraStarterGame/Plugins/GameFeatures/ShooterCore/Content/Accolades/DT_BasicShooterAccolades.uasset` | - | Lyra | 成就数据表 |

### 33. Curve Table (曲线表)

| 字段 | 内容 |
|------|------|
| **前缀** | `CT_` |
| **引擎类** | `UCurveTable` |
| **内部类型字符串** | `CurveTable` |
| **描述** | 曲线数据表 |

### 34. Enum (用户定义枚举)

| 字段 | 内容 |
|------|------|
| **前缀** | `E_` / `Enum_` |
| **引擎类** | `UUserDefinedEnum` |
| **内部类型字符串** | `UserDefinedEnum` |
| **描述** | 蓝图可用枚举 |

**测试文件示例:**

| 文件路径 | 来源项目 | 适合测试 |
|----------|----------|----------|
| `Games/LyraStarterGame/Content/Tools/Enum_PanelType.uasset` | Lyra | 面板类型枚举 |

### 35. Structure (用户定义结构体)

| 字段 | 内容 |
|------|------|
| **前缀** | `F_` / `ST_` |
| **引擎类** | `UUserDefinedStruct` |
| **内部类型字符串** | `UserDefinedStruct` |
| **描述** | 蓝图可用结构体 |

### 36. Primary Data Asset (主数据资产)

| 字段 | 内容 |
|------|------|
| **前缀** | 无固定前缀，常用描述性名称 |
| **引擎类** | `UPrimaryDataAsset` |
| **描述** | 游戏主数据配置 |

**测试文件示例:**

| 文件路径 | 大小 | 来源项目 | 适合测试 |
|----------|------|----------|----------|
| `Games/LyraStarterGame/Content/DefaultGameData.uasset` | - | Lyra | 游戏默认配置 |
| `Games/LyraStarterGame/Content/DefaultGame_Label.uasset` | - | Lyra | 游戏标签 |

---

## 九、相机资产 (Camera Assets)

### 37. Camera Shake Asset (相机震动)

| 字段 | 内容 |
|------|------|
| **前缀** | `BP_CameraShake_` / 无固定 |
| **引擎类** | `UCameraShakeAsset` |
| **描述** | 程序化相机震动效果 |
| **插件** | GameplayCameras |

**测试文件示例:**

| 文件路径 | 来源项目 | 适合测试 |
|----------|----------|----------|
| `ThirtPerson/Content/Variant_Combat/Blueprints/BP_CameraShake_Hit_Enemy.uasset` | ThirdPerson | 受击震动 |
| `ThirtPerson/Content/Variant_Combat/Blueprints/BP_CameraShake_Hit_Player.uasset` | ThirdPerson | 玩家受击震动 |

### 38. Camera Manager (相机管理器)

| 字段 | 内容 |
|------|------|
| **前缀** | `BP_*CameraManager` / `CM_` |
| **引擎类** | `AGameplayCameraActor` (Actor蓝图) |
| **描述** | 相机行为管理 |
| **插件** | GameplayCameras |

**测试文件示例:**

| 文件路径 | 来源项目 | 适合测试 |
|----------|----------|----------|
| `FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCameraManager.uasset` | FirstPerson | 第一人称相机 |
| `ThirtPerson/Content/Variant_SideScroller/Blueprints/BP_SideScrollingCameraManager.uasset` | ThirdPerson | 横版相机 |
| `Games/LyraStarterGame/Plugins/GameFeatures/TopDownArena/Content/Game/CM_ArenaFramingCamera.uasset` | Lyra | 竞技场环绕相机 |

---

## 十、动画通知资产 (Animation Notify Assets)

### 39. Animation Notify (动画通知)

| 字段 | 内容 |
|------|------|
| **前缀** | `AN_` |
| **引擎类** | `UAnimNotify` / `UAnimNotifyState` |
| **描述** | 动画播放时触发的事件 |

**测试文件示例:**

| 文件路径 | 来源项目 | 适合测试 |
|----------|----------|----------|
| `Games/LyraStarterGame/Content/Effects/AnimationNotifies/AN_FootPlant_Left.uasset` | Lyra | 左脚踩踏通知 |
| `Games/LyraStarterGame/Content/Effects/AnimationNotifies/AN_FootPlant_Right.uasset` | Lyra | 右脚踩踏通知 |
| `Games/LyraStarterGame/Content/Characters/Heroes/Abilities/AN_Melee.uasset` | Lyra | 近战攻击通知 |
| `Games/LyraStarterGame/Content/Characters/Heroes/Abilities/AN_Reload.uasset` | Lyra | 换弹通知 |
| `Games/LyraStarterGame/Content/Characters/Heroes/Mannequin/Animations/AnimNotifies/AN_PlayWeaponMontage.uasset` | Lyra | 播放武器蒙太奇 |
| `ThirtPerson/Content/Variant_Combat/Anims/AN_AttackCombo.uasset` | ThirdPerson | 攻击连段通知 |
| `ThirtPerson/Content/Variant_Combat/Anims/AN_ChargedAttack.uasset` | ThirdPerson | 蓄力攻击通知 |
| `ThirtPerson/Content/Variant_Platforming/Anims/AN_EndDash.uasset` | ThirdPerson | 冲刺结束通知 |

---

## 十一、Material Function (材质函数)

| 字段 | 内容 |
|------|------|
| **前缀** | `MF_` |
| **引擎类** | `UMaterialFunction` |
| **内部类型字符串** | `MaterialFunction` |
| **描述** | 可复用的材质图子图 |

**测试文件示例:**

| 文件路径 | 来源项目 | 适合测试 |
|----------|----------|----------|
| `Games/LyraStarterGame/Content/Characters/Heroes/Mannequin/Effects/MF_AlphaLevels.uasset` | Lyra | Alpha混合函数 |
| `Games/LyraStarterGame/Content/Characters/Heroes/Mannequin/Effects/MF_DepthFade.uasset` | Lyra | 深度消退函数 |
| `Games/LyraStarterGame/Content/Characters/Heroes/Mannequin/Effects/MF_MotionStretch.uasset` | Lyra | 运动模糊函数 |

---

## 十二、Level Sequence (关卡序列)

| 字段 | 内容 |
|------|------|
| **前缀** | `LS_` |
| **引擎类** | `ULevelSequence` |
| **内部类型字符串** | `LevelSequence` |
| **描述** | Sequencer过场动画 |

---

## 十三、扩展插件资产类型 (Extended Plugin Asset Types)

以下为引擎插件中定义的高级资产类型，Samples中可能较少直接实例：

| # | 资产类型 | 前缀 | 引擎类 | 插件 | 描述 |
|---|---------|------|--------|------|------|
| 40 | Virtual Texture | VT_ / `UVirtualTexture2D` | `UVirtualTexture2D` | Engine | 运行时虚拟纹理 |
| 41 | Niagara Script | NS_ | `UNiagaraScript` | Niagara | Niagara脚本 |
| 42 | Niagara Effect Type | - | `UNiagaraEffectType` | Niagara | 粒子效果类型 |
| 43 | Niagara Parameter Collection | - | `UNiagaraParameterCollection` | Niagara | 粒子参数集合 |
| 44 | Sound Submix | - | `USoundSubmix` | Audio | 音频混音 |
| 45 | Sound Effect Preset | - | `USoundEffectPreset` | Audio | 音效预设 |
| 46 | Sound Control Bus | - | `USoundControlBus` | AudioModulation | 音频控制总线 |
| 47 | Destructible Mesh | DM_ | `UDestructibleMesh` | ApexDestruction | 可破坏网格 |
| 48 | Dialogue Asset | - | `UDialogueAsset` | Layerel | 对话资产 |
| 49 | Field System | - | `UFieldSystem` | FieldSystem | 场系统(力场) |
| 50 | Geometry Collection Cache | - | `UGeometryCollectionCache` | GeometryCollection | 几何集合缓存 |
| 51 | Chaos Cache Collection | - | `UChaosCacheCollection` | ChaosCaching | Chaos物理缓存 |
| 52 | ACL Compression DB | - | `UAnimationCompressionLibraryDatabase` | ACLPlugin | 动画压缩数据库 |
| 53 | Sound Simple | - | `USoundSimple` | SoundUtilities | 简化音效 |
| 54 | Landscape Layer Info | - | `ULandscapeLayerInfoObject` | Landscape | 地形层信息 |
| 55 | Conversation Database | - | `UConversationDatabase` | CommonConversation | 对话数据库 |
| 56 | NDisplay Config | NDC_ | `UNDisplayConfiguration` | ICVFX | LED墙显示配置 |
| 57 | Level Snapshots | SNAP_ | `ULevelSnapshot` | LevelSnapshots | 关卡快照 |
| 58 | Remote Control Preset | RCP_ | `URemoteControlPreset` | RemoteControl | 远程控制预设 |
| 59 | Mass Entity Config | - | `UMassEntityConfigAsset` | MassEntity | Mass实体配置 |
| 60 | PCG Graph | - | `UPCGGraph` | PCG | 程序化生成图 |
| 61 | PCG Settings | - | `UPCGSettings` | PCG | 程序化生成设置 |
| 62 | Media Source | MS_ | `UMediaSource` | MediaFramework | 媒体源 |
| 63 | Post Process Material | PPM_ | `UMaterial` | Engine | 后处理材质 |
| 64 | OCIO Profile | OCIO_ | `UOCIOProfile` | Engine | 色彩管理配置 |
| 62 | HDRI | HDR_ | `UTextureCube` | Engine | HDR环境贴图 |

---

## 十四、Samples 项目资产分布总览

| 项目 | 路径 | 主要资产类型 | 适合标注 |
|------|------|-------------|----------|
| **StarterContent** | `Samples/StarterContent/Content/` | StaticMesh, Texture, Material, Particle, Sound, Shape | 基础类型验证 |
| **FirstPerson** | `Samples/FirstPerson/Content/` | Blueprint, Animation, ControlRig, Camera | 角色动画/相机 |
| **FirstPersonC** | `Samples/FirstPersonC/Content/` | Blueprint(GA/GE风格), Animation, UI, Input | 战斗系统/输入 |
| **ThirdPerson** | `Samples/ThirtPerson/Content/` | Blueprint, Animation, Material, Camera, LevelPrototyping | 综合验证 |
| **LyraStarterGame** | `Samples/Games/LyraStarterGame/Content/` | 全类型覆盖(GAS, Niagara, UI, DataAsset) | **最佳测试源** |

---

## 十五、推荐测试标注策略

### 按资产类型分组标注优先级

| 优先级 | 资产类型 | 标注要点 | 推荐源 |
|--------|---------|---------|--------|
| P0 | StaticMesh | 解析LOD/Section/顶点数据 | StarterContent SM_Statue, SM_Bush |
| P0 | Texture2D | 解析压缩格式/分辨率/通道 | StarterContent T_Brick_Clay, T_Metal_Steel_N |
| P0 | Blueprint | 解析蓝图类结构/节点 | Lyra B_Weapon, FirstPerson BP_Character |
| P0 | Material | 解析材质图/参数/表达式 | Lyra M_Mannequin, StarterContent M_Water_Ocean |
| P1 | SkeletalMesh | 解析骨骼/权重/MorphTarget | Lyra SK_Mannequin, SK_Pistol |
| P1 | Animation Montage | 解析动画轨道/段/通知 | Lyra AM_Weap_Pistol_Fire |
| P1 | Animation Blueprint | 解析AnimGraph/状态机 | Lyra ABP_Mannequin_Base |
| P1 | Material Instance | 解析父引用/参数覆写 | Lyra MI_UI_TitleMaterial |
| P2 | GameplayAbility | 解析能力逻辑 | Lyra GA_Weapon_Fire |
| P2 | GameplayEffect | 解析效果/修饰器 | Lyra GE_Damage_Basic_Instant |
| P2 | GameplayCueNotify | 解析通知逻辑 | Lyra GCN_Weapon_Impact |
| P2 | Physics Material | 解析物理属性 | Lyra PM_Concrete, PM_Glass |
| P2 | Physics Asset | 解析碰撞体 | Lyra PA_Mannequin |
| P2 | DataTable | 解析表格行 | Lyra DT_UniversalActions |
| P2 | Input Action | 解析输入行为 | Lyra IA_Jump, IA_Move |
| P2 | Input Mapping Context | 解析键位映射 | Lyra IMC_Default |
| P3 | Niagara System | 解析粒子配置 | Lyra NS_Grenade_Explosion, NS_JumpPad |
| P3 | Sound Wave | 解析音频数据 | StarterContent Starter_Music01, Fire01 |
| P3 | ControlRig | 解析Rig逻辑 | FirstPerson CtrlRig_FPWarp |
| P3 | Widget Blueprint | 解析UI层次 | FirstPersonC UI_Horror |
| P3 | Camera Shake | 解析震动曲线 | ThirdPerson BP_CameraShake_* |
| P3 | Animation Notify | 解析动画通知 | Lyra AN_FootPlant, AN_Melee |
| P4 | Enum/Struct | 解析用户定义类型 | Lyra Enum_PanelType |
| P4 | Curve Table | 解析曲线数据 | Lyra CT_* |
| P4 | Level Sequence | 解析Sequencer数据 | 在Sample中搜索 LS_* |
| P5 | BehaviorTree | 解析AI行为 | 在Template中搜索 BT_* |
| P5 | PCG Graph | 解析PCG流程 | 在Sample中搜索 PCG图 |
| P5 | Mass Entity Config | 解析实体配置 | Lyra DefaultGameData |
