# 第四章 UI 架构与登录流程

## 概述

第四章涵盖 Lyra 项目的 UI 架构和登录流程，对应课程编号 039~054。本章聚焦 Lyra 基于 CommonUI 和 CommonUser 插件构建的完整 UI 框架，包括 HUD 布局、按钮系统、对话框、会话系统、用户初始化、设置界面等子系统。

## 章节范围

| 项目 | 说明 |
|------|------|
| 课程编号 | 039 ~ 054 |
| 核心主题 | UI 架构、登录流程、游戏设置 |
| 补充来源 | 041 为 .docx 讲义（含 CommonUI 控件编辑界面截图），文本已提取至 `docs/..._041_CommonUI_主界面.txt` |
| 主要目录 | `UI/`、`UI/Foundation/`、`UI/Frontend/`、`UI/Common/`、`Plugins/CommonGame/`、`Plugins/CommonUser/`、`Plugins/GameSettings/`、`Settings/`、`GameModes/` |

## 讲义范围

| 讲义编号 | 标题 | 对应知识文件 |
|----------|------|-------------|
| 039 | CommonLoadingScreen | [01-HUD架构与布局系统](ch4/01-HUD架构与布局系统.md) |
| 040 | 登录流程 | [01-HUD架构与布局系统](ch4/01-HUD架构与布局系统.md) |
| 041 | CommonUI 主界面（.docx） | [01-HUD架构与布局系统](ch4/01-HUD架构与布局系统.md) |
| 042 | 异步推送控件的激活时机 | [01-HUD架构与布局系统](ch4/01-HUD架构与布局系统.md) |
| 043 | LyraHUDLayout | [01-HUD架构与布局系统](ch4/01-HUD架构与布局系统.md) |
| 044 | LyraButton | [02-按钮系统](ch4/02-按钮系统.md) |
| 045 | 对话框 | [03-对话框系统](ch4/03-对话框系统.md) |
| 046_AI | 关于 Shift+ESC 如何控制退出游戏 | [03-对话框系统](ch4/03-对话框系统.md) |
| 047 | 底部按钮栏 | [04-底部操作栏](ch4/04-底部操作栏.md) |
| 048 | 会话系统 | [05-会话系统](ch4/05-会话系统.md) |
| 049 | CommonUser | [06-CommonUser插件](ch4/06-CommonUser插件.md) |
| 050 | 游戏设置界面 | [08-游戏设置界面与注册器](ch4/08-游戏设置界面与注册器.md) |
| 051 | LyraTabListWidgetBase | [07-Tab列表系统](ch4/07-Tab列表系统.md) |
| 052 | GameSettingPanel | [09-设置面板列表与细节视图](ch4/09-设置面板列表与细节视图.md) |
| 053 | GameSettingListView | [09-设置面板列表与细节视图](ch4/09-设置面板列表与细节视图.md) |
| 054 | GameSettingDetailView | [09-设置面板列表与细节视图](ch4/09-设置面板列表与细节视图.md) |

## 子系统一览

| 子系统 | 核心类 | 职责 |
|--------|--------|------|
| HUD 架构 | `ULyraHUDLayout`、`UPrimaryGameLayout` | 根 HUD 控件、UI 层栈管理（Game/Menu/Modal） |
| 按钮系统 | `ULyraButtonBase`、`ULyraBoundActionButton` | 通用按钮基类、状态管理、输入法样式切换 |
| 对话框系统 | `ULyraConfirmationScreen`、`UCommonGameDialog` | 模态对话框、消息接收与显示管线 |
| 底部操作栏 | `UCommonBoundActionBar`、`UCommonBoundActionButton` | 持久操作按钮栏、UIAction 绑定显示 |
| 会话系统 | `UCommonSessionSubsystem`、`ULyraUserFacingExperienceDefinition` | 创建/查找/加入会话、QuickPlay、Beacon |
| 用户子系统 | `UCommonUserSubsystem`、`UCommonUserInfo` | 用户初始化、登录流程、权限检查 |
| Tab 列表 | `ULyraTabListWidgetBase`、`ILyraTabButtonInterface` | 标签页管理、标签导航 |
| 设置界面 | `ULyraSettingScreen`、`ULyraGameSettingRegistry` | 设置屏幕、注册器、Tab-内容联动 |
| 设置面板 | `UGameSettingPanel`、`UGameSettingListView`、`UGameSettingDetailView` | 设置列表、细节面板、过滤器状态 |

