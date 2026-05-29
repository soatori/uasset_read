# FirstPerson 蓝图资产解析测试报告

## 测试概述

**测试日期**: 2026-05-30
**测试范围**: `E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content`
**对照组**: `E:\Develop\lib\UnrealEngine\Samples\FirstPersonC\Source` (C++ 实现)
**解析器版本**: uasset_read (worktree: test-blueprint-vs-cpp)

---

## 一、测试结果总结

### 总体统计

| 指标 | 数值 |
|------|------|
| **总测试资产数** | 29 |
| **成功解析** | 29 (100%) |
| **解析失败** | 0 (0%) |
| **蓝图资产** | 17 |
| **其他类型资产** | 12 |

### 按资产类型统计

| 资产类型 | 数量 | 成功率 | 未知Token | 未知K2Node |
|----------|------|--------|-----------|------------|
| Blueprint | 17 | 100% | 75 | 19 |
| AnimationBlueprint | 4 | 100% | 102 | 4 |
| BlendSpace | 1 | 100% | 0 | 0 |
| ControlRig | 1 | 100% | 0 | 0 |
| InputAction | 2 | 100% | 0 | 0 |
| InputMappingContext | 1 | 100% | 0 | 0 |
| DataTable | 1 | 100% | 0 | 0 |
| StateTree | 1 | 100% | 3 | 0 |
| EQS | 1 | 100% | 0 | 0 |

---

## 二、解析器问题分析

### 1. 未知字节码 Token (Unknown EExprToken)

**总计**: 180 个

| Token | 出现次数 | 影响资产 |
|-------|----------|----------|
| `0xFF` | 179 | HorrorCharacter, HorrorPlayerController, ShooterCharacter, ShooterGameMode, ShooterPlayerController, ShooterAIController, ShooterNPC, ShooterPickup, ABP_FP_Pistol |
| `0xF9` | 1 | ShooterNPC |

**分析**: `0xFF` token 在多个蓝图中出现，主要影响：
- HorrorCharacter (4次)
- ShooterCharacter (18次)
- ShooterNPC (20次)
- ABP_FP_Pistol (91次) - 动画蓝图中最多

**可能原因**: UE5 新版本引入的字节码操作符，解析器尚未支持。

### 2. 未知 K2Node 类型

**总计**: 22 个

| K2Node 类型 | 出现次数 | 描述 |
|-------------|----------|------|
| `K2Node_CallParentFunction` | 4 | 调用父类函数 |
| `K2Node_Message` | 4 | 消息调用 |
| `K2Node_Knot` | 2 | 连接节点 |
| `K2Node_MacroInstance` | 3 | 宏实例 |
| `K2Node_CallDelegate` | 2 | 委托调用 |
| `K2Node_AddDelegate` | 1 | 添加委托 |
| `K2Node_AssignDelegate` | 1 | 赋值委托 |
| `K2Node_CallArrayFunction` | 1 | 数组函数调用 |
| `K2Node_CreateWidget` | 1 | 创建控件 |
| `K2Node_GetDataTableRow` | 1 | 获取数据表行 |
| `K2Node_LoadAsset` | 1 | 加载资产 |
| `K2Node_SpawnActorFromClass` | 1 | 从类生成Actor |

**分析**: 这些 K2Node 类型在蓝图图表中常见，解析器需要添加支持。

### 3. BPGC 字节码回退

**总计**: 14 次

| 出现位置 | 描述 |
|----------|------|
| `Aim` | BP_FirstPersonCharacter |
| `ExecuteUbergraph_BP_HorrorCharacter` | 恐怖角色 |
| `ExecuteUbergraph_BP_HorrorPlayerController` | 恐怖玩家控制器 |
| `ExecuteUbergraph_BP_ShooterGameMode` | 射击游戏模式 |
| `ExecuteUbergraph_BP_ShooterPlayerController` | 射击玩家控制器 |
| `BndEvt__BP_Rifle_SphereCollision...` | 步枪碰撞事件 |
| 各种 ABP_* | 动画蓝图 |

**分析**: BPGC 回退表明 Kismet 图解析失败，需要从字节码提取信息。

### 4. P73 恢复

**总计**: 4 次

出现在 `BP_ShooterCharacter` 中，涉及 `LinkedTo` 字段的坏计数恢复。

---

## 三、蓝图 vs C++ 对比分析

### 测试的蓝图-C++ 对映射

| # | 蓝图资产 | C++ 类 | 状态 |
|---|----------|--------|------|
| 1 | BP_FirstPersonCharacter | AFirstPersonCCharacter | ✓ |
| 2 | BP_FirstPersonGameMode | AFirstPersonCGameMode | ✓ |
| 3 | BP_FirstPersonCameraManager | AFirstPersonCCameraManager | ✓ |
| 4 | BP_FirstPersonPlayerController | AFirstPersonCPlayerController | ✓ |
| 5 | BP_HorrorCharacter | AHorrorCharacter | ✓ |
| 6 | BP_HorrorGameMode | AHorrorGameMode | ✓ |
| 7 | BP_HorrorPlayerController | AHorrorPlayerController | ✓ |
| 8 | BP_ShooterCharacter | AShooterCharacter | ✓ |
| 9 | BP_ShooterGameMode | AShooterGameMode | ✓ |
| 10 | BP_ShooterPlayerController | AShooterPlayerController | ✓ |
| 11 | BP_ShooterAIController | AShooterAIController | ✓ |
| 12 | BP_ShooterNPC | AShooterNPC | ✓ |
| 13 | BP_ShooterNPCSpawner | AShooterNPCSpawner | ✓ |
| 14 | BP_ShooterWeapon | AShooterWeapon | ✓ |
| 15 | BP_ShooterProjectile | AShooterProjectile | ✓ |
| 16 | BP_ShooterPickup | AShooterPickup | ✓ |
| 17 | WBP_BulletCounter | UShooterBulletCounterUI | ✓ |

