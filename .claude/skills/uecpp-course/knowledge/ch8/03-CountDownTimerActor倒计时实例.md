# CountDownTimerActor 倒计时实例

## 概述

`AXGCountDownTimerActor` 是一个完整的倒计时定时器实现，通过 `UTextRenderComponent` 在世界空间中显示数字倒计时，倒计时归零后显示 "GO!"。本节展示定时器驱动的数值变化与文本更新模式。

## 类声明

[XGCountDownTimerActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/011_Timer/XGCountDownTimerActor.h)

```cpp
UCLASS()
class AXGCountDownTimerActor : public AActor
{
    GENERATED_BODY()
public:
    AXGCountDownTimerActor();
    class UTextRenderComponent* CountdownText;

protected:
    virtual void BeginPlay() override;
    void AdvanceTimer();
    void UpdateTimerDisplay();
    UFUNCTION(BlueprintNativeEvent)
    void CountdownHasFinished();

public:
    virtual void Tick(float DeltaTime) override;

protected:
    UPROPERTY(EditAnywhere)
    int32 CountdownTime;
    FTimerHandle CountdownTimerHandle;
};
```

## 构造函数

[XGCountDownTimerActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/011_Timer/XGCountDownTimerActor.cpp)

```cpp
AXGCountDownTimerActor::AXGCountDownTimerActor()
{
    PrimaryActorTick.bCanEverTick = false;

    CountdownText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("CountdownNumber"));
    CountdownText->SetHorizontalAlignment(EHTA_Center);
    CountdownText->SetWorldSize(150.0f);
    RootComponent = CountdownText;

    CountdownTime = 3;
}
```

| 配置 | 说明 |
|------|------|
| `bCanEverTick = false` | 不需要 Tick，节省性能 |
| `CreateDefaultSubobject<UTextRenderComponent>` | 在世界空间中显示文本的组件 |
| `SetHorizontalAlignment(EHTA_Center)` | 文本水平居中 |
| `SetWorldSize(150.0f)` | 文本世界大小（不随距离缩放的固定尺寸） |
| `RootComponent = CountdownText` | UTextRenderComponent 直接作为根组件 |
| `CountdownTime = 3` | 默认倒计时 3 秒，可在编辑器中覆盖 |

## BeginPlay 启动定时器

```cpp
void AXGCountDownTimerActor::BeginPlay()
{
    Super::BeginPlay();
    UpdateTimerDisplay();
    GetWorldTimerManager().SetTimer(
        CountdownTimerHandle,
        this,
        &AXGCountDownTimerActor::AdvanceTimer,
        1.0f,
        true
    );
}
```

- 先调用 `UpdateTimerDisplay()` 显示初始倒计时值
- SetTimer 使用 **循环模式**（第 4 参数 `true`），每秒触发一次 AdvanceTimer
- 省略 `InFirstDelay` 参数，使用默认值（与 InRate 相同，即 1 秒）

## 倒计时驱动模式

### AdvanceTimer（定时器回调）

```cpp
void AXGCountDownTimerActor::AdvanceTimer()
{
    --CountdownTime;
    UpdateTimerDisplay();
    if (CountdownTime < 1)
    {
        GetWorldTimerManager().ClearTimer(CountdownTimerHandle);
        CountdownHasFinished();
    }
}
```

执行流程：
1. 每次回调递减 `CountdownTime`
2. 调用 `UpdateTimerDisplay()` 刷新文本显示
3. 当 `CountdownTime < 1` 时：
   - `ClearTimer` 清理定时器，停止进一步触发
   - 调用 `CountdownHasFinished()` 触发结束逻辑

### UpdateTimerDisplay（数值转文本）

```cpp
void AXGCountDownTimerActor::UpdateTimerDisplay()
{
    CountdownText->SetText(
        FText::FromString(FString::FromInt(FMath::Max(CountdownTime, 0)))
    );
}
```

| 函数链 | 作用 |
|--------|------|
| `FMath::Max(CountdownTime, 0)` | 确保不会显示负数 |
| `FString::FromInt(...)` | 将整数转换为字符串 |
| `FText::FromString(...)` | 将 FString 转换为 FText（UTextRenderComponent 所需的类型） |

### CountdownHasFinished（结束回调）

```cpp
void AXGCountDownTimerActor::CountdownHasFinished_Implementation()
{
    CountdownText->SetText(FText::FromString(TEXT("GO!")));
}
```

函数名后缀 `_Implementation` 是因为 `BlueprintNativeEvent` 要求 C++ 默认实现使用此命名约定（详见 [04-蓝图交互与BlueprintNativeEvent](04-蓝图交互与BlueprintNativeEvent.md)）。

## 计时逻辑对照

| 触发次数 | CountdownTime 变化 | 显示 | 动作 |
|----------|-------------------|------|------|
| BeginPlay | 3 | "3" | 设置定时器 |
| 第 1 秒 | 2 | "2" | AdvanceTimer 递减 |
| 第 2 秒 | 1 | "1" | AdvanceTimer 递减 |
| 第 3 秒 | 0 | "0" | CountdownTime < 1，清理定时器 |
| — | 0 | "GO!" | CountdownHasFinished 触发 |

## 代码参考

- [XGCountDownTimerActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/011_Timer/XGCountDownTimerActor.h)
- [XGCountDownTimerActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/011_Timer/XGCountDownTimerActor.cpp)
