# 异步蓝图节点框架与生命周期管理

## UBlueprintAsyncActionBase 概述

`UBlueprintAsyncActionBase` 是 UE 提供的基础类，用于创建可在蓝图中以异步方式执行的节点。继承此类可实现"在蓝图中触发 → 后台执行 → 完成后通过自定义事件引脚返回结果"的模式。

## 枚举：定义可选接口

```cpp
UENUM(BlueprintType)
enum class EXGSampleNetTimeType : uint8
{
    Local       UMETA(DisplayName = "LocalTimeAPI"),
    TaoBao      UMETA(DisplayName = "TaobaoTimeAPI"),
    XGServer    UMETA(DisplayName = "XGServerTimeAPI"),
    MaxNum      UMETA(Hidden)
};
```

- `UMETA(DisplayName = "...")`：蓝图中显示的友好名称
- `UMETA(Hidden)`：在蓝图中隐藏该枚举值，用于计数等内部用途
- `uint8` 基础类型：确保枚举体积最小

## 结构体：定义返回数据结构

```cpp
USTRUCT(BlueprintType)
struct FXGSampleNetTimeRespInfo
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "XGNetTime")
    FDateTime BeijingDateTime = FDateTime();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "XGNetTime")
    FDateTime UTCDateTime = FDateTime();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "XGNetTime")
    FXGSampleNetTimeRespMessage RespMessage;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "XGNetTime")
    FString RawMessage = TEXT("");
};
```

结构体作为返回数据的容器，所有字段公开给蓝图使用。支持嵌套结构体（`RespMessage` 内嵌 `FXGSampleNetTimeRespMessage`）和 `TArray<FString>`。

## 委托定义：传递异步结果

```cpp
DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(
    FXGSampleNetTimeDelegate,
    FGuid, AsyncID,
    bool, bResult,
    FString, Message,
    FXGSampleNetTimeRespInfo, RespInfo
);
```

- `DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams`：四个参数的多播委托
- `FGuid AsyncID`：唯一标识，用于区分多个异步调用实例
- `bool bResult`：执行结果是否成功
- `FString Message`：附带的消息描述
- `FXGSampleNetTimeRespInfo RespInfo`：实际返回数据

所有委托参数签名保持一致，便于统一处理。

## 三引脚设计

```cpp
UPROPERTY(BlueprintAssignable)
FXGSampleNetTimeDelegate Then;

UPROPERTY(BlueprintAssignable)
FXGSampleNetTimeDelegate OnSuccess;

UPROPERTY(BlueprintAssignable)
FXGSampleNetTimeDelegate OnFail;
```

- **Then**：节点启动时立即触发，通知调用方"请求已发出，等待结果"
- **OnSuccess**：异步操作成功时触发
- **OnFail**：异步操作失败时触发

三个引脚使用同一委托类型，保证了调用方接口的一致性。

## HideThen 元数据

```cpp
UCLASS(meta = (HideThen = true))
```

`HideThen = true` 会隐藏 `UBlueprintAsyncActionBase` 默认的 `Then` 引脚，允许使用自定义的 `UPROPERTY(BlueprintAssignable)` 委托引脚替代。这样可以在自定义引脚上携带类型化的返回数据，而非原始基类的空 Then 引脚。

## 工厂函数模式

```cpp
UFUNCTION(BlueprintCallable, meta = (
    BlueprintInternalUseOnly = "true",
    WorldContext = "WorldContextObject",
    DisplayName = "XGSampleHttpTimeAsyncAction",
    Keywords = "XG Sample Net Time"),
    Category = "XGSample|NetTime")
static UXGSampleHttpTimeAsyncAction* XGSampleHttpTimeAsyncAction(
    UObject* WorldContextObject,
    EXGSampleNetTimeType InNetTimeType);
```

- `BlueprintInternalUseOnly = "true"`：工厂函数在蓝图中不直接显示，而是作为异步节点的创建入口
- `WorldContext = "WorldContextObject"`：指定上下文参数，用于获取 GameInstance
- `static` 构造函数：创建 `NewObject` 并注册到 GameInstance
- 返回值类型即异步动作类本身，蓝图会自动将返回值展开为节点的执行引脚

## 生命周期：NewObject + RegisterWithGameInstance

```cpp
UXGSampleHttpTimeAsyncAction* AsyncAction = NewObject<UXGSampleHttpTimeAsyncAction>();
AsyncAction->NetTimeType = InNetTimeType;
AsyncAction->RegisterWithGameInstance(WorldContextObject);
return AsyncAction;
```

- `NewObject<>()`：在 UE 反射系统中创建对象实例，不依赖 Actor
- `RegisterWithGameInstance()`：将异步动作注册到 GameInstance 中，保证其在异步操作完成前不会被 GC 回收
- 若不调用 `RegisterWithGameInstance`，`NewObject` 创建的对象在蓝图引脚连接完成后可能被 GC 回收导致崩溃

## 析构与资源释放

```cpp
UXGSampleHttpTimeAsyncAction::~UXGSampleHttpTimeAsyncAction()
{
    RealeaseResources();
}
```

- 析构函数中调用 `RealeaseResources()`，确保对象销毁时清理所有绑定的委托
- `.generated.h` 的包含必须放在所有头文件包含的最后，且文件名需与类定义所在的文件基本名保持一致（Hot-Reload 时 UE 按文件名查找生成的代码）

> **代码位置**：[XGSampleHttpTime.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/025_HttpTime/XGSampleHttpTime.h) — 枚举、结构体、委托和类定义
>
> **字幕位置**：025 第二十五章 002
