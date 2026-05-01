# GameSettingRegistry 体系

## 概述

`ULyraGameSettingRegistry` 是设置系统的中心注册表，它继承自 `UGameSettingRegistry`（GameSettings 插件），负责创建和管理所有游戏设置项。注册表由 `ULyraSettingScreen` 创建并持有，是设置界面与底层数据之间的桥梁。

## 核心类

### UGameSettingRegistry（基类）

- **头文件**：[GameSettingRegistry.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameSettings/Source/Public/GameSettingRegistry.h)
- **职责**：设置注册表基类，管理设置的注册、过滤和事件分发

核心成员：

| 成员 | 类型 | 说明 |
|------|------|------|
| `TopLevelSettings` | `TArray<UGameSetting*>` | 顶层设置集合，通过 `RegisterSetting` 添加 |
| `RegisteredSettings` | `TArray<UGameSetting*>` | 所有已注册设置的扁平列表 |
| `OwningLocalPlayer` | `ULocalPlayer*` | 所属本地玩家 |
| `OnSettingChangedEvent` | 多播委托 | 设置值变化时触发，参数：(Setting, ChangeReason) |
| `OnSettingEditConditionChangedEvent` | 多播委托 | 编辑条件变化时触发 |
| `OnSettingNamedActionEvent` | 多播委托 | 命名动作触发时回调 |
| `OnExecuteNavigationEvent` | 多播委托 | 导航到子设置页面时触发 |

生命周期方法：

| 方法 | 说明 |
|------|------|
| `Initialize(LocalPlayer)` | 入口：设置 OwningLocalPlayer → 调用 `OnInitialize` |
| `OnInitialize(LocalPlayer)` | 纯虚函数，子类实现具体设置注册 |
| `Regenerate()` | 重新生成所有设置 |
| `SaveChanges()` | 保存所有设置变更 |
| `GetSettingsForFilter(FilterState)` | 按过滤条件获取设置列表 |
| `FindSettingByDevName(DevName)` | 按开发者名称查找设置 |

### ULyraGameSettingRegistry（具体实现）

- **头文件**：[LyraGameSettingRegistry.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Settings/LyraGameSettingRegistry.h)
- **实现文件**：[LyraGameSettingRegistry.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Settings/LyraGameSettingRegistry.cpp)
- **附加实现**：`LyraGameSettingRegistry_Audio.cpp`、`_Gamepad.cpp`、`_Gameplay.cpp`、`_MouseAndKeyboard.cpp`、`_PerfStats.cpp`、`_Video.cpp`
- **继承链**：`UObject` → `UGameSettingRegistry` → `ULyraGameSettingRegistry`

## OnInitialize 流程

```
ULyraGameSettingRegistry::OnInitialize(LocalPlayer)
  │
  ├── VideoSettings = InitializeVideoSettings(LyraLocalPlayer)
  │     ├── InitializeVideoSettings_FrameRates(VideoSettings, LyraLocalPlayer)
  │     └── RegisterSetting(VideoSettings)
  │
  ├── AudioSettings = InitializeAudioSettings(LyraLocalPlayer)
  │     └── RegisterSetting(AudioSettings)
  │
  ├── GameplaySettings = InitializeGameplaySettings(LyraLocalPlayer)
  │     └── RegisterSetting(GameplaySettings)
  │
  ├── MouseAndKeyboardSettings = InitializeMouseAndKeyboardSettings(LyraLocalPlayer)
  │     └── RegisterSetting(MouseAndKeyboardSettings)
  │
  └── GamepadSettings = InitializeGamepadSettings(LyraLocalPlayer)
        └── RegisterSetting(GamepadSettings)
```

每个 `Initialize*Settings` 函数创建并返回一个 `UGameSettingCollection`，内部包含设置集合的层级结构。

## 注册流程

```
UGameSettingRegistry::RegisterSetting(InSetting)
  ├── TopLevelSettings.Add(InSetting)           // 添加到顶层列表
  ├── InSetting->SetRegistry(this)              // 指定归属注册表
  └── RegisterInnerSettings(InSetting)          // 递归注册
        ├── RegisteredSettings.Add(InSetting)   // 添加到扁平列表
        ├── 绑定事件：
        │     ├── OnSettingChanged → HandleSettingChanged
        │     ├── OnSettingApplied → HandleSettingApplied
        │     ├── OnSettingEditConditionChanged → HandleSettingEditConditionsChanged
        │     ├── OnSettingNamedAction → HandleSettingNamedAction
        │     └── OnExecuteNavigation → HandleSettingNavigation
        └── 如果是 UGameSettingCollection：
              └── 对每个子 Setting 递归调用 RegisterInnerSettings
```

