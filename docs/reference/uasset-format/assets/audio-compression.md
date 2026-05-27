# 音频压缩格式

## 概述

USoundWave 使用块压缩格式减少音频数据存储大小。引擎提供多种压缩格式选项，根据质量、延迟、兼容性等需求选择。

**决策 D-46:** 简要格式枚举，不展开每种格式详细结构。

## ESoundAssetCompressionType 块压缩格式枚举

| 枚举值 | 说明 | 适用场景 | 压缩比 |
|--------|------|----------|--------|
| BinkAudio | 感知编解码器，支持所有平台特性 | 通用音频，高兼容性 | 可调节 |
| RADAudio | 更高质量的 BinkAudio | 高质量音频，采样率限制 (48000/44100/32000/24000) | 可调节 |
| ADPCM | 自适应差分脉冲编码调制，固定质量 | 低延迟音频 (对话、UI音效) | ~4x |
| PCM | 未压缩音频 | 高质量音频，大数据 | 无压缩 |
| Opus | Opus 编解码器 | 低延迟语音通信，流式应用 | 高压缩比 |
| PlatformSpecific | 平台特定格式 | 平台优化音频，不支持 Seek | 平台依赖 |
| ProjectDefined | 项目定义编解码器 | 使用项目默认设置 | 项目依赖 |

**源码位置:** SoundWave.h:342-367

### 格式特性对比

| 特性 | BinkAudio/RADAudio | ADPCM | PCM | Opus |
|------|-------------------|-------|-----|------|
| 压缩质量 | 可调节 (1-100) | 固定质量 | 最高 | 可调节 |
| 压缩比 | 可变 | ~4x | 无 | 高 |
| 解码延迟 | 中等 | 低 | 极低 | 低 |
| Seek 支持 | 支持 | 支持 | 支持 | 支持 |
| 兼容性 | 所有平台 | 所有平台 | 所有平台 | 所有平台 |
| CPU 开销 | 中等 | 低 | 极低 | 低-中 |

## EDecompressionType 解压缩缓冲类型

| 枚举值 | 说明 | 用途 |
|--------|------|------|
| DTYPE_Setup | 设置阶段 | 初始化解压缩 |
| DTYPE_Invalid | 无效类型 | 错误状态 |
| DTYPE_RealTime | 实时解压缩 | 运行时解压到缓冲区 |
| DTYPE_Procedural | 程序生成 | 程序化音频数据 |
| DTYPE_Xenon | Xenon 平台 (已弃用) | 遗留支持 |
| DTYPE_Streaming | 流式解压缩 | 流式播放音频 |

**源码位置:** SoundWave.h:44-54

## CompressionQuality 质量设置

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| CompressionQuality | int32 | 压缩质量 (1-100)，1=最佳压缩，100=最佳质量 | SoundWave.h:424 |
| SoundAssetCompressionType | ESoundAssetCompressionType | 压缩格式类型 | SoundWave.h:463 |

**注意:** ADPCM 和 PCM 格式忽略 CompressionQuality 参数。

## 压缩选择指南

### 按场景选择

| 场景 | 推荐格式 | 原因 |
|------|----------|------|
| 对话语音 | ADPCM | 低延迟，固定压缩比，CPU 开销低 |
| 环境音效 | BinkAudio/RADAudio | 高压缩比，支持所有特性 |
| 背景音乐 | Opus | 高压缩比，流式友好 |
| UI 音效 | PCM 或 ADPCM | 低延迟，快速响应 |
| 语音通信 | Opus | 低延迟，专为语音设计 |
| 长音频 | PlatformSpecific | 平台优化，最大化压缩 |
| 通用音频 | ProjectDefined | 使用项目统一设置 |

### 按质量需求选择

| 质量等级 | CompressionQuality | 适用格式 |
|----------|-------------------|----------|
| 最佳压缩 | 1-20 | BinkAudio, RADAudio, Opus |
| 平衡质量 | 40-60 | BinkAudio, RADAudio, Opus |
| 最佳质量 | 80-100 | BinkAudio, RADAudio, Opus |
| 最高质量 | N/A | PCM (无压缩) |
| 固定质量 | N/A | ADPCM (~4x 固定) |

## 源码引用

- Runtime/Engine/Classes/Sound/SoundWave.h — ESoundAssetCompressionType, EDecompressionType 定义
- Runtime/Engine/Private/Sound/SoundWave.cpp — 压缩格式序列化实现
- Runtime/Engine/Private/Audio/AudioCompressionSettings.cpp — 压缩配置实现

## 版本差异

### UE5 新增

- **RADAudio**: 新增格式，比 BinkAudio 更高质量，采样率限制 (48000/44100/32000/24000)
- **ProjectDefined**: 新增类型，使用项目默认编解码器设置
- **SoundAssetCompressionType**: 替代 UE4 的零散布尔属性 (bUseBinkAudio, bSeekableStreaming)

### UE4 vs UE5

| UE4 属性 | UE5 替代 |
|----------|----------|
| bUseBinkAudio | SoundAssetCompressionType::BinkAudio |
| bSeekableStreaming | SoundAssetCompressionType::ADPCM (5.0 已弃用) |
| OGG 格式 | SoundAssetCompressionType::Opus |

**注:** UE4 使用传统布尔属性控制压缩格式，UE5 统一为枚举类型。

## 相关文档

- [音频基础结构](audio-structure.md) — USoundWave 属性字段表
- [BulkData 存储机制](../bulkdata-region.md) — 音频数据存储结构