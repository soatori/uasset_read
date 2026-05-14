# Phase 33: 入口与测试适配 - Research

**Researched:** 2026-05-12
**Domain:** Python CLI 入口、模块解析管线组装、测试导入适配
**Confidence:** HIGH

## Summary

Phase 33 是 v6.0 模块化重构的"最后一公里"——将旧版 `uasset_read.py` 的 CLI 入口、`parse_uasset` 主解析管线、以及公共 API 完整迁移到 `src/uasset_read/` 包中，并删除旧文件。本 phase 依赖于 Phase 31（graph/ 模块）和 Phase 32（formatters/ 模块）已完成的前提。Phase 33 本身不做新功能开发，只做等价迁移和路径适配。

当前基线：**411 passed, 47 skipped, 0 failed**。所有测试通过 `from uasset_read import ...` 导入，因为 `src/uasset_read/__init__.py` 已从新版模块导出 50+ 项，但 `parse_uasset` 等关键函数仍从旧版 `uasset_read.py` 重导出。Phase 33 完成后，所有重导出将来自新版模块，旧文件可安全删除。

**Primary recommendation:** 按"管线组装 -> CLI -> __init__.py 扩展 -> 测试验证 -> 删除旧文件"五步执行。`parse_uasset.py` 作为顶层模块（与 graph/、formatters/ 同级），消费所有子模块产出。

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01 (模块位置):** CLI 入口放在 `src/uasset_read/cli.py`，`pyproject.toml` 中 `uasset_read.cli:main` 已定义，保持不变。
- **D-02 (__main__.py):** 创建 `src/uasset_read/__main__.py` 支持 `python -m uasset_read`，内容为 `from uasset_read.cli import main; main()`。
- **D-03 (argparse 标志):** 等价迁移旧版 `create_parser()` 的全部标志：`file`（位置参数）、`--json/--text/--summary/--markdown`（互斥组）、`--verbose`、`--output`、`--export`、`--graph`、`--schema`。标志行为完全不变。
- **D-04 (退出码):** 等价迁移旧版退出码常量：`EXIT_SUCCESS=0`、`EXIT_PARSE_ERROR=1`、`EXIT_FILE_NOT_FOUND=2`、`EXIT_ARGUMENT_ERROR=3`。放在 `cli.py` 模块顶部。
- **D-05 (格式路由):** `main()` 中的格式路由逻辑等价迁移——根据 `args` 标志调用对应 `format_xxx()` 函数。Phase 32 已锁定格式化函数签名 `format_xxx(result: ParseResult, ...) -> Dict | str`。
- **D-06 (模块位置):** `parse_uasset` 函数放在 `src/uasset_read/parse_uasset.py`——与 formatters/graph/parsers 同级的顶层模块，因为它是整个解析管线的入口，消费所有子模块。
- **D-07 (管线流程):** 等价迁移旧版 `parse_uasset()` 的完整流程：FArchive → read_package_summary → read_name_table → read_import_map → read_export_map → parse_properties_from_export (per export) → extract_component_transforms → extract_blueprint_metadata → extract_blueprint_graphs (Phase 31) → ParseResult。
- **D-08 (错误处理):** 等价迁移 D-15 优雅降级模式——VersionError/ParseError 捕获到 result.errors，不中断解析，返回部分结果。
- **D-09 (导出扩展):** 在现有 `__init__.py` 基础上追加导出：`parse_uasset` (from `.parse_uasset`)、所有 graph 模块公共 API (from `.graph`)、所有 formatters 公共 API (from `.formatters`)、常量追加：`MAX_PINS_PER_NODE`, `MAX_NODES_PER_GRAPH`, `MAX_LINKEDTO_PER_PIN`, `START_EVENT_TYPES`、版本更新：`__version__` 从 "5.1.0" 更新为 "6.0.0"。
- **D-10 (向后兼容):** `__all__` 列表保持现有 50+ 导出项不变，仅追加不删除——直到 Phase 34 等价验证完成后才考虑清理。
- **D-11 (导入路径更新):** 所有测试文件中的 `from uasset_read import X` 改为从 `src/uasset_read/` 的新模块路径导入。但 `parse_uasset` 和公共 API 仍通过 `from uasset_read import X` 导入（因为 `__init__.py` 会重新导出）。
- **D-12 (mock 数据):** 测试中直接引用旧版内部函数的部分（如 `from uasset_read import read_ue_graph`）需要改为从新模块路径导入，或使用 mock。
- **D-13 (已知失败):** ROADMAP.md 提到 7 个已知失败测试——Phase 33 修复这些失败的导入路径问题，功能性修复留给 Phase 34 等价验证。
- **D-14 (测试顺序):** 先跑 `pytest tests/ --tb=short` 确认基线（当前 411 passed, 47 skipped），再逐个修复失败。
- **D-15 (删除时机):** 在测试全部适配并通过后再删除 `uasset_read.py`。删除前确认：(1) 所有测试通过，(2) `python -m uasset_read` 能正常解析测试资产，(3) CLI `uasset-read` 入口可用。
- **D-16 (保留引用):** 删除后 `CLAUDE.md` 中关于旧版的描述需要更新，`__init__.py` 中从旧版重导出的代码需要移除。

