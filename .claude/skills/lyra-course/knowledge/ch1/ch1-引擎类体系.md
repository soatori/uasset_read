# 引擎类体系

## 引擎类继承关系

```
UEngine (基类)
├─ UGameEngine (游戏运行时引擎)
└─ UEditorEngine (通用编辑器引擎基类)
   └─ UUnrealEdEngine (虚幻专用编辑器引擎)
```

引擎类位置：`Engine/Source/Runtime/Engine/Classes/Engine/Engine.h`

## 引擎类区别

| 特性 | UGameEngine | UEditorEngine (基类) | UUnrealEdEngine (子类) |
|------|-------------|---------------------|----------------------|
| 用途 | 纯游戏运行 | 编辑器基础框架 | 虚幻编辑器完整实现 |
| 模块依赖 | 仅核心游戏模块 | 基础编辑器工具 | 全部编辑器工具链 |
| 运行场景 | 打包后的游戏 | 自定义编辑器工具开发 | Unreal Editor |
| 是否支持 PIE | 否 | 是（通过派生类实现） | 是（完整 PIE/SIE 支持） |

## Lyra 的引擎类配置

Lyra 在 `DefaultEngine.ini` 的 `[/Script/Engine.Engine]` 段替换了 7 个核心引擎类：

```ini
[/Script/Engine.Engine]
GameEngine=/Script/LyraGame.LyraGameEngine
UnrealEdEngine=/Script/LyraEditor.LyraEditorEngine
EditorEngine=/Script/LyraEditor.LyraEditorEngine
GameViewportClientClassName=/Script/LyraGame.LyraGameViewportClient
AssetManagerClassName=/Script/LyraGame.LyraAssetManager
WorldSettingsClassName=/Script/LyraGame.LyraWorldSettings
LocalPlayerClassName=/Script/LyraGame.LyraLocalPlayer
GameUserSettingsClassName=/Script/LyraGame.LyraSettingsLocal
```

## UEngine 的可配置类

UEngine 通过 `FSoftClassPath` 属性暴露可替换的类：

| 属性 | 类型 | 说明 |
|------|------|------|
| `GameViewportClientClassName` | `FSoftClassPath` | 游戏视口客户端类 |
| `AssetManagerClassName` | `FSoftClassPath` | 全局 AssetManager 类 |
| `WorldSettingsClassName` | `FSoftClassPath` | WorldSettings 类 |
| `LocalPlayerClassName` | `FSoftClassPath` | 本地玩家类 |
| `GameUserSettingsClassName` | `FSoftClassPath` | 游戏用户设置类 |

## 引擎加载时机

引擎初始化发生在极早期（`main()` 之前），核心代码位于 `LaunchEngineLoop.cpp`（约 4530 行）。

关键流程：

```cpp
if (!GIsEditor) {
    // 游戏模式：加载 GameEngine
    GConfig->GetString(TEXT("/Script/Engine.Engine"), TEXT("GameEngine"), 
        GameEngineClassName, GEngineIni);
    EngineClass = StaticLoadClass(UGameEngine::StaticClass(), nullptr, *GameEngineClassName);
    GEngine = NewObject<UEngine>(GetTransientPackage(), EngineClass);
} else {
    // 编辑器模式：加载 UnrealEdEngine
    GConfig->GetString(TEXT("/Script/Engine.Engine"), TEXT("UnrealEdEngine"), 
        UnrealEdEngineClassName, GEngineIni);
    EngineClass = StaticLoadClass(UUnrealEdEngine::StaticClass(), nullptr, *UnrealEdEngineClassName);
    GEngine = GEditor = GUnrealEd = NewObject<UUnrealEdEngine>(GetTransientPackage(), EngineClass);
}
```

### 配置来源优先级

| 配置文件 | 说明 |
|---------|------|
| `BaseEngine.ini` | 引擎默认配置（不可修改） |
| `DefaultEngine.ini` | 项目级配置（覆盖基类配置） |
| 平台特定 INI | 如 Windows/Android 目录下的配置 |
| `Saved/Config/...` | 用户运行时覆盖配置 |

## 验证当前引擎类

方法一 — 控制台命令：
```
obj list class=Engine
```

方法二 — 代码调试：
在 `UGameEngine::Init()` 或 `UUnrealEdEngine::Init()` 设置断点。

## Lyra 自定义引擎接口

| 类名 | 所在文件 | 继承自 |
|------|---------|--------|
| [ULyraGameEngine](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraGameEngine.h) | `LyraGame/System/LyraGameEngine.h` | `UGameEngine` |
| [ULyraEditorEngine](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraEditor/LyraEditorEngine.h) | `LyraEditor/LyraEditorEngine.h` | `UUnrealEdEngine` |
| [ULyraGameViewportClient](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/UI/LyraGameViewportClient.h) | `LyraGame/UI/LyraGameViewportClient.h` | `UCommonGameViewportClient` |
| [ULyraAssetManager](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraAssetManager.h) | `LyraGame/System/LyraAssetManager.h` | `UAssetManager` |
| [ALyraWorldSettings](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraWorldSettings.h) | `LyraGame/GameModes/LyraWorldSettings.h` | `AWorldSettings` |
| [ULyraLocalPlayer](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Player/LyraLocalPlayer.h) | `LyraGame/Player/LyraLocalPlayer.h` | `UCommonLocalPlayer` |
| [ULyraSettingsLocal](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Settings/LyraSettingsLocal.h) | `LyraGame/Settings/LyraSettingsLocal.h` | `UGameUserSettings` |
