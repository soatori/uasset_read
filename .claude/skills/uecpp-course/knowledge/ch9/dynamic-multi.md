# 动态多播委托

## 声明

```cpp
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(
    FXGDynamicMultiThree,
    FString, InName,
    int32,   InHealth,
    int32,   InMana
);
```

## 成员变量与 BlueprintAssignable

动态多播委托可通过 `UPROPERTY(BlueprintAssignable)` 暴露给蓝图，允许在蓝图编辑器中直接绑定事件：

```cpp
// 无 UPROPERTY — 仅 C++ 可访问
FXGDynamicMultiThree XGDynamicMultiThree;

// BlueprintAssignable — 蓝图可见，可在蓝图图表中用 Bind Event 绑定
UPROPERTY(BlueprintAssignable)
FXGDynamicMultiThree XGDynamicMultiThreeRight;
```

`UPROPERTY(BlueprintAssignable)` 是关键标记。没有这个标记，蓝图无法看到该委托。

## C++ 绑定与生命周期

动态多播在 C++ 中的绑定使用 `AddDynamic` / `RemoveDynamic` 宏：

```cpp
void AXGDynamicMulityDelegateActor::BeginPlay()
{
    Super::BeginPlay();

    // 绑定
    XGDynamicMultiThreeRight.AddDynamic(
        this,
        &AXGDynamicMulityDelegateActor::WorkDynamicNative
    );
}

void AXGDynamicMulityDelegateActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    Super::EndPlay(EndPlayReason);

    // 解绑
    XGDynamicMultiThreeRight.RemoveDynamic(
        this,
        &AXGDynamicMulityDelegateActor::WorkDynamicNative
    );

    XGDynamicMultiThreeRight.Clear();
}
```

**`AddDynamic` / `RemoveDynamic` 是宏**，展开后调用 `__Internal_AddDynamic` / `__Internal_RemoveDynamic`。

## 执行（Broadcast）

```cpp
UFUNCTION(BlueprintCallable)
void AXGDynamicMulityDelegateActor::CallExceteDynamicMultiThreeRight()
{
    XGDynamicMultiThreeRight.Broadcast(
        TEXT("XG"),
        Health,
        Mana
    );
}
```

## 蓝图绑定流程

1. 在**关卡蓝图**或**Actor 蓝图**中，右键选择 "Bind Event" 或拖入委托变量
2. 选择目标委托（蓝图会列出所有 `BlueprintAssignable` 的动态多播委托）
3. 连接要执行的自定义事件
4. 运行时通过 C++ 调用 `Broadcast`，蓝图绑定的事件自动触发

## 外部注入（骚操作）

与动态单播类似，动态多播也可以通过外部传入的方式在 C++ 中使用：

```cpp
UFUNCTION(BlueprintCallable)
void AXGDynamicMulityDelegateActor::InitXGDynamicMultiThree(
    FXGDynamicMultiThree InDelegate
)
{
    XGDynamicMultiThree = InDelegate;
}
```

这允许从外部构造一个动态多播委托并赋值给内部变量，实现类似 Native 委托的替换效果。外部注入的委托需要通过其他机制（如 `AddDynamic` 宏）绑定目标函数。

## 四种委托对比

| 特性 | Native 单播 | Native 多播 | 动态单播 | 动态多播 |
|------|-------------|-------------|----------|----------|
| 蓝图绑定 | 不支持 | 不支持 | UFUNCTION 参数传递 | BlueprintAssignable + Bind Event |
| 返回值 | 支持 | 不支持 | 支持 | 不支持 |
| 宏参数 | 只用类型 | 只用类型 | 类型+变量名 | 类型+变量名 |
| 绑定 API | Bind* | Add* | BindUFunction / = | AddDynamic / AddUFunction |
| 执行 | Execute | Broadcast | ExecuteIfBound | Broadcast |
| 生命周期 | 部分自动 | 手动 | 手动 | 手动 |
| 性能 | 最高 | 高 | 反射开销 | 反射开销 |
| 典型用途 | 内部逻辑解耦 | 事件广播系统 | 蓝图扩展点 | 蓝图事件系统 |

> **代码位置**：[XGDynamicMulityDelegateActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/012_Delegate/XGDynamicMulityDelegateActor.h) / [XGDynamicMulityDelegateActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/012_Delegate/XGDynamicMulityDelegateActor.cpp)
