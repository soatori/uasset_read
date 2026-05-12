# Phase 34: 等价验证 - Research

**Researched:** 2026-05-12 (更新)
**Domain:** 新旧输出等价性验证（JSON/Text/Markdown 逐字段对比）
**Confidence:** HIGH

## Summary

Phase 34 的目标是验证新版模块化代码（`src/uasset_read/`）与旧版单文件（`uasset_read_legacy.py`）对同一 `.uasset` 文件的输出完全一致。2026-05-12 实测更新确认：新旧输出之间存在**9 类已验证差异**，涵盖有意设计变更（graphs_summary 扩展、status 修复、top-level keys 移除）和待修复问题（parent_class str(dict) bug、execution_flows 信息丢失、mermaid 缺失、ObjectProperty 格式变更）。

实测采用合成资产和真实蓝图资产双线对比。合成资产（`create_test_uasset()`）由于结构简单，输出仅在 top-level keys 层面有差异；真实资产（`BP_FirstPersonCharacter.uasset`）暴露了大部分深层差异。

**Primary recommendation:** 采用"基线快照 + 差异分类"策略——用旧版生成所有测试资产的四种格式输出作为基线，逐对比新版输出，将差异自动分类为"已知/可接受"或"待修复"，最终生成 VERIFICATION.md 报告。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01 (验证策略):** 两者结合 — 先用整体 diff 快速验证 JSON/Text/Markdown 输出，发现差异时再用逐字段对比定位具体差异位置。整体 diff 使用 `json.dumps()` 序列化后字符串比较，逐字段对比使用递归遍历 dict 结构。
- **D-02 (验证范围):** 全部四种输出格式 — JSON Full、JSON Summary、Text、Markdown。不跳过任何格式。
- **D-03 (资产覆盖):** 合成资产 + 真实资产结合 — 既使用 tests/ 中的合成测试资产（覆盖边界场景），也使用真实蓝图资产（如 BP_FirstPersonCharacter）验证实际解析场景。
- **D-04 (差异策略):** 记录并继续 — 发现差异后记录到差异列表并继续验证其他资产/格式，最后生成完整差异报告。不中断验证流程。
- **D-05 (报告形式):** Markdown 报告 — 在 `.planning/phases/34-equivalence-verification/VERIFICATION.md` 中记录所有发现的差异、修复状态和最终结论。
- **D-06 (工具形式):** 测试文件 — 在 `tests/test_equivalence.py` 中创建验证测试，使用 pytest 运行。每个资产+格式组合一个测试用例。
- **D-07 (验证函数):** 在测试文件中定义辅助函数 `_compare_outputs(old_output, new_output, format_name)` 实现两种对比策略，不放在 src/uasset_read/ 模块中。
- **D-08 (前置条件):** Phase 33 完成后才能开始 Phase 34 验证。前置条件包括：(1) `python -m uasset_read` 能正常解析测试资产 (2) `uasset-read` CLI 入口可用 (3) 旧版 `uasset_read.py` 已删除 (4) 全部 373+ 测试通过。

