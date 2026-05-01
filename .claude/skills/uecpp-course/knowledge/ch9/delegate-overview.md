# 委托系统概述

## 委托的本质

委托是 UE 中的**类型安全的函数指针**。与 C/C++ 原生函数指针相比，委托提供：
- **类型安全**：签名（参数类型、返回值）在编译期检查
- **对象安全**：`UObject` 和 `TSharedPtr` 绑定自动管理生命周期
- **灵活性**：支持 Lambda、成员函数、静态函数、全局函数等多种目标

## 四种委托类型

| 类型 | 声明宏 | 关系 | 返回值 | 蓝图支持 | 核心区别 |
|------|--------|------|--------|----------|----------|
| 单播 (Single-cast) | `DECLARE_DELEGATE` | 一对一 | 支持 | 否 | 绑定即替换，可接收返回值 |
| 多播 (Multicast) | `DECLARE_MULTICAST_DELEGATE` | 一对多 | 不支持 | 否 | 多个绑定同步触发，无返回值 |
| 动态单播 (Dynamic Single) | `DECLARE_DYNAMIC_DELEGATE` | 一对一 | 支持 | 是 | 蓝图可绑定，配置式使用 |
| 动态多播 (Dynamic Multicast) | `DECLARE_DYNAMIC_MULTICAST_DELEGATE` | 一对多 | 不支持 | 是 | `UPROPERTY(BlueprintAssignable)` 暴露，蓝图 Bind Event |

## 声明宏体系

### 宏命名规则

```
DECLARE_[DYNAMIC_][MULTICAST_]DELEGATE[_RetVal][_OneParam/_TwoParams/...](Name, [RetValType,] [ParamTypes...])
```

- **Native 委托**：参数只需类型，无需变量名
- **Dynamic 委托**：参数需要类型和变量名（因为是反射系统，变量名用于蓝图匹配）
- **前缀顺序**：`_RetVal` 在前，`_Params` 在后
- **尾缀**：单参数用 `_OneParam`，多参数加 's' 用 `_TwoParams`/`_ThreeParams` 等

### 示例对照

```cpp
// Native 单播 — 无返回值，无参数
DECLARE_DELEGATE(FXGSingDelegatePrintLocation);

// Native 单播 — 有返回值，一个参数
DECLARE_DELEGATE_RetVal_OneParam(FVector, FXGSingDelegateGetLocation, FString);

// Native 多播 — 一个参数
DECLARE_MULTICAST_DELEGATE_OneParam(FXGMulityDelegate, FString);

// Dynamic 单播 — 两个参数（注意需要变量名）
DECLARE_DYNAMIC_DELEGATE_TwoParams(FXGDynamicTwo, FString, InName, int32, InMoney);

// Dynamic 单播 — 有返回值，一个参数
DECLARE_DYNAMIC_DELEGATE_RetVal_OneParam(int32, FXGDynamicRetOne, FString, InName);

// Dynamic 多播 — 三个参数
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FXGDynamicMultiThree, FString, InName, int32, InHealth, int32, InMana);
```

## 核心操作对照

| 操作 | 单播 | 多播 | 动态单播 | 动态多播 |
|------|------|------|----------|----------|
| 绑定 | `Bind*()` | `Add*()` | `BindUFunction()` / `=` | `AddDynamic()` |
| 执行 | `Execute()` / `ExecuteIfBound()` | `Broadcast()` | `Execute()` / `ExecuteIfBound()` | `Broadcast()` |
| 解绑单个 | 自动替换 | `Remove(Handle)` / `Remove*()` | `Clear()` | `RemoveDynamic()` |
| 清空全部 | `Clear()` | `Clear()` | `Clear()` | `Clear()` |
| 是否绑定 | `IsBound()` | — | `IsBound()` | — |

## 文件结构

```
subtitles/009第九章委托/ — 9 个字幕文件
code/.../012_Delegate/   — 8 个代码文件
  ├── XGSingleDelegateActor.h/.cpp      — 单播各种绑定方式
  ├── XGMultiDelegateActor.h/.cpp       — 多播各种绑定方式 + 执行 Actor
  ├── XGDynamicSingleActor.h/.cpp       — 动态单播
  └── XGDynamicMulityDelegateActor.h/.cpp — 动态多播
```

> **代码位置**：[012_Delegate/](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/012_Delegate/)
