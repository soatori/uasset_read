# 第二十七章：HTTP 上传文件——摄像头活体检测

## 概述

实现"摄像头活体检测"：通过 UE Media Framework 捕获摄像头视频帧，转换为 PNG 二进制数据，通过 HTTP POST 上传到科大讯飞静默活体检测 API，解析人脸检测结果。

## 细粒度知识文档

| 文档 | 内容 |
|------|------|
| [01-知识概览](ch27/01-知识概览.md) | 章节架构、Pipeline 总览、文件索引、边界说明 |
| [02-异步蓝图节点框架](ch27/02-异步蓝图节点框架.md) | UBlueprintAsyncActionBase 模式、委托、工厂方法、Activate/Release |
| [03-RenderTarget2D转PNG](ch27/03-RenderTarget2D转PNG.md) | ReadPixels、Alpha 修正、FImageUtils::ExportToPNG 异步 |
| [04-摄像头视频流整合](ch27/04-摄像头视频流整合.md) | Media Framework、设备枚举、轨道选择、DrawMaterialToRenderTarget |
| [05-HMAC-SHA256鉴权与URL签名](ch27/05-HMAC-SHA256鉴权与URL签名.md) | OpenSSL HMAC-SHA256、三级鉴权、完整签名流程 |
| [06-请求体构造与HTTP发送](ch27/06-请求体构造与HTTP发送.md) | JSON body 三级结构、Base64 编码、4MB 限制、HTTP 发送 |
| [07-响应解析](ch27/07-响应解析.md) | 一级/二级服务码、RawMessage/TextMessage 解析 |
| [08-UObject生命周期管理](ch27/08-UObject生命周期管理.md) | GC 回收预防、RegisterWithGameInstance、Super::Activate |
| [09-插件架构与模块依赖](ch27/09-插件架构与模块依赖.md) | 两插件设计、Build.cs 依赖、加密库 ThirdParty 结构 |

## 关键架构

### 两插件分离

```
XGSamplePicture（摄像头→PNG） ───依赖──→ XGSampleLink/XGSampleXFLink（讯飞HTTP通讯）
```

- **XGSamplePicture**：Media Framework 摄像头 + RenderTarget2D → PNG
- **XGSampleXFLink**：HMAC-SHA256 签名 + HTTP POST + 响应解析
- **XGSampleXFLinkLibrary**（ThirdParty 加密库）：OpenSSL 封装、Xunfei/Baidu 签名、URL 编码

### 数据流

```
Camera → MediaPlayer → MediaTexture → Material → RenderTarget2D
    → ReadPixels → PNG 压缩 → Base64 → JSON Body → HTTP POST → 讯飞 API
    → 一级鉴权 → 二级业务解析 → BP Delegate
```

## 字幕资源

- 来源：`subtitles/027第二十七章HTTP上传文件_摄像头活体检测/`
- 共 15 个字幕文件（001-015）

## 操作日志

见 [log.md](log.md)。
