# Target 文件配置

## Target 文件类型

UE 项目支持四种 Target 文件，分别对应不同的编译目标：

| Target 文件 | 编译目标 | 用途 |
|-------------|---------|------|
| `LyraGame.Target.cs` | Game | 游戏主程序 |
| `LyraEditor.Target.cs` | Editor | 编辑器模式 |
| `LyraClient.Target.cs` | Client | 纯客户端（无服务器逻辑） |
| `LyraServer.Target.cs` | Server | 专用服务器 |

## 共享配置方法

Lyra 通过 `ApplySharedLyraTargetSettings()` 方法统一管理跨 Target 的共享配置。所有 Target 文件调用此方法以减少重复。

共享配置包含：

### 编译配置

```csharp
// 阴影变量警告级别
ShadowVariableWarningLevel = WarningLevel.Error;

// 非 Shipping 崩溃报告
bUseLoggingInShipping = true;

// 仅在开发配置下生成 INI 文件
bAllowGeneratedIniWhenCooked = true;

// 仅非 Shipping 配置允许未验证证书
bDisableUnverifiedCertificates = !bHasShippingConfig;

// AssetRegistry 指针优化
UE_ASSETREGISTRY_INDIRECT_ASSETDATA_POINTERS = 1;
```

### 插件管理

通过 `ConfigureGameFeaturePlugins()` 方法声明 GameFeature 插件与编译目标的关系：

```csharp
// 禁用特定插件在服务器 Target 中
if (Target.Type == TargetRules.TargetType.Server)
{
    DisablePlugin(Target, "SomeClientPlugin");
}
```

## LyraGame.Target.cs 核心结构

```csharp
public class LyraGameTarget : TargetRules
{
    public LyraGameTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V4;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_4;
        ExtraModuleNames.AddRange(new string[] { "LyraGame", "LyraEditor" });
        
        ApplySharedLyraTargetSettings(this);
        ConfigureGameFeaturePlugins(this);
    }
}
```

## Target 文件 vs Build 文件

| | `.Target.cs` | `.Build.cs` |
|--|-------------|-------------|
| 作用域 | 编译目标级别 | 模块级别 |
| 配置内容 | 目标类型、编辑器/服务器模式、平台设置 | 模块依赖、头文件路径、库文件 |
| 典型配置 | `Type = TargetType.Game` | `PublicDependencyModuleNames` |
| 修改时机 | 新目标平台或新模块 | 新增依赖 |

## 注意事项

- 编辑器 Target（LyraEditor）不需要 `ApplySharedLyraTargetSettings`，因为编辑器有自己独立的配置路径
- 服务器 Target（LyraServer）应禁用不必要的客户端插件以减少构建体积
