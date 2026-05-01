# 多张 WebP 生成：Subsystem 与蓝图接口

## 概述

`UXGSampleWebPMultiShotSubsystem` 是生成多张动态 WebP 的核心控制器。它负责管理截图录制状态、逐帧收集像素数据、触发异步编码、并将结果回调给蓝图。

代码：[XGSampleWebPMultiShotSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Subsystem/XGSampleWebPMultiShotSubsystem.h)

## 状态机设计

多张生成分为三个处理状态：

```cpp
// [XGSampleWebPType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Type/XGSampleWebPType.h)
enum class EXGSampleWebpProcessType : uint8
{
    None,        // 空闲
    Recording,   // 正在录制（逐帧截图）
    Generating,  // 正在生成（异步编码）
    Max
};
```

状态转换：

```
None  ──BeginRecord──→  Recording
Recording ──EndRecord──→  Generating
Generating ──回调用完成──→  None
```

## 核心成员变量

| 变量 | 类型 | 用途 |
|------|------|------|
| `ProcessType` | `EXGSampleWebpProcessType` | 当前处理状态 |
| `WebPColor` | `TArray<TArray<FColor>>` | 收集的所有帧像素数据 |
| `WebpTimestepMillisecond` | `TArray<int32>` | 收集的所有帧时间戳 |
| `ScreenHandle` | `FDelegateHandle` | 截图代理句柄 |
| `FinshWebpBPDelegate` | `FXGWebpFinishGenerateMultiWebp` | 完成时回调蓝图的动态委托 |
| `SampleWebPMultiCallBack` | `FSampleWebPMultiCallBack` | 内部使用的原生委托 |
| `XGWebpMutex` | `FCriticalSection` | 线程安全锁 |
| `WebpPictureInformation` | `TSharedPtr<FXGSampleWebpPictureInformation>` | 图片裁剪区域 |

## 核心流程

### BeginRecord（开始记录）

1. 检查状态（如果已在 `Recording` 或 `Generating`，拒绝）
2. 保存图片路径和裁剪信息
3. 注册截图回调 `ScreenShotCallback`
4. 设置状态为 `Recording`

### Tick 驱动的逐帧录制

`UXGSampleWebPMultiShotSubsystem` 继承 `FTickableGameObject`，每帧自动调用 `Tick()`：

1. 检查当前是否处于 `Recording` 状态
2. 调用 `RecordOneFrame(DeltaTime)`：
   - 发起 `FScreenshotRequest::RequestScreenshot(false)`
   - 刷新渲染命令 `FlushRenderingCommands()`
3. 截图回调 `ScreenShotCallback()` 中：
   - 将像素数据拷贝追加到 `WebPColor`
   - 记录当前时间戳到 `WebpTimestepMillisecond`

### EndRecord（结束记录）

1. 设置状态为 `Generating`
2. 移除截图回调
3. 发起异步任务：
   - 创建 `AsyncTask` 或在后台线程中调用 `FXGSampleWebPCore::GenerateDynamicWebpPicture()`
   - 将结果通过 `AsyncTask` 回调到 GameThread
4. GameThread 回调中：
   - 触发蓝图动态委托 `FinshWebpBPDelegate`
   - 调用 `ResetRecord()` 清理状态和数据

### ResetRecord

清理所有中间数据，恢复到 `None` 状态。

## 蓝图暴露的委托

```cpp
// [XGSampleWebPType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Type/XGSampleWebPType.h)
DECLARE_DYNAMIC_DELEGATE_OneParam(FXGWebpFinishGenerateMultiWebp, bool, bFinishGenerate);
```

蓝图使用方式：
1. 调用 `BeginRecord` 或 `BeginRecordFullViewport` 开始录制
2. 在需要停止时调用 `EndRecord`，传入动态委托事件
3. 委托触发时参数 `bFinishGenerate` 表示是否成功生成

## BPLibrary 暴露的蓝图接口

| 蓝图函数 | 参数 | 说明 |
|---------|------|------|
| `BeginRecord` | WorldContext, Path, PictureInfo, bBegin (out) | 开始录制，指定裁剪区域 |
| `BeginRecordFullViewport` | WorldContext, Path, bBegin (out) | 开始录制，全视口 |
| `EndRecord` | WorldContext, Delegate | 结束录制并生成 |

## FXGSampleWebpPictureInformation

图片裁剪信息结构体：

```cpp
// [XGSampleWebPType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Type/XGSampleWebPType.h)
USTRUCT(BlueprintType)
struct FXGSampleWebpPictureInformation
{
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 X0, Y0, X1, Y1;  // 左上角 (X0,Y0) 到 右下角 (X1,Y1)
};
```

用于指定截图裁剪区域（例如只截取场景中某个人物的头像区域）。

## 线程安全

- `FCriticalSection XGWebpMutex` 保护 `WebPColor` 和 `WebpTimestepMillisecond` 的并发访问
- 截图回调可能在 RenderThread 触发，而 Tick 在 GameThread
- 异步编码任务在 WorkerThread