## 数据源宏

用于将设置控件与 `ULyraSettingsLocal` 或 `ULyraSettingsShared` 的属性绑定：

```cpp
// 本地设置数据源：ULyraLocalPlayer → GetLocalSettings() → Property
#define GET_LOCAL_SETTINGS_FUNCTION_PATH(FunctionOrPropertyName) \
    MakeShared<FGameSettingDataSourceDynamic>(TArray<FString>({ \
        GET_FUNCTION_NAME_STRING_CHECKED(ULyraLocalPlayer, GetLocalSettings), \
        GET_FUNCTION_NAME_STRING_CHECKED(ULyraSettingsLocal, FunctionOrPropertyName) \
    }))

// 共享设置数据源：ULyraLocalPlayer → GetSharedSettings() → Property
#define GET_SHARED_SETTINGS_FUNCTION_PATH(FunctionOrPropertyName) \
    MakeShared<FGameSettingDataSourceDynamic>(TArray<FString>({ \
        GET_FUNCTION_NAME_STRING_CHECKED(ULyraLocalPlayer, GetSharedSettings), \
        GET_FUNCTION_NAME_STRING_CHECKED(ULyraSettingsShared, FunctionOrPropertyName) \
    }))
```

### GET_FUNCTION_NAME_STRING_CHECKED

- **头文件**：`LyraGameSettingRegistry.h`
- **实现**：`((void)sizeof(&ClassName::FunctionName), TEXT(#FunctionName))`

利用 `sizeof(&ClassName::FunctionName)` 在编译期检测函数是否存在。如果函数不存在，编译器报错。逗号运算符确保值为右侧的 `TEXT(#FunctionName)` 字符串。零运行时开销。

### FGameSettingDataSourceDynamic

- **头文件**：[GameSettingDataSourceDynamic.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameSettings/Source/Public/DataSource/GameSettingDataSourceDynamic.h)

接收属性路径字符串数组，内部使用 `FCachedPropertyPath` 进行属性解析。支持以下属性类型：
- `FObjectProperty` / `UObjectProperty`：对象/弱对象引用
- `FStructProperty`：结构体
- `FArrayProperty`：数组

## GC 生命周期

```
// 从 LocalPlayer 中查找已存在的注册表
ULyraGameSettingRegistry* Registry = FindObject<ULyraGameSettingRegistry>(
    InLocalPlayer, TEXT("LyraGameSettingRegistry"), true);

// 不存在则创建
if (Registry == nullptr)
{
    // Outer = InLocalPlayer — 但 Outer 不能防止 GC
    Registry = NewObject<ULyraGameSettingRegistry>(InLocalPlayer,
        TEXT("LyraGameSettingRegistry"));
    Registry->Initialize(InLocalPlayer);
}

// 实际由 ULyraSettingScreen::CreateRegistry() 持有
UGameSettingRegistry* ULyraSettingScreen::CreateRegistry()
{
    // 注意：Outer 为 nullptr，由成员变量 Registry 持有
    ULyraGameSettingRegistry* NewRegistry = NewObject<ULyraGameSettingRegistry>();
    NewRegistry->Initialize(LocalPlayer);
    return NewRegistry;
}
```

Outer 不能防止 GC。注册表必须被一个 `UPROPERTY()` 成员（如 `ULyraSettingScreen::Registry`）持有才能避免被回收。

## IsFinishedInitializing

`ULyraGameSettingRegistry::IsFinishedInitializing()` 在基类检查之外，额外等待共享设置（`ULyraSettingsShared`）异步加载完成：

```cpp
bool ULyraGameSettingRegistry::IsFinishedInitializing() const
{
    if (Super::IsFinishedInitializing())
    {
        if (ULyraLocalPlayer* LocalPlayer = Cast<ULyraLocalPlayer>(OwningLocalPlayer))
        {
            if (LocalPlayer->GetSharedSettings() == nullptr)
                return false;
        }
        return true;
    }
    return false;
}
```

## 数据流

```
用户操作 UI → 设置值变更
  → OnSettingChanged(Setting, ChangeReason)
    → MarkDirty + Registry 记录变更
      → SaveChanges()
        → 调用各 Setting 的 Apply()
          → ULyraSettingsLocal::ApplySettings()
          → ULyraSettingsShared::SaveSettings()
            → Config 持久化 / 存档持久化
```
