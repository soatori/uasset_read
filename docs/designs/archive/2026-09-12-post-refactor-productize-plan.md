# Post-Refactor Productize Plan（合并总调度）

> **ARCHIVED (2026-09-26):** Executed closeout / plan-of-record. Historical evidence only — do not re-execute. Binding contracts and the canonical target remain under [`docs/designs/`](../README.md).


> **Status:** current（Wave A 已执行于 `docs/productize-unversioned`；Wave B P0–P8 及二次审查加固已执行；本文仅作完成记录与交接索引）
> **合并决策:** 减法优先——先完整落地 [`2026-09-12-ponytail-evaluation-fix-plan.md`](2026-09-12-ponytail-evaluation-fix-plan.md)（Wave A），再在减法后的树上执行本文 Wave B。  
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 在零行为争议的前提下完成两段工作：(A) 逐项复核过的 ponytail 减法 + 两个真实缺陷修复；(B) 在减法后的代码上，用**现有样本**补上真正可交付的蓝图语义投影与 unversioned 做通。**不采购样本。**

**Architecture:**  
- Wave A 不改公共 JSON（decode 哈希逐字节闸门），只删只写字段/死链/死支。  
- Wave B **不恢复** Wave A 删除的 K2Node 二进制 reader / `FMemberReference` reader / pin 写字段；语义只来自减法后仍存活的 `raw_properties`（tagged）与 pin 拓扑。  
- Unversioned 仅用 `BP_UnversionedTest` / `DA_UnversionedTest` + `UnversionedTest.usmap`。

**Tech Stack:** Python 3.10+（阻断 Win + 3.14）、pytest、ruff、零运行时依赖。

**Spec:**
- 减法规格：`docs/designs/2026-09-12-ponytail-evaluation-fix-plan.md` **附录 C** + 附录 A 重写义务
- 权威目标：`docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`
- 契约：`docs/designs/2026-08-31-v2-contract-stability.md`（semantic experimental）

## Global Constraints（两段共同）

- `$env:PYTHONPATH="E:/Develop/uasset_read/src"`；`python -m pytest -q` 为阻断门禁。
- 零运行时依赖；只读解析器；临时物只进 `temp/`（不提交）。
- 代码/注释/提交英文；`refactor:` / `fix:` / `feat:` / `test:` / `docs:`；**不 push**。
- 不碰 `external/`、`UnrealEngine/`、`dist/`、`build/`。
- **Wave A 附加：** 顺序读取器的 `archive.read_*()` 不得删（游标）；源码文本锚点 `# 5 Node type readers` / `MulticastInlineDelegateProperty` 计数必须保留；`fixture_gaps` **留给 Wave B**。
- **Wave B 附加：** 不恢复 Wave A 已删符号；semantic 增键不 bump `format_version`；禁止 skip/xfail 伪装。

## Explicit Non-Goals（两段共同）

| 禁止 | 原因 |
| --- | --- |
| 采购 Zen / cooked-unversioned 样本 | 用户指令 |
| ZenPackageReader、Pak 全量产品路径 | 缺 body / 另计划 |
| parent-asset、C++ skeleton、伪码、Semantic 1.x、jmap、文件日志 | Gate G/K/L 已剔除 |
| 恢复 `read_k2node_*` 分派链或 `_read_member_reference_from_tags` | Wave A 已删且证实输出无关 |
| 同时执行 A、B 或未 rebase 就写 B | 必冲突 |

## Execution Order

```text
Wave A（权威：ponytail-evaluation-fix-plan.md）
  T1  parity oracle + ruff CI 恢复绿
  T2  删 K2Node node_data 分派链（411 行）【与旧 B1/B2/B5 冲突】
  T3  删 pin/graph 只写字段【钉死 pin key set】
  T4  删 export/import 标志、PropertyTag 只写字段
  T5  graph_pin/graph_helpers 死链
  T6–T14  parsers/kismet/mappings/iostore/测试树/配置
  T15 _run_cases 重构（需设计修订授权）
  T16 decode 静默丢 Kismet 函数体（正确性缺陷）
       ↓ 闸门：pytest 绿 + decode 哈希相同 + ruff 绿
Wave B（本文，基于减法后树重写后的任务）
  P0  确认减法后基线（parity 重录为「新 golden」）
  P1  state_count（subgraph_references 仍活）
  P2  exec 边摘要（pin category=exec + linked）
  P3  节点展示名修正（_export_object_name 已删 → 用 export 名策略见 P3）
  P4  raw_properties 投影为有限 node_data（禁止恢复二进制 reader）
  P5  VariableGet/Set 语义：仅从 raw_properties / tags
  P6  Unversioned 现有样本做通
  P7  manifest fixture_gaps + README 诚实化
  P8  体积棘轮收口
```

