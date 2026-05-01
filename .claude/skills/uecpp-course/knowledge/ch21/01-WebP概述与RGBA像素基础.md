# WebP 概述与 RGBA 像素基础

## 概述

WebP 是 Google 开发的图像格式，支持有损/无损压缩和动态图片（类似 GIF）。本章展示如何在 UE 中集成 libwebp 库，实现截图→编码→生成本地 .webp 文件。

## WebP 是什么

- **本质**：图片格式，压缩率高，同时支持静态图和动态图
- **与 GIF 对比**：压缩率更高，支持有损+无损，Alpha 通道
- **动态图原理**：连续不断切换的图片，每张带时间戳
- **官网**：Google Developers / libwebp 官方文档提供了编码/解码 API、命令行工具 `cwebp`/`dwebp`

## 动态图片本质

```
时间轴上的图片序列：
  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │ 图片 #1  │→│ 图片 #2  │→│ 图片 #3  │→ ...
  │ 第16ms   │  │ 第40ms   │  │ 第100ms  │
  └─────────┘  └─────────┘  └─────────┘
```

每张图片是一个 RGBA 像素数组，附带一个 `int` 类型时间戳。生成 WebP 时只需记录"时间戳 + 像素数据"。

## RGBA 像素基础

一个像素点由 **4 个字节**组成：

| 通道 | 含义 | 范围 |
|------|------|------|
| R | 红色（Red） | 0~255（uint8） |
| G | 绿色（Green） | 0~255 |
| B | 蓝色（Blue） | 0~255 |
| A | 透明度（Alpha） | 0~255 |

- 一张 1920×1080 的屏幕 = 1920×1080 = 2,073,600 个像素点
- 总数据量 = 1920 × 1080 × 4 字节 ≈ 8.3 MB
- UE 中通过 `FColor`（本质就是 RGBA 四个 `uint8`）来表示一个像素

### Alpha 通道方向差异（重要）

UE 中的 A 通道方向可能与 libwebp 预期相反。如果生成出来的图片全是马赛克或全黑/全白，大概率是 A 通道未反转：

```
A(channel_in_UE)     vs    A(channel_in_libwebp)
  255=完全不透明          vs    255 可能表示完全透明
```

代码中的处理：遍历像素时对 A 通道做 `255 - A` 反转。

## 本案例在课程中的定位

- 是 **第一个综合案例**，将之前学到的：多线程、异步、智能指针、第三方库集成、容器（TArray/TMap）、Subsystem、委托/代理 全部串联
- 承上启下：后续 HTTP/WebSocket 通讯中的"像素推流"技术是本章的升级版
- 引擎不支持原生 WebP，需自行扩展（`UTexture2D` 只支持 PNG/JPG 等静态格式）

## 配套代码

| 组件 | 路径 |
|------|------|
| 插件 | [XGSampleWebP](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWebP/) |
| Demo Actor | [XGSampleWebpActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/023_LibWebP/XGSampleWebpActor.h) |
| 第三方库 | [code/012_第三方库资源/libwebp/](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/012_第三方库资源/) |
| 字幕 | `subtitles/021第二十一章LibWebP的集成使用_生成/` |