### Claude's Discretion
- 测试用例的具体分组和命名（如 `test_json_equivalence_firstperson` vs `test_equivalence_json_firstperson`）由规划阶段确定
- diff 工具的具体实现（使用 Python 标准库 `difflib` 还是直接字符串比较）由规划阶段确定
- 差异报告的具体字段格式（哪些列、如何展示 diff）由规划阶段确定

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| 等价-01 | JSON Full 输出等价 | §差异清单 #1, #2, #8 — imports/soft_references/circular_deps 移除、parent_class str(dict) bug |
| 等价-02 | JSON Summary 输出等价 | §差异清单 #1, #5, #6 — graphs_summary 8键 vs 2键、execution_flows 格式变化 |
| 等价-03 | Text 输出等价 | §差异清单 #4 — ObjectProperty 值格式变化（227 行 diff） |
| 等价-04 | Markdown 输出等价 | §差异清单 #7, #8 — mermaid 缺失、parent_class str(dict) dict 格式 |
| 等价-05 | 合成资产验证 | §环境可用性 — create_test_uasset() 可生成、旧版/新版均可解析 |
| 等价-06 | 真实资产验证 | §环境可用性 — BP_FirstPersonCharacter 等 5+ 蓝图资产可用 |
| 等价-07 | VERIFICATION.md 报告生成 | §验证架构 — DiffRecorder → Markdown 报告生成模式 |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 旧版输出生成 | API/Backend（本地 Python） | — | 调用 `uasset_read_legacy.py` 作为独立进程 |
| 新版输出生成 | API/Backend（本地 Python） | — | 调用 `python -m uasset_read` 或 `uasset-read` |
| 结构化对比 | API/Backend（本地 Python） | — | Python 递归 dict/list 遍历比较 |
| 字符串 diff | API/Backend（本地 Python） | — | Python `difflib` 标准库 |
| 报告生成 | API/Backend（本地 Python） | — | Markdown 模板渲染 |
| pytest 集成 | 测试工具链 | — | pytest 框架运行验证测试 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `difflib` | Python stdlib | 字符串级 diff 生成（ndiff, unified_diff） | Python 标准库，零依赖，内置统一 diff 格式 |
| `json` | Python stdlib | JSON 序列化/反序列化、规范化排序 | `json.dumps(obj, sort_keys=True, indent=2)` 确保确定性对比 |
| `pytest` | >= 8.0 (project dev dependency) | 测试框架运行验证用例 | 项目已使用，fixture/parametrize 支持 |
| `subprocess` | Python stdlib | 调用旧版/新版 CLI 获取输出 | 无需额外依赖，支持捕获 stdout/stderr/returncode |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tempfile` | Python stdlib | 临时基线文件存储 | 生成旧版输出后保存为临时文件用于 diff |
| `pathlib` | Python stdlib | 路径管理 | 测试资产路径操作 |
| `re` | Python stdlib | Markdown 结构解析（mermaid 块提取） | 分解 Markdown 输出为结构化节 |

**Not available (verified 2026-05-12):** `deepdiff` — NOT installed in project environment. Standard library `difflib` + custom recursive compare is sufficient.

**Installation:** No additional packages needed — all tools are Python standard library or already installed dev dependencies.

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────────┐
                    │   Test Asset Sources    │
                    │  (synthetic + real)     │
                    └─────────┬───────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
     ┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
     │  Old CLI Runner  │ │ New CLI      │ │ Programmatic API │
     │  (subprocess)    │ │ Runner       │ │ (import module)  │
     │  uasset_read_    │ │ python -m    │ │ parse_uasset()   │
     │  legacy.py       │ │ uasset_read  │ │ format_xxx()     │
     └───────┬─────────┘ └──────┬───────┘ └────────┬─────────┘
             │                  │                   │
             ▼                  ▼                   ▼
     ┌──────────────────────────────────────────────────────┐
     │              Output Normalizer                        │
     │  json.dumps(sort_keys=True, indent=2) for JSON        │
     │  Direct string for Text/Markdown                      │
     └──────────────────────┬───────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
     ┌─────────────────┐         ┌─────────────────┐
     │  Overall Diff   │         │  Field-by-Field  │
     │  (string cmp)   │────────▶│  Compare (dict)  │
     │  Fast pass/fail │  fail   │  Recursive walk  │
     └─────────────────┘         └────────┬────────┘
                                          │
                                          ▼
                                 ┌─────────────────┐
                                 │  Diff Recorder   │
                                 │  Record & Continue│
                                 └────────┬────────┘
                                          │
                                          ▼
                                 ┌─────────────────┐
                                 │ VERIFICATION.md  │
                                 │ Markdown Report  │
                                 └─────────────────┘
```

### Recommended Project Structure

No new source files needed. Test structure within `tests/`:

```
tests/
├── test_equivalence.py          # Main equivalence verification tests
# (No new src/ modules — D-07: helpers in test file only)
```

### Pattern 1: Record-and-Continue Diff
**What:** 发现差异后记录到列表，不中断验证流程，最终生成完整报告
**When to use:** D-04 locked decision
**Example:**
```python
class DiffRecorder:
    """收集所有差异，不中断验证流程（D-04）"""
    def __init__(self):
        self.diffs: list[dict] = []

    def record(self, asset_name: str, format_name: str,
               field_path: str, old_value, new_value,
               severity: str = "diff", category: str = "unknown"):
        self.diffs.append({
            "asset": asset_name,
            "format": format_name,
            "field": field_path,
            "old_value": old_value,
            "new_value": new_value,
            "severity": severity,  # "diff" | "bug" | "improvement" | "known"
            "category": category,  # "top_level_keys" | "graphs_summary" | "execution_flows" | "parent_class" | ...
        })

    def get_by_severity(self, severity: str) -> list[dict]:
        return [d for d in self.diffs if d["severity"] == severity]

    def get_by_category(self, category: str) -> list[dict]:
        return [d for d in self.diffs if d["category"] == category]
```

### Pattern 2: Two-Level Comparison (D-01)
**What:** 先整体字符串 diff（快速通过），失败时递归逐字段对比
**When to use:** D-01 locked decision

Level 1 — Overall string diff (fast):
```python
def overall_diff(old_str: str, new_str: str) -> bool:
    """整体字符串对比。返回 True 表示完全一致。"""
    return old_str == new_str
```

