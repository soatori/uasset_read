# 音频基础结构

## 概述

USoundWave 是 UE 引擎中的音频资产类，存储音频数据、压缩信息和平台相关数据。继承自 USoundBase，支持多种压缩格式和流式播放。

完整属性覆盖约 25+ 字段，涵盖音频属性、压缩信息、平台数据、播放控制等类别。

## USoundWave 核心属性字段表

### 基础音频属性

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| SampleRate | int32 | Cooked 采样率 | SoundWave.h:799 (protected, UPROPERTY VisibleAnywhere) |
| ImportedSampleRate | int32 | 导入时原始采样率 (EditorOnly) | SoundWave.h:804 (UPROPERTY VisibleAnywhere) |
| NumChannels | int32 | 通道数 (1=单声道, 2=立体声) | SoundWave.h:774 (UPROPERTY VisibleAnywhere) |
| NumFrames | int32 | 音频帧数 | FSoundWaveData:1722 (非 USoundWave 直接成员) |
| Duration | float | 音频时长 (秒) | FSoundWaveData:1719 / USoundBase.h:202 (基类属性) |
| RawPCMData | uint8* | 原始 PCM 数据指针 | SoundWave.h:918 |
| RawPCMDataSize | int32 | 原始 PCM 数据大小 | SoundWave.h:915 |

### 压缩格式属性

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| SoundAssetCompressionType | ESoundAssetCompressionType | 压缩格式类型，默认 PlatformSpecific | SoundWave.h:463 |
| CompressionQuality | int32 | 压缩质量 (1-100, 1=最佳压缩, 100=最佳质量) | SoundWave.h:424 |
| DecompressionType | EDecompressionType (TEnumAsByte) | 解压缩缓冲类型 | SoundWave.h:439 |
| CompressedDataGuid | FGuid | 唯一标识符 (DDC 缓存键) | SoundWave.h:1101 |
| SampleRateQuality | ESoundwaveSampleRateSettings | 采样率质量设置 | SoundWave.h:436 |

### 压缩格式类型枚举 (ESoundAssetCompressionType)

> **注意**: 枚举顺序与源码一致 (SoundWave.h:344-366)，RADAudio 在最后而非第二位。

| 枚举值 | 源码注释说明 | 特性 |
|--------|-------------|------|
| BinkAudio | 感知编解码器，支持所有平台上的全部特性 | 通用音频，高兼容性 |
| ADPCM | 使用 ADPCM 编码，时域编解码器，固定质量，~4x 压缩比，解码成本低 | 低延迟音频 (对话、UI 音效) |
| PCM | 未压缩音频，大内存占用 (流式块包含较少音频)，解码成本极低，支持全部特性 | 高质量音频 |
| Opus | 高适应性音频编解码器，主要为交互式语音和音乐互联网传输设计，也适用于存储和流式应用 | 语音/音乐传输和流式应用 |
| PlatformSpecific | 编码为平台特定格式，不同平台格式不同，当前不支持 Seek | 平台优化音频 |
| ProjectDefined | 项目定义该资产的编解码器 | 使用项目默认设置 |
| RADAudio | 与 BinkAudio 相同，但质量更好，CPU 使用率相当。仅支持采样率: 48000、44100、32000、24000 | 高质量音频 |

### 播放控制属性

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Volume | float | 音量系数 (默认 1.0, UPROPERTY ClampMin=0.0) | SoundWave.h:766 |
| Pitch | float | 音调系数 (范围 0.125-4.0, 默认 1.0) | SoundWave.h:770 |
| SoundGroup | TEnumAsByte<ESoundGroup> | 音频组分类 | SoundWave.h:442 |
| bLooping | uint8 : 1 | 是否循环播放 (UPROPERTY AssetRegistrySearchable) | SoundWave.h:446 |
| bStreaming | uint8 : 1 | 是否流式播放 (遗留代码兼容，保留) | SoundWave.h:450 |
| bProcedural | uint8 : 1 | 是否程序生成音频 | SoundWave.h:669 |
| bDynamicResource | uint8 : 1 | 是否动态资源 (上传后释放) | SoundWave.h:681 |
| bIsSourceBus | uint8 : 1 | 是否总线源 | SoundWave.h:675 |
| bRequiresStopFade | uint8 : 1 | 是否需要停止淡出 | SoundWave.h:672 |
| bCanProcessAsync | uint8 : 1 | 是否可异步处理 | SoundWave.h:678 |
| Priority | float | 播放优先级 (范围 0.0-100.0) | USoundBase.h:218 |

