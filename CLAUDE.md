# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 行为规则

- 所有对话、代码注释、错误提示、文档统一使用中文
- 输出专业简洁

## 项目概述

**uasset_read** — 虚幻引擎 `.uasset` 文件的 Python 解析器。专注于未烘焙/编辑器保存的资产（含完整蓝图数据）。

- **版本**: 0.4.4 | **Python**: 3.10+ | **运行时依赖**: 零依赖
- 构建系统: 直接脚本运行（src 布局），禁止 `pip install`
- 详细开发指南见 [docs/guides/dev-guide.md](docs/guides/dev-guide.md)

## 运行解析器

### CLI 命令

```bash
# 基础用法
python run.py path/to/file.uasset              # JSON（默认）
python run.py path/to/file.uasset --text       # 人类可读文本
python run.py path/to/file.uasset --markdown   # Markdown + Mermaid
python run.py path/to/file.uasset --cpp-skeleton  # C++ 类骨架
python run.py path/to/file.uasset --blueprint-text  # 蓝图节点文本

# 模式控制
python run.py path/to/file.uasset --strict     # 遇警告停止
python run.py path/to/file.uasset --verbose    # 调试日志

# 批量
python run.py --batch-dir path/to/dir/         # 批量导出
```

### Windows 注意事项

- 路径使用正斜杠 `E:/Develop/...` 或双反斜杠 `E:\\Develop\\...`，避免单反斜杠转义问题
- Workflow 脚本中统一使用正斜杠：`const BASE = 'E:/Develop/lib/UnrealEngine/Samples'`
- PowerShell 中调用时路径含空格需加引号：`python run.py "E:/path with spaces/file.uasset"`

### Workflow 中调用解析器的规范

在 Workflow agent prompt 中调用解析器时，使用以下模板：

```
运行命令：python run.py "<完整路径>" [选项]
工作目录：E:/Develop/uasset_read
返回格式：直接返回解析输出或错误信息
```

## 测试

```bash
# 运行测试
python -m pytest tests/ -v                     # 全部测试
python -m pytest tests/ -v -m integration      # 仅集成测试
python -m pytest tests/test_pak_handling.py -v # 单个文件
python -m pytest tests/ -v --cov=uasset_read   # + 覆盖率
python -m pytest tests/test_api_cleanup.py -v  # API 导出验证
```

- 位置: `tests/`（1172 用例通过，2 skipped，2 xfail）
- 要求: 100% 通过率，≥ 12 种资产类型
- 稳定资产必须在 strict 和 tolerant 双模式下通过
- 样本资产路径: `E:\Develop\lib\UnrealEngine\Samples`
- pytest 标记: `integration`（集成测试）、`quality`（质量门禁）、`regression`（回归）、`slow`（慢速）

## 架构

解析器镜像 UE 内部的 `FArchive` 序列化管线。数据流：

```
.uasset 文件
  → FArchive（archive.py）二进制读取，字节交换、mmap
  → 序列化层（serializers/）PackageFileSummary、ImportMap、ExportMap、PropertyTag
  → 属性解析（parsers/）40+ 种属性类型解析器 + 分发器
  → 对象图重建（link/）PackageLinker 两阶段链接
  → IR 构建（ir_builder.py）统一中间表示 PackageIR
  → 渲染器（renderers/）6 种格式输出（JSON/Text/Markdown/BlueprintText/BlueprintUE/CppSkeleton）
```

### 核心模块关系

- **parse_uasset.py** — 主解析入口，编排整个管线。`parse_package()` 返回 `ParseResult`，`parse_uasset_with_linker()` 额外返回 `PackageLinker`
- **core.py** — 纯函数高层 API（`parse_single`、`parse_batch`），CLI 和脚本共用
- **ir_builder.py** — 将 `ParseResult` 转为 `PackageIR`，渲染器只接收 IR 不访问 ParseResult
- **models/ir.py** — IR 数据结构：`PackageIR → ExportIR → GraphIR → NodeIR → PinIR`
- **models/result.py** — `ParseResult`：解析结果容器（summary、linker、graphs、blueprint 等）

### 蓝图解析链

