# AssetManager 与异步加载

## ULyraAssetManager

[ULyraAssetManager](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraAssetManager.h) 继承自 `UAssetManager`，是 Lyra 的全局资产管理器。它负责：

1. 异步加载资产（通过 `FSoftObjectPath`）
2. Asset Bundle 管理
3. 初始化时的资产预热加载

## 异步资产加载

### TSoftObjectPtr 与 FSoftObjectPath

Lyra 中大量使用 `TSoftObjectPtr` 和 `FSoftObjectPath` 进行异步加载：

- **`TSoftObjectPtr<UObject>`** — 类型安全的软引用，用于资产拉取
- **`FSoftObjectPath`** — 底层路径字符串表示，无类型约束
- **`FPrimaryAssetId`** — 主资产 ID，由 `PrimaryAssetType:PrimaryAssetName` 构成

二者的区别：

| 特性 | TSoftObjectPtr\<T\> | FSoftObjectPath |
|------|---------------------|----------------|
| 类型安全 | 是 | 否 |
| 运行时同步/异步加载 | 是 | 是 |
| 内存占用 | 较大 | 较小 |
| 序列化 | 稳定 | 稳定 |

使用场景：
- 初始化阶段存在某些不必要的资源时，使用 `TSoftObjectPtr` 替代硬指针
- 如果只存储路径字符串，`FSoftObjectPath` 更轻量

### 核心加载方法

```cpp
// 同步加载（但通常应避免）
TSoftObjectPtr<UObject> MyObject;
UObject* Loaded = MyObject.LoadSynchronous();

// 异步加载（推荐）
TSoftObjectPtr<UObject> MyObject;
TStreamableHandlePtr Handle = UAssetManager::GetStreamableManager().RequestAsyncLoad(
    MyObject.ToSoftObjectPath(),
    FStreamableDelegate::CreateUObject(this, &ThisClass::OnLoadComplete));
```

### 在 Experience 中的使用

`ULyraExperienceDefinition` 中使用 `TSoftClassPtr` 引用 GA/GE/AttributeSet：

```cpp
UPROPERTY(EditDefaultsOnly, Category = Gameplay)
TArray<TSoftClassPtr<ULyraGameplayAbility>> GameplayAbilities;

UPROPERTY(EditDefaultsOnly, Category = Gameplay)
TArray<TSoftClassPtr<ULyraAttributeSet>> AttributeSets;

UPROPERTY(EditDefaultsOnly, Category = Gameplay)
TArray<TSoftClassPtr<UGameplayEffect>> GameplayEffects;
```

## Asset Bundle

Asset Bundle 是 UE 的资产分组机制，将多个资产打包为一个 Bundle，实现按需加载。

在 Lyra 中，Asset Bundle 配合 Experience 系统使用：
1. Experience 定义中声明需要的资产（GA/GE/AttributeSet）
2. AssetManager 将这些资产归类为 Bundle
3. Experience 加载时通知 AssetManager 请求该 Bundle
4. AssetManager 异步加载 Bundle 中的所有资产
5. 加载完成后 Experience 通知 GameMode 允许玩家登录

## 性能优化的宏

Lyra 中使用的性能优化宏：

### UE_INLINE_GENERATED_CPP_BY_NAME

将 `_gen.cpp` 的内容内联到头文件中，减少间接调用。注意：
- 每个类仅能使用一次
- 使用后移除对应的 `#include` 语句（因为头文件已包含生成代码）

### UE_DISABLE_OPTIMIZATION / UE_ENABLE_OPTIMIZATION

用于禁用/启用特定代码的编译器优化：

```cpp
UE_DISABLE_OPTIMIZATION
// 不需要优化的代码
UE_ENABLE_OPTIMIZATION
```

### UE_AUTORTTR_END_SCOPE

用于作用域内自动结束 RTT 追踪标记：
- 通常在代码中搜索 `TRACE_CPUPROFILER_EVENT_SCOPE` 标记的热点函数
- 标记 `RTT` 缩写可快速定位

### 引用标记搜索技巧

在 VS 中搜索以下标记辅助定位：

| 标记 | RTT 缩写 | 说明 |
|------|---------|------|
| `RTT` | R | 热点函数标记 |
| `TRACETAG` | T | CPU 追踪标签 |
| `TRACE_CPUPROFILER_EVENT_SCOPE` | T | 作用域 CPU 追踪 |

## 常见性能陷阱

直接使用 `StaticLoadObject` / `StaticConstructObject` / `LoadObject` 会导致同步加载阻塞游戏线程。正确的做法是使用 `UAssetManager::GetStreamableManager().RequestAsyncLoad` 进行异步加载。
