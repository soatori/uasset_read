# Phase 15: Claude Code skill封装 - Research

**Researched:** 2026-05-03
**Domain:** Claude Code skill封装、知识库组织、触发词设计
**Confidence:** HIGH

## Summary

Phase 15 将 uasset_read 工具封装成 Claude Code skill，让 AI 能通过触发词直接调用解析功能，并提供知识库帮助正确解读输出。这是 v3.0 的最后一个阶段，完成后 API 稳定、skill 可用、后续可直接集成到 AI 工作流。

**Primary recommendation:** 参考 lyra-course skill 的成熟结构，创建 SKILL.md + knowledge/ + examples/ 三层组织，知识文件采用教程风格（800-1500行），触发词覆盖多种用户表述习惯。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-15-01:** 组合触发词模式 — `uasset`、`.uasset`、`蓝图解析`、`蓝图图`、`parse_uasset`、`uasset_read`
- **D-15-02:** 项目本地安装 — `.claude/skills/uasset-read/`
- **D-15-03:** 详细教程风格 — 每文件800-1500行，含代码示例、架构说明、概念解释
- **D-15-04:** 使用FirstPerson模板资产 — `E:\Develop\lib\UnrealEngine\Samples\FirstPerson`
- **D-15-05:** 四个示例文件 — basic-usage.md、blueprint-analysis.md、cpp-conversion.md、troubleshooting.md

### Claude's Discretion

- SKILL.md具体结构（是否包含"项目全景"类表格）
- 知识文件命名和分组方式
- 示例文件中的具体代码示例选择
- 知识库是否复用现有CLAUDE.md内容

### Deferred Ideas (OUT OF SCOPE)

- MCP Server封装（SKILL-05, SKILL-06）— 延后到v2需求
- 多资产批量解析 — 超出v3.0范围
- TypeScript类型定义生成 — 次要功能

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SKILL-01 | 创建SKILL.md主文件（YAML Frontmatter格式，触发词、能力范围） | lyra-course SKILL.md 作为参考模板，触发词已锁定为 D-15-01 |
| SKILL-02 | 编写5-6个知识文件：blueprint-semantics、node-types、pin-type-mapping、cpp-conversion、common-patterns、troubleshooting | 知识文件风格已锁定（D-15-03），可复用现有解析代码注释 |
| SKILL-03 | 编写3-4个示例文件：basic-usage、blueprint-analysis、cpp-conversion | 示例文件已锁定（D-15-05），使用 BP_FirstPersonCharacter 作为演示资产（D-15-04） |
| SKILL-04 | skill集成测试 — 验证skill触发、调用parse_uasset() API、输出解读正确 | 测试框架 pytest 已存在，测试目录 tests/ 有16个测试文件 |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Skill触发词匹配 | Claude Code CLI | — | Claude Code 核心 skill 系统负责触发词检测和加载 |
| parse_uasset() 调用 | Python Runtime | — | skill 通过 Python API 调用解析函数 |
| JSON输出解读 | Claude LLM | — | AI 需要理解 output_version: "3.0" 格式的语义 |
| 知识库内容 | Skill Files | — | knowledge/ 目录提供蓝图概念、节点类型等解释 |
| 示例展示 | Skill Files | — | examples/ 目录提供具体使用场景 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Claude Code skill system | Native | skill加载和触发 | Claude Code 内置skill机制，无需额外安装 [VERIFIED: lyra-course存在] |
| parse_uasset() | uasset_read.py | 主解析函数 | Phase 1-14 实现的核心API [VERIFIED: uasset_read.py:4472] |
| output_version: "3.0" | Frozen API | 稳定输出格式 | Phase 14 冻结，skill可依赖稳定字段 [VERIFIED: VERIFICATION.md] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 316 passed | skill测试验证 | 验证skill触发后API调用正确 |
| format_json_full() | Phase 14 | 完整JSON输出 | 详细分析场景 |
| format_json_summary() | Phase 14 | 精简JSON输出 | 快速查看场景 |
| format_markdown() | Phase 14 | Markdown输出 | 人类友好输出 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 项目本地skill | 全局安装skill | 项目本地随Git分发更方便，无需用户手动安装 |
| 教程风格知识文件 | 简要参考格式 | AI可能不熟悉UE蓝图，需要完整解释 |

