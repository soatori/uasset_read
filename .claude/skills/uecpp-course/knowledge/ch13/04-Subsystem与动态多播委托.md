# Subsystem 与动态多播委托

## 模式概述

Subsystem 作为全局可访问的单例，很适合作为事件分发中心。结合第九章的动态多播委托（Dynamic Multicast Delegate），可以实现 Subsystem 统一管理事件、多个监听者（Actor、Blueprint）分别响应的架构模式。

## 声明委托类型

在 Subsystem 头文件中，使用 `DECLARE_DYNAMIC_MULTICAST_DELEGATE` 宏声明委托类型：

```cpp
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(
    FXGSubsystemActorLocation,
    FString, InActionName,
    int32,   InActionIndexTime
);
```

- 必须放在 `.generated.h` 包含（#include）**之前**
- 参数命名规则：`DECLARE_DYNAMIC_MULTICAST_DELEGATE_{参数数量}Params`
- 上限为 4 个参数

## 在 Subsystem 中暴露委托

```cpp
UCLASS()
class UXGSimpleSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    UPROPERTY(BlueprintAssignable)
    FXGSubsystemActorLocation XGSubsystemActorLocationDelegate;
};
```

- `UPROPERTY(BlueprintAssignable)` 标记允许蓝图中绑定事件
- 委托成员变量名任意，通常描述事件含义

## 触发广播

在 Subsystem 的方法中调用 `Broadcast` 通知所有监听者：

```cpp
void UXGSimpleSubsystem::CallLocaion(FString InActionName, int32 InActionIndex)
{
    XGSubsystemActorLocationDelegate.Broadcast(InActionName, InActionIndex);
}
```

- `Broadcast` 是动态多播委托的固有方法
- 参数类型和数量必须与 DECLARE 声明一致
- C++ 中调用 `Broadcast` 会同时触发所有 C++ 和 Blueprint 中绑定的回调

## Blueprint 侧使用

1. **获取 Subsystem** — 使用 "Get Game Instance Subsystem" 节点，类型选择 `UXGSimpleSubsystem`
2. **绑定事件** — 拖出 `XGSubsystemActorLocationDelegate` 引脚，选择 "Assign"
3. **处理回调** — 在生成的 Event 节点中编写处理逻辑
4. **可选：解绑** — 在合适的生命周期点解绑事件

## 架构优势

```
Subsystem（事件源）
    ├── Broadcast("跳跃", 1) ──→ Blueprint Actor A：播放跳跃动画
    ├── Broadcast("攻击", 2) ──→ Blueprint Actor B：播放攻击动画
    └── Broadcast("死亡", 3) ──→ Blueprint Actor C：播放死亡动画 + UI
```

- 解耦：Subsystem 不关心谁在监听，监听者不关心事件从哪来
- 跨 C++/Blueprint 边界：C++ 端广播，Blueprint 端处理
- 集中管理：所有同类事件的触发点在同一个 Subsystem 中

## 配套代码

- [XGSimpleSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/016_Subsystem/XGSimpleSubsystem.h) — 委托声明与 BlueprintAssignable 属性
- [XGSimpleSubsystem.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/016_Subsystem/XGSimpleSubsystem.cpp) — CallLocation 中 Broadcast 调用
