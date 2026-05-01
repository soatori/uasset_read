# HUD 架构与布局系统

## 概述

Lyra 的 HUD 系统基于 CommonUI 插件的 `UPrimaryGameLayout` 构建，采用层栈（Layer Stack）架构管理不同优先级和用途的 UI 内容。HUD 本身不继承传统的 `AHUD`，而是完全基于 Widget 体系。

## 核心类

### ULyraHUDLayout

- **头文件**：[LyraHUDLayout.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/UI/LyraHUDLayout.h)
- **继承链**：`UCommonActivatableWidget` → `ULyraActivatableWidget` → `ULyraHUDLayout`
- **职责**：作为根 HUD Widget，管理所有 HUD 级别的子 Widget

### UPrimaryGameLayout

- **头文件**：[PrimaryGameLayout.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/CommonGame/Source/Public/PrimaryGameLayout.h)
- **继承链**：`UCommonUserWidget` → `UPrimaryGameLayout`
- **职责**：UI 层栈容器，管理不同层的 Widget 堆叠

## 架构设计

```
ULyraHUDLayout
  └── UPrimaryGameLayout
        ├── Game Layer (0)     — 游戏内 HUD 元素
        ├── Game Menu Layer (1) — 游戏内菜单
        ├── Menu Layer (2)     — 主菜单 UI
        └── Modal Layer (3)    — 模态对话框
```

### 层栈管理

- 每层独立管理 Widget 堆栈
- 上层自动获得焦点优先级
- PushContentToLayer 用于将 Widget 推入指定层
- 支持异步加载（通过 `UAsyncAction_PushContentToLayerForPlayer`）

### HUD 初始化流程

1. `ULyraHUDLayout` 作为根 HUD Widget 被创建
2. 内部持有 `UPrimaryGameLayout` 作为层栈容器
3. 各功能模块通过 `GameFeatureAction` 在特性激活时向对应层添加 Widget

## 关键 API

- `PushContentToLayerForPlayer`：将指定 Widget 推入目标层
- `FindWidgetInLayer`：在指定层中查找已存在的 Widget
- `RemoveWidgetFromLayer`：从层中移除 Widget

## 相关文件

- [LyraHUDLayout.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/UI/LyraHUDLayout.h)
- [LyraHUD.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/UI/LyraHUD.cpp)
- [PrimaryGameLayout.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/CommonGame/Source/Public/PrimaryGameLayout.h)
