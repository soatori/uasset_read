# 动态单播委托

## 声明

动态单播委托使用 `DECLARE_DYNAMIC_DELEGATE` 宏体系声明。**与 Native 委托的关键区别**：参数需要同时提供**类型**和**变量名**（反射系统需要变量名来匹配蓝图 Pin）：

```cpp
// 两个参数，无返回值
DECLARE_DYNAMIC_DELEGATE_TwoParams(FXGDynamicTwo, FString, InName, int32, InMoney);

// 一个参数，有返回值（int32）
DECLARE_DYNAMIC_DELEGATE_RetVal_OneParam(int32, FXGDynamicRetOne, FString, InName);
```

对比 Native 委托的参数声明：

| 委托类型 | 声明 | 参数写法 |
|----------|------|----------|
| Native | `DECLARE_DELEGATE_OneParam(Name, FString)` | 只需类型 |
| Dynamic | `DECLARE_DYNAMIC_DELEGATE_OneParam(Name, FString, InName)` | 类型 + 变量名 |

## 成员变量

动态单播委托变量通常声明为 `protected`，通过 `UFUNCTION` 公开操作接口：

```cpp
UCLASS()
class AXGDynamicSingleActor : public AActor
{
protected:
    FXGDynamicTwo XGDynamicTwoDelegate;
    FXGDynamicRetOne XGDynamicRetOneDelegate;

public:
    UFUNCTION(BlueprintCallable)
    void InitXGDynamicTwoDelegate(FXGDynamicTwo InDelegate);

    UFUNCTION(BlueprintCallable)
    void CallXGDynamicTwoDelegate();

    UFUNCTION(BlueprintCallable)
    void ReleaseXGDynamicTwoDelegate();
};
```

## 典型使用模式：Init / Call / Release

动态单播采用**外部注入**模式——外部代码（C++ 或蓝图）创建委托实例，通过 Init 方法注入到持有类：

```cpp
// 初始化（注入委托）— 从外部传入
void AXGDynamicSingleActor::InitXGDynamicTwoDelegate(FXGDynamicTwo InDelegate)
{
    XGDynamicTwoDelegate = InDelegate;
}

// 执行
void AXGDynamicSingleActor::CallXGDynamicTwoDelegate()
{
    XGDynamicTwoDelegate.ExecuteIfBound(TEXT("XG"), 999);
}

// 释放
void AXGDynamicSingleActor::ReleaseXGDynamicTwoDelegate()
{
    XGDynamicTwoDelegate.Clear();
}
```

**三种操作分离**的设计意图：
- `Init`：外部传入委托（来自蓝图的 `BindUFunction` 或 C++ 的绑定）
- `Call`：在合适的时机触发执行
- `Release`：清除委托引用

## 绑定方式

动态单播主要通过 `BindUFunction` 绑定（基于反射），也可以在 C++ 中通过赋值操作：

```cpp
// C++ 中创建并绑定动态委托
FXGDynamicTwo NewDelegate;
NewDelegate.BindUFunction(this, TEXT("SomeUFUNCTION"));

// 注入
DynamicActor->InitXGDynamicTwoDelegate(NewDelegate);
```

## 蓝图集成

动态单播的变量**不需要** `UPROPERTY` 即可被蓝图使用——通过 `UFUNCTION(BlueprintCallable)` 的参数传递：

1. 在蓝图中创建动态委托实例（使用 `Create Event` 节点或 `Bind Event` 到函数）
2. 调用 Init 方法注入
3. 调用 Call 方法触发执行

## 与 Native 单播对比

| 特性 | Native 单播 | 动态单播 |
|------|-------------|----------|
| 蓝图支持 | 不支持 | 支持 |
| 参数声明 | 只需类型 | 类型 + 变量名 |
| 绑定方法 | 多种 `Bind*` | 主要 `BindUFunction` |
| 性能 | 高 | 略低（反射开销） |
| 典型用途 | C++ 内部回调 | 暴露给蓝图使用 |

> **代码位置**：[XGDynamicSingleActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/012_Delegate/XGDynamicSingleActor.h) / [XGDynamicSingleActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/012_Delegate/XGDynamicSingleActor.cpp)
