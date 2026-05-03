# uasset_read

## What This Is

Python工具用于读取Unreal Engine .uasset文件，让AI agent能直接解析资产内容（尤其是蓝图），无需人工介入UE编辑器。v2.0新增完整蓝图图解析（Graph→Node→Pin）、高级属性类型支持、依赖分析功能，输出可作为C++转换参考的详细JSON。

## Core Value

**让AI agent直接读取蓝图逻辑，无需UE编辑器介入。**

v2.0验证：成功解析BP_FirstPersonCharacter蓝图，输出95%转换质量的C++代码框架参考。

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
- ✓ JSON输出包含graphs顶层字段（与blueprint同级） — v2.0
- ✓ CLI --graph标志支持 — v2.0

### Active

v3.0需求（Phase 11-15）：

- [ ] ExportMap属性值提取（组件属性、变量默认值）
- [ ] BlueprintVariables完整提取（名称、类型、默认值、元数据）
- [ ] 组件变换属性解析（位置、旋转、缩放）
- [ ] 输出格式优化（更易AI理解）
- [ ] 测试覆盖完善
- [ ] Claude Code skill封装

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

## Background

### 技术背景

- .uasset是Unreal Engine的资产文件格式
- 包含多种类型：蓝图、材质、纹理、模型、动画等
- 当前项目主要关注蓝图相关的.uasset（未烘焙/编辑器保存的资产）
- v2.0支持蓝图图完整解析（UEdGraph/UEdGraphNode/UEdGraphPin）

### 源码参考

- 项目内有部分UE源码：`UnrealEngine/`目录（只读参考）
- UE 5.7完整源码：`E:\Develop\lib\UnrealEngine`（只读参考）
- 关键模块：CoreUObject（序列化）、BlueprintRuntime（蓝图）
- 关键源码文件：
  - `PackageFileSummary.h` — 文件头部结构
  - `ObjectResource.h` — 导入/导出结构
  - `Archive.h` — FArchive模式
  - `EdGraph.h` — 蓝图图结构

### 目标用户

- AI agents（主要） — 直接解析蓝图逻辑，生成C++转换参考
- 开发者（次要） — 调试资产内容、理解蓝图结构

## Context

**Shipped:**
- v1.0 MVP（2026-05-02）：核心解析、基本属性、蓝图元数据
- v2.0 蓝图图解析（2026-05-02）：完整蓝图图、高级属性、依赖分析

**Tech Stack:**
- Python 3.10+（match/case，类型提示）
- 零运行时依赖（仅标准库）
- 主文件：uasset_read.py（4,901 lines）
- 测试：tests/（5,141 lines，62+ tests）

**Architecture:**
分层管道模式（镜像UE FArchive）：
```
.uasset → FArchive → Deserializer → Models → OutputFormatter
                ↓ v2.0扩展组件
          GraphParser (Phase 7)
          AdvancedPropParser (Phase 9)
          DependencyGraphBuilder (Phase 10)
```

**Key Patterns:**
- type_dispatch模式（属性类型路由）
- dataclass + asdict() → JSON输出
- mmap大文件处理
- 递归深度限制（安全边界）

**Known Issues / Tech Debt:**
- 某些节点类型特定数据可能不完整（需更多测试资产验证）
- 递归深度限制硬编码为5（可能需根据资产复杂度调整）
- OUT2-02（高级属性替换原始值）待实现

## Key Decisions

| 决策 | 理由 | 结果 |
|------|------|------|
| Python实现 | 易于agent调用，快速原型开发 | ✓ Good |
| 参考UE源码 | .uasset格式未公开文档，需从源码推断 | ✓ Good |
| 结构化JSON优先 | agent直接理解，无需二次转换 | ✓ Good |
| 零运行时依赖 | 减少环境配置复杂度 | ✓ Good |
| FArchive管道模式 | 镜像UE架构，易于理解和扩展 | ✓ Good |
| Phase 6 D-01: 统一版本检查 | UE5文件自动满足UE4版本条件 | ✓ Good |
| Phase 6 D-05: 严格按UE源码顺序序列化 | 避免偏移错位 | ✓ Good |
| Phase 7 D-01: LinkedTo原始数据存储 | Phase 8构建映射，降低Wave 1复杂度 | ✓ Good |
| Phase 7 D-04: 顶层graphs字段 | 与blueprint同级，清晰JSON结构 | ✓ Good |
| Phase 8 D-08-05: 连接映射单向表示 | 仅从Output出发，避免重复连接 | ✓ Good |
| Phase 9 D-08: parse_property_value参数扩展 | summary和depth用于版本检查和递归限制 | ✓ Good |
| Phase 10: ImportMap + SoftObjectPaths依赖图 | 完整依赖分析，支持循环检测 | ✓ Good |

## Constraints

- **语言**: Python 3.10+ — 用户指定
- **性能**: 不能卡死，需响应及时（大文件使用mmap）
- **进度管理**: Git版本控制 + GSD workflow
- **源码依赖**: 需要参考UE源码理解格式（只读）
- **范围边界**: 仅支持未烘焙/编辑器保存的资产（Cooked资产超出范围）

---

*最后更新：2026-05-02 after v2.0 milestone*

## Current Milestone: v3.0 解析完善 + Skill打包

**Goal:** 补齐缺失数值解析，输出可用结果，打包成Claude Code skill

**Target features:**
- ExportMap属性值提取
- 变量默认值提取
- 组件变换属性解析
- 输出格式优化
- 测试覆盖完善
- Claude Code skill封装

---

*最后更新：2026-05-03 启动v3.0里程碑*

## 演进

本文档在阶段过渡和里程碑边界时演进。

**每次阶段过渡后**（通过 `/gsd-transition`）：
1. 需求失效？ → 移至超出范围并注明原因
2. 需求验证？ → 移至已验证并引用阶段
3. 新需求出现？ → 添加至活跃需求
4. 需求记录决策？ → 添加至关键决策
5. "项目简介"仍准确？ → 如有偏离则更新

**每个里程碑后**（通过 `/gsd-complete-milestone`）：
1. 全面审查所有章节
2. 核心价值检查 —— 仍是正确优先级？
3. 审计超出范围 —— 原因仍有效？
4. 用当前状态更新背景