---

# Wave A — 减法与缺陷修复（执行细节见 ponytail 原文）

**Do not execute from this file.** 打开并按序执行：

[`docs/designs/2026-09-12-ponytail-evaluation-fix-plan.md`](2026-09-12-ponytail-evaluation-fix-plan.md)

本文件只固定 **合并后的义务**（与原文一致，便于总览）：

| A-Task | 摘要 | 与旧产品化计划冲突 |
| --- | --- | --- |
| T1 | `temp/decode_parity.py` + 删 ruff 红灯 4 行 | 无 |
| T2 | 删 K2Node 分派链 / `read_fmember_reference` / `_read_member_reference_from_tags` | **废止** 旧 B Task 1/2/5 的「接进投影」 |
| T3 | 删 pin/`FEdGraphPinType` 写字段；**先钉** `test_decode_pin_payload_key_set_is_frozen` | **废止** 旧 B 的 default_value/subcategory/hidden |
| T4–T14 | 标志/属性标签/schema 表/soft-path/kismet 写字段/mappings/iostore/测试/配置 | 无（B 的 unversioned 仍可用 usmap） |
| T15 | `_run_cases` → 原生收集 | 需授权 |
| T16 | decode 丢函数体修复 | **应先于 B**（B 的 Kismet 语义依赖 decode 单调） |

Wave A 完成定义：

- [x] `python -m pytest -q` 绿（与 T1.3 同一通过集，允许 T13/T15 的用例数变化但零失败）
- [x] 触碰读路径的任务 `python temp/decode_parity.py check` 逐字节相同
- [x] `python -m ruff check src/uasset_read tests/` PASS
- [x] 每 A-Task 收紧 `tests/size-baseline.json`（T15 授权项除外）

---

# Wave B — 产品化（减法后重写；附录 A 合规）

> 下列任务 **禁止** 在 Wave A 未合并时执行。执行者应先 `git pull`/rebase 到含 A 的树。

## Wave B 前提：减法后仍存活的语义源

| 源 | 状态 | B 用途 |
| --- | --- | --- |
| `node.node_data`（Anim `subgraph_references`） | **保留**（A T2 明确保留 `_handle_full_context`） | P1 state_count |
| `pin.category` + `pin.linked` | **保留** | P2 exec 边 |
| `pin.id/name/direction/category/linked` 五键 | **冻结**（A T3 契约钉） | 禁止加 default/subcategory |
| `raw_properties`（script serial tags） | **保留**（A T2 活键） | P4/P5 唯一节点语义源 |
| `read_k2node_call_function` / `FMemberReference` readers | **已删** | 不得恢复 |
| `UEdGraphPin.default_value` 等 17 字段 | **已删** | 不得恢复 |
| usmap / unversioned fixtures | **未删** | P6 |

---

### Task P0: 减法后基线与 parity 重录

**Files:**
- Create: `temp/parity-baseline.json`（gitignored，**覆盖** A 波使用的哈希）
- Test: 无新生产代码

**Interfaces:**
- Produces: Wave B 自己的「减法后输出」基准；此后 B 的「行为变更」任务允许 **有意** 偏离，但必须在提交信息写明 diff 面。

- [x] **Step P0.1: 确认树含 Wave A 全部提交**

```powershell
git log --oneline -20
python -m pytest -q
python -m ruff check src/uasset_read tests/
```

- [x] **Step P0.2: 重录 decode 哈希（B 的起点）**

```powershell
$env:PYTHONPATH="E:/Develop/uasset_read/src"
python temp/decode_parity.py record
```

Expected: `recorded 66 fixtures`。若脚本已被 A 删除，按 A T1 原文重建。

- [x] **Step P0.3: Commit**  
无需（temp 不提交）。在 `temp/` 留 `wave-b-start.txt` 记录 SHA 即可。

---

### Task P1: 修正 `state_count`（存活路径）

