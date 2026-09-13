# Ponytail Evaluation Fix Plan (减法优先 / Subtraction-First)

> **ARCHIVED (2026-09-26):** Executed closeout / plan-of-record. Historical evidence only — do not re-execute. Binding contracts and the canonical target remain under [`docs/designs/`](../README.md).


> **Status:** historical (executed 2026-09-12; Wave A complete, T15 deferred). Restored from local draft 2026-09-26. Not a binding target — see [residual cuts](2026-09-12-ponytail-residual-cuts.md) and [productize plan](2026-09-12-post-refactor-productize-plan.md).


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地已逐项对抗性复核过的 ponytail 减法结果(约 1,750 行,含 41 项确认、5 项推翻、21 项部分成立),同时修掉两个真实缺陷(CI ruff 红灯、`--depth decode` 静默丢 42/45 个 Kismet 函数体),全程零行为变更。

**Architecture:** 纯减法 + 两处重构/修复。每个任务一个提交,以 `python -m pytest -q` 的 220 passed 为 parity 闸门;凡触碰读路径或投影层的任务,额外以「66 个真实 fixture 的 `--depth decode` 输出哈希」逐字节相等为强闸门。**绝不删除顺序读取器里的 `archive.read_*()` 调用**——只写字段的 read 必须保留以推进游标;只删字段声明、构造 kwarg 与派生解析块。

**Tech Stack:** Python 3.10+(阻断环境 Win + Python 3.14.7),pytest,零运行时依赖,ruff 0.16.5,pyright。

**Spec:** 本文件的「附录 C 逐项判定表」是本次减法的规格来源——它记录了六份独立评估对每一项的 判定/修正行数/破坏面。上游背景:`docs/designs/2026-09-08-ponytail-audit-cleanup-plan.md`、`docs/designs/2026-09-12-ponytail-residual-cuts.md`。执行前必须先读附录 C 与附录 A。

## 前提与顺序决策(必须先读)

1. **顺序:减法优先。** 并发产品化计划 `docs/designs/2026-09-12-post-refactor-productize-plan.md` 已于 2026-09-12 **合并重写为总调度**：Wave A = 本计划；Wave B 按附录 A 重写后挂在减法之后。旧版「把已删 K2Node/pin 字段接进投影」的任务已废止。执行本计划时不要恢复这些字段；Wave B 步骤见总调度文件。
2. **不要动 `docs/designs/README.md`。** 它当前处于另一个会话的脏状态(已 +1 行索引,且正是这一行把 `docs_markdown` 从 45979 顶到 45980)。本计划的索引行待补,见文末「待补索引行」。
3. **HEAD 是绿的。** `0d709175`(`dev-0.6.0`)上 `python -m pytest -q` = **220 passed**。如果开跑前看到 `1 failed`(`docs_markdown` 超 ceiling)或 CI ruff 报错,那是脏工作区/既有 CI 债,不是本计划引入的;T1 负责把它们收拾干净再开工。

## 全局约束

- 本机命令前置:`$env:PYTHONPATH="E:/Develop/uasset_read/src"`(包未安装);解释器 `C:\Program Files\Python314\python.exe`。仓库根目录执行 `python -m pytest -q`。
- **零运行时依赖。** 不得新增 `[project.dependencies]`。`mappings.py` 的 brotli/zstandard 惰性 import 是既有能力边界,不要动。
- **只读解析器。** 不得引入任何写路径。永不修改 `external/`、`UnrealEngine/`、`dist/`、`build/`。
- 临时脚本与调查产物只进 `temp/`(`.gitignore` 已忽略),**不得提交**,也不得成为运行时依赖。
- 代码、注释、错误信息、提交信息一律英文。提交格式 `refactor: <summary>` 或 `fix: <summary>`,**不 push**。
- `tests/size-baseline.json` 是双向棘轮:
  - `max_lines` 是 ceiling——删除随意;**每个任务结束重新测量并按精确值收紧**,并追加**一句** `_note`。
  - `min_files` 是 floor——**当前余量为零**(src 72/72、tests 13/13)。**任何删除文件的任务必须在同一提交里下调对应 floor**,否则 `tests/test_size_baseline.py` 失败。
  - 当前值:src_python `72 / 20182`;tests_python `13 / 5862`(实测 5857);docs_markdown `151 / 45979`。
  - 测量命令见 T1 Step 1.2。
- **CI 闸门必须通过**:`.github/workflows/ci.yml` 跑 `ruff check src/uasset_read tests/` 与 `pyright src/uasset_read`。删掉一个字段却留下绑定它的局部变量/import 会让 ruff F401/F841 失败——**这是本次减法最主要的隐性成本**。
- **顺序读取器的 read 不得删。** 只有字段声明、构造 kwarg、派生解析块可删。`archive.read_*()` 必须留在原地(必要时改写为裸调用或 `_` 绑定)。
- **源码文本测试的锚点字符串必须保留**:
  - `src/uasset_read/serializers/graph_node.py` 中的 `# 5 Node type readers` 与 `dispatch handlers` 注释——`tests/test_core.py:1976-1982` 按这两个字面量切分该文件源码,删掉会 IndexError。
  - `src/uasset_read/kismet/native_fields.py` 中 `MulticastInlineDelegateProperty` 出现次数必须仍 ≥3 且 `InlineMulticastDelegateProperty` 仍为 0——`tests/test_core.py:1810-1814` 断言。
- 部分模型的字段被 wiki 记为契约面。**`wiki/` 是 gitignore 的外部仓库**(`git ls-files wiki` 为 0),其同步只能体外进行——见 **附录 B**,不要试图在同一提交里改它。
- 不修改 `tests/samples/manifest.json` 的 `fixture_gaps`(并发计划 Task 9 正在编辑它);也不降低 `T_ParserBulk` 系列的跳过守卫之外的行为预期。
- **搜索取证工具陷阱(会直接导致错误结论)**:`rg` 在路径参数被引号包裹**或传入多于一个根**时会静默返回零匹配;grep 工具在交替模式(`a|b`)下也会返回 "No files found"。**凡"零命中"前提必须用单模式 grep 工具或 `git ls-files` 之上的 Python 逐字节扫描复核**,否则视为未证实。

---

## 文件结构

本计划不新建运行时模块,只改既有文件。删减按「同一变更点聚集」分组,而非按目录:

| 任务 | 主改文件 | 职责 |
| --- | --- | --- |
| T1 | `temp/decode_parity.py`(新增,忽略提交)、`mappings.py`、`constants.py`、`property_parser.py` | parity oracle + CI 恢复绿 |
| T2 | `serializers/graph_node.py`、`docs/reference/k2node-reference.md` | 删 K2Node `node_data` 分派链 |
| T3 | `models/core.py`、`serializers/graph_pin.py`、`serializers/graph.py`、`serializers/blueprint_graph.py` | 删 pin/graph 模型只写字段 |
| T4 | `serializers/object_resources.py`、`models/properties.py`、`serializers/property_tags.py`、`parsers/property_parser.py` | 删 export/import 标志、PropertyTag 只写字段、无效 setattr |
| T5 | `serializers/graph_pin.py`、`serializers/graph_helpers.py`、`serializers/blueprint_graph.py` | 删 helper 空转与死链 |
| T6 | `parsers/property_types.py` | 删只写 schema 表 |
| T7 | `parsers/property_parser.py`、`parsers/property_types.py`、`parsers/asset_types/handlers_impl.py`、`parsers/class_specific_skip.py` | 折叠参数表、去转发器、小死代码 |
| T8 | `parsers/property_types.py` | 删 25 行不可达 struct size |
| T9 | `parsers/binary_or_native_handlers.py`、`parsers/property_types.py`、`parsers/property_parser.py`、`tests/test_core.py` | 删 UE5.7 soft-object-path 死支 |
| T10 | `kismet/ufunction_reader.py`、`kismet/native_fields.py` | 去重复构造与空转 helper |
| T11 | `kismet/expressions/*.py`、`kismet/result.py`、`kismet/decompile_bridge.py`、`kismet/expressions/__init__.py`、`kismet/bytecode_extractor.py` | 删表达式/结果只写字段 |
| T12 | `mappings.py`、`iostore.py`、18 个模块的 docstring 位置 | mappings/iostore 残留 |
| T13 | `tests/samples/manifest.json`、`tests/test_payload_extraction.py`、`tests/test_core.py`、`tests/test_unversioned_fixtures.py`、`tests/serialization/*`、`tests/size-baseline.json` | 测试树去重 |
| T14 | `.github/codeql/`、`.gitattributes`、`pyproject.toml`、`exceptions.py` 与 ruff 子集 | 配置与格式 |
| T15 | `tests/test_core.py`、`tests/test_size_baseline.py`、`docs/designs/2026-08-26-*.md`、`README.md` | `_run_cases` 重构(需授权) |
| T16 | `parsers/asset_types/handlers_impl.py`、`tests/test_blueprint_decode.py` | `--depth decode` 丢函数体缺陷修复 |

---

## Wave 0 — 闸门

### Task 1: Parity oracle + CI 恢复绿

**Files:**
- Create: `temp/decode_parity.py`(gitignored,不提交)
- Modify: `src/uasset_read/mappings.py:8,12`
- Modify: `src/uasset_read/constants.py:64`
- Modify: `src/uasset_read/parsers/property_parser.py:468`

**Interfaces:**
- Consumes: 无
- Produces: `temp/decode_parity.py record|check`;`temp/parity-baseline.json`(66 个 fixture 的 sha256)。后续所有触碰读路径/投影层的任务用它当强闸门。

- [ ] **Step 1.1: 写下 parity oracle**

`temp/decode_parity.py`:

```python
"""One-off subtraction-wave oracle: hash the projected JSON of every tracked fixture.

Not a runtime dependency. Usage:
    python temp/decode_parity.py record   # write temp/parity-baseline.json
    python temp/decode_parity.py check    # exit 1 on any difference
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = pathlib.Path(__file__).resolve().parent / "parity-baseline.json"
DEPTHS = ("package", "object", "asset", "decode")


def fixtures() -> list[pathlib.Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "tests/samples"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return sorted(ROOT / f for f in out.split("\0") if f.endswith((".uasset", ".umap")))


def digest(path: pathlib.Path, depth: str) -> str | None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.run(
        [sys.executable, "-m", "uasset_read", str(path), "--depth", depth],
        cwd=ROOT, env=env, capture_output=True,
    )
    if proc.returncode != 0:
        return None  # a fixture that already fails to parse stays "None"; not a regression signal
    return hashlib.sha256(proc.stdout).hexdigest()


def survey() -> dict[str, dict[str, str | None]]:
    return {str(p.relative_to(ROOT)): {d: digest(p, d) for d in DEPTHS} for p in fixtures()}


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    current = survey()
    if mode == "record":
        BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
        print(f"recorded {len(current)} fixtures -> {BASELINE.relative_to(ROOT)}")
        return 0
    previous = json.loads(BASELINE.read_text(encoding="utf-8"))
    diffs = [
        f"{name} {depth}: {previous[name][depth]} -> {current.get(name, {}).get(depth)}"
        for name in previous
        for depth in DEPTHS
        if previous[name][depth] != current.get(name, {}).get(depth)
    ]
    if diffs:
        print("OUTPUT CHANGED:")
        print("\n".join(diffs))
        return 1
    print(f"output identical across {len(previous)} fixtures x {len(DEPTHS)} depths")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 1.2: 记录基线并写下测量命令**

Run: `$env:PYTHONPATH="E:/Develop/uasset_read/src"; python temp/decode_parity.py record`
Expected: `recorded 66 fixtures -> temp/parity-baseline.json`

测量脚本(每个任务收尾都跑,用来收紧 `max_lines`):

```powershell
python -c "
import subprocess, pathlib
def m(p, ext):
    out = subprocess.run(['git','ls-files','-z',p],capture_output=True).stdout.decode()
    fs=[f for f in out.split('\0') if f.endswith(ext)]
    return len(fs), sum(len(pathlib.Path(f).read_bytes().splitlines()) for f in fs)
for p,ext,label in (('src','.py','src_python'),('tests','.py','tests_python'),('docs','.md','docs_markdown')):
    n,l=m(p,ext); print(f'{label}: files={n} lines={l}')"
```

- [ ] **Step 1.3: 确认基线全绿**

Run: `python -m pytest -q`
Expected: `220 passed`。若此时看到 `1 failed`(`test_docs_tree_within_baseline`),**不要改 ceiling** ——那是本工作区 `docs/designs/README.md` 的并发脏改动造成的,记录它并继续(`docs_markdown` 相关失败在本计划中不视为回归)。

- [ ] **Step 1.4: 复现 CI 红灯**

Run: `python -m ruff check src/uasset_read tests/`
Expected: FAIL,恰好 3 个错误——`mappings.py:8:20 F401 typing.Any`、`mappings.py:12:35 F401 MAX_ARRAY_DIM`、`property_parser.py:468:5 F841 mappings`。

- [ ] **Step 1.5: 删掉 4 行让 CI 恢复绿**

`src/uasset_read/mappings.py`:删除第 8 行 `from typing import Any`,并把第 12 行的 `MAX_ARRAY_DIM` 从 `from uasset_read.constants import ...` 中移除(该行只导入它一个时整行删除)。

`src/uasset_read/constants.py`:删除第 64 行 `MAX_ARRAY_DIM = ...`(删掉 import 后它成为零引用常量;已复核它不在 `wiki/07-Dev-Guide/Public-API.md:178` 的公开常量表内)。

`src/uasset_read/parsers/property_parser.py:468`:删除 `mappings = getattr(summary, "_mappings", None)`。**注意第 469 行 `game = getattr(summary, "_game", None)` 是被使用的(:529-540),必须保留。** 第 468 行的兄弟逻辑在 :1014-1015 的 `setattr(summary, "_mappings", mappings)`,一并删除(见 T7 Step 7.6)。

- [ ] **Step 1.6: 验证绿**

Run: `python -m ruff check src/uasset_read tests/`
Expected: PASS,无输出。

Run: `python -m pytest -q`
Expected: `220 passed`(或与 Step 1.3 完全相同的通过/失败组合)。

Run: `python temp/decode_parity.py check`
Expected: `output identical across 66 fixtures x 4 depths`

- [ ] **Step 1.7: Commit**

```bash
git add src/uasset_read/mappings.py src/uasset_read/constants.py src/uasset_read/parsers/property_parser.py
git commit -m "refactor: drop unused mappings imports and write-only _mappings local (unblocks ruff-check)"
```

---

## Wave 1 — 无争议减法

### Task 2: 删除 K2Node `node_data` 分派链(411 行)

**结论出处:** 附录 C 第 1 行。判定 PARTIAL(确认死,数字修正为 411)。

**Files:**
- Modify: `src/uasset_read/serializers/graph_node.py`(删除下列行区间)
- Modify: `docs/reference/k2node-reference.md:184,217-256`

**Interfaces:**
- Consumes: 无
- Produces: `create_node_from_archive(archive, name_map, summary, export_map, import_map, node_export, base_node, raw_properties=None)`(去掉 `node_refs` 参数);`_NODE_TYPE_HANDLERS` 与 `_handle_unknown_type` 消失。

**为什么能整段删:** 已用 monkeypatch 把 `_NODE_TYPE_HANDLERS` 清空后重解析 5 个真实样本,CLI 完整投影 JSON **逐字节相同**(含 933KB 的 BP_CombatCharacter)。`_read_node_pins` 按绝对偏移定位(`node_export.script_serialization_end_offset + 4`),且每个节点都重新 `archive.seek(node_export.serial_offset)`,因此 K2Node 体的读取不承担游标对齐职责。

**必须同批删的隐藏耦合:** `FunctionReference`/`EventReference` 两个分支(878-889)与它们的消费者(即上面这批 handler)**必须一起删**。只删分支会让 `_handle_call_function` 从 pins 之后的游标盲读 `FMemberReference`,向输出注入 20 条虚假低层诊断(`fstring_all_null` 16→30、`fname_index_shift_recovered` 0→2、`name_index_out_of_range` 0→4)。

**必须保留:** `_handle_full_context`(它是 `graph.py:226-238` 里 `node_data["subgraph_references"]` 的唯一生产者——ALS_AnimBP 上有 672 条子图边,删了会丢 52% 节点)、`_read_anim_graph_node`、`_handle_package_index`、`_handle_node_comment`、`_read_byte_enum_tag_name`、`_NODE_SIMPLE_TAGS`、`_read_node_property_tag`、`_read_node_pins`、`_read_node_script_serial` 的活键(`node_guid`/`node_pos_x`/`node_pos_y`/`node_comment`/`raw_properties`)、以及第 70 行的 `# 5 Node type readers` 注释(见全局约束)。

