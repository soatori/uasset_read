# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 行为规则

- **语言**：所有对话、代码注释、错误提示、文档统一使用中文
- **输出**：专业简洁，避免冗余
- **CodeGraph**：优先使用 `codegraph_*` 工具回答结构化问题（详见全局 CLAUDE.md）

## 项目概述

**uasset_read** — 虚幻引擎 `.uasset` 文件的 Python 解析器，零运行时依赖。

- **专注领域**：未烘焙/编辑器保存的资产（含完整蓝图数据）
- **版本**：0.4.5 | **Python**：3.10+
- **构建系统**：直接脚本运行（src 布局），禁止 `pip install`
- **详细开发指南**：[docs/guides/dev-guide.md](docs/guides/dev-guide.md)

## 快速开始

```bash
# 解析单个文件
python run.py path/to/file.uasset              # JSON 输出（默认）
python run.py path/to/file.uasset --text       # 人类可读文本
python run.py path/to/file.uasset --markdown   # Markdown + Mermaid 图表
python run.py path/to/file.uasset --cpp-skeleton  # C++ 类骨架

# 运行测试
python scripts/test_matrix.py smoke            # 快速烟雾测试
python scripts/test_matrix.py unit             # 单元测试
python scripts/test_matrix.py all              # 全量测试

# 代码质量
python scripts/test_matrix.py quality          # 质量门禁
```

## 常用命令

### 解析器 CLI

```bash
# 输出格式
python run.py file.uasset --summary            # 摘要
python run.py file.uasset --blueprint-text     # 蓝图节点文本
python run.py file.uasset --blueprint-ue-text  # UE 格式文本

# 模式控制
python run.py file.uasset --strict             # 遇警告停止
python run.py file.uasset --tolerant           # 容错模式（默认）
python run.py file.uasset --verbose            # 调试日志

# 批量处理
python run.py --batch-dir path/to/dir/         # 批量导出
```

**Windows 路径注意**：使用正斜杠 `E:/Develop/...` 或双反斜杠，避免单反斜杠转义问题。

### 测试矩阵

```bash
python scripts/test_matrix.py smoke            # L0 烟雾测试（最快）
python scripts/test_matrix.py unit             # L0+L1 单元测试
python scripts/test_matrix.py integration      # 集成测试
python scripts/test_matrix.py regression       # 回归测试
python scripts/test_matrix.py quality          # 质量门禁
python scripts/test_matrix.py acceptance       # 最终验收
python scripts/test_matrix.py all              # 全量

# 直接 pytest
python -m pytest tests/test_pak_handling.py -v # 单个文件
python -m pytest tests/ -v -m integration      # 仅集成测试
python -m pytest tests/ -v --cov=uasset_read   # 覆盖率
```

**测试要求**：100% 通过率，≥12 种资产类型，稳定资产必须在 strict 和 tolerant 双模式下通过。
**样本路径**：`E:\Develop\lib\UnrealEngine\Samples`
**pytest 标记**：`integration`、`quality`、`regression`、`slow`

## 核心架构

解析器镜像 UE 内部的 `FArchive` 序列化管线：

```
.uasset → FArchive → Serializers → Parsers → Linker → IR Builder → Renderers
```

### 关键模块

- **parse_uasset.py** — 主入口，`parse_package()` 返回 `ParseResult`
- **core.py** — 高层 API（`parse_single`、`parse_batch`），CLI 和脚本共用
- **ir_builder.py** — `ParseResult` → `PackageIR`，渲染器只接收 IR
- **models/ir.py** — IR 数据结构：`PackageIR → ExportIR → GraphIR → NodeIR → PinIR`
- **models/result.py** — `ParseResult` 容器（summary、linker、graphs、blueprint）

### 蓝图解析链

```
serializers/graph.py → graph/flow_builder.py → graph/data_tracker.py
  → blueprint/variable_extractor.py → kismet/（字节码 → AST → C++）
```

### 渲染器系统

渲染器通过 `RENDERER_REGISTRY` 自动注册。新增格式：
1. 在 `renderers/` 实现 `IRenderer` 子类
2. 调用 `register_renderer(format_name, RendererClass)`
3. 在 `renderers/__init__.py` 添加 import

### 容错模式

- **strict**：遇警告停止
- **tolerant**（默认）：遇错继续，标记 partial
- **轻量解析**：export_count > 300 时自动跳过完整蓝图解析

## 分支管理与提交规范

### 分支策略

| 分支 | 用途 | 说明 |
|---|---|---|
| `develop` | **日常开发**（默认工作分支） | 所有开发任务基于此分支，包含完整文件（src、tests、docs、wiki、scripts） |
| `master` | **发布分支** | 仅包含发布内容（src、CI、README、CLAUDE.md、pytest.ini），定期从 develop 同步 |
| `wiki/master` | Wiki 专用 | 独立维护，不纳入主分支 |

**默认工作分支为 `develop`**，所有功能开发、Bug 修复、测试编写均在 develop 上进行。

### master 分支文件白名单

master 仅保留以下内容，开发辅助文件不进入 master：

| 允许 | 排除 |
|---|---|
| `src/uasset_read/` | `wiki/` |
| `.github/workflows/` | `docs/guides/`、`docs/superpowers/`、`docs/reports/` |
| `README.md`、`README.zh-CN.md` | `scripts/` |
| `CLAUDE.md`、`LICENSE` | `.claude/skills/`、`.claude/workflows/`、`.claude/agents/` |
| `pytest.ini`、`run.py` | `temp/` |
| `.claude/rules/` | |
| `tests/`（CI 需要） | |
| `docs/formats/`、`docs/designs/`、`docs/reference/`、`docs/agents/`、`docs/release-notes/` | |

### 版本发布流程

定期版本发布时，从 develop 合并到 master：

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
git push origin master
```

**CI 自动校验**：master 分支包含文件目录合规检查，违反白名单将被拒绝。

### 提交信息格式

```
<type>: <简要描述>
```

类型：`feat`、`fix`、`refactor`、`test`、`docs`、`chore`、`release`

## 关键约束

见 [.claude/rules/constraints.md](.claude/rules/constraints.md)。核心：
- 仅支持未烘焙/编辑器保存的资产
- 只读，不支持修改或写入
- 零运行时依赖
- 必须参考 UE 源码（`E:\Develop\lib\UnrealEngine`），禁止猜测二进制格式
- 临时文件放 `temp/`

## CodeGraph

本项目已配置 CodeGraph MCP 服务器。工具选择和使用规则详见全局 CLAUDE.md。

## 文档与工具

### 文档结构

- `wiki/` — 开发指南（独立维护）
- `docs/formats/uasset/` — UE .uasset 格式参考（60+ 文件）
- `docs/designs/` — 永久设计规格
- `docs/reference/` — 技术参考资料
- `docs/release-notes/` — 版本发布说明
- `temp/` — 临时文件、脚本、中间产物

### Agent skills

项目 skills 位于 `.claude/skills/`，通过 `/skill-name` 调用：

| Skill | 触发场景 |
|---|---|
| `test-runner` | 运行测试、更新文档统计 |
| `code-quality-fix` | P0-P3 分级代码质量修复 |
| `doc-consistency` | 文档一致性审计 |
| `version-sync` | 跨文件版本号同步 |
| `release-prep` | 发布前完整流程（版本同步→测试→文档→提交） |

### Issue tracker

使用 GitHub Issues 跟踪任务（gh CLI）。详见 `docs/agents/issue-tracker.md`。

**Triage labels**：needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix（详见 `docs/agents/triage-labels.md`）。

**Domain docs**：单上下文布局，详见 `docs/agents/domain.md`。
