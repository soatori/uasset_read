# GameSetting 类体系

## 概述

GameSetting 类体系定义了设置系统的核心数据结构。所有设置项（音量滑块、下拉选择、按钮动作等）都继承自 `UGameSetting` 基类，通过多态层级区分不同类型的行为。

## 完整类层级

```
UGameSetting（抽象基类）
  ├── UGameSettingCollection（设置集合容器）
  │     └── UGameSettingCollectionPage（可导航的子页面）
  ├── UGameSettingValue（可修改的值）
  │     ├── UGameSettingValueScalar（连续值滑块）
  │     │     └── UGameSettingValueScalarDynamic（动态数据源的滑块）
  │     └── UGameSettingValueDiscrete（离散值选择器）
  │           ├── UGameSettingValueDiscreteDynamic（动态离散值）
  │           │     ├── UGameSettingValueDiscreteDynamic_Bool
  │           │     ├── UGameSettingValueDiscreteDynamic_Number
  │           │     ├── UGameSettingValueDiscreteDynamic_Enum
  │           │     ├── UGameSettingValueDiscreteDynamic_Color
  │           │     └── UGameSettingValueDiscreteDynamic_Vector2D
  │           └── Lyra 自定义离散值：
  │                 ├── ULyraSettingValueDiscrete_Resolution
  │                 ├── ULyraSettingValueDiscrete_Language
  │                 ├── ULyraSettingValueDiscrete_PerfStat
  │                 ├── ULyraSettingValueDiscrete_MobileFPSType
  │                 ├── ULyraSettingValueDiscrete_OverallQuality
  │                 └── ULyraSettingValueDiscreteDynamic_AudioOutputDevice
  └── UGameSettingAction（可执行的动作按钮）
        ├── ULyraSettingAction_SafeZoneEditor（安全区编辑器）
        └── ULyraSettingKeyboardInput（按键绑定）
```

## UGameSetting 基类

- **头文件**：[GameSetting.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameSettings/Source/Public/GameSetting.h)
- **继承链**：`UObject` → `UGameSetting`

核心属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `DevName` | `FName` | 开发者标识名，用于查找 |
| `DisplayName` | `FText` | UI 显示名称 |
| `DescriptionRichText` | `FText` | 富文本描述 |
| `WarningRichText` | `FText` | 警告文本 |
| `Tags` | `FGameplayTagContainer` | 标签 |
| `DynamicDetails` | 脚本委托 | 动态详情文本 |
| `SettingParent` | `UGameSetting*` | 父设置 |
| `OwningRegistry` | `UGameSettingRegistry*` | 所属注册表 |
| `bReady` | `bool` | 是否初始化完成 |
| `EditableStateCache` | `FGameSettingEditableState` | 编辑状态缓存 |
| `EditConditions` | `TArray<FGameSettingEditCondition*>` | 编辑条件列表 |

事件委托：

| 事件 | 参数 | 说明 |
|------|------|------|
| `OnSettingChanged` | `(Setting, EGameSettingChangeReason)` | 值变化时触发 |
| `OnSettingApplied` | `(Setting)` | 值应用时触发 |
| `OnSettingEditConditionChanged` | `(Setting)` | 编辑条件变化时触发 |
| `OnNamedAction` | `(Setting, FGameplayTag)` | 命名动作触发 |

### 生命周期

```
Initialize(LocalPlayer)
  ├── 检查 DevName 非空（!UE_BUILD_SHIPPING 下 ensure）
  ├── Initialize 子 Setting（集合类型递归）
  └── Startup()
        ├── StartupComplete()
        └── OnInitialized()
              └── ComputeEditableState()
```

`UGameSettingValueScalarDynamic` 的重写：

```
Startup()
  └── Getter->Startup(LocalPlayer, OnDataSourcesReady)
        └── OnDataSourcesReady()
              └─ Setter->Startup(LocalPlayer, nullptr)
              └─ StartupComplete()
```

### 编辑状态