**Installation:**
无需安装 — skill随项目Git分发，Claude Code自动检测 `.claude/skills/` 目录。

## Architecture Patterns

### Skill Directory Structure Pattern

**What:** Claude Code skill采用三层目录结构：SKILL.md + knowledge/ + examples/
**When to use:** 所有Claude Code skill封装项目

**Verified pattern from lyra-course:**
```
.claude/skills/{skill-name}/
├── SKILL.md                  # 主入口：触发词、能力说明、索引
├── knowledge/                # 知识库：详细教程文件
│   ├── ch{N}/               # 按章节组织（可选）
│   │   └── *.md             # 具体知识文件
│   └── *.md                 # 或扁平组织
└── examples/                 # 示例（可选）
    └── *.md                  # 使用示例
```

**uasset-read skill 目录结构（推荐）:**
```
.claude/skills/uasset-read/
├── SKILL.md                  # 主入口（触发词、能力范围）
├── knowledge/
│   ├── blueprint-semantics.md    # 蓝图语义（EventGraph、变量、组件）
│   ├── node-types.md             # K2Node类型参考
│   ├── pin-type-mapping.md       # Pin类型→JSON类型映射
│   ├── cpp-conversion.md         # 蓝图→C++转换参考
│   ├── common-patterns.md        # 常见蓝图模式
│   └── troubleshooting.md        # 故障排除
└── examples/
    ├── basic-usage.md            # CLI和Python API基础调用
    ├── blueprint-analysis.md     # EventGraph分析流程
    ├── cpp-conversion.md         # 蓝图→C++转换示例
    └── troubleshooting.md        # 错误处理场景
```

### SKILL.md Frontmatter Pattern

**What:** SKILL.md开头使用表格格式定义skill元数据
**When to use:** 所有SKILL.md文件

**Verified pattern from lyra-course SKILL.md:**
```markdown
# lyra-course

| 字段 | 值 |
|------|-----|
| Skill 名称 | lyra-course |
| 版本 | UE 5.6 |
| 分类 | Unreal Engine 项目架构分析 |
| 触发词 | Lyra、LyraGame、Lyra 架构 |

---

## Skill 说明

### 能做什么
- [列出具体能力]

### 不能做什么
- [列出限制]

---

## 项目全景
[可选：项目概述、目录结构]
```

**uasset-read SKILL.md frontmatter（推荐）:**
```markdown
# uasset-read

| 字段 | 值 |
|------|-----|
| Skill 名称 | uasset-read |
| 版本 | v3.0 |
| 分类 | Unreal Engine 资产解析 |
| 触发词 | uasset、.uasset、蓝图解析、蓝图图、parse_uasset |

---

## Skill 说明

### 能做什么
- 解析 UE .uasset 蓝图文件，提取变量、组件、EventGraph 节点
- 输出 JSON/Markdown 格式的蓝图结构和执行流程
- 提供蓝图→C++转换参考（函数名、参数类型）

### 不能做什么
- 不解析 Cooked 资产（已剥离蓝图数据）
- 不生成完整 C++ 代码（仅提供参考级别信息）
- 不反编译蓝图字节码
```

### Knowledge File Pattern

**What:** 知识文件采用教程风格，包含UE背景、JSON结构映射、代码片段
**When to use:** 当AI可能不熟悉领域概念时

**Verified pattern from lyra-course knowledge/ch7/01-GAS架构概述.md:**
- 开头引用对应讲义
- 每节包含类名、文件路径链接
- 核心数据结构用表格展示
- 代码片段带注释
- 类方法用列表说明

