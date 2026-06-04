# 音频版本差异

## 概述

音频结构在 UE4 到 UE5 版本间有若干重要变更，主要通过 VER_UE4_SOUND 系列版本号控制兼容性。这些版本号定义在 ObjectVersion.h 中，影响音频压缩、并发控制、字幕数据等特性的序列化行为。

## 关键版本号

### VER_UE4_SOUND 系列版本

| 版本号 | 序号 | 用途 | 源码位置 |
|--------|------|------|----------|
| VER_UE4_SOUND_CLASS_GRAPH_EDITOR | 215 | 新增图状 SoundClass 编辑器 | ObjectVersion.h:215 |
| VER_UE4_SOUND_NODE_ENVELOPER_CURVE_CHANGE | 287 | USoundNodeEnveloper 曲线类型变更 (UDistributionFloatConstantCurve → FRichCurve) | ObjectVersion.h:287 |
| VER_UE4_SOUND_COMPRESSION_TYPE_ADDED | 476 | USoundWave 增加压缩格式类型信息 | ObjectVersion.h:476 |
| VER_UE4_SOUND_CONCURRENCY_PACKAGE | 673 | 音频并发设置结构和覆盖支持 | ObjectVersion.h:673 |

### FFrameworkObjectVersion 音频版本

| 版本号 | 用途 | 源码位置 |
|--------|------|----------|
| RemoveSoundWaveCompressionName | 移除 SoundWave CompressionName 属性 | FrameworkObjectVersion.h:51 |
| HardSoundReferences | 序列化音频文件的硬引用 | FrameworkObjectVersion.h:86 |

## 版本号功能详解

### VER_UE4_SOUND_CLASS_GRAPH_EDITOR (215)

**变更内容:**
- 新增基于图的 SoundClass 编辑器
- 弃用旧的列表式 SoundClass 编辑界面

**影响:**
- SoundClass 资产序列化格式变更
- 增加节点连接序列化数据

### VER_UE4_SOUND_NODE_ENVELOPER_CURVE_CHANGE (287)

**变更内容:**
- USoundNodeEnveloper 曲线类型变更
- 从 UDistributionFloatConstantCurve 改为 FRichCurve

**影响:**
- 音频包络节点序列化格式变更
- 曲线数据结构简化

### VER_UE4_SOUND_COMPRESSION_TYPE_ADDED (476)

**变更内容:**
- USoundWave 对象增加压缩方案信息
- 新增 CompressionName 字段 (后在 FFrameworkObjectVersion 中移除)

**影响:**
- 音频资产可记录使用的压缩格式
- 加载时根据版本判断是否读取 CompressionName

**序列化逻辑 (SoundWave.cpp:1254):**
```
if (Ar.IsLoading() && (Ar.UEVer() >= VER_UE4_SOUND_COMPRESSION_TYPE_ADDED) && (Ar.CustomVer(FFrameworkObjectVersion::GUID) < FFrameworkObjectVersion::RemoveSoundWaveCompressionName))
{
    FName DummyCompressionName;
    Ar << DummyCompressionName;
}
```

**兼容性处理:**
- 当版本 >= VER_UE4_SOUND_COMPRESSION_TYPE_ADDED 且 < RemoveSoundWaveCompressionName 时，读取并忽略 CompressionName
- 新版本资产不再序列化此字段

### VER_UE4_SOUND_CONCURRENCY_PACKAGE (673)

**变更内容:**
- 新增音频并发设置结构
- 支持并发规则覆盖配置

**影响:**
- SoundConcurrency 资产序列化格式
- 音频播放并发控制逻辑

### RemoveSoundWaveCompressionName

**变更内容:**
- 移除 SoundWave 的 CompressionName 属性
- 改用 SoundAssetCompressionType 枚举统一管理

**影响:**
- 压缩格式信息存储方式变更
- 从 FName 改为枚举类型

## UE5 新增字段