Level 2 — Recursive field-by-field (on failure):
```python
def deep_compare(old: Any, new: Any, path: str = "") -> list[dict]:
    """递归对比任意 Python 对象，返回差异列表（D-01 逐字段对比）"""
    diffs = []

    if type(old) != type(new):
        diffs.append({"path": path, "type": "type_changed",
                      "old_type": type(old).__name__, "new_type": type(new).__name__,
                      "old_value": old, "new_value": new})
        return diffs

    if isinstance(old, dict):
        all_keys = set(old.keys()) | set(new.keys())
        for key in sorted(all_keys):
            current_path = f"{path}.{key}" if path else key
            if key not in old:
                diffs.append({"path": current_path, "type": "added", "new_value": new[key]})
            elif key not in new:
                diffs.append({"path": current_path, "type": "removed", "old_value": old[key]})
            else:
                diffs.extend(deep_compare(old[key], new[key], current_path))
    elif isinstance(old, list):
        max_len = max(len(old), len(new))
        for i in range(max_len):
            current_path = f"{path}[{i}]"
            if i >= len(old):
                diffs.append({"path": current_path, "type": "added", "new_value": new[i]})
            elif i >= len(new):
                diffs.append({"path": current_path, "type": "removed", "old_value": old[i]})
            else:
                diffs.extend(deep_compare(old[i], new[i], current_path))
    elif old != new:
        diffs.append({"path": path, "type": "value_changed",
                      "old_value": old, "new_value": new})

    return diffs
```

### Anti-Patterns to Avoid
- **在 src/ 中放验证代码:** D-07 明确禁止 — 验证是测试阶段工具，不是生产代码
- **发现第一个差异就停止:** 违反 D-04 — 必须记录并继续
- **跳过 Text/Markdown 格式:** 违反 D-02 — 全部四种格式都要验证
- **使用 `deepdiff` 等第三方库:** 项目未安装，且标准库 `difflib` + custom `deep_compare` 已足够
- **假设新旧输出完全一致:** 实测确认存在 9 类差异——验证的目标是**分类和记录**差异，而非追求零差异

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON 规范化排序 | 自定义排序函数 | `json.dumps(obj, sort_keys=True, indent=2)` | Python 标准库，确保字段顺序一致性 |
| 字符串 diff | 自行实现 diff 算法 | `difflib.unified_diff()` / `difflib.ndiff()` | 标准库，输出格式成熟（unified diff 格式） |
| 子进程调用 | `os.system()` / `subprocess.Popen` 手动管理 | `subprocess.run(..., capture_output=True, text=True)` | 简化 API，自动处理编码和超时 |
| 临时文件管理 | 手动创建/删除临时文件 | `tempfile.NamedTemporaryFile(delete=False)` | 自动清理，安全路径生成 |
| pytest 测试分组 | 自定义测试运行器 | `pytest.mark.parametrize` | 项目已有，支持 fixture 和参数化 |
| Markdown 结构化解析 | 正则逐行解析 | `re.findall(r'```mermaid\n(.*?)```', text, re.DOTALL)` | 提取 mermaid 块进行结构化对比 |

**Key insight:** 等价验证的核心是"可重复的对比流程"，不是"复杂的 diff 引擎"。Python 标准库完全覆盖所有需求。

## Verified Difference Inventory (2026-05-12 实测)

通过实测 `BP_FirstPersonCharacter.uasset` (138KB) 和合成测试资产确认的**9 类差异**：

### Category A: Intentional Design Changes (可接受)

| # | Category | Description | Old Behavior | New Behavior | Severity |
|---|----------|-------------|-------------|--------------|----------|
| 1 | top_level_keys | JSON 顶层移除了 `imports`, `soft_references`, `circular_deps` | 3 个额外顶层键 | 仅保留核心键 (Phase 32 D-02) | known |
| 2 | status | blueprint parent 检测修复 | `status: "fail"` + PARSE_ERROR | `status: "success"` (parent 正确解析) | improvement |
| 3 | graphs_summary_keys | graphs_summary 条目键数扩展 | 2 键: `{graph_name, execution_flows}` | 8 键: `{connections, data_flows, execution_flows, graph_name, graph_type, node_count, schema, warnings}` | improvement |
| 4 | ObjectProperty_value | ObjectProperty 值序列化格式变化 | `{'raw_index': 6, 'resolved': {'type': 'export', ...}}` (dict) | `6` (裸整数 raw_index) | **needs decision** |
| 5 | execution_flows_format | 执行流结构从 event 型改为 node 型 | `{event, function_name, calls[]}` — calls 是函数名列表 | `{start_event, nodes[]}` — nodes 是 `{node_guid, node_type}` 列表 | **needs investigation** |
| 6 | execution_flows_count | 执行流数量减少 | EventGraph 有 7 个 flows | EventGraph 有 4 个 flows | **possible regression** |