**知识文件风格要点（D-15-03锁定）:**
- 每文件800-1500行
- 包含UE概念背景解释
- JSON字段→UE概念映射
- 典型代码片段（带注释）
- troubleshooting文件包含常见错误和解决方案

### Anti-Patterns to Avoid

- **触发词过于具体:** 只用 `parse_uasset` 会错过用户说 "帮我看看这个蓝图" 的意图 — 使用组合触发词覆盖多种表述
- **知识文件过于精简:** AI不熟悉UE蓝图概念，简要参考格式会导致误解 — 采用教程风格
- **示例资产不存在:** 使用项目私有资产会导致示例无法复现 — 使用FirstPerson模板资产（UE安装自带）
- **忽略API版本:** 知识文件描述过时JSON格式 — 必须锁定 output_version: "3.0"

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Skill目录结构 | 自定义结构 | lyra-course参考模式 | 已验证可用，Claude Code自动检测 |
| SKILL.md格式 | 自定义格式 | 表格frontmatter | 与现有skill风格一致 |
| 知识内容 | 从零编写 | 复用CLAUDE.md + 代码注释 | 项目已有详细文档和注释 |
| 输出格式描述 | 自定义描述 | Phase 14 VERIFICATION.md | API已冻结，字段含义已验证 |

**Key insight:** lyra-course skill 已有90+知识文件，结构成熟可复用。本项目知识库可借鉴其组织方式，内容复用现有文档。

## Common Pitfalls

### Pitfall 1: 触发词覆盖不足

**What goes wrong:** 用户说"解析蓝图"但skill未触发
**Why it happens:** 触发词仅包含技术术语，缺少自然语言表述
**How to avoid:** 组合触发词覆盖多种习惯（D-15-01已锁定6个触发词）
**Warning signs:** skill激活率低，用户需要手动调用

### Pitfall 2: 知识文件与API不匹配

**What goes wrong:** 知识文件描述JSON字段与实际输出不符
**Why it happens:** 知识文件基于旧版本API编写，Phase 14冻结后未更新
**How to avoid:** 所有知识文件锁定 output_version: "3.0"，引用VERIFICATION.md字段描述
**Warning signs:** AI解读输出时字段名错误

### Pitfall 3: 示例资产路径错误

**What goes wrong:** 示例使用 `./test/MyBlueprint.uasset` 但用户环境不存在
**Why it happens:** 使用项目私有资产而非公共模板资产
**How to avoid:** 使用FirstPerson模板资产（D-15-04已锁定）
**Warning signs:** 用户无法复现示例

### Pitfall 4: 知识文件过度精简

**What goes wrong:** AI误解蓝图概念，如将"K2Node_CallFunction"当作普通函数调用
**Why it happens:** 知识文件仅列出术语，缺少UE背景解释
**How to avoid:** 教程风格，包含UE概念背景（D-15-03已锁定）
**Warning signs:** AI回答中出现概念错误

## Code Examples

### parse_uasset() API调用示例

```python
# Source: uasset_read.py:4472-4493 (parse_uasset签名)
from uasset_read import parse_uasset, format_json_full, format_json_summary

# 基础调用
result = parse_uasset("BP_FirstPersonCharacter.uasset")

# 检查解析状态
if result.is_success:
    print(f"解析成功: {result.summary.package_name}")
else:
    for error in result.errors:
        print(f"错误: {error}")

# 完整JSON输出
full_output = format_json_full(result)
# 包含: status, output_version, summary, exports, graphs, graphs_summary

# 精简JSON输出（70%+ token减少）
summary_output = format_json_summary(result)
# 仅包含: status, output_version, version, package_name, exports_summary, graphs_summary
```

### 输出JSON结构示例 (output_version: "3.0")