### Claude's Discretion
- `cli.py` 中辅助函数的精确划分（如 `_route_format()` 是否需要独立函数）由规划阶段确定
- `parse_uasset.py` 的内部结构（单函数 vs 分步骤函数）由规划阶段确定
- 测试修复的精确顺序和分组由规划阶段确定

### Deferred Ideas (OUT OF SCOPE)
- MCP Server 封装 — 延后至 v4.x（PROJECT.md Out of Scope）
- JSON Schema 验证 — 延后至 v9.0 (Phase 48)
- `uasset-read` CLI 的额外功能（如批量处理、管道输入）— 不在等价迁移范围内

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CLI 入口与参数解析 | 客户端（CLI） | — | 纯本地命令行入口，无网络交互 |
| 解析管线编排 | API/后端 | — | `parse_uasset` 是纯本地文件解析函数 |
| 公共 API 导出 | API/后端 | — | `__init__.py` 是包的公共接口 |
| 测试导入适配 | 测试层 | — | 测试通过 `from uasset_read` 导入 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| argparse | Python 3.10 stdlib | CLI 参数解析 | 旧版已使用，零依赖项目标准选择 |
| sys | Python 3.10 stdlib | 退出码、stdout/stderr 路由 | 标准 CLI 模式 |
| pathlib.Path | Python 3.10 stdlib | 文件路径操作 | 旧版已使用 |
| json | Python 3.10 stdlib | JSON 序列化输出 | 旧版已使用 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=7.0 (dev) | 测试运行 | 运行 18 个测试文件 |

**无需安装新依赖** — 项目零运行时依赖，CLI 全部使用标准库。

## Architecture Patterns

### System Architecture Diagram

```
CLI (cli.py)
  │
  ├─ argparse → parse args (file, --json, --text, --summary, --markdown, --verbose, --output, --export, --graph, --schema)
  │
  ├─ parse_uasset(path) ───────────────────────────────────┐
  │  │                                                      │
  │  ├─ FArchive(path)                                     │
  │  ├─ read_package_summary(archive) → summary            │
  │  ├─ read_name_table(archive, summary) → name_map       │
  │  ├─ read_import_map(archive, summary, name_map) → import_map
  │  ├─ read_export_map(archive, summary, name_map) → export_map
  │  ├─ for export in export_map:                          │
  │  │   └─ parse_properties_from_export(export, ...)       │
  │  ├─ extract_blueprint_metadata(bpgc, ...) → blueprint  │  parse_uasset.py
  │  ├─ extract_blueprint_graphs(archive, ...) → graphs    │  (Phase 33 创建)
  │  ├─ build_imports_list(import_map) → imports           │
  │  ├─ read_soft_object_paths(archive, ...) → soft_refs   │
  │  └─ detect_circular_deps(import_map) → circular_deps   │
  │                                                         │
  ├─ ← ParseResult ◄───────────────────────────────────────┘
  │
  ├─ format routing ──► format_json_full(result, include_schema)
  │                    format_json_summary(result, include_schema)
  │                    format_text_full(result)
  │                    format_markdown(result)
  │                    format_graphs_json(result.graphs)  [--graph only]
  │
  └─ output → stdout or --output file
```

### Recommended Project Structure (新增文件)