### Category B: Confirmed Bugs (待修复)

| # | Category | Description | Root Cause | Fix Location |
|---|----------|-------------|------------|-------------|
| 7 | mermaid_missing | Markdown 输出缺少 Mermaid 流程图 | `execution_flows` 结构从 `{event, function_name, calls[]}` 改为 `{start_event, nodes[]}`，且 nodes 缺少 `function_name` 字段。`_build_mermaid_flowchart()` 依赖 `node_type == "K2Node_CallFunction"` 过滤但 nodes 只有 `K2Node_Event` 类型 | `markdown_formatter.py:106-145` and `graph/extractor.py` |
| 8 | parent_class_str | `parent_class` 为 `str(dict)` 而非原生 dict | `variable_extractor.py:357`: `str(prop.value)` 对 ObjectProperty 调用 str() 产生 `"{'type': 'import', ...}"` 字面量 | `blueprint/variable_extractor.py:357` |

### Category C: Shared Limitation (非回归)

| # | Category | Description | Old Behavior | New Behavior | Impact |
|---|----------|-------------|-------------|--------------|--------|
| 9 | json_full_crash | `--json` full format 在真实资产上因非可序列化对象而崩溃 | exit code 1, `json.dumps()` TypeError | exit code 1, 同类型错误 | 等价 (shared limitation) — 不影响等价-01 验证，可使用合成资产或修复后对比 |

### Diff 行数统计 (Text Format)

```
Text unified_diff 总行数: 602 行
  - ObjectProperty/Value 相关: 227 行 (差异 #4)
  - parent 相关:             18 行 (差异 #8)
  - graph 相关:              20 行 (差异 #5, #6)
  - 其他结构性差异:          337 行
```

## Runtime State Inventory

不适用 — 本 phase 是验证测试阶段，不修改运行时状态，不涉及 rename/refactor/migration。

## Common Pitfalls

### Pitfall 1: JSON 序列化不一致
**What goes wrong:** 同一 dict 两次 `json.dumps()` 可能产生不同字符串（字段顺序随机）
**Why it happens:** Python 3.7+ dict 保留插入顺序，但 `sort_keys=True` 才是确定性输出的唯一保证
**How to avoid:** 所有 JSON 对比必须使用 `json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False)`
**Warning signs:** 相同数据产生不同 diff 结果

### Pitfall 2: subprocess 路径中的 Windows 路径分隔符
**What goes wrong:** `subprocess.run(['python', '-m', 'uasset_read', path])` 中 path 使用反斜杠（Windows）导致参数解析异常
**Why it happens:** Windows 路径 `E:\path\to\file.uasset` 中 `\f` 等被解释为转义字符
**How to avoid:** 使用正斜杠路径（`E:/path/to/file.uasset`）或 `pathlib.Path.as_posix()`
**Warning signs:** `unrecognized arguments` 错误

### Pitfall 3: parent_class Field 类型不一致
**What goes wrong:** 新版 `parent_class` 在 JSON 中是 `str` 类型（`"{'type': 'import', ...}"`），旧版是 `None`
**Why it happens:** `variable_extractor.py:357` 对 `prop.value` 调用 `str()`，当 value 是 ObjectProperty 实例时产生 Python 字面量字符串
**How to avoid:** 在 VERIFICATION.md 分类中标记为"bug — 待修复"，同时验证测试接受此差异为已知
**Warning signs:** `parent_class` 值以 `{` 开头的字符串；`json.dumps()` 将其序列化为含转义引号的字符串

### Pitfall 4: execution_flows 结构不兼容导致 mermaid 静默失败
**What goes wrong:** 新版 Markdown 输出无 mermaid 图表，但无错误信息
**Why it happens:** `_build_mermaid_flowchart()` 期望 nodes 有 `function_name` 字段和 `node_type == "K2Node_CallFunction"` 过滤，但新版 execution_flows 的 nodes 仅有 `{node_guid, node_type}` 且全是 `K2Node_Event` 类型。函数静默返回空列表，不报错。
**How to avoid:** 验证测试应显式检查 mermaid 块存在性（`re.findall(r'```mermaid', output)`）
**Warning signs:** Markdown 输出缺少 ```` ```mermaid ```` 围栏块

### Pitfall 5: `--json` full format 在真实资产上崩溃是共享限制
**What goes wrong:** 验证者可能认为新版 `--json` 崩溃是新引入的 bug
**Why it happens:** 旧版和新版都在 `json.dumps(format_json_full(...))` 时因非可序列化对象（如 ObjectProperty 实例被直接放入输出结构）而失败。这是两版共有的限制。
**How to avoid:** 等价-01 (JSON Full) 验证应使用合成资产（合成资产无此问题），或先修复两版的序列化问题
**Warning signs:** 两版都返回 exit code 1，stderr 显示 `TypeError: Object of type X is not JSON serializable`

## Code Examples

Verified patterns from Python standard library documentation:

### Overall String Diff (difflib.unified_diff)
```python
import difflib

