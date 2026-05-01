# 源码架构概览

## 模块结构

Lyra 工程由两个主模块组成：

```
Lyra/
├── Source/
│   ├── LyraGame/          # 运行时模块，游戏核心逻辑
│   └── LyraEditor/        # 编辑器模块，编辑工具和定制
└── Plugins/               # 插件目录
    ├── CommonGame/
    ├── CommonUser/
    ├── CommonLoadingScreen/
    ├── GameSettings/
    ├── GameplayMessageRouter/
    ├── ModularGameplayActors/
    ├── UIExtension/
    ├── PocketWorlds/
    ├── AsyncMixin/
    ├── ControlFlows/
    └── GameFeatures/       # 游戏功能插件
        ├── ShooterCore/
        ├── ShooterMaps/
        ├── ShooterExplorer/
        ├── TopDownArena/
        └── ShooterTests/
```

## LyraGame 模块目录结构

```
LyraGame/
├── AbilitySystem/          # GAS 能力系统
├── Audio/                  # 音频系统
├── Camera/                 # 相机系统
├── Character/              # 角色系统
├── Cosmetics/              # 换装系统
├── Equipment/              # 装备系统
├── Feedback/               # 反馈系统
├── GameFeatures/           # GameFeature 插件
├── GameModes/              # 游戏模式
├── Hotfix/                 # 热修复
├── Input/                  # 输入系统
├── Interaction/            # 交互系统
├── Inventory/              # 物品栏
├── Messages/               # 消息系统
├── Player/                 # 玩家管理
├── Replays/                # 回放系统
├── Settings/               # 设置系统
├── System/                 # 基础设施
├── Teams/                  # 队伍系统
├── UI/                     # UI 系统
├── Weapons/                # 武器系统
└── LyraGame.Build.cs       # 模块编译配置
```

## 核心设计概念

1. **模块化**：功能通过模块和插件划分，支持按需加载
2. **GameFeature 插件**：UE5 新增的项目架构方式，插件内容可反向引用主项目
3. **Experience 驱动**：使用 ExperienceDefinition 数据资产替代传统硬编码 GameMode
4. **消息驱动**：通过 GameplayMessageRouter 实现子系统间解耦通信
5. **可扩展性**：核心系统定义接口和基类，具体行为由插件提供实现

## 蓝图结构概要

核心框架蓝图：
- `DefaultGameData` — 硬编码加载的默认资产
- `GameInstance` — 全局状态管理，继承自 C++ 类
- Game Mode 基类 — 多模式扩展的玩法规则基类
- `Label` 资产 — 划分打包模块
- `InputConfig` — 管理增强输入映射

角色系统蓝图：
- 骨骼网格体与动画逻辑分离，通过 CurveMod 驱动动画混合
- `CatMesh` 组件 — 动态换装系统
- 堆栈式相机管理（`LyraCameraMode`），非弹簧臂实现
