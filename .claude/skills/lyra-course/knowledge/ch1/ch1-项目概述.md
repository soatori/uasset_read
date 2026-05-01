# 项目概述

## Lyra 是什么

Lyra 是 Epic Games 开发的一个模块化游戏示例项目，随 UE5 版本更新。它的目的不是提供一个完整的游戏，而是为开发者展示 UE5 中多种系统的整合方式，可以作为快速开发特定类型游戏的起点。

Lyra 采用模块化架构，核心系统与 Gameplay 功能插件分离，不同游戏模式通过插件实现。

## 功能特点

- 模块化架构，包含核心系统和插件，定期随 UE5 更新
- 跨平台兼容性和可扩展性，支持多人游戏和跨平台功能
- 三种游戏模式：淘汰赛（Elimination）、控制点占领（Control）、爆炸器派对游戏（Exploder）
- 自定义 Gameplay 技能系统（GAS）
- Niagara 粒子特效
- UMG 控件内核 UI
- 手工制作内容：移动动画、资产、声音、武器系统等

## 游戏模式与地图

| 游戏模式 | 说明 | 地图路径 |
|----------|------|---------|
| 控制（Control） | 和队友一起保护控制点以提高得分 | /ShooterMaps/Maps/L_Convolution_Blockout |
| 淘汰（Elimination） | 团队竞赛，消灭敌人获得足够分数 | /ShooterMaps/Maps/L_Expanse |
| 前端（Front End） | 主菜单界面 | /Game/System/FrontEnd/Maps/L_LyraFrontEnd |
| 默认地图 | 测试 ShooterCore 插件功能的测试关卡 | /Game/System/DefaultEditorMap/L_DefaultEditorOverview |
| 射击训练场 | 射击测试 | /ShooterCore/Maps/L_ShooterGym |
| 爆炸器 | 俯视角派对游戏 | /TopDownArena/Maps/L_TopDownArenaGym |

## 核心系统与插件

Lyra 的 Gameplay 功能插件体系：

| 插件 | 说明 |
|------|------|
| Lyra Example Content | 共享材质、网格体等基础资产 |
| Shooter Core Content | 射击游戏核心元素：Gameplay 逻辑、Gameplay 能力、AI、武器、UI |
| ShooterMaps Content | 射击游戏地图（广阔区域、盘旋） |
| TopDownArena Content | 俯视角派对游戏内容 |

Experience（体验）系统替代传统 GameMode，通过 `ULyraExperienceDefinition` 数据资产动态加载玩法模块。每个游戏模式独立派生自同一核心基类，仅调整获胜条件和积分方式。

## 下载与安装

1. 通过 Epic 商城搜索 "Lyra"，找到 "Lyra Starter Game"
2. 添加到我的库，通过 Epic 启动程序下载
3. 安装兼容的引擎版本（如 5.6.0），勾选调试符号
4. 创建工程并命名为 "Lyra"
