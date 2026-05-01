# Tab 列表系统

## 概述

Tab 列表系统（`ULyraTabListWidgetBase`）是 Lyra UI 中用于管理标签页切换的组件。它基于 `UCommonTabListWidgetBase` 扩展，提供标签注册、内容创建和导航功能。

## 核心类

### FLyraTabDescriptor

- **头文件**：[LyraTabListWidgetBase.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/UI/Common/LyraTabListWidgetBase.h)
- **职责**：标签描述符结构

| 字段 | 类型 | 说明 |
|------|------|------|
| TabId | FName | 标签唯一标识 |
| TabText | FText | 标签显示文本 |
| IconBrush | FSlateBrush | 标签图标 |
| bHidden | bool | 是否隐藏（隐藏的标签不注册） |
| TabButtonType | TSubclassOf<UCommonButtonBase> | 标签按钮控件类 |
| TabContentType | TSubclassOf<UCommonUserWidget> | 标签内容控件类 |
| CreatedTabContentWidget | UWidget* | 已创建的内容控件实例（缓存） |

### ILyraTabButtonInterface

- **头文件**：同上
- **职责**：标签按钮接口，定义 `SetTabLabelInfo(FLyraTabDescriptor)` 方法
- **实现类**：通过 `ULyraTabButtonInterface`（UInterface）暴露给蓝图

### ULyraTabListWidgetBase

- **头文件**：同上
- **继承链**：`UCommonTabListWidgetBase` → `ULyraTabListWidgetBase`
- **职责**：标签列表 Widget 基类

## 标签注册流程

```
RegisterDynamicTab(FLyraTabDescriptor)
  ├── 检查 bHidden → 隐藏的直接返回 true（跳过注册）
  ├── 存入 PendingTabLabelInfoMap.Add(TabId, TabDescriptor)
  └── 调用 RegisterTab(TabId, TabButtonType, CreatedTabContentWidget) [基类]
        └── HandleTabCreation_Implementation(FName TabId, UCommonButtonBase* TabButton)
              ├── 查找 FLyraTabDescriptor:
              │     1. PreregisteredTabInfoArray（预注册标签）
              │     2. PendingTabLabelInfoMap（动态注册标签）
              └── 如果 TabButton 实现 ILyraTabButtonInterface:
                    Execute_SetTabLabelInfo(TabButton, *TabInfoPtr)
                    → PendingTabLabelInfoMap.Remove(TabId)
```

## 标签导航

### 自动监听输入

- 设置 `bAutoListenForInput = true`
- 内部调用 `SetListeningForInput` → `UpdateBindings`
- 注册 NextTab/PreviousTab 的 UIActionBinding

### 导航逻辑

```
SelectNextButton() / SelectPreviousButton():
  └── 递归 lambda: 跳过禁用的按钮，支持 bAllowWrap 循环

SelectButtonAtIndex(ButtonIndex):
  └── ButtonToSelect->SetSelectedInternal(true)
        └── NativeOnSelected
              ├── BP_OnSelected (蓝图事件)
              └── OnSelectedChangedBase.Broadcast (广播)
```

## 相关文件

- [LyraTabListWidgetBase.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/UI/Common/LyraTabListWidgetBase.h)