```json
// Source: Phase 14 VERIFICATION.md (API冻结验证)
{
  "status": {
    "status": "success",      // success/fail/error (JSend style)
    "message": "",
    "code": null
  },
  "output_version": "3.0",    // API版本标识
  "summary": {
    "tag": 2620143297,
    "package_name": "/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter"
  },
  "exports": [
    {
      "name": "BP_FirstPersonCharacter_C",
      "class": "BlueprintGeneratedClass",
      "parent_class": "FirstPersonCharacter",
      "properties": [...]
    }
  ],
  "graphs_summary": [
    {
      "graph_name": "EventGraph",
      "execution_flows": [
        {
          "function_name": "ReceiveBeginPlay",
          "params": []
        }
      ]
    }
  ]
}
```

### SKILL.md结构模板

```markdown
# uasset-read

| 字段 | 值 |
|------|-----|
| Skill 名称 | uasset-read |
| 版本 | v3.0 |
| 分类 | Unreal Engine 资产解析 |
| 触发词 | uasset、.uasset、蓝图解析、蓝图图、parse_uasset |

---

## Skill 说明

### 能做什么

- 解析 UE .uasset 蓝图文件，提取：
  - 蓝图变量（名称、类型、默认值）
  - 组件列表（SkeletalMesh、Camera等）
  - EventGraph 执行流程（函数调用链）
- 输出格式：JSON / Markdown / 精简摘要
- 提供蓝图→C++转换参考（函数名、参数类型）

### 不能做什么

- **不解析 Cooked 资产** — Cooked资产已剥离蓝图数据
- **不生成完整C++代码** — 仅提供参考级别信息
- **不反编译蓝图字节码** — 专注于编辑器保存的资产
- **不解析 Verse 脚本** — 仅关注蓝图层

---

## 快速开始

```python
from uasset_read import parse_uasset

result = parse_uasset("path/to/BP_MyBlueprint.uasset")
if result.is_success:
    for graph in result.graphs:
        print(f"图: {graph.graph_name}")
