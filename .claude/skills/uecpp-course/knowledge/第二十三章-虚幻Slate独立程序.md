# 第二十三章：虚幻 Slate 独立程序

## 字幕资源

- 来源：`subtitles/023第二十三章虚幻Slate独立程序/`
- 共 17 个字幕文件（000~016）

---

## 本章概述

本章是课程的**案例2**，讲解如何编写虚幻引擎独立程序。独立程序不包含 Gameplay 框架，基于源码引擎，脱离编辑器直接运行。课程从一个空白的 BlankProgram 开始，逐步搭建 Slate 独立程序框架，编写两个实用工具（文件批量重命名、代码行数统计），最后演示手动打包流程。

## 知识文档索引

| 序号 | 文档 | 覆盖字幕 | 核心内容 |
|------|------|----------|----------|
| 01 | [独立程序概述与BlankProgram创建](ch23/01-独立程序概述与BlankProgram创建.md) | 000, 001 | 独立程序两种类型、环境要求、从模板复制创建 BlankProgram |
| 02 | [Slate独立程序框架搭建](ch23/02-Slate独立程序框架搭建.md) | 002, 003, 004 | Build.cs/Target.cs 配置、引擎初始化序列、主循环框架、帧率控制 |
| 03 | [小程序架构与Tick管理单例](ch23/03-小程序架构与Tick管理单例.md) | 005, 006 | MVC三层架构、Core单例管理器、TickObject接口、弱指针管理 |
| 04 | [Slate基础概述](ch23/04-Slate基础概述.md) | 007 | 类声明宏体系、控件层级、链式编程、槽位系统、Button事件绑定 |
| 05 | [ModifyName的UI布局与文件操作](ch23/05-ModifyName的UI布局与文件操作.md) | 008, 009, 010, 011 | SScrollBox布局、FDesktopPlatformModule文件对话框、IFileManager文件遍历、路径持久化 |
| 06 | [CountCode分帧状态机设计](ch23/06-CountCode分帧状态机设计.md) | 012, 013 | 状态机枚举、类继承关系、构造函数设计、UI日志输出、生命周期管理 |
| 07 | [文件夹深度遍历与文件筛选计数](ch23/07-文件夹深度遍历与文件筛选计数.md) | 014, 015 | 分帧广度优先遍历、文件后缀筛选、行数统计、时间统计汇总 |
| 08 | [独立程序暴力打包](ch23/08-独立程序暴力打包.md) | 016 | 排除法手动打包、最小依赖清单、CEF3/Shader/国际化资源依赖 |

## 关键类/API 速查

| 类/API | 位置 | 用途 |
|--------|------|------|
| `IMPLEMENT_APPLICATION` | `XGSlateSample.cpp` | 声明独立程序模块入口 |
| `FXGSSPCore` | [Core/XGSSPCore.h](ch23/../code/013_独立程序源码/XGSlateSample/Private/Core/XGSSPCore.h) | 单例管理器，Tick 调度 |
| `FXGSSPTickObject` | [Core/XGSSPCountCode.h](ch23/../code/013_独立程序源码/XGSlateSample/Private/Core/XGSSPCountCode.h) | 可 Tick 对象接口 |
| `FXGSSPCountCode` | [Core/XGSSPCountCode.h](ch23/../code/013_独立程序源码/XGSlateSample/Private/Core/XGSSPCountCode.h) | 分帧代码计数业务类 |
| `FXGSSPUtil` | [Util/XGSSPUtil.h](ch23/../code/013_独立程序源码/XGSlateSample/Private/Util/XGSSPUtil.h) | 路径持久化工具 |
| `SXGSSPModifyName` | [Slate/SXGSSPModifyName.h](ch23/../code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPModifyName.h) | ModifyName Tab Slate 控件 |
| `SXGSSPCoundCodeBox` | [Slate/SXGSSPCountCodeBox.h](ch23/../code/013_独立程序源码/XGSlateSample/Private/Slate/SXGSSPCountCodeBox.h) | CountCode Tab Slate 控件 |
| `FDesktopPlatformModule` | 引擎 `DesktopPlatform` 模块 | 平台文件对话框 |
| `FGlobalTabmanager` | 引擎 `Slate` 模块 | Tab 全局管理器 |
| `FSlateApplication` | 引擎 `Slate` 模块 | Slate 独立应用生命期 |

## 代码工程关联

| 目录 | 说明 |
|------|------|
| [code/013_独立程序源码/XGBlankProgram/](ch23/../code/013_独立程序源码/XGBlankProgram/) | 空白独立程序源码 |
| [code/013_独立程序源码/XGSlateSample/](ch23/../code/013_独立程序源码/XGSlateSample/) | Slate 独立程序源码（本章主代码） |
| [code/013_独立程序源码/XGSampleServer/](ch23/../code/013_独立程序源码/XGSampleServer/) | HTTP Server 独立程序源码（第26章） |
| [code/006_SlateViewerTemplate_5.0.3/](ch23/../code/006_SlateViewerTemplate_5.0.3/) | SlateViewer 打包模板 (5.0.3) |
| [code/007_UEProgram1/](ch23/../code/007_UEProgram1/) | 打包产物参考：Slate 独立程序 (5.4.2) |
| [code/008_UEProgram2/](ch23/../code/008_UEProgram2/) | 打包产物参考：HTTP 独立程序 (5.4.2) |

## 与前序章节的关联

| 依赖知识点 | 出处在章节 |
|-----------|----------|
| 智能指针 TSharedPtr/TWeakPtr/TSharedFromThis | 第16章 |
| 单例模式、Subsystem | 第13章 |
| ControlFlows 任务管理模式 | 第18章 |
| 容器的 Add/Remove/Insert/遍历 | 第4~6章 |
| 多线程（可进一步优化分帧） | 第17章 |