### 加载行为属性

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| LoadingBehavior | mutable ESoundWaveLoadingBehavior | 加载行为 (流式缓存模式) | SoundWave.h:743 |
| NumPrecacheFrames | int32 | 预缓存帧数 | SoundWave.h:912 |
| NumSourcesPlaying | FThreadSafeCounter | 当前播放源数量 | SoundWave.h:648 |
| ResourceID | int32 | 资源索引 (跨引用) | SoundWave.h:825 |
| TrackedMemoryUsage | int32 | 内存使用跟踪 | SoundWave.h:830 |

### 字幕属性

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Subtitles | TArray<FSubtitleCue> | 字幕提示数据 | SoundWave.h:836 |
| SubtitlePriority | float | 字幕优先级 | SoundWave.h:762 |
| bMature | uint8 : 1 | 是否包含成人内容 (UPROPERTY AssetRegistrySearchable) | SoundWave.h:685 |
| bManualWordWrap | uint8 : 1 | 是否禁用自动换行 | SoundWave.h:689 |
| bSingleLine | uint8 : 1 | 是否单行字幕显示 | SoundWave.h:693 |

### 高级属性

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| bIsAmbisonics | uint8 : 1 | 是否 Ambisonics 格式 (UPROPERTY Category=Format) | SoundWave.h:704 |
| bDecompressedFromOgg | uint8 : 1 | 是否从 OGG 解压 | SoundWave.h:707 |
| bRequiresStopFade | uint8 : 1 | 是否需要停止淡出 | SoundWave.h:672 |
| bCanProcessAsync | uint8 : 1 | 是否可异步处理 | SoundWave.h:678 |
| bIsSourceBus | uint8 : 1 | 是否总线源 | SoundWave.h:675 |

## 音频数据存储

### 数据存储字段表

| 字段名 | 类型 | 用途 | 数据位置 |
|--------|------|------|----------|
| RawData | FEditorAudioBulkData (内含 UE::Serialization::FEditorBulkData) | 编辑器原始 WAV 数据 (EditorOnly) | 内联/Payload |
| CookedPlatformData | TSortedMap<FString, FStreamedAudioPlatformData*> | Cooked 平台数据映射 | 按平台名索引 |
| ResourceData | FBulkDataBuffer<uint8> (FSoundWaveData 内部) | 运行时压缩音频数据 | FSoundWaveData:1696 |
| ZerothChunkData | FBulkDataBuffer<uint8> (FSoundWaveData 内部) | 首块音频数据 (流式加载) | FSoundWaveData:1679 |

### FStreamedAudioPlatformData 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| AudioFormat | FName | 音频块存储格式 |
| Chunks | TIndirectArray<FStreamedAudioChunk> | 音频块数组 |
| DerivedDataKey | FString (WITH_EDITORONLY_DATA) | DDC 关联键 (EditorOnly) |
| AsyncTaskLock | mutable TDontCopy<FRWLock> (WITH_EDITORONLY_DATA) | 异步任务锁，保护 AsyncTask 的多线程访问 |
| AsyncTask | FStreamedAudioAsyncCacheDerivedDataTask* (WITH_EDITORONLY_DATA) | 异步缓存任务 |

### FStreamedAudioChunk 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| DataSize | int32 (默认 0) | 数据大小 (含零填充) |
| AudioDataSize | int32 (默认 0) | 音频数据大小 (含 Seek 表) |
| SeekOffsetInAudioFrames | uint32 (默认 INDEX_NONE) | 流中位置 (帧)，!= INDEX_NONE 时表示存在 Seek 表 |
| BulkData | FByteBulkData | Bulk 数据存储 |
| CachedDataPtr | uint8* (私有) | 缓存数据指针 (内部) |
| DerivedDataKey | FString (WITH_EDITORONLY_DATA) | DDC 键 |
| bLoadedFromCookedPackage | bool (WITH_EDITORONLY_DATA) | 是否从 cooked 包加载 |
| bInlineChunk | bool (WITH_EDITORONLY_DATA) | 是否内联块 |

### 数据存储位置说明

**未压缩音频 (EditorOnly):**
- RawData 字段存储导入的原始 WAV 数据，使用 FEditorAudioBulkData (内含 UE::Serialization::FEditorBulkData)
- 数据保证 16 位，单声道或立体声格式
- 多通道数据通过 ChannelOffsets/ChannelSizes 分离，每个通道对应独立的 RIFF 文件拼接

**压缩音频 (Cooked):**
- CookedPlatformData 存储各平台优化数据
- FStreamedAudioPlatformData 包含音频块数组
- 流式音频分块存储，支持按需加载

**运行时数据:**
- ResourceData (位于 FSoundWaveData 内部) 存储当前平台压缩数据
- ZerothChunkData (位于 FSoundWaveData 内部) 缓存首块音频 (流式加载优化)
- RunningPlatformData (FSoundedAudioPlatformData) 管理运行时的流式音频数据

