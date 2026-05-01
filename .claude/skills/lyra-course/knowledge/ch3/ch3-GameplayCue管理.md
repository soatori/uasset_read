# GameplayCue 管理

## 概述

ULyraGameplayCueManager 继承自 UGameplayCueManager，是 Lyra 项目中 GameplayCue 管理的定制实现。提供延迟加载机制、预加载管理和 GameplayCue 路径注册功能。

## ULyraGameplayCueManager

继承自 `UGameplayCueManager`，位于 `AbilitySystem/` 目录。

### 关键方法

| 方法 | 用途 |
|------|------|
| OnCreated() | 创建时初始化 |
| ShouldAsyncLoadRuntimeObjectLibraries() | 是否异步加载运行时对象库 |
| ShouldSyncLoadMissingGameplayCues() | 是否同步加载缺失的 GameplayCue |
| ShouldAsyncLoadMissingGameplayCues() | 是否异步加载缺失的 GameplayCue |
| LoadAlwaysLoadedCues() | 加载始终需要加载的 GameplayCue |
| RefreshGameplayCuePrimaryAsset() | 刷新 GameplayCue Primary Asset 的 Bundle |

### 延迟加载机制

Lyra 实现了 GameplayCue 的延迟加载策略：

1. 启动时不立即加载所有 GameplayCue
2. `ShouldAsyncLoadRuntimeObjectLibraries()` 控制是否异步加载
3. 当 GameplayTag 被引用时，通过 `OnGameplayTagLoaded` 回调触发按需加载
4. 预加载的 Cue 存储在 `PreloadedCues` 集合中
5. 代码引用或显式声明的 Cue 存储在 `AlwaysLoadedCues` 集合中

### 预加载机制

```cpp
// 预加载的 Cue（因被内容引用而提前加载）
UPROPERTY(transient)
TSet<TObjectPtr<UClass>> PreloadedCues;

// 始终加载的 Cue（代码引用或显式声明）
UPROPERTY(transient)
TSet<TObjectPtr<UClass>> AlwaysLoadedCues;
```

### 垃圾回收后处理

`HandlePostGarbageCollect()` 在 GC 后处理待加载的 GameplayTag，通过 `ProcessLoadedTags()` 执行实际加载。

## GameplayCue 路径注册

GameplayCue 的搜索路径通过两种机制扩展：

### 1. GameFeatureAction_AddGameplayCuePath

GameFeature 插件通过 `UGameFeatureAction_AddGameplayCuePath` 在加载时注册自定义的 GameplayCue 搜索路径：

```cpp
UPROPERTY(EditAnywhere, Category = "Game Feature | Gameplay Cues", meta = (RelativeToGameContentDir, LongPackageName))
TArray<FDirectoryPath> DirectoryPathsToAdd;
```

### 2. ULyraGameFeature_AddGameplayCuePaths

GameFeature 策略的 Observer，监听 GameFeature 插件的注册/注销事件，自动添加/移除 GameplayCue 路径：

```cpp
OnGameFeatureRegistering()   // 注册时添加路径
OnGameFeatureUnregistering() // 注销时移除路径
```

## 调试

```cpp
static void DumpGameplayCues(const TArray<FString>& Args);
```

提供控制台命令用于导出 GameplayCue 列表，辅助调试。
