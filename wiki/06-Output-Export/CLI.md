---
title: CLI 接口
section: cli
---

# CLI 接口

命令行工具 `uasset-read` 提供对 `.uasset`/`.umap` 文件的解析和多种格式导出能力。

## 模块信息

| 项目 | 值 |
|------|------|
| 文件路径 | `src/uasset_read/cli.py` |
| 入口函数 | `main()` |
| 参数解析 | `create_parser()` |
| 格式路由 | `resolve_format()` |

## 基本用法

```bash
uasset-read path/to/file.uasset              # 默认 YAML 风格文本
uasset-read path/to/file.uasset --json       # 完整 JSON 输出
uasset-read path/to/file.uasset --summary    # 紧凑摘要
uasset-read path/to/file.uasset --markdown   # Markdown + Mermaid 图表
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
| `--json` | `json` | 完整 JSON 结构输出 |
| `--json-summary` | `json_summary` | 精简 JSON 摘要（token 减少 70%+） |
| `--text` | `text` | YAML 风格全文（默认） |
| `--text-summary` | `text_summary` | YAML 风格精简摘要 |
| `--summary` | `json_summary` | 同 `--json-summary`，紧凑摘要 |
| `--markdown` | `markdown` | Markdown + Mermaid 流程图 |
| `--blueprint-text` | `blueprint_text` | 蓝图节点翻译参考文本（紧凑格式） |
| `--blueprint-ue-text` | `blueprint_ue_text` | UE 编辑器风格蓝图节点文本 |
| `--cpp-skeleton` | `cpp_skeleton` | C++ 类骨架 `.h` 头文件（需要 Blueprint） |
| `--cpp-json-ir` | `cpp_json_ir` | C++ 类骨架 JSON IR 格式 |
| `--n2c` | `n2c` | N2C 中间格式 JSON |

### 解析控制标志

| 标志 | 说明 |
|------|------|
| `--verbose` | 输出额外详细字段 |
| `--graph` | 包含蓝图图数据（向后兼容逻辑） |
| `--function-graphs` | 在 JSON 输出中包含 `function_graphs` 数组（output_version 5.0） |
| `--tolerant` | 容错模式（默认开启） |
| `--strict` | 禁用容错模式：序列化问题抛出 ParseError |
| `--export INDEX` | 仅输出指定索引的 export |
| `--schema` | 包含字段语义注解（`_schema`） |

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
| `--verbose` | 启用调试日志 |
| `--output FILE` | 将输出写入文件而非 stdout |
| `--list-formats` | 列出所有可用导出格式并退出 |
| `--validate` | 验证输出是否符合 schema（N2C 格式） |
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
--n2c            → n2c
--cpp-json-ir    → cpp_json_ir
--cpp-skeleton   → cpp_skeleton
--blueprint-text → blueprint_text
--blueprint-ue-text → blueprint_ue_text
--markdown       → markdown
--summary        → json_summary
--json-summary   → json_summary
--json           → json
--text-summary   → text_summary
--text           → text
(无标志)         → text（默认）
```

## 解析路径

CLI 主函数根据格式选择不同的解析路径：

### 需要 Linker 解析的格式

以下格式调用 `parse_uasset_with_linker()`，需要完整的对象图重建：

- `cpp_skeleton`
- `cpp_json_ir`
- `blueprint_ue_text`
- `json`
- `json_summary`

### 标准解析路径

其他格式调用 `parse_package()` 进行标准解析。

### 特殊路径：`--graph` 模式

`--graph` 标志不经过统一导出器，直接调用旧版格式化器函数（向后兼容）：

- `--graph` + `--json-summary` / `--summary` → `format_json_summary`
- `--graph` + `--json` / `--verbose` → `format_json_full`
- `--graph` + `--text-summary` → `format_text_summary`
- `--graph` + `--text` → `format_text_full`
- `--graph` 单独使用 → 仅输出图数据的 JSON

## 批量模式

```bash
# 处理目录中所有 .uasset/.umap 文件
uasset-read /path/to/assets/ --batch

# 指定输出目录
uasset-read /path/to/assets/ --batch --batch-dir /path/to/output/

# 批量导出为 JSON
uasset-read /path/to/assets/ --batch --json
```

批量导出目录结构：

```
output_dir/
  BP_MyBlueprint/
    blueprint.json
  BP_Another/
    blueprint.json
```

批量结果报告输出到 stderr：

```
Batch export complete: 10 files
  Success: 8
  Skipped: 1
    - BP_Skipped.uasset: already cooked
  Failed: 1
    - BP_Error.uasset: ParseError: ...
```

## 完整示例

```bash
# 1. 解析单个文件，输出到 stdout
uasset-read MyBlueprint.uasset

# 2. 完整 JSON 输出
uasset-read MyBlueprint.uasset --json

# 3. 输出到文件
uasset-read MyBlueprint.uasset --json --output result.json

# 4. C++ 骨架生成（需要 Blueprint）
uasset-read MyBlueprint.uasset --cpp-skeleton --output MyBlueprint.h

# 5. Markdown + Mermaid 文档
uasset-read MyBlueprint.uasset --markdown --output report.md

# 6. N2C 中间格式 + 验证
uasset-read MyBlueprint.uasset --n2c --validate

# 7. 包含父级资产解析
uasset-read MyBlueprint.uasset --json --include-parent-assets --asset-root /Game/Content

# 8. 使用类型映射
uasset-read MyBlueprint.uasset --json --mappings mappings.usmap

# 9. 列出包文件
uasset-read MyBlueprint.uasset --list-package-files

# 10. 列出所有可用格式
uasset-read --list-formats
```

## 双入口点

CLI 可通过以下方式调用：

- **命令行**: `uasset-read ...`（通过 `pyproject.toml` 的 `console_scripts` 入口）
- **模块**: `python -m uasset_read ...`（通过 `__main__.py`）

两者都调用同一个 `main()` 函数。

## 输出流约定

- **stdout**: 仅用于数据输出
- **stderr**: 用于错误消息、状态信息和批量报告

这允许用户通过管道将数据与其他工具连接，同时保留人类可读的错误信息。

**相关章节**: [[导出系统]] · [[格式化器]]