| 字段 | 类型 | 用途 | 源码位置 |
|------|------|------|----------|
| SoundAssetCompressionType | ESoundAssetCompressionType | 压缩格式枚举 (替代旧布尔属性)，默认 PlatformSpecific | SoundWave.h:463 |
| LoadingBehavior | mutable ESoundWaveLoadingBehavior | 加载行为控制 (Inherited=0, RetainOnLoad=1, PrimeOnLoad=2, LoadOnDemand=3, ForceInline=4) | SoundWave.h:743 |
| ZerothChunkData | FBulkDataBuffer<uint8> | 首块缓存优化 (位于 FSoundWaveData 内部) | FSoundWaveData:1679 |
| bEnableCloudStreaming | uint8 : 1 (WITH_EDITORONLY_DATA) | 云流式播放支持 (需平台插件) | SoundWave.h:879 |
| CuePoints | TArray<FSoundWaveCuePoint> (WITH_EDITORONLY_DATA) | WAV 文件 Cue 点和 Loop Region 支持 | SoundWave.h:808 |
| ESoundWaveCuePointOrigin | enum (WaveFile=0, MarkerTransformation) | Cue 点来源控制 | SoundWave.h:73-77 |
| SampleRateQuality | ESoundwaveSampleRateSettings | 采样率质量设置 | SoundWave.h:436 |
| CookedSpectralTimeData | TArray<FSoundWaveSpectralTimeData> | Cook-time FFT 分析数据 | SoundWave.h:585 |
| CookedEnvelopeTimeData | TArray<FSoundWaveEnvelopeTimeData> | Cook-time 振幅包络分析数据 | SoundWave.h:589 |

## UE4 到 UE5 结构变更

### 压缩格式管理变更

| UE4 属性 | UE5 替代 | 说明 |
|----------|----------|------|
| bUseBinkAudio (已弃用) | SoundAssetCompressionType::BinkAudio | 布尔属性改为枚举，保留为 deprecated |
| bSeekableStreaming (已弃用) | SoundAssetCompressionType::ADPCM | 流式 Seek 属性重构，保留为 deprecated |
| CompressionName (已移除) | SoundAssetCompressionType | FName 改为枚举 |

### 数据存储变更

| 变更类型 | UE4 | UE5 |
|----------|-----|-----|
| RawData 存储 | FByteBulkData | FEditorAudioBulkData (内含 UE::Serialization::FEditorBulkData) |
| CookedPlatformData 类型 | TMap | TSortedMap |
| 流式缓存 | 基础流式加载 | Stream Caching 机制 |
| 云流式播放 | 不支持 | bEnableCloudStreaming 支持 (EditorOnly, 需插件) |

### 新增功能

| 功能 | UE4 | UE5 |
|------|-----|-----|
| RADAudio 格式 | 不支持 | 支持，与 BinkAudio 相同但质量更好，仅支持特定采样率 |
| ProjectDefined 格式 | 不支持 | 使用项目默认编解码器 |
| Cue 点解析 | 不支持 | 从 WAV 文件解析 Cue Points/Loop Region (EditorOnly) |
| Cook-time 分析数据 | 不支持 | FFT/Envelope 数据支持 |
| 首块缓存优化 | 不支持 | ZerothChunkData 缓存 (位于 FSoundWaveData 内部) |
| 采样率质量控制 | 不支持 | ESoundwaveSampleRateSettings |

## 废弃字段

| 字段 | 废弃版本 | 废弃原因 |
|------|----------|----------|
| CompressionName | FFrameworkObjectVersion::RemoveSoundWaveCompressionName | 改用 SoundAssetCompressionType 枚举 |
| DTYPE_Xenon | UE4 早期 | Xenon 平台已弃用，枚举值保留 |
| bUseBinkAudio | UE5 | 整合到 SoundAssetCompressionType，保留为 deprecated 属性 |
| bSeekableStreaming | UE5 | 整合到 SoundAssetCompressionType，保留为 deprecated 属性 |
| StreamingPriority | UE5 | Stream Caching 启用后流式优先级不再生效，保留为 deprecated |

