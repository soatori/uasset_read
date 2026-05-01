# 第十八章：ControlFlows

## 章节概述

本章讲解 Unreal Engine 5 的 **ControlFlows** 异步任务编排框架。ControlFlows 是 UE5 实验性插件（源自 Lyra 项目），用于将多个异步步骤组织为线性链条，避免回调嵌套。在此基础上，课程实现了 **ManageTask** 并行子任务管理系统，通过 FTickableGameObject 的 Tick 轮询检测大量并行子任务的完成状态。三个层次的异步模型贯穿本章：同步线性执行、逐步骤独立异步、管理任务并行拆分。

## 核心架构

```
InitLevel (入口)
  │
  ├─ InitLocalAsset ───── AsyncTask(AnyThread) → Sleep → AsyncTask(GameThread) → ContinueFlow
  ├─ InitNetInfo ──────── ManageTask (10 个子任务并行) ─── Tick 轮询完成 → ContinueFlow/CancelFlow
  ├─ InitUserInfo ─────── AsyncTask(AnyThread) → FFileHelper 写文件 → AsyncTask(GameThread) → ContinueFlow
  ├─ NotifyMainUI ─────── 根据宏开关广播 InitResult 或 ContinueFlow
  └─ FinishThisInit ──── 广播最终结果 → bIniting = false
```

## 字幕资源

- 来源：`subtitles/018第十八章ControlFlows/`
- 共 10 个字幕文件（001~010）
- 代码：`code/001_XGSampleDemo/Source/XGSampleDemo/021_ControlFlows/`

## 知识文档

### 核心框架

| 文档 | 对应字幕 | 说明 |
|------|----------|------|
| [01-FControlFlow异步编排框架](ch18/01-FControlFlow异步编排框架.md) | 001, 004 | FControlFlow API（Create/QueueStep/ContinueFlow/CancelFlow）、生命周期、帧计数器 |
| [02-模块配置与插件依赖](ch18/02-模块配置与插件依赖.md) | 003 | ControlFlows 插件启用、.uproject 配置、.Build.cs 依赖 |
| [03-蓝图交互委托框架](ch18/03-蓝图交互委托框架.md) | 005 | 动态多播委托、FGuid 实例标识、InitProgress/InitResult 模式 |

### 异步执行模型

| 文档 | 对应字幕 | 说明 |
|------|----------|------|
| [04-异步执行与线程跳跃模式](ch18/04-异步执行与线程跳跃模式.md) | 006, 007 | AnyThread→GameThread 线程跳跃、FFileHelper 持久化、XGCONCTROLRESULT 宏 |
| [05-ManageTask并行子任务架构](ch18/05-ManageTask并行子任务架构.md) | 007, 008, 009 | ManageTask 结构体、SubTask 生命周期、状态检测算法 |
| [06-Tick状态检测与资源清理](ch18/06-Tick状态检测与资源清理.md) | 009, 010 | FTickableGameObject、Tick 轮询、管理任务清理、常见 Bug 修复 |

## 代码对应关系

| 代码文件 | 对应知识文档 |
|----------|-------------|
| `XGControlFlowsSubsystem.h/.cpp` | 所有文档 — 子系统核心实现 |
| `XGControlFlowsActor.h/.cpp` | [01-FControlFlow异步编排框架](ch18/01-FControlFlow异步编排框架.md) — Actor 调用入口 |

## 关键知识点

1. **FControlFlowStatics::Create** 创建命名 ControlFlow 实例，**QueueStep** 将步骤加入链中，**ExecuteFlow** 启动执行
2. 每个 QueueStep 接受回调函数 `(FControlFlowNodeRef, double)`，通过 `SubFlow->ContinueFlow()` 通知框架进入下一步
3. **ControlFlows 插件**源自 Lyra，需要在 `.uproject` 的 `Plugins` 数组和 `.Build.cs` 的 `PublicDependencyModuleNames` 中启用
4. **线程跳跃模式**：`AsyncTask(AnyThread)` 做后台工作 → `AsyncTask(GameThread)` 回主线程广播结果并调用 ContinueFlow
5. **ManageTask** 是自定义的管理结构体，管理 N 个并行子任务，通过 Tick 轮询 `CheckManageTaskStatus()` 检测完成状态
6. **FTickableGameObject** 使 Subsystem 每帧 Tick，用于检查 ManageList 中的任务是否全部完成
7. **XGCONCTROLRESULT** 宏（0/1）切换失败/成功模拟，是 Epic 风格的开发期调试手段
8. 实际代码中已修正字幕讲解时的三个 Bug：FGuid 未初始化、ManageTaskStatus 未初始化、CheckManageTaskStatus 默认返回 Processing 的问题
9. **BlueprintAssignable 委托**必须在 GameThread 广播，跨线程时通过 AsyncTask 推回 GameThread

## 操作记录

见 [log.md](log.md)。
