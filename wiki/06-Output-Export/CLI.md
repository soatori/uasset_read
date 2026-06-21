---
title: CLI 接口
section: cli
---

# CLI 接口

通过 `python run.py` 或 `python -m uasset_read` 提供对 `.uasset`/`.umap` 文件的解析和多种格式输出能力。

## 架构变更（0.4.1）

CLI 在 0.4.1 进行了重构，核心逻辑委托给 `core.py` 的纯函数 API，CLI 仅负责参数解析和输出写入。

```
CLI (cli.py) → core.py (parse_single/parse_batch) → IR → Renderers → Output
```

`--n2c` 和 `--cpp-json-ir` 标志已移除（N2C 模块整体删除）。

## 模块信息

| 项目 | 值 |
|------|------|
| 文件路径 | `src/uasset_read/cli.py` |
| 入口函数 | `main()` |
| 参数解析 | `create_parser()` |
| 格式路由 | `resolve_format()` |
| 核心委托 | `core.py`（parse_single / parse_batch / list_formats） |

## 基本用法

```bash
python run.py path/to/file.uasset              # JSON 输出（默认）
python run.py path/to/file.uasset --markdown   # Markdown + Mermaid 图表
```

## 命令行参数

### 位置参数

| 参数 | 说明 |
|------|------|
| `file` | `.uasset`/`.umap` 文件路径（必需；批量模式下为目录路径） |

### 输出格式标志（互斥）

以下标志位于互斥组中，同一时间只能使用一个：

| 标志 | 格式名 | 说明 |
|------|--------|------|
| `--json` | `json` | 结构化 JSON 输出（C++ 翻译参考，默认） |
| `--markdown` | `markdown` | Markdown + Mermaid 流程图 |

### 已移除的标志

| 标志 | 说明 |
|------|------|
| `--n2c` | N2C 模块已整体删除 |
| `--cpp-json-ir` | 合并到 cpp_skeleton |
| `--validate` | N2C 验证已移除 |
| `--graph` | 旧版兼容标志已移除 |
| `--json-summary` | 输出格式精简时移除 |
| `--text` | 输出格式精简时移除 |
| `--text-summary` | 输出格式精简时移除 |
| `--summary` | 输出格式精简时移除 |
| `--blueprint-text` | 输出格式精简时移除 |
| `--blueprint-ue-text` | 输出格式精简时移除 |
| `--cpp-skeleton` | 输出格式精简时移除 |

### 解析控制标志

| 标志 | 说明 |
|------|------|
| `--verbose` | 输出额外详细字段 |
| `--function-graphs` | 在输出中包含 `function_graphs` |
| `--tolerant` | 容错模式（默认开启） |
| `--strict` | 禁用容错模式：序列化问题抛出 ParseError |
| `--export INDEX` | 仅输出指定索引的 export |
| `--schema` | 包含字段语义注解 |

### 资源解析标志

| 标志 | 说明 |
|------|------|
| `--asset-root DIR` | 搜索父级 `.uasset` 文件的根目录（可重复使用） |
| `--include-parent-assets` | 解析并包含父级 Blueprint 资产 |
| `--mappings FILE` | 加载 `.usmap`/`.jmap`/`.jmap.gz` 类型映射 |
| `--game NAME` | 启用游戏专用属性读取器（如 `Borderlands4`） |

### 批量模式标志

| 标志 | 说明 |
|------|------|
| `--batch` | 启用批量模式：将位置参数视为 `.uasset` 文件目录 |
| `--batch-dir DIR` | 批量模式输出目录（默认：`{input_dir}/output`） |

### 调试和工具标志

| 标志 | 说明 |
|------|------|
| `--output FILE` | 将输出写入文件而非 stdout |
| `--list-formats` | 列出所有可用导出格式并退出 |
| `--list-package-files` | 列出发现的包侧车/载荷文件并退出 |

## 退出代码

| 代码 | 常量 | 说明 |
|------|------|------|
| `0` | `EXIT_SUCCESS` | 成功 |
| `1` | `EXIT_PARSE_ERROR` | 解析错误 |
| `2` | `EXIT_FILE_NOT_FOUND` | 文件不存在或不是文件 |
| `3` | `EXIT_ARGUMENT_ERROR` | 参数错误 |

## 格式路由逻辑

`resolve_format()` 函数将 CLI 标志映射到内部格式名：

```
--markdown        → markdown
--json            → json
(无标志)          → json（默认）
```

> [!WARNING]
> 以下旧路由已移除：`--n2c`、`--cpp-json-ir`、`--graph`、`--text`、`--summary`、`--blueprint-text`、`--blueprint-ue-text`、`--cpp-skeleton`

## 解析路径

CLI 通过 `core.py` 的 `parse_single()` 进行解析：

1. 根据格式判断是否需要 linker（`cpp_skeleton` 需要，其他不需要）
2. 调用 `parse_single()` → 内部自动完成：解析 → IR 构建 → 渲染
3. 写入 stdout 或文件

## 批量模式

```bash
# 处理目录中所有 .uasset/.umap 文件
python run.py /path/to/assets/ --batch

# 指定输出目录
python run.py /path/to/assets/ --batch --batch-dir /path/to/output/

# 批量导出为 JSON
python run.py /path/to/assets/ --batch --json
```

批量结果报告输出到 stderr：

```
Batch export complete: 10 files
  Success: 8
  Failed: 2
    - BP_Error.uasset: ParseError: ...
```

## 完整示例

```bash
# 1. 解析单个文件，输出到 stdout
python run.py MyBlueprint.uasset

# 2. JSON 输出
python run.py MyBlueprint.uasset --json

# 3. 输出到文件
python run.py MyBlueprint.uasset --json --output result.json

# 4. Markdown + Mermaid 文档
python run.py MyBlueprint.uasset --markdown --output report.md

# 5. 包含父级资产解析
python run.py MyBlueprint.uasset --json --include-parent-assets --asset-root /Game/Content

# 6. 使用类型映射
python run.py MyBlueprint.uasset --json --mappings mappings.usmap

# 7. 列出包文件
python run.py MyBlueprint.uasset --list-package-files

# 8. 列出所有可用格式
python run.py --list-formats
```

## 调用方式

CLI 可通过以下方式调用：

- **脚本**: `python run.py ...`（项目根目录）
- **模块**: `python -m uasset_read ...`（`__main__.py` 入口）

两者都调用同一个 `main()` 函数。

## 输出流约定

- **stdout**: 仅用于数据输出
- **stderr**: 用于错误消息、状态信息和批量报告

这允许用户通过管道将数据与其他工具连接，同时保留人类可读的错误信息。

**相关章节**: [[渲染器系统]] · [[格式化器]]