```
src/uasset_read/
├── __init__.py           # 扩展导出：追加 parse_uasset + graph + formatters API
├── __main__.py           # NEW: python -m uasset_read 入口
├── cli.py                # NEW: CLI 入口（argparse + 格式路由 + 错误处理）
├── parse_uasset.py       # NEW: 主解析管线函数
├── constants.py          # EXISTING: 需追加 MAX_PINS_PER_NODE, START_EVENT_TYPES 等
├── archive.py            # EXISTING: FArchive
├── exceptions.py         # EXISTING
├── serializers/          # EXISTING (Phase 28)
├── models/               # EXISTING (Phase 29-30)
├── parsers/              # EXISTING (Phase 30)
├── blueprint/            # EXISTING (Phase 30)
├── graph/                # ASSUMED: Phase 31 产出（已存在但未验证）
│   ├── __init__.py
│   ├── parser.py
│   ├── node_reader.py
│   └── flow_builder.py
└── formatters/           # ASSUMED: Phase 32 产出（已存在但未验证）
    ├── __init__.py
    ├── json_formatter.py
    ├── text_formatter.py
    ├── markdown_formatter.py
    └── helpers.py
```

### Pattern 1: CLI 入口模板

**What:** 等价迁移旧版 `main()` + `create_parser()`
**When to use:** Phase 33 创建 `cli.py` 时

```python
# Source: uasset_read.py §7853-7970（等价迁移）
EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='uasset_read',
        description='Parse Unreal Engine .uasset files and output structured data'
    )
    parser.add_argument('file', help='Path to .uasset file to parse')
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--json', action='store_true', help='Output full JSON structure')
    group.add_argument('--text', action='store_true', help='Output YAML-style text (default)')
    group.add_argument('--summary', action='store_true', help='Output compact summary format')
    group.add_argument('--markdown', action='store_true', help='Output Markdown format')
    parser.add_argument('--verbose', action='store_true', help='Include extra detail fields')
    parser.add_argument('--output', metavar='FILE', help='Write output to file instead of stdout')
    parser.add_argument('--export', metavar='INDEX', type=int, help='Output only specific export by index')
    parser.add_argument('--graph', action='store_true', help='Include blueprint graph data in output')
    parser.add_argument('--schema', action='store_true', help='Include field semantic annotations (_schema)')
    return parser

def main():
    parser = create_parser()
    try:
        args = parser.parse_args()
    except SystemExit as e:
        sys.exit(EXIT_ARGUMENT_ERROR)

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    result = parse_uasset(args.file)

    if not result.is_success:
        print("Parse errors:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    # Format routing (等价迁移旧版逻辑)
    if args.graph:
        if args.json or args.verbose:
            include_schema = args.schema or args.verbose
            output_str = json.dumps(format_json_full(result, include_schema), indent=2, ensure_ascii=False)
        elif args.text:
            output_str = format_text_full(result)
        else:
            output_str = json.dumps({"graphs": format_graphs_json(result.graphs)}, indent=2, ensure_ascii=False)
    elif args.markdown:
        output_str = format_markdown(result)
    elif args.json:
        include_schema = args.schema or args.verbose
        output_str = json.dumps(format_json_full(result, include_schema), indent=2, ensure_ascii=False)
    elif args.summary:
        include_schema = args.schema or args.verbose
        output_str = json.dumps(format_json_summary(result, include_schema), indent=2, ensure_ascii=False)
    else:
        output_str = format_text_full(result)

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_str)
            print(f"Output written to {args.output}", file=sys.stderr)
        except IOError as e:
            print(f"Error writing to file: {e}", file=sys.stderr)
            sys.exit(EXIT_ARGUMENT_ERROR)
    else:
        print(output_str)

    sys.exit(EXIT_SUCCESS)
```

### Pattern 2: parse_uasset 管线组装

**What:** 等价迁移旧版 `parse_uasset()` (uasset_read.py §6223-6412)
**When to use:** Phase 33 创建 `parse_uasset.py` 时

管线步骤（按执行顺序）：
1. `FArchive(path)` — 打开二进制文件
2. `archive.get_mmap_info()` — 记录 mmap 使用情况
3. `read_package_summary(archive)` → `result.summary`
4. `read_name_table(archive, result.summary)` → `result.name_map`
5. `read_import_map(archive, result.summary, result.name_map)` → `result.import_map`
6. `read_export_map(archive, result.summary, result.name_map)` → `result.export_map`
7. **for export in export_map:** `parse_properties_from_export(...)` → `export.properties`
8. **for export with properties:** `extract_component_transforms(export.properties)` → `export.transforms`
9. **Blueprint metadata:** `find_main_blueprint_generated_class(...)` → `extract_blueprint_metadata(...)` → `result.blueprint`
10. **Blueprint graphs:** `extract_blueprint_graphs(archive, ...)` → `result.graphs`
11. **Dependency analysis:** `build_imports_list(...)`, `read_soft_object_paths(...)`, `detect_circular_deps(...)`
12. 错误处理：VersionError/ParseError/Exception → result.errors, result.is_success = False
13. finally: `archive.close()`

