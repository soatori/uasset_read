# 设置系统架构

## 概述

Lyra 的设置系统采用双层架构：本地设置（ULyraSettingsLocal）与共享设置（ULyraSettingsShared）。本地设置继承自 UGameUserSettings，存储机器绑定的配置（音频设备、视频分辨率、画质等）；共享设置继承自 ULocalPlayerSaveGame，存储用户绑定的配置（语言、色盲、字幕、灵敏度等）。双层设置通过 ULyraGameSettingRegistry 统一注册到设置 UI。

## UGameUserSettings 基类

UE5 的 UGameUserSettings 是游戏用户设置的引擎基类，数据存储于 `DefaultEngine.ini`（`[Script/Engine.GameUserSettings]` 节）。

### 初始化流程

```
音频设备初始化 → GEngine->LoadConfig()
  → UEngine::CreateGameUserSettings()
    → 构造 UGameUserSettings 单例
    → 读取 DefaultEngine.ini 配置
```

### 关键方法

| 方法 | 用途 |
|------|------|
| LoadSettings() | 从配置文件加载已保存的设置 |
| SaveSettings() | 将当前设置保存到配置文件 |
| ApplySettings() | 应用所有设置（包括非分辨率和分辨率设置） |
| ApplyNonResolutionSettings() | 应用除分辨率外的所有设置 |
| ValidateSettings() | 验证设置有效性 |
| GetOverallScalabilityLevel() | 获取整体画质等级（0~3：低/中/高/史诗） |
| SetOverallScalabilityLevel() | 设置整体画质等级 |

### Scalability 系统

Scalability::FQualityLevels 包含 11 个可调画质通道：

| 通道 | 说明 |
|------|------|
| ResolutionQuality | 分辨率质量（50~100） |
| ViewDistanceQuality | 视距 |
| AntiAliasingQuality | 抗锯齿 |
| ShadowQuality | 阴影 |
| GlobalIlluminationQuality | 全局光照 |
| ReflectionQuality | 反射 |
| PostProcessQuality | 后处理 |
| TextureQuality | 纹理 |
| EffectsQuality | 特效 |
| FoliageQuality | 植被 |
| ShadingQuality | 着色 |

整体画质等级（OverallScalabilityLevel）自动映射到各个通道的对应值。

## ULyraSettingsLocal

继承自 `UGameUserSettings`，通过 `DefaultEngine.ini` 替换引擎默认的 GameUserSettings 类。

```ini
[SystemSettings]
GameUserSettingsClass=/Script/LyraGame.LyraSettingsLocal
```

### 设置类别

| 类别 | 说明 |
|------|------|
| 音频 | 音量控制（Overall/Music/SoundFX/Dialogue/VoiceChat），音频输出设备切换，耳机模式（HRTF），HDR Audio |
| 视频 | 帧率限制（电池/菜单/后台/始终），显示伽马，分辨率模式确认 |
| 画质 | 整体画质等级，设备配置后缀，移动端 FPS 模式，移动端分辨率质量钳制 |
| 帧率 | 桌面帧率限制，控制台帧同步，移动端帧率模式 |
| 性能统计 | PerfStatDisplayState 系统 |
| 回放 | 自动记录回放，保留回放数量 |
| 控制器 | 控制器平台，控制器预设，输入配置名 |
| 安全区 | 安全区缩放 |

### 关键方法

| 方法 | 用途 |
|------|------|
| LoadSettings() | 加载设置（Override） |
| SetToDefaults() | 恢复默认设置 |
| ApplyNonResolutionSettings() | 应用非分辨率设置（音量、画质、帧率等） |
| GetOverallScalabilityLevel() | 获取整体画质等级 |
| SetOverallScalabilityLevel() | 设置整体画质等级 |
| OnExperienceLoaded() | Experience 加载完成时的回调 |
| OnHotfixDeviceProfileApplied() | 设备配置热修复应用回调 |

### 帧率限制层级

ULyraSettingsLocal 定义 4 种帧率限制模式：

| 属性 | 说明 |
|------|------|
| FrameRateLimit_OnBattery | 电池供电时帧率限制 |
| FrameRateLimit_InMenu | 菜单界面帧率限制 |
| FrameRateLimit_WhenBackgrounded | 后台运行时帧率限制 |
| FrameRateLimit_Always | 始终生效的帧率限制 |

实际帧率限制由 `GetEffectiveFrameRateLimit()` 根据当前状态取最小值。

### 音频音量控制

通过 ControlBus 系统实现 5 路音量控制：

| 音量通道 | ControlBus 绑定 | 默认值 |
|----------|----------------|--------|
| OverallVolume | OverallControlBus | 1.0 |
| MusicVolume | MusicControlBus | 1.0 |
| SoundFXVolume | SoundFXControlBus | 1.0 |
| DialogueVolume | DialogueControlBus | 1.0 |
| VoiceChatVolume | VoiceChatControlBus | 1.0 |

