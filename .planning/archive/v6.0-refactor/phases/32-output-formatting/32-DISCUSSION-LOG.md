# Phase 32: 输出格式化模块 - Discussion Log

**Date:** 2026-05-12
**Mode:** --batch

## Discussion Summary

### Gray Area 1: 输出格式兼容性策略

**Question:** 旧版 `format_json_full` 中的历史遗留字段（`imports`、`soft_references`、`circular_deps`）是否保持完全一致？

**Decision:** 允许清理冗余历史字段。这些依赖分析的字段不属于格式化模块的核心职责，可移除。核心输出结构（status, output_version, summary, exports, blueprint, graphs_summary, errors）必须保持一致。

### Gray Area 2: CLI 入口归属

**Question:** Phase 32 的格式化模块是否应包含格式路由辅助函数，还是纯粹只做格式化？

**Decision:** 由 Phase 33 处理 CLI。Phase 32 只提供纯格式化函数，接口约定为 `format_xxx(result: ParseResult, ...) -> Dict | str`。

### Gray Area 3: Mermaid 生成方式

**Question:** Markdown 中的 Mermaid 流程图是否抽成独立的 mermaid 构建函数？

**Decision:** 独立函数 `_build_mermaid_flowchart(execution_flows)`，放在 helpers.py 或 markdown_formatter.py 中。逻辑不变，等价迁移。

### Gray Area 4: Schema 信息处理

**Question:** `build_schema_info()` 简易 schema 是迁移还是预留正式 Schema 扩展点？

**Decision:** 简易版本迁移，预留 `formatters/schemas/` 空目录为后续正式 JSON Schema 定义扩展点。

---

*All 4 gray areas discussed and resolved.*