```

---

## 输出格式

output_version: "3.0" (Phase 14冻结)

| 字段 | 含义 |
|------|------|
| status.status | 解析状态：success/fail/error |
| graphs_summary | 执行流程概览（顶层） |
| exports | 导出对象列表 |

---

## 知识库索引

| 文件 | 内容 |
|------|------|
| [blueprint-semantics.md](knowledge/blueprint-semantics.md) | 蓝图概念：EventGraph、变量、组件 |
| [node-types.md](knowledge/node-types.md) | K2Node类型参考 |
| [pin-type-mapping.md](knowledge/pin-type-mapping.md) | Pin类型→JSON映射 |
| [cpp-conversion.md](knowledge/cpp-conversion.md) | 蓝图→C++转换参考 |
| [common-patterns.md](knowledge/common-patterns.md) | 常见蓝图模式 |
| [troubleshooting.md](knowledge/troubleshooting.md) | 故障排除 |

---

## 示例索引

| 文件 | 场景 |
|------|------|
| [basic-usage.md](examples/basic-usage.md) | CLI和Python API调用 |
| [blueprint-analysis.md](examples/blueprint-analysis.md) | EventGraph分析流程 |
| [cpp-conversion.md](examples/cpp-conversion.md) | 蓝图→C++转换 |
| [troubleshooting.md](examples/troubleshooting.md) | 错误处理 |
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 手动调用parse_uasset() | skill触发词自动激活 | Phase 15 | AI无需记住API名称 |
| 无知识库 | 6个知识文件提供UE概念解释 | Phase 15 | AI正确解读蓝图语义 |
| 无示例 | 4个示例覆盖典型场景 | Phase 15 | 用户可快速上手 |

**Deprecated/outdated:**
- Phase 14之前的输出格式：skill必须锁定 output_version: "3.0"

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Claude Code自动检测 `.claude/skills/` 目录 | Standard Stack | 需验证skill加载机制 |
| A2 | lyra-course触发词格式适用于uasset-read | Architecture Patterns | 可能需要调整表格字段 |

**验证建议:** A1可通过创建测试skill验证；A2已有lyra-course成功案例，风险低。

## Open Questions

1. **知识文件是否需要按章节分组？**
   - What we know: lyra-course使用ch1-ch10章节分组
   - What's unclear: uasset-read知识量较小（6文件），是否需要章节分组
   - Recommendation: 扁平组织即可（6文件直接放knowledge/目录）

2. **SKILL.md是否需要"项目全景"章节？**
   - What we know: lyra-course包含完整目录结构和模块依赖图
   - What's unclear: uasset-read是单文件工具，全景可能过于简单
   - Recommendation: 包含简化版"快速开始"和"输出格式"章节

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Claude Code CLI | skill加载 | ✓ | — | — |
| Python 3.10+ | parse_uasset() | ✓ | — | — |
| pytest | skill测试 | ✓ | — | — |
| FirstPerson资产 | 示例演示 | ✓ | UE Samples | — |

**Missing dependencies with no fallback:** None

**Missing dependencies with fallback:** None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | tests/ 目录，无pytest.ini |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SKILL-01 | SKILL.md创建和格式验证 | manual | — | ❌ Wave 0 |
| SKILL-02 | 知识文件内容验证 | manual | — | ❌ Wave 0 |
| SKILL-03 | 示例文件可执行验证 | integration | `python -c "from uasset_read import parse_uasset; parse_uasset('...')"` | ❌ Wave 0 |
| SKILL-04 | skill触发测试 | manual | Claude Code交互测试 | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** 无自动测试（skill文件为文档）
- **Per wave merge:** 手动验证skill结构
- **Phase gate:** skill完整且可触发

### Wave 0 Gaps
- [ ] `.claude/skills/uasset-read/SKILL.md` — SKILL-01
- [ ] `.claude/skills/uasset-read/knowledge/*.md` — SKILL-02（6文件）
- [ ] `.claude/skills/uasset-read/examples/*.md` — SKILL-03（4文件）
- [ ] skill触发验证方法 — SKILL-04

*(注：skill封装主要为文档创建，测试依赖手动验证Claude Code交互)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | skill无需认证 |
| V3 Session Management | no | skill无会话 |
| V4 Access Control | no | skill无权限控制 |
| V5 Input Validation | yes | 文件路径验证（parse_uasset内置） |
| V6 Cryptography | no | skill无加密需求 |

### Known Threat Patterns for Skill封装

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 无（skill为静态文档） | — | — |

**注：** skill封装是文档创建阶段，不涉及运行时安全。parse_uasset()已有边界验证（WR-01）。

## Sources

### Primary (HIGH confidence)
- `.claude/skills/lyra-course/SKILL.md` — skill结构和frontmatter格式 [VERIFIED]
- `.claude/skills/lyra-course/knowledge/ch7/01-GAS架构概述.md` — 知识文件风格 [VERIFIED]
- `uasset_read.py:4472-4493` — parse_uasset() API签名 [VERIFIED]
- `.planning/phases/14-output-format-optimization/14-VERIFICATION.md` — API冻结验证 [VERIFIED]

### Secondary (MEDIUM confidence)
- `.planning/phases/15-claude-code-skill-packaging/15-CONTEXT.md` — 锁定决策 [CITED]
- `.planning/REQUIREMENTS.md` — SKILL-01~04需求定义 [CITED]
- `CLAUDE.md` — 项目概述和技术栈 [CITED]

### Tertiary (LOW confidence)
- Claude Code skill系统加载机制 — [ASSUMED: A1]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — lyra-course存在验证，API冻结验证完成
- Architecture patterns: HIGH — lyra-course提供完整参考模板
- Pitfalls: HIGH — 基于CONTEXT.md锁定决策分析

**Research date:** 2026-05-03
**Valid until:** 30 days（skill封装模式稳定）