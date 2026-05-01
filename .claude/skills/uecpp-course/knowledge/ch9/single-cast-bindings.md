# 单播绑定方式详解

单播委托提供多种 `Bind*` 方法，适用于不同生命周期管理需求的对象类型。

## BindUObject — UObject 安全绑定

绑定到 `UObject` 派生类的成员函数。UObject 被销毁时委托自动解绑：

```cpp
SingDelegatePrintLocation.BindUObject(this, &AXGSingleDelegateActor::MyFunction);
SingDelegateGetLocation.BindUObject(LocationActor, &AXGLocationActor::GetLocation);
```

**安全等级：** 高（弱引用，UObject 销毁时自动清理）

## BindRaw — 原生 C++ 对象绑定

绑定到原生 C++ 结构体/类的成员函数。**不管理生命周期**——必须在原始对象销毁前手动解绑或确保不再调用：

```cpp
FXGSingeRawStruct* RawStructPtr = new FXGSingeRawStruct();
SingDelegateRaw.BindRaw(RawStructPtr, &FXGSingeRawStruct::RawLocation, PayloadMoney);
```

**安全等级：** 低（裸指针，不追踪生命周期）

## BindSP / BindSPLambda — 共享指针绑定

绑定到 `TSharedPtr`/`TSharedRef` 管理的对象。共享指针存活时委托有效：

```cpp
TSharedRef<FXGSingeRawStruct> StructPtr(new FXGSingeRawStruct());
SmartStructPtr = StructPtr;  // 成员变量持有引用，防止提前释放

SingDelegateSmartPointer.BindSP(StructPtr, &FXGSingeRawStruct::SmartLocation);
SingDelegateSmartPointerLambda.BindSPLambda(StructPtr, []()
{
    UE_LOG(LogTemp, Warning, TEXT("SingDelegateSmartPointerLambda Execute"));
});
```

**安全等级：** 中高（持有弱引用，SharedPtr 释放后自动失效）

## BindLambda — Lambda 绑定

绑定到匿名 Lambda 表达式。**注意生命周期**——如果 Lambda 捕获了 `this` 指针，必须确保对象在 Lambda 被调用时仍然存活：

```cpp
SingDelegateLambda.BindLambda([]()
{
    UE_LOG(LogTemp, Warning, TEXT("SingDelegateLambda Execute"));
});

SingDelegateLambdaLocation.BindLambda([](FString InStr) -> FVector
{
    UE_LOG(LogTemp, Warning, TEXT("SingDelegateLambdaLocation Execute"));
    return FVector::ZeroVector;
});
```

**安全等级：** 视捕获内容而定（捕获裸指针时同 Raw 等级）

## BindStatic — 静态/全局函数绑定

绑定到静态函数或全局函数：

```cpp
// 静态函数
static void MyStaticMeth()
{
    UE_LOG(LogTemp, Warning, TEXT("Exec Static Method"));
}

SingDelegateStaticMethod.BindStatic(MyStaticMeth);
```

**安全等级：** 高（函数本身无生命周期问题）

## BindThreadSafeSP — 线程安全共享指针绑定

与 `BindSP` 类似，但额外支持跨线程调用：

```cpp
TSharedRef<FXGSingeRawStruct, ESPMode::ThreadSafe> StructPtrSafe(new FXGSingeRawStruct());
SingDelegateSmartPointerSafe.BindThreadSafeSP(
    StructPtrSafe,
    &FXGSingeRawStruct::SmartLocation
);
```

**安全等级：** 中高（线程安全版本，但仍有生命周期管理）

## BindUFunction — 反射绑定

通过函数名（`FName`）绑定，目标函数必须是 `UFUNCTION()`：

```cpp
UFUNCTION()
void MyFunction();

SingDelegateUFunction.BindUFunction(this, TEXT("MyFunction"));
```

**安全等级：** 高（UObject 机制）

## BindWeakLambda — 弱 Lambda 绑定

Lambda 捕获的对象以弱引用形式持有。传入的 `UObject*` 被销毁后，Lambda 不会被执行：

```cpp
SingDelegateWeakLambda.BindWeakLambda(this, []()
{
    UE_LOG(LogTemp, Warning, TEXT("SingDelegateWeakLambda Execute"));
});
```

**安全等级：** 高（持有 UObject 弱引用，自动安全）

## 绑定方式对比

| 方法 | 目标类型 | 生命周期安全 | 适用场景 |
|------|----------|-------------|----------|
| `BindUObject` | UObject 成员函数 | 安全 | 最常见的 UE 对象绑定 |
| `BindRaw` | 原生 C++ 对象 | 不安全 | 短期明确的临时对象 |
| `BindSP` | TSharedPtr 对象 | 较安全 | 生命周期明确的对象 |
| `BindLambda` | Lambda | 视捕获内容 | 简单逻辑、临时回调 |
| `BindStatic` | 静态/全局函数 | 安全 | 工具函数 |
| `BindThreadSafeSP` | TSharedPtr(ThreadSafe) | 较安全 | 跨线程委托 |
| `BindUFunction` | UFUNCTION | 安全 | 反射调用 |
| `BindWeakLambda` | Lambda + UObject | 安全 | 需要 Lambda 但防悬空 |

> **代码位置**：[XGSingleDelegateActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/012_Delegate/XGSingleDelegateActor.cpp) — `BeginPlay()` 中演示了所有绑定方式
