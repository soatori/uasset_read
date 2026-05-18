---
phase: 55-json-output-enhancement
plan: 01
type: execute
wave: 0
depends_on: ["53-function-execution-flow", "54-data-flow-tracking"]
files_modified:
  - src/uasset_read/graph/flow_builder.py
  - src/uasset_read/formatters/json_formatter.py
  - src/uasset_read/cli.py
  - tests/test_output_formatting.py
autonomous: true
requirements: [OUT-01, OUT-02, OUT-03]
user_setup: []

must_haves:
  truths:
    - "function_graphs 作为顶层数组出现在 JSON 输出中，与 graphs_summary 同级"
    - "每个 K2Node_FunctionEntry 对应一个独立的 function_graph 条目"
    - "每个 function_graph 包含 function_name、signature、execution_flows"
    - "execution_flows 节点内嵌 data_providers 和 data_sources 标注"
    - "不带 --function-graphs 时 output_version 为 4.0 且无 function_graphs 字段"
    - "带 --function-graphs 时 output_version 为 5.0 且包含 function_graphs 字段"
  artifacts:
    - path: "src/uasset_read/graph/flow_builder.py"
      provides: "build_function_graphs() 函数"
      contains: "def build_function_graphs"
    - path: "src/uasset_read/formatters/json_formatter.py"
      provides: "format_json_full() 增强（include_function_graphs 参数）"
      contains: "include_function_graphs"
    - path: "src/uasset_read/cli.py"
      provides: "--function-graphs CLI flag"
      contains: "--function-graphs"
    - path: "tests/test_output_formatting.py"
      provides: "function_graphs 输出结构测试"
      contains: "test_function_graphs"
  key_links:
    - from: "build_execution_flows() / build_data_flows()"
      to: "build_function_graphs()"
      via: "pin-guid-to-node lookup，复用现有 pin_lookup 模式"
      pattern: "data_flows source/target -> node pin mapping -> annotation"
    - from: "build_data_flows() output"
      to: "_annotate_node_with_data_flow()"
      via: "node_name_lookup 反向映射 — data_flows 的 formatted string (NodeName:PinName) 提取节点名，匹配 execution_flow 节点名进行分组"
      pattern: "parse source/target string, extract node name part, group by node"
    - from: "result.blueprint.functions"
      to: "build_function_graphs() signature extraction"
      via: "function_reference.member_name -> BlueprintFunction.name 匹配"
      pattern: "lookup_function_metadata(member_name, blueprint.functions)"
    - from: "format_json_full()"
      to: "cli.py main()"
      via: "include_function_graphs=True when --function-graphs flag set"
      pattern: "args.function_graphs -> format_json_full(result, include_function_graphs=True)"
---

<objective>
Phase 55: JSON 输出增强 — 顶层 function_graphs 数组

Purpose: 在 format_json_full() 中新增顶层 function_graphs 数组，按 FunctionEntry
粒度组织函数图数据（执行流链路 + 节点内嵌数据流标注），使 JSON 输出可直接翻译为
等价 C++ 函数实现。
Output: build_function_graphs() 函数 + json_formatter.py 注入 + CLI flag + 测试
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/55-json-output-enhancement/55-CONTEXT.md
@.planning/phases/55-json-output-enhancement/55-DISCUSSION-LOG.md

# 上游决策
@.planning/phases/53-function-execution-flow/53-CONTEXT.md
@.planning/phases/54-data-flow-tracking/54-CONTEXT.md

# 参考文件：Move 函数数据流
@reference/蓝图节点文本参考.md L228-340

# 核心源文件
@src/uasset_read/formatters/json_formatter.py L1-85
@src/uasset_read/graph/flow_builder.py L636-714
@src/uasset_read/cli.py
</context>

<interfaces>
From src/uasset_read/models/blueprint.py:
```python
@dataclass
class BlueprintFunction:
    name: str = ""
    return_type: str = ""
    parameters: List[FunctionParameter] = field(default_factory=list)
    function_flags: int = 0
    is_pure: bool = False
```

From src/uasset_read/models/blueprint.py:
```python
@dataclass
class FunctionParameter:
    name: str = ""
    pin_type: str = ""
    direction: str = ""  # "input" or "output"
```

From src/uasset_read/models/node_types.py:
```python
@dataclass
class K2NodeFunctionEntry(UEdGraphNode):
    function_reference: Optional[FMemberReference] = None
    extra_flags: int = 0
    b_is_editable: bool = False
```