`ComputeEditableState()` 计算当前设置的编辑状态：

```
ComputeEditableState()
  └── 创建新的 FGameSettingEditableState
        ├── 遍历所有 EditConditions → GatherEditState(EditableState)
        └── 缓存到 EditableStateCache
```

## UGameSettingCollection

- **头文件**：[GameSettingCollection.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameSettings/Source/Public/GameSettingCollection.h)
- **职责**：容纳子设置的容器，实现设置层级结构

| 方法 | 说明 |
|------|------|
| `AddSetting(Setting)` | 添加子设置 |
| `GetSettingsForFilter(FilterState)` | 按过滤条件获取可见子设置 |

### UGameSettingCollectionPage

`IsSelectable=true`，可独立导航到子设置页面。通过 `NavigationText` 定义导航文本，`OnExecuteNavigationEvent` 处理导航操作。

## UGameSettingValue

- **头文件**：[GameSettingValue.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameSettings/Source/Public/GameSettingValue.h)
- **纯虚方法**：

| 方法 | 说明 |
|------|------|
| `StoreInitial()` | 在 Startup 后存储初始值 |
| `ResetToDefault()` | 重置为默认值 |
| `RestoreToInitial()` | 恢复为初始值 |

### UGameSettingValueScalar

- **头文件**：[GameSettingValueScalar.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameSettings/Source/Public/GameSettingValueScalar.h)
- 范围滑块值，通过 `SetValueNormalized(n)` / `GetValueNormalized()` 读写归一化值
- `SourceRange` / `SourceStep` 定义原始值范围和步进

### UGameSettingValueScalarDynamic

- **头文件**：[GameSettingValueScalarDynamic.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameSettings/Source/Public/GameSettingValueScalarDynamic.h)
- 通过动态数据源（Getter/Setter `FGameSettingDataSource`）读写值
- 自定义 `DisplayFormat` lambda 控制显示格式
- `SetDefaultValue(Value)` 设置默认值
- 异步 `Startup`：Getter → OnDataSourcesReady → Setter → StartupComplete

### UGameSettingValueDiscrete

- **头文件**：[GameSettingValueDiscrete.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameSettings/Source/Public/GameSettingValueDiscrete.h)
- 离散值选择器（下拉/单选按钮）

| 方法 | 说明 |
|------|------|
| `SetDiscreteOptionByIndex(Index)` | 按索引设置选项 |
| `GetDiscreteOptions()` | 获取所有选项文本 |
| `GetDiscreteOptionDefaultIndex()` | 获取默认选项索引 |

## UGameSettingAction

- **头文件**：[GameSettingAction.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameSettings/Source/Public/GameSettingAction.h)
- 可执行的按钮动作

| 属性 | 说明 |
|------|------|
| `ActionText` | 按钮文本 |
| `NamedAction` / `CustomAction` | 动作回调（命名动作通过 FGameplayTag 触发） |

## 过滤状态

### FGameSettingFilterState

- **头文件**：[GameSettingFilterState.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameSettings/Source/Public/GameSettingFilterState.h)

| 属性 | 默认值 | 说明 |
|------|--------|------|
| `bIncludeDisabled` | `true` | 是否包含被禁用的设置 |
| `bIncludeHidden` | `false` | 是否包含被隐藏的设置 |
| `bIncludeResetable` | `true` | 是否包含可重置的设置 |
| `bIncludeNestedPages` | `false` | 是否包含嵌套页面 |
| `SearchText` | 空 | 搜索文本 |
| `SettingRootList` | 空 | 根设置列表白名单 |
| `SettingAllowList` | 空 | 设置白名单 |

`DoesSettingPassFilter(Setting)` 依次检查：可见性 → 启用态 → 可重置 → 允许列表 → 搜索文本匹配。

## 编辑状态

### FGameSettingEditableState

- **头文件**：[GameSettingFilterState.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameSettings/Source/Public/GameSettingFilterState.h)

