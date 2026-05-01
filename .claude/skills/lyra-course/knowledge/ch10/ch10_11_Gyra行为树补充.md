# Gyra 行为树补充

## 概述

本节简要介绍 Gyra 项目中行为树的补充使用，涵盖小兵和 Boss 的行为树设计、自定义 Task/Decorator 以及跳跃链接等 Navigation Mesh 相关技术。

## 小兵追击行为树

小兵行为树包含以下自定义节点：

- `BTT_SetMovementSpeed`：设置移动速度的自定义 Task
- `BTT_Monster_MeleeAttack`：近战攻击 Task

## Boss 阶段行为树

Boss 行为树包含更复杂的阶段切换逻辑：

- 生命值检测：低于预期生命值时释放终极技能
- 传送技能、火球技能、生成僵尸技能
- 复用小兵追击行为树作为子行为树

### 自定义 Decorator

- `BTDecorator_HealthCheck`：检测生命值阈值，控制行为树分支切换
- `BTDecorator_CheckDistance`：检测与目标距离，控制技能释放时机

### 自定义 Task

- `BTT_Lich_Transport`：Boss 传送 Task

## 跳跃链接

跳跃链接用于定义 AI 可以跳跃跨越的路径点，在 Navigation Mesh 上创建连接。

参考文档：[修改寻路网格体概述](https://dev.epicgames.com/documentation/zh-cn/unreal-engine/overview-of-how-to-modify-the-navigation-mesh-in-unreal-engine)

## 参考源码

本节内容为 Gyra 项目的独立行为树实现，不在 Lyra 工程源码中。相关内容可参考 Lyra 工程中的 AI 系统实现。