From src/uasset_read/graph/flow_builder.py:
```python
def build_execution_flows(graph: UEdGraph) -> List[Dict]:
    """返回 [{"start_event": "...", "nodes": [...]}]"""

def build_data_flows(graph: UEdGraph, mode: str = "name") -> List[Dict]:
    """返回 [{"source": "...", "target": "..."}]"""
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: build_function_graphs() 核心函数</name>
  <files>src/uasset_read/graph/flow_builder.py</files>
  <behavior>
    - 遍历所有图，收集所有 K2Node_FunctionEntry 节点
    - 对每个 FunctionEntry，通过 function_reference.member_name 匹配 result.blueprint.functions 获取签名元数据
    - 为该 FunctionEntry 构建 execution_flows（复用 _trace_execution_from_event）
    - 对 execution_flows 中的每个节点，通过 build_data_flows 结果计算 data_providers 和 data_sources
    - 过滤空 execution_flows 的条目
  </behavior>
  <action>
在 `src/uasset_read/graph/flow_builder.py` 末尾添加 `build_function_graphs()` 函数：

```python
def build_function_graphs(
    graphs: List[UEdGraph],
    blueprint_functions: Optional[List] = None,
) -> List[Dict]:
    """构建顶层 function_graphs 数组（Phase 55）。

    每个 FunctionEntry 节点对应一个条目，包含签名、执行流和数据流内嵌标注。

    Args:
        graphs: UEdGraph 列表
        blueprint_functions: BlueprintFunction 列表（用于签名提取）

    Returns:
        List[Dict]: function_graphs 数组
    """
