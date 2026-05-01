# 独立程序概述与BlankProgram创建

## 概述

虚幻引擎独立程序是与游戏工程项目不同类型的可执行程序。它不包含 Gameplay 框架（无 World、无 Actor），纯粹基于 U 类和引擎底层运行，承担特定工具任务。独立程序是高级/资深 UE 开发者的必备知识。

## 两种类型

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| 命令行独立程序 | 基于 BlankProgram 模板，纯控制台输出 | 小服务器、增删改查本地工具、自动化脚本 |
| Slate UI 独立程序 | 基于 SlateViewer 模板，带可视化窗口界面 | 编辑器工具、工业化数字孪生平台、资产处理工具 |

两者都脱离 Gameplay 框架，直接操作 U 类。对引擎底层框架不熟悉则极易出错。

## 环境要求

- 必须使用**源码引擎**（发布版引擎无法创建独立程序）
- 建议对引擎源码做版本管理（Git），避免改坏后无法恢复
- 磁盘空间至少 300GB+（源码引擎+编译产物）
- 课程基于 UE 5.4.2，已验证 5.0~5.4 兼容
- VS 各版本要求：5.0 需 VS2019，5.4 需 VS2022

## BlankProgram 创建流程

### 1. 复制模板

从引擎源码目录复制 BlankProgram 模板：

```
Engine/Source/Programs/BlankProgram/  →  复制为新目录 XGBlankProgram/
```

### 2. 文件重命名

复制后需要逐个文件修改类名、Module 名、Target 名，前缀统一加 `XG`：

| 文件 | 修改内容 |
|------|----------|
| `XGBlankProgram.Target.cs` | 类名加 `XG` 前缀 |
| `XGBlankProgram.Build.cs` | Module 名加 `XG` 前缀 |
| `Private/XGBlankProgram.h` | 类名、Log 类别名加 `XG` 前缀 |
| `Private/XGBlankProgram.cpp` | `IMPLEMENT_APPLICATION` 宏参数、Log 声明 |
| `Resources/Windows/BlankProgram.ico` | 可不改 |

### 3. 关键代码修改点

**IMPLEMENT_APPLICATION 宏** — 此宏声明独立程序的入口：
```cpp
IMPLEMENT_APPLICATION(XGBlankProgram, "XGBlankProgram");
```

**日志声明** — 从引擎模板的日志改为自定义：
```cpp
DEFINE_LOG_CATEGORY_STATIC(LogXGBlankProgram, Log, All);
```

**WinMain 主函数** — 独立程序的真正入口，负责引擎初始化→执行业务→引擎退出：
```cpp
int WINAPI WinMain(...)
{
    GEngineLoop.PreInit(CommandLine);      // 引擎预初始化
    // ... 业务代码 ...
    GEngineLoop.AppPreExit();              // 引擎预退出
    FModuleManager::Get().UnloadModulesAtShutdown();
    GEngineLoop.AppExit();                 // 引擎真正退出
    return 0;
}
```

## 独立程序的限制

- **不能使用 Nigara 模块**：独立程序中编译 Nigara 会失败
- **不能使用继承 UBlueprintFunctionLibrary 的插件类**：需改为继承 `UObject`
- 不能使用 Gameplay 框架：无 World、无 Actor、无 GameMode
- Subsystem 依赖于 Engine 模块，独立程序中不可直接使用

## 配套代码

| 文件 | 路径 |
|------|------|
| XGBlankProgram.h | [code/013_独立程序源码/XGBlankProgram/Private/XGBlankProgram.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGBlankProgram/Private/XGBlankProgram.h) |
| XGBlankProgram.cpp | [code/013_独立程序源码/XGBlankProgram/Private/XGBlankProgram.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGBlankProgram/Private/XGBlankProgram.cpp) |
| XGBlankProgram.Target.cs | [code/013_独立程序源码/XGBlankProgram/XGBlankProgram.Target.cs](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/013_独立程序源码/XGBlankProgram/XGBlankProgram.Target.cs) |
| SlateViewerTemplate_5.0.3 | [code/006_SlateViewerTemplate_5.0.3/](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/006_SlateViewerTemplate_5.0.3/) — 5.0.3 版本 SlateViewer 模板参考 |