音量值通过 LoadUserControlBusMix 加载 ControlBusMix，调用 USoundControlBusMix 的 SetMixValue 应用。

### 性能统计显示

PerfStatDisplayState 系统控制 HUD 性能小部件的显示模式：

```cpp
ELyraStatDisplayMode // Hidden/TextOnly/GraphOnly/TextAndGraph
TMap<ELyraDisplayablePerformanceStat, ELyraStatDisplayMode> DisplayStatList
```

设置通过 SetPerfStatDisplayState() 修改，变更时触发 PerfStatSettingsChanged 事件。

## ULyraSettingsShared

继承自 `ULocalPlayerSaveGame`，存储于存档系统，支持云同步。

### 设置类别

| 类别 | 属性 |
|------|------|
| 色盲模式 | ColorBlindMode（Off/Deuteranope/Protanope/Tritanope），ColorBlindStrength（0~10） |
| 字幕 | 启用/禁用，文字大小/颜色/边框，背景不透明度 |
| 音频 | AllowAudioInBackground（Off/AllSounds） |
| 语言 | PendingCulture，ResetToDefaultCulture |
| 鼠标灵敏度 | MouseSensitivityX/Y，TargetingMultiplier，InvertVerticalAxis，InvertHorizontalAxis |
| 手柄灵敏度 | GamepadLookSensitivityPreset，GamepadTargetingSensitivityPreset（Slow~Insane 10级） |
| 手柄死区 | GamepadMoveStickDeadZone，GamepadLookStickDeadZone |
| 手柄震动 | bForceFeedbackEnabled |
| 扳机震动 | bTriggerHapticsEnabled，TriggerHapticStrength，TriggerHapticStartPosition |

### 生命周期

```cpp
// 创建临时设置对象
static ULyraSettingsShared* CreateTemporarySettings();

// 同步加载（登录前不可调用）
static ULyraSettingsShared* LoadOrCreateSettings();

// 异步加载
static bool AsyncLoadOrCreateSettings(..., FOnSettingsLoadedEvent Delegate);

// 保存
void SaveSettings(); // 异步存档

// 应用
void ApplySettings(); // 字幕 + 背景音频 + 文化 + 输入
```

### 脏标记机制

ChangeValueAndDirty 模板方法实现统一的"值与脏标记"管理：当属性值变化时更新值、标记脏位、广播 OnSettingChanged 事件。

## ULyraGameSettingRegistry

设置注册表，继承自 `UGameSettingRegistry`，将 ULyraSettingsLocal 和 ULyraSettingsShared 的属性注册为 UGameSetting 集合。

### 注册类别

| 类别 | 初始化方法 | 数据源 |
|------|-----------|--------|
| Video | InitializeVideoSettings() | ULyraSettingsLocal |
| Audio | InitializeAudioSettings() | ULyraSettingsLocal |
| Gameplay | InitializeGameplaySettings() | ULyraSettingsLocal + ULyraSettingsShared |
| MouseAndKeyboard | InitializeMouseAndKeyboardSettings() | ULyraSettingsShared |
| Gamepad | InitializeGamepadSettings() | ULyraSettingsShared |

### SaveChanges 流程

保存时依次应用并保存两级设置：

```cpp
void ULyraGameSettingRegistry::SaveChanges() {
    LocalPlayer->GetLocalSettings()->ApplySettings(false);  // 应用本地设置
    LocalPlayer->GetSharedSettings()->ApplySettings();       // 应用共享设置
    LocalPlayer->GetSharedSettings()->SaveSettings();        // 保存共享设置
}
```

## 自定义设置值类型

位于 `Settings/CustomSettings/` 目录，继承自 UGameSettingValue*：

| 类 | 用途 |
|------|------|
| ULyraSettingValueDiscrete_Resolution | 分辨率选择器 |
| ULyraSettingValueDiscrete_OverallQuality | 整体画质选择器 |
| ULyraSettingValueDiscrete_MobileFPSType | 移动端 FPS 选择器 |
| ULyraSettingValueDiscrete_Language | 语言选择器 |
| ULyraSettingValueDiscrete_PerfStat | 性能统计选择器 |
| ULyraSettingValueDiscreteDynamic_AudioOutputDevice | 音频输出设备选择器 |
| ULyraSettingKeyboardInput | 键盘映射设置 |
| ULyraSettingAction_SafeZoneEditor | 安全区编辑器动作 |

## 设置编辑器界面

位于 `Settings/Screens/` 目录：

| 类 | 用途 |
|------|------|
| ULyraSafeZoneEditor | 安全区可视化编辑器 |
| ULyraBrightnessEditor | 亮度/伽马值可视化编辑器 |

## 设置列表控件

位于 `Settings/Widgets/` 目录：

| 类 | 用途 |
|------|------|
| ULyraSettingsListEntrySetting_KeyboardInput | 键盘映射列表条目控件 |