- [ ] **Step 2.1: 记录删除前状态**

Run: `python temp/decode_parity.py check`
Expected: `output identical across 66 fixtures x 4 depths`

Run: `python -m pytest -q`
Expected: `220 passed`

- [ ] **Step 2.2: 删掉 6 个已死的精确匹配 handler 与其分派表**

删除 `graph_node.py` 第 497-500 行(4 行的 `_NODE_TYPE_HANDLERS` 查询)与第 504-506 行(3 行的 unknown-type 分支),然后把第 502 行的 `elif` 改写成 `if`。结果片段:

```python
    if raw_properties:
        node_data: dict[str, Any] = dict(raw_properties)
    else:
        node_data = {}
    if not node_data:
        return node_data
    node_data["_base_node"] = base_node
    return node_data
```

(以文件实际内容为准;关键是去掉分派查询与 unknown 分支,并让剩下那一个条件成为 `if`。)

删除第 369-394 行的 `_NODE_TYPE_HANDLERS = {` 整块(**10** 行表项,不是 11)与第 351-366 行的 `_handle_unknown_type` + `_handle_raw_prop_copies`。

- [ ] **Step 2.3: 删掉 5 个死 handler 与 7 个死读取器(第 74-260 行区间)**

删除:`read_k2node_call_function`(74-102)、`read_k2node_event`(103-148)、`read_k2node_knot`(149-153)、`read_edgraph_node_comment`(154-170)、`TRIGGER_EVENT_NAMES`(172-174)、`_build_trigger_events_from_pins`(175-191)、`read_k2node_enhanced_input`(192-229)、`read_k2node_functionentry`(230-260)、`_handle_call_function`/`_handle_event`/`_handle_comment`/`_handle_enhanced_input`/`_handle_function_entry`(268-337)。

同时删除因它们而变成孤儿的级联(评估明确补上的两处,原审计漏算):

- `read_fmember_reference`(43-66 附近,26 行)——唯一调用方是上面被删的第 95/131 行。
- `_read_member_reference_from_tags`(516-571 附近,58 行)——唯一调用方是下面的 878/888 行。

- [ ] **Step 2.4: 删掉 member-reference 分支与 `node_refs` 管道**

删除第 878-889 行的 `FunctionReference`/`EventReference` 分支(12 行)。

删除 `node_refs` 全部管道:`create_node_from_archive` 的 `node_refs` 参数(第 470 行)、ctx 里的 entry(第 490 行)、`read_ue_graph_node` 里的传参(947-948 行)、以及 `_read_node_script_serial` 中 6 个死的默认键(821-826 行,`function_reference`/`event_reference` 等)。共 4 处 + 6 行。

- [ ] **Step 2.5: 取证明细表(逐段核对)**

删除跨度与行数(行号基于评估时的 `graph_node.py`,按符号定位):

| 区间 | 行 | 内容 |
| --- | --- | --- |
| 43-68 | 26 | `read_fmember_reference`(级联) |
| 74-102 | 29 | `read_k2node_call_function` |
| 103-148 | 46 | `read_k2node_event` |
| 149-153 | 5 | `read_k2node_knot` |
| 154-170 | 17 | `read_edgraph_node_comment` |
| 172-174 | 3 | `TRIGGER_EVENT_NAMES` |
| 175-191 | 17 | `_build_trigger_events_from_pins` |
| 192-229 | 38 | `read_k2node_enhanced_input` |
| 230-260 | 31 | `read_k2node_functionentry` |
| 268-337 | 70 | 5 个死 dispatch handler |
| 351-366 | 16 | `_handle_unknown_type` + `_handle_raw_prop_copies` |
| 369-394 | 26 | `_NODE_TYPE_HANDLERS`(10 行表项) |
| 497-500, 504-506 | 7 | 分派查询 + unknown 分支 |
| 516-573 | 58 | `_read_member_reference_from_tags`(级联) |
| 821-826 | 6 | `node_refs` 死默认键 |
| 878-889 | 12 | `FunctionReference`/`EventReference` 分支 |
| 470, 490, 947-948 | 4 | `node_refs` 管道 |

- [ ] **Step 2.6: 删除后必须通过源码文本测试**

Run: `python -m pytest tests/test_core.py -q -k "invented_k2node or native_fields_delegate"`
Expected: PASS。若 IndexError → 第 70 行的 `# 5 Node type readers` 注释被误删,恢复它。

- [ ] **Step 2.7: 强闸门**

Run: `python temp/decode_parity.py check`
Expected: `output identical across 66 fixtures x 4 depths`

Run: `python -m pytest -q`
Expected: `220 passed`

Run: `python -m ruff check src/uasset_read tests/`
Expected: PASS。若报 F401(未用 import)或 F821,删掉相应 import。

- [ ] **Step 2.8: 同步格式参考文档**

`docs/reference/k2node-reference.md` 第 184 行的分派示例与第 217-256 行的字段表把 `read_k2node_call_function()`、`function_reference`、`b_defaults_to_pure`、`event_reference` 写成解析器输出字段。该页**本来就已经是虚构的**(它记录了并不存在的 `read_node_data()`、`read_k2node_message()`、`read_k2node_call_delegate()`、`read_k2node_call_array_function()`、`read_k2node_macro_instance()`,且 `tests/test_core.py:1982` 还在断言 `read_k2node_message(` 不得出现)。把第 184 行的分派树改成只列真实存在的入口,并在 217-256 的字段表上加一行:

```markdown
> **状态(2026-09-12):** K2Node 体读取链已按减法波次删除——这些语义字段在 v2 投影层从未被输出。
> 若需要它们,应在投影层(`serializers/blueprint_graph.py`)重新设计,而不是恢复读者。
```

- [ ] **Step 2.9: 收紧棘轮 + commit**

Run 测量命令(Step 1.2),把 `src_python.max_lines` 设为精确值;`_note` 追加一句:

```
Tightened 2026-09-12 after the subtraction wave task 2: deleted the K2Node node_data dispatch chain (411 lines); output byte-identical across 66 fixtures x 4 depths.
```

```bash
git add src/uasset_read/serializers/graph_node.py docs/reference/k2node-reference.md tests/size-baseline.json
git commit -m "refactor: delete K2Node node_data dispatch chain (411 lines, output byte-identical)"
```

---

### Task 3: 删除 pin/graph 模型的只写字段(约 136 行)

**结论出处:** 附录 C 第 3/4/5 行。覆盖 `UEdGraphPin` 17 字段、`FEdGraphPinType` 11 字段、`UEdGraph` 4 字段、`UEdGraphNode.node_guid`/`_export_object_name`。

**Files:**
- Modify: `src/uasset_read/models/core.py`
- Modify: `src/uasset_read/serializers/graph_pin.py`
- Modify: `src/uasset_read/serializers/graph.py`
- Test: `tests/test_blueprint_decode.py`(追加一个契约钉测试)
- Modify: `tests/size-baseline.json`

**Interfaces:**
- Consumes: 无
- Produces: `UEdGraphPin` 只剩 `pin_id/pin_name/direction/pin_type/linked_to_raw`;`FEdGraphPinType` 保留 `pin_category/pin_subcategory_object/container_type/is_reference/map_key_terminal_is_const/map_key_terminal_is_weak_pointer/map_key_terminal_is_uobject_wrapper`;`UEdGraph` 只剩 `graph_name/nodes/subgraphs`;`UEdGraphNode` 去掉 `node_guid`/`_export_object_name`。

**为什么安全:** 全部 66 个 fixture 的 decode 普查里这批键一个都没出现(`pin_tooltip`/`friendly_name`/`graph_guid`/`b_editable`/`schema` 均 0 次)。唯一的读点是 `blueprint_graph.py:184-187`(pin)、`:266-271`(linked_to_raw)、`graph_node.py:179-188`(pin_type),以及 `handlers_impl.py:1177-1187`(那是**另一套**字典解码器,与这些 dataclass 无关)。

**绝不能删的东西:** `graph_pin.py:589,592,595,598,604,605,608,611,614,619,622,625,629,634` 这些 `archive.read_*()`——pin 是**顺序**读的(pin 计数在 `:773` 一次读出,不是每 pin seek),删掉会错位。只删字段声明、构造 kwarg 与派生解析块。`_read_pin_ftext_field`(469-492)必须留(它消费 FText 字节)。

**`UEdGraphNode.node_guid` 的处置:** 只删字段(`core.py:85`)与两处构造入参(`graph.py:161`、`graph_node.py:929`)。**保留** `_handle_node_guid`(它仍要烧掉 16 字节)与 `serial["node_guid"]` 这个**字典键**——它属于 `_read_node_script_serial` 的返回契约,删它收益 0 而风险非零。

- [ ] **Step 3.1: 先写契约钉测试(删除前必须已通过)**

追加到 `tests/test_blueprint_decode.py` 末尾:

```python
def test_decode_pin_payload_key_set_is_frozen():
    """The emitted pin dict carries exactly id/name/direction/category/linked.

    Write-only UEdGraphPin fields must never leak into this payload. The subtraction
    wave deletes those fields; this test is the contract that guards the emitter.
    """
    dec = _decode("StackOBot_BP_Drone.uasset", ("export:0",))
    bp = next(o for o in dec.objects if o.id == "export:0")
    graphs = bp.semantic["graphs"]
    pins = [p for g in graphs for n in g["nodes"] for p in n["pins"]]
    assert pins, "expected at least one decoded pin"
    for pin in pins:
        assert set(pin) == {"id", "name", "direction", "category", "linked"}, sorted(pin)
```

- [ ] **Step 3.2: 确认它在删除前就通过**

Run: `python -m pytest tests/test_blueprint_decode.py::test_decode_pin_payload_key_set_is_frozen -v`
Expected: PASS。若 FAIL(说明 payload 还有别的键),**停下来**,记录实际键集合,并按实际键集合重算本任务的删除范围——不要继续。

- [ ] **Step 3.3: 删 `UEdGraphPin` 的 17 个字段与 16 个构造 kwarg**

`models/core.py` 删除:`pin_friendly_name`(53)、`pin_tooltip`(54)、`default_value`(59)、`auto_default_value`(60)、`default_object`(61)、`default_text_value`(62)、`sub_pins`(65)、`parent_pin`(66)、`ref_pass_through`(67)、`hidden`(69)、`not_connectable`(70)、`advanced_view`(71)、`orphaned_pin`(72)、`owning_node_index`(74)、`source_index`(75)、`persistent_guid`(76)、`flags`(78)。保留 `pin_id`/`pin_name`/`direction`/`pin_type`/`linked_to_raw`。删除随之孤立的 5 条分组注释(58/63/68/73/77)。

`serializers/graph_pin.py` 删除构造 kwarg(639,640,643,644,645,646,648,649,650,651,652,653,654,655,656,657)。`flags` 本来就没有构造入参。

- [ ] **Step 3.4: 折叠 `_read_pin_bitfield`**

四个输出全死后,`graph_pin.py:533-549` 的 def + docstring + 4 个 flag 局部 + try/except 塌成一次调用。第 634 行改写为:

```python
    # 18. BitField (EditorOnly) — uint32 in both UE4 and UE5 (EdGraphPin.cpp L1902)
    archive.read_u32()
```

并删除 `_read_pin_bitfield` 整个函数(533-549)。

- [ ] **Step 3.5: 删 `FEdGraphPinType` 的 11 个字段**

`models/core.py` 删除:`pin_subcategory`、`pin_subcategory_object`、`pin_subcategory_object_name`、`map_key_terminal_category`、`map_key_terminal_sub_category`、`map_key_terminal_sub_category_object`、`map_key_terminal_sub_category_object_name`、`is_weak_pointer`、`is_const`、`is_uobject_wrapper`、`b_serialize_as_single_precision_float`。

**保留**(`tests/test_core.py:1948-1952` 断言):`pin_category`、`container_type`、`is_reference`、`map_key_terminal_is_const`、`map_key_terminal_is_weak_pointer`、`map_key_terminal_is_uobject_wrapper`。

`graph_pin.py:57-122` 中:`pin_subcategory_object` 的解析块(61-67)与 map-terminal 的(78-86)整块删除;其余 `archive.read_*()` 保留为裸调用。

- [ ] **Step 3.6: 删 `UEdGraphNode.node_guid` / `_export_object_name`**

`models/core.py` 删除 `node_guid`(85)与 `_export_object_name`(93)。`graph.py:161` 与 `graph_node.py:929` 去掉 `node_guid=` 入参;`graph_node.py:936` 与 `graph.py:170` 的 `setattr(base_node, "_export_object_name", ...)` 两行删除。

- [ ] **Step 3.7: 删 `UEdGraph` 的 4 个字段与 graph.py 管道**

`models/core.py` 删除 `graph_class`(102)、`schema`(103)、`graph_guid`(105)、`b_editable`(106)。

`serializers/graph.py`:
- `_extract_graph_properties` 的 Schema 分支(55-58)与 GraphGuid 分支(61-75)删除 —— 该函数只剩「返回 Nodes int list」。
- 第 113 行 `schema = schema_name` 别名删除。
- 第 172/174/181-182 的 `bEditable` 分支删除。
- `read_ue_graph` 的 `graph_class` 形参删除,更新它的 2 个调用点(`blueprint_graph.py:134`、`graph.py:204`)与返回构造(242-249 去掉 `graph_class=`/`schema=`/`graph_guid=`/`b_editable=`)。
- **`import struct` 必须保留**(135/158/220/239 用 `struct.error`);只删第 69 行的 `struct.pack`。
- `blueprint_graph.py:243` 那个 `"graph_class": class_name` 是**输出字典的键**,由本地 `resolve_class_name` 计算,与 `graph.graph_class` 字段无关 —— 不要动。