### Anti-Patterns to Avoid

- **不要从旧版 `uasset_read.py` 直接复制粘贴代码** — 应导入新版模块中的函数，只在 `parse_uasset.py` 中编排调用流程
- **不要在 `__init__.py` 中直接导入旧版模块** — 删除旧文件前，必须确保所有导出都来自新版模块
- **不要修改测试断言** — 只修导入路径，不修改测试逻辑（功能性修复留给 Phase 34）
- **不要在 Phase 33 添加新功能** — 等价迁移是唯一目标

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI 参数解析 | 手动解析 sys.argv | `argparse` | 旧版已使用，mutually_exclusive_group 处理复杂 |
| 退出码管理 | 硬编码数字 | 命名常量 (EXIT_*) | 可读性、可维护性 |
| 路径操作 | os.path 拼接 | `pathlib.Path` | 跨平台兼容、旧版已使用 |
| JSON 输出 | 手动字符串拼接 | `json.dumps()` | 正确处理转义、缩进、ensure_ascii |

**Key insight:** Phase 33 是"胶水层"工作——不涉及新的算法或解析逻辑，只是把已有的模块组装起来。最大的风险不是技术难度，而是遗漏依赖或导入路径错误。

## parse_uasset.py 依赖链分析

`parse_uasset.py` 需要导入的完整依赖树：

```
parse_uasset.py
├── FArchive                          → .archive (EXISTS)
├── VersionError, ParseError           → .exceptions (EXISTS)
├── read_package_summary              → .serializers (EXISTS)
├── read_name_table                   → .serializers (EXISTS)
├── read_import_map                   → .serializers (EXISTS)
├── read_export_map                   → .serializers (EXISTS)
├── parse_properties_from_export      → .parsers (EXISTS)
├── extract_component_transforms      → .blueprint (MISSING — 需在 parse_uasset.py 前或同期实现)
├── find_main_blueprint_generated_class → .serializers (MISSING — 需从旧版迁移)
├── extract_blueprint_metadata        → .blueprint (EXISTS)
├── detect_blueprint                  → .serializers (EXISTS)
├── extract_blueprint_graphs          → .graph (Phase 31 产出 — 需确认存在)
├── build_imports_list                → .serializers (EXISTS)
├── read_soft_object_paths            → .serializers (EXISTS)
├── detect_circular_deps              → .serializers (EXISTS)
└── ParseResult                       → .models (EXISTS)
```

**缺口（在 Phase 33 之前需补齐）：**
1. `extract_component_transforms` — 不在新版 `blueprint/` 模块中，需从旧版迁移
2. `find_main_blueprint_generated_class` — 不在新版 `serializers/` 模块中，需从旧版迁移
3. `extract_blueprint_graphs` — 依赖 Phase 31 完成
4. Phase 31 的 graph 模块全部函数
5. Phase 32 的 formatters 模块全部函数

**cli.py 依赖链：**
```
cli.py
├── parse_uasset                      → .parse_uasset (Phase 33 创建)
├── format_json_full                  → .formatters (Phase 32 产出)
├── format_json_summary               → .formatters (Phase 32 产出)
├── format_text_full                  → .formatters (Phase 32 产出)
├── format_markdown                   → .formatters (Phase 32 产出)
├── format_graphs_json                → .graph 或 .formatters (Phase 31/32 产出)
├── argparse, sys, json, pathlib      → stdlib
└── ParseResult                       → .models (EXISTS)
```

## 测试导入模式分析

### 测试文件分类（按导入依赖）

#### 类别 A：仅使用已在新模块中的函数（导入应自动工作）

| 测试文件 | 导入项 | 状态 |
|----------|--------|------|
| `test_loop_limits.py` | MAX_PROPERTY_COUNT, MAX_NAME_COUNT, MAX_IMPORT_COUNT, MAX_EXPORT_COUNT | 已在 __init__.py |
| `test_partial_results.py` | ErrorContext, ParseResult | 已在 __init__.py |
| `test_boundary_validation.py` | FArchive, ParseError, PackageIndex | 已在 __init__.py |
| `test_mmap_behavior.py` | FArchive, ParseError | 已在 __init__.py |

#### 类别 B：使用 parse_uasset + 已在新模块中的函数（导入应自动工作）