## 架构关系

```
ULyraHUDLayout (根 HUD)
  └── UPrimaryGameLayout (UI 层栈)
        ├── Game Layer (游戏内 HUD)
        ├── Menu Layer (菜单)
        └── Modal Layer (模态对话框)

UCommonUserSubsystem (用户初始化)
  └── ULyraSettingScreen (设置屏幕)
        ├── ULyraTabListWidgetBase (Tab 切换)
        ├── UGameSettingPanel (设置面板)
        │     ├── UGameSettingListView (设置列表)
        │     └── UGameSettingDetailView (细节面板)
        └── ULyraGameSettingRegistry (设置注册器)

UCommonSessionSubsystem (会话管理)
  ├── HostSession/CreateOnlineSession
  ├── FindSessions/QuickPlaySession
  └── JoinSession

ULyraConfirmationScreen (对话框)
  └── UCommonGameDialog (通用对话框基类)
```

## 关键模式

- **UPrimaryGameLayout 层栈**：将 UI 分为 Game/Menu/Modal 三层，支持各自独立的焦点和可见性管理
- **UIActionBinding**：通过 `RegisterUIActionBinding` 将输入动作绑定到 UI 控件，支持 `bDisplayInActionBar` 参数控制是否在操作栏显示
- **ControlFlow**：用于管理异步登录流程的状态机模式
- **GameFeatureAction**：用于在游戏特性激活/停用时按需执行 UI 相关的设置
- **FGameSettingFilterState**：设置过滤状态机，支持按根设置列表、禁用/隐藏开关进行过滤
- **FUserWidgetPool**：用于管理动态子控件的对象池，避免频繁创建/销毁

## 代码文件索引

### LyraGame 主模块

| 文件路径 | 关键类 |
|---------|--------|
| `UI/LyraHUDLayout.h` | `ULyraHUDLayout` |
| `UI/LyraHUD.cpp` | HUD 初始化逻辑 |
| `UI/Foundation/LyraButtonBase.h` | `ULyraButtonBase` |
| `UI/Foundation/LyraConfirmationScreen.h` | `ULyraConfirmationScreen` |
| `UI/Common/LyraBoundActionButton.h` | `ULyraBoundActionButton` |
| `UI/Common/LyraTabListWidgetBase.h` | `FLyraTabDescriptor`、`ILyraTabButtonInterface`、`ULyraTabListWidgetBase` |
| `UI/LyraSettingScreen.h` | `ULyraSettingScreen` |
| `Settings/LyraGameSettingRegistry.h` | `ULyraGameSettingRegistry` |
| `GameModes/LyraUserFacingExperienceDefinition.h` | `ULyraUserFacingExperienceDefinition` |

### CommonGame 插件

| 文件路径 | 关键类 |
|---------|--------|
| `Plugins/CommonGame/Source/Public/PrimaryGameLayout.h` | `UPrimaryGameLayout` |
| `Plugins/CommonGame/Source/Public/Messaging/CommonGameDialog.h` | `UCommonGameDialog` |

### CommonUser 插件

| 文件路径 | 关键类 |
|---------|--------|
| `Plugins/CommonUser/Source/CommonUser/Public/CommonUserSubsystem.h` | `UCommonUserSubsystem`、`UCommonUserInfo`、`FCommonUserInitializeParams` |
| `Plugins/CommonUser/Source/CommonUser/Public/CommonUserTypes.h` | `ECommonUserInitializationState`、`ECommonUserPrivilege`、`ECommonUserAvailability` |

### GameSettings 插件

| 文件路径 | 关键类 |
|---------|--------|
| `Plugins/GameSettings/Source/Public/Widgets/GameSettingPanel.h` | `UGameSettingPanel` |
| `Plugins/GameSettings/Source/Public/Widgets/GameSettingListView.h` | `UGameSettingListView` |
| `Plugins/GameSettings/Source/Public/Widgets/GameSettingDetailView.h` | `UGameSettingDetailView` |
| `Plugins/GameSettings/Source/Public/Widgets/GameSettingVisualData.h` | `UGameSettingVisualData` |
