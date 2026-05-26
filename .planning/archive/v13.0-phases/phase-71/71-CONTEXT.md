# Phase 71 — 执行流链式表达

## 来源
Phase 70（N2CStruct JSON Schema）已在 `n2c/` 内部实现链式提取（`extract_chains`），但仅在 N2C 输出中可用。
Phase 71 将链式表达从 N2C 内部提取为**一等公民 API**，并替代现有的 pair 格式。

<domain>
## Domain Boundary

将执行流输出从逐对连接 `{"from": "...", "to": "..."}` 升级为链式字符串 `"N1->N2->N3"`。

**交付：**
1. `build_execution_chains()` 独立 API（`graph/chain_builder.py`）
2. `format_graphs_json()` / `build_graphs_summary()` 输出格式从 `execution_flows` → `execution_chains`
3. 所有 formatter（text/markdown）和 cpp_gen consumer 适配链式格式
4. 旧 `build_execution_flows()` 标注 deprecated，内部回退到新 API 保持向后兼容

**不包含：** N2CStruct schema 改动（Phase 70 已交付）、数据流链式化（仅执行流）
</domain>

<decisions>
## Implementation Decisions

### 输出格式替换（D-01）
- `build_execution_flows()` 返回的 pair 格式将被 `build_execution_chains()` 的链式格式替代
- JSON 输出字段名从 `execution_flows` 改为 `execution_chains`
- 旧 `build_execution_flows()` 保留并标注 deprecated，内部调用 `build_execution_chains()` + pair 回退转换
- Phase 内一次性替换所有 consumer，下版本移除 deprecated 函数

### 新 API 设计（D-02）
- 新增 `graph/chain_builder.py` 模块，提供 `build_execution_chains(graph)` 函数
- 返回格式：`[{"start_event": "...", "chains": ["N1->N2->N3", "N1->N4"], "has_cycle": bool}]`
- `has_cycle` 标志告知 consumer 是否有环（环情况下 chains 可能不完整）

### 分支处理（D-03）
- Branch/Sequence 等多出口控制流节点：每条链终止于分支点
- Branch 节点拆分为多条链：`N1->N2`（True）、`N1->N3`（False）
- 不复用 N2C 的 `_format: pairs` 回退 — 有环时直接返回已提取的链 + `has_cycle: true`

### 模块归属（D-04）
- `extract_chains()` 从 `n2c/flow_extractor.py` 提取到 `graph/chain_builder.py` 作为通用函数
- N2C serializer 改为导入 `graph.chain_builder`，不再自包含链提取逻辑
- `n2c/flow_extractor.py` 重命名为 `n2c/chain_extractor.py` 并保留为 chain_builder 的薄封装（向后兼容）

### JSON 输出结构（D-05）
- `format_graphs_json()`: 每个 graph dict 中 `"execution_flows"` → `"execution_chains"`（链式字符串列表）
- `build_graphs_summary()`: 同上，`"execution_chains"` 替代 `"execution_flows"`
- 新增 `"chain_metadata": {"has_cycle": bool, "branch_count": int}` 可选字段

### Consumer 适配（D-06）
- `formatters/text_formatter.py`: 链式字符串直接展示，替代逐对遍历
- `formatters/markdown_formatter.py`: `_build_mermaid_flowchart()` 从 pair 遍历改为链解析
- `cpp_gen/extractors/cpp_function_body_extractor.py`: 链式格式下节点顺序天然有序，简化遍历
- `formatters/helpers.py`: schema 描述更新

### 向后兼容（D-07）
- `build_execution_flows()` deprecated 但保持原有返回格式不变
- `n2c/serializer.py` 在 Phase 内暂时保持 `extract_chains()` 调用不变（逻辑已移至 chain_builder，通过 import 重定向）
- `from uasset_read import build_execution_flows` 公共 API 保留

## Claude's Discretion
- 新 API 函数的具体参数设计（是否支持 Knot 穿透配置、最大链长限制）由实现者判断
- deprecated 警告的具体格式（DeprecationWarning vs logging.warning）由实现者判断
- `chain_metadata` 中除 `has_cycle`/`branch_count` 外的额外元数据字段由实现者判断
</decisions>

