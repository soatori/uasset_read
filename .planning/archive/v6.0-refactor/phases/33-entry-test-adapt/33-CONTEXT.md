# Phase 33: 入口与测试适配 - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

## Phase Boundary

将旧版 `uasset_read.py` 的 CLI 入口和 `parse_uasset` 主函数迁移到新版 `src/uasset_read/` 模块化包，更新所有测试以适配新模块路径，删除旧版单文件。覆盖范围：
- `src/uasset_read/cli.py` — 新建 CLI 入口（argparse + 格式路由 + 错误处理）
- `src/uasset_read/__main__.py` — `python -m uasset_read` 支持
- `src/uasset_read/__init__.py` — 更新公共 API 导出（追加 graph/formatters/parse_uasset）
- 新建 `src/uasset_read/parse_uasset.py` 或等价模块 — 完整解析管线入口
- 测试适配：18 个测试文件的导入路径更新
- 删除旧版 `uasset_read.py`

**不包含：** 新功能开发、等价验证（Phase 34）、JSON Schema 定义（SCHEMA-01）。

## Implementation Decisions

### CLI 入口设计

- **D-01 (模块位置):** CLI 入口放在 `src/uasset_read/cli.py`，`pyproject.toml` 中 `uasset-read = "uasset_read.cli:main"` 已定义，保持不变。
- **D-02 (__main__.py):** 创建 `src/uasset_read/__main__.py` 支持 `python -m uasset_read`，内容为 `from uasset_read.cli import main; main()`。
- **D-03 (argparse 标志):** 等价迁移旧版 `create_parser()` 的全部标志：`file`（位置参数）、`--json/--text/--summary/--markdown`（互斥组）、`--verbose`、`--output`、`--export`、`--graph`、`--schema`。标志行为完全不变。
- **D-04 (退出码):** 等价迁移旧版退出码常量：`EXIT_SUCCESS=0`、`EXIT_PARSE_ERROR=1`、`EXIT_FILE_NOT_FOUND=2`、`EXIT_ARGUMENT_ERROR=3`。放在 `cli.py` 模块顶部。
- **D-05 (格式路由):** `main()` 中的格式路由逻辑等价迁移——根据 `args` 标志调用对应 `format_xxx()` 函数。Phase 32 已锁定格式化函数签名 `format_xxx(result: ParseResult, ...) -> Dict | str`。

### parse_uasset 主函数

- **D-06 (模块位置):** `parse_uasset` 函数放在 `src/uasset_read/parse_uasset.py`——与 formatters/graph/parsers 同级的顶层模块，因为它是整个解析管线的入口，消费所有子模块。
- **D-07 (管线流程):** 等价迁移旧版 `parse_uasset()` 的完整流程：FArchive → read_package_summary → read_name_table → read_import_map → read_export_map → parse_properties_from_export (per export) → extract_component_transforms → extract_blueprint_metadata → extract_blueprint_graphs (Phase 31) → ParseResult。
- **D-08 (错误处理):** 等价迁移 D-15 优雅降级模式——VersionError/ParseError 捕获到 result.errors，不中断解析，返回部分结果。

### __init__.py 更新

- **D-09 (导出扩展):** 在现有 `__init__.py` 基础上追加导出：
  - `parse_uasset` (from `.parse_uasset`)
  - 所有 graph 模块公共 API (from `.graph`)
  - 所有 formatters 公共 API (from `.formatters`)
  - 常量追加：`MAX_PINS_PER_NODE`, `MAX_NODES_PER_GRAPH`, `MAX_LINKEDTO_PER_PIN`, `START_EVENT_TYPES`
  - 版本更新：`__version__` 从 "5.1.0" 更新为 "6.0.0"
- **D-10 (向后兼容):** `__all__` 列表保持现有 50+ 导出项不变，仅追加不删除——直到 Phase 34 等价验证完成后才考虑清理。

### 测试适配策略

- **D-11 (导入路径更新):** 所有测试文件中的 `from uasset_read import X` 改为从 `src/uasset_read/` 的新模块路径导入。但 `parse_uasset` 和公共 API 仍通过 `from uasset_read import X` 导入（因为 `__init__.py` 会重新导出）。
- **D-12 (mock 数据):** 测试中直接引用旧版内部函数的部分（如 `from uasset_read import read_ue_graph`）需要改为从新模块路径导入，或使用 mock。
- **D-13 (已知失败):** ROADMAP.md 提到 7 个已知失败测试——Phase 33 修复这些失败的导入路径问题，功能性修复留给 Phase 34 等价验证。
- **D-14 (测试顺序):** 先跑 `pytest tests/ --tb=short` 确认基线（当前 411 passed, 47 skipped），再逐个修复失败。

### 旧文件删除时机

- **D-15 (删除时机):** 在测试全部适配并通过后再删除 `uasset_read.py`。删除前确认：(1) 所有测试通过，(2) `python -m uasset_read` 能正常解析测试资产，(3) CLI `uasset-read` 入口可用。
- **D-16 (保留引用):** 删除后 `CLAUDE.md` 中关于旧版的描述需要更新，`__init__.py` 中从旧版重导出的代码需要移除。

