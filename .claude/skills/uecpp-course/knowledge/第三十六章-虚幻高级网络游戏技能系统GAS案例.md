# 第三十六章：虚幻高级网络游戏技能系统 GAS 案例

## 课程信息

本章以 017_XGRPG 项目为主线，完整实现了一个基于 GAS（GameplayAbilitySystem）的多人网络 RPG 战斗系统。项目约 7600 行 C++ 代码，架构参考了 Lyra 项目、MMORPG 教程和 Action RPG 示例的设计模式。

## 字幕资源

- 来源：`subtitles/036第三十六虚幻高级网络游戏技能系统GAS案例/`
- 共 60 个字幕文件（001~059，含 009 两个版本）

## 知识文档

本章知识拆分为 16 篇细粒度文档，按系统组织如下：

### 核心架构篇

| # | 文档 | 内容概要 |
|---|------|---------|
| 01 | [项目架构总览](ch36/01-项目架构总览.md) | 工程结构、目录组织、Lyra 参考模式、代码统计与子系统划分 |
| 02 | [GAS 核心框架](ch36/02-GAS核心框架.md) | ASC 实现、GameplayTag 定义体系、Ability 注册激活、输入处理、网络同步 |
| 03 | [AttributeSet 与属性系统](ch36/03-AttributeSet与属性系统.md) | 两层属性集架构、12 个具体属性、网络复制、PostGameplayEffectExecute 事件分发 |
| 04 | [伤害计算与 GEEC](ch36/04-伤害计算与GEEC.md) | UXGRPGDamageExecution 与 UXGRPGDamageExecution_Air 两种伤害执行器 |

### 战斗系统篇

| # | 文档 | 内容概要 |
|---|------|---------|
| 05 | [连击系统](ch36/05-连击系统.md) | ComboComponent 状态机、连击窗口管理、蒙太奇播放与输入联动 |
| 06 | [重攻击与碰撞盒子系统](ch36/06-重攻击与碰撞盒子系统.md) | HitBox 生成与管理、碰撞检测、BuffTag 机制、设置器控制台 |
| 07 | [远程攻击与弹道系统](ch36/07-远程攻击与弹道系统.md) | 弹道碰撞盒、UProjectileMovementComponent 整合、命中处理、表现层虚函数 |
| 08 | [技能系统](ch36/08-技能系统.md) | 冲刺、跳跃攻击、耐力恢复、回复、伤害技能等 5 类 GameplayAbility |

### 生存与 UI 篇

| # | 文档 | 内容概要 |
|---|------|---------|
| 09 | [死亡与重生系统](ch36/09-死亡与重生系统.md) | HealtComponent 状态机、死亡驱逐、生命复活、GameState 控制 |
| 10 | [伤害数字系统](ch36/10-伤害数字系统.md) | 四层组件化架构：请求 → 组件 → Actor → UI（DamageNumberActor + DamageNumberWidgetComponent） |
| 11 | [UI 系统](ch36/11-UI系统.md) | UI 基类体系、HUD 管理、血条/蓝条/属性展示、背包/装备面板、伤害数字、结算 UI |

### 物品与配置篇

| # | 文档 | 内容概要 |
|---|------|---------|
| 12 | [背包系统](ch36/12-背包系统.md) | InventoryComponent（复制）+ InventoryUI + InventorySlot，物品数据驱动 |
| 13 | [装备系统](ch36/13-装备系统.md) | EquipmentComponent（复制）+ EquipmentItem + EquipmentUI + Slot 面板 |
| 14 | [AssetManager 与 GameData](ch36/14-AssetManager与GameData.md) | 物品数据表管理、GE 引用加载、异步/同步加载策略 |
| 15 | [动画通知系统](ch36/15-动画通知系统.md) | 8 个动画通知类：Attack、ApplyGameplayEffect、ResetCombo、NextCombo、AddForce、StopSpeed、StopRotation、IgnoreInput |
| 16 | [打包与工程配置](ch36/16-打包与工程配置.md) | 模块初始化、专有服务器限制、网络配置、打包注意事项 |

## 操作日志

本次知识提取与验证记录见 [log.md](log.md)。
