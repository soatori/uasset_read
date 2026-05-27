# 音频资产版本差异

## 概述

音频资产 (USoundWave) 在 UE4 演进过程中经历多项格式变更，涉及音频压缩格式变更、音频数据存储变更、平台数据序列化等变更。本文档汇总音频相关关键版本差异。

## 版本差异表格

| 版本号 | 变更描述 | 影响字段/结构 |
|-------|----------|---------------|
| 233 | ReverbEffect 资产类型 | ReverbEffect |
| 234 | 音频 SoundClass 图表编辑器 | SoundClassGraphEditor |
| 251 | Atmospheric Fog 缓存数据 | AudioFogData |
| 281 | SoundNodeEnveloper 曲线变更 | EnveloperCurve |
| 318 | 音频压缩类型添加 (VER_UE4_SOUND_COMPRESSION_TYPE_ADDED) | CompressionType |
| 361 | 音频 SlateSound 转换 | SlateSound |
| 409 | 音频并发包 (VER_UE4_SOUND_CONCURRENCY_PACKAGE) | ConcurrencySettings |
| 447 | 音频低通滤波频率 | LowPassFilterFrequency |
| 474 | 音频并发设置结构 | ConcurrencyStructure |
| 511 | 音频引擎版本对象 | EngineVersionObject |
| 518 | 音频 BulkData 存储变更 | AudioBulkData |
| 536 | 音频资产导入数据 JSON | AssetImportData |

## UE5 音频变更

| 特性 | 说明 |
|------|------|
| PayloadTOC | 音频 BulkData 通过 PayloadTOC 管理 |
| Data Resources | 音频大数据通过 Data Resources 表管理 |

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| SoundWave.h | Runtime/Engine/Classes/Sound/ | 音频波形类定义 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*