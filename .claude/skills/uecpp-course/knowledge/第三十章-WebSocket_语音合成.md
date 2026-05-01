# 第三十章：WebSocket——语音合成

## 字幕资源

- 来源：`subtitles/030第三十章WebSocket_语音合成/`
- 共 8 个字幕文件（001~008）

---

## 细粒度知识文档

| 文档 | 内容 |
|------|------|
| [01-知识概览](ch30/01-知识概览.md) | 章节概述、文件索引、Pipeline、与第二十九章的对比 |
| [02-TTS异步节点架构](ch30/02-TTS异步节点架构.md) | UBlueprintAsyncActionBase、工厂方法、四输出引脚、生命周期 |
| [03-讯飞TTS认证与WebSocket通信](ch30/03-讯飞TTS认证与WebSocket通信.md) | HMAC-SHA256 鉴权、AssembleAuthUrl、JSON 请求/响应协议 |
| [04-请求参数体系](ch30/04-请求参数体系.md) | 三层嵌套 USTRUCT（common/business/data）、发音人/语速/音量参数 |
| [05-响应解析与音频数据提取](ch30/05-响应解析与音频数据提取.md) | JSON 反序列化、code 检查、Base64 解码、音频累积 |
| [06-USoundWave创建三种方式](ch30/06-USoundWave创建三种方式.md) | RawPCMData / RawData / FSampleBuffer 三种创建方式对比 |
| [07-WAV文件生成与存储](ch30/07-WAV文件生成与存储.md) | WAV 文件结构（RIFF/fmt/data）、ConvertPCMToWave、异步保存 |
| [08-文本编码与Base64](ch30/08-文本编码与Base64.md) | FString→UTF-8→Base64 编码链路、TCHAR_TO_UTF8 原理 |

## 知识架构

```
┌─────────────────────────────────────────────────────┐
│               XGSampleXFLink 插件                     │
│                                                     │
│  UXGSampleTTSAsyncAction (UBlueprintAsyncActionBase) │
│         ├── WebSocket → ws://tts-api.xfyun.cn/v2/tts │
│         ├── AssembleAuthUrl (HMAC-SHA256 鉴权)        │
│         ├── FJsonObjectConverter (UStruct↔JSON)      │
│         ├── USoundWave 创建 (内存播放)                │
│         └── WAV 文件保存 (磁盘存储)                   │
│                                                     │
│  请求参数: FXGXunFeiTTSReqInfo (三层嵌套 USTRUCT)     │
│  响应解析: FXGXunFeiTTSRespInfo (Base64 音频)        │
└─────────────────────────────────────────────────────┘
```
