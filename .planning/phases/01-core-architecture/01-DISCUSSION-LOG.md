# Phase 1: 核心架构与基础解析 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 1-核心架构与基础解析
**Areas discussed:** 解析库使用边界, CustomVersion 映射策略, 测试文件来源, 错误处理策略

---

## 解析库使用边界

| Option | Description | Selected |
|--------|-------------|----------|
| 主结构用 dissect | FPackageFileSummary 用 dissect.cstruct 定义，接近 C 语法便于与 UE 源码对比验证 | |
| 主结构用 struct (推荐) | FPackageFileSummary 用 struct.Struct 预编译，性能最优 | ✓ |
| 纯 struct 实现 | 全部使用 struct.Struct，最大化性能和源码可追溯性 | |

**User's choice:** 主结构用 struct (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| CustomVersion 也用 struct | CustomVersionContainer 结构简单（GUID + int32），用 struct 更高效 | ✓ |
| CustomVersion 用 dissect | GUID + Version 可用 dissect.cstruct 定义为子结构，可读性更好 | |
| 动态边界 | 根据字段数量动态选择：≤4 字节用 struct，>4 字节或有嵌套用 dissect | |

**User's choice:** CustomVersion 也用 struct

---

| Option | Description | Selected |
|--------|-------------|----------|
| FString 用 struct + 手动逻辑 | FString 有版本差异逻辑（UE4 vs UE5），逻辑复杂度超过结构本身 | ✓ |
| FString 结构用 dissect | FString 结构定义用 dissect，但读取逻辑仍手动处理版本差异 | |
| FString 全用 dissect | 完全用 dissect.cstruct 定义，包括条件字段 | |

**User's choice:** FString 用 struct + 手动逻辑

---

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 1 纯 struct | Phase 1 全部用 struct + 手动逻辑，保持一致性和最大性能 | |
| 按需决策 (推荐) | 已确定核心结构用 struct；后续遇到真正复杂的嵌套结构时再按需选择 | ✓ |
| 版本条件 = struct | 定义明确边界：所有带版本条件判断的结构用 struct，所有固定结构可考虑 dissect | |

**User's choice:** 按需决策 (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| 常量定义 | 每个结构单独定义 struct.Struct 常量 | |
| 偏移类封装 (推荐) | 定义 SummaryOffsets 类封装偏移常量，动态计算字段位置（支持版本差异） | ✓ |
| 直接调用 | 直接在代码中使用 struct.unpack，不预编译（性能最低） | |

**User's choice:** 偏移类封装 (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| 直接赋值 | struct.unpack 结果直接赋值给字段，无中间结构 | |
| dataclass 封装 (推荐) | 定义 dataclass 或 TypedDict 存储解析结果，便于类型检查和 IDE 支持 | ✓ |
| pydantic 模型 | 使用 pydantic BaseModel，增加验证但增加依赖 | |

**User's choice:** dataclass 封装 (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 1 不引入 dissect | dissect.cstruct 作为可选工具，Phase 1 不使用 | |
| 引入作为辅助工具 (推荐) | 引入 dissect.cstruct 作为依赖，定义辅助结构，但不用于主解析 | ✓ |
| 完全不用 dissect | 不使用 dissect.cstruct，完全依赖 Python 标准库 | |

**User's choice:** 引入作为辅助工具 (推荐)

---

## CustomVersion 映射策略

| Option | Description | Selected |
|--------|-------------|----------|
| 硬编码常量字典 (推荐) | 从 UE 源码 ObjectVersion.h 提取所有 GUID 和名称，硬编码为 Python 常量字典 | ✓ |
| 动态注册表 | 定义注册表类，允许动态添加新版本映射，支持未来扩展 | |
| 外部配置文件 | GUID 到名称映射存为外部 JSON/YAML 文件 | |

**User's choice:** 硬编码常量字典 (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| 最小集合 | 只包含 Phase 1 需要的核心版本 | |
| 完整提取 (推荐) | 从 UE ObjectVersion.h 提取所有已定义的 CustomVersion（约 100+） | ✓ |
| 常用集合 | 包含常用版本 + 可能遇到的版本 | |