**Files:**
- Modify: `src/uasset_read/parsers/asset_types/handlers_impl.py`（`_extract_state_machines`）
- Test: `tests/test_blueprint_decode.py`

**Interfaces:**
- Consumes: 投影节点 dict 上的 `node_data.subgraph_references`（由 `blueprint_graph` 序列化自 `UEdGraphNode.node_data`）
- Produces: `state_machines[].state_count` = 带该引用的节点数；**禁止**回落为 `node_count`

**前提核查：** A 后 `blueprint_graph._convert_nodes` 是否仍丢 `node.data`。若是，本任务必须 **同时** 在投影层写出 `node_data`（仅 Anim 子集）：

```python
def _anim_node_data(node: Any) -> dict[str, Any] | None:
    nd = getattr(node, "node_data", None)
    if not isinstance(nd, dict):
        return None
    refs = nd.get("subgraph_references")
    if not refs:
        return None
    # only package_index ints survive; keep dict small
    compact = {}
    for key, info in refs.items():
        if isinstance(info, dict) and isinstance(info.get("package_index"), int):
            compact[str(key)] = info["package_index"]
    return {"subgraph_references": compact} if compact else None
```

在 `_convert_nodes` 的节点 dict 中写入 `"node_data": _anim_node_data(node)`（可为 `None` 则省略键）。

- [x] **Step P1.1: 失败测试**

```python
def test_state_machine_state_count_not_node_count():
    from uasset_read import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document("tests/samples/ALS_AnimBP.uasset", depth="decode", tolerant=True)
    page = project_document(doc, depth="decode", max_bytes=4_000_000)
    machines = []
    for o in page.get("objects") or []:
        machines.extend((o.get("semantic") or {}).get("state_machines") or [])
    assert machines
    for sm in machines:
        assert sm["state_count"] <= sm["node_count"]
        if sm["node_count"] > 20:
            assert sm["state_count"] < sm["node_count"], sm
```

- [x] **Step P1.2: RED → 实现**

```python
states = sum(
    1 for n in nodes if (n.get("node_data") or {}).get("subgraph_references")
)
# drop: states if states else node_count
```

- [x] **Step P1.3: GREEN + parity（decode 有意变更）**

```bash
python -m pytest tests/test_blueprint_decode.py -v
python -m pytest -q
python -m ruff check src/uasset_read tests/
```

Record expected decode hash change on ALS fixtures only（提交信息写明）。

- [x] **Step P1.4: Commit**

```bash
git add src/uasset_read/serializers/blueprint_graph.py src/uasset_read/parsers/asset_types/handlers_impl.py tests/test_blueprint_decode.py
git commit -m "fix: count anim state machine states from subgraph_references instead of node_count"
```

---

### Task P2: exec 边摘要

**Files:**
- Modify: `src/uasset_read/serializers/blueprint_graph.py`
- Modify: `src/uasset_read/parsers/asset_types/handlers_impl.py`
- Test: `tests/test_blueprint_decode.py`

**Interfaces:**
- Consumes: 五键 pin 上的 `category` 与 `linked`
- Produces: `semantic.exec_chains = [{graph, edges:[{from_node,from_pin,to_node,to_pin}]}]`（experimental）

- [x] **Step P2.1: 失败测试**

```python
def test_exec_edges_available_for_event_graph():
    from uasset_read import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(
        "tests/samples/StackOBot_BP_Drone.uasset", depth="decode", tolerant=True
    )
    page = project_document(doc, depth="decode", max_bytes=2_000_000)
    chains = []
    for o in page.get("objects") or []:
        chains.extend((o.get("semantic") or {}).get("exec_chains") or [])
    assert chains and any(c.get("edges") for c in chains)
```

- [x] **Step P2.2: 实现 `summarize_exec_edges`**

```python
def summarize_exec_edges(graphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for graph in graphs:
        edges = []
        for node in graph.get("nodes") or []:
            for pin in node.get("pins") or []:
                if (pin.get("category") or "") != "exec":
                    continue
                for link in pin.get("linked") or []:
                    edges.append(
                        {
                            "from_node": node.get("id"),
                            "from_pin": pin.get("name"),
                            "to_node": link.get("to_node"),
                            "to_pin": link.get("to_pin"),
                        }
                    )
        if edges:
            out.append({"graph": graph.get("name"), "edges": edges})
    return out
```

