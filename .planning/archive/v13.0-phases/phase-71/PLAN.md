# Phase 71 — 执行流链式表达 PLAN

## Goal

将执行流输出从逐对连接 `{"from": "...", "to": "..."}` 升级为链式字符串 `"N1->N2->N3"`，作为一等公民 API 暴露，并在所有 formatter 和 consumer 中完成适配。

**Requirements:** CHAIN-01 (新 API + 标准 JSON 替换), CHAIN-02 (Consumer 适配 + 向后兼容)

## Architecture

```
n2c/flow_extractor.py (extract_chains)  ──提取/重定向──►  graph/chain_builder.py (build_execution_chains)
                                                                                         ▲
                                                                                         │
graph/flow_builder.py (build_execution_flows) ──deprecated, 内部调用──► chain_builder
                                                                                         │
format_graphs_json() / build_graphs_summary() ──execution_flows → execution_chains ────► chain_builder
```

## Tasks

### Wave 1: 核心 API — `graph/chain_builder.py`

**Goal:** 将 `n2c/flow_extractor.py` 的 `_detect_cycle()` 和 `extract_chains()` 提取到 `graph/chain_builder.py`，并新增顶层 `build_execution_chains(graph)` 函数。

**Files:**
- **Create:** `src/uasset_read/graph/chain_builder.py`
- **Rename:** `src/uasset_read/n2c/flow_extractor.py` → `src/uasset_read/n2c/chain_extractor.py`
- **Modify:** `src/uasset_read/n2c/serializer.py` — import 重定向
- **Modify:** `src/uasset_read/graph/__init__.py`, `src/uasset_read/__init__.py` — 导出符号

**Steps:**

1. 创建 `graph/chain_builder.py`，包含：
   - `_detect_cycle(adjacency)` — 从 flow_extractor 迁移 DFS 环检测
   - `_extract_chains_from_pairs(pairs, id_mapper)` — 从 flow_extractor.extract_chains 的核心逻辑迁移（pair → chain string）
   - `build_execution_chains(graph)` — 顶层 API，内部调用 `build_execution_flows()` → 构建 `N2CIdMapper` → `_extract_chains_from_pairs()` → 返回 `[{"start_event": "...", "chains": ["N1->N2"], "has_cycle": bool}]`
   - `build_execution_chains_from_flows(execution_flows, id_mapper)` — 公开 extract_chains 逻辑供 N2C serializer 直接调用

2. **重命名** `n2c/flow_extractor.py` → `n2c/chain_extractor.py`：
   - 新文件头部注释：「逻辑已迁移至 graph/chain_builder.py，本文件保留为薄封装」
   - `_detect_cycle` / `extract_chains` / `extract_data_flow_map` 改为从 `graph.chain_builder` 导入
   - 保留原函数签名作为向后兼容薄封装
   - 更新所有 `from uasset_read.n2c.flow_extractor import ...` 指向 `chain_extractor`（grep 全项目替换）

3. 更新 `n2c/serializer.py`：
   - import 从 `n2c.flow_extractor` 改为 `graph.chain_builder`

4. 更新 `graph/__init__.py` 和 `uasset_read/__init__.py`：
   - 导出 `build_execution_chains` 和 `build_execution_chains_from_flows`

### Wave 2: JSON 输出替换 — `execution_flows` → `execution_chains`

**Goal:** `format_graphs_json()` 和 `build_graphs_summary()` 输出 `execution_chains` 替代 `execution_flows`。

**Files:**
- **Modify:** `src/uasset_read/graph/flow_builder.py` — `format_graphs_json()`, `build_graphs_summary()`, `build_function_graphs()`
- **Modify:** `src/uasset_read/formatters/json_formatter.py` — `format_json_full()`

**Steps:**

1. `flow_builder.py` 中修改 `build_graphs_summary()`:
   - 调用 `build_execution_chains(graph)` 替代 `build_execution_flows(graph)`
   - 返回 dict 中 `"execution_flows"` → `"execution_chains"`
   - 添加 `"chain_metadata": {"has_cycle": bool, "branch_count": int}`

2. `flow_builder.py` 中修改 `format_graphs_json()`:
   - 同上，`"execution_flows"` → `"execution_chains"`
   - 保留 `build_execution_flows()` 函数体，添加 `warnings.warn(DeprecationWarning)`