| 测试文件 | 导入项 | 状态 |
|----------|--------|------|
| `test_phase21_verification.py` | parse_uasset, format_json_full | parse_uasset 需迁移，format_json_full 需 Phase 32 |
| `test_phase12_blueprint_variables.py` | BlueprintVariable, FEdGraphPinType, parse_property_flags_to_labels, format_variable_type, parse_uasset | parse_property_flags_to_labels 和 format_variable_type 需从旧版迁移，parse_uasset 需迁移 |
| `test_skill_integration.py` | parse_uasset, format_json_full, format_json_summary, format_markdown | 全部需 Phase 32/33 |

#### 类别 C：使用 Phase 31/32 产物的函数（需前置 phase 完成）

| 测试文件 | 导入项 | 依赖 Phase |
|----------|--------|-----------|
| `test_graph_parsing.py` | read_ue_graph, read_ue_graph_node, read_ue_graph_pin, read_k2node_*, extract_blueprint_graphs, CONTROL_FLOW_NODES, START_EVENT_TYPES, MAX_PINS_PER_NODE, MAX_NODES_PER_GRAPH, MAX_LINKEDTO_PER_PIN | Phase 31 |
| `test_output_formatting.py` | format_json_full, format_text_full, format_json_summary, format_graphs_json, build_connections_map, build_execution_flows, FORMAT_CONFIG, _derive_node_name, format_pin_ref, build_status_info, build_graphs_summary, build_schema_info | Phase 32 |
| `test_phase14_output_formats.py` | build_status_info, build_graphs_summary, format_json_full, format_json_summary, format_markdown, build_schema_info | Phase 32 |

#### 类别 D：使用需从旧版迁移到新版但未迁移的函数

| 测试文件 | 导入项 | 需迁移位置 |
|----------|--------|-----------|
| `test_blueprint_extraction.py` | resolve_parent_class, read_ed_graph_pin_type (TYPE_CHECKING) | serializers/graph |
| `test_uasset_read.py` | CustomVersion, get_asset_class | CustomVersion 需迁移到 models 或 serializers；get_asset_class 已在 serializers |
| `test_phase13_transform.py` | VectorValue, RotatorValue, ScaleValue, parse_vector_value, parse_rotator_value, parse_scale_value, format_transform_value, extract_component_transforms | 需从旧版迁移 |
| `test_phase26_blueprint_metadata_enhancement.py` | read_blueprint_variable, CPF_EditAnywhere, CPF_EditInstanceOnly, CPF_BlueprintReadWrite, CPF_BlueprintReadOnly, CPF_Transient, CPF_SaveGame, CPF_ExposeOnSpawn | CPF 常量需从旧版迁移到 blueprints/ 或 constants |
| `test_property_parsing.py` | use_complete_type_name, read_property_tag, resolve_package_index_to_reference | 需从旧版迁移 |
| `test_dependency_analysis.py` | build_imports_list, read_soft_object_paths, detect_circular_deps | 已在 serializers ✓ |
| `test_advanced_properties.py` | _extract_struct_type_from_tag, _extract_map_types_from_tag, _extract_set_type_from_tag, _extract_enum_type_from_tag | 这些是旧版内部函数，需确认新版是否有等价物 |
| `test_exportmap_properties.py` | use_complete_type_name, read_property_tag | 需从旧版迁移 |

### 迁移缺口汇总

以下函数/常量在旧版 `uasset_read.py` 中定义，但**尚未在 `src/uasset_read/` 中实现**：