## 向后兼容处理

### 版本判断机制

加载音频资产时，引擎根据版本号决定序列化行为:

1. **文件版本判断:**
   - 使用 `Ar.UEVer()` 检查 UE4 版本号
   - 使用 `Ar.UE5Ver()` 检查 UE5 版本号

2. **自定义版本判断:**
   - 使用 `Ar.CustomVer()` 检查特定模块版本
   - 音频相关使用 FFrameworkObjectVersion::GUID

### 兼容性处理示例

**CompressionName 处理:**
- 版本 >= VER_UE4_SOUND_COMPRESSION_TYPE_ADDED: 读取 CompressionName
- 版本 >= RemoveSoundWaveCompressionName: 不读取，使用枚举替代

**曲线数据处理:**
- 版本 < VER_UE4_SOUND_NODE_ENVELOPER_CURVE_CHANGE: 读取旧曲线格式
- 版本 >= 此版本号: 读取 FRichCurve 格式

### 加载兼容性原则

- 旧版本音频资产在加载时自动适配新格式
- 废弃字段在加载时忽略并替换为默认值
- 版本号判断确保正确序列化行为

## 版本判断实现

### 序列化注册

音频资产序列化时注册自定义版本:

```
Ar.UsingCustomVersion(FFrameworkObjectVersion::GUID);
Ar.UsingCustomVersion(FUE5MainStreamObjectVersion::GUID);
```

### 版本检查顺序

1. 首先检查 UE4 全局版本号 (`Ar.UEVer()`)
2. 然后检查自定义版本号 (`Ar.CustomVer()`)
3. 组合判断决定序列化行为

## 符号说明

> 以下符号在源码检索中**未找到**: `FCompressedAudioInfo`、`USoundBaseAsyncData`、`FSoundBaseChunkData`。这些符号可能在旧版 UE 中存在或已被重命名/移除。当前 UE 源码中对应的功能由以下结构替代:
> - 压缩音频信息: 通过 `ESoundAssetCompressionType` 枚举 + `FStreamedAudioPlatformData` 管理
> - 异步数据: 通过 `FStreamedAudioPlatformData::AsyncTask` 和 `FAsyncAudioDecompressWorker` 管理
> - 块数据: 通过 `FStreamedAudioChunk` 和 `FSoundWaveData` 管理

## 源码引用

### 版本定义
- Runtime/Core/Public/UObject/ObjectVersion.h — VER_UE4_SOUND 系列版本号
- Runtime/Core/Public/UObject/FrameworkObjectVersion.h — FFrameworkObjectVersion 音频版本
- Runtime/Core/Public/UObject/UE5MainStreamObjectVersion.h — UE5 主线版本

### 音频结构
- Runtime/Engine/Classes/Sound/SoundWave.h — USoundWave 定义
- Runtime/Engine/Classes/Sound/SoundBase.h — USoundBase 基类定义
- Runtime/Engine/Classes/Sound/SoundGroups.h — 音频组定义
- Runtime/Engine/Classes/Sound/SoundConcurrency.h — 并发控制定义
- Runtime/Engine/Classes/Sound/SoundWaveLoadingBehavior.h — 加载行为枚举

### 序列化实现
- Runtime/Engine/Private/SoundWave.cpp — 版本判断和序列化实现
- Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp — 加载兼容性处理

## 相关文档

- [音频基础结构](audio-structure.md) — USoundWave 属性字段表
- [音频压缩格式](audio-compression.md) — ESoundAssetCompressionType 枚举
- [音频平台数据](audio-platform-data.md) — FStreamedAudioPlatformData 结构
- [BulkData 存储机制](../bulkdata-region.md) — 音频数据存储