```

**实现步骤：**

1. 构建 `blueprint_functions` 查找字典：`{func.name: func for func in blueprint_functions or []}`

2. 遍历所有 graph.nodes，收集所有 `class_name == "K2Node_FunctionEntry"` 节点

3. 对每个 FunctionEntry 节点：
   a. 提取 `function_name` 从 `function_reference.member_name`
   b. 查找 `blueprint_functions` 字典获取签名：
      - `return_type`: BlueprintFunction.return_type
      - `parameters`: [{"name": p.name, "type": p.param_type, "direction": "input" if p.is_input else "output"} for p in func.parameters]
   c. 调用 `_trace_execution_from_event(function_entry_node, pin_lookup, node_lookup)` 获取执行流节点列表
   d. 如果执行流为空，跳过该 FunctionEntry
   e. 对每个执行流节点，通过 `build_data_flows(graph)` 计算内嵌标注：
      - 节点的 input non-exec pins 作为 data_flows target → 找到 source 节点 → data_providers
      - 节点的 output non-exec pins 作为 data_flows source → 找到 target 节点 → data_sources
   f. 构建条目：
      ```json
      {
        "function_name": "Move",
        "graph_source": "UberGraph",
        "entry_node_guid": "...",
        "signature": {"return_type": "void", "parameters": [...]},
        "execution_flows": [{
          "start_event": "FunctionEntry.Move",
          "nodes": [{"node_name": "...", "pure": true, "data_providers": [...], "data_sources": [...]}]
        }]
      }
      ```

4. 返回所有非空条目列表

**注意：** 数据流标注逻辑创建内部辅助函数 `_annotate_node_with_data_flow(node, data_flows, node_name_lookup)` 保持 `_trace_execution_from_event()` 不变，确保向后兼容。
  </action>
  <verify>
    <automated>python -c "from uasset_read.graph.flow_builder import build_function_graphs; print('OK')"</automated>
  </verify>
  <done>build_function_graphs 函数可导入，不报语法或导入错误</done>
</task>

<task type="auto">
  <name>Task 2: JSON 输出注入</name>
  <files>src/uasset_read/formatters/json_formatter.py</files>
  <behavior>
    - format_json_full() 增加 include_function_graphs 参数
    - 当 include_function_graphs=True 时，调用 build_function_graphs() 并注入顶层
    - output_version 条件化为 "5.0"
    - 当 include_function_graphs=False 时，保持 "4.0" 且无 function_graphs 字段
  </behavior>
  <action>
修改 `src/uasset_read/formatters/json_formatter.py` 的 `format_json_full()` 函数：

1. 函数签名增加参数：`include_function_graphs: bool = False`

2. 在 output dict 构建逻辑中：
   - 计算 `output_version = "5.0" if include_function_graphs else "4.0"`
   - 如果 `include_function_graphs=True` 且 `result.graphs` 非空：
     - `from uasset_read.graph.flow_builder import build_function_graphs`
     - 获取 blueprint_functions: `result.blueprint.functions if result.blueprint else None`
     - 调用 `build_function_graphs(result.graphs, blueprint_functions)`
     - 添加到 output: `"function_graphs": [...]`
   - 否则不添加 function_graphs 字段

3. 更新函数 docstring 反映新参数

保持其他字段不变。
  </action>
  <verify>
    <automated>python -c "from uasset_read.formatters.json_formatter import format_json_full; import inspect; sig = inspect.signature(format_json_full); assert 'include_function_graphs' in sig.parameters; print('OK')"</automated>
  </verify>
  <done>format_json_full 接受 include_function_graphs 参数，调用时不报错</done>
</task>

<task type="auto">
  <name>Task 3: CLI --function-graphs flag</name>
  <files>src/uasset_read/cli.py</files>
  <behavior>
    - 新增 --function-graphs flag
    - 当设置时，传递 include_function_graphs=True 到 format_json_full()
    - 如果用户只指定 --function-graphs（无 --json/--text/--summary），自动隐含 --json
  </behavior>
  <action>
修改 `src/uasset_read/cli.py`：

1. 在 create_parser() 中添加 flag（非互斥组，在互斥组之后）：
   ```python
   parser.add_argument('--function-graphs', action='store_true',
                       help='Include top-level function_graphs array in JSON output (output_version 5.0)')
   ```

2. 在 main() 的格式路由中：
   - 在 `--graph` 检查之前，添加 `--function-graphs` 隐含 `--json` 的逻辑：
     ```python
     if args.function_graphs and not (args.json or args.text or args.summary or args.markdown):
         args.json = True  # 隐含 JSON
     ```
   - 在调用 `format_json_full()` 的地方（--graph + --json 和 --json 分支），传递：
     ```python
     include_function_graphs=args.function_graphs
     ```

3. 注意：`format_json_summary` 和 `format_text_full` 不传递该参数（function_graphs 仅 full JSON 模式支持）
  </action>
  <verify>
    <automated>python -m uasset_read --help | grep "function-graphs"</automated>
  </verify>
  <done>--function-graphs 出现在帮助输出中，与 --json 组合使用不报错</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: 单元测试</name>
  <files>tests/test_output_formatting.py</files>
  <behavior>
    - 测试 function_graphs 出现在顶层位置
    - 测试每个 FunctionEntry 对应独立条目
    - 测试 signature 正确提取
    - 测试 data_providers/data_sources 内嵌标注
    - 测试 output_version 4.0/5.0 条件化
    - 测试空流过滤
  </behavior>
  <action>
在 `tests/test_output_formatting.py` 中添加 function_graphs 测试。

复用 Phase 54 的 `sample_function_graph_with_data_flow` fixture（包含 FunctionEntry 节点）。

**测试函数：**

1. `test_function_graphs_top_level(result_with_graphs)` — 验证 function_graphs 在顶层 key 中，不在 blueprint 内
   - 调用 format_json_full(result, include_function_graphs=True)
   - 断言 "function_graphs" in output
   - 断言 "function_graphs" not in output.get("blueprint", {})

2. `test_function_graphs_per_entry(result_with_graphs)` — 验证 FunctionEntry 粒度
   - 如果有 1 个 FunctionEntry，assert len(output["function_graphs"]) == 1
   - 每个条目有 function_name 字段

3. `test_function_graphs_signature(result_with_graphs)` — 验证签名提取
   - 断言每个 function_graph 有 signature 对象
   - signature 有 return_type 和 parameters 字段

4. `test_function_graphs_data_providers(result_with_graphs)` — 验证数据流标注
   - 找到非纯执行节点
   - 断言有 data_providers 或 data_sources 字段

5. `test_output_version_4_without_flag(result_with_graphs)` — 无 flag 时 version 4.0
   - format_json_full(result, include_function_graphs=False)
   - assert output["output_version"] == "4.0"
   - assert "function_graphs" not in output

6. `test_output_version_5_with_flag(result_with_graphs)` — 有 flag 时 version 5.0
   - format_json_full(result, include_function_graphs=True)
   - assert output["output_version"] == "5.0"
   - assert "function_graphs" in output

7. `test_function_graphs_empty_filtered(result_no_function_entry)` — 空流过滤
   - 使用不含 FunctionEntry 的图
   - format_json_full(result, include_function_graphs=True)
   - assert output.get("function_graphs") == [] 或不存在

**fixture 补充：** 如果现有 fixture 没有 FunctionEntry，在 conftest.py 或测试文件中创建简易 mock。
  </action>
  <verify>
    <automated>python -m pytest tests/test_output_formatting.py -k "function_graphs or output_version" --collect-only | grep -c "test_"</automated>
  </verify>
  <done>至少 7 个 function_graphs 相关测试被 pytest 收集，能运行（skip/pass 均可）</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CLI flag → format_json_full | 用户输入控制，仅布尔值，无注入风险 |
| blueprint.functions → signature | 内部数据，已由 Phase 26 解析验证 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-55-SC | Tampering | function_graphs output | accept | 纯输出格式化，无外部输入执行 |
</threat_model>

<verification>
- build_function_graphs 可从 uasset_read.graph.flow_builder 导入
- format_json_full 接受 include_function_graphs 参数
- CLI --function-graphs flag 出现在帮助中
- 至少 7 个相关测试被 pytest 收集
</verification>

<success_criteria>
- `build_function_graphs()` 在 flow_builder.py 中实现
- `format_json_full()` 支持 include_function_graphs 参数
- CLI 支持 --function-graphs flag
- 不带 flag 时 output_version 为 "4.0" 且无 function_graphs
- 带 flag 时 output_version 为 "5.0" 且包含 function_graphs 顶层数组
- 每个 FunctionEntry 对应一个 function_graph 条目
- 执行流节点包含 data_providers 和 data_sources 内嵌标注
- 所有测试通过
</success_criteria>

<output>
完成后创建 `.planning/phases/55-json-output-enhancement/55-SUMMARY.md`
</output>
