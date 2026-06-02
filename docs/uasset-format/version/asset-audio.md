# 音频资产版本差异

## 概述

音频资产 (USoundWave) 在 UE4 至 UE5 演进过程中经历多项格式变更，涉及音频压缩格式变更、音频数据存储变更、平台数据序列化等变更。本文档汇总音频相关关键版本差异。

> **源码同步状态**: 基于 `ObjectVersion.h` EUnrealEngineObjectUE4Version 枚举。

## UE4 版本差异表格

| 版本号 | 版本名 | 变更描述 | 影响字段/结构 |
|-------|--------|----------|---------------|
| 233 | VER_UE4_REVERB_EFFECT_ASSET_TYPE | ReverbEffect 资产类型 | ReverbEffect |
| 234 | VER_UE4_SOUND_CLASS_GRAPH_EDITOR | 音频 SoundClass 图表编辑器 | SoundClassGraphEditor |
| 251 | VER_UE4_ATMOSPHERIC_FOG_CACHE_DATA | Atmospheric Fog 缓存数据 | AudioFogData |
| 281 | VER_UE4_SOUND_NODE_ENVELOPER_CURVE_CHANGE | SoundNodeEnveloper 曲线变更 | EnveloperCurve |
| 318 | VER_UE4_SOUND_COMPRESSION_TYPE_ADDED | 音频压缩类型添加 | CompressionType |
| 361 | VER_UE4_FSLATESOUND_CONVERSION | 音频 SlateSound 转换 | SlateSound |
| 409 | VER_UE4_SOUND_CONCURRENCY_PACKAGE | 音频并发包 | ConcurrencySettings |
| 447 | VER_UE4_USE_LOW_PASS_FILTER_FREQ | 音频低通滤波频率 | LowPassFilterFrequency |
| 474 | VER_UE4_ENGINE_VERSION_OBJECT | 音频引擎版本对象 | EngineVersionObject |
| 518 | VER_UE4_SKINWEIGHT_PROFILE_DATA_LAYOUT_CHANGES | 音频 BulkData 存储变更 | AudioBulkData |
| 536 | VER_UE4_ASSET_IMPORT_DATA_AS_JSON | 音频资产导入数据 JSON | AssetImportData |

## UE5 音频变更

| 特性 | 版本 | 说明 |
|------|------|------|
| PayloadTOC | 1002 | 音频 BulkData 通过 PayloadTOC 管理 |
| Data Resources | 1009 | 音频大数据通过 Data Resources 表管理 |
| MetaSound | UE5.0+ | MetaSound 系统（独立架构） |

## 关键变更详细说明

### VER_UE4_REVERB_EFFECT_ASSET_TYPE (233)

ReverbEffect 作为独立资产类型引入：
- 版本 < 233：混响效果内嵌于其他资产
- 版本 >= 233：UReverbEffect 作为独立资产类型

### VER_UE4_SOUND_CLASS_GRAPH_EDITOR (234)

SoundClass 图表编辑器：
- 版本 < 234：SoundClass 通过属性面板编辑
- 版本 >= 234：使用图表编辑器可视化编辑 SoundClass 层次

### VER_UE4_SOUND_COMPRESSION_TYPE_ADDED (318)

音频压缩类型字段：
- 版本 < 318：无压缩类型字段
- 版本 >= 318：USoundWave 包含 CompressionType 字段
- 支持 OGG、ADPCM、Opus 等压缩格式

### VER_UE4_FSLATESOUND_CONVERSION (361)

FName 音频名称转为 FSlateSound：
- 版本 < 361：音频引用使用 FName
- 版本 >= 361：转换为 FSlateSound 结构

### VER_UE4_SOUND_CONCURRENCY_PACKAGE (409)

音频并发设置：
- 版本 < 409：并发设置内嵌
- 版本 >= 409：使用独立的 SoundConcurrency 资产
- 支持并发限制、音量管理、优先级

### VER_UE4_USE_LOW_PASS_FILTER_FREQ (447)

高通/低通滤波频率重命名：
- HighFrequencyGain → LowPassFilterFrequency
- 语义更明确的参数命名

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| SoundWave.h | Runtime/Engine/Classes/Sound/ | 音频波形类定义 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*
*Updated: 2026-06-01 — 基于 UE ObjectVersion.h 完整枚举同步版本号与版本名*
