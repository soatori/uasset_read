# 第二十一章：LibWebP 的集成使用——生成篇

## 字幕资源

- 来源：`subtitles/021第二十一章LibWebP的集成使用_生成/`
- 共 14 个字幕文件

## 章节概述

案例 1（LibWebP 集成使用）的上半部分。从零搭建 XGSampleWebP 插件，实现四层封装架构（原生 C API → 纯 C++ 层 → UEC++ 层 → Subsystem/BPLibrary 层），完成视口像素获取、单张/多张 WebP 图片的编码生成。

## 子模块索引

| 模块 | 文档 | 核心内容 |
|------|------|----------|
| 概念基础 | [01-WebP概述与RGBA像素基础.md](ch21/01-WebP概述与RGBA像素基础.md) | WebP 格式、RGBA 像素、动态图原理 |
| 架构设计 | [02-插件四层架构设计.md](ch21/02-插件四层架构设计.md) | 四层封装架构、各层职责与用户画像 |
| 工程搭建 | [03-第三方库插件搭建与模块组织.md](ch21/03-第三方库插件搭建与模块组织.md) | 插件创建、子模块目录、Build.cs 配置 |
| 库集成 | [04-libwebp静态库集成与版本验证.md](ch21/04-libwebp静态库集成与版本验证.md) | .lib 导入、版本 API、授权机制、编码问题 |
| 编码接口 | [05-单张WebP底层编码接口.md](ch21/05-单张WebP底层编码接口.md) | GenerateWebpByRGBA、WebPEncodeRGBA、质量因子 |
| 像素获取 | [06-视口像素获取与截图回调.md](ch21/06-视口像素获取与截图回调.md) | FScreenshotRequest、GameViewportClient 截图代理 |
| 动态编码 | [07-多张动态WebP底层编码接口.md](ch21/07-多张动态WebP底层编码接口.md) | WebPAnimEncoder、多帧合成、时间戳 |
| Subsystem | [08-多张WebP生成Subsystem与蓝图接口.md](ch21/08-多张WebP生成Subsystem与蓝图接口.md) | MultiShotSubsystem 状态机、BeginRecord/EndRecord |
| 线程模型 | [09-单张与多张WebP线程交互模型.md](ch21/09-单张与多张WebP线程交互模型.md) | GameThread→RenderThread→WorkerThread 完整链路 |
| 测试调试 | [10-测试调试与打包修复.md](ch21/10-测试调试与打包修复.md) | 蓝图层测试、A 通道反转、打包注意事项 |

## 配套代码工程

| 工程 | 路径 |
|------|------|
| 插件 | `code/001_XGSampleDemo/Plugins/XGSampleWebP/` |
| Demo Actor | `code/001_XGSampleDemo/Source/XGSampleDemo/023_LibWebP/` |
| 第三方库 | `code/012_第三方库资源/libwebp/` |
| 插件第三方依赖 | `code/001_XGSampleDemo/Plugins/XGSampleWebP/Source/ThirdParty/XGSampleWebPLibrary/` |

## 关键类索引

| 类名 | 层级 | 职责 |
|------|------|------|
| `FXGSampleWebPLib` | 第二层：纯 C++ | 封装原生 libwebp API，使用 `friend` 保护 |
| `FXGSampleWebPCore` | 第三层：UEC++ | UE 类型 ↔ C++ 类型转换，参数校验 |
| `UXGSampleWebPOneShotSubsystem` | 第四层 | 单张 WebP 生成控制 |
| `UXGSampleWebPMultiShotSubsystem` | 第四层 | 多张动态 WebP 生成控制（继承 FTickableGameObject） |
| `UXGSampleWebPBPLibrary` | 第四层 | 蓝图暴露的静态函数入口 |
| `FXGSampleWebpPictureInformation` | 数据结构 | 图片裁剪四角坐标 |
| `EXGSampleWebpProcessType` | 枚举 | 生成状态（None/Recording/Generating） |