| 名称 | 旧版位置 | 应迁移到 | 测试影响 |
|------|---------|---------|---------|
| `parse_uasset` | §6223 | `parse_uasset.py` (D-06) | 多个测试 |
| `extract_component_transforms` | §1590 | `blueprint/` 或 `parse_uasset.py` | test_phase13_transform |
| `VectorValue, RotatorValue, ScaleValue` | §1435-1480 | `models/` 或 `blueprint/` | test_phase13_transform |
| `parse_vector_value, parse_rotator_value, parse_scale_value` | §1514-1588 | `blueprint/` | test_phase13_transform |
| `format_transform_value` | §1483 | `blueprint/` | test_phase13_transform |
| `find_main_blueprint_generated_class` | §3063 | `serializers/` | parse_uasset 管线 |
| `resolve_parent_class` | §3146 | `serializers/` | test_blueprint_extraction |
| `read_property_tag` | §5186 | `serializers/` | test_property_parsing, test_exportmap_properties |
| `use_complete_type_name` | §5167 | `serializers/` | test_property_parsing, test_exportmap_properties |
| `resolve_package_index_to_reference` | §991 | `serializers/` | test_property_parsing |
| `parse_default_value` | §4682 | `blueprint/` | test_blueprint_extraction (TYPE_CHECKING) |
| `read_blueprint_variable` | §4942 | `blueprint/` | test_phase26, test_blueprint_extraction (TYPE_CHECKING) |
| `parse_property_flags_to_labels` | §4807 | `blueprint/` | test_phase12 |
| `format_variable_type` | §4861 | `blueprint/` | test_phase12 |
| `CustomVersion` | §945 | `serializers/` 或 `models/` | test_uasset_read |
| CPF_* 常量 | §4744-4770 | `blueprint/` 或 `constants` | test_phase26 |
| `read_ed_graph_pin_type` | §3191 | `serializers/graph` (Phase 31) | test_blueprint_extraction (TYPE_CHECKING) |
| `_extract_struct_type_from_tag` 等 | §5521-5644 | `parsers/` 内部 | test_advanced_properties |

**注意：** `_extract_struct_type_from_tag`, `_extract_map_types_from_tag`, `_extract_set_type_from_tag`, `_extract_enum_type_from_tag` 是旧版内部辅助函数。需要检查新版 `parsers/property_types.py` 是否有等价实现。

## Common Pitfalls

### Pitfall 1: 导入循环
**What goes wrong:** `parse_uasset.py` 导入 graph/formatters，而 graph/formatters 又导入 parse_uasset，造成循环导入。
**Why it happens:** 管线模块和格式化模块之间的依赖方向不正确。
**How to avoid:** 严格遵循依赖方向：`cli → parse_uasset → (graph, formatters, parsers, blueprint) → models → serializers → archive`。parse_uasset.py 不导入 formatters，cli.py 同时导入 parse_uasset 和 formatters（cli 在顶层，不会循环）。
**Warning signs:** `ImportError: cannot import name 'parse_uasset' from partially initialized module`

### Pitfall 2: `__init__.py` 中的旧版重导出残留
**What goes wrong:** 删除旧文件后，`__init__.py` 中从旧版重导出的代码（当前可能存在的）会引发 ImportError。
**Why it happens:** 当前 `src/uasset_read/__init__.py` 没有从旧版重导出的代码（经检查），但需要在删除旧文件前再次确认。
**How to avoid:** 删除旧文件前，确认 `__init__.py` 中所有导入都来自 `.` 相对导入（即新版模块内部）。

### Pitfall 3: CPF_ 常量位值不一致
**What goes wrong:** 旧版 `uasset_read.py` 中的 CPF_ 常量位值与新版 `blueprint/variable_extractor.py` 中的位值不一致。
**Why it happens:** 旧版定义了完整的 CPF_ 常量（包括 CPF_EditAnywhere=0x02000000 等），而新版 `variable_extractor.py` 定义了简化版（CPF_Edit=0x00000001）。test_phase26 导入的是旧版的 CPF_EditAnywhere 等。
**How to avoid:** 需要确认旧版的 CPF_ 常量定义是否完整迁移到新版，或在 `__init__.py` 中重新导出。

### Pitfall 4: 测试文件中的 `create_test_uasset` 辅助函数
**What goes wrong:** `test_uasset_read.py` 有 `create_test_uasset()` 辅助函数，它直接写入二进制数据来模拟 .uasset 文件。如果新版 FArchive 或序列化函数与旧版行为不一致，这些测试会失败。
**Why it happens:** 合成数据依赖于旧版的精确二进制格式。
**How to avoid:** Phase 33 只修导入路径，不改测试逻辑。任何合成数据失败都属于 Phase 34 等价验证范围。

### Pitfall 5: Phase 31/32 未完成时的阻塞
**What goes wrong:** 开始 Phase 33 时，graph/ 和 formatters/ 模块尚未创建，导致 `parse_uasset.py` 和 `cli.py` 无法导入。
**Why it happens:** Phase 33 依赖于 Phase 31 和 32 的产出。
**How to avoid:** 在执行 Phase 33 之前，先确认 `src/uasset_read/graph/` 和 `src/uasset_read/formatters/` 目录存在且可导入。如果不存在，Phase 33 无法开始。

## Code Examples

### __main__.py（D-02）
```python
# Source: D-02 决策
from uasset_read.cli import main

if __name__ == "__main__":
    main()
```