def string_diff(old_str: str, new_str: str, old_label: str = "old", new_label: str = "new") -> str:
    """生成 unified diff 格式的差异输出"""
    old_lines = old_str.splitlines(keepends=True)
    new_lines = new_str.splitlines(keepends=True)
    return "".join(difflib.unified_diff(old_lines, new_lines,
                                         fromfile=old_label, tofile=new_label))
```

### Subprocess CLI Runner
```python
import subprocess

def run_cli(legacy: bool, format_flag: str, asset_path: str) -> tuple[str, int]:
    """运行 CLI 命令并返回 (stdout, returncode)

    Args:
        legacy: True=旧版 uasset_read_legacy.py, False=新版 python -m uasset_read
        format_flag: '--json', '--summary', '--text', '--markdown'
        asset_path: .uasset 文件路径（使用正斜杠）
    """
    if legacy:
        cmd = ["python", "uasset_read_legacy.py", format_flag, asset_path]
    else:
        cmd = ["python", "-m", "uasset_read", format_flag, asset_path]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout, result.returncode
```

### Mermaid Block Detection
```python
import re

def extract_mermaid_blocks(markdown_output: str) -> list[str]:
    """从 Markdown 输出中提取所有 mermaid 代码块"""
    return re.findall(r'```mermaid\n(.*?)```', markdown_output, re.DOTALL)
```

### VERIFICATION.md Report Builder
```python
def build_verification_report(diff_recorder: 'DiffRecorder', asset_count: int) -> str:
    """从 DiffRecorder 构建 VERIFICATION.md 报告"""
    lines = [
        "# Phase 34: 等价验证报告",
        "",
        f"**验证日期:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}",
        f"**测试资产数:** {asset_count}",
        f"**总差异数:** {len(diff_recorder.diffs)}",
        "",
        "## 差异分类",
        "",
    ]

    # 按分类分组
    bugs = diff_recorder.get_by_severity("bug")
    improvements = diff_recorder.get_by_severity("improvement")
    known = diff_recorder.get_by_severity("known")
    diffs = diff_recorder.get_by_severity("diff")

    if bugs:
        lines.append("### Bugs (待修复)")
        for d in bugs:
            lines.append(f"- **{d['category']}**: `{d['field']}` — old={d['old_value']!r}, new={d['new_value']!r}")
        lines.append("")

    if improvements:
        lines.append("### Improvements (有意改进)")
        for d in improvements:
            lines.append(f"- **{d['category']}**: {d.get('note', d['field'])}")
        lines.append("")

    if known:
        lines.append("### Known Differences (已知差异)")
        for d in known:
            lines.append(f"- **{d['category']}**: {d.get('note', d['field'])}")
        lines.append("")

    if diffs:
        lines.append("### Other Differences (需审查)")
        for d in diffs:
            lines.append(f"- `{d['field']}`: old={d['old_value']!r}, new={d['new_value']!r}")
        lines.append("")

    # 结论
    lines.append("## 结论")
    if bugs:
        lines.append(f"- **{len(bugs)} 个待修复问题** — 需在 v6.1 或更早修复")
    lines.append(f"- **{len(improvements)} 个有意改进** — 新版行为更正确")
    lines.append(f"- **{len(known)} 个已知差异** — 设计决策导致的结构变化")
    lines.append(f"- **{len(diffs)} 个其他差异** — 需人工审查")

    return "\n".join(lines)
