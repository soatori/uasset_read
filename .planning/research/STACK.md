# 技术栈：Claude Code Skill封装

**项目:** uasset_read v3.0
**研究日期:** 2026-05-02
**聚焦:** Skill封装技术、文件格式、结构规范

---

## 推荐技术栈

### 核心格式

| 技术 | 版本 | 用途 | 选择理由 |
|------|------|------|----------|
| Markdown (.md) | 标准 | Skill主文件格式 | Claude Code原生支持，文本格式易编辑易版本控制 |
| YAML Frontmatter | 标准 | 元数据配置 | 官方推荐格式，支持name/description/triggers字段 |
| UTF-8 编码 | 标准 | 文件编码 | Claude Code默认编码，支持中英文 |

### Skill文件结构

| 组件 | 位置 | 说明 |
|------|------|------|
| SKILL.md | `.claude/skills/<skill-name>/SKILL.md` | Skill主入口文件 |
| knowledge/ | `.claude/skills/<skill-name>/knowledge/` | 知识库目录（可选） |
| references/ | `.claude/skills/<skill-name>/references/` | 参考文档目录（可选） |

### 集成方式

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| Python CLI调用 | Skill指令中调用 `python uasset_read.py` | 简单集成，无需额外代码 |
| JSON输出解析 | Skill解析CLI输出的JSON结构化数据 | 数据消费场景 |
| Bash工具 | Skill使用Bash工具执行Python脚本 | Claude Code原生工具 |

---

## Skill文件格式规范

### 格式一：YAML Frontmatter（官方推荐）

```markdown
---
name: uasset-read
description: Use when parsing Unreal Engine .uasset files, analyzing blueprint graphs, extracting asset metadata, or debugging UE serialization. Triggers for .uasset file analysis, blueprint parsing, ImportExport questions.
---

# UE .uasset 解析工具

## Purpose
[描述skill用途]

## Instructions
[Claude执行指令]

## Examples
[使用示例]
```

**Frontmatter字段：**

| 字段 | 必需 | 说明 |
|------|------|------|
| `name` | 是 | Skill唯一标识符，用于 `/skill-name` 调用 |
| `description` | 是 | 简短描述，用于skill选择和自动触发匹配 |
| `triggers` | 否 | 自动触发关键词列表（项目内未使用） |

### 格式二：表格式元数据（项目内现有格式）

```markdown
# skill-name

| 字段 | 值 |
|------|-----|
| Skill 名称 | skill-name |
| 版本 | vX.X |
| 分类 | 分类描述 |
| 触发词 | 关键词1、关键词2 |

---

## Skill 说明

### 能做什么
[能力列表]

### 不能做什么
[限制列表]
```

**推荐：** 采用格式一（YAML Frontmatter），符合官方规范，自动触发更可靠。

---

## 目录结构规范

### 标准结构

```
.claude/
├── skills/
│   └── uasset-read/
│       ├── SKILL.md              # 主入口
│       ├── knowledge/            # 知识库（可选）
│       │   ├── blueprint-parsing.md
│       │   ├── property-types.md
│       │   └── graph-structure.md
│       └── references/           # 参考文档（可选）
│           ├── cli-usage.md
│           └── output-format.md
```

### 项目内现有结构参考

| Skill | 结构 | 特点 |
|-------|------|------|
| lyra-course | `knowledge/ch1-ch10/` | 10章课程结构，每章多个md文件 |
| uasset-format | `references/` | 按主题分类的参考文档 |
| uecpp-course | `references/` | 模式文档索引 |

---

## 与Python工具集成

### 方案：Bash工具 + CLI调用

Skill通过Claude Code的Bash工具调用现有Python CLI：

```markdown
## Instructions

解析.uasset文件时，使用以下命令：

\`\`\`bash
python uasset_read.py <file.uasset> [--graph] [--json]
\`\`\`

输出解析：
- `--json` 输出结构化JSON，包含：
  - `name_map`: 名称表
  - `import_map`: 导入依赖
  - `export_map`: 导出对象
  - `blueprint`: 蓝图元数据
  - `graphs`: 蓝图图结构（使用--graph时）
```

### 调用示例

```markdown
## Examples

### 示例：解析蓝图文件

用户请求："分析 BP_FirstPersonCharacter.uasset 的蓝图图结构"

执行命令：
\`\`\`bash
python uasset_read.py BP_FirstPersonCharacter.uasset --graph --json
\`\`\`

解析输出JSON的 `graphs` 字段，提取：
- EventGraph节点链路
- 变量读写节点
- 函数调用关系
```

---

## uasset-read Skill草案

### SKILL.md内容框架

