# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 行为规则

- **语言**：所有对话、代码注释、错误提示、文档统一使用中文
- **输出**：专业简洁，避免冗余
- **无需向后兼容** — 纯输出脚本，不对外暴露 API，可直接修改/删除接口
- **CodeGraph**：优先使用 `codegraph_*` 工具回答结构化问题（详见全局 CLAUDE.md）

## 项目概述

**uasset_read** — 虚幻引擎 `.uasset` 文件的 Python 解析器，零运行时依赖。

- **专注领域**：未烘焙/编辑器保存的资产（含完整蓝图数据）
- **版本**：0.4.5 | **Python**：3.10+
- **构建系统**：直接脚本运行（src 布局），禁止 `pip install`
- **核心使命**：在不开启 UE 编辑器的情况下，读取并解析 `.uasset` 等 UE 二进制资产文件
- **统一输出架构**：所有解析结果经过统一 IR 层，可输出 JSON / Markdown / Text / C++ 骨架等格式
- **版本优先级**：主要支持 UE5+，UE4 仅兼容部分主要资产类型
- **输出质量标准**：解析输出质量必须与对照的 C++ 类定义和蓝图节点文本相匹配
- **序列化策略**：优先遵从 UE 编辑器源码的 `FArchive` 管线，仅在特殊场景使用替代方式
- **测试策略**：优先随机真实资产抽测，特别关注大文件内存安全（防 OOM/泄漏）

## CLI 与测试

```bash
# 解析（默认 JSON）
python run.py file.uasset                    # JSON（默认）
python run.py file.uasset --text             # 人类可读文本
python run.py file.uasset --markdown         # Markdown + Mermaid
python run.py file.uasset --cpp-skeleton     # C++ 类骨架
python run.py file.uasset --summary          # 摘要
python run.py file.uasset --blueprint-text   # 蓝图节点文本
python run.py file.uasset --blueprint-ue-text # UE 格式文本

# 模式控制
python run.py file.uasset --strict           # 遇警告停止
python run.py file.uasset --tolerant         # 容错模式（默认）
python run.py file.uasset --verbose          # 调试日志
python run.py --batch-dir path/to/dir/       # 批量导出

# 测试矩阵
python scripts/test_matrix.py smoke          # L0 烟雾测试（最快）
python scripts/test_matrix.py unit           # L0+L1 单元测试
python scripts/test_matrix.py integration    # 集成测试
python scripts/test_matrix.py regression     # 回归测试
python scripts/test_matrix.py quality        # 质量门禁
python scripts/test_matrix.py acceptance     # 最终验收
python scripts/test_matrix.py all            # 全量

# 直接 pytest
python -m pytest tests/test_pak_handling.py -v
python -m pytest tests/ -v -m integration
python -m pytest tests/ -v --cov=uasset_read
```

**Windows 路径**：使用正斜杠 `E:/Develop/...` 或双反斜杠。
**测试要求**：100% 通过率，≥12 种资产类型，稳定资产 strict + tolerant 双模式通过。
**样本路径**：`E:\Develop\lib\UnrealEngine\Samples`
**pytest 标记**：`integration`、`quality`、`regression`、`slow`、`auxiliary`、`acceptance`

## 核心架构

解析器镜像 UE 内部的 `FArchive` 序列化管线，采用**两层架构**：

```
第一层：二进制解析
.uasset → FArchive → Serializers → Parsers → Linker → ParseResult

第二层：IR 转换与渲染
ParseResult → IR Builder → PackageIR → Renderers → JSON/Text/Markdown/C++
```

`ParseResult` 是原始解析结果容器；`PackageIR` 是统一中间表示，所有渲染器只接收 IR。

### 关键模块

- **parse_uasset.py** — 底层入口，`parse_package()` 返回 `ParseResult`
- **core.py** — 高层 API（`parse_single`、`parse_batch`），CLI 和脚本共用
- **models/result.py** — `ParseResult` 容器
- **models/ir.py** — IR 数据结构：`PackageIR → ExportIR → GraphIR → NodeIR → PinIR`
- **ir_builder.py** — `ParseResult` → `PackageIR` 转换器