Handler 在 graphs 就绪后：`result["exec_chains"] = summarize_exec_edges(graphs)`（无则空列表省略键）。

- [x] **Step P2.3: GREEN + ruff + Commit**

```bash
git add src/uasset_read/serializers/blueprint_graph.py src/uasset_read/parsers/asset_types/handlers_impl.py tests/test_blueprint_decode.py
git commit -m "feat: expose exec-pin edge chains in blueprint semantic output"
```

---

### Task P3: 节点展示名（不再使用 `_export_object_name`）

**Files:**
- Modify: `src/uasset_read/serializers/blueprint_graph.py`（`_convert_nodes`）
- Test: `tests/test_blueprint_decode.py`

**Interfaces:**
- Produces: 节点 `name` = export 对象名；A T3 已删 dataclass 字段，用 **reader 侧仍写入的可用信息**（`node` 构造时的 object name 若仅存在于 `graph.nodes` 循环外——以减法后源码为准）。
- 若减法后节点上无对象名可读：用 `id`（`export:N`）并 **不要** 再写 graph 名冒充节点名（当前 bug）；测试断言 `name` 不恒等于 `graph.name`（当 node_count>1）。

- [x] **Step P3.1: 失败测试**

```python
def test_node_name_is_not_graph_name_for_multi_node_graphs():
    from uasset_read import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(
        "tests/samples/StackOBot_BP_Drone.uasset", depth="decode", tolerant=True
    )
    page = project_document(doc, depth="decode", max_bytes=2_000_000)
    for o in page.get("objects") or []:
        for g in (o.get("semantic") or {}).get("graphs") or []:
            nodes = g.get("nodes") or []
            if len(nodes) <= 1:
                continue
            assert any(n.get("name") != g.get("name") for n in nodes)
```

- [x] **Step P3.2: 实现（按减法后可读字段）**  
优先：`getattr(node, "_export_object_name", None)`——若 A T3 已删，则在 `read_ue_graph_node` / `graph.py` 构造时 **只写投影 dict、不写 dataclass 字段**（允许在 `_convert_nodes` 使用 `node.class_name` + 短 id 作为兜底显示名）。

禁止为了好看而恢复 A T3 删除的 dataclass 字段。

- [x] **Step P3.3: GREEN + Commit**

```bash
git add src/uasset_read/serializers/blueprint_graph.py tests/test_blueprint_decode.py
git commit -m "fix: stop labeling every blueprint node with its graph name"
```

---

### Task P4: 从 `raw_properties` 投影有限 `node_data`（不恢复 K2Node reader）

**Files:**
- Modify: `src/uasset_read/serializers/blueprint_graph.py`
- Test: `tests/test_blueprint_decode.py`

**Interfaces:**
- Consumes: `UEdGraphNode.node_data` 减法后仅剩的 **dict**（来自 raw tags / Anim full_context）
- Produces: 节点 `node_data`：白名单键 + 原语值；dataclass/对象 → 不出现
- **禁止** import 已删的 `read_k2node_*` / `FMemberReference`

**白名单（初始，可评审扩大）：**

```python
_NODE_DATA_ALLOW = {
    "FunctionReference", "EventReference", "MemberName", "MemberParent",
    "VariableReference", "SelfContextInfo", "FunctionName",
    "subgraph_references", "bDefaultsToPure",
}
```

- [x] **Step P4.1: 调查减法后 node_data 实际键（temp/，不提交）**

对 StackOBot / BP_CombatCharacter dump `set(node.node_data)` 的键分布。

- [x] **Step P4.2: 失败测试（CallFunction 语义来自 tags）**

```python
def test_call_function_raw_properties_reach_node_data():
    from uasset_read import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(
        "tests/samples/StackOBot_BP_Drone.uasset", depth="decode", tolerant=True
    )
    page = project_document(doc, depth="decode", max_bytes=2_000_000)
    nodes = [
        n
        for o in page.get("objects") or []
        for g in (o.get("semantic") or {}).get("graphs") or []
        for n in g.get("nodes") or []
        if "CallFunction" in (n.get("type") or "")
    ]
    assert nodes
    hits = [n for n in nodes if n.get("node_data")]
    assert hits, "CallFunction nodes must surface tag-derived node_data"
```