```markdown
---
name: uasset-read
description: Use when parsing Unreal Engine .uasset files, analyzing blueprint graphs, extracting asset metadata, understanding ImportExport structures, or debugging UE asset serialization. Triggers for .uasset analysis, blueprint parsing, asset dependencies.
---

# UE .uasset 文件解析器

## Purpose

让Claude直接解析Unreal Engine .uasset文件（尤其是蓝图），无需UE编辑器介入。支持：
- 文件头/名称表/导入表/导出表解析
- 蓝图元数据提取（父类、变量、组件）
- 蓝图图结构解析（Graph->Node->Pin）
- 依赖分析与循环检测

## Instructions

### 基础解析

使用CLI工具解析.uasset文件：

\`\`\`bash
# 基础解析（文件头+表+蓝图元数据）
python uasset_read.py <file.uasset> --json

# 包含蓝图图结构
python uasset_read.py <file.uasset> --graph --json
\`\`\`

### 输出结构

JSON输出包含以下顶层字段：
- `summary`: PackageFileSummary文件头
- `name_map`: 名称表（FName列表）
- `import_map`: 导入依赖（外部资产引用）
- `export_map`: 导出对象（本文件内对象）
- `blueprint`: 蓝图元数据（父类、变量、组件）
- `graphs`: 蓝图图结构（使用--graph时）
- `dependencies`: 依赖图（Phase 10）
- `circular_deps`: 循环依赖检测结果

### 使用限制

- 仅支持未烘焙/编辑器保存的资产（Cooked资产超出范围）
- 不支持蓝图字节码反编译
- 不修改.uasset文件（只读解析）

## Examples

### 解析蓝图执行流程

用户："分析 BP_FirstPersonCharacter 的BeginPlay事件链路"

\`\`\`bash
python uasset_read.py BP_FirstPersonCharacter.uasset --graph --json
\`\`\`

从 `graphs` 字段提取 EventGraph，查找 EventBeginPlay 节点，追踪 LinkedTo 连接链。

### 检测资产依赖

用户："BP_Weapon依赖哪些资产？"

\`\`\`bash
python uasset_read.py BP_Weapon.uasset --json
\`\`\`

读取 `import_map` 和 `dependencies` 字段，列出所有外部依赖。
```

---

## 安装/部署

### 无额外依赖

Skill封装无需安装任何额外包或工具：
- Skill文件：Markdown格式，直接创建
- Python工具：现有uasset_read.py，无需修改
- Claude Code：原生支持skills目录

### 创建步骤

```bash
# 1. 创建skill目录
mkdir -p .claude/skills/uasset-read

# 2. 创建SKILL.md
touch .claude/skills/uasset-read/SKILL.md

# 3. 编写skill内容（如上草案）

# 4. 可选：添加knowledge/references目录
mkdir -p .claude/skills/uasset-read/knowledge
```

---

## 来源与置信度

| 信息 | 来源 | 置信度 |
|------|------|--------|
| Skill格式规范 | 项目内现有skill文件（3个示例） | HIGH |
| YAML Frontmatter | WebSearch结果 + uasset-format示例 | HIGH |
| 目录结构 | `.claude/skills/` 现有结构 | HIGH |
| 集成方式 | uasset_read.py CLI接口 | HIGH |
| 自动触发机制 | WebSearch结果 | MEDIUM（项目内未使用triggers） |

**关键来源：**
- 项目内示例：`.claude/skills/lyra-course/SKILL.md`、`.claude/skills/uasset-format/SKILL.md`、`.claude/skills/uecpp-course/SKILL.md`
- WebSearch：Claude Code skill格式文档搜索结果

---

## 技术要点总结

1. **文件格式**：Markdown (.md)，UTF-8编码
2. **元数据**：YAML Frontmatter（推荐）或表格式
3. **位置**：`.claude/skills/<skill-name>/SKILL.md`
4. **集成**：Bash工具调用现有Python CLI
5. **知识库**：可选knowledge/references子目录
6. **无新依赖**：完全基于现有工具和Claude Code原生能力

---

## 项目内现有Skill示例分析

### lyra-course（表格式元数据）

```
结构：knowledge/ch1-ch10/ + references/
特点：
- 10章课程结构，每章多个md文件
- 表格式元数据（Skill名称、版本、分类、触发词）
- 包含"能做什么/不能做什么"说明
- 详细的类索引、设计模式、跨系统调用链路
```

### uasset-format（YAML Frontmatter）

```
结构：references/serialization/ + references/cooked/ + references/version/ + references/assets/
特点：
- YAML frontmatter（name, description）
- 核心原则强调（禁止猜测二进制格式）
- Quick Reference文档导航
- Common Mistakes / Red Flags警告
```

### uecpp-course（表格式元数据）

```
结构：references/
特点：
- 表格式元数据
- 课程全景（章节结构总览）
- 横向模式总结
- 使用示例索引表
```

---

## uasset-read Skill推荐结构

基于项目内现有skill模式和uasset_read.py功能，推荐以下结构：

```
.claude/skills/uasset-read/
├── SKILL.md                      # 主入口（YAML Frontmatter格式）
├── knowledge/                    # 知识库（可选，按需添加）
│   ├── blueprint-parsing.md      # 蓝图解析概念
│   ├── property-types.md         # 属性类型参考
│   └── graph-structure.md        # 图结构说明
└── references/                   # 参考文档（可选）
    ├── cli-usage.md              # CLI使用指南
    ├── output-format.md          # JSON输出格式说明
    └── ue-source-reference.md    # UE源码参考路径
```

**推荐先创建最小版本（仅SKILL.md），按需扩展knowledge和references。**