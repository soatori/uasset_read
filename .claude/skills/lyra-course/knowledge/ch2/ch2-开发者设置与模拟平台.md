# 开发者设置与模拟平台

## UDeveloperSettings

UE 的 `UDeveloperSettings` 是引擎级的配置类体系，用于在 `Project Settings` 编辑器中呈现可配置项。

### 使用方式

```cpp
UCLASS(Config="Game", DefaultConfig)
class ULyraSomeSettings : public UDeveloperSettings
{
    GENERATED_BODY()

public:
    UPROPERTY(Config, EditDefaultsOnly, Category = "Settings")
    bool bSomeFlag;
};
```

### 在 Lyra 中的例子

`ULyraAudioSettings` 继承自 `UDeveloperSettings`，提供音频配置的可视化编辑：

- `DefaultSoundClass` — 默认声音类
- `DefaultSoundConcurrencyName` — 默认声音并发机制
- `DefaultBaseSoundMix` — 基础音效混音方案
- `MasterSubmix` — 主输出子混音

## 模拟平台设置

Lyra 支持通过编辑器工具模拟不同平台的行为，用于开发阶段的平台行为验证：

### 模拟范围

| 设置项 | 说明 |
|--------|------|
| 平台输入 | 模拟目标平台的输入映射 |
| 平台性能 | 模拟目标平台的性能限制 |
| 平台分辨率 | 模拟目标平台的屏幕分辨率 |
| 平台存储 | 模拟目标平台的文件系统 |

### 实现方式

基于 `UGameInstanceSubsystem` 或编辑器工具，在开发者设置中添加平台模拟选项。当启用模拟时：

1. 重写 `UGameInstanceSubsystem` 中的平台检测方法
2. 替换平台特定的输入/显示设置在开发环境中
3. 在编辑器中添加切换界面

## ULyraUserFacingExperienceDefinition

[ULyraUserFacingExperienceDefinition](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraUserFacingExperienceDefinition.h) 继承自 `UPrimaryDataAsset`，用于前端 UI 中展示可选的游戏模式。

### 定义

```cpp
UCLASS()
class ULyraUserFacingExperienceDefinition : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    // 显示名称（UI 中展示）
    UPROPERTY(EditDefaultsOnly, Category = Display)
    FText DisplayName;

    // 描述文本
    UPROPERTY(EditDefaultsOnly, Category = Display)
    FText Description;

    // 关联的 Experience
    UPROPERTY(EditDefaultsOnly, Category = Gameplay)
    TSoftObjectPtr<ULyraExperienceDefinition> Experience;

    // 关联的地图
    UPROPERTY(EditDefaultsOnly, Category = Gameplay)
    TSoftObjectPtr<UWorld> Map;

    // 额外参数
    UPROPERTY(EditDefaultsOnly, Category = Gameplay)
    TMap<FString, FString> ExtraOptions;
};
```

### 用途

- 在主菜单 UI 中列出可选游戏模式（控制、淘汰等）
- 提供 Experience + 地图 + 参数的组合
- 用户选择后通过 `UGameInstance` 的 `TryLoadExperience()` 触发加载
