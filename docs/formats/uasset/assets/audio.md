# 音频资产文档

音频资产类型 (USoundWave) 相关文档导航。

## 子文档

| 文档 | 内容 | 说明 |
|------|------|------|
| [audio-structure.md](audio-structure.md) | 基础结构 | USoundWave 完整属性字段 |
| [audio-platform-data.md](audio-platform-data.md) | 平台数据 | FStreamedAudioPlatformData 结构 |
| [audio-compression.md](audio-compression.md) | 压缩格式 | ESoundAssetCompressionType 枚举 |
| [audio-version.md](audio-version.md) | 版本差异 | VER_UE4_SOUND 和 UE5 新增字段 |

## 核心源码

- Runtime/Engine/Classes/Sound/SoundWave.h — USoundWave、FStreamedAudioPlatformData、FStreamedAudioChunk、ESoundAssetCompressionType 定义
- Runtime/Engine/Classes/Sound/SoundBase.h — USoundBase 基类定义
- Runtime/Engine/Classes/Sound/SoundWaveLoadingBehavior.h — ESoundWaveLoadingBehavior 枚举
- Runtime/Engine/Private/SoundWave.cpp — 序列化实现

## 相关文档

- [BulkData 存储结构](../bulkdata-region.md) — 音频数据块存储
- [BulkData 运行时机制](../serialization/bulkdata.md) — 流式加载机制
