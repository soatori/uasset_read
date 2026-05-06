# uasset_read

## What This Is

Python工具用于读取Unreal Engine .uasset文件，让AI agent能直接解析资产内容（尤其是蓝图），无需人工介入UE编辑器。v3.x新增完整属性值提取、输出格式优化、Claude Code skill封装、UE 5.7兼容性修复。

## Core Value

**让AI agent直接读取蓝图逻辑，无需UE编辑器介入。**

v3.x验证：成功解析UE 5.7 BP_FirstPersonCharacter蓝图，359测试通过，skill封装完整。

## Requirements

### Validated

v1.0需求（Phase 1-5）：

- ✓ 能解析 .uasset 文件格式 — v1.0
- ✓ 提取名称表、导入表、导出表 — v1.0
- ✓ 解析基本属性类型 — v1.0
- ✓ 提取蓝图元数据（父类、变量） — v1.0
- ✓ 输出 JSON 和文本格式 — v1.0
- ✓ CLI 工具可用 — v1.0
- ✓ 安全边界验证 — v1.0

v2.0需求（Phase 6-10）：

- ✓ 修复导出表 OuterIndex/TemplateIndex 缺失 bug — v2.0
- ✓ 解析蓝图图结构（Graph → Node → Pin三层） — v2.0
- ✓ 输出蓝图执行流程（Event → CallFunction链路） — v2.0
- ✓ 解析六种高级属性类型 — v2.0
- ✓ 构建 ImportMap + SoftObjectPaths 依赖图 — v2.0
- ✓ 检测循环依赖 — v2.0
- ✓ JSON输出包含graphs顶层字段 — v2.0
- ✓ CLI --graph标志支持 — v2.0

v3.x需求（Phase 11-17）：

- ✓ ExportMap属性值提取 — v3.x (Phase 11)
- ✓ BlueprintVariables完整提取 — v3.x (Phase 12)
- ✓ 组件变换属性解析 — v3.x (Phase 13)
- ✓ 输出格式优化（status字段、Markdown、摘要） — v3.x (Phase 14)
- ✓ Claude Code skill封装 — v3.x (Phase 15)
- ✓ Bool序列化修复 — v3.x (Phase 16)
- ✓ 属性解析修复（偏移、Extensions、阈值） — v3.x (Phase 17)

### Active

v4.0需求（Phase 18-21）：

- ⬜ 修复属性Size阈值检测 — v4.0 (Phase 18)
- ⬜ 解析FunctionReference/EventReference/InputAction — v4.0 (Phase 18)
- ⬜ 解析Pin数组与LinkedTo连接 — v4.0 (Phase 18-19)
- ⬜ 解析NodeGuid/节点位置 — v4.0 (Phase 20)
- ⬜ 构建执行流程图和数据流图 — v4.0 (Phase 19)
- ⬜ 连接验证测试 — v4.0 (Phase 21)

### Out of Scope

| 功能 | 原因 |
|------|------|
| 导出资源文件（纹理、模型等二进制数据） | 专注于蓝图元数据和图结构 |
| 修改/编辑 .uasset 文件 | 仅支持只读解析 |
| 实时解析/监控 | 批量解析场景，无需实时功能 |
| Cooked资产解析 | Cooked资产已剥离图数据；使用不同序列化格式 |
| 蓝图字节码反编译 | 编译蓝图使用字节码格式；专注于编辑器保存的资产 |
| 节点可视化 | 复杂UI工作；AI agent无需视觉预览 |
| 自动C++代码生成 | 仅提供参考级别JSON，不实现自动转换 |
| 自定义节点类型处理器 | 游戏特定自定义节点需要游戏特定知识 |
| MCP Server封装 | 延后至v4.x（SKILL-05/SKILL-06） |
| JSON Schema生成 | 延后至v4.x（OUT-07/OUT-08） |

## Background

### 技术背景

- .uasset是Unreal Engine的资产文件格式
- 包含多种类型：蓝图、材质、纹理、模型、动画等
- 当前项目主要关注蓝图相关的.uasset（未烘焙/编辑器保存的资产）
- v3.x支持UE 5.7资产完整解析

### 源码参考

- 项目内有部分UE源码：`UnrealEngine/`目录（只读参考）
- UE 5.7完整源码：`E:\Develop\lib\UnrealEngine`（只读参考）
- 关键模块：CoreUObject（序列化）、BlueprintRuntime（蓝图）

### 目标用户

- AI agents（主要） — 直接解析蓝图逻辑，生成C++转换参考
- 开发者（次要） — 调试资产内容、理解蓝图结构

## Context

**Shipped:**
- v1.0 MVP（2026-05-02）：核心解析、基本属性、蓝图元数据
- v2.0 蓝图图解析（2026-05-02）：完整蓝图图、高级属性、依赖分析
- v3.x 解析完善+Skill+兼容性（2026-05-04）：属性值提取、输出优化、skill封装、UE 5.7兼容
- v4.0 节点属性深度解析（2026-05-05）：节点属性、执行流、连接验证
- v5.0 原功能完善（2026-05-06）：蓝图编译研究、元数据增强（部分完成）

**Tech Stack:**
- Python 3.10+（match/case，类型提示）
- 零运行时依赖（仅标准库）
- 主文件：uasset_read.py（5,100+ lines）
- 测试：tests/（359 tests passed）

**Architecture:**
分层管道模式（镜像UE FArchive）：
```
.uasset → FArchive → Deserializer → Models → OutputFormatter
                ↓ v3.x扩展组件
          PropertyParser (Phase 11)
          OutputFormatter v3.0 (Phase 14)
          Skill封装 (Phase 15)
          BoolFix (Phase 16)
          PropertyParsingFix (Phase 17)
```

**Known Issues / Tech Debt:**
- MCP Server封装延后（SKILL-05/SKILL-06）
- JSON Schema生成延后（OUT-07/OUT-08）
- EventGraph测试跳过（Cooked资产情况）

## Key Decisions

| 决策 | 理由 | 结果 |
|------|------|------|
| Python实现 | 易于agent调用，快速原型开发 | ✓ Good |
| 参考UE源码 | .uasset格式未公开文档 | ✓ Good |
| 结构化JSON优先 | agent直接理解 | ✓ Good |
| 零运行时依赖 | 减少环境配置复杂度 | ✓ Good |
| FArchive管道模式 | 镜像UE架构，易于扩展 | ✓ Good |
| Bool: read_u32()!=0 | UE源码正确值 | ✓ Good |
| 偏移: serial+script_serial_offset | ObjectResource.h注释明确 | ✓ Good |
| 阈值: PROPERTY_TAG_COMPLETE_TYPE_NAME=1012 | UE5格式切换点 | ✓ Good |
| Status三元分类 | JSend规范，AI友好 | ✓ Good |
| output_version: "3.0" | API版本锁定 | ✓ Good |

## Constraints

- **语言**: Python 3.10+ — 用户指定
- **性能**: 不能卡死，需响应及时（大文件使用mmap）
- **进度管理**: Git版本控制 + GSD workflow
- **源码依赖**: 需要参考UE源码理解格式（只读）
- **范围边界**: 仅支持未烘焙/编辑器保存的资产

## Current Milestone: v5.1 模块化重构与C++代码生成准备

**目标:** 以最小化改动实现模块化架构，为蓝图转C++自动化做好准备

**目标功能:**
- 最小化模块化拆分（保持核心结构清晰）
- C++代码生成准备的JSON输出结构
- 完成Phase 23-24的技术债务

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

*最后更新：2026-05-06 — 开始v5.1里程碑*