- [ ] **Step 3.8: 三闸门**

Run: `python -m pytest tests/test_blueprint_decode.py tests/test_core.py -q`
Expected: PASS(含 Step 3.1 的契约钉与 `test_map_pin_terminal_reads_trailing_bools`)。

Run: `python temp/decode_parity.py check`
Expected: `output identical across 66 fixtures x 4 depths`

Run: `python -m ruff check src/uasset_read tests/`
Expected: PASS。

- [ ] **Step 3.9: 收紧棘轮 + commit**

测量后把 `src_python.max_lines` 设为精确值;`tests_python.max_lines` 因新增测试需**上调**(记为 deliberate);`_note` 追加:

```
Tightened 2026-09-12 after subtraction wave task 3: deleted write-only pin/graph model fields; the emitted pin key set is now pinned by test_decode_pin_payload_key_set_is_frozen (tests grew by one contract test).
```

```bash
git add src/uasset_read/models/core.py src/uasset_read/serializers/graph_pin.py src/uasset_read/serializers/graph.py src/uasset_read/serializers/blueprint_graph.py tests/test_blueprint_decode.py tests/size-baseline.json
git commit -m "refactor: delete write-only pin and graph model fields (output byte-identical)"
```

---

### Task 4: 删除 export/import 标志、PropertyTag 只写字段与无效 setattr(约 51 行)

**结论出处:** 附录 C 第 6/7/12/13 行。

**Files:**
- Modify: `src/uasset_read/serializers/object_resources.py`
- Modify: `src/uasset_read/models/properties.py`
- Modify: `src/uasset_read/serializers/property_tags.py`
- Modify: `src/uasset_read/parsers/property_parser.py`

**Interfaces:**
- Consumes: 无
- Produces: `ObjectExport`/`ObjectImport` 失去下列标志;`PropertyTag` 失去 5 个只写字段;`read_property_tag` 里 `type_name` 变为局部变量。

- [ ] **Step 4.1: 删 `ObjectExport`/`ObjectImport` 的 9 个只写字段**

`serializers/object_resources.py` 删除字段声明与构造 kwarg:`b_import_optional`、`b_forced_export`、`b_not_for_client`、`b_not_for_server`、`b_is_inherited_instance`、`b_not_always_loaded_for_editor_game`、`b_generate_public_hash`(评估清单内 7 项),外加评估额外发现的 `package_flags` 与 `guid`。

**保留 `b_is_asset`**(`legacy_reader.py:268,272,625` + `tests/test_samples.py:529,657` 在用)。

每个写入形如 `b_forced_export = archive.read_bool()`,把该行改成裸的 `archive.read_bool()`(**游标必须推进**)。`package_flags`/`guid` 同理保留各自的 `archive.read_*()`。

- [ ] **Step 4.2: 删 `ObjectExport.transforms` 及其两个写入块**

`object_resources.py` 删除 `transforms` 字段(118)。`parsers/property_parser.py` 删除 615-618 与 626-629 两个写入块,以及因之孤立的 `overridden_operation = None`(596)。

`? : archive.read_u8()` 这个游标步骤必须保留 —— 只丢 `overridden_operation` 绑定。同时删除 616/627 的 `hasattr(export, "transforms")` 守卫(该字段是 `default_factory=dict`,守卫永远为真)。

- [ ] **Step 4.3: 删 6 处无效 `setattr(export, ...)`**

`parsers/property_parser.py` 删除 `:681` `parse_status="opaque_unversioned"`、`:682` `fallback_reason="missing_mapping"`、`:928` `parse_status="partial"`、`:1052` `parse_status="skipped"`、`:1053` `fallback_reason="unsupported_type"`、`:1054` `class_name=…`,以及 `:680` 的过时注释。

`ObjectExport` 不声明这三个属性;`src` 里 `export.parse_status` / `export.fallback_reason` / `export.class_name` 读取为 **0**,`__dict__`/`vars(` 在 `src` 里也为 0。可观测行为由 `PropertyFallback(reason=…)` 承担。

- [ ] **Step 4.4: 删 `PropertyTag` 的 5 个只写字段**

`models/properties.py` 删除 `struct_guid`(32)、`property_guid`(33)、`override_operation`(35)、`experimental_overridable_logic`(36)、`external_objects_byte`(37)。

每个写入形如 `tag.property_guid = archive.read_u32()`,改写为裸 `archive.read_u32()`(游标)。**这一项只省声明那 6 行,赋值行一行都省不了** —— 不要试图删整行。

- [ ] **Step 4.5: `PropertyTag.type_name` 改成局部变量**

`models/properties.py` 删除 `type_name`(39)。`serializers/property_tags.py:190-192` 改为把原第 190 行的读取赋给**局部** `type_name`,后两行照旧读该局部。除本函数外全仓无 `tag.type_name` 读取。

- [ ] **Step 4.6: 三闸门 + commit**

Run: `python -m pytest -q` → `220 passed`
Run: `python temp/decode_parity.py check` → 逐字节相同
Run: `python -m ruff check src/uasset_read tests/` → PASS(若报 F841,说明某个裸调用仍绑了局部名)

```bash
git add src/uasset_read/serializers/object_resources.py src/uasset_read/models/properties.py src/uasset_read/serializers/property_tags.py src/uasset_read/parsers/property_parser.py tests/size-baseline.json
git commit -m "refactor: delete write-only export flags, PropertyTag field block and dead export setattrs"
```

---

### Task 5: 清理 graph_pin / graph_helpers 的空转与死链(约 48 行)

**结论出处:** 附录 C 第 8/9/10/11/17 行。

**Files:**
- Modify: `src/uasset_read/serializers/graph_pin.py`
- Modify: `src/uasset_read/serializers/graph_helpers.py`
- Modify: `src/uasset_read/serializers/blueprint_graph.py`

**Interfaces:**
- Consumes: 无
- Produces: `read_pin_reference(archive)`(单参数,返回 `{"pin_guid": ...}`);`read_pin_array`/`_read_pin_ref_array` 去掉 `name_map`;`_try_recover_to_subpins` 返回 `int | None`;`_read_pin_fstring_field` 去掉 `max_length` 形参。

- [ ] **Step 5.1: 删 `read_ftext`(19 行)**

`serializers/graph_helpers.py:277-295` 整段删除。全仓唯一出现是它自己的 def;`tests/test_core.py:1907-1912` 用的是**不同**函数 `read_ftext_fstring`;`serializers/__init__.py` 是一行 docstring,不做再导出。

Run: `python -m pytest tests/test_core.py -q -k ftext`
Expected: PASS(证明删的是另一个函数)。

- [ ] **Step 5.2: 删 `name_map` 转发链与 `owning_node`**

`graph_pin.py`:
- `read_pin_reference`(124-158):函数体从不引用 `name_map`。删掉 141-151 的 owning-node 解析块与 154 的 `"owning_node"` 结果键后,`export_map`/`import_map` 也不再被用到 → 签名收缩为 `read_pin_reference(archive: FArchive) -> dict[str, str]`,返回 `{"pin_guid": ...}`。
- `read_pin_array`(161-209):只在 :206 转发 `name_map` → 去掉形参与该转发。
- `_read_pin_ref_array`(495-530):只在 :511 转发 → 同上。
- 更新 :614/:619/:622/:625 四个调用点。

`blueprint_graph.py:261` 的 docstring 本来就写着 `owning_node` "is unused",删后把该句一并去掉。

- [ ] **Step 5.3: 折叠 `_try_recover_to_subpins` 的返回**

`graph_pin.py:523-529` 的调用方**消费** `recovered_pos`,所以改成返回 `int | None` 时必须同批改写它的日志行:

```python
    recovered_pos = _try_recover_to_subpins(archive, end_token, pin_name)
    if recovered_pos is not None:
        logger.info("Pin array recovery: subpins_resync at %d for pin %s", recovered_pos, pin_name)
```

函数内两个分支的 dict 字面量各 6 行 → 各 1 行 `return recovered_pos`;删除常量局部 `recovery_type`。`archive.seek(recovered_pos)` 保留。

**警告**:该路径在 66 个 fixture 与全部测试里**一次都没被执行**(instrumentation 实测 0 次调用,`grep _try_recover_to_subpins tests` 为空)。改动只能靠阅读验证 —— 保持几何最小,不要顺手重构。

- [ ] **Step 5.4: 内联两个单调用 helper**

`blueprint_graph.py`:
- `_pin_direction`(89-91)只有一个调用点(186)→ 内联 `{0: "input", 1: "output"}.get(...)`,把 `EEdGraphPinDirection: EGPD_Input = 0, EGPD_Output = 1` 这条注释留作内联注释。
- `_collect_all_nodes`(277-284,8 行)只有一个调用点(296)→ 内联进 `resolve_pin_links`,把「emitted graph dicts carry no `subgraphs` key」这条注释留作内联注释(它记录了一个真实的未来陷阱)。

- [ ] **Step 5.5: 内联 `max_length` 默认值**

`graph_pin.py:448-453` 去掉 `max_length: int = 4096` 形参(3 个调用点 595/604/605 都没传),并在 :458 显式写 `_read_fstring_safe(archive, max_length=4096)`。**不要删掉 4096** —— `_read_fstring_safe` 自己的默认是 `MAX_SAFE_COUNT`,两者不同。

- [ ] **Step 5.6: 三闸门 + commit**

Run: `python -m pytest -q` → `220 passed`
Run: `python temp/decode_parity.py check` → 逐字节相同
Run: `python -m ruff check src/uasset_read tests/` → PASS

```bash
git add src/uasset_read/serializers/graph_pin.py src/uasset_read/serializers/graph_helpers.py src/uasset_read/serializers/blueprint_graph.py tests/size-baseline.json
git commit -m "refactor: drop dead graph_pin name_map chain, owning_node resolution and single-caller helpers"
```

---

### Task 6: 删除只写 schema 表 `_TAGGED_FALLBACK_STRUCT_SCHEMAS`(96 行)