**User's choice:** 完整提取 (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| 记录原始值继续 (推荐) | 解析时如遇到未识别 GUID，记录原始 GUID 值，不中断解析 | ✓ |
| 警告继续 | 未识别 GUID 抛出警告，但继续解析 | |
| 异常停止 | 未识别 GUID 抛出异常，停止解析 | |

**User's choice:** 记录原始值继续 (推荐)

---

## 测试文件来源

| Option | Description | Selected |
|--------|-------------|----------|
| UE 源码示例项目 (推荐) | 使用 E:\Develop\lib\UnrealEngine\Samples 中的示例项目资产 | ✓ |
| 自己创建测试资产 | 自己用 UE Editor 创建简单测试资产 | |
| 第三方项目测试数据 | 从 FModel/pyUE4Parse 等项目的测试数据获取 | |

**User's choice:** UE 源码示例项目 (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| 单个示例项目 | 选择一个简单项目（如 ContentExamples） | |
| 多版本覆盖 (推荐) | 从多个示例项目中选择不同 UE 版本的资产，覆盖 UE4 到 UE5 | ✓ |
| 最小验证 | 先找一个最简单的资产验证基础解析 | |

**User's choice:** 多版本覆盖 (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| 复制到项目目录 (推荐) | 测试文件复制到项目 tests/fixtures 目录 | |
| 读取原始路径 | 测试时直接读取 UE 源码路径 | |
| 灵活支持 | 两种都支持：默认读取项目目录，可选读取原始路径 | ✓ |

**User's choice:** 灵活支持

---

## 错误处理策略

| Option | Description | Selected |
|--------|-------------|----------|
| 立即异常停止 | 立即抛出异常并停止，适合严格验证场景 | |
| 记录错误继续 (推荐) | 记录错误信息到解析结果，继续尝试解析剩余部分 | ✓ |
| 分级处理 | 分为致命错误（停止）和非致命错误（继续） | |

**User's choice:** 记录错误继续 (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| 关键错误停止 (推荐) | 魔数不匹配、文件无法打开等关键错误，立即停止 | ✓ |
| 所有错误继续 | 所有错误都记录并继续 | |
| 严格停止 | 任何错误都立即停止 | |

**User's choice:** 关键错误停止 (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| 版本不支持停止 | 版本不支持时停止解析 | |
| 尝试继续并警告 (推荐) | 版本不支持时尝试用最新已知版本逻辑继续，记录版本警告 | ✓ |
| 跳过版本字段 | 版本不支持时跳过版本相关字段 | |

**User's choice:** 尝试继续并警告 (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| logging 模块 | 使用 Python logging 模块记录错误 | ✓ |
| ParseError dataclass | 定义 ParseError dataclass 存储错误信息 | |
| 内置 Exception | 使用 Python 内置 Exception | |

**User's choice:** logging 模块

---

| Option | Description | Selected |
|--------|-------------|----------|
| 组合方案 (推荐) | logging 模块输出到 stderr，同时 ParseResult 包含 errors 列表 | ✓ |
| 只用 logging | 只用 logging 模块，不存储错误信息 | |
| 只用 dataclass | 只用 ParseError dataclass，不使用 logging | |

**User's choice:** 组合方案 (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| 四级日志 (推荐) | 定义 ERROR、WARN、INFO、DEBUG 四级 | ✓ |
| 两级日志 | 定义 ERROR、WARN 两级 | |
| 单级日志 | 只记录 ERROR 级别 | |

**User's choice:** 四级日志 (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| 自定义异常类 (推荐) | 定义自定义异常类：ParseError, VersionError, MagicError 等 | ✓ |
| 内置异常 | 使用 Python 内置 ValueError, IOError 等 | |
| 无异常模式 | 不抛出异常，只记录错误信息 | |

**User's choice:** 自定义异常类 (推荐)

---

| Option | Description | Selected |
|--------|-------------|----------|
| 丰富上下文 (推荐) | 异常包含文件路径、偏移位置、错误类型、上下文信息 | ✓ |
| 简洁消息 | 异常只包含错误消息 | |
| 链式异常 | 异常包含错误消息 + 原始异常 | |

**User's choice:** 丰富上下文 (推荐)

---

## Claude's Discretion

None — all key decisions were confirmed through discussion.

## Deferred Ideas

None — discussion stayed within phase scope.