# 音频平台数据

## 概述

音频平台数据存储各平台优化的压缩音频数据。不同平台可使用不同的音频格式和压缩方案，如 Windows 使用 BinkAudio/RADAudio，iOS 使用 AAC，Android 使用 Opus 等。

平台数据通过 FStreamedAudioPlatformData 结构管理，支持流式播放和分块加载机制。

## FStreamedAudioPlatformData 结构

运行时流式音频的平台特定数据，存储音频块数组及格式信息。定义在 SoundWave.h:141-219。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| AudioFormat | FName | 音频块存储格式 | SoundWave.h:147 |
| Chunks | TIndirectArray<FStreamedAudioChunk> | 音频块数组 | SoundWave.h:149 |
| DerivedDataKey | FString (WITH_EDITORONLY_DATA) | DDC 关联键 (EditorOnly) | SoundWave.h:153 |
| AsyncTaskLock | mutable TDontCopy<FRWLock> (WITH_EDITORONLY_DATA) | 异步任务锁，保护 AsyncTask 的多线程访问 | SoundWave.h:155 |
| AsyncTask | FStreamedAudioAsyncCacheDerivedDataTask* (WITH_EDITORONLY_DATA) | 异步缓存任务 (EditorOnly) | SoundWave.h:157 |

> **更正:** AsyncTaskLock 不是 EditorOnly 独有，而是 mutable TDontCopy<FRWLock>，用于保护 AsyncTask 的多线程访问。AsyncTask 本身才是 EditorOnly。

### 核心方法

| 方法名 | 返回类型 | 用途 |
|--------|----------|------|
| GetChunkFromDDC | int32 | 从 DDC 加载音频块 |
| GetChunks | TIndirectArray<FStreamedAudioChunk>& | 获取音频块数组 (确保异步任务完成) |
| GetNumChunks | int32 | 获取音频块数量 (确保异步任务完成) |
| GetAudioFormat | FName | 获取音频格式 (确保异步任务完成) |
| Serialize | void | 序列化操作 |
| Cache | void | 缓存平台数据 (EditorOnly) |
| FinishCache | void | 完成缓存 (EditorOnly) |
| IsFinishedCache | bool | 检查缓存是否完成 (EditorOnly) |
| TryInlineChunkData | bool | 尝试内联块数据 (EditorOnly) |
| AreDerivedChunksAvailable | bool | 检查派生块是否可用 (EditorOnly) |

## FStreamedAudioChunk 结构

流式音频的单个数据块，支持按需加载和 Seek 定位。定义在 SoundWave.h:92-136。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| DataSize | int32 (默认 0) | 数据大小 (含零填充) | SoundWave.h:104 |
| AudioDataSize | int32 (默认 0) | 音频数据大小 (含 Seek 表) | SoundWave.h:107 |
| SeekOffsetInAudioFrames | uint32 (默认 INDEX_NONE) | 流中位置 (帧)，!= INDEX_NONE 时表示存在 Seek 表 | SoundWave.h:110 |
| BulkData | FByteBulkData | Bulk 数据存储 | SoundWave.h:113 |
| CachedDataPtr | uint8* (私有, 默认 nullptr) | 缓存数据指针 (内部) | SoundWave.h:116 |
| DerivedDataKey | FString (WITH_EDITORONLY_DATA) | DDC 键 (EditorOnly) | SoundWave.h:122 |
| bLoadedFromCookedPackage | bool (WITH_EDITORONLY_DATA, 默认 false) | 是否从 cooked 包加载 (EditorOnly) | SoundWave.h:125 |
| bInlineChunk | bool (WITH_EDITORONLY_DATA, 默认 false) | 是否内联块 (EditorOnly) | SoundWave.h:128 |

### 字段详解

**DataSize vs AudioDataSize:**
- DataSize: 包含零填充的完整块大小
- AudioDataSize: 实际音频数据大小，可能包含 Seek 表

**SeekOffsetInAudioFrames:**
- 音频帧位置索引
- 当值不为 INDEX_NONE 时，表示存在 Seek 表

**BulkData:**
- 使用 FByteBulkData 存储大数据块
- 支持内联或外部存储模式

### 核心方法

| 方法名 | 返回类型 | 用途 |
|--------|----------|------|
| Serialize | void | 序列化操作 (接受 FArchive&, UObject* Owner, int32 ChunkIndex) |
| GetCopy | bool | 获取数据副本 |
| MoveOutAsBuffer | FBulkDataBuffer<uint8> | 移出数据为缓冲区 (从 ByteBulkData 复制并丢弃原始数据) |
| StoreInDerivedDataCache | uint32 | 存储到 DDC (EditorOnly) |

## CookedPlatformData 存储机制

USoundWave 使用 TSortedMap 存储各平台的 Cooked 数据。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| CookedPlatformData | TSortedMap<FString, FStreamedAudioPlatformData*> | 按平台名索引的平台数据映射 | SoundWave.h:1111 |

### 平台数据特点

**TSortedMap 选择原因:**
- 保持平台数据的有序性
- 支持快速查找和迭代
- 避免 TMap 的哈希冲突开销

**平台数据存储流程:**
1. Cook 时为每个目标平台生成优化数据
2. 数据存储在 FStreamedAudioPlatformData 中
3. 运行时根据当前平台选择对应数据
4. 流式音频按块加载，支持 Seek 定位