```
serializers/graph.py          读取 UEdGraph 原始节点和引脚
  → graph/flow_builder.py     构建执行流/数据流
  → graph/data_tracker.py     追踪数据依赖
  → blueprint/variable_extractor.py  提取变量、事件、函数、元数据
  → kismet/                   字节码 → AST → C++ 翻译
```

### 渲染器系统

渲染器通过 `RENDERER_REGISTRY` 自动注册。新增格式需：
1. 在 `renderers/` 下实现 `IRenderer` 子类
2. 调用 `register_renderer(format_name, RendererClass)`
3. 在 `renderers/__init__.py` 添加 import 触发注册

### 容错模式

- **strict**：遇警告停止解析
- **tolerant**（默认）：遇错继续，标记 partial 状态
- **轻量解析**：export_count > 300 时自动跳过完整蓝图解析（`LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD`）

## 关键约束

见 [.claude/rules/constraints.md](.claude/rules/constraints.md)。核心：
- 仅支持未烘焙/编辑器保存的资产
- 只读，不支持修改或写入
- 零运行时依赖
- 必须参考 UE 源码（`E:\Develop\lib\UnrealEngine`），禁止猜测二进制格式
- 临时文件放 `temp/`

## CodeGraph 使用规范

本项目已配置 CodeGraph MCP 服务器（`codegraph_*` 工具），提供 tree-sitter 解析的符号知识图库。

### 工具选择决策表

| 问题 | 使用工具 | 不要用 |
|---|---|---|
| "X 在哪里定义？" / "查找符号 X" | `codegraph_search` | grep/read |
| "谁调用了 Y？" | `codegraph_callers` | 手动 grep |
| "Y 调用了什么？" | `codegraph_callees` | 手动 read |
| "X 到 Y 的调用路径？" | `codegraph_trace` | 多次 search+callers |
| "改 Z 会影响什么？" | `codegraph_impact` | 手动推导 |
| "查看 Y 的签名/源码" | `codegraph_node` | read 文件 |
| "给我任务相关的上下文" | `codegraph_context` | 多次 search+node |
| "批量查看多个符号" | `codegraph_explore` | 逐个 node 调用 |
| 字符串内容/注释/日志文字 | `grep` / Grep | codegraph |

### 核心规则

1. **结构性问题优先用 codegraph** — 调用链、定义位置、影响范围等，codegraph 比 grep 快且准确
2. **不要重复 codegraph 已做的事** — `codegraph_context` 一次返回符号定义+调用者+被调用者+源码，无需再用 search+node 组合
3. **检查索引新鲜度** — 如果返回结果含 "⚠️ Some files…were edited since the last index sync"，用 `codegraph_status` 查看待同步文件，对这些文件用 Read 获取最新内容
4. **只有字面搜索才用 grep** — 查找日志文本、注释内容、硬编码字符串等

## 文档结构

```
docs/
├── guides/              ← 开发规范（活跃参考）
│   ├── dev-guide.md           开发指南（架构、模块、CLI、测试）
│   ├── development-scope.md   开发范围及限制
│   └── testing-requirements.md  测试要求规范
├── formats/uasset/      ← UE .uasset 格式参考（60+ 文件）
├── designs/             ← 永久设计规格
├── reference/           ← 技术参考资料
└── release-notes/       ← 版本发布说明

wiki/                    ← 代码指南（独立维护）
temp/                    ← 临时文件、脚本、中间产物
```

## Agent skills

项目 skills 位于 `.claude/skills/`，通过 `/skill-name` 调用。

| Skill | 触发场景 |
|---|---|
| `test-runner` | 运行测试、更新文档统计 |
| `code-quality-fix` | P0-P3 分级代码质量修复 |
| `doc-consistency` | 文档一致性审计 |
| `version-sync` | 跨文件版本号同步 |
| `release-prep` | 发布前完整流程（版本同步→测试→文档→提交） |

### Issue tracker

使用 GitHub Issues 跟踪任务（gh CLI）。详见 `docs/agents/issue-tracker.md`。

### Triage labels

五个标准角色标签：needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix。详见 `docs/agents/triage-labels.md`。

### Domain docs

单上下文布局。详见 `docs/agents/domain.md`。