<canonical_refs>
## Canonical References

### 现有实现（需读取/复用/迁移）
- `src/uasset_read/n2c/flow_extractor.py` — `extract_chains()` / `extract_data_flow_map()` / `_detect_cycle()`（链提取核心算法，需提取到 graph/）
- `src/uasset_read/n2c/serializer.py` — `to_n2c_json()` 中 `extract_chains()` 调用（需更新 import）
- `src/uasset_read/n2c/id_mapper.py` — `N2CIdMapper`（GUID → 短 ID 映射）
- `src/uasset_read/graph/flow_builder.py` — `build_execution_flows()` / `_trace_execution_from_event()` / `format_graphs_json()` / `build_graphs_summary()`（consumer 和旧 API）

### Consumer 需适配
- `src/uasset_read/formatters/text_formatter.py` — 调用 `build_execution_flows()` 展示执行流
- `src/uasset_read/formatters/markdown_formatter.py` — `_build_mermaid_flowchart()` 从 pair 格式读取
- `src/uasset_read/formatters/helpers.py` — schema info 中 `execution_flows` 描述
- `src/uasset_read/cpp_gen/extractors/cpp_function_body_extractor.py` — 从 execution_flows 生成 C++ 函数体

### 公共 API
- `src/uasset_read/__init__.py` — 导出符号（需新增 `build_execution_chains`）
- `src/uasset_read/graph/__init__.py` — 导出符号（需新增 `build_execution_chains`）

### 项目参考
- `.planning/ROADMAP.md` — v12.0 路线图，Phase 71 定义
- `.planning/STATE.md` — v12.0 里程碑状态
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`extract_chains()`**（`n2c/flow_extractor.py`）— 链提取核心算法：pair → adjacency → cycle detection → chain string。Phase 71 提取到 `graph/` 后直接复用。
- **`N2CIdMapper`**（`n2c/id_mapper.py`）— GUID → 短 ID 映射，支持 register/to_short。Phase 71 复用。
- **`_detect_cycle()`**（`n2c/flow_extractor.py`）— DFS 环检测。Phase 71 复用。
- **`_trace_execution_from_event()`**（`graph/flow_builder.py`）— 执行流追踪，产生 pair 格式。Phase 71 的新 API 可直接调用它作为输入源。

### Consumer Impact（需适配的文件）
| Consumer | 当前行为 | 适配动作 |
|----------|---------|---------|
| `text_formatter.py` | 遍历 `execution_flows[0].nodes` 逐对展示 | 直接展示 chains 字符串列表 |
| `markdown_formatter.py` | `_build_mermaid_flowchart()` 逐对生成 `A --> B` | 解析 chains 字符串生成 mermaid 节点+边 |
| `cpp_function_body_extractor.py` | 遍历 `flow.nodes` 按顺序提取 C++ | chains 天然有序，简化遍历逻辑 |
| `n2c/serializer.py` | 导入 `extract_chains` 从 `n2c/flow_extractor` | 改为导入 `graph/chain_builder` |

### Established Patterns
- **graph/ 模块组织** — `flow_builder.py` 已有 `build_*` 函数族（`build_execution_flows`, `build_data_flows`, `build_connections_map`）。新 `build_execution_chains` 应遵循相同命名和签名模式。
- **deprecated 策略** — 现有代码无 deprecated 先例，建议使用 `warnings.warn()` + `DeprecationWarning`。
- **零运行时依赖** — 不引入新依赖。
</code_context>

<deferred>
## Deferred Ideas

- 数据流也采用链式表达（当前只做执行流）
- Knot 节点穿透追踪（`_resolve_knot_chain` 已有基础，但非本 phase 重点）
- 链式表达的可视化增强（Mermaid 以外的渲染方式）
</deferred>

---

*Phase: 71-执行流链式表达*
*Context gathered: 2026-05-22*
