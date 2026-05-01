# 音频基础结构

## 概述

USoundWave 是 UE 引擎中的音频资产类，存储音频数据、压缩信息和平台相关数据。继承自 USoundBase，支持多种压缩格式和流式播放。

完整属性覆盖约 25+ 字段，涵盖音频属性、压缩信息、平台数据、播放控制等类别。

## USoundWave 核心属性字段表

### 基础音频属性

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| SampleRate | int32 | Cooked 采样率 | SoundWave.h:799 |
| ImportedSampleRate | int32 | 导入时原始采样率 (EditorOnly) | SoundWave.h:804 |
| NumChannels | int32 | 通道数 (1=单声道, 2=立体声) | SoundWave.h:774 |
| NumFrames | int32 | 音频帧数 | FSoundWaveData |
| Duration | float | 音频时长 (秒) | FSoundWaveData |
| RawPCMData | uint8* | 原始 PCM 数据指针 | SoundWave.h:918 |
| RawPCMDataSize | int32 | 原始 PCM 数据大小 | SoundWave.h:915 |

### 压缩格式属性

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| SoundAssetCompressionType | ESoundAssetCompressionType | 压缩格式类型 | SoundWave.h:463 |
| CompressionQuality | int32 | 压缩质量 (1-100, 1=最佳压缩, 100=最佳质量) | SoundWave.h:424 |
| DecompressionType | EDecompressionType | 解压缩缓冲类型 | SoundWave.h:439 |
| CompressedDataGuid | FGuid | 唯一标识符 (DDC 缓存键) | SoundWave.h:1101 |

### 压缩格式类型枚举 (ESoundAssetCompressionType)

| 枚举值 | 说明 | 特性 |
|--------|------|------|
| BinkAudio | Bink 音频编解码器 | 支持所有平台特性 |
| RADAudio | RAD 音频编解码器 | 更高质量，采样率限制 (48000/44100/32000/24000) |
| ADPCM | 自适应差分脉冲编码调制 | ~4x 压缩率，固定质量，低成本解码 |
| PCM | 未压缩音频 | 大内存占用，极低成本解码 |
| Opus | Opus 编解码器 | 适用于语音/音乐传输和流式应用 |
| PlatformSpecific | 平台特定格式 | 不同平台格式不同，不支持 Seek |
| ProjectDefined | 项目定义编解码器 | 使用项目默认设置 |

### 播放控制属性

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Volume | float | 音量系数 (默认 1.0) | SoundWave.h:766 |
| Pitch | float | 音调系数 (范围 0.125-4.0) | SoundWave.h:770 |
| SoundGroup | ESoundGroup | 音频组分类 | SoundWave.h:442 |
| bLooping | bool | 是否循环播放 | SoundWave.h:446 |
| bStreaming | bool | 是否流式播放 | SoundWave.h:450 |
| bProcedural | bool | 是否程序生成音频 | SoundWave.h:669 |
| bDynamicResource | bool | 是否动态资源 (上传后释放) | SoundWave.h:681 |
| Priority | float | 播放优先级 | 通过 SoundClass 继承 |

### 加载行为属性

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| LoadingBehavior | ESoundWaveLoadingBehavior | 加载行为 (流式缓存模式) | SoundWave.h:743 |
| NumPrecacheFrames | int32 | 预缓存帧数 | SoundWave.h:912 |
| NumSourcesPlaying | FThreadSafeCounter | 当前播放源数量 | SoundWave.h:648 |
| ResourceID | int32 | 资源索引 (跨引用) | SoundWave.h:825 |
| TrackedMemoryUsage | int32 | 内存使用跟踪 | SoundWave.h:830 |

### 字幕属性

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Subtitles | TArray<FSubtitleCue> | 字幕提示数据 | SoundWave.h:836 |
| SubtitlePriority | float | 字幕优先级 | SoundWave.h:762 |
| bMature | bool | 是否包含成人内容 | SoundWave.h:685 |
| bManualWordWrap | bool | 是否禁用自动换行 | SoundWave.h:689 |
| bSingleLine | bool | 是否单行字幕显示 | SoundWave.h:693 |

### 高级属性

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| bIsAmbisonics | bool | 是否 Ambisonics 格式 | SoundWave.h:704 |
| bDecompressedFromOgg | bool | 是否从 OGG 解压 | SoundWave.h:707 |
| bRequiresStopFade | bool | 是否需要停止淡出 | SoundWave.h:672 |
| bCanProcessAsync | bool | 是否可异步处理 | SoundWave.h:678 |
| bIsSourceBus | bool | 是否总线源 | SoundWave.h:675 |