若 dump 显示键名不同，**改测试键名**，不要为通过测试去恢复 reader。

- [x] **Step P4.3: 实现**

```python
def _project_node_data(node_data: Any) -> dict[str, Any] | None:
    if not isinstance(node_data, dict):
        return None
    out: dict[str, Any] = {}
    for key, value in node_data.items():
        if key not in _NODE_DATA_ALLOW and not key.startswith("_"):
            continue
        if key.startswith("_"):
            continue  # never emit private bookkeeping
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[key] = value
        elif isinstance(value, dict):
            prims = {
                k: v for k, v in value.items() if isinstance(v, (str, int, float, bool, type(None)))
            }
            if prims:
                out[key] = prims
    return out or None
```

节点 dict：`"node_data": _project_node_data(...)`，`None` 则省略键。

- [x] **Step P4.4: 键集合冻结测试（可选但推荐）**

禁止出现 `default_value` 在 pin 上；node 上禁止出现非白名单大对象。

- [x] **Step P4.5: GREEN + Commit**

```bash
git add src/uasset_read/serializers/blueprint_graph.py tests/test_blueprint_decode.py
git commit -m "feat: project allow-listed tag-derived node_data onto decode nodes"
```

---

### Task P5: VariableGet/Set — 仅 tags

**Files:**
- Modify: 仅当 P4 白名单缺键时扩 `_NODE_DATA_ALLOW` / `_project_node_data`
- Test: `tests/test_blueprint_decode.py`

**Interfaces:**
- Produces: `node_data` 含 `VariableReference` 或等价 tag 键  
- **禁止** 修改 `graph_node.py` 去恢复 member reader

