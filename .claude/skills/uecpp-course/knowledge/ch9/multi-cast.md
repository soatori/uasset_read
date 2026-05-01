# 多播委托

## 声明

```cpp
DECLARE_MULTICAST_DELEGATE_OneParam(FXGMulityDelegate, FString);
```

多播委托**不支持返回值**。

## 绑定与执行

多播委托使用 `Add*` 系列方法添加绑定（而非 `Bind*`），允许同一个委托绑定多个目标：

```cpp
// 多播委托成员变量
FXGMulityDelegate MulityMoreDelegate;

// 添加各种绑定
MulityMoreDelegate.AddLambda([](FString InStr) { ... });
MulityMoreDelegate.AddRaw(RawStruct, &FXGMultiRawStruct::PrintStr);
MulityMoreDelegate.AddSP(SmartStructPtr, &FXGMultiRawStruct::PrintSPStr);
MulityMoreDelegate.AddStatic(MyMultiStaticMeth);
MulityMoreDelegate.AddThreadSafeSP(SmartStructPtrSafe, &FXGMultiRawStructSafe::PrintSPStr);
MulityMoreDelegate.AddUFunction(this, TEXT("MyUFUNCTION"));
MulityMoreDelegate.AddUObject(this, &AXGMultiDelegateActor::PrintInStr);
MulityMoreDelegate.AddWeakLambda(this, [](FString InStr) { ... });
```

绑定方式的命名规律：**`Add` + 【绑定类型】**，与单播的 `Bind` + 【绑定类型】一一对应。

**执行使用 `Broadcast()`**：

```cpp
MulityMoreDelegate.Broadcast(TEXT("Send All"));
```

`Broadcast` 会调用所有已绑定的目标函数。

## FDelegateHandle — 定点移除

每次 `Add*` 返回一个 `FDelegateHandle`，用于后续单独移除：

```cpp
// 绑定并保存 Handle
FDelegateHandle MyHandle = MulityDelegate.AddUObject(
    this,
    &AXGMultiExecuteActor::Work,
    InHealth
);

// 通过 Handle 单独移除
MulityDelegate.Remove(MyHandle);
```

## 生命周期管理

**必绑必解**——多播委托不会自动移除已销毁对象的绑定。正确的生命周期管理：

```cpp
// AXGMultiExecuteActor 的 BeginPlay 中绑定
void AXGMultiExecuteActor::BeginPlay()
{
    AActor* ActorPtr = UGameplayStatics::GetActorOfClass(
        this,
        AXGMultiDelegateActor::StaticClass()
    );
    if (AXGMultiDelegateActor* MultiDelActor = Cast<AXGMultiDelegateActor>(ActorPtr))
    {
        int32 Health = 100;
        MyDelegateHandle = MultiDelActor->MulityDelegate.AddUObject(
            this,
            &AXGMultiExecuteActor::Work,
            Health
        );
    }
}

// AXGMultiExecuteActor 的 EndPlay 中移除
void AXGMultiExecuteActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    Super::EndPlay(EndPlayReason);
    AActor* ActorPtr = UGameplayStatics::GetActorOfClass(
        this,
        AXGMultiDelegateActor::StaticClass()
    );
    if (AXGMultiDelegateActor* MultiDelActor = Cast<AXGMultiDelegateActor>(ActorPtr))
    {
        MultiDelActor->MulityDelegate.Remove(MyDelegateHandle);
    }
}
```

`AXGMultiDelegateActor`（持有委托的一方）也应在 `EndPlay` 中清空：

```cpp
void AXGMultiDelegateActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    Super::EndPlay(EndPlayReason);
    MulityDelegate.Clear();      // 移除所有绑定
    MulityMoreDelegate.Clear();  // 移除所有绑定
    
    if (RawStruct)
    {
        delete RawStruct;
        RawStruct = nullptr;
    }
}
```

## 多执行 Actor 模式

多播的典型用法：**一个 Manager 持有多播委托，多个 Executor Actor 各自注册回调**。

```cpp
// Executor Actor 使用 GUID 标识自己
UCLASS()
class AXGMultiExecuteActor : public AActor
{
    FGuid MyActorID;  // 在构造或 BeginPlay 中生成唯一 GUID
    
    void Work(FString InFString, int32 InHealth);
    
    FDelegateHandle MyDelegateHandle;
};
```

每个 `AXGMultiExecuteActor` 实例都有自己的 `FGuid`，在日志输出中可区分是哪号 Actor 触发了回调。

## 清空操作

| 方法 | 效果 |
|------|------|
| `Delegate.Clear()` | 移除所有绑定 |
| `Delegate.Remove(Handle)` | 移除特定绑定 |
| `Delegate.RemoveAll(Object)` | 移除某个 UObject 的所有绑定 |

## 多播与单播对照表

| 特性 | 单播 | 多播 |
|------|------|------|
| 关系 | 一对一（绑定即替换） | 一对多（追加） |
| 绑定方法 | `Bind*` | `Add*` |
| 执行 | `Execute()` / `ExecuteIfBound()` | `Broadcast()` |
| 返回值 | 支持 | 不支持 |
| 定点移除 | 自动替换 | `FDelegateHandle` |
| 清空 | `Clear()` | `Clear()` |
| 生命周期 | 部分自动（UObject） | 需手动管理 |

> **代码位置**：[XGMultiDelegateActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/012_Delegate/XGMultiDelegateActor.h) / [XGMultiDelegateActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/012_Delegate/XGMultiDelegateActor.cpp)
> 
> [XGMultiDelegateActor.h — AXGMultiExecuteActor](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/012_Delegate/XGMultiDelegateActor.h)
