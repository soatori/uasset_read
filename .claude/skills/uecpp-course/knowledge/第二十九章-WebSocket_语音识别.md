# 第二十九章：WebSocket——语音识别

## 字幕资源

- 来源：`subtitles/029第二十九章WebSocket_语音识别/`
- 共 16 个字幕文件（001~015）

---

## 细粒度知识文档

| 文档 | 内容 |
|------|------|
| [01-知识概览](ch29/01-知识概览.md) | 章节概述、文件索引、Pipeline、与第二十七章/三十章的对比 |
| [02-STT子系统与状态机](ch29/02-STT子系统与状态机.md) | UXGSampleSTTSubsystem、状态机（Ready/Init/WaitToServerClose）、WebSocket 生命周期 |
| [03-音频采集子系统](ch29/03-音频采集子系统.md) | UXGSampleAudioCaptureSubsystem、UAudioCapture、OnAudioGenerate 回调 |
| [04-音频重采样与格式转换](ch29/04-音频重采样与格式转换.md) | 48K/44.1K→16K 降采样、LinearResample 线性插值、float→int16→uint8 转换 |
| [05-音频消费线程](ch29/05-音频消费线程.md) | FXGSampleConsumeVoiceRunnable、FRunnable 轮询模型、生产者-消费者模式 |
| [06-讯飞STT认证与WebSocket通信](ch29/06-讯飞STT认证与WebSocket通信.md) | HMAC-SHA1 鉴权、GenerateRequireParams、009_WebSocketJson 协议模板 |
| [07-STT响应解析](ch29/07-STT响应解析.md) | JSON 解析、started/result/error 三种响应、蓝图委托回调 |
| [08-麦克风音量计算](ch29/08-麦克风音量计算.md) | RMS 均方根算法、跨线程音量传递、AsyncTask 游戏线程回调 |
| [09-蓝图接口](ch29/09-蓝图接口.md) | BPLibrary 五个静态函数、Start/Stop/ForceToStop/IsWorking/GetVolume |

## 知识架构

```
┌─────────────────────────────────────────────────────────────┐
│                  XGSampleXFLink 插件                          │
│                                                             │
│  UXGSampleXFLinkBPLibrary (Blueprint 入口)                   │
│         ↓                                                    │
│  UXGSampleSTTSubsystem (UGameInstanceSubsystem, WebSocket)  │
│         ├── WebSocket → ws://rtasr.xfyun.cn/v1/ws           │
│         ├── FXGSampleConsumeVoiceRunnable (FRunnable 线程)   │
│         └── UXGSampleAudioCaptureSubsystem (音频采集)        │
│                                                             │
│  协议参考: 009_WebSocketJson/ (InitJson/MessJson/TickJson)   │
└─────────────────────────────────────────────────────────────┘
```