### 蓝图解析链

```
serializers/graph.py → graph/flow_builder.py → graph/data_tracker.py
  → blueprint/variable_extractor.py → kismet/（字节码 → AST → C++）
```

### 渲染器系统

渲染器通过 `RENDERER_REGISTRY` 自动注册。新增格式：在 `renderers/` 实现 `IRenderer` 子类 → `register_renderer()` → `__init__.py` 添加 import。
**可用渲染器**：JSON、Text、Markdown、BlueprintText、BlueprintUE、CppSkeleton

### 其他机制

- **类处理注册表**：`ClassHandlerRegistry` 为特定 UE 类定制序列化行为（`parsers/class_registry.py`）
- **属性回退**：未知属性返回 `PropertyFallback`（含诊断信息），结构体内部用 `StructFallback`
- **容错模式**：strict（遇警告停止）/ tolerant（默认，遇错继续标记 partial）
- **轻量解析**：export_count > 300 时自动跳过完整蓝图解析

## 分支管理与提交规范

### 分支策略

| 分支 | 用途 |
|---|---|
| `develop` | **日常开发**（默认），包含完整文件 |
| `master` | **发布分支**，仅含发布内容，定期从 develop 同步 |
| `wiki/master` | Wiki 专用，独立维护 |

**默认工作分支为 `develop`**。

### master 分支文件白名单

master 仅保留：`src/uasset_read/`、`.github/workflows/`、`README*.md`、`CLAUDE.md`、`LICENSE`、`pytest.ini`、`run.py`、`.claude/rules/`、`tests/`、`docs/formats/`、`docs/designs/`、`docs/reference/`、`docs/agents/`、`docs/release-notes/`。

排除：`wiki/`、`docs/guides/`、`docs/superpowers/`、`docs/reports/`、`scripts/`、`.claude/skills/`、`.claude/workflows/`、`.claude/agents/`、`temp/`。

### 版本发布流程

从 develop 合并到 master，执行前确认 release commit/tag 已完成、`git status --short` 为空。

```bash
git checkout master
git merge develop --no-commit
# 排除仅开发文件
git reset HEAD wiki/ docs/guides/ docs/superpowers/ docs/reports/ scripts/ \
    .claude/skills/ .claude/workflows/ .claude/agents/
git checkout HEAD -- wiki/ docs/guides/ docs/superpowers/ docs/reports/ scripts/ \
    .claude/skills/ .claude/workflows/ .claude/agents/ 2>/dev/null
git clean -fd wiki/ docs/guides/ docs/superpowers/ docs/reports/ scripts/ \
    .claude/skills/ .claude/workflows/ .claude/agents/
git commit -m "Merge develop (vX.Y.Z) into master"
```

远端推送仅在用户明确要求后执行。CI 自动校验白名单合规。

### 提交信息格式

`<type>: <简要描述>` — 类型：`feat`、`fix`、`refactor`、`test`、`docs`、`chore`、`release`

## 关键约束

见 [.claude/rules/constraints.md](.claude/rules/constraints.md)。核心：仅支持未烘焙资产、只读、零依赖、必须参考 UE 源码、临时文件放 `temp/`。

## 文档与 Skills

**文档**：`wiki/`（开发指南）、`docs/formats/uasset/`（格式参考）、`docs/designs/`（设计规格）、`docs/reference/`（技术参考）、`docs/release-notes/`（发布说明）、`temp/`（临时文件）。

**Skills**（`.claude/skills/`，通过 `/skill-name` 调用）：
`test-runner`（测试）、`code-quality-fix`（质量修复）、`doc-consistency`（文档审计）、`version-sync`（版本同步）、`release-prep`（发布流程）、`ue-source-research`（UE 源码对照）、`ue-wiki-lookup`（UE wiki 查询）。

**Issue tracker**：GitHub Issues（gh CLI），详见 `docs/agents/issue-tracker.md`。
Triage labels：needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix。