```

## State of the Art

### Output Format Evolution (v6.0)

| Aspect | Old (uasset_read_legacy.py) | New (src/uasset_read/) | Change Type |
|--------|----------------------------|------------------------|-------------|
| `format_json_full` top-level keys | includes `imports`, `soft_references`, `circular_deps` | excludes these fields (Phase 32 D-02) | Intentional removal |
| `format_json_summary` graphs_summary | minimal: `{graph_name, execution_flows}` | expanded: 8 keys including `graph_type`, `node_count`, `schema`, `connections`, `data_flows`, `warnings` | Intentional expansion |
| `format_text_full` ObjectProperty | `{'raw_index': N, 'resolved': {...}}` (dict with both raw and resolved) | raw int `N` (e.g., `6`) — simplified | Format change (needs decision) |
| `format_markdown` graph key | `.get("graph")` — **bug** (key doesn't exist in summary output) | `.get("graph_name")` — correct | Bug fix in new code |
| `format_markdown` mermaid | Present — uses old `{event, function_name, calls[]}` format | **Missing** — new `{start_event, nodes[]}` lacks `function_name` and `K2Node_CallFunction` filtering | **Bug in new code** |
| `build_status_info` | Returns `fail` + warning for parent detection issue | Returns `success` (parent properly resolved) | Behavior improvement |
| `parent_class` output type | `None` (unresolved) | `str` (Python dict `repr`): `"{'type': 'import', ...}"` | **Bug in new code** |
| `execution_flows` format | `{event: str, function_name: str, calls: list[str]}` (7 flows in EventGraph) | `{start_event: "Unknown", nodes: [{node_guid, node_type}]}` (4 flows) | Structure change + information loss |
| `blueprint` section (summary) | `{blueprint_name, parent_class}` only | `{blueprint_name, parent_class}` same keys | Equivalent for basic structure |

### Impact on Phase Requirements

| Req ID | Format | Feasibility | Notes |
|--------|--------|------------|-------|
| 等价-01 | JSON Full | **Blocked** for real assets | Both old and new crash on `BP_FirstPersonCharacter` — shared serialization issue. Use synthetic assets only. |
| 等价-02 | JSON Summary | **Feasible** | 4/9 diffs apply: #1 (keys), #2 (status), #3 (graphs_summary), #5 (execution_flows). Requires `deep_compare` not string diff. |
| 等价-03 | Text | **Feasible** | 602 lines diff; main categories: ObjectProperty (227), parent (18), graph (20). String diff + field diff both needed. |
| 等价-04 | Markdown | **Feasible** | Requires structured parsing (mermaid block extraction) for meaningful comparison. |
| 等价-05 | Synthetic | **Easy** | Only diff #1 (top-level keys) applies. Near-equivalent output. |
| 等价-06 | Real | **Feasible** | All 9 diffs apply. BP_FirstPersonCharacter is primary test asset. |
| 等价-07 | Report | **Feasible** | DiffRecorder → VERIFICATION.md generation. |

### Deprecated/outdated:
- **旧版 `format_markdown` 的 `"graph"` 键**: 旧版使用 `graph_summary.get("graph", "Unknown")`，但 `build_graphs_summary` 输出的 key 是 `"graph_name"` — 这导致旧版 Markdown 输出中所有图名都是 "Unknown"。新版已修复为 `"graph_name"`。
- **旧版 `build_graphs_summary` 的 execution_flows 格式**: 使用 `{event, function_name, calls[]}`（calls 是字符串列表），新版改为 `{start_event, nodes[]}`（nodes 是结构化 dict 列表）。

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `uasset_read_legacy.py` 在项目根目录可正常运行 | Runtime State | 如果旧版文件损坏或被修改，无法生成基线输出。Git 恢复可用 (commit `32a55f3^`) |
| A2 | `deepdiff` 不可用（仅测试了当前 Python 环境） | Standard Stack | 如果 deepdiff 实际可用，规划可考虑使用简化对比 |
| A3 | 373 passed, 71 skipped 是当前正确测试状态（2026-05-12） | Environment | Phase 33 修复可能改变测试计数 |
| A4 | `create_test_uasset()` 生成的合成资产对旧版和新版都能解析 | Test Assets | 如果旧版无法解析合成资产，需要调整基线生成策略 |
| A5 | `--json` full format 崩溃是旧版和新版共有的限制，非新引入 | Difference #9 | 如果旧版实际上在某些资产上能成功输出 `--json`，则新版可能有回归 |
| A6 | `execution_flows` 数量差异 (7→4) 是信息丢失而非有意简化 | Difference #6 | 如果 Phase 31 决策中明确要求精简 flows，则是设计行为 |

## Open Questions

1. **ObjectProperty 值格式统一**: 新版使用裸整数（`6`），旧版使用 `{'raw_index': 6, 'resolved': {...}}`。应该回滚到旧版格式以保持一致性，还是接受新版的简化格式？
   - 当前状态：差异 #4, Text 输出中影响 227 行
   - 推荐：接受简化格式 — 旧版的 `resolved` 字段虽然信息更丰富，但新版的 `raw_index` 省略是有意的设计决策（减少输出冗余）。如果用户要求完全等价，则需在 formatters 中恢复 resolved 输出。

2. **graphs_summary 字段扩展**: 新版比旧版多出 6 个字段。等价验证应该要求"字段完全一致"还是"旧版字段一致即可，允许新版扩展"？
   - 推荐：允许扩展 — 这是 Phase 31 的有意增强，不是 bug。验证测试应对"新增字段"采用宽容模式（允许 extra keys），仅标记为"结构变化"

3. **Markdown mermaid 图表缺失**: 新版没有 mermaid 图表。是否需要修复 `_build_mermaid_flowchart()` 以适配新的 execution_flows 格式？
   - 当前状态：差异 #7 — mermaid 块存在但为空（旧版有 1 个 mermaid 块含 7 条边）
   - root cause: (a) execution_flows format changed from `{event, function_name, calls[]}` to `{start_event, nodes[]}`; (b) nodes 缺少 `function_name` 字段; (c) `_build_mermaid_flowchart()` 未更新以适配新格式
   - 推荐：修复 — mermaid 是 Markdown 输出的重要功能。需要两步：(1) 在 graph extraction 中保留 function_name 到 nodes；(2) 更新 `_build_mermaid_flowchart()` 以处理新格式

4. **execution_flows 数量差异 (7→4)**: 新版 EventGraph 只有 4 个 flows，旧版有 7 个。这是信息丢失还是过滤改进？
   - 当前状态：差异 #6 — 3 个 flow 在新版中消失
   - 推荐：需调查 — 检查 Phase 31 build_execution_flows() 的过滤逻辑。如果是有意过滤（如去重 EnhancedInputAction Triggered/Ongoing 双事件），应标记为改进。如果是信息丢失，需要修复。

5. **parent_class str(dict) bug**: 新版 `parent_class` 是 `str` 类型，值为 Python dict 的 repr 字符串。这是明确的 bug 还是序列化层的问题？
   - 当前状态：差异 #8 — `variable_extractor.py:357` 调用 `str(prop.value)`, prop.value 是 ObjectProperty 实例
   - 推荐：修复 — 应将 `str(prop.value)` 改为适当的提取逻辑（如 `prop.value.raw_value` 或 `resolve_fpackage_index(prop.value, ...)`）

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | CLI runner, test execution | ✓ | 3.14.3 | — |
| pytest | Test framework | ✓ | via dev deps | — |
| `uasset_read_legacy.py` | Baseline output generation | ✓ | 312KB, functional | Recover from git (commit `32a55f3^`) |
| BP_FirstPersonCharacter.uasset | Primary real asset testing | ✓ | 138KB | — |
| BP_FirstPersonCameraManager.uasset | Additional real asset | ✓ | 15KB | — |
| BP_FirstPersonGameMode.uasset | Additional real asset | ✓ | 16KB | — |
| BP_FirstPersonPlayerController.uasset | Additional real asset | ✓ | available | — |
| BP_ShooterCharacter.uasset | Additional real asset (Shooter variant) | ✓ | available | — |
| `deepdiff` | Advanced dict comparison | ✗ | — | Use `difflib` + custom `deep_compare()` function |
| `gsd-sdk` | Init/query commands | ⚠ partial | v0.1.0 (run/auto/init only) | Direct file reads for .planning/ |

**Missing dependencies with no fallback:**
- None — all core dependencies available

**Missing dependencies with fallback:**
- `deepdiff` — fallback to custom `deep_compare()` function using standard library

### Real Blueprint Assets Available

| Asset | Path | Size | Has Graph | Notes |
|-------|------|------|-----------|-------|
| BP_FirstPersonCharacter | `/Content/FirstPerson/Blueprints/` | 138KB | ✓ (4 graphs) | Primary test target |
| BP_FirstPersonCameraManager | `/Content/FirstPerson/Blueprints/` | 15KB | ✓ | Lightweight, good for --json full |
| BP_FirstPersonGameMode | `/Content/FirstPerson/Blueprints/` | 16KB | — | Simple, no graphs |
| BP_FirstPersonPlayerController | `/Content/FirstPerson/Blueprints/` | available | ✓ | Has input mapping |
| BP_ShooterCharacter | `/Content/Variant_Shooter/Blueprints/` | available | ✓ | Heavier, good stress test |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via project dev dependencies) |
| Config file | None — uses project root `pytest` defaults |
| Quick run command | `python -m pytest tests/test_equivalence.py -v --tb=short` |
| Full suite command | `python -m pytest tests/ -v --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? | Expected Outcome |
|--------|----------|-----------|-------------------|-------------|-----------------|
| 等价-01 | JSON Full 输出等价 (合成资产) | automated | `pytest tests/test_equivalence.py::test_json_full_synthetic -x` | ❌ Wave 0 | Pass or known diff #1 |
| 等价-02 | JSON Summary 输出等价 (合成+真实) | automated | `pytest tests/test_equivalence.py::test_json_summary -x` | ❌ Wave 0 | Diffs #1,#2,#3,#5 recorded |
| 等价-03 | Text 输出等价 (合成+真实) | automated | `pytest tests/test_equivalence.py::test_text -x` | ❌ Wave 0 | Diffs #4,#8 recorded |
| 等价-04 | Markdown 输出等价 (合成+真实) | automated | `pytest tests/test_equivalence.py::test_markdown -x` | ❌ Wave 0 | Diffs #7,#8 recorded + mermaid detected |
| 等价-05 | 合成资产全部格式验证 | automated | `pytest tests/test_equivalence.py -k synthetic -v` | ❌ Wave 0 | Should be near-pass (only diff #1) |
| 等价-06 | 真实资产全部格式验证 | automated | `pytest tests/test_equivalence.py -k real -v` | ❌ Wave 0 | All 9 diffs may appear |
| 等价-07 | VERIFICATION.md 报告生成 | automated | Check file after test run: `.planning/phases/34-equivalence-verification/VERIFICATION.md` | ❌ Wave 0 | Report exists with correct structure |

### Sampling Rate
- **Per asset+format test:** `pytest tests/test_equivalence.py::<test_name> -x`
- **Per wave merge:** `python -m pytest tests/test_equivalence.py -v`
- **Phase gate:** All equivalence tests pass OR have documented known diffs in VERIFICATION.md; report generated

### Wave 0 Gaps
- [ ] `tests/test_equivalence.py` — 核心验证测试文件（包含 DiffRecorder、deep_compare、CLI runner helpers）
- [ ] 基线输出获取机制 — 决定是每次动态生成旧版输出（临时文件）还是预生成快照
- [ ] DiffRecorder 类 — 在测试文件中实现，支持按 severity/category 分组
- [ ] VERIFICATION.md 报告生成函数 — `build_verification_report()` 在测试文件中实现
- [ ] Mermaid 块检测逻辑 — `extract_mermaid_blocks()` 用于 Markdown 格式的结构化对比
- [ ] pytest parametrize fixture — 资产 x 格式 的笛卡尔积测试矩阵

## Security Domain

Not applicable — this is a verification/testing phase with no external dependencies, no network access, and no new security-sensitive code. The phase only reads local files and runs local comparisons.

`security_enforcement` check: Config has `nyquist_validation: true`, but this phase has no user input processing, no authentication, no cryptographic operations, and no external data ingestion. ASVS categories do not apply.

## Sources

### Primary (HIGH confidence)
- **Runtime verification** (2026-05-12) — Both old and new CLI tested on `BP_FirstPersonCharacter.uasset`; all 4 formats (--json, --summary, --text, --markdown) compared; diff statistics computed
- **Runtime verification** (2026-05-12) — Synthetic asset comparison via `create_test_uasset()`; confirmed only top-level key differences
- **Codebase inspection** — `src/uasset_read/blueprint/variable_extractor.py:357` (parent_class str(dict) root cause)
- **Codebase inspection** — `src/uasset_read/formatters/markdown_formatter.py:106-145` (_build_mermaid_flowchart format dependency)
- **Codebase inspection** — `src/uasset_read/formatters/markdown_formatter.py:73-81` (mermaid block generation call site)
- **Git recovery** — `uasset_read_legacy.py` is current working file (312KB), not from git recovery

### Secondary (MEDIUM confidence)
- **Python 3.14 stdlib docs** — `difflib`, `json`, `subprocess`, `tempfile`, `re` modules
- **Phase 32 CONTEXT.md** — D-01 to D-09 (formatter decisions that cause output differences)
- **Phase 31 CONTEXT.md** — D-01 to D-09 (graph module structure decisions, graphs_summary expansion)
- **Phase 33 REVIEW.md** — Confirmed test count (373 passed) and legacy file status

### Tertiary (LOW confidence)
- **Test asset count** — 373 passed, 71 skipped (may change with future Phase 33 patches)
- **execution_flows count difference** — 7 vs 4 flows assumed to be information loss; needs Phase 31 code review to confirm

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified via `python -c "import X"` and project inspection
- Architecture: HIGH — verified by running both old and new CLI on real assets with diff analysis
- Pitfalls: HIGH — based on actual diff results between old and new outputs on BP_FirstPersonCharacter.uasset
- Difference inventory: HIGH — each difference verified by subprocess output capture and JSON/string comparison (2026-05-12)

**Research date:** 2026-05-12
**Valid until:** 2026-06-12 (30 days — stable verification methodology)