3. `flow_builder.py` 中修改 `build_function_graphs()` (line ~1103):
   - 内嵌的 `"execution_flows": [{"start_event": ..., "nodes": ...}]` → `"execution_chains": [...]`
   - 注意：`build_function_graphs` 的 execution_flows 包含完整的 `nodes[]` 列表（含 node_type/parameters/data_providers），
     链式化时**保留 nodes 数组**，额外添加 `"chains": ["N1->N2"]` 字段作为链式视图，
     而非替换 nodes。原因：下游 consumer（如 cpp_gen）仍需节点详情。

4. `json_formatter.py` 中 `format_json_full()`:
   - 如果内部使用了 `execution_flows` 相关逻辑，更新为 `execution_chains`

### Wave 3: Consumer 适配

**Goal:** 所有 formatter 和 cpp_gen consumer 适配链式格式。

**Files:**
- **Modify:** `src/uasset_read/formatters/text_formatter.py`
- **Modify:** `src/uasset_read/formatters/markdown_formatter.py`
- **Modify:** `src/uasset_read/cpp_gen/extractors/cpp_function_body_extractor.py`
- **Modify:** `src/uasset_read/formatters/helpers.py`

**Steps:**

1. `text_formatter.py`:
   - ExecutionFlow 展示从遍历 `flow.nodes` 改为直接展示 chains 字符串
   - 格式：`      - Event.X: N1->N2->N3`

2. `markdown_formatter.py`:
   - `_build_mermaid_flowchart()` 从 chains 字符串解析生成 mermaid 边
   - 每条 chain `"N1->N2->N3"` → `N1 --> N2` + `N2 --> N3`

3. `cpp_function_body_extractor.py`:
   - **注意：** `execution_chains` 是字符串列表（`"N1->N2->N3"`），不含节点详情。
     Extractor 继续使用 `flow["nodes"]` 获取 node_type/parameters 等信息用于 C++ 翻译，
     链式字段仅用于日志/调试输出。无需实质性改动，仅需更新字段引用。

4. `helpers.py`:
   - schema info 描述从 `"函数调用链路径"` 更新为 `"链式执行流（N1->N2->N3）"`

### Wave 4: deprecated 标记

**Goal:** `build_execution_flows()` 标注 deprecated，内部回退到新 API。

**Files:**
- **Modify:** `src/uasset_read/graph/flow_builder.py` — `build_execution_flows()`

**Steps:**

1. 在 `build_execution_flows()` 函数体开头添加：
   ```python
   warnings.warn(
       "build_execution_flows() is deprecated, use build_execution_chains() instead. "
       "This function will be removed in a future version.",
       DeprecationWarning,
       stacklevel=2
   )
   ```
2. 保持返回格式不变（旧 consumer 仍可调用）

### Wave 5: 测试

**Goal:** 为新 API 编写测试，确保现有测试通过。

**Files:**
- **Create:** `tests/graph/test_chain_builder.py`
- **Modify:** 现有测试中引用 `execution_flows` 的地方

**Steps:**

1. `tests/graph/test_chain_builder.py`:
   - 测试 `build_execution_chains()` 返回格式
   - 测试线性链、分支链、环检测
   - 测试 `build_execution_chains_from_flows()` 直接调用
   - 测试 deprecated 警告触发

2. 补充测试 `build_function_graphs()` 输出的 `execution_chains` 字段：
   - 验证 nodes 数组仍然保留（不被链式字段替换）
   - 验证 chains 字符串正确生成

3. 运行全量测试，确保 0 regression

## Verification Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| CHAIN-01 | `build_execution_chains(graph)` API 可用 | import 成功，返回正确格式 |
| CHAIN-02 | JSON 输出 `execution_chains` 替代 `execution_flows` | format_json_full() 输出包含 execution_chains |
| CHAIN-03 | 所有 formatter 适配链式格式 | text/markdown/cpp_gen 测试通过 |
| CHAIN-04 | 旧 `build_execution_flows()` deprecated 但可用 | DeprecationWarning 触发，返回格式不变 |
| CHAIN-05 | N2C serializer import 重定向 | n2c/serializer.py 从 graph.chain_builder 导入 |
| CHAIN-06 | 全量测试 0 regression | pytest 全量通过 |
| CHAIN-07 | `build_function_graphs()` 输出一致 | execution_chains + nodes 同时存在 |

## Threat Model

| Threat | Impact | Mitigation |
|--------|--------|-----------|
| 现有 consumer 依赖 `execution_flows` 字段 | 输出格式变更破坏下游解析 | 旧函数保留 deprecated，新格式为 `execution_chains` 新字段名 |
| 环检测误判 | 有环蓝图丢失部分链 | has_cycle 标志 + 已提取链仍返回 |
| 分支拆分错误 | 多出口控制流连链不正确 | 每条链终止于分支点，branch_count 验证 |