### pyproject.toml 版本更新
```toml
# 从
version = "5.1.0"
# 改为
version = "6.0.0"
```

### __init__.py 版本和追加导出（D-09）
```python
# 版本更新
__version__ = "6.0.0"

# 追加导出（在现有导出后追加）
from .parse_uasset import parse_uasset

# Phase 31 graph 模块公共 API（假设 Phase 31 已实现）
from .graph import (
    extract_blueprint_graphs,
    build_execution_flows,
    build_data_flows,
    build_connections_map,
    # 其他 graph 公共 API...
)

# Phase 32 formatters 模块公共 API（假设 Phase 32 已实现）
from .formatters import (
    format_json_full,
    format_json_summary,
    format_text_full,
    format_text_summary,
    format_markdown,
    format_graphs_json,
    format_blueprint_dict,
    build_status_info,
    build_graphs_summary,
    build_schema_info,
    # 其他 formatters 公共 API...
)

# 追加常量（D-09）
from .constants import (
    MAX_PINS_PER_NODE,
    MAX_NODES_PER_GRAPH,
    MAX_LINKEDTO_PER_PIN,
    START_EVENT_TYPES,
    FORMAT_CONFIG,
)

# __all__ 追加（D-10：仅追加不删除）
__all__ = [
    # ... 现有的 50+ 项保持不变 ...
    # 追加：
    "parse_uasset",
    # graph
    "extract_blueprint_graphs",
    "build_execution_flows",
    "build_data_flows",
    "build_connections_map",
    # formatters
    "format_json_full",
    "format_json_summary",
    "format_text_full",
    "format_text_summary",
    "format_markdown",
    "format_graphs_json",
    "format_blueprint_dict",
    "build_status_info",
    "build_graphs_summary",
    "build_schema_info",
    # 常量
    "MAX_PINS_PER_NODE",
    "MAX_NODES_PER_GRAPH",
    "MAX_LINKEDTO_PER_PIN",
    "START_EVENT_TYPES",
    "FORMAT_CONFIG",
    "CONTROL_FLOW_NODES",
]
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 31 和 Phase 32 已完成，`graph/` 和 `formatters/` 模块存在且可导入 | 依赖链分析 | 如果未完成，Phase 33 无法开始，需先执行 31/32 |
| A2 | `src/uasset_read/__init__.py` 当前没有从旧版 `uasset_read.py` 重导出的代码 | Pitfall 2 | 如果有残留重导出，删除旧文件会导致 ImportError |
| A3 | Phase 31 会将 `extract_blueprint_graphs`、`build_execution_flows`、`build_connections_map` 等函数放在 `graph/` 模块中 | 依赖链分析 | 如果位置不同，`__init__.py` 导入路径需调整 |
| A4 | Phase 32 会将 `format_json_full`、`format_text_full` 等函数放在 `formatters/` 模块中 | 依赖链分析 | 如果位置不同，`__init__.py` 导入路径需调整 |
| A5 | `extract_component_transforms` 不在当前新版 `blueprint/` 模块中，需额外迁移 | 迁移缺口汇总 | 如果已存在，则无需迁移 |
| A6 | CPF_ 常量在 `variable_extractor.py` 中是内部使用，未被 `__init__.py` 导出 | 迁移缺口汇总 | 如果不正确，test_phase26 导入会失败 |

## Open Questions (RESOLVED)

1. **`_extract_struct_type_from_tag` 等内部函数是否已在新版 `parsers/` 中存在？** → **已确认存在**
   - `__init__.py` 第 170-173 行已从 `parsers` 导出 `_extract_struct_type_from_tag`, `_extract_map_types_from_tag`, `_extract_set_type_from_tag`, `_extract_enum_type_from_tag`
   - 这些函数已在 `parsers/property_types.py` 中实现
   - 测试依赖的辅助函数已就位，无需额外迁移

2. **`resolve_parent_class` 函数的迁移目标？** → **将在 Plan 01 Task 3 中迁移到 `serializers/object_resources.py`**
   - 旧版在 §3146 定义
   - Plan 01 步骤 C-1 已包含从 `serializers.object_resources` 导入 `resolve_parent_class`

3. **`read_property_tag` 和 `use_complete_type_name` 的迁移目标？** → **已确认部分存在**
   - `use_complete_type_name` 已在 `constants.py` 中定义并通过 `__init__.py` 第 77 行导出
   - `read_property_tag` 目前仍在 shim 中，将在 Plan 01 中通过 `parsers.property_types` 导入

4. **VectorValue/RotatorValue/ScaleValue 数据类是否已在 models 中定义？** → **不存在，需在 Plan 01 中创建**
   - 当前新版 `models/` 不导出这些类
   - Plan 01 Task 1 将创建 `models/transforms.py` 包含这些数据类

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime, CLI | ✓ | 3.10+ | — |
| pytest | Test execution | ✓ | >=7.0 | — |
| Test assets (BP_FirstPersonCharacter.uasset) | Integration tests | ✓ | UE 5.7 | — |
| `uasset-read` CLI entry | CLI usage | ✓ (in pyproject.toml, points to `uasset_read.cli:main`) | — | `python -m uasset_read` |
| `src/uasset_read/graph/` | parse_uasset.py, cli.py | ✗ (Phase 31 产出，尚未验证存在) | — | **BLOCKING — 无 fallback** |
| `src/uasset_read/formatters/` | cli.py | ✗ (Phase 32 产出，尚未验证存在) | — | **BLOCKING — 无 fallback** |

**Missing dependencies with no fallback:**
- `graph/` 模块 — 如果 Phase 31 未完成，Phase 33 无法开始
- `formatters/` 模块 — 如果 Phase 32 未完成，Phase 33 无法开始

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=7.0 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `python -m pytest tests/ -x --tb=short` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLI-01~06 | CLI 入口、参数解析、退出码 | integration | `python -m uasset_read --help` | ❌ 需创建 |
| MOD-12 | parse_uasset 管线组装 | integration | `python -c "from uasset_read import parse_uasset"` | ❌ 需创建 |
| MOD-13 | __init__.py 公共 API 完整导出 | unit | `python -c "from uasset_read import *; print(__all__)"` | ❌ 需创建 |
| TEST-01 | 18 个测试文件导入路径适配 | integration | `python -m pytest tests/ -v` | ✅ 已存在，需更新 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x --tb=short`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** 411 passed, 47 skipped, 0 failed + `python -m uasset_read <test_asset>` 成功

