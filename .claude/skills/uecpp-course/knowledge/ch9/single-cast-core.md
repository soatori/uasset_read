# 单播委托核心

## 声明

单播委托使用 `DECLARE_DELEGATE` 宏体系声明，支持带返回值和一个或多个参数：

```cpp
// 无返回值、无参数
DECLARE_DELEGATE(FXGSingDelegatePrintLocation);

// 有返回值（FVector）、一个参数（FString）
DECLARE_DELEGATE_RetVal_OneParam(FVector, FXGSingDelegateGetLocation, FString);
```

## 成员变量

声明后的委托类型可直接作为成员变量，存储在管理类中：

```cpp
// XGSingleDelegateActor.h
FXGSingDelegatePrintLocation SingDelegatePrintLocation;
FXGSingDelegateGetLocation SingDelegateGetLocation;
```

## 绑定

单播委托使用 `Bind*` 方法系列进行绑定。**绑定新委托会替换之前的绑定**（一对一关系）：

```cpp
// 绑定 UObject 成员函数
SingDelegatePrintLocation.BindUObject(this, &AXGSingleDelegateActor::MyFunction);

// 绑定带 Payload 的成员函数（额外参数在执行前已注入）
SingDelegateGetLocation.BindUObject(this, &AXGLocationActor::GetLocationWithPayload, Health, Money);
```

## 执行

```cpp
// 有返回值、有参数
FVector Result = SingDelegateGetLocation.Execute(TEXT("Hello"));

// 检查后再执行（安全方式）
if (SingDelegatePrintLocation.IsBound())
{
    SingDelegatePrintLocation.Execute();
}

// 更简洁的检查执行
SingDelegatePrintLocation.ExecuteIfBound();
```

## 返回值

单播委托**支持返回值**。返回值类型在声明宏中指定：

```cpp
// 声明：返回 FVector，接受 FString 参数
DECLARE_DELEGATE_RetVal_OneParam(FVector, FXGSingDelegateGetLocation, FString);

// 执行并获取返回值
FVector Location = SingDelegateGetLocation.Execute(TEXT("Player"));
```

## Payload（负载参数）

Payload 允许在**绑定时刻传入额外参数**，这些参数会被存储在委托内部，在执行时自动传递给目标函数。目标函数的参数签名 = 委托声明的参数 + Payload 参数：

```cpp
// 声明：委托签名只有 FString
DECLARE_DELEGATE_RetVal_OneParam(FVector, FXGSingDelegateGetLocation, FString);

// 绑定：额外传入 Health, Money 作为 Payload
// 目标函数签名：FVector GetLocationWithPayload(FString, int32, int32)
SingDelegateGetLocation.BindUObject(
    LocationActor,
    &AXGLocationActor::GetLocationWithPayload,
    Health,    // Payload 参数 1
    Money      // Payload 参数 2
);

// 执行时只需传入委托声明的参数
FVector Result = SingDelegateGetLocation.Execute(TEXT("Hello"));
```

**Payload 的特点**：
- 值在绑定时被**拷贝存储**
- 执行时自动追加到目标函数的参数列表末尾
- 适用于在绑定时注入上下文数据，无需改变委托签名

## 执行安全

| 方式 | 代码 | 说明 |
|------|------|------|
| 无检查 | `Delegate.Execute()` | 未绑定时崩溃 |
| 预检查 | `if(Delegate.IsBound()) Delegate.Execute()` | 安全但两步 |
| 合一 | `Delegate.ExecuteIfBound()` | 安全，一步完成 |

建议始终使用 `ExecuteIfBound()` 或先检查 `IsBound()`。

> **代码位置**：[XGSingleDelegateActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/012_Delegate/XGSingleDelegateActor.h) / [XGSingleDelegateActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/012_Delegate/XGSingleDelegateActor.cpp)