## 音频数据存储

### 数据存储字段表

| 字段名 | 类型 | 用途 | 数据位置 |
|--------|------|------|----------|
| RawData | FEditorAudioBulkData | 编辑器原始 WAV 数据 (EditorOnly) | 内联/Payload |
| CookedPlatformData | TSortedMap<FString, FStreamedAudioPlatformData*> | Cooked 平台数据映射 | 按平台名索引 |
| ResourceData | FBulkDataBuffer<uint8> | 运行时压缩音频数据 | 流式缓存 |
| ZerothChunkData | FBulkDataBuffer<uint8> | 首块音频数据 (流式加载) | 流式缓存 |

### FStreamedAudioPlatformData 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| AudioFormat | FName | 音频块存储格式 |
| Chunks | TIndirectArray<FStreamedAudioChunk> | 音频块数组 |
| DerivedDataKey | FString | DDC 关联键 (EditorOnly) |

### FStreamedAudioChunk 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| DataSize | int32 | 数据大小 (含零填充) |
| AudioDataSize | int32 | 音频数据大小 (含 Seek 表) |
| SeekOffsetInAudioFrames | uint32 | 流中位置 (帧) |
| BulkData | FByteBulkData | Bulk 数据存储 |

### 数据存储位置说明

**未压缩音频 (EditorOnly):**
- RawData 字段存储导入的原始 WAV 数据
- 数据保证 16 位，单声道或立体声
- 多通道数据通过 ChannelOffsets/ChannelSizes 分离

**压缩音频 (Cooked):**
- CookedPlatformData 存储各平台优化数据
- FStreamedAudioPlatformData 包含音频块数组
- 流式音频分块存储，支持按需加载

**运行时数据:**
- ResourceData 存储当前平台压缩数据
- ZerothChunkData 缓存首块音频 (流式加载优化)

## 解压缩类型 (EDecompressionType)

| 枚举值 | 说明 |
|--------|------|
| DTYPE_Setup | 设置阶段 |
| DTYPE_Invalid | 无效类型 |
| DTYPE_RealTime | 实时解压缩 |
| DTYPE_Procedural | 程序生成 |
| DTYPE_Xenon | Xenon 平台 (已弃用) |
| DTYPE_Streaming | 流式解压缩 |

## 加载行为 (ESoundWaveLoadingBehavior)

| 枚举值 | 说明 |
|--------|------|
| Uninitialized | 未初始化 |
| ForceInline | 强制内联加载 |
| RetainOnLoad | 加载时保留 |
| PrimeOnLoad | 加载时预填充 |
| LazyOnDemand | 按需延迟加载 |

## 源码引用

- Runtime/Engine/Classes/Sound/SoundWave.h — USoundWave 定义
- Runtime/Engine/Private/Sound/SoundWave.cpp — 序列化实现
- Runtime/Engine/Classes/Sound/SoundGroups.h — 音频组定义
- Runtime/CoreUObject/Public/Serialization/BulkData.h — BulkData 结构
- Runtime/CoreUObject/Public/Serialization/BulkDataBuffer.h — BulkDataBuffer 结构

## 版本差异

### UE5 新增

- **SoundAssetCompressionType**: 新增 RADAudio、ProjectDefined 类型
- **LoadingBehavior**: 细化加载行为控制 (RetainOnLoad, PrimeOnLoad, LazyOnDemand)
- **ZerothChunkData**: 首块缓存优化，支持流式缓存
- **bEnableCloudStreaming**: 云流式播放支持
- **FEditorAudioBulkData**: 替代传统 FByteBulkData，支持 Payload 机制
- **CookedPlatformData**: TSortedMap 替代 TMap，优化平台数据存储
- **CuePoints**: 支持从 WAV 文件解析 Cue 点和 Loop Region

### UE4 vs UE5

- UE4: 使用传统 FByteBulkData 存储 RawData
- UE5: 使用 FEditorAudioBulkData，支持更灵活的数据管理
- UE5: 新增流式缓存机制 (Stream Caching)
- UE5: 新增云流式播放支持 (需平台插件)
- UE5: 新增 Cook-time 分析数据 (FFT/Envelope)

详见 [bulkdata-region.md](../bulkdata-region.md) BulkData 存储机制。
详见 [file-structure.md](../file-structure.md) 整体结构概述。