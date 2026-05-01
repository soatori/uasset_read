# 属性同步与 OnRep 通知

## 概述

属性同步（Property Replication）是 UE 网络框架将服务器上的属性值同步到客户端的内置机制。属性同步**只能从服务器到客户端**，客户端永远不会向服务器发送属性更新。

## 启用属性同步

需满足三个条件：

1. Actor 开启了网络复制：`bReplicates = true`
2. 属性标记了 `UPROPERTY(Replicated)` 或 `UPROPERTY(ReplicatedUsing = OnRep_FunctionName)`
3. 在 `GetLifetimeReplicatedProps()` 中通过 `DOREPLIFETIME` 注册

## DOREPLIFETIME 注册

所有要同步的属性必须在 `GetLifetimeReplicatedProps` 中注册：

```cpp
#include "Net/UnrealNetwork.h"

void AMyActor::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(AMyActor, Health);
}
```

## 基础示例：XGNetDerivedRep

代码位置：[026_Net/XGNetDerivedRep.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/026_Net/XGNetDerivedRep.h)

```cpp
UCLASS()
class AXGNetDerivedRep : public AActor
{
    GENERATED_BODY()
public:
    UPROPERTY(Replicated)
    uint32 Health;
};
```

在 Tick 中仅在专用服务器上修改 Health：

```cpp
void AXGNetDerivedRep::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    if (GetWorld()->GetNetMode() == NM_DedicatedServer)
    {
        Health++;
    }
}
```

关键点：
- 属性标记 `Replicated` 后自动声明 `ReplicatedUsing` 规范
- 服务器上修改 → 自动同步到所有客户端
- 同步跳过中间值：值从 100→200→300，客户端最终看到 300，不保证看到 200

## OnRep_Notify 三种签名

代码位置：[026_Net/XGNetDerivedRepUsing.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/026_Net/XGNetDerivedRepUsing.h)

声明方式：`UPROPERTY(ReplicatedUsing = OnRep_Health)`

### 签名 1：无参数

```cpp
void OnRep_Health();
```

最简单的通知形式，不关心旧值。

### 签名 2：const 引用

```cpp
void OnRep_Health(const int32& LastValue);
```

通过 const 引用接收旧值，避免拷贝。

### 签名 3：值拷贝

```cpp
void OnRep_Health(int32 LastValue);
```

通过值拷贝接收旧值。

三种签名中引擎会自动匹配调用，推荐使用签名 2（const 引用），兼具效率和安全性。

## REPNOTIFY_Always vs REPNOTIFY_OnChange

通过 `DOREPLIFETIME` 的第四个参数控制 OnRep 触发条件：

```cpp
DOREPLIFETIME(Class, Property);                                    // 默认 OnChange
DOREPLIFETIME(Class, Property, REPNOTIFY_Always);                  // 每次同步都触发 OnRep
DOREPLIFETIME(Class, Property, REPNOTIFY_OnChange);                // 值变化时才触发 OnRep
```

| 模式 | 行为 |
|------|------|
| `REPNOTIFY_OnChange`（默认） | 属性值实际变化时才触发 OnRep |
| `REPNOTIFY_Always` | 即使值未变化，每次同步都触发 OnRep。可用于条件复制中强制回调 |

## Blueprint 与 C++ 的 OnRep 差异

| 差异点 | C++ | Blueprint |
|--------|-----|-----------|
| 服务器触发 OnRep | 不触发 | Set 节点自动触发（含服务器） |
| 主动调用需求 | 服务器上修改后需手动调用 OnRep 相关逻辑 | 不需额外处理 |

在 C++ 中，如果在服务器上修改了属性值，OnRep 在服务器上不会自动触发。因此需要在修改逻辑中主动处理：

```cpp
// 服务器修改 Health
Health = NewValue;
// 需要手动调用 OnRep 逻辑（或直接执行相关处理）
OnRep_Health(OldValue);
```

而在蓝图中，使用 Set 节点设置 Replicated 属性时，会自动触发 OnRep，即使在服务器上也触发。