### Wave 0 Gaps
- [ ] `python -m uasset_read` 可运行 — 需创建 `__main__.py` 和 `cli.py`
- [ ] `from uasset_read import parse_uasset` 不从旧版重导出 — 需创建 `parse_uasset.py`
- [ ] 18 个测试文件导入路径更新 — 需逐个检查并更新

## Security Domain

> `security_enforcement` 未在 `.planning/config.json` 中显式设为 false，默认启用。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | argparse 类型验证（--export 为 int）、文件存在性检查 |
| V7 Error Handling | yes | 错误信息输出到 stderr，不泄露内部路径 |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 路径遍历 | Tampering | CLI 接受用户提供的文件路径，但仅用于读取，不执行 |
| 恶意 .uasset 文件 | Tampering | FArchive 边界验证（validate_package_index）、循环限制（MAX_PROPERTY_COUNT） |

## Sources

### Primary (HIGH confidence)
- 旧版 `uasset_read.py` — 直接源码分析（§6223-6412 parse_uasset, §7846-7970 CLI, §7973-8136 __all__）
- 新版 `src/uasset_read/__init__.py` — 当前 50+ 导出项
- 新版 `src/uasset_read/serializers/__init__.py` — 序列化函数导出
- 新版 `src/uasset_read/parsers/__init__.py` — 解析函数导出
- 新版 `src/uasset_read/blueprint/__init__.py` — 蓝图函数导出
- 新版 `src/uasset_read/models/__init__.py` — 数据模型导出
- `pyproject.toml` — CLI 入口定义、版本 5.1.0

### Secondary (MEDIUM confidence)
- 18 个测试文件 — import 模式分析（grep + 手动检查）
- Phase 31/32 CONTEXT.md — 模块结构和决策
- `.planning/ROADMAP.md` — Phase 33 目标和成功标准

### Tertiary (LOW confidence)
- Phase 31/32 的实际实现状态 — graph/ 和 formatters/ 目录尚不存在，假设会在 Phase 33 前完成

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Python stdlib，零依赖项目
- Architecture: HIGH — 旧版源码直接分析，决策已锁定
- Pitfalls: HIGH — 基于旧版结构和新模块依赖关系的推理
- 迁移缺口: MEDIUM — 基于 grep 搜索的负向声明，可能需要进一步验证

**Research date:** 2026-05-12
**Valid until:** Phase 31/32 完成前有效（依赖它们的产出）
