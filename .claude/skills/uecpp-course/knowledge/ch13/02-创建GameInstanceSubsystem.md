# 创建 GameInstanceSubsystem

## 头文件声明

创建一个 GameInstanceSubsystem 需要继承 `UGameInstanceSubsystem`，并包含 `Subsystems/GameInstanceSubsystem.h` 头文件。

```cpp
#pragma once
#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "XGSimpleSubsystem.generated.h"

UCLASS()
class UXGSimpleSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;
};
```

## 三个可重写方法

### ShouldCreateSubsystem

条件控制 Subsystem 是否创建。返回 `true` 则创建，返回 `false` 则不创建。

```cpp
bool UXGSimpleSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
    return true;
}
```

典型使用场景：

- 仅在服务端创建（判断 `Outer` 是否为 Dedicated Server）
- 仅在客户端创建
- 根据配置文件决定

引擎通过检查 CDO（Class Default Object）来做决定——`Initialize()` 之前，引擎会先调用 CDO 的 `ShouldCreateSubsystem()` 判断是否需要创建实例。

### Initialize

当 Subsystem 被创建时自动调用。在此处进行资源初始化、网络连接建立、数据加载等操作。

```cpp
void UXGSimpleSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    // 初始化逻辑
}
```

`Super::Initialize(Collection)` 调用父类实现。父类 `UGameInstanceSubsystem::Initialize()` 本身是空实现，调用 Super 是规范做法。

### Deinitialize

当 Subsystem 被销毁前自动调用。在此处进行资源释放、文件写入等清理工作。

```cpp
void UXGSimpleSubsystem::Deinitialize()
{
    // 清理逻辑
    Super::Deinitialize();
}
```

## 引擎自动管理

Subsystem 不需要手动实例化。只要 UCLASS 被引擎反射系统识别，引擎会自动：

1. 在 GameInstance 创建时检查所有 UGameInstanceSubsystem 子类
2. 调用 `ShouldCreateSubsystem()` 判断是否创建
3. 创建实例并调用 `Initialize()`
4. 在 GameInstance 销毁时调用 `Deinitialize()` 并销毁实例

## 命名约定

Subsystem 类名建议使用 `U{描述}Subsystem` 格式，如 `UXGSimpleSubsystem`、`UAssetManagerSubsystem`。

## 跨关卡数据持久性

GameInstanceSubsystem 在关卡切换时保持存活。这是它区别于 GameMode/GameState/PlayerController/PlayerState 的关键特性——后四者在关卡切换时都会被销毁重建。

这个特性使 Subsystem 非常适合存储：

- 游戏进度数据
- 玩家累积数据（如分数、生命值）
- 网络连接状态
- 跨场景全局状态

## 配套代码

- [XGSimpleSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/016_Subsystem/XGSimpleSubsystem.h) — 完整声明
- [XGSimpleSubsystem.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/016_Subsystem/XGSimpleSubsystem.cpp) — Initialize/Deinitialize 实现