### Claude's Discretion

- `cli.py` 中辅助函数的精确划分（如 `_route_format()` 是否需要独立函数）由规划阶段确定
- `parse_uasset.py` 的内部结构（单函数 vs 分步骤函数）由规划阶段确定
- 测试修复的精确顺序和分组由规划阶段确定

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 旧版源码参考（迁移源）

- `uasset_read.py` §6223-6430 — `parse_uasset()` 完整解析管线
- `uasset_read.py` §7850-7888 — 退出码常量 + `create_parser()` argparse 配置
- `uasset_read.py` §7891-7970 — `main()` CLI 入口 + 格式路由
- `uasset_read.py` §7973-8060 — `__all__` 公共 API 导出列表
- `uasset_read.py` §1-30 — 顶层 import 语句（标准库依赖清单）

### 现有模块参考

- `src/uasset_read/__init__.py` — 当前公共 API 导出（50+ 项），需扩展
- `src/uasset_read/archive.py` — FArchive 类，`parse_uasset` 的底层读取器
- `src/uasset_read/serializers/package_summary.py` — `read_package_summary` 函数
- `src/uasset_read/serializers/object_resources.py` — `read_import_map`, `read_export_map`, `read_name_table`
- `src/uasset_read/parsers/property_parser.py` — `parse_properties_from_export`
- `src/uasset_read/blueprint/` — `extract_blueprint_metadata`, `extract_blueprint_variables`
- `src/uasset_read/models/result.py` — `ParseResult` dataclass
- `pyproject.toml` §34-35 — CLI 入口定义 `uasset-read = "uasset_read.cli:main"`

### 前期决策

- `.planning/phases/31-graph-parsing/31-CONTEXT.md` — D-01 至 D-09（graph 模块结构、flow builder）
- `.planning/phases/32-output-formatting/32-CONTEXT.md` — D-01 至 D-09（formatters 模块结构、格式化函数签名）
- `.planning/phases/30-property-parsing/30-CONTEXT.md` — D-01 至 D-09（parsers 模块组织）
- `.planning/phases/29-core-data-models/29-CONTEXT.md` — D-01 至 D-14（dataclass 定义）
- `.planning/ROADMAP.md` §Phase 33 — Phase 33 目标、成功标准

### 测试参考

- `tests/test_graph_parsing.py` — 图解析测试（需更新导入）
- `tests/test_output_formatting.py` — 输出格式化测试（需更新导入）
- `tests/test_property_parsing.py` — 属性解析测试（需更新导入）
- `tests/test_blueprint_extraction.py` — 蓝图提取测试（需更新导入）
- `tests/test_uasset_read.py` — 主入口测试（需大幅更新）
- 全部 18 个测试文件

## Existing Code Insights

### Reusable Assets

- **FArchive (archive.py):** 完整的二进制读取器已就位，`parse_uasset` 直接复用
- **序列化函数:** `read_package_summary`, `read_name_table`, `read_import_map`, `read_export_map` 已在 serializers/ 中实现
- **解析器:** `parse_properties_from_export` 已在 parsers/ 中实现
- **蓝图:** `extract_blueprint_metadata`, `extract_blueprint_variables` 已在 blueprint/ 中实现
- **数据模型:** 所有 dataclass（ParseResult, UEdGraph, PropertyTag 等）已在 models/ 中定义
- **退出码常量:** 旧版中已定义，需等价迁移到 cli.py

### Established Patterns

- **函数式解析:** serializers/parsers/blueprint 中已建立独立函数返回 dataclass 的模式
- **扁平导入:** 所有模块通过 `__init__.py` 统一导出
- **分层架构依赖方向:** cli → parse_uasset → (graph, formatters, parsers, blueprint) → models → serializers → archive，单向依赖
- **零运行时依赖:** pyproject.toml 中 `dependencies = []`
- **dataclass + from_archive stub → serializer 委托:** Phase 29 D-06 已锁定

### Integration Points

- `cli.py` 消费 `parse_uasset` 和所有 `format_xxx` 函数
- `parse_uasset.py` 消费 serializers/graph/parsers/blueprint 的所有公共函数
- `__init__.py` 需重新导出 parse_uasset + graph + formatters 的公共 API
- 18 个测试文件需要从旧版导入切换到新版模块路径
- `pyproject.toml` 的 CLI 入口已指向 `uasset_read.cli:main`——该模块尚不存在
- Phase 34 将消费 Phase 33 的产出进行新旧输出对比验证

## Specific Ideas

无特定要求 — 采用上述讨论的架构设计。

## Deferred Ideas

- MCP Server 封装 — 延后至 v4.x（PROJECT.md Out of Scope）
- JSON Schema 验证 — 延后至 v9.0 (Phase 48)
- `uasset-read` CLI 的额外功能（如批量处理、管道输入）— 不在等价迁移范围内

---

*Phase: 33-入口与测试适配*
*Context gathered: 2026-05-12*
