# Tick 驱动纹理更新机制

## 概述

动态 WebP 展示的核心是：已解码的逐帧像素数据 + 每帧根据时间戳切换纹理。`UXGSampleWebpShowMultiSubsystem` 通过 `FTickableGameObject` 接口实现这一机制。

代码：[XGSampleWebpShowMultiSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/XGSampleWebP/Public/Subsystem/XGSampleWebpShowMultiSubsystem.h)

## Tick 驱动的帧切换逻辑

### 数据结构

```
PicturesColors:      [Frame0][Frame1][Frame2]...[FrameN]
WebpTimestepMillisecond: [16]    [40]    [100]  ...[N_ms]
```

时间戳是毫秒级的绝对时间点，表示该帧应该在动画的第几毫秒显示。

### Tick 实现

```cpp
void Tick(float DeltaTime)
{
    if (LoadAndShowStatus != EXGSampleWebpLoadAndShowType::Showing)
        return;

    CurrentMillisecond += DeltaTime * 1000;  // 秒转毫秒

    // 查找当前时间应显示的帧
    int32 NewIndex = WebpShowIndex;
    for (int32 i = WebpShowIndex + 1; i < WebpTimestepMillisecond.Num(); ++i)
    {
        if (CurrentMillisecond >= WebpTimestepMillisecond[i])
        {
            NewIndex = i;
        }
        else
        {
            break;
        }
    }

    // 如果帧索引变化，更新纹理
    if (NewIndex != WebpShowIndex)
    {
        WebpShowIndex = NewIndex;
        UpdateWebpTexture();
    }
}
```

### 帧查找逻辑

逐帧扫描时间戳数组，找到 `CurrentMillisecond >= WebpTimestepMillisecond[i]` 的最大索引。由于时间戳递增，可以用单向扫描优化。

## UpdateTextureRegions 纹理更新

### 方式一：UpdateTextureRegions（推荐）

通过 `UpdateTextureRegions()` 将像素数据写入已有的 `UTexture2D`，避免每次创建新纹理对象：

```cpp
FUpdateTextureRegion2D Region(0, 0, 0, 0, WebpWidth, WebpHeight);
WebpTexture->UpdateTextureRegions(
    0,                      // MipLevel
    1,                      // 区域数量
    &Region,
    WebpWidth * 4,          // SrcPitch（每行字节数）
    sizeof(FColor),         // SrcBpp（每像素字节数）
    (uint8*)PicturesColors[WebpShowIndex].GetData()
);
```

### 方式二：直接更新 PlatformData（也可行）

直接操作 `FTexturePlatformData` 的 Mip 数据，然后调用 `UpdateResource()`。但 `UpdateTextureRegions` 更高效（使用 `RHIUpdateTexture2D` 路径）。

## 循环播放处理

当 `CurrentMillisecond` 超过最后一帧的时间戳：

| 策略 | 处理方式 |
|------|---------|
| 保持最后一帧 | 当前实现：`WebpShowIndex` 不再递增 |
| 循环播放 | 将 `CurrentMillisecond` 归零，`WebpShowIndex` 重置为 0 |

当前实现采用的是"保持最后一帧"，因为 WebP 动画通常不要求循环。

## UTexture2D 生命周期管理

- `UTexture2D` 是 UObject，需要被 UPROPERTY 持有指针防止 GC
- 在 `Deinitialize()` 或 `ReleaseLoadedWebp()` 中释放
- `RF_Transient` 标志确保纹理不参与序列化

## 性能注意事项

| 操作 | 耗时 | 说明 |
|------|------|------|
| 创建 `UTexture2D` | ~1ms | 仅在加载时执行一次 |
| `UpdateTextureRegions` | <0.1ms | 每帧执行，开销极小 |
| 帧查找循环 | <0.01ms | 单向扫描，帧数 ≤ 100 |

### 对比：Media Player 框架

对于专业的音视频播放，UE 提供了 `IMediaPlayer` / `FMediaIOCapture` 框架。本章的实现是简化版，适用于"几张到几十张动态图"的场景，而非真正的视频播放。

## 完整展示流程

```
1. LoadWebp(Path, Delegate)
   ├── 异步解码 .webp → PicturesColors + Timestamps
   ├── 创建 UTexture2D
   ├── 设置第一帧纹理
   └── 回调蓝图 Delegate (bLoad=true, Texture, W, H)

2. 蓝图接收 Texture → 创建 MaterialInstanceDynamic → 设置 Texture Parameter → 应用材质

3. Tick() 每帧根据 ElapsedTime 切换帧
   └── UpdateTextureRegions()

4. ReleaseLoadedWebp()
   └── 释放 UTexture2D、清理数据
```
