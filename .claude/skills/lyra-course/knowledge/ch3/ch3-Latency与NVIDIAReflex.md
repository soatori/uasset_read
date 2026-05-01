# Latency 与 NVIDIA Reflex

## 概述

Lyra 集成了 NVIDIA Reflex 低延迟技术，通过 ILatencyMarkerModule 接口注入延迟标记，在渲染管线的关键阶段标记时间戳，实现端到端延迟的精确测量和可视化。

## ILatencyMarkerModule

NVIDIA Reflex 的模块化延迟标记接口，定义了延迟标记的注入方式和标记类型。

### 延迟标记注入

通过 `SetCustomLatencyMarker` 在渲染管线的指定阶段注入时间戳标记：

```
具体阶段 → SetCustomLatencyMarker(markerType)
  → NvAPI_D3D_SetLatencyMarker(..., markerType, frameID)
  → NVIDIA Reflex 驱动记录时间戳
```

### 自定义标记类型（推荐范围）

| 标记类型 | 推荐值范围 |
|----------|-----------|
| NVIDIA Reflex 内置标记 | 0x0000 ~ 0x00FF |
| 应用自定义标记 | 0x1000 以上 |

自定义标记需绑定具体帧号（frameID），确保延迟测量与渲染帧对齐。

## LatencyFlashIndicators

NVIDIA Reflex 延迟的可视化调试工具，通过颜色闪烁指示各管线阶段的延迟状态：

| 颜色 | 对应阶段 | 含义 |
|------|---------|------|
| 红色 | SlateTick | UI 逻辑更新延迟 |
| 绿色 | SlatePaint | UI 渲染绘制延迟 |
| 蓝色 | RenderThread | 渲染线程处理延迟 |
| 黄色 | GPU | GPU 渲染延迟 |

### ELatencyStage 枚举

定义延迟追踪的管线阶段：

| 阶段 | 说明 |
|------|------|
| 输入采样 | 从输入设备到游戏逻辑 |
| 游戏逻辑 | 游戏线程处理输入 |
| 渲染提交 | 渲染线程提交渲染命令 |
| GPU 执行 | GPU 执行渲染命令 |
| 显示输出 | 最终帧输送到显示器 |

## Lyra 中的集成

ULyraSettingsLocal 中与延迟相关的功能：

- `FLyraPerformanceStatCache`：性能统计缓存，收集各阶段的延迟数据
- 延迟标记作为性能统计的一部分，通过 PerfStatDisplayState 系统决定是否在 HUD 上显示

## 设置 UI 中的延迟选项

通过 `ULyraGameSettingRegistry` 注册延迟相关的设置项，用户可在设置界面中选择是否显示延迟指示器和性能统计图表。
