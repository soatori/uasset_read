# 工程搭建流程

## 核心步骤

1. 创建 UE5.6 空白 C++ 项目
2. 拆分单模块为 LyraGame（运行时）+ LyraEditor（编辑器）双模块
3. 配置 `.uproject` 文件声明模块和插件
4. 配置 `.Target.cs` 文件声明编译目标
5. 配置 `.Build.cs` 文件声明模块依赖
6. 复制 Lyra 示例工程的 Content 资产
7. 完成项目设置（碰撞配置、音频设置等）

## 模块拆分

从单模块拆分为运行时 + 编辑器模块：

| 方面 | LyraGame（运行时） | LyraEditor（编辑器） |
|------|-------------------|-------------------|
| LoadingPhase | Default | Default |
| Type | Runtime | Editor |
| 依赖 | 运行时模块 | LyraGame + 编辑器模块 |

## `.uproject` 配置

`Lyra.uproject` 的核心结构：

```json
{
  "FileVersion": 3,
  "EngineAssociation": "5.6",
  "Category": "",
  "Description": "",
  "Modules": [
    {
      "Name": "LyraGame",
      "Type": "Runtime",
      "LoadingPhase": "Default"
    },
    {
      "Name": "LyraEditor",
      "Type": "Editor",
      "LoadingPhase": "Default"
    }
  ],
  "Plugins": [
    { "Name": "CommonGame", "Enabled": true },
    { "Name": "CommonUser", "Enabled": true },
    { "Name": "CommonLoadingScreen", "Enabled": true },
    { "Name": "GameSettings", "Enabled": true },
    { "Name": "GameplayMessageRouter", "Enabled": true },
    { "Name": "ModularGameplayActors", "Enabled": true },
    { "Name": "UIExtension", "Enabled": true },
    { "Name": "PocketWorlds", "Enabled": true },
    { "Name": "AsyncMixin", "Enabled": true },
    { "Name": "ControlFlows", "Enabled": true },
    { "Name": "ShooterCore", "Enabled": true },
    { "Name": "ShooterMaps", "Enabled": true },
    { "Name": "TopDownArena", "Enabled": true },
    { "Name": "ShooterExplorer", "Enabled": true },
    { "Name": "ShooterTests", "Enabled": true },
    { "Name": "OpenImageDenoise", "Enabled": false }
  ]
}
```

## LyraGame.Build.cs 核心依赖

```csharp
PublicDependencyModuleNames.AddRange(new string[] {
    "Core", "CoreUObject", "CoreOnline", "ApplicationCore",
    "Engine", "PhysicsCore",
    "GameplayTags", "GameplayTasks", "GameplayAbilities",
    "AIModule",
    "ModularGameplay", "ModularGameplayActors",
    "DataRegistry", "ReplicationGraph", "GameFeatures",
    "Niagara",
    "CommonLoadingScreen", "AsyncMixin", "ControlFlows"
});

PrivateDependencyModuleNames.AddRange(new string[] {
    "InputCore", "Slate", "SlateCore",
    "EnhancedInput",
    "UMG", "CommonUI", "CommonInput",
    "CommonGame", "CommonUser",
    "GameplayMessageRuntime",
    "AudioMixer", "NetworkReplayStreaming",
    "UIExtension", "AudioModulation",
    "DTLSHandlerComponent", "Json"
});
```

## LyraEditor.Build.cs 核心依赖

```csharp
PublicDependencyModuleNames.AddRange(new string[] {
    "Core", "CoreUObject", "Engine", "EditorFramework", "UnrealEd",
    "GameplayTagsEditor", "GameplayTasksEditor",
    "GameplayAbilities", "GameplayAbilitiesEditor",
    "StudioTelemetry",
    "LyraGame"
});

PrivateDependencyModuleNames.AddRange(new string[] {
    "InputCore", "Slate", "SlateCore", "ToolMenus",
    "EditorStyle", "DataValidation", "MessageLog",
    "Projects", "DeveloperToolSettings",
    "CollectionManager", "SourceControl", "Chaos"
});
```

## 编译选项

- `WITH_RPC_REGISTRY` — 用于 RPC 注册表
- `SHIPPING_DRAW_DEBUG_ERROR` — 在 Shipping 配置下将 DrawDebug 视为错误
- `SetupGameplayDebuggerSupport()` — 启用 GameplayDebugger 支持
- `SetupIrisSupport()` — 启用 Iris 网络复制框架
