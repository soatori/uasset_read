# 第二十二章：LibWebP 的集成使用——展示篇

## 字幕资源

- 来源：`subtitles/022第二十二章LibWebP的集成使用_展示/`
- 共 6 个字幕文件

## 章节概述

案例 1（LibWebP 集成使用）的下半部分。在第 21 章生成 WebP 的基础上，实现反方向的解码→展示流程：从本地 `.webp` 文件解码出逐帧像素数据，动态创建 `UTexture2D`，通过 Tick 驱动逐帧切换纹理显示在场景中。

## 子模块索引

| 模块 | 文档 | 核心内容 |
|------|------|----------|
| 底层解码 | [01-WebP底层解码接口.md](ch22/01-WebP底层解码接口.md) | WebPDemuxer、LoadDynamicWebpPictureByRGBA、类型转换 |
| 展示入口 | [02-UEC++解码封装与蓝图展示入口.md](ch22/02-UEC++解码封装与蓝图展示入口.md) | ShowMultiSubsystem 状态机、UTexture2D 创建、材质应用 |
| Tick 驱动 | [03-Tick驱动纹理更新机制.md](ch22/03-Tick驱动纹理更新机制.md) | UpdateTextureRegions、帧切换逻辑、生命周期管理 |
| 测试修复 | [04-测试与打包修复.md](ch22/04-测试与打包修复.md) | 完整流程测试、技能汇总 |

## 配套代码工程

| 工程 | 路径 |
|------|------|
| 插件 | `code/001_XGSampleDemo/Plugins/XGSampleWebP/` |
| Demo Actor | `code/001_XGSampleDemo/Source/XGSampleDemo/023_LibWebP/` |

## 关键类索引

| 类名 | 层级 | 职责 |
|------|------|------|
| `FXGSampleWebPLib` | 第二层 | `LoadDynamicWebpPictureByRGBA` 解码实现 |
| `FXGSampleWebPCore` | 第三层 | UE 类型版 `LoadDynamicWebpPicture` |
| `UXGSampleWebpShowMultiSubsystem` | 第四层 | 加载→展示状态控制、Tick 帧切换（继承 FTickableGameObject） |
| `UXGSampleWebPBPLibrary` | 第四层 | `LoadWebp` / `ReleaseLoadedWebp` 蓝图接口 |
| `FXGWebpLoadAndShowWebp` | 委托 | 四参数动态多播委托（bLoad, Texture, W, H） |
| `EXGSampleWebpLoadAndShowType` | 枚举 | 展示状态（None/Loading/Showing） |

## 与第二十一章的关系

第二十一~二十二章是同一案例（案例 1）的上下游：
- 第二十一章（生成）：截图 → 编码 → 生成 .webp 文件
- 第二十二章（展示）：加载 .webp 文件 → 解码 → 逐帧纹理展示

两章共享同一插件 `XGSampleWebP`、同一套四层架构、同一 Subsystem/BPLibrary 体系。