| 属性 | 默认值 | 说明 |
|------|--------|------|
| `bVisible` | `true` | 是否可见 |
| `bEnabled` | `true` | 是否可交互 |
| `bResetable` | `true` | 是否可重置 |
| `bHideFromAnalytics` | `false` | 是否从分析中隐藏 |

方法：

| 方法 | 说明 |
|------|------|
| `Hide(DevReason)` | 隐藏（附带开发者理由） |
| `Disable(Reason)` | 禁用 |
| `DisableOption(Option)` | 禁用特定选项 |
| `UnableToReset()` | 不可重置 |
| `HideFromAnalytics()` | 从分析中隐藏 |
| `Kill(DevReason)` | 同时 Hide + HideFromAnalytics + UnableToReset |

## 编辑条件

### FGameSettingEditCondition（基类）

- **头文件**：[GameSettingFilterState.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameSettings/Source/Public/GameSettingFilterState.h)

| 虚方法 | 说明 |
|--------|------|
| `Initialize(Setting)` | 初始化，可绑定事件 |
| `GatherEditState(EditableState)` | 收集编辑状态 |
| `SettingApplied(Setting)` | 设置被应用时回调 |
| `SettingChanged(Value, ChangeReason)` | 设置变化时回调 |

### 内置编辑条件

| 类 | 说明 |
|----|------|
| `FWhenCondition` | 通过 lambda 判断条件 |
| `FWhenPlatformHasTrait` | 按平台特性 GameplayTag 控制 |
| `FWhenPlayingAsPrimaryPlayer` | 仅主玩家可用（单例） |

#### FWhenPlatformHasTrait

- **头文件**：[WhenPlatformHasTrait.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameSettings/Source/Public/EditCondition/WhenPlatformHasTrait.h)

工厂方法（全部静态）：

| 方法 | 行为 |
|------|------|
| `KillIfMissing(Tag)` | 标签不存在时 Kill |
| `DisableIfMissing(Tag)` | 标签不存在时 Disable |
| `KillIfPresent(Tag)` | 标签存在时 Kill |
| `DisableIfPresent(Tag)` | 标签存在时 Disable |

### 编辑依赖

通过 `AddEditDependency(Setting)` 建立跨设置联动。当依赖设置的 EditableState 变化时，自动触发本设置的 EditableState 重算。

## Lyra 自定义类型

### ULyraSettingValueDiscrete_Resolution

- **头文件**：[LyraSettingValueDiscrete_Resolution.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Settings/CustomSettings/LyraSettingValueDiscrete_Resolution.h)
- 从 `ULyraSettingsLocal` 获取可用分辨率列表
- 依赖 WindowMode 设置（全屏模式才可切换分辨率）

### ULyraSettingValueDiscrete_Language

- **头文件**：[LyraSettingValueDiscrete_Language.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Settings/CustomSettings/LyraSettingValueDiscrete_Language.h)
- 通过 `FTextLocalizationManager` 获取可用语言列表
- 使用 `ULyraSettingsShared::SetPendingCulture` 暂存语言变更

### ULyraSettingValueDiscrete_PerfStat

- **头文件**：[LyraSettingValueDiscrete_PerfStat.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Settings/CustomSettings/LyraSettingValueDiscrete_PerfStat.h)
- 4 种显示模式：Hidden / TextOnly / GraphOnly / TextAndGraph

### ULyraSettingAction_SafeZoneEditor

- **头文件**：[LyraSettingAction_SafeZoneEditor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Settings/CustomSettings/LyraSettingAction_SafeZoneEditor.h)
- 导航到安全区编辑器界面
- 内嵌 `ULyraSettingValueScalarDynamic_SafeZoneValue` 子设置

### ULyraSettingKeyboardInput

- **头文件**：[LyraSettingKeyboardInput.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Settings/CustomSettings/LyraSettingKeyboardInput.h)
- 按键绑定设置，与 Enhanced Input 的 `UEnhancedPlayerMappableKeyProfile` 集成
