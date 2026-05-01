# 单张与多张 WebP 的线程交互模型

## 概述

WebP 生成涉及三个线程的协作：GameThread（发起）、RenderThread（截图）、WorkerThread（编码）。理解各线程间的数据流向是掌握本案例的关键。

## 单张 WebP 线程交互

### 交互流程

```
 ┌──────────┐     ①发起截图        ┌──────────┐
 │GameThread│ ──────────────────→  │RenderThread│
 │          │                       │           │
 │  ⑤回调   │ ←────── ④像素数据 ──── │  ②渲染   │
 │  主线程   │                       │  ③截图   │
 └────┬─────┘                       └───────────┘
      │
      │ ⑥拷贝像素数据 + 发起 AsyncTask
      ▼
 ┌──────────┐     ⑦调用编码API     ┌──────────┐
 │WorkerThread│ ──────────────────→ │libwebp    │
 │             │                     │编码完成   │
 │  ⑧AsyncTask│ ←────────────────── │           │
 │  回主线程   │                     └──────────┘
 └────┬─────┘
      │
      │ ⑨触发蓝图回调
      ▼
 ┌──────────┐
 │GameThread│  → 通知用户生成结果
 └──────────┘
```

### 关键步骤

1. **GameThread**：获取 Subsystem，调用 `BeginSampleWebPOneShot()`，传入蓝图委托
2. **注册截图代理**：`OnScreenshotCaptured().AddUObject()`
3. **发起截图**：`FScreenshotRequest::RequestScreenshot(false)`
4. **RenderThread**：下一帧渲染完成后触发代理，返回像素数据
5. **GameThread 回调**：在 `ScreenShotCallback` 中拷贝像素数据
6. **发起异步编码**：`AsyncTask` 或自定义线程中调用 `GenerateStaticWebpPicture()`
7. **WorkerThread**：执行 CPU 密集的 WebP 编码
8. **AsyncTask 回调 GameThread**：`AsyncTask(ENamedThreads::GameThread, ...)`
9. **GameThread**：触发蓝图委托，通知完成/失败，清理资源

### 同一时间只允许一个截图

使用 `bool bWorking` 标志防止重复触发：

```cpp
// [XGSampleWebPOneShotSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Subsystem/XGSampleWebPOneShotSubsystem.h)
bool bWorking = false;
```

- `BeginSampleWebPOneShot` 中检查 `bWorking`，若为 `true` 则直接 `return`
- 开始时设为 `true`，编码完成后 `AsyncTask` 回调中设为 `false`

## 多张 WebP 线程交互

### 交互流程

```
 ┌──────────┐   BeginRecord → Tick每帧发起截图   ┌──────────┐
 │GameThread│ ─────────────────────────────────→ │RenderThread│
 │          │                                      │           │
 │  每帧回调 │ ←────── 每帧返回像素数据 ───────────── │  逐帧截图 │
 └────┬─────┘                                      └───────────┘
      │
      │ 累积 N 帧像素数据 + 时间戳
      │
      │ EndRecord → AsyncTask
      ▼
 ┌──────────┐   调用 GenerateDynamicWebpPicture   ┌──────────┐
 │WorkerThread│ ────────────────────────────────→ │libwebp    │
 │             │                                   │AnimEncoder│
 │  AsyncTask  │ ←──────────────────────────────── │           │
 │  回主线程   │                                   └──────────┘
 └────┬─────┘
      │
      │ 触发蓝图回调 (bFinishGenerate)
      ▼
 ┌──────────┐
 │GameThread│
 └──────────┘
```

### 与单张的关键区别

| 维度 | 单张 | 多张 |
|------|------|------|
| 截图频率 | 一次 | 每帧（Tick 驱动） |
| 状态管理 | `bWorking` bool | `EXGSampleWebpProcessType` 枚举（None/Recording/Generating） |
| 编码 API | `WebPEncodeRGBA` | `WebPAnimEncoder` 系列 |
| 数据结构 | `TArray<FColor>` | `TArray<TArray<FColor>>` + `TArray<int32>`（时间戳） |
| 线程安全 | 简单（一次性） | 需要 `FCriticalSection` 保护累积中的数据 |
| 需要 Tick | 否 | 是（继承 `FTickableGameObject`） |

## 为什么编码必须在异步线程？

- WebP 编码是 **CPU 密集型** 操作
- 一张 1920×1080 图片编码约需 10~30ms
- 多张动态图按 N 倍增长
- 同步调用会阻塞 GameThread → 游戏卡死

## 委托的两种使用方式

### 内部委托（Native Delegate）

```cpp
// 用于内部 Subsystem 流程控制
DECLARE_DELEGATE_OneParam(FSampleWebPOneShotCallBack, bool)
```

在 `Initialize()` 中通过 `BindUObject(this, &ThisClass::SampleWebPOneShotCallBackMethod)` 绑定，不暴露给蓝图。

### 蓝图委托（Dynamic Delegate）

```cpp
// 用于通知蓝图用户
DECLARE_DYNAMIC_DELEGATE_OneParam(FSampleWebPOneShotCallBackBP, bool, bFinishGenerate)
```

由用户在蓝图中传入，编码完成后触发。

### 两层委托的必要性

- 内部委托：控制 Subsystem 内部状态流转（编码完成 → 清理截图代理 → 设置工作状态），**固定不变**
- 蓝图委托：让用户定义自己的后续逻辑（成功做什么、失败做什么），**每次可能不同**

## 拷贝数据的必要性

截图回调返回的 `const TArray<FColor>&` 是引用，回调结束后可能失效。传给异步线程前必须**深度拷贝**一份：

```cpp
TArray<FColor> CopiedColors = InColors;  // 值拷贝
```

如果不拷贝，异步线程访问时原数据可能已被释放或覆盖。
