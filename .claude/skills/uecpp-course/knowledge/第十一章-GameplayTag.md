# 第十一章：GameplayTag

## 字幕资源

- 来源：`subtitles/011第十一章GameplayTag/`
- 共 4 个字幕文件（001~004）

## 代码资源

- 来源：`code/001_XGSampleDemo/Source/XGSampleDemo/014_Tag/`
- 代码文件：
  - [XGTagType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/014_Tag/XGTagType.h) — GameplayTag 宏声明（模块级）
  - [XGTagType.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/014_Tag/XGTagType.cpp) — GameplayTag 宏定义
  - [XGTagActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/014_Tag/XGTagActor.h) — GameplayTag Actor，实现 IGameplayTagAssetInterface
  - [XGTagActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/014_Tag/XGTagActor.cpp) — 容器操作与 BeginPlay 执行顺序

## 知识文档

### 核心概念

| # | 文档 | 内容 |
|---|------|------|
| 01 | [GameplayTag 概述与设计动机](ch11/01-GameplayTag概述与设计动机.md) | bool→enum→GameplayTag 演进，层级结构定义，与 FName 标签的区别 |
| 02 | [GameplayTag 的四种创建方式](ch11/02-GameplayTag的四种创建方式.md) | Project Settings / INI / Data Table / C++ 宏，打包前注册约束 |
| 03 | [GameplayTag 匹配操作](ch11/03-GameplayTag匹配操作.md) | MatchTag/MatchAny/MatchAll，概念包含 vs 精确，GameplayTagQuery |

### C++ 实践

| # | 文档 | 内容 |
|---|------|------|
| 04 | [GameplayTag 的 C++ 声明与使用](ch11/04-GameplayTag的C++声明与使用.md) | UE_DECLARE/UE_DEFINE 宏模式，Build.cs 配置，运行时 RequestGameplayTag |
| 05 | [FGameplayTagContainer 与 GetOwnedGameplayTags](ch11/05-FGameplayTagContainer与GetOwnedGameplayTags.md) | 容器操作 API，IGameplayTagAssetInterface 接口，多容器聚合模式，Blueprint 叠加问题 |
| 06 | [GameplayTag 版本兼容问题](ch11/06-GameplayTag版本兼容问题.md) | UE5.5+ GetOwnedGameplayTags Self 引脚修复 |

---

> 操作记录见 [log.md](log.md)。