- [x] **Step P5.1: dump CombatCharacter Variable* 节点键 → temp/**

- [x] **Step P5.2: 失败测试**

```python
def test_variable_nodes_carry_tag_derived_reference():
    from uasset_read import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(
        "tests/samples/BP_CombatCharacter.uasset", depth="decode", tolerant=True
    )
    page = project_document(doc, depth="decode", max_bytes=3_000_000)
    nodes = [
        n
        for o in page.get("objects") or []
        for g in (o.get("semantic") or {}).get("graphs") or []
        for n in g.get("nodes") or []
        if "Variable" in (n.get("type") or "")
    ]
    assert nodes
    assert any(n.get("node_data") for n in nodes)
```

- [x] **Step P5.3: 扩白名单或 JSON 化嵌套 tag 值（最小）**

若 `VariableReference` 是 `StructValue`：在 `_project_node_data` 增加 StructValue → 深度 2 的原语 dict。

- [x] **Step P5.4: GREEN + Commit**

---

### Task P6: Unversioned — 现有样本做通

**Files:**
- Test: `tests/test_unversioned_fixtures.py`
- Modify: `src/uasset_read/parsers/property_parser.py`（mapping 路径）
- Modify: 仅必要时 `mappings.py`（保持 usmap 枚举游标行为，A T12 已降级只推进）

**Interfaces:**
- Consumes: `LegacyPackageReader(mappings_path="tests/samples/UnversionedTest.usmap")`
- Produces: 非空属性袋 **或** 显式整段 opaque；**禁止** tagged name-index 错位后仍报 complete

- [x] **Step P6.1: 结构断言测试（RED）**

以文件内现有 `test_bp_unversioned_parses` 调用序为准改写：

```python
def test_unversioned_bp_exposes_mapped_properties():
    # use the same open/read sequence as existing parse tests in this file
    ...
    props = primary.properties or {}
    assert props, "unversioned export with usmap must produce a non-empty property bag"
    codes = [d.code for d in doc.diagnostics]
    assert codes.count("name_index_out_of_range") == 0 or props.get("kind") == "opaque"
```

- [x] **Step P6.2: RED → 修 mapping 路径**

原则：
1. 无 usmap / struct 未命中 → 整段 `UnversionedOpaque`（保留）。
2. 命中 → 从 unversioned 正确起点顺序读；变长 size 不可靠则 **停止并 opaque 余下**。
3. **禁止** 回退 tagged FName 解析。

排查顺序：struct 名解析 → header fragment → `script_property_region` 起点。

- [x] **Step P6.3: GREEN + 全量 + Commit**

```bash
python -m pytest tests/test_unversioned_fixtures.py tests/test_core.py -v
python -m pytest -q
git add src/uasset_read/parsers/property_parser.py tests/test_unversioned_fixtures.py
git commit -m "fix: parse unversioned properties from usmap without tagged name-index fallback"
```

---

### Task P7: manifest `fixture_gaps` + README 诚实化

**Files:**
- Modify: `tests/samples/manifest.json`（**仅** `fixture_gaps.unversioned_properties` 及必要注记；A T13 不碰此块）
- Modify: `README.md`
- Modify: `docs/reference/agent-dev-reference.md`（若路径/能力句仍错）

**Interfaces:**
- Produces: 文档只描述已实现行为

- [x] **Step P7.1: 更新 unversioned gap**

- `status`: `partial`（editor unversioned + 本仓 usmap；不覆盖 cooked/Zen）
- 删除「Cannot determine if any samples…」过时句

- [x] **Step P7.2: README**

1. Blueprint Features：改为「pin-level links + tag-derived node_data + exec edges + Kismet expressions」；删除未实现的 “Event → CallFunction chain tracking / data dependencies” 夸大句。  
2. 模块路径改为 `serializers/blueprint_graph.py`（减法后仍如此）。  
3. 提及 pin 输出键集合为五键（A T3 契约）。

- [x] **Step P7.3: 棘轮若 docs 超限则按实测收紧**

```bash
python -m pytest -q
git add tests/samples/manifest.json README.md docs/reference/agent-dev-reference.md tests/size-baseline.json
git commit -m "docs: align blueprint and unversioned claims with post-subtraction v2 behavior"
```

---

### Task P8: Wave B 验收

- [x] **Step P8.1: 全量门禁**

```bash
python -m pytest -q
python -m ruff check src/uasset_read tests/
```

- [x] **Step P8.2: 体积基线**

按 git ls-files 口径测量；有意提高 tests 则更新 `size-baseline.json` 并写 note。

- [x] **Step P8.3: 对照 Acceptance 清单**

| 验收 | 通过标准 |
| --- | --- |
| state_count | ALS 大状态机 `state_count < node_count` |
| exec | StackOBot EventGraph 有 `exec_chains.edges` |
| node 名 | 多节点图不出现「全员同名」 |
| node_data | CallFunction/Variable 有 tag 派生键；无恢复的二进制 reader |
| pin 契约 | 仍为五键（A T3 钉） |
| unversioned | 非空袋或显式 opaque；无 name-index 风暴 |
| 文档 | README 无超前宣称 |
| 套件 | 零失败；ruff 绿 |

---

## 与旧版产品化计划的差异（附录 A 对照）

| 旧任务 | 处置 |
| --- | --- |
| 旧 Task 1–2：断言 `function_reference` 来自已删 reader | **废止** → P4/P5 tags-only |
| 旧 Task 2：pin default/subcategory/hidden | **废止** → A T3 五键冻结 |
| 旧 Task 3：state_count | **保留** → P1（source 改为存活 subgraph_references） |
| 旧 Task 4：edge_count | **保留** → 并入 A T5 后视需要小修（不在 B 重复大改） |
| 旧 Task 5：改 graph_node 恢复 member 读 | **废止** → P5 |
| 旧 Task 6：exec 链 | **保留** → P2 |
| 旧 Task 7–8：unversioned | **保留** → P6 |
| 旧 Task 9：manifest/README | **保留** → P7（fixture_gaps 仍归 B） |
| 旧 Task 10：棘轮 | **保留** → P8 |

## 索引行（本合并后）

- 本文件：`target`，总调度（Wave A 参见 ponytail 原文；Wave B 重写）。
- `2026-09-12-ponytail-evaluation-fix-plan.md`：减法权威规格与逐步步骤。

---

## 执行交接（已执行）

**Plan complete, executed** on branch `docs/productize-unversioned`.

1. Wave A (ponytail T1–T14, T16; T15 intentionally **not** executed) landed in the Wave A commit chain through size-baseline tightening.
2. Wave B P0–P8 and second-review hardening (`81eb9de9`…`2419de4e`) landed on the same branch.
3. Remaining work is outside this plan: Phase A (this document's successor plan), Phase C research gates, Phase D deferred bundling. See `docs/designs/2026-09-13-next-phase-closeout-and-deferred-gates.md` if present.