**结论出处:** 附录 C 第 18 行。判定 CONFIRM。`git log -S` 溯源证明历史上唯一的读者是**已被删除的测试**(`tests/temp/test_issue_515_candidate_selection.py`、`tests/test_issue_522_cube_builder_metadata.py`),不是被删的解析器。

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`

**Interfaces:**
- Consumes: 无
- Produces: `_TAGGED_FALLBACK_STRUCTS`(活的,用于 `:979/:1030/:1110`)不变;`_TAGGED_FALLBACK_STRUCT_SCHEMAS`、`_register_schema_alias` 消失。

- [ ] **Step 6.1: 先复核零读者(必须单模式搜)**

用单模式 grep 工具分别搜 `_TAGGED_FALLBACK_STRUCT_SCHEMAS` 与 `_register_schema_alias`。
Expected: 前者只出现在 `property_types.py`(def + `:261` docstring 散文 + 5 处 alias 入参)与 `docs/designs/archive/issue-521-completion-plan-2.md`(归档文档,不要回改);后者只出现在 `property_types.py`。

**若出现任何读取(`.get(` 或下标),停止本任务。**

- [ ] **Step 6.2: 删除 96 行块**

`property_types.py` 删除第 264-359 行:`_TAGGED_FALLBACK_STRUCT_SCHEMAS: dict[str, list[tuple[str, str]]] = {` 起、到第 345 行 `}`、含第 348 行 `def _register_schema_alias(schemas: dict, canonical: str, *aliases: str) -> None:` 与第 355-359 的 5 次调用。

- [ ] **Step 6.3: 修掉现在为假的 docstring**

`_TAGGED_FALLBACK_STRUCTS` 的 docstring(:260-261)写着「use the field lists defined in `_TAGGED_FALLBACK_STRUCT_SCHEMAS` for fallback parsing」。删表后这句是假的,把那两句指向 schema 表的散文删掉,只留集合本身的语义。

- [ ] **Step 6.4: 闸门 + commit**

Run: `python -m pytest -q` → `220 passed`
Run: `python temp/decode_parity.py check` → 逐字节相同

```bash
git add src/uasset_read/parsers/property_types.py tests/size-baseline.json
git commit -m "refactor: delete write-only _TAGGED_FALLBACK_STRUCT_SCHEMAS table (its readers were deleted in prior waves)"
```

---

### Task 7: 折叠参数表 + 去转发器 + 小死代码(约 73 行)

**结论出处:** 附录 C 第 19/20/21/23/24/25/26/27/28/30/31/32 行。

**Files:**
- Modify: `src/uasset_read/parsers/property_parser.py`
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `src/uasset_read/parsers/asset_types/handlers_impl.py`
- Modify: `src/uasset_read/parsers/class_specific_skip.py`

**Interfaces:**
- Consumes: 无
- Produces: `_ARGS_DEFAULT` / `_ARGS_OVERRIDES`(取代 `_PROPERTY_ARGS`);`parse_soft_class_property` 消失(`SoftClassProperty` 直指 `parse_soft_object_property`);新增 `_split_inner(inner, default)`;`_capability_tier` 消除。

- [ ] **Step 7.1: 复核 `_PROPERTY_ARGS` 基线(实测,不要凭信)**

```powershell
$env:PYTHONPATH="E:/Develop/uasset_read/src"; python -c "
from uasset_read.parsers.property_parser import _PROPERTY_ARGS, _get_parse_functions
from collections import Counter
print('keys', len(_PROPERTY_ARGS), len(_get_parse_functions()), set(_PROPERTY_ARGS) == set(_get_parse_functions()))
print(Counter(_PROPERTY_ARGS.values()))"
```
Expected: `keys 43 43 True`,且恰好 **7 种**不同元组:28×`("tag","archive")`、6×+`name_map`、3×+`export_map,summary`、2×+`soft_path_list,summary`、2×+`export_map,summary,depth`、1×`("tag","archive","dev_notes")`、1×+`name_map,summary`。

- [ ] **Step 7.2: 折叠为默认 + 15 项 override(59 → 18 行)**

删除第 199-257 行整块,替换为:

```python
# Positional args parse_property_value passes each handler. Only the deviations from
# the ("tag", "archive") default are listed; names index the `values` dict below.
_ARGS_DEFAULT: tuple[str, ...] = ("tag", "archive")
_ARGS_OVERRIDES: dict[str, tuple[str, ...]] = {
    "TextProperty": ("tag", "archive", "dev_notes"),
    "NameProperty": ("tag", "archive", "name_map"),
    "DelegateProperty": ("tag", "archive", "name_map"),
    "MulticastDelegateProperty": ("tag", "archive", "name_map"),
    "MulticastInlineDelegateProperty": ("tag", "archive", "name_map"),
    "MulticastSparseDelegateProperty": ("tag", "archive", "name_map"),
    "FieldPathProperty": ("tag", "archive", "name_map"),
    "EnumProperty": ("tag", "archive", "name_map", "summary"),
    "SoftObjectProperty": ("tag", "archive", "name_map", "summary"),
    "SoftClassProperty": ("tag", "archive", "name_map", "summary"),
    "MapProperty": ("tag", "archive", "name_map", "export_map", "summary"),
    "SetProperty": ("tag", "archive", "name_map", "export_map", "summary"),
    "OptionalProperty": ("tag", "archive", "name_map", "export_map", "summary"),
    "ArrayProperty": ("tag", "archive", "name_map", "export_map", "summary", "depth"),
    "StructProperty": ("tag", "archive", "name_map", "export_map", "summary", "depth"),
}
```

第 568 行调用点改为:

```python
        return handler(*(values[n] for n in _ARGS_OVERRIDES.get(tag.type, _ARGS_DEFAULT)))
```

第 549-550 行的 `ByteProperty` 特例调用**保持原样**(它不查表),并在其上方加注释说明该特例绕过参数表。

注:`SoftObjectProperty`/`SoftClassProperty` 两项此处先写成不含 `soft_path_list` —— T9 会删掉该参数,若 T9 先执行则本步照 T9 之后的状态写即可;两个任务不得各自留下半截。

- [ ] **Step 7.3: 验证折叠逐字节等价**

Run: `python temp/decode_parity.py check`
Expected: `output identical across 66 fixtures x 4 depths`

- [ ] **Step 7.4: 删 `parse_soft_class_property` 转发器(10 行)**

`property_types.py` 删除第 530-538 的 def(9 行)+ 空行;`property_parser.py:129` 删除它的 import;`_TYPE_HANDLER_MAP` 中把 `"SoftClassProperty"` 直指 `parse_soft_object_property`。

已复核:`parse_soft_object_property` 的位置参数槽与 `SoftClassProperty` 的参数元组同序同数(`tag/archive/name_map/soft_object_path_list/summary`)。

- [ ] **Step 7.5: 抽 `_split_inner` 去重(10 行)**

`property_types.py` 中 `_extract_enum_type_from_tag`(约 :1473)与 `_extract_struct_type_from_tag` 共享一段逐字节相同的 6 行尾部。新增模块级 helper:

```python
def _split_inner(inner: str | None, default: str) -> str:
    """Return the last dotted segment of *inner*, or *default* when absent."""
    return default if inner is None else inner.rsplit(".", 1)[-1]
```

两个函数改为调用它。struct 版的 `getattr(tag, "struct_type", None)` 快路径**逐字保留**(评估指出那条快路径正是两者唯一的结构差异)。

`rsplit` 改写已在 `None, "", "a", "a.b", "a.b.", ".b", "x.y.z", "FVector"` 上验证等价。

- [ ] **Step 7.6: 内联 `_capability_tier`(9 行)**

`handlers_impl.py` 删除第 64-74 的 def + docstring,在第 103 行原地内联:

```python
    cap = getattr(handler, "capability", "summary")
    tier = str(cap(result)) if callable(cap) else str(cap)
    if tier == "decoded":
```

两种形态(`capability = "decoded"` 字符串,以及 `:585/:724/:1049` 的绑定方法)都被这 3 行覆盖。

- [ ] **Step 7.7: 删 `summary._mappings` 往返与小项**

`property_parser.py` 删除 `:1014-1015` 的 `if mappings is not None: setattr(summary, "_mappings", mappings)`(第 468 行已由 T1 Step 1.5 删除)。

**注意**:`parse_property_value` **没有** `mappings` 形参(形参是 `tag, archive, name_map, export_map, summary, depth, tolerant`),所以 `:468` 的局部是纯粹未被读取,不是遮蔽。活的 `mappings` 参数属于 `:643/:791/:991/:1116/:1302` 等**其他**函数,且被 `tests/test_core.py:1086-1126` 两个 spy 测试盯着 —— 不要动。

同批三项:

- `property_parser.py:260` `_skip_type_tree_nodes` 去掉未用的 `name_map` 形参(与其 docstring 一行),更新 `:420` 调用点(`map_len = len(name_map)` 已在 `:342` 算好)。
- `property_parser.py:410` `first_idx, first_ic = ...` → `first_idx, _ = ...`(0 行变化;ruff F841 不抓元组解包目标,所以它一直存活)。
- `class_specific_skip.py:28` 删除 `"NiagaraNodeParameterMapGet"` —— 唯一消费方是一次 `str.startswith(tuple)`,而 `"NiagaraNode"` 在同元组内,匹配前者者必匹配后者,顺序无关。

- [ ] **Step 7.8: 闸门 + commit**

Run: `python -m pytest -q` → `220 passed`
Run: `python temp/decode_parity.py check` → 逐字节相同
Run: `python -m ruff check src/uasset_read tests/` → PASS

```bash
git add src/uasset_read/parsers/property_parser.py src/uasset_read/parsers/property_types.py src/uasset_read/parsers/asset_types/handlers_impl.py src/uasset_read/parsers/class_specific_skip.py tests/size-baseline.json
git commit -m "refactor: fold property arg table into handler map; drop soft-class forwarder and small dead parser code"
```

---

### Task 8: 删除 25 行不可达的 `_EXPECTED_STRUCT_SIZES`(25 行)

**结论出处:** 附录 C 第 22 行。独立复算:60 行中 25 行被 LWC 表遮蔽,35 行可达。

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Test: `tests/test_core.py`(追加 characterization 测试)

**Interfaces:**
- Consumes: 无
- Produces: `_EXPECTED_STRUCT_SIZES` 只剩可达的 35 行;`_LWC_TYPE_MAP`/`_LWC_DOUBLE_TYPE_TO_BASE`/`_LWC_FLOAT_TYPE_TO_BASE` 不变(`tests/test_core.py:471` import `_LWC_TYPE_MAP`)。

**机制:** `get_struct_size`(:185-201)对三个 LWC 表的成员提前 `return`,所以这些名字永远走不到 `:204` 的 `_EXPECTED_STRUCT_SIZES.get(...)`。

- [ ] **Step 8.1: 写 characterization 测试(删除前通过、删除后仍通过)**

追加到 `tests/test_core.py` **模块级**(不要放进 T15 才重构的 `_run_cases`):

```python
def test_get_struct_size_matches_lwc_tables_for_shadowed_names():
    """Names present in the LWC tables are served by the LWC branch, never by the
    _EXPECTED_STRUCT_SIZES fallback. Pins the values the subtraction wave relies on."""
    from uasset_read.parsers.property_types import get_struct_size

    expected = {
        "Vector": (12, 24),
        "Rotator": (12, 24),
        "Vector2D": (8, 16),
        "Quat": (16, 32),
        "Vector3f": (12, 12),
        "Rotator3f": (12, 12),
    }
    for name, (float_size, double_size) in expected.items():
        assert get_struct_size(name, 0) == float_size, name
        assert get_struct_size(name, 1005) == double_size, name
```

- [ ] **Step 8.2: 运行,确认通过(characterization 基线)**

Run: `python -m pytest tests/test_core.py::test_get_struct_size_matches_lwc_tables_for_shadowed_names -v`
Expected: PASS。若 FAIL,**停止** —— 说明遮蔽前提不成立,`get_struct_size` 的早返回顺序与评估不符,需重新评估而不是删除。

- [ ] **Step 8.3: 独立复算遮蔽集合**

```powershell
$env:PYTHONPATH="E:/Develop/uasset_read/src"; python -c "
from uasset_read.parsers import property_types as p
exp=set(p._EXPECTED_STRUCT_SIZES)
shadow=exp & (set(p._LWC_TYPE_MAP)|set(p._LWC_DOUBLE_TYPE_TO_BASE)|set(p._LWC_FLOAT_TYPE_TO_BASE))
print('total', len(exp), 'shadowed', len(shadow), 'reachable', len(exp)-len(shadow))
print(sorted(shadow))"
```
Expected: `total 60 shadowed 25 reachable 35`,名单为:

```
Vector, Rotator, Vector2D, Vector4, Quat, Plane, Box, Sphere, BoxSphereBounds,
Matrix, TwoVectors, Transform, Vector2f, Vector3f, Vector3d, Vector4f, Vector4d,
Rotator3f, Rotator3d, Quat4f, Quat4d, Plane4f, Plane4d, Sphere3f, Sphere3d
```

- [ ] **Step 8.4: 删除这 25 行**

`property_types.py` 删除第 43,44,45,46,49,50,55,56,57,58,59,61 行(12 行)与第 88-100 行(13 行)。同时删除第 87 行那条分节注释 `# UE5 LWC math types`(删掉这些名字后,它会错误地统领仍可达的 `Box2f/Box3f/Matrix44f/Transform3f`)。

- [ ] **Step 8.5: 闸门 + commit**

Run: `python -m pytest -q` → `220 passed`(含 Step 8.1 的新测试)
Run: `python temp/decode_parity.py check` → 逐字节相同

```bash
git add src/uasset_read/parsers/property_types.py tests/test_core.py tests/size-baseline.json
git commit -m "refactor: delete 25 unreachable _EXPECTED_STRUCT_SIZES rows shadowed by the LWC tables"
```

---

### Task 9: 删除不可达的 UE5.7 soft-object-path 分支(59 行)

**结论出处:** 附录 C 第 21 行。producer 在 `ae8027e1`(#621 v1 流水线移除)被连带删除,只剩消费方;`read_soft_object_paths` 现在全仓 0 命中。

**Files:**
- Modify: `src/uasset_read/parsers/binary_or_native_handlers.py`
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `src/uasset_read/parsers/property_parser.py`
- Modify: `tests/test_core.py`

**Interfaces:**
- Consumes: T7 的 `_ARGS_OVERRIDES`(本任务会改动其中两项)
- Produces: `parse_soft_object_property(tag, archive, name_map, summary)`(去掉 `soft_object_path_list` 形参);`_decode_soft_object_path_index` 与 `values["soft_path_list"]` 消失。

**必须先改测试(否则静默错位):** `tests/test_core.py:577-579` 与 `:587-589` 把 `None` **按位置传在第 4 个参数**。删掉形参而不改测试,会把 `None` 静默重绑给 `summary`。

- [ ] **Step 9.1: 复核零 producer**

分别单模式搜 `_soft_object_path_list` 与 `read_soft_object_paths`。
Expected: 前者只有 2 处 `getattr(summary, "_soft_object_path_list", None)` 读取(`property_parser.py:565`、`binary_or_native_handlers.py:310`)+ 1 条注释 + 2 处测试传 `None`;后者 0 命中。**任何赋值都意味着前提不成立,停止。**

- [ ] **Step 9.2: 改测试的调用形态**

`tests/test_core.py:575-589`:删掉两处 `_soft_object_path_list=None` kwarg,并去掉位置参数列表里的第 4 个 `None`,使其与新签名 `parse_soft_object_property(tag, archive, name_map, summary)` 对齐。

- [ ] **Step 9.3: 删消费侧(59 行)**

- `binary_or_native_handlers.py:305` `_decode_soft_object_path_index`(27 行 + 空行)与 `:493-496` 的调用点(4 行)。
- `property_types.py:478` `parse_soft_object_property` 的 `if soft_object_path_list is not None ... else:` 半支(20 行)、形参(1 行)、docstring 相关一行。
- `property_parser.py:565` 的 `"soft_path_list": getattr(...)` 条目(1 行)。
- T7 的 `_ARGS_OVERRIDES` 中 `SoftObjectProperty`/`SoftClassProperty` 已按 T7 Step 7.2 的注记写成 4 元组,本步无需再改;若 T7 写在 `soft_path_list` 之前,则本步把这两项改为 `("tag", "archive", "name_map", "summary")`。
- 该分支上方若有说明性注释,一并删(1 行)。

- [ ] **Step 9.4: 闸门 + commit**

Run: `python -m pytest -q` → `220 passed`(特别是 `test_soft_object_path_inline_is_fname_based`)
Run: `python temp/decode_parity.py check` → 逐字节相同

```bash
git add src/uasset_read/parsers/binary_or_native_handlers.py src/uasset_read/parsers/property_types.py src/uasset_read/parsers/property_parser.py tests/test_core.py tests/size-baseline.json
git commit -m "refactor: delete unreachable UE5.7 soft-object-path index branch (producer removed in ae8027e1)"
```

---

### Task 10: ufunction_reader 去重构造 + native_fields 空转 helper(约 98 行)

**结论出处:** 附录 C 第 29/33 行。

**Files:**
- Modify: `src/uasset_read/kismet/ufunction_reader.py`
- Modify: `src/uasset_read/kismet/native_fields.py`

**Interfaces:**
- Consumes: 无
- Produces: `_make_failure(export, export_index, code, msg, *, class_name=None, bytecode_buffer_size=None, serialized_script_size=None)`(扩 3 个关键字参数);`_make_invalid_script_size_failure` 消失;`_read_metadata` 返回 `None`;三个 tail forwarder 内联。

- [ ] **Step 10.1: 扩展 `_make_failure` 并消灭 4 处手写构造(约 70 行)**

`ufunction_reader.py:88-102` 的 `_make_failure` 当前 7 个字段硬编码。把它扩展为:

```python
def _make_failure(
    export,
    export_index: int,
    error_code: str,
    error_message: str,
    *,
    class_name: str | None = None,
    bytecode_buffer_size: int | None = None,
    serialized_script_size: int | None = None,
) -> FunctionScriptFailure:
    return FunctionScriptFailure(
        error_code=error_code,
        error_message=error_message,
        function_name=export.object_name,
        export_index=export_index,
        class_name=class_name or (resolve_class_name(export.class_index, [], [export]) or "Unknown"),
        package_offset=export.serial_offset,
        export_offset=export.serial_offset,
        bytecode_buffer_size=bytecode_buffer_size,
        serialized_script_size=serialized_script_size,
    )
```

然后把这四处逐字段核对后压成一次调用:

| 原位置 | 行数 | 额外参数 |
| --- | --- | --- |
| `:326-337`(`validation[0]/[1]`) | 12 | 无 |
| `:351-367`(`truncated_script`) | 17 | `bytecode_buffer_size=`、`serialized_script_size=` |
| `:381-392`(`read_error`) | 12 | 无 |
| `:482-493`(`not_function_export`) | 12 | `class_name=class_name or "Unknown"`(这里的 `class_name` 来自真实 `import_map` 解析,`status="no_script"` 也要保留) |

再删除 `_make_invalid_script_size_failure`(`:425-442`,18 行)并把它的 **3 个调用点**(`:272-276`、`:278-282`、`:294-298`,15 行)压成单行 `_make_failure(...)` 调用 —— 这是原审计**双算并漏算**的部分,实际收益比它估的 45 行更大。

`class_name` 的占位默认必须与被替换的代码逐字一致(评估已逐字段核对三处完全匹配)。

- [ ] **Step 10.2: 验证错误输出逐值不变**

错误码/错误消息/`error_context.class_name`/`script_metrics.bytecode_buffer_size` 与 `serialized_script_size` 都由 `decompile_bridge.py:94-116` 投影出去。逐字段核对后:

Run: `python -m pytest tests/test_blueprint_decode.py -q`
Expected: PASS(`test_kismet_one_failed_function_keeps_others`、`test_kismet_result_status_serializations`、`test_extract_bridge_one_failure_keeps_sibling_functions` 是这一项的守卫)

- [ ] **Step 10.3: 处理 `_read_metadata`**

`native_fields.py:153` 的调用**不能删** —— 它的函数体读一个 bool,为真时再读 `count` + `count`×(FName, FString),是真实的游标推进。只做两件事:

- 删除未读的 `_metadata =` 赋值目标(调用改成裸调用)。
- 删除 `:198-204` 的 dict 累积(3 行)与 `-> dict[str, str]` 返回注解 / docstring 中的对应一行(共约 5 行)。

- [ ] **Step 10.4: 内联三个 tail forwarder(约 23 行)**

`native_fields.py`:删除 `_read_class_tail`(8 行)、`_read_map_tail`(9 行)、`_read_bool_tail`(4 行),把各自唯一调用点(:378、:395、:372)就地展开 —— 它们分别只是 2× `_read_single_ref_tail` / 2× `_read_inner_field_tail` / 6× `read_u8` 的纯转发。

**取舍说明:** 这会牺牲三行「Class/SoftClassProperty: base class ref + meta-class ref」式的布局说明。若评审认为对称性更重要(它们与 `_read_single_ref_tail`/`_read_enum_tail`/`_read_inner_field_tail`/`_read_fieldpath_tail` 同形),**可以只保留它们、放弃这 23 行收益**;不要用注释去替代。

- [ ] **Step 10.5: 源码文本测试必须仍通过**

Run: `python -m pytest tests/test_core.py -q -k native_fields_delegate`
Expected: PASS。`native_fields.py` 中 `MulticastInlineDelegateProperty` 出现次数必须仍 ≥3 且 `InlineMulticastDelegateProperty` 必须仍为 0。

- [ ] **Step 10.6: 闸门 + commit**

Run: `python -m pytest -q` → `220 passed`
Run: `python temp/decode_parity.py check` → 逐字节相同
Run: `python -m ruff check src/uasset_read tests/` → PASS(本步最容易踩 F841:删了字段却留下绑定的局部名)

```bash
git add src/uasset_read/kismet/ufunction_reader.py src/uasset_read/kismet/native_fields.py tests/size-baseline.json
git commit -m "refactor: deduplicate FunctionScriptFailure construction; inline native-field tail forwarders"
```

---

### Task 11: 删除 kismet 表达式与结果的只写字段(约 105 行)

**结论出处:** 附录 C 第 34/35/36/37 行。

**Files:**
- Modify: `src/uasset_read/kismet/expressions/{containers,context,rtfm,special,casts,string_consts,vector_consts}.py`
- Modify: `src/uasset_read/kismet/result.py`
- Modify: `src/uasset_read/kismet/decompile_bridge.py`
- Modify: `src/uasset_read/kismet/native_fields.py`
- Modify: `src/uasset_read/kismet/expressions/__init__.py`
- Modify: `src/uasset_read/kismet/bytecode_extractor.py`

**Interfaces:**
- Consumes: 无
- Produces: 若干表达式类退化为「token-only + 只推进游标的 `from_archive`」;`KismetDecompiledResult` 去掉 7 个字段,`build_native_function_signature` 只返回签名字符串。

**机制(必须先理解):** `KismetExpression.to_dict()`(`expressions/base.py:35-40`)只发 `{Inst, StatementIndex}`;`KismetExpressionT.to_dict` 追加 `Value`;`result.py:70-72` 先 `asdict(self)` 再把 `d["expressions"]` **覆盖**成手写 `to_dict()` 列表 —— 所以没有 `to_dict` 覆写的类,其 dataclass 字段既不被读也不被输出。

**必须逐个字段核,不能按模块整砍:** 评估**推翻**了「`EX_AutoRtfm*` 整桶死」的说法。以下是**在别处被读**的字段,不得删除:

- `EX_AutoRtfmTransact.CodeOffset`(`bytecode_extractor.py:140`)
- `EX_SwitchValue.EndGotoOffset`(:136)、`EX_SwitchValue.Cases`(:137)
- `FKismetSwitchCase.NextOffset`(:138)
- `EX_SetSet.Num`(`tests/test_core.py:1900`)、`EX_Assert.LineNumber`/`DebugMode`(:1896)
- `FScriptText.SourceString`/`KeyString`/`Namespace`/`TableIdString`(:1854-1859)
- `EX_TextConst.Text`(它自己的 `to_dict` 读)

同名字段跨类存在(`EX_RotationConst.Pitch` vs `EX_TransformConst.Pitch`;`EX_CastBase.Target` vs `EX_Cast.Target`),**按字段全名核,不要按名字核**。

- [ ] **Step 11.1: 先建可复现的字段普查脚本**

`temp/kismet_field_audit.py`(gitignored):

```python
"""Enumerate expression dataclass fields and diff them against emitted to_dict keys."""
from __future__ import annotations

import dataclasses
import importlib
import inspect
import pathlib
import pkgutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import uasset_read.kismet.expressions as expr_pkg  # noqa: E402


def main() -> None:
    root = pathlib.Path(expr_pkg.__file__).parent
    for mod in pkgutil.iter_modules([str(root)]):
        m = importlib.import_module(f"uasset_read.kismet.expressions.{mod.name}")
        for name, obj in vars(m).items():
            if not (inspect.isclass(obj) and dataclasses.is_dataclass(obj)):
                continue
            if obj.__module__ != m.__name__:
                continue
            fields = {f.name for f in dataclasses.fields(obj)}
            if not fields:
                continue
            emitted = set()
            try:
                inst = obj.__new__(obj)
                for f in dataclasses.fields(obj):
                    setattr(inst, f.name, None)
                inst.StatementIndex = 0
                emitted = set(inst.to_dict())
            except Exception as exc:  # pragma: no cover - audit aid
                print(f"  !! {name}: {exc}")
            missing = fields - emitted - {"StatementIndex", "Value"}
            if missing:
                print(f"{m.__name__.rsplit('.', 1)[-1]}.{name}: {len(missing)} not emitted -> {sorted(missing)}")


if __name__ == "__main__":
    main()
```

Run: `python temp/kismet_field_audit.py | Tee-Object temp/kismet-fields.txt`
Expected: 一份「类 → 未输出字段」清单。**以此清单为准**执行 Step 11.2;若清单与本节列名不一致,以清单为准并在提交信息里记录差异。

- [ ] **Step 11.2: 逐字段删除(约 42 行点名 / 约 70 行全量)**

按 Step 11.1 的清单删除字段声明与构造 kwarg。已点名的确认死集(可作交叉验证):`EX_SetArray.ArrayInnerProp`(仅声明、从未写入)、`EX_MapConst.KeyProperty`/`ValueProperty`、`EX_Context.ObjectExpression`/`RValuePointer`/`ContextExpression`、`EX_InterfaceContext.InterfaceValue`、`EX_StructMemberContext.StructExpression`、`EX_Return.ReturnExpression`、`EX_SwitchValue.IndexTerm`/`DefaultTerm`、`FScriptText.StringTableAsset`(仅声明)、`EX_SoftObjectConst.SoftObject`、`EX_TransformConst.{X,Y,Z,W,Pitch,Yaw,Roll,SX,SY,SZ}`(整类缺覆写,共 **10** 个)、`FKismetSwitchCase.CaseIndexValueTerm`/`CaseTerm`、`EX_InstrumentationEvent.EventType`/`EventName`、`EX_ArrayGetByRef.ArrayVariable`/`ArrayIndex`、`EX_SetMap.Elements`、`EX_SetSet.Elements`、`EX_Cast.Target`、`EX_FieldPathConst.Value`、`EX_Assert.AssertExpression`、`EX_AutoRtfmTransact.Id`、`EX_AutoRtfmStopTransact.Id`/`Mode`、`EX_AutoRtfmAbortIfNot.BoolExpression`。

每个 `from_archive` 里对应的解析调用**必须保留**,但改成**不绑定**的裸调用(绑定会触发 F841):

```python
    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_SetArray:
        # UE5's post-VER_UE4_CHANGE_SETARRAY_BYTECODE layout serializes the
        # array target as an expression, not as a bare FProperty pointer.
        archive.read_expression()
        archive.read_expression_array(EExprToken.EX_EndArray)
        return cls()
```

`EX_InstrumentationEvent` 的局部 `evt_type` **必须保留** —— 它在 `:122-124` 决定是否继续读 FName。

**不要动** `from_archive(cls, archive, name_map)` 的两参数协议(53 处,2026-09-12 计划 Task 5 Step 5.3 明确接受)。

- [ ] **Step 11.3: 删 `KismetDecompiledResult` 的 7 个字段(约 33 行)**

`kismet/result.py:48-60` 删除:`local_variables`、`warnings`、`function_ref_stats`、`bytecode_source`、`parameters`、`return_type`、`native_signature`。

**保留**:`function_name`、`signature`、`bytecode_status`、`expressions`、`error_code`、`error_message`、`error_context`、`script_metrics`、`fallback_reasons` —— 这 9 个是 `handlers_impl.py:1060-1097` 白名单**真实输出**的键(实测:asset 深度各 45 次、decode 深度各 3 次)。

同批:
- `decompile_bridge.py` 的 5 处 `bytecode_source=` kwarg(64/92/142/186/201)与 `parameters=`/`return_type=`/`native_signature=`(:188-190)、`function_ref_stats={}`(:191)。
- `build_native_function_signature` 只返回签名字符串(它只有 1 个调用方,`decompile_bridge.py:172`);**同批删除** `native_params`/`native_return_type`/`native_signature_used` 三个局部,否则 ruff F841 会让 CI 变红。
- `native_fields.py:436-485` 随之为签名返回而收缩;`_CPF_OutParm`(:430)变成未用,一并删。

- [ ] **Step 11.4: 小项(约 5 行)**

- `kismet/expressions/__init__.py:7,9`:删除 `EXPR_CLASS_MAP` 的 import 与再导出(`from uasset_read.kismet.expressions import ...` 全仓 0 命中;`archive.py:10` 直接从 `_map` 导入)。同时修正 `:3-4` 那句「re-exported here for the archive dispatcher」的假说明。
- `kismet/bytecode_extractor.py:147-149`:删除尾部悬空的 `# Output formatting (BYTECODE-03)` 分节横幅(文件到 149 行为止,横幅下没有任何内容)。

- [ ] **Step 11.5: 闸门 + commit**

Run: `python -m pytest tests/test_blueprint_decode.py tests/test_core.py -q`
Expected: PASS。若 Step 11.2 误删了「必须保留」列表里的字段,这里会红。

Run: `python temp/decode_parity.py check` → 逐字节相同
Run: `python -m ruff check src/uasset_read tests/` → PASS

```bash
git add src/uasset_read/kismet src/uasset_read/parsers tests/size-baseline.json
git commit -m "refactor: delete write-only kismet expression and result fields (never emitted by the K0 whitelist)"
```

---

### Task 12: mappings / iostore 残留 + 模块 docstring 位置(约 33 行)

**结论出处:** 附录 C 第 38/39/40/41/42 行。

**Files:**
- Modify: `src/uasset_read/mappings.py`
- Modify: `src/uasset_read/iostore.py`
- Modify: `src/uasset_read/kismet/decompile_bridge.py`、`src/uasset_read/memory_safety.py`、`src/uasset_read/parsers/{class_specific_skip,custom_properties,property_parser,property_types}.py`、`src/uasset_read/serializers/package_summary.py`、`src/uasset_read/kismet/expressions/*.py`(docstring 位置)

**Interfaces:**
- Consumes: 无
- Produces: `TypeMappings` 去掉 `enums`;`PropertyType` 去掉 `is_enum_as_byte`;`extract_kismet_decompiled` / `open_package_bundle` / `_read_native_payload_start` / `_consume_tagged_properties` 去掉未用参数;iostore 去掉 2 常量 + 8 字段。

- [ ] **Step 12.1: 删 `TypeMappings.enums`,但**保留** usmap 枚举块的读取(7 行)**

`mappings.py:105` 删除 `enums` 字段。`mappings.py:209-222` 的枚举解析循环**不能整段删** —— `_BytesReader`(126-159)是纯顺序游标、没有 seek,删掉读取会让后续 struct 解析错位。实测证据:删 209-222 后解析 `tests/samples/UnversionedTest.usmap` 报 `ParseError: Usmap name index out of bounds: 10420224`(枚举块 748 字节被当成 name index)。

把该循环降为「只推进游标」:

```python
        enum_count = ar.u32()
        for _ in range(enum_count):
            ar.name(name_lut)
            value_count = ar.u16() if version >= 3 else ar.u8()
            for _ in range(value_count):
                if version >= 4:
                    ar.u64()
                ar.name(name_lut)
```

Run: `python -m pytest tests/test_unversioned_fixtures.py -q`
Expected: PASS(该文件会在 T13 里精简,但 usmap 解析断言必须保留)。

- [ ] **Step 12.2: 删 `PropertyType.is_enum_as_byte`(1 行)**

`mappings.py:70` 整行删除(全仓唯一出现是声明本身)。

- [ ] **Step 12.3: 删 4 处未用参数(8 行)**

| 位置 | 改动 |
| --- | --- |
| `kismet/decompile_bridge.py:24` | 去掉 `path: str`;`legacy_reader.py:1204` 相应删掉 `str(archive._path) if hasattr(archive, "_path") else ""` 那个纯为它服务的实参计算 |
| `package.py:181` | `open_package_bundle` 去掉 `tolerant`(函数体从不引用);3 个调用点(`package.py:224`、`tests/test_unversioned_fixtures.py:217,232`)同步 |
| `kismet/ufunction_reader.py:127-128` | `_read_native_payload_start` 去掉 `import_map`/`export_map`(函数体只用 `archive/export/summary/name_map/export_index`) |
| `kismet/ufunction_reader.py:204` | `_consume_tagged_properties` 去掉 `summary`(函数体只用 `archive`/`name_map`) |

`_read_ustruct_prefix_and_script` 的 `import_map`/`export_map` **确实被使用**(`:306-307`),不要动。

`tests/test_blueprint_decode.py:380-388` 按位置传 `str(sample)` 给 `extract_kismet_decompiled`,同批改掉。

- [ ] **Step 12.4: iostore 残留(20-26 行)— 需显式推翻旧决策**

**前置:这一项推翻了 2026-09-08 计划 Step 7.2 的明文「Keep all `FLAG_*`/`META_*` constants」。** 该步的其余部分已落地(`_FLAG_NAMES` 已在 `c40eacae` 删除),但它给出的保留理由对下面这两个常量并不成立。执行时必须在提交信息里写明这次推翻:

- `iostore.py:58` `FLAG_COMPRESSED`、`:62` `FLAG_ON_DEMAND` —— 各只出现 1 次(声明本身)。`FLAG_ENCRYPTED`(:166/:319)、`FLAG_SIGNED`(:170/:317)、`FLAG_INDEXED`(:404)是活的,保留。
- 8 个只写字段与其构造 kwarg:`IoStoreChunk.hash`(103)、`IoStoreBlock.uncompressed_size`/`method_index`(127-128)、`IoStoreToc.container_id`/`partition_count`/`partition_size`/`perfect_hash_seed_count`/`chunks_without_perfect_hash_count`(151-156)。
- 必须同批清理否则 ruff F841 报错:`container_id`(:302)与 `partition_size`(:306)是**无游标作用**的裸读;`word2`(:356)随两个 word2 派生字段一起死;metas 列表推导(:375-381)塌成只取 flags。
- **必须保留**:`perfect_hash_seeds`/`chunks_without_perfect_hash` 两个**局部**(它们在 `:326/:328` 决定 span 并在 `:349` 推进 `pos`)。

**模块整体是 KEEP 的**(`docs/designs/2026-09-10-codebase-slimming-plan.md:105,317` 标注为延迟能力 #624),`read_toc` 在 `src/` 里 0 个调用点(仅测试用)。游标安全已由 `read_toc` 自身 `total == size` 的断言保证(:334-340)。

- [ ] **Step 12.5: 修正 18 个模块的 docstring 位置(0 行,纯卫生)**

`from __future__ import annotations` **之后**再放模块 docstring,会让该字符串成为被丢弃的表达式语句、`__doc__` 为 `None`。受影响的模块(评估实测 18 个):`kismet/decompile_bridge.py`、`kismet/expressions/{assignments,casts,containers,control_flow,delegates,functions,literals,rtfm,string_consts,structs,variables,vector_consts}.py`、`memory_safety.py`、`mappings.py`、`parsers/{class_specific_skip,custom_properties,property_parser,property_types}.py`、`serializers/package_summary.py`。

把 docstring 移到 future import **之上**。行数不变,无测试读 `__doc__`(0 命中),尺寸棘轮按行计,因此中性。

Run: `python -c "import uasset_read.memory_safety as m; print(m.__doc__)"`
Expected: 打印真实描述而非 `None`。

- [ ] **Step 12.6: 闸门 + commit**

Run: `python -m pytest -q` → `220 passed`
Run: `python temp/decode_parity.py check` → 逐字节相同
Run: `python -m ruff check src/uasset_read tests/` → PASS

```bash
git add src/uasset_read
git commit -m "refactor: drop write-only mappings/iostore residues and unused params (overturns the 2026-09-08 FLAG_* keep decision)"
```

---

### Task 13: 测试树去重(约 430 行)

**结论出处:** 附录 C 第 43-50 行。

**Files:**
- Modify: `tests/samples/manifest.json`
- Modify: `tests/test_payload_extraction.py`
- Modify: `tests/test_core.py`
- Modify: `tests/test_unversioned_fixtures.py`
- Modify: `tests/serialization/test_package_trailer.py`、`tests/serialization/test_data_resource.py`
- Modify: `tests/size-baseline.json`

**Interfaces:**
- Consumes: 无
- Produces: `tests/test_payload_extraction.py` 新增 `_desc(**overrides)` helper;`tests/test_core.py` 新增 `_json_bytes(value)`。

**不要碰的东西:**
- `manifest.json` 的 `fixture_gaps`(评估标为 UNCERTAIN;`tests/test_handler_capability_ledger.py:9` 的 docstring 引用它,**且并发计划 Task 9 正在编辑它**)。
- `tests/test_core.py` 的两处源码文本抓取测试(见 Step 13.6)。
- 除下面点名的键以外,`manifest.json` 任何仍在被读的键(评估列出的活键:`version`、`sidecars`、`export_count`、`b_is_asset_count`、`engine_layout`、`size_bytes`、`sha256`、`golden_files`、`container_kind`、`committed`、`local_only_reason`、`summary.total_samples`)。

- [ ] **Step 13.1: 删 manifest 死键(234 行)**

逐键复核后删除(单模式搜,每个键在 `src/` 与 `tests/` 的字符串读取必须为 0):每个样本的 `asset_type_hint`(66)、`has_multiple_b_is_asset`(66)、`legacy_file_version`(10)、`asset_class`(10)、per-sample `diagnostics`(23);`summary` 块除 `total_samples` 外全部(50);顶层 `description`(1);golden 的 `generator_commit`(3);container 的 `note`(5)。

验证方式(不凭信):

```powershell
python -c "
import json, pathlib, subprocess
m = json.loads(pathlib.Path('tests/samples/manifest.json').read_text(encoding='utf-8'))
keys = ['asset_type_hint','has_multiple_b_is_asset','legacy_file_version','asset_class','generator_commit']
files = subprocess.run(['git','ls-files','-z'],capture_output=True).stdout.decode().split(chr(0))
hits = {k: 0 for k in keys}
for f in files:
    if f.endswith('.json') or not f: continue
    try: text = pathlib.Path(f).read_text(encoding='utf-8', errors='ignore')
    except OSError: continue
    for k in keys: hits[k] += text.count('\"' + k + '\"')
print(hits)"
```
Expected: 每个键都是 `0`。**任何非零都必须停止并保留该键。**

改完后必须保持 JSON 语义不变(`json.dumps(indent=2, ensure_ascii=True)` 往返实测与原文件字节等价,仅 `\u2014` 转义形式不同):

Run: `python -m pytest tests/test_samples.py -q`
Expected: PASS(尤其 `test_manifest_matches_every_real_sample` 与 `total_samples`)

- [ ] **Step 13.2: `test_payload_extraction.py` 去样板(约 110 行)**

`fixture_dir` 出现 11 次、`main_path = fixture_dir / "T_ParserBulk.uasset"` 10 次、`if not main_path.exists(): pytest.skip(...)` 10 次(守卫永不触发:`git ls-files tests/samples | Select-String T_ParserBulk` 证明三个文件都被跟踪,且设计约定「缺失/哈希不符必须 FAIL 而不是 skip」)。

改成模块级一次:

```python
FIXTURE_DIR = Path(__file__).parent / "samples"
MAIN_PATH = FIXTURE_DIR / "T_ParserBulk.uasset"

pytestmark = pytest.mark.skipif(
    not (MAIN_PATH.exists() and MAIN_PATH.with_suffix(".uexp").exists()),
    reason="T_ParserBulk fixture or its .uexp sidecar is missing",
)
```

并加一个 `_desc` helper 取代 9 处内联 `PayloadDescriptor(...)` 字面量(84 行 → 13 行;9 处的字段集实测一致,只要 `id`/`owner` 加上 5 个可覆盖项):

```python
def _desc(**overrides) -> PayloadDescriptor:
    base = {
        "id": "payload:(export:0)",
        "owner": "export:0",
        "offset": 0,
        "compressed_size": 0,
        "raw_size": 0,
        "logical_size": 0,
        "compression": "none",
    }
    return PayloadDescriptor(**{**base, **overrides})
```

**以模型的实际字段名为准**(`models/payloads.py:27-36`),上面的键名需按文件现状核对后再落笔。

- [ ] **Step 13.3: 删测试内重复 fake(约 34 行)**

**评估推翻了 3 处「重复」判断,只删这些:**

- `Ok` stub 类 ×2(`tests/test_core.py:981-988` 与 `1007-1014`,逐字节相同)→ 提为模块级一份:-8 行。
- `spy` ×2(`1089` 与 `1116`)→ 一份:-3 行。
- 4 个 `ObjectRecord(...)` 字面量(`990-996`/`1016-1022`/`1038-1044` 三处相同 + 一处只差 `id`),使用 `:1254` 已有的 helper(需把该 helper 泛化以接受 `id`):约 -21 行。
- `tests/test_core.py` 的 `record` 与 `tests/test_handler_capability_ledger.py:51` 的 `_record` 逐字节相同(评估实测)→ 保留 `tests/` 内一份并共享:-2 行。

**不要动**:两个 `boom`(抛的异常不同:`ParseError` vs `ValueError`)、`_KismetLike` 与 `_WidthProbe`(只共享 3 个方法,合并会造出一个两边都有未用方法的 9 方法探针)。handler stub 的未用参数(`obj`/`ctx`/`all_objs`/`data`)是协议一致性,不是发现。

- [ ] **Step 13.4: `test_unversioned_fixtures.py` 删重复完整性层(约 26 行)**

`tests/test_samples.py:301-315` 已对**每个** manifest 样本与声明的 sidecar 断言 exists/size/sha256(`:286` 还钉了 `actual_files == expected_files`),两个 unversioned 文件都在 manifest 里带 `sha256`+`size_bytes`(实测:`BP_UnversionedTest.uasset` 3098 B、`DA_UnversionedTest.uasset` 803 B)。

删除:`_sha256_file`(20-25)、两个完整性测试(`39-45`、`47-54`)、exists 循环(`56-63`),并把「≥2 个 unversioned 条目」这个前提折进版本测试。内联 `_load_manifest`。

**保留**(unversioned 专有):`file_version_ue4 == 0` 断言(65-71)、usmap exists/parse 断言(73-91)。**不要删整个文件** —— 那会丢掉 USMAP 覆盖,且需要下调 `tests_python.min_files`。

- [ ] **Step 13.5: 删 serialization 重复测试(约 18 行)**

- `tests/serialization/test_package_trailer.py:23-28` 与 `:147-153` 逐字节相同(只有变量名不同;`:147` 的 docstring 声称测 `_read_core_tables` 的填充,实际测的是 dataclass 默认值 —— 它也顺带修掉一个谎言)。保留一处或参数化。
- `tests/serialization/test_package_trailer.py:31-36` 与 `tests/serialization/test_data_resource.py:49-55` 逐字节相同。保留一处。
- `test_serializers_exports`(11 行)只断言两个刚 import 的函数 `callable()` —— 导入本身就是检查。缩减为导入语句。

- [ ] **Step 13.6: 删 1 行源码抓取断言,保留另外两个**

`tests/test_core.py` 中 `test_guid_display_is_36_chars` 的 `assert "00000000" not in h_src` 子句(约 1993)删除 —— 它 grep `handlers_impl.py`,而 `handlers_impl.py` 里的 GUID 格式化是**行为式**的(`:303` `format_guid_bytes`、`:1151-1155` `_guid_hex`),同测试已通过 `format_guid_bytes` 覆盖显示行为,该子句只会在无关的未来文本上误报。

**保留** `test_native_fields_delegate_type_name`(1810-1814)与 `test_no_invented_k2node_tails`(1976-1982) —— 它们钉的是没有 fixture 替代品的 UE 源码不变量(G4 尾部字节是 manifest 里公开的缺口)。**但注意**:后者的 `src.split("# 5 Node type readers")[1]` 会在注释被改名时以 IndexError 报错(而非干净的失败),这正是全局约束里要求保留那条横幅的原因。

- [ ] **Step 13.7: 小项**

- `tests/test_core.py` 的 `_size`(2275)与 `size`(2388)逐字节相同 → 保留一个作模块级 `_json_bytes(value)`。**注意:16 处内联 `separators=(",", ":")` 是行内替换,省 0 行** —— 只省掉重复的那个 helper(约 2 行)。
- `tests/test_samples.py:985-997` 的同一段 5 行 manifest 过滤在 `parametrize` 的值列表与 `ids=` 各写了一遍 → 提为模块常量(约 5 行)。
- 两个死的 `tmp_path` 形参:`tests/test_core.py:79` 的 `test_reader_boundaries_reject_malformed_access(tmp_path)`(用例走 `tempfile.TemporaryDirectory`)与 `:365` 的 `test_iostore_parses_supported_layouts(tmp_path=None)`。
- `tests/size-baseline.json`:删掉 5,352 字符的单行 `_note` 变更日志(**要求实际是 5,352 字符**),只留一句总结;删除无人读的 `wheel_bytes._measured`(CI 只读 `max_bytes`)。JSON 改动不计入任何 `max_lines`,无需重测。

- [ ] **Step 13.8: 闸门 + commit**

Run: `python -m pytest -q`
Expected: 通过数与 Step 1.3 相同(删除的测试用例数应等于删掉的用例数,不得出现新的失败)。

```bash
git add tests
git commit -m "test: deduplicate fixture boilerplate, manifest dead keys and duplicate serialization tests"
```

---

### Task 14: 仓库配置 + ruff 收缩子集(约 55 行)

**结论出处:** 附录 C 第 51-56 行。

**Files:**
- Delete: `.github/codeql/codeql-config.yml`
- Modify: `.gitattributes`
- Modify: `pyproject.toml`
- Modify: `src/uasset_read/exceptions.py`
- Modify: ruff 命中的其余位置(见 Step 14.5)

**Interfaces:**
- Consumes: 无
- Produces: 无。

- [ ] **Step 14.1: 删 codeql 配置(5 行)**

`.github` 下只有 `workflows/ci.yml` 一个 workflow,其 job 为 directory-compliance / package-smoke / ruff-check / pyright-check / peer-evidence-hygiene / pytest-smoke,**没有任何 CodeQL 步骤**;全仓内容搜 `codeql`(大小写不敏感)0 命中。且该文件唯一的排除路径 `src/uasset_read/pak/crypto.py` 所在的整个 `pak/` 包已在 `ac667ba7`(2026-08-31)删除。GitHub 的 default setup 只通过 repo property `github-codeql-config-file` 读取配置文件,不会自动发现 `.github/codeql/codeql-config.yml`(只有 `.github/codeql/extensions/` 会被自动发现,用于 model pack)。

Run: `git rm .github/codeql/codeql-config.yml`
Expected: 文件被删除。

- [ ] **Step 14.2: 删 `.gitattributes` 的悬空 diff 属性(2 行)**

第 4 行 `*.uasset diff=uasset-read` 与第 6 行 `*.umap diff=uasset-read` 删除。自定义 driver 全仓未定义(`git config --get-regexp '^diff\.'` 只有 `astextplain` 与 `text`),属性会覆盖第 3/5 行的 `binary` 宏然后回退到内容嗅探,输出与不设时相同。

**溯源(写进提交信息)**:这是 #266 git textconv 集成的残留 —— 它的安装器 `scripts/install-git-textconv.ps1`(定义 `diff.uasset-read.textconv`)与文档 `docs/guides/git-textconv.md` 在 2026-07-04 因 CI 的禁用目录规则(`ci.yml` 禁止 `^scripts/` 与 `^docs/guides/`)被移出 master。**若 textconv 仍是被期望的能力,正确做法是把安装器重新安置到允许的目录,而不是保留悬空属性** —— 执行者若无法判断,保留属性并只加一条 TODO 注释,不要删。

Run: `git check-attr -a -- tests/samples/DT_ParserWeapon.uasset`
Expected: `diff: unset`(不再是 `diff: uasset-read`)。

- [ ] **Step 14.3: 删 `pyproject.toml` 的空操作 ignore(1 行)**

第 44 行 `ignore = ["E501"]` 删除 —— `select` 是显式列表(`F401,F821,F841,F811,F541,B007,B009,B023,E741`)且不含 E501,该 ignore 永远无效;`line-length = 120` 对 `ruff check` 同样不被任何已选规则消费。

**取舍**:这是**潜伏守卫** —— 若日后把 `select` 扩到 `E` 组,删掉它会让 15 个 E501 命中浮现。若评审更看重这一点,替代方案是保留 `ignore` 并删掉同样无效的 `line-length`,或补一个 `ruff format --check` 门。二者择一,不要两个都留。

Run: `python -m ruff check src/uasset_read tests/`
Expected: PASS(行为不变)。

- [ ] **Step 14.4: 删 `exceptions.py` 的 3 个空 `pass`(3 行)**

`src/uasset_read/exceptions.py:17,23,33` 三个 `pass` 删除(每类都已有 docstring 作为合法函数体)。`ParseError`(:26)未被 PIE790 命中 —— 它只有 docstring、没有 `pass`,不要动。

Run: `python -c "from uasset_read.exceptions import UAssetError, VersionError, ParseError, ExportBoundsExceeded"`
Expected: 无输出、无异常。

- [ ] **Step 14.5: ruff 收缩子集(约 43 行 —— 只做推荐的,不做全部)**

**先看清代价再动手。** 全量应用 ruff 建议可得约 95 行,但其中两处是**倒退**:

- **不要用 C420 的 autofix**。6 处 `dict.fromkeys` 替换会长出 576/209/125/122/128/81 字符的行,其中 4 行超过仓库自己的 120 约定。若要做,必须手工折行,收益从 48 行降到很小。**本计划选择跳过 C420。**
- **SIM114 只做 `property_tags.py:310` 那一处(-5 行)**。`native_fields.py:373`/`379` 的合并会产出 138 字符的行。

推荐执行(实测行数):

| 规则 | 位置 | 净行数 |
| --- | --- | --- |
| SIM108 | `archive.py:567`、`kismet/archive.py:161,201`、`kismet/native_fields.py:112`、`binary_or_native_handlers.py:52`、`property_parser.py:671,1180`、`utils.py:75`、`package_summary.py:317,752` | -24 |
| RET504 | `agent_tools.py:45`、`kismet/native_fields.py:335,338`、`graph_pin.py:158` | -4 |
| SIM114 | `property_tags.py:310` | -5 |
| RET505 | `property_types.py:418,489`、`object_resources.py:434,455` | -4 |
| SIM103 | `archive.py:240` —— 手写成 `return remaining >= expected_bytes`(**不要**用 ruff 的 `not remaining < expected_bytes`) | -2 |
| SIM105 | `legacy_reader.py:853` —— 需要新增 `import contextlib` | -2 |
| SIM102 | `graph_node.py:186` | -1 |
| RET507 | `kismet/archive.py:68` | -1 |
| PIE790 | 已由 Step 14.4 计入 | — |
| F841 | 已由 T1 Step 1.5 计入 | — |

**明确不做**(0 行或负收益):C420、PIE810(`graph.py:150`、`graph_node.py:502`)、C408(`tests/test_samples.py:680`)、SIM115(`archive.py:68` 的 `open` 是长生命期句柄,无法改 `with`)、RET503(`handlers_impl.py:890` 会 +1 行)、SIM114 的 `native_fields` 两处。

- [ ] **Step 14.6: 闸门 + commit**

Run: `python -m ruff check src/uasset_read tests/` → PASS
Run: `python -m pytest -q` → `220 passed`
Run: `python temp/decode_parity.py check` → 逐字节相同

```bash
git add -A .github/codeql .gitattributes pyproject.toml src tests
git commit -m "chore: drop unreferenced codeql config and dangling diff attribute; apply safe ruff shrink subset"
```

---

## Wave 2 — 需要授权

### Task 15: `_run_cases` 重构为 pytest 原生收集(约 245 行,**需设计修订**)

**结论出处:** 附录 C 第 57 行。

**Files:**
- Modify: `tests/test_core.py`
- Modify: `tests/test_size_baseline.py`(结构闸门的 N)
- Modify: `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md:787-789`
- Modify: `README.md:30`

**Interfaces:**
- Consumes: 无
- Produces: `tests/test_core.py` 顶层收集到约 128 个 `test_*` 函数;`_run_cases` helper 消失。

**这是重构,不是删除。执行前必须拿到设计修订授权**,因为 canonical 设计 `:787-789` 明文要求这个形状并把「提高 N」定义为需要 deliberate、reviewable diff 的动作,`README.md:30` 复述该约束,`tests/test_core.py:2984-3019` 的结构闸门把它钉成 `len(funcs) == 13`。

**三个实测陷阱,漏掉任何一个都会静默丢测试:**

1. 嵌套 def 是 **174** 个(不是 134),其中 95 个叫 `test_*`。
2. **28 个 case 函数不叫 `test_*`**(例如 `depends_map_stops_at_unsized_count`、`core_projection_honors_views`)。朴素提升会让这 28 个**不被收集**——必须先改名。
3. 用例闭包**捕获外层局部**(`doc`、`d`、`schema`、`_env`、`pp`、`calls`、`real`、`main_size`、函数内的 import、17 个 handler 类,以及 `monkeypatch` fixture)。有 5 个 helper def 必须提到模块级:`_synthetic_toc`、`boom`、`record`、`_size`、`partial_page_budget`。

- [ ] **Step 15.1: 取授权并记录**

向仓库所有者确认设计修订(本计划已获授权则跳过)。在 `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md:787-789` 把 N-lock 从 13 改为新的顶层测试数,并注明修订理由(测试形状回归 pytest 原生收集,`_run_cases` 注册表删除)。

- [ ] **Step 15.2: 先量化基线**

```powershell
python -c "
import ast, pathlib
t = ast.parse(pathlib.Path('tests/test_core.py').read_text(encoding='utf-8'))
calls = [n for n in ast.walk(t) if isinstance(n, ast.Call) and getattr(n.func, 'id', '') == '_run_cases']
tuples = sum(len(a.elts) for c in calls for a in c.args if isinstance(a, ast.List))
nested = [n for n in ast.walk(t) if isinstance(n, (ast.FunctionDef,)) and n.col_offset > 0]
named = [n for n in nested if n.name.startswith('test_')]
print('calls', len(calls), 'cases', tuples, 'nested defs', len(nested), 'named test_', len(named))"
```
Expected: `calls 8 cases 123 nested defs 174 named test_ 95`。把实际值记进提交信息;**与预期不符时先搞清差异再动。**

- [ ] **Step 15.3: 机械提升用例**

对 8 个 `_run_cases([...])` 块(约在 394/671/886/1183/1995/2240/2446/2581):

1. 把每个 case 函数从外层函数内**提到模块级**(它们的 def 本来就在外层函数里、以名字传进列表,不在参数列表内)。
2. 给 Step 15.2 查出的 28 个非 `test_` 名字加 `test_` 前缀,并同步它在 `_run_cases` 列表里的引用(列表随注册表一起删除,所以只需改名)。
3. 把 5 个 helper(`_synthetic_toc`、`boom`、`record`、`_size`、`partial_page_budget`)提到模块级。
4. 把用例闭包捕获的局部(fixtures 除外:用到的 `monkeypatch` 等改为 pytest fixture 形参)改为用例自己的形参或模块级常量;文件内 import 提到模块顶部。
5. 删除 `_run_cases` helper(49-54)与 8 个已只含 helper/import 的外层 shell(每个 shell 在用例搬空后都会变成空跑测试,必须一并删)。
6. 每个 `_run_cases` 块原有的注释/`ids` 说明,改写成该组用例上方的分节注释。

- [ ] **Step 15.4: 更新结构闸门**

`tests/test_size_baseline.py` 与 `tests/test_core.py:3006` 的 `len(funcs) == 13` 改为新的顶层测试数(`~128`,以 Step 15.2 的实际数为准);同时确认 `SRC` 文件列表与「无 class / 无 decorator」断言仍成立(它们与本次形状无关,应保持)。

- [ ] **Step 15.5: 逐项名对照**

```powershell
python -m pytest tests/test_core.py --collect-only -q | Select-String "::" | Measure-Object -Line
```
Expected: 收集数 == 旧的「8 个外层测试 + 123 个用例」覆盖的用例数。**再用 `python -m pytest --collect-only -q > temp/after.txt` 与重构前 `temp/before.txt` 逐名 diff,确认没有用例消失**(允许出现的差异只有:28 个改名、8 个空 shell 消失)。

- [ ] **Step 15.6: 闸门 + commit**

Run: `python -m pytest -q`
Expected: 通过数 = Step 1.3 的 220 + (123 - 8) 附近,**且零失败**。

```bash
git add tests/test_core.py tests/test_size_baseline.py docs/designs/2026-08-26-package-first-uasset-parser-refactor.md README.md
git commit -m "test: replace the _run_cases registry with native pytest collection (design-amended N-lock)"
```

---

### Task 16: 修复 `--depth decode` 静默丢弃 Kismet 函数体(正确性缺陷)

**结论出处:** 附录 C 第 58 行(评估在清单之外发现的高价值缺陷)。

**现象:** `BP_CombatCharacter` 的 `export:2`(`BlueprintGeneratedClass`)在 `--depth asset` 下输出 42 个函数,在 `--depth decode` 下 `functions` 整个消失;`extract_kismet_decompiled` 两次都正确产出 45 个结果。**decode 不是 asset 的超集**,与文档化的单调性矛盾(`handlers_impl.py:1061-1064`、`wiki/04-Advanced-Features/Kismet.md:110-113`)。

**根因:** `handlers_impl.py:984-993` 的 kismet 投影嵌在 `:933` 的 `if graphs:` 里;`else` 分支(`:994-1001`)只记「graph missing」并丢弃已经算好的 `entry["kismet"]`。`BlueprintGeneratedClass` **拥有 Function export(有字节码)但不拥有 FunctionGraph export**,所以必然落进 `else`。

**Files:**
- Modify: `src/uasset_read/parsers/asset_types/handlers_impl.py:929-1003`
- Test: `tests/test_blueprint_decode.py`

**Interfaces:**
- Consumes: 无
- Produces: `semantic.functions` 在 asset 与 decode 两个深度上对同一 export 给出同样的函数集;`blueprint.graph` 的 missing 覆盖条目保留不变。

- [ ] **Step 16.1: 先确认数字(不要凭信)**

```powershell
$env:PYTHONPATH="E:/Develop/uasset_read/src"; python -c "
from uasset_read import parse_package_document
for depth in ('asset','decode'):
    doc = parse_package_document('tests/samples/BP_CombatCharacter.uasset', depth=depth, object_ids=['export:2'])
    o = next(x for x in doc.objects if x.id=='export:2')
    fns = (o.semantic or {}).get('functions')
    print(depth, 'functions:', 0 if not fns else len(fns), '| cov:', [c.feature for c in o.coverage])"
```
Expected: `asset functions: 42` / `decode functions: 0`。**若两者都已相等,说明缺陷已被别处修掉 —— 本任务作废,记录下来并跳到 T15 之后的验收。**

- [ ] **Step 16.2: 写失败的测试(RED)**

追加到 `tests/test_blueprint_decode.py`:

```python
def test_generated_class_kismet_functions_survive_decode():
    """A BlueprintGeneratedClass owns Function exports (bytecode) but no FunctionGraph exports.

    decode is documented as a superset of asset (handlers_impl.py:1061-1064;
    wiki Kismet.md:110-113), so the graph gate must not drop its Kismet functions.
    """
    dec = _decode("BP_CombatCharacter.uasset", ("export:2",))
    bpgc = next(o for o in dec.objects if o.id == "export:2")
    fns = (bpgc.semantic or {}).get("functions")
    assert fns, "decode dropped the generated class's Kismet functions"


def test_generated_class_function_count_is_depth_independent():
    from uasset_read import parse_package_document

    counts = {}
    for depth in ("asset", "decode"):
        doc = parse_package_document(
            "tests/samples/BP_CombatCharacter.uasset", depth=depth, object_ids=["export:2"]
        )
        bpgc = next(o for o in doc.objects if o.id == "export:2")
        counts[depth] = len(((bpgc.semantic or {}).get("functions") or []))
    assert counts["decode"] == counts["asset"] == 42, counts
```

- [ ] **Step 16.3: 运行确认失败**

Run: `python -m pytest tests/test_blueprint_decode.py -q -k generated_class`
Expected: FAIL —— `assert fns` 失败(以及 `counts` 为 `{'asset': 42, 'decode': 0}`)。

- [ ] **Step 16.4: 把 kismet 投影提出 `if graphs:`**

先读 `handlers_impl.py:925-1005` 全文,确认投影块的精确边界与它依赖的局部。然后**只做结构搬移**:把 `:984-993` 这段 kismet 投影提到 `:933` 的 `if graphs:` **同级之前**,条件是 `entry.get("kismet")` 非空;`if graphs: ... else: <记 blueprint.graph missing>` 原样保留。

搬移后该处的形态(以实际局部名为准):

```python
    # Kismet functions belong to the export, not to its graphs: a
    # BlueprintGeneratedClass owns Function exports but no FunctionGraph exports,
    # so gating this projection on `graphs` silently drops them at depth=decode.
    kismet = entry.get("kismet")
    if kismet:
        entry["functions"] = _project_kismet_functions(kismet, include_expressions=<原 depth 判断>)
        <原 coverage 条目原样搬来>

    if graphs:
        <原样>
    else:
        <原样>
```

**不要**顺手改投影内容、白名单键或 coverage 语义 —— 本任务只修可达性。

- [ ] **Step 16.5: 运行确认通过**

Run: `python -m pytest tests/test_blueprint_decode.py -q -k generated_class`
Expected: PASS(`counts == {'asset': 42, 'decode': 42}`)。

Run: `python -m pytest -q`
Expected: 220 passed。若 `test_combat_character_kismet_functions` 之类原本依赖「decode 下只有 3 个函数」而失败,说明它写死了旧错误行为 —— 按新语义修正断言,并在提交信息里说明。

- [ ] **Step 16.6: 这是**唯一**会改变输出的任务 —— 重录 oracle**

Run: `python temp/decode_parity.py record`
Expected: 记录新基线。**在提交信息里明确写出这次基线变更是有意的**,并把变更差异(`decode` 下 `export:2` 多出的 42 个函数)写进提交正文,供后续评审对照。

- [ ] **Step 16.7: 更新文档口径**

`wiki/04-Advanced-Features/Kismet.md:110-113` 与本修复相关(它是 gitignore 的外部仓 → 见附录 B,体外同步)。

- [ ] **Step 16.8: commit**

```bash
git add src/uasset_read/parsers/asset_types/handlers_impl.py tests/test_blueprint_decode.py tests/size-baseline.json
git commit -m "fix: keep Kismet functions at depth=decode for graph-less BlueprintGeneratedClass exports

decode was dropping 42 of 45 function bodies for BP_CombatCharacter's export:2 because the
kismet projection was nested inside the graph gate. Regression tests:
test_generated_class_kismet_functions_survive_decode,
test_generated_class_function_count_is_depth_independent.
Parity baseline re-recorded: this is the only intentional output change in the wave."
```

---

## 明确不做(已复核推翻,不要再提)

| 项 | 为什么不做 |
| --- | --- |
| `Diagnostic.size` | 已发布契约字段:`docs/designs/contract/package_document_v2.schema.json:362` 在 `$defs.Diagnostic`(`additionalProperties:false`)里声明它,`wiki/06-Output/Output-Format.md:188-193` 说明它 emit-when-set,canonical 设计 `:542` 的例子含 `"size": 8`。删它要 4 处文档+契约联动。 |
| `memory_safety.py` | 活模块:3 个 src importer + 1 个测试 + `README.md:209` API 表。 |
| `tests/test_core.py:2540` schema 反射闸门 | 真实漂移闸门:比对两个独立维护的已发布产物,且 `PayloadDescriptor` 在 `agent_tools.py:328,372` 被真实构造(其 docstring 的「zero emitters」只是过期陈述)。 |
| `test_test_suite_structure_gate` | canonical 设计强制的 N-lock 执行臂,6 条断言里 5 条与 `_run_cases` 形状无关;T15 只改 N,不删闸门。 |
| `handlers_impl.py:20-38` `AssetHandler` Protocol | pyright 在用,且被 3 页 wiki 记为 handler 契约(含 `Pipeline.md:78` 把它的 docstring 当 #629 规则的依据)。删它省 19 行、代价是 4 个注解退化 + 3 处 wiki 改动。 |
| `TypeMappings.enums` 的解析循环 | 只删字段,**循环必须保留读取**(顺序游标,删了会损坏后续 struct 解析;实测报 `ParseError: Usmap name index out of bounds`)。 |
| ruff C420 autofix(6 处) | 替换行 4/6 超过仓库自己的 120 约定(最长 576 字符),是可读性倒退。 |
| `VersionContext` 多字段 | G1 契约(`docs/designs/2026-08-31-version-context-field-contract.md`)要求保留,同类削减曾被回退(`280b7e09`)。 |
| `_recover_pin_array_count` 启发式 | 删除会改变宽容解析输出 = 正确性范畴;且该区域内有已知的延迟 bug(`graph_pin.py:303,309` 把 `(valid, reason)` 元组当 dict 下标)。 |
| `cli._sanitize_error_message` 的 6 条正则 | 安全相关,前几波明确保留。 |

---

## 附录 A:对并发产品化计划的重写义务

**2026-09-12 更新：** `docs/designs/2026-09-12-post-refactor-productize-plan.md` 已按本表完成重写，并改为总调度（Wave A→B）。下表保留为历史对照；Wave B 新任务号为 P0–P8。

| 它的任务 | 冲突点 | 重写方向 |
| --- | --- | --- |
| Task 1:70-89 | 断言 `node_data["function_reference"]` 出现在 decode 输出 | `read_k2node_call_function` 与 `read_fmember_reference` 已被 T2 删除。若要该语义,必须先重新设计投影层的读取路径(在 `blueprint_graph.py` / 一个新 reader 里按需读取),而不是恢复整条 K2Node 分派链 |
| Task 2:128-189 | `_node_data_to_json` 投影 `node_data` 并读 `pin.default_value` / `pin_type.pin_subcategory` / `UEdGraphPin.hidden` | T2 删掉 `node_data` 的生产, T3 删掉这些 pin 字段。需重新定义它要做的最小投影契约,并只重新引入真正需要的字段 |
| Task 2:158 | 序列化 `function_reference`/`event_reference`/`member_reference` | `FMemberReference` 与其两个 reader 已被 T2/T5 删除 |
| Task 5:349 | 「Modify `graph_node.py`(读路径若尚未写入 node_data)」 | 整套 K2Node 读取器已删;该任务需改为在投影层实现 |
| Task 3:217-218 | 依赖 `node_data.subgraph_references` | **不受影响** —— T2 明确保留 `_handle_full_context` 与 `_read_anim_graph_node`,该键仍是活的 |
| Task 9:563 | 编辑 `manifest.json` 的 `fixture_gaps` | T13 **不动** `fixture_gaps`,留给它 |
| Task 10:595 | 提高 `tests/size-baseline.json` 上限 | 本计划每波收紧 `max_lines`;它提交时按当时的实测值重新提高 |

**执行顺序：** 先完成本计划 Wave A（含 T16），再跑总调度 Wave B（P0–P8）。Wave B 禁止在 A 未落地时开工，也禁止恢复本表「冲突点」中的已删符号。

---

## 附录 B:wiki(体外)同步清单

`wiki/`(`.gitignore:107`)与 `docs/superpowers/`(`:102`)是**被忽略的外部仓**,无法在同一提交里更新。以下是会产生漂移的页面,由维护者在 wiki 仓单独提交:

| wiki 页 | 漂移原因 |
| --- | --- |
| `03-Core-Modules/Models.md:28-30,69` | 列出 `pin_tooltip`/`persistent_guid`/`node_guid`/`graph_class`/`schema`/`Diagnostic.size` 等字段(T3/T5 后不再存在;`Diagnostic.size` 是刻意保留的) |
| `03-Core-Modules/Serializers.md:34,39-40,95` | 列出 `depends_map`/`preload_dependencies`/`b_import_optional`;`read_ftext` 条目还指向一个**已不存在的**消费者 `parsers/asset_types/niagara_node.py` |
| `03-Core-Modules/Parsers.md:28,38,63,84,150-152,191` | 列出 `resolve_name_from_index`(`:28`)、`AssetHandler`(保留)、`_PROPERTY_ARGS`(`:63`)、`parse_soft_class_property`(`:84`)、一条已不成立的 `parse_status = "opaque_unversioned"` 断言(`:150-152`)、`CustomPropertyContext` 的字段表(`:191`) |
| `04-Advanced-Features/Kismet.md:26,55-65,97-103,110-113` | `KismetDecompiledResult` 字段表(`:97-101`)与 `extract_kismet_decompiled(path, …)` 签名(`:55-65`)在 T11/T12 后变化;`:110-113` 的深度单调性描述在 T16 后需要更新 |
| `06-Output/Output-Format.md:188-197` | 诊断字段的 emit-when-set 说明(与刻意保留的 `Diagnostic.size` 一致,无需改,但应在 T3 后复核) |
| `07-Dev-Guide/Public-API.md:137,142,146,178` | `AssetHandler` 契约(保留);公开常量表(`MAX_ARRAY_DIM` 在 T1 被删,但它**不在**该表中,无需改) |

---

## 附录 C:逐项判定表(本计划的规格来源)

「原估」是首轮审计的粗估,「修正」是六份独立评估对抗性复核后的行数。判定:**C**=确认,**R**=推翻,**U**=需产品决策,**P**=部分成立(结论对、数字或做法需修正)。

### node_data 链

| # | 项 | 判定 | 原估 | 修正 |
| --- | --- | --- | --- | --- |
| 1 | K2Node `node_data` 分派链(T2) | P | ~320 | **411**(含两处级联) |

### serializers / models

| # | 项 | 判定 | 原估 | 修正 |
| --- | --- | --- | --- | --- |
| 2 | `UEdGraphPin` 17 字段(T3) | C | 34 | 33(折叠 bitfield 后 53) |
| 3 | `FEdGraphPinType` 11 字段(T3) | P | 20 | 30 |
| 4 | `FMemberReference` + 两个 reader(T2) | C | 90 | 90 |
| 5 | `UEdGraph` 4 字段(T3) | C | 30 | 40 |
| 6 | `node_guid`/`_export_object_name`(T3) | C | 8 | 10 |
| 7 | export/import 标志 + transforms(T4) | C | 25 | 38 |
| 8 | `PropertyTag` 5 字段 + `type_name`(T4) | P | 13 | 6 |
| 9 | graph_pin `name_map` 链 + `owning_node`(T5) | C | 20 | 17 |
| 10 | 两个单调用 helper(T5) | P | 9 | 10 |
| 11 | `_read_pin_fstring_field` max_length(T5) | C | 1 | 1 |
| 12 | `_try_recover_to_subpins` 返回(T5) | P | 10 | 14 |
| 13 | `read_ftext`(T5) | C | 19 | 19 |
| 14 | `summary_gate_modes` | P | 12 | 12(会连带改一个已登记的测试) |
| 15 | `depends_map`/`preload_dependencies`(T4 同批可选) | C | 2 | 2 |
| 16 | `Diagnostic.size` | **R** | 1 | **0** |
| 17 | `_read_property_tag_legacy` 重复体 | C | 11 | 16 |
| 18 | `_TAGGED_FALLBACK_STRUCT_SCHEMAS`(T6) | C | 96 | 96 |

### parsers

| # | 项 | 判定 | 原估 | 修正 |
| --- | --- | --- | --- | --- |
| 19 | `_PROPERTY_ARGS`(T7) | C | 50 | 41 |
| 20 | `parse_soft_class_property`(T7) | C | 9 | 10 |
| 21 | UE5.7 soft-object-path(T9) | C | 50 | 59 |
| 22 | `_EXPECTED_STRUCT_SIZES` 25 行(T8) | C | 25 | 25 |
| 23 | `resolve_name_from_index`(T7) | C | 7 | 7 |
| 24 | 6 处 `setattr`(T4) | C | 6 | 7 |
| 25 | `_capability_tier`(T7) | C | 5 | 9 |
| 26 | `safe_parse` on_error(T7 同批可选) | C | 4 | 3 |
| 27 | `script_serialization_end_offset` 兜底(T7 同批可选) | C | 3 | 4 |
| 28 | `NiagaraNodeParameterMapGet`(T7) | C | 1 | 1 |
| 29 | ufunction_reader 重复构造(T10) | P | 45 | 70 |
| 30 | `_skip_type_tree_nodes` name_map(T7) | C | 1 | 2 |
| 31 | `first_ic`(T7) | C | 1 | 0 |
| 32 | `summary._mappings` 往返(T7) | P | 2 | 3 |
| 33 | native_fields 空转 helper(T10) | P | 33 | 28 |
| 34 | `_parse_fd`/`_parse_fe` 合并 | C | 12 | 12(会重新加回 `type_id`,需说明) |
| 35 | `_extract_enum_type_from_tag`(T7) | P | 9 | 10 |

### kismet / iostore / mappings / tests / 配置

| # | 项 | 判定 | 原估 | 修正 |
| --- | --- | --- | --- | --- |
| 36 | `KismetDecompiledResult` 7 字段(T11) | C | 33 | 33 |
| 37 | 表达式只写字段(T11) | P | 40 | 42 点名 / ~70 全量 |
| 38 | `TypeMappings.enums`(T12) | P | 16 | 7(循环必须保留读取) |
| 39 | `is_enum_as_byte`(T12) | C | 1 | 1 |
| 40 | 4 处未用参数(T12) | P | 12 | 8 |
| 41 | iostore 残留(T12) | P | 18 | 20-26(需推翻旧决策) |
| 42 | kismet/config 小项(T11/T12) | P | 3+3+0+0 | 2+3+0+0 |
| 43 | `_run_cases` harness(T15) | P | 250 | 230-245(**需设计修订**) |
| 44 | manifest 死键(T13) | C | 217 | 234 |
| 45 | test_payload 样板(T13) | C | 85 | 110 |
| 46 | 测试内重复 fake(T13) | P | 70 | 34 |
| 47 | `payload_descriptor` schema 闸门 | **R** | — | **0** |
| 48 | unversioned 重复层(T13) | C | 37 | 26 |
| 49 | 结构闸门 | **R** | — | **0** |
| 50 | uexp 三段重复 | C | 28 | 23 |
| 51 | serialization 重复测试(T13) | C | 24 | 18 |
| 52 | 源码文本抓取测试(T13) | P | 18 | 1 |
| 53 | size-baseline `_note`(T13) | C | 20 | 2 |
| 54 | 测试小项(T13) | P | 6 | 7 |
| 55 | codeql 配置(T14) | C | 5 | 5 |
| 56 | `.gitattributes` diff driver(T14) | C | 2 | 2 |
| 57 | `pyproject.toml` ignore(T14) | C | 1 | 1 |
| 58 | `exceptions.py` ×3 pass(T14) | C | 3 | 3 |
| 59 | ruff 收缩子集(T14) | P | 25 | **43 推荐**(全量 95 含倒退) |
| 60 | `memory_safety.py` | C | 4 | 3 |
| 61 | `parse_guard` 整模块 | P | — | 3(模块是活的) |
| 62 | `constants.py` 全量 | C | — | 0(80 个名字,零额外死常量) |
| 63 | `memory_safety.py` 死模块 | **R** | — | **0** |
| 64 | `--depth decode` 丢函数体(**缺陷**,T16) | 新发现 | — | 正确性修复 |
| 65 | CI ruff 红灯 3 处(**缺陷**,T1) | 新发现 | — | 3 行 |

**预期净效果:约 -1,750 行已确认减除,加 T15 的设计授权后约 -2,000 行;零新增依赖;零运行时行为变更(T16 是唯一有意的输出变更)。**

---

## 待补索引行(执行者补齐)

本计划**没有**修改 `docs/designs/README.md`(它处于另一会话的脏状态)。待那份并发编辑落定后,在同一提交里把它加进「Companion Contracts」表:

```markdown
| — | [`2026-09-12-ponytail-evaluation-fix-plan.md`](2026-09-12-ponytail-evaluation-fix-plan.md) | target | Subtraction-first wave after six adversarial evaluations of the 2026-09-12 ponytail audit: 41 confirmed cuts (~1,750 lines), 5 refuted, 2 defect fixes (CI ruff red, depth=decode kismet loss). Overturns the 2026-09-08 FLAG_* keep decision; supersedes the 2026-09-12-post-refactor-productize-plan's reader assumptions (see appendix A). |
```

注意:该行会让 `docs_markdown` 计数增加,必须同批重新测量并写明 `max_lines` 的调整理由。

---

## 自审

**规格覆盖:** 附录 C 的 65 行逐项判定全部映射到任务 —— T1(65、+CI 红灯)、T2(1、4)、T3(2、3、5、6)、T4(7、8、15、24)、T5(9、10、11、12、13)、T6(18)、T7(19、20、23、25、26、27、28、30、31、32、35)、T8(22)、T9(21)、T10(29、33)、T11(36、37、42)、T12(38、39、40、41)、T13(44-54)、T14(55-59、60、61、62)、T15(43)、T16(64)。**未纳入任务、需单独授权的 3 项**:第 14 行 `summary_gate_modes`(12 行,会连带改写 `tests/test_core.py:832-858` 与其在 case ledger 的登记,建议单独评审)、第 17 行 `_read_property_tag_legacy` 重复体(16 行,该路径只在 `file_version_ue5 < 1012` 走到,66 个 fixture 基本未覆盖)、第 34 行 `_parse_fd`/`_parse_fe` 合并(12 行,会把 2026-09-08 Task 13.2 删掉的 `CustomPropertyContext.type_id` 加回来 —— 是**显式推翻已执行决策**,需所有者点头)。这三项都是「值得做但会牵动已落地决策或未覆盖路径」,执行者不得顺手带上。

**占位符扫描:** 无 TBD/TODO;每个 Step 都有可执行命令或可直接照抄的代码;重复性删除给的是精确行号清单 + 重写后的代码形态,而不是「照上文处理」。已知的不确定点已写成带**停止条件**的步骤(Step 3.2、6.1、8.2、9.1、11.1、13.1、16.1),而不是含糊的「酌情处理」。

**类型一致性:** T7 建立的 `_ARGS_OVERRIDES` 与 T9 的 `soft_object_path_list` 删除有先后耦合,已在 T7 Step 7.2 与 T9 Step 9.3 双向写明(谁先执行都能收敛)。T10 的 `_make_failure` 新增 3 个关键字参数与 T11 的 `build_native_function_signature` 返回类型收缩都只被本计划内的任务消费。T11 引用的 `_project_kismet_functions` 是 `handlers_impl.py:1060-1097` 的既有函数,T16 复用它,不改其签名。T3 新增的 `test_decode_pin_payload_key_set_is_frozen` 用 `tests/test_blueprint_decode.py:20` 已存在的 `_decode(sample, object_ids)` helper;T16 的两个测试用同一个 helper 与 `uasset_read.parse_package_document(..., depth=, object_ids=)` 的既有形态。

