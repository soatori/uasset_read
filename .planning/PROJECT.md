# uasset_read

## What This Is

Python工具读取 Unreal Engine .uasset 文件，让 AI agent 直接解析蓝图内容，无需 UE 编辑器介入。**v6.0** 已完成模块化重构，支持 UE 5.7，373 测试通过。

## Core Value

**让 AI agent 直接读取蓝图逻辑，无需 UE 编辑器介入。**

## 已完成里程碑

| 版本 | 范围 | 完成日期 |
|------|------|----------|
| v1-v5.1 | 核心功能构建 + 项目结构初始化 | 2026-05-02 ~ 2026-05-07 |
| v6.0 | **模块化重构**：单文件拆分为分层 Python 包 | 2026-05-13（进行中） |

**历史详情**: 见 [MILESTONES.md](MILESTONES.md) 归档。

## 活跃需求（v6.0 剩余）

- ⬜ **Phase 35b**: Pin 连接深度调试修复 `linked_to_raw` 空列表问题

## Out of Scope

| 功能 | 原因 |
|------|------|
| 导出纹理/模型二进制 | 专注蓝图元数据和图结构 |
| 修改/编辑 .uasset | 仅支持只读解析 |
| Cooked 资产解析 | 已剥离图数据，格式不同 |
| 蓝图字节码反编译 | 专注编辑器保存的资产 |
| 自动 C++ 代码生成 | 仅提供解析输出，生成延后 |
| MCP Server 封装 | 延后至 v7.x |
| JSON Schema 生成 | 延后至 v7.x |

## Background

- **格式**: `.uasset` 是 UE 资产格式，本项目专注**未烘焙蓝图资产**解析
- **源码参考**: `E:\Develop\lib\UnrealEngine` (UE 5.7 完整源码，只读)
- **目标用户**: AI agents (主) — 蓝图 → C++ 转换参考；开发者 (次) — 调试
- **技术栈**: Python 3.10+，**零运行时依赖**（仅标准库）
- **架构**: 分层管道模式镜像 UE FArchive：
  ```
  .uasset → FArchive → 序列化 → 数据模型 → 属性解析 → 蓝图图 → 格式化输出
  ```

## Key Decisions

| 决策 | 结果 |
|------|------|
| Python 实现 + 零依赖 | 易于 agent 调用，环境配置简单 | ✓ Good |
| 参考 UE 源码 | 格式未公开文档，保证正确性 | ✓ Good |
| 结构化 JSON 优先 | AI 直接理解，便于后续处理 | ✓ Good |
| FArchive 管道模式 | 镜像 UE 架构，易于扩展维护 | ✓ Good |
| v6.0 等价迁移 | 先重构不改变功能，避免范围蔓延 | ✓ Good |

## Constraints

- 语言：Python 3.10+（用户指定）
- 性能：大文件使用 mmap，响应及时
- 范围：仅支持未烘焙/编辑器保存的资产

## Current Milestone: v6.0 模块化重构

**目标:** 将单文件 `uasset_read.py` 重构为模块化 Python 包

**已完成阶段:**
- ✓ Phase 27: 项目结构初始化 (`constants.py`, `exceptions.py`)
- ✓ Phase 28: 核心序列化模块 (`archive.py`, `serializers/`)
- ✓ Phase 28a: 测试基线修复
- ✓ Phase 29: 核心数据模型 (`models/`)
- ✓ Phase 30: 属性解析模块 (`parsers/`)
- ✓ Phase 31: 蓝图图解析模块 (`graph/`)
- ✓ Phase 32: 输出格式化模块 (`formatters/`)
- ✓ Phase 33: 入口适配 + 删除旧 `uasset_read.py`
- ✓ Phase 33a: UE5 序列化问题修复
- ✓ Phase 34: 等价验证（373 passed, 71 skipped, 0 failed）
- ✓ Phase 35a: UAT 收尾快速修复

**当前焦点:**
- 🔴 **Phase 35b**: Pin 连接深度调试与修复 (`linked_to_raw` 根因修复)

**架构（v6.0 完成后）:**
```
src/uasset_read/
├── archive.py          # FArchive 二进制读取
├── constants.py        # 常量/阈值
├── exceptions.py       # 异常类
├── serializers/        # Package/Import/Export/PropertyTag
├── models/             # 数据类 (Graph/Node/Pin/Property)
├── parsers/            # 属性类型解析器
├── blueprint/          # 蓝图元数据提取
├── graph/              # 蓝图图解析、执行流构建
├── formatters/         # JSON/Text/Markdown 输出
└── cli.py              # CLI 入口
```

## Evolution

本文档在阶段转换和里程碑边界更新：
- 阶段转换后：更新需求状态、添加决策
- 里程碑完成后：全文评审，更新上下文

---

*最后更新：2026-05-13 — v6.0 主线完成，Phase 35b Pin 连接调试进行中*