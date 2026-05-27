# GSD → Superpowers 迁移设计

## 目标

将项目从 GSD phase-based 规划体系迁移到 Superpowers specs + plans 工作流，删除所有 GSD 专用文件，保留有价值的历史研究和里程碑记录。

## 架构

在当前 `dev-0.3.0` 分支上，新建 `docs/superpowers/` 目录结构，将 Phase 76-80 的规划内容提取为 Superpowers spec 文档，然后删除所有 GSD 专用文件（`.planning/phases/`、`.planning/ROADMAP.md`、`.planning/STATE.md` 等），最后更新 CLAUDE.md 和 DEVELOPMENT.md 中的引用。

## 迁移范围

### 新建结构

```
docs/superpowers/
├── specs/          # 设计文档（从 Phase research + plans 提取）
│   ├── 2026-05-27-farchive-cor-fixes-design.md
│   ├── 2026-05-27-uobject-inheritance-linker-design.md
│   ├── 2026-05-27-iostore-utoc-ucas-design.md
│   └── 2026-05-27-pascalcase-output-format-design.md
└── plans/          # 实施计划（由 writing-plans 技能后续生成）
```

### 保留文件

| 路径 | 原因 |
|------|------|
| `.planning/MILESTONES.md` | 版本历史索引 |
| `.planning/archive/` | 已完成里程碑（v1.0-v13.0） |
| `.planning/milestones/` | 各版本测试报告 |

### 删除文件

| 路径 | 原因 |
|------|------|
| `.planning/phases/` (整个目录) | GSD phase 文件 — 内容已提取到 specs |
| `.planning/research/` (整个目录) | GSD 研究文件 — 内容已提取到 specs |
| `.planning/ROADMAP.md` | GSD 路线图 — 信息合并到 CLAUDE.md |
| `.planning/STATE.md` | GSD 状态追踪 — 信息合并到 CLAUDE.md |
| `.planning/REQUIREMENTS.md` | GSD 需求文档 — 内容提取到 specs |
| `.planning/PROJECT.md` | GSD 项目定义 — 信息合并到 CLAUDE.md |
| `.planning/config.json` | GSD 配置 |

### 更新文档

| 文件 | 变更 |
|------|------|
| `CLAUDE.md` | 删除 "gsd-sdk 使用" 章节，更新 "规划文档" 路径为 `docs/superpowers/specs/`，更新 "上下文与效率" 中的 GSD 引用为 Superpowers |
| `docs/DEVELOPMENT.md` | 删除 "GSD Workflow" 章节（第 6 节） |
| `docs/CONTRIBUTING.md` | 删除 "GSD Workflow Stages" 引用（第 11 节） |

## Spec 内容摘要

### Spec 1: FArchive COR Fixes

**来源:** `phases/phase-76/76-01-PLAN.md` + `76-RESEARCH.md`

**核心内容:**
- VersionContainer 从结果对象升级为序列化决策基础设施
- 4 个关键路径的版本判断收敛：`property_parser.py` (3处)、`graph.py` (2处)、`bytecode_extractor.py` (2处)、`bpgc_bytecode.py` (2处)
- 推荐方案：给 `PackageFileSummary` 添加可选 `version_container` 字段
- StructProperty fast-path 增加 `tag.size` 校验，不匹配时回退到 PropertyTag loop
- BodyInstance 不添加 fast-path，统一走 PropertyTag loop
- 修复 Phase 75 回归测试红灯

**关键文件:** `versioning.py`, `parsers/property_parser.py`, `serializers/graph.py`, `parsers/property_types.py`

### Spec 2: UObject Inheritance + Linker Refactor

**来源:** `phases/phase-78/INDEX.md` + `78-01-PLAN.md` + `78-02-PLAN.md` + `78-03-PLAN.md`

**核心内容:**
- 新建 `models/uobject.py`：UObject → UField → UEnum/UStruct/UClass/UFunction 反射层次
- 导出类标签分类：Graph/GraphNode/Component/Actor/BlueprintClass
- PackageLinker 增加 `build_super_tree()`, `resolve_class_ref()`, `resolve_template_ref()`
- UObjectInstance 新增 `super` 字段和 `get_super_field_chain()`
- 独立 Archive 实例 + 生命周期由 LinkerParseResult 管理
- preload() 使用 save/restore 模式，不污染 archive 位置
- 连续 parse_uasset 无缓存串扰
- Provider 接口边界 + graph linker-aware 单一路径
- `/Script/` import 占位符策略

**关键文件:** `models/uobject.py`(新建), `link/linker.py`, `link/object_instance.py`, `link/result.py`, `parse_uasset.py`

### Spec 3: IoStore .utoc/.ucas Parser

**来源:** `ROADMAP.md` 中的 Phase 79 描述

**核心内容:**
- FIoStoreTocResource 解析（Chunk ID 表、偏移量、压缩块信息）
- .ucas 数据段提取
- DefaultFileProvider 路径扫描
- 解析 .utoc/.ucas 对，提取有效 Container 条目
- 依赖 Phase 78 的 Provider 接口

**关键文件:** `io_store/` (新建目录), `file_provider/` (新建)

### Spec 4: PascalCase Output Format

**来源:** `ROADMAP.md` 中的 Phase 80 描述

**核心内容:**
- `format_json_cue4parse()` — PascalCase 字段名、ExportTypes 结构
- `format_text_full()` 重构 — dict→统一文本渲染
- BlueprintText 统一到 Schema
- JSON 输出与 CUE4Parse 字段名一一对应，无 snake_case 残留

**关键文件:** `formatters/json_formatter.py`, `formatters/text_formatter.py`

## 执行顺序

1. 为 4 个 Phase 创建对应的 spec 文档
2. 更新 CLAUDE.md
3. 更新 DEVELOPMENT.md 和 CONTRIBUTING.md
4. 删除 GSD 专用文件
5. 提交变更

## 验证

- `git status` 确认无未跟踪文件（除了新建的 docs/superpowers/）
- `.planning/phases/` 目录已删除
- `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, `.planning/PROJECT.md`, `.planning/config.json` 已删除
- `.planning/MILESTONES.md`, `.planning/archive/`, `.planning/milestones/` 仍然存在
- `CLAUDE.md` 中不再有 "gsd-sdk" 或 "GSD" 引用
- `docs/superpowers/specs/` 下有 4 个 spec 文件