## 平台音频格式映射

不同平台使用不同的音频格式，格式选择取决于硬件支持和性能需求。

| 平台 | 常用格式 | 说明 |
|------|----------|------|
| Windows | BinkAudio, RADAudio, Opus | 支持全特性编解码 |
| Mac | AAC, Opus | Apple 系统优化格式 |
| iOS | AAC | 硬件解码支持 |
| Android | Opus, ADPCM | 低功耗解码 |
| Xbox | XMA2 | Xbox 系统格式 |
| PlayStation | ATRAC9 | Sony 系统格式 |

### 格式特性对比

| 格式 | 压缩率 | CPU 消耗 | Seek 支持 |
|------|--------|----------|-----------|
| PCM | 无压缩 | 极低 | 是 |
| ADPCM | ~4x | 低 | 是 |
| BinkAudio | 高 | 中 | 是 |
| RADAudio | 高 | 中 | 是 |
| Opus | 高 | 中高 | 是 |
| PlatformSpecific | 平台相关 | 低 | 否 |

## 音频数据存储位置

### 编辑器数据 (EditorOnly)

**RawData (FEditorAudioBulkData):**
- 存储导入的原始 WAV 数据
- 内含 UE::Serialization::FEditorBulkData
- 保证 16 位深度
- 单声道或立体声格式
- 多通道通过 ChannelOffsets/ChannelSizes 分离，每个通道对应独立 RIFF 文件拼接

### Cooked 数据

**CookedPlatformData:**
- 各平台优化压缩数据
- FStreamedAudioPlatformData 管理块数组
- 支持流式加载和按需缓存

### 运行时数据

**RunningPlatformData (FSoundWaveData 内部):**
- 当前平台的流式音频数据
- FStreamedAudioPlatformData 内部管理

**ResourceData (FSoundWaveData 内部):**
- 当前平台压缩音频数据
- FBulkDataBuffer<uint8> 存储

**ZerothChunkData (FSoundWaveData 内部):**
- 首块音频缓存
- 流式加载优化，减少首帧延迟

## 平台数据序列化

### 序列化流程

1. **SerializeCookedPlatformData:**
   - 读取/写入 CookedPlatformData 映射
   - 处理各平台的 FStreamedAudioPlatformData

2. **FStreamedAudioPlatformData::Serialize:**
   - 序列化 AudioFormat 和 Chunks
   - 处理 BulkData 块引用

3. **FStreamedAudioChunk::Serialize:**
   - 序列化 DataSize、AudioDataSize
   - 序列化 SeekOffsetInAudioFrames
   - 处理 BulkData 数据块

### BulkData 处理

音频块使用 FByteBulkData 存储，支持两种模式：

**内联模式 (bInlineChunk=true):**
- 数据直接存储在 .uasset 文件内
- 适合小音频块或频繁访问数据

**外部模式:**
- 数据存储在单独的 .ubulk 文件
- 通过 BulkDataOffset 和 BulkDataSize 引用
- 适合大型流式音频块

## 源码引用

- Runtime/Engine/Classes/Sound/SoundWave.h — FStreamedAudioPlatformData、FStreamedAudioChunk 定义
- Runtime/Engine/Private/SoundWave.cpp — 平台数据序列化实现
- Runtime/CoreUObject/Public/Serialization/BulkData.h — FByteBulkData 定义
- Runtime/CoreUObject/Public/Serialization/BulkDataBuffer.h — FBulkDataBuffer 定义
- Runtime/CoreUObject/Public/Serialization/EditorBulkData.h — FEditorBulkData 定义
- Runtime/Engine/Public/AudioDevice.h — 音频设备和格式处理

## 版本差异

### UE5 新增特性

**TSortedMap 替代 TMap:**
- CookedPlatformData 使用有序映射
- 提升平台数据查找效率

**FEditorAudioBulkData:**
- 替代传统 FByteBulkData
- 内含 UE::Serialization::FEditorBulkData，支持 Payload 机制和更灵活的数据管理

**流式缓存优化:**
- ZerothChunkData 首块缓存 (位于 FSoundWaveData 内部)
- LoadOnDemand 按需加载机制
- 多种 LoadingBehavior 模式 (Inherited, RetainOnLoad, PrimeOnLoad, LoadOnDemand, ForceInline)

**云流式播放:**
- bEnableCloudStreaming 支持 (EditorOnly, 需平台插件)
- PlatformSettings 平台特定设置 (TMap<FGuid, FSoundWaveCloudStreamingPlatformSettings>)
- 需平台插件支持

### UE4 vs UE5

**UE4:**
- 使用 TMap 存储平台数据
- 传统 FByteBulkData 存储原始数据
- 基础流式加载机制

**UE5:**
- TSortedMap 优化平台数据索引
- FEditorAudioBulkData (内含 UE::Serialization::FEditorBulkData) 支持 Payload
- 流式缓存机制 (Stream Caching)
- 云流式播放支持
- Cook-time 分析数据 (FFT/Envelope) — CookedSpectralTimeData / CookedEnvelopeTimeData

详见 [audio-structure.md](audio-structure.md) USoundWave 基础结构。
详见 [../bulkdata-region.md](../bulkdata-region.md) BulkData 存储机制。