### 关键发现

1. **所有蓝图资产均可成功解析** - 解析器核心功能稳定
2. **C++ 类中的蓝图实现部分** - 蓝图版本会重写 C++ 函数的逻辑
3. **预期差异**:
   - C++ 基类函数 (如 `DoAim`, `DoMove`) 在蓝图中被覆盖
   - 组件声明在 C++ 中通过 `UPROPERTY`，蓝图中通过组件树
   - 委托/事件在蓝图中通过 K2Node 实现

---

## 四、建议修复优先级

### P0 - 高优先级

1. **添加 `0xFF` token 支持**
   - 影响范围广 (179 次)
   - 主要出现在复杂蓝图 (ShooterCharacter, ABP_FP_Pistol)

2. **支持常见 K2Node 类型**
   - `K2Node_CallParentFunction` - 调用父类函数
   - `K2Node_Message` - 消息调用
   - `K2Node_MacroInstance` - 宏实例
   - `K2Node_CallDelegate` - 委托调用

### P1 - 中优先级

3. **改进 BPGC 回退机制**
   - 当前回退提取字节码，但丢失了图表结构信息
   - 建议: 增强 BPGC 解析以恢复更多图表信息

4. **支持 `0xF9` token**
   - 出现较少，但可能是重要操作符

### P2 - 低优先级

5. **添加其他 K2Node 类型支持**
   - `K2Node_Knot`
   - `K2Node_CreateWidget`
   - `K2Node_GetDataTableRow`
   - `K2Node_LoadAsset`
   - `K2Node_SpawnActorFromClass`

---

## 五、测试资产清单

### 蓝图资产 (17个)

| 文件名 | 类型 | 大小 | 状态 |
|--------|------|------|------|
| BP_FirstPersonCharacter | 角色蓝图 | ~514 KB | ✓ |
| BP_FirstPersonGameMode | 游戏模式 | ~22 KB | ✓ |
| BP_FirstPersonCameraManager | 相机管理器 | - | ✓ |
| BP_FirstPersonPlayerController | 玩家控制器 | - | ✓ |
| BP_HorrorCharacter | 恐怖角色 | - | ✓ |
| BP_HorrorGameMode | 恐怖游戏模式 | - | ✓ |
| BP_HorrorPlayerController | 恐怖玩家控制器 | - | ✓ |
| BP_ShooterCharacter | 射击角色 | - | ✓ |
| BP_ShooterGameMode | 射击游戏模式 | - | ✓ |
| BP_ShooterPlayerController | 射击玩家控制器 | - | ✓ |
| BP_ShooterAIController | AI控制器 | - | ✓ |
| BP_ShooterNPC | NPC | - | ✓ |
| BP_ShooterNPCSpawner | NPC生成器 | - | ✓ |
| BP_ShooterWeapon | 武器 | - | ✓ |
| BP_ShooterProjectile | 投射物 | - | ✓ |
| BP_ShooterPickup | 拾取物 | - | ✓ |
| WBP_BulletCounter | UI控件 | - | ✓ |

### 其他类型资产 (12个)

| 文件名 | 类型 | 状态 |
|--------|------|------|
| ABP_Unarmed | 动画蓝图 | ✓ |
| ABP_FP_Copy | 动画蓝图 | ✓ |
| ABP_FP_Pistol | 动画蓝图 | ✓ |
| ABP_TP_Rifle | 动画蓝图 | ✓ |
| BS_Idle_Walk_Run | 混合空间 | ✓ |
| CtrlRig_FPWarp | ControlRig | ✓ |
| IA_Jump | 输入动作 | ✓ |
| IA_Move | 输入动作 | ✓ |
| IMC_Default | 输入映射上下文 | ✓ |
| DT_WeaponList | 数据表 | ✓ |
| StateTreeTask_ShootAtTarget | StateTree | ✓ |
| EQS_FindRoamLocation | EQS | ✓ |

---

## 六、结论

### 解析器性能评估

- **核心解析能力**: 优秀 (100% 成功率)
- **蓝图图表解析**: 良好 (存在未知token和K2Node类型)
- **字节码回退**: 可用 (BPGC 回退机制工作正常)
- **P73 恢复**: 可用 (链接恢复机制工作正常)

### 改进建议

1. **短期**: 添加 `0xFF` token 支持和常见 K2Node 类型
2. **中期**: 改进 BPGC 回退以保留更多图表信息
3. **长期**: 支持更多 UE5 新特性 (如 StateTree、ControlRig 的完整解析)

---

*报告生成时间: 2026-05-30*
*测试环境: Windows 11, Python 3.10+, uasset_read v6.0.0*
