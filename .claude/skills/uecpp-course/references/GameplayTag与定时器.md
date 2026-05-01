# GameplayTag 与定时器

## 概述

GameplayTag（FName 层级标识符）和定时器（FTimerManager）是 UE 开发中的两个基础工具组件。Tag 提供轻量级的类型/状态标记体系，定时器提供托管在 GameInstance 上的延迟/重复执行机制。

## GameplayTag

### 设计动机

```
bool → enum → tag（开发者发现的演进路径）
bool          → 不可扩展，状态增多时爆炸
enum         → 有限值，不能 OR 组合
GameplayTag  → 层级结构，支持父子匹配、运行时注册、Network 同步
```

### 四种创建方式

```cpp
// 1. C++ 硬编码 + 代码验证（推荐入口类统一管理）
FGameplayTag::RequestGameplayTag(TEXT("Inventory.Item.Weapon"));

// 2. Blueprint 选择器
// IGameplayTagAssetInterface + GetOwnedGameplayTags

// 3. 数据表驱动
// UDataTable + FGameplayTagTableRow

// 4. 编辑器专用
// 在 Editor 中按 Tag.Child.SubChild 层级手动创建
```

### 匹配操作

```cpp
Tag.MatchesAny(Container);                    // OR 匹配：任一 Tag 匹配即可
Tag.MatchesAny(Container, bExactMatch);       // 可选是否精确匹配
Tag.MatchesTag(OtherTag);                     // 精确匹配
Tag.MatchesTagDepth(OtherTag);                // 层级匹配（Parent.Match(Child) = false）
```

### C++ 声明与使用

```cpp
// 在 .h 中声明
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Tag")
FGameplayTag WeaponTag;

// 在 .cpp 中使用
if (WeaponTag.IsValid())
{
    FGameplayTagContainer OwnedTags = ...;
    if (OwnedTags.HasTagExact(WeaponTag)) { }
}
```

### FGameplayTagContainer

```cpp
FGameplayTagContainer Container;
Container.AddTag(Tag1);
Container.AddTag(Tag2);
Container.RemoveTag(Tag1);
Container.HasAny(OtherContainer);
Container.HasAll(OtherContainer);

// 网络复制
UPROPERTY(Replicated)
FGameplayTagContainer NetContainer;
```

## 定时器

### 核心类型

| 类型 | 说明 |
|------|------|
| **FTimerManager** | 定时器管理器，通过 World 获取 |
| **FTimerHandle** | 定时器句柄（轻量级，可用于检查/暂停/取消） |

### SetTimer API

```cpp
// 延迟 2s 后调用一次
GetWorldTimerManager().SetTimer(Handle, this, &UMyClass::Callback, 2.0f, false);

// 每 1s 调用一次，首次 0.5s 后触发
GetWorldTimerManager().SetTimer(Handle, this, &UMyClass::Tick, 1.0f, true, 0.5f);

// 清除
GetWorldTimerManager().ClearTimer(Handle);

// 检查状态
if (GetWorldTimerManager().IsTimerActive(Handle)) { }
if (GetWorldTimerManager().IsTimerPaused(Handle)) { }
GetWorldTimerManager().GetTimerRemaining(Handle);
GetWorldTimerManager().GetTimerElapsed(Handle);
```

### TimerRate vs TimerDelegate

- **TimerRate**：固定频率执行（SetTimer 的 Rate 参数）
- **TimerDelegate**：自定义委托回调，支持动态延迟

### TIntervalCountdown

```cpp
TIntervalCountdown Countdown(FTimespan::FromSeconds(30));
if (Countdown.GetRemaining().IsZero()) { /* 倒计时结束 */ }
```

### 关键注意

- FTimerManager 在 `UWorld` 上，World 销毁时所有定时器自动清理
- 回调函数必须是 `UFUNCTION` 或使用 `FTimerDelegate`
- 不要依赖定时器的精确性（GameThread 排队执行，非实时）

## 代码入口

| 文件 | 说明 |
|------|------|
| [XGGameplayTagTest.h](../../../../code/001_XGSampleDemo/Source/XGSampleDemo/011_GameplayTag/XGGameplayTagTest.h) | GameplayTag 使用（Tag/Container/匹配） |
| [XGGameplayTagTest.cpp](../../../../code/001_XGSampleDemo/Source/XGSampleDemo/011_GameplayTag/XGGameplayTagTest.cpp) | RequestGameplayTag 创建 |
| [XGTimeTest.h](../../../../code/001_XGSampleDemo/Source/XGSampleDemo/008_Timer/XGTimeTest.h) | FTimerManager 使用 |
