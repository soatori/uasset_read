# 性能与渲染设置

## 概述

Lyra 的性能与渲染系统处理帧率限制、画质等级、设备配置、平台特定渲染设置等。核心类包括 ULyraPlatformSpecificRenderingSettings（平台渲染设置）、ULyraPerformanceSettings（桌面性能设置）、LyraSettingsHelpers（移动端品质辅助）。

## ULyraPlatformSpecificRenderingSettings

继承自 `UPlatformSettings`，通过 `PerPlatformSettings` 机制在 `DefaultEngine.ini` 中按平台配置。

### 属性

| 属性 | 类型 | 用途 |
|------|------|------|
| DefaultDeviceProfileSuffix | FString | 默认设备配置后缀 |
| UserFacingDeviceProfileOptions | TArray<FLyraQualityDeviceProfileVariant> | 用户可选的设备配置变体 |
| bSupportsGranularVideoQualitySettings | bool | 是否支持精细视频画质设置 |
| bSupportsAutomaticVideoQualityBenchmark | bool | 是否支持自动画质基准测试 |
| FramePacingMode | ELyraFramePacingMode | 帧率控制模式 |
| MobileFrameRateLimits | TArray<int32> | 移动端可用帧率列表 |

### ELyraFramePacingMode

| 模式 | 说明 | 适用平台 |
|------|------|---------|
| DesktopStyle | 手动帧率限制，用户可选是否垂直同步 | 桌面平台 |
| ConsoleStyle | 通过设备配置选择呈现间隔控制帧率 | 主机 |
| MobileStyle | 用户从设备配置允许的帧率中选择 | 移动端 |

### FLyraQualityDeviceProfileVariant

| 属性 | 说明 |
|------|------|
| DisplayName | UI 显示名称 |
| DeviceProfileSuffix | 追加到基础设备配置名的后缀 |
| MinRefreshRate | 启用所需的最低刷新率 |

## ULyraPerformanceSettings

继承自 `UDeveloperSettingsBackedByCVars`，配置于 `DefaultGame.ini` 的 `[LyraPerformanceSettings]` 节。

### 属性

| 属性 | 用途 |
|------|------|
| DesktopFrameRateLimits | 桌面平台可选的帧率限制列表 |
| UserFacingPerformanceStats | 用户可启用的性能统计组 |

### FLyraPerformanceStatGroup

| 属性 | 用途 |
|------|------|
| VisibilityQuery | 基于平台特性的可见性查询（GameplayTag 查询） |
| AllowedStats | 查询通过时可用的统计集合 |

## LyraSettingsHelpers

位于 `LyraSettingsLocal.cpp` 的命名空间，提供移动端品质管理辅助函数。

### TMobileQualityWrapper<T>

模板包装类，用于解析 CVar 驱动的阈值规范。CVar 格式为 `"FPS:Value,FPS2:Value2,..."`，表示在不同帧率阈值下应用的品质限制值。

### 关键函数

| 函数 | 用途 |
|------|------|
| HasPlatformTrait | 检查平台是否具有指定特性 |
| GetHighestLevelOfAnyScalabilityChannel | 获取任意可伸缩通道的最高等级 |
| FillScalabilitySettingsFromDeviceProfile | 从设备配置填充可伸缩性设置 |
| ConstrainFrameRateToBeCompatibleWithOverallQuality | 限制帧率以兼容整体画质 |

### 移动端 CVar

| CVar | 格式 | 用途 |
|------|------|------|
| Lyra.DeviceProfile.Mobile.OverallQualityLimits | FPS:MaxQuality,FPS2:MaxQuality2 | 帧率对应的最高画质限制 |
| Lyra.DeviceProfile.Mobile.ResolutionQualityLimits | FPS:MaxResQuality | 帧率对应的最高分辨率限制 |
| Lyra.DeviceProfile.Mobile.ResolutionQualityRecommendation | FPS:Recommendation | 帧率对应的推荐分辨率 |
| Lyra.DeviceProfile.Mobile.DefaultFrameRate | int | 移动端默认帧率（30） |
| Lyra.DeviceProfile.Mobile.MaxFrameRate | int | 移动端最大帧率（30） |

## 帧率控制

### 桌面帧率

桌面平台通过 `GetEffectiveFrameRateLimit()` 计算实际帧率限制。该函数根据当前状态（前台/后台/菜单/电池）取各限制值的最小值。

### 控制台帧同步

控制台平台通过设备配置驱动目标帧率和帧同步类型：

```cpp
CVarDeviceProfileDrivenTargetFps     // Lyra.DeviceProfile.Console.TargetFPS
CVarDeviceProfileDrivenFrameSyncType // Lyra.DeviceProfile.Console.FrameSyncType
```

### 移动端帧率

移动端帧率控制通过 `UpdateMobileFramePacing()` 实现：

1. 从设备配置读取默认和最大帧率
2. 用户选择期望的帧率（`DesiredMobileFrameRateLimit`）
3. 根据帧率自动钳制分辨率画质（`ClampMobileResolutionQuality`）
4. 设置平台帧率加速器

```cpp
void ClampMobileResolutionQuality(int32 TargetFPS);  // 根据目标帧率钳制分辨率
void RemapMobileResolutionQuality(int32 FromFPS, int32 ToFPS); // 帧率切换时重新映射
```

### 动态分辨率

通过 `UpdateDynamicResFrameTime(float TargetFPS)` 根据目标帧率更新动态分辨率帧时间。

## 设备配置

### 设备配置后缀

控制台和移动端平台使用 `DeviceProfileSuffix` 机制切换画质预设：

1. `UserChosenDeviceProfileSuffix` 持久化用户选择
2. 热修复时调用 `OnHotfixDeviceProfileApplied()`
3. `UpdateGameModeDeviceProfileAndFps()` 应用当前模式对应的设备配置

### 前端性能设置

`SetShouldUseFrontendPerformanceSettings(bool bInFrontEnd)` 控制前端界面下的性能设置（降低画质以优化 UI 响应）。