## 解压缩类型 (EDecompressionType)

> 定义在 SoundWave.h:44-54，底层类型为 int

| 枚举值 | 说明 |
|--------|------|
| DTYPE_Setup | 设置阶段 |
| DTYPE_Invalid | 无效类型 |
| DTYPE_RealTime | 实时解压缩 |
| DTYPE_Procedural | 程序生成 |
| DTYPE_Xenon | Xenon 平台 (已弃用) |
| DTYPE_Streaming | 流式解压缩 |
| DTYPE_MAX | 最大值边界 |

## 加载行为 (ESoundWaveLoadingBehavior)

> 定义在 SoundWaveLoadingBehavior.h:22-37，底层类型为 uint8。仅在 Stream Caching 启用时生效。

| 枚举值 | 值 | 说明 |
|--------|------|------|
| Inherited | 0 | 继承自 USoundClass 或通过 au.streamcache cvar 定义的默认行为 |
| RetainOnLoad | 1 | 首块音频加载后保留在音频缓存中，直到 SoundWave 销毁或调用 ReleaseCompressedAudio |
| PrimeOnLoad | 2 | 首块音频在资产加载时从磁盘加载到缓存，但可能为其他音频腾出空间而被驱逐 |
| LoadOnDemand | 3 | 首块音频在资产播放或被预加载前不会加载 (USoundWave 类的 meta LoadBehavior 默认值) |
| ForceInline | 4 | 强制所有音频数据生活在缓存外，使用非流式解码路径 (仅在 USoundWave 上设置时可用) |
| Uninitialized | 0xff | 表示 ESoundWaveLoadingBehavior 的值尚未在 USoundWave 上缓存 |

优先级顺序: USoundWave 设置 > USoundClass 设置 > 父级 USoundClass > au.streamcache cvar

## 源码引用

- Runtime/Engine/Classes/Sound/SoundWave.h — USoundWave、FStreamedAudioPlatformData、FStreamedAudioChunk、ESoundAssetCompressionType、EDecompressionType 定义
- Runtime/Engine/Classes/Sound/SoundBase.h — USoundBase 基类定义
- Runtime/Engine/Classes/Sound/SoundWaveLoadingBehavior.h — ESoundWaveLoadingBehavior 枚举
- Runtime/Engine/Private/SoundWave.cpp — 序列化实现
- Runtime/Engine/Classes/Sound/SoundGroups.h — 音频组定义
- Runtime/CoreUObject/Public/Serialization/BulkData.h — BulkData 结构
- Runtime/CoreUObject/Public/Serialization/BulkDataBuffer.h — BulkDataBuffer 结构
- Runtime/CoreUObject/Public/Serialization/EditorBulkData.h — FEditorBulkData 结构

## 版本差异

### UE5 新增

- **SoundAssetCompressionType**: 统一压缩格式管理 (枚举顺序: BinkAudio, ADPCM, PCM, Opus, PlatformSpecific, ProjectDefined, RADAudio)
- **LoadingBehavior**: 细化加载行为控制 (Inherited=0, RetainOnLoad=1, PrimeOnLoad=2, LoadOnDemand=3, ForceInline=4, Uninitialized=0xff)
- **ZerothChunkData**: 首块缓存优化，位于 FSoundWaveData 内部
- **bEnableCloudStreaming**: 云流式播放支持 (EditorOnly, 需要平台插件)
- **FEditorAudioBulkData**: 替代传统 FByteBulkData，内含 UE::Serialization::FEditorBulkData，支持 Payload 机制
- **CookedPlatformData**: TSortedMap 替代 TMap，优化平台数据存储
- **CuePoints**: 支持从 WAV 文件解析 Cue 点和 Loop Region (EditorOnly)
- **CookedSpectralTimeData / CookedEnvelopeTimeData**: Cook-time 分析数据存储
- **SampleRateQuality**: 采样率质量设置 (ESoundwaveSampleRateSettings)

### UE4 vs UE5

- UE4: 使用传统 FByteBulkData 存储 RawData
- UE5: 使用 FEditorAudioBulkData (内含 UE::Serialization::FEditorBulkData)，支持更灵活的数据管理
- UE5: 新增流式缓存机制 (Stream Caching)
- UE5: 新增云流式播放支持 (需平台插件)
- UE5: 新增 Cook-time 分析数据 (FFT/Envelope)

详见 [bulkdata-region.md](../bulkdata-region.md) BulkData 存储机制。
详见 [file-structure.md](../file-structure.md) 整体结构概述。
