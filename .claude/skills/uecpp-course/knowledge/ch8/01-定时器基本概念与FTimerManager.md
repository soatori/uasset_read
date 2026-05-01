# 定时器基本概念与 FTimerManager

## 概述

UE 定时器系统基于 **FTimerManager** 管理器 + **FTimerHandle** 句柄的设计模式。定时器不由开发者手动创建和销毁，而是通过 World 的 TimerManager 注册回调，由引擎在 Tick 间隙统一调度。

## 核心类型

### FTimerManager

定时器的集中管理器，单例化绑定到特定生命周期域：

```cpp
FTimerManager& TimerManager = GetWorldTimerManager();
```

访问入口 `GetWorldTimerManager()` 是 `AActor` 和 `UObject` 的快捷方法，等价于 `GetWorld()->GetTimerManager()`。

### FTimerHandle

定时器的轻量标识符（基于 `uint64` 的句柄结构），用于后续的暂停、恢复、查询和清理操作：

```cpp
FTimerHandle MyTimerHandle;
```

- 调用 `SetTimer` 时传入引用，句柄自动绑定到新创建的定时器
- 句柄为 0 表示无效（未绑定或已清理）
- 必须有持久存储（如成员变量），才能对定时器进行后续操作

## 定时器生命周期

### 创建

`SetTimer` 向 FTimerManager 注册一个定时器，绑定回调函数和时间参数。

### 运行

FTimerManager 在 Tick 间隙检查定时器是否到期，到期则执行回调。循环定时器会自动重置下一次触发。

### 销毁

| 销毁方式 | 机制 |
|----------|------|
| `ClearTimer(Handle)` | 手动清理指定定时器 |
| `ClearAllTimersForObject(Object)` | 清理关联某个 UObject 的所有定时器 |
| Actor 销毁 | Actor 销毁时，FTimerManager 自动清理绑定到该 Actor 的所有定时器 |
| World 卸载 | Level 切换时，World 级别的 TimerManager 被销毁，所有定时器自动清理 |

### 生命周期绑定层级

选择在哪个 FTimerManager 上注册定时器，决定了定时器的生命周期范围：

| 访问方式 | 生命周期 | 跨 Level 持久化 |
|----------|----------|----------------|
| `GetWorldTimerManager()` | World 级别，Level 切换时销毁 | 否 |
| `GetGameInstance()->GetTimerManager()` | GameInstance 级别，整个游戏会话存活 | 是 |

## 适用场景

- 延迟触发：某个事件发生后等待 N 秒再执行
- 周期检测：每秒检测一次某个条件是否满足
- 冷却计时：技能或道具的冷却倒计时
- 倒计时显示：UI 或世界空间的倒计时数值
- 节流控制：限制某个操作的执行频率

## 不适用场景（应使用多线程）

以下场景不应使用定时器，应使用多线程（FRunnable、Async 等）：

| 场景 | 原因 |
|------|------|
| 重型 I/O | 读取大 JSON 文件、大量磁盘读写 |
| 数据库访问 | SQL 查询等阻塞操作 |
| 网络通讯 | TCP/UDP/HTTP/WebSocket 数据传输 |
| 图片/视频处理 | 编解码、滤镜、渲染 |

定时器运行在 Game Thread，如果回调中执行阻塞操作，会直接卡死主线程、导致帧率骤降或应用无响应。

## 代码参考

- [TimerActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/011_Timer/TimerActor.h)
- [TimerActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/011_Timer/TimerActor.cpp)
