# 获取 Subsystem 的三种方式

GameInstanceSubsystem 的获取方式有三种，适用场景和安全性各不相同。

## 方式一：AActor 直接获取（推荐）

当调用方是一个 AActor（或拥有 GetGameInstance() 的对象）时，直接通过 GameInstance 获取 Subsystem：

```cpp
void AXGWorkActor::BeginPlay()
{
    Super::BeginPlay();
    UGameInstance* MyGameInstance = GetGameInstance();
    if (MyGameInstance)
    {
        UXGSimpleSubsystem* MyXGSimpleSubsystem = MyGameInstance->GetSubsystem<UXGSimpleSubsystem>();
        MyXGSimpleSubsystem->AddHealth(998);
    }
}
```

**特点**：

- 最常用的方式
- 在 Actor 的 BeginPlay 及之后都安全可用
- 依赖 `GetGameInstance()->GetSubsystem<T>()` 模板函数

## 方式二：UObject 通过 WorldContext 获取

当调用方没有 `GetGameInstance()` 方法时（如 UBlueprintFunctionLibrary 工具函数），需要传入 WorldContext 对象来间接获取：

```cpp
UFUNCTION(BlueprintCallable, Category = "XG",
    meta = (WorldContext = "InWorldContextObject"))
void ObjectGetSubsystem(const UObject* InWorldContextObject)
{
    if (InWorldContextObject && InWorldContextObject->GetWorld())
    {
        UGameInstance* MyGameInstance =
            InWorldContextObject->GetWorld()->GetGameInstance();
        if (MyGameInstance)
        {
            UXGSimpleSubsystem* MyXGSimpleSubsystem =
                MyGameInstance->GetSubsystem<UXGSimpleSubsystem>();
            MyXGSimpleSubsystem->AddHealth(2000);
        }
    }
}
```

**关键要点**：

- 函数参数中需要有一个 `const UObject*` 类型的 WorldContext 参数
- UFUNCTION 的 `meta = (WorldContext = "InWorldContextObject")` 告诉蓝图哪个参数是 WorldContext
- 获取链路：WorldContext → GetWorld() → GetGameInstance() → GetSubsystem()
- 每一步都需要判空，因为某些情况下的 UObject 可能没有有效的 World

> **陷阱**：在 BlueprintFunctionLibrary 中，如果 UFUNCTION 声明为 `BlueprintPure` 同时使用了 `WorldContext` 元数据，打包时会产生难以定位的编译错误。不要在纯函数（Pure）中使用 WorldContext。

## 方式三：静态单例模式（有风险）

在 Subsystem 内部持有一个静态指针，通过静态函数直接返回。这种方法最便捷，但存在生命周期风险。

**定义**：

```cpp
// .h
static UXGSimpleSubsystem* GetXGSubsystemMyself();

// .cpp
UXGSimpleSubsystem* UXGSimpleSubsystem::MySubsystemPtr = nullptr;

void UXGSimpleSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    MySubsystemPtr = this;
}

void UXGSimpleSubsystem::Deinitialize()
{
    MySubsystemPtr = nullptr;
    Super::Deinitialize();
}

UXGSimpleSubsystem* UXGSimpleSubsystem::GetXGSubsystemMyself()
{
    return MySubsystemPtr;
}
```

**使用**：

```cpp
if (UXGSimpleSubsystem* SelfSubstemPtr = UXGSimpleSubsystem::GetXGSubsystemMyself())
{
    SelfSubstemPtr->AddHealth(500);
}
```

**风险说明**：

- **安全区间**：仅在 `Initialize()` 之后到 `Deinitialize()` 之前这段时间内安全
- **危险区间**：引擎初始化初期（Initialize 之前）和引擎关闭末期（Deinitialize 之后），静态指针为空或已失效
- 如果在危险区间访问，可能访问到已被销毁的对象，导致崩溃
- 适合快速原型开发，不适合正式项目或需要可靠性的场景

## 三种方式对比

| 方式 | 安全性 | 便捷性 | 适用场景 |
|------|--------|--------|---------|
| AActor 直接获取 | 最高 | 中 | Actor 类中的标准用法 |
| UObject WorldContext | 高 | 低 | 工具函数、BlueprintFunctionLibrary |
| 静态单例 | 低（限生命周期内） | 最高 | 快速原型、内部工具 |

## 配套代码

- [XGWorkActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/016_Subsystem/XGWorkActor.h) — 演示 WorldContext 方式的函数声明
- [XGWorkActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/016_Subsystem/XGWorkActor.cpp) — BeginPlay 中演示方式一和方式三
- [XGSimpleSubsystem.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/016_Subsystem/XGSimpleSubsystem.cpp) — 静态单例实现
