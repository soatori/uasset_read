# 音频系统

## 概述

Lyra 的音频系统由 ULyraAudioSettings 配置 ControlBus 引用，ULyraAudioMixEffectsSubsystem 在运行时加载 ControlBus 并应用用户音量设置。音频系统支持 HDR/LDR 动态范围切换、耳机模式（HRTF）以及多通道音量独立控制。

## ULyraAudioSettings

继承自 `UDeveloperSettings`，配置中的路径引用定义在 `DefaultGame.ini` 的 `[LyraAudioSettings]` 节。

### ControlBus 路径配置

| 属性 | 类型 | 用途 |
|------|------|------|
| DefaultControlBusMix | FSoftObjectPath | 默认基础 ControlBusMix |
| LoadingScreenControlBusMix | FSoftObjectPath | 加载屏幕 ControlBusMix |
| UserSettingsControlBusMix | FSoftObjectPath | 用户设置 ControlBusMix |
| OverallVolumeControlBus | FSoftObjectPath | 总音量 ControlBus |
| MusicVolumeControlBus | FSoftObjectPath | 音乐音量 ControlBus |
| SoundFXVolumeControlBus | FSoftObjectPath | 音效音量 ControlBus |
| DialogueVolumeControlBus | FSoftObjectPath | 对话音量 ControlBus |
| VoiceChatVolumeControlBus | FSoftObjectPath | 语音聊天音量 ControlBus |

### 动态范围效果链

| 属性 | 用途 |
|------|------|
| HDRAudioSubmixEffectChain | HDR 音频模式下的 Submix 效果链 |
| LDRAudioSubmixEffectChain | LDR 音频模式下的 Submix 效果链 |

## ULyraAudioMixEffectsSubsystem

继承自 `UWorldSubsystem`，在关卡开始时自动加载 ControlBus 并应用用户音量设置。

### 运行时持有的引用

| 属性 | 类型 | 来源 |
|------|------|------|
| DefaultBaseMix | USoundControlBusMix | 从 ULyraAudioSettings 加载 |
| LoadingScreenMix | USoundControlBusMix | 从 ULyraAudioSettings 加载 |
| UserMix | USoundControlBusMix | 从 ULyraAudioSettings 加载 |
| OverallControlBus | USoundControlBus | 从 ULyraAudioSettings 加载 |
| MusicControlBus | USoundControlBus | 从 ULyraAudioSettings 加载 |
| SoundFXControlBus | USoundControlBus | 从 ULyraAudioSettings 加载 |
| DialogueControlBus | USoundControlBus | 从 ULyraAudioSettings 加载 |
| VoiceChatControlBus | USoundControlBus | 从 ULyraAudioSettings 加载 |

### 生命周期

```
Initialize() → 从 ULyraAudioSettings 加载 ControlBus 路径
  → PostInitialize() → 完成初始化
  → OnWorldBeginPlay() → 应用默认 BaseMix
  → ApplyDynamicRangeEffectsChains(bHDRAudio) → 切换 HDR/LDR 效果链
  → 加载屏幕时：ApplyOrRemoveLoadingScreenMix()
  → Deinitialize() → 清理
```

### ApplyDynamicRangeEffectsChains

根据是否启用 HDR Audio，将 HDRSubmixEffectChain 或 LDRSubmixEffectChain 应用到对应的 Submix 上。当用户切换 HDR Audio 设置时，ULyraSettingsLocal 调用此方法更新效果链。

### 加载屏幕音频

`OnLoadingScreenStatusChanged` 回调监听加载屏幕状态变化，在加载屏幕打开时应用 `LoadingScreenMix`，关闭时移除。

## ControlBus 音频调制

UE5 Audio Modulation 系统通过 ControlBus 实现参数化音频控制。

### 核心概念

| 概念 | 说明 |
|------|------|
| ControlBus | 参数化控制总线，定义了值的范围和单位 |
| ControlBusMix | 多个 ControlBus 值的集合，作为整体激活/停用 |

### 音频调制链路

```
MetaSound/SoundClass → ControlBus 绑定
  → ControlBusMix 激活
    → 调制参数（音量/音高/滤波器等）
      → 最终音频输出
```

### 混音规则

| 规则 | 说明 |
|------|------|
| Union 模式 | 多个 Mix 同时激活时，取各值中的最大值 |
| Override 模式 | 直接覆盖为指定值 |

## HRTF 耳机模式

HRTF（Head-Related Transfer Function，头部相关传输函数）用于耳机音频定位。

### 实现原理

| 机制 | 说明 |
|------|------|
| 频谱滤波 | 根据声源方向对人耳频谱进行滤波 |
| ITD（Interaural Time Difference） | 双耳时间差，判断水平方位 |
| IID（Interaural Intensity Difference） | 双耳强度差，判断垂直方位 |

### Lyra 中的实现

```cpp
// ULyraSettingsLocal
bool IsHeadphoneModeEnabled() const;   // 是否启用耳机模式
void SetHeadphoneModeEnabled(bool bEnabled);  // 启用/禁用
bool CanModifyHeadphoneModeEnabled() const;   // 是否可修改（平台是否强制）
```

- `bUseHeadphoneMode`（Config 标记）持久化存储
- `bDesiredHeadphoneMode`（Transient 标记）运行时期望值
- 如果平台通过 CVar `au.DisableBinauralSpatialization` 强制设置，则 `CanModifyHeadphoneModeEnabled()` 返回 false

## 音频设备切换

```cpp
// ULyraSettingsLocal
FString GetAudioOutputDeviceId() const;
void SetAudioOutputDeviceId(const FString& InAudioOutputDeviceId);
```

切换时触发 `OnAudioOutputDeviceChanged` 事件，音频子系统响应并切换输出设备。
