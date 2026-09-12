# Residual Closeout, G2 Cache, and Bundle 1/2 Execution Plan

> **Status:** current（Wave A + Wave B 已执行；**Wave C/D 用户暂缓**——不实现 Zen/IoStore 与 SchemaProvider；Wave E 收尾。本文为完成记录）
> **Date:** 2026-09-13
> **Branch context:** `dev-0.6.0` tip `c2151db4`（本地领先 origin 8 提交；合并入 `master` 见执行记录）
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 关闭重构后的文档/门禁残留；实现已冻结的 G2 解析缓存；按 UE 源码证据启动 Bundle 1（Zen/IoStore package body）与 Bundle 2（SchemaProvider / cooked unversioned）。产品向 deferred（`--diff`、Pak 全产品路径、C++ skeleton、batch 编排增强）**只记录不实现**。

**2026-09-13 执行边界（用户决策）：** 只执行 Wave A（S1/batch/wiki Gate C）与 Wave B（G2）。**Wave C（Zen/IoStore）与 Wave D（SchemaProvider）暂缓不实现**；对应 Bundles 仍见 `2026-09-13-deferred-capability-bundling.md`。合并动作：本地 `dev-0.6.0` → `master` fast-forward；**不 push** 主仓与 wiki。

**Architecture:**

- 工作留在 `dev-0.6.0`（不新建长期 feature 分支）；每波可独立 commit。
- Wave A（文档/门禁）与 Wave B（G2）**立即可执行**。
- Wave C/D 先 research 后实现；缺 fixture 的能力只到“有界合成字节 + 源码证据 + 明确 partial/deferred 声明”，**不买样本、不 skip/xfail**。
- wiki 是嵌套独立 git 仓库（`wiki/` → `uasset_read.wiki`）；主仓 push 与 wiki push 均**不做**（用户 standing rule；本计划只允许本地 commit）。

**Tech Stack:** Python 3.10+（阻断环境 Windows + Python 3.14）、pytest、ruff、零运行时依赖。

**Spec:**

- 权威架构：`docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`
- 收尾前置：`docs/designs/2026-09-13-next-phase-closeout-and-deferred-gates.md`（A–D 已执行）
- G2 契约：`docs/designs/2026-08-31-agent-doc-cache-contract.md`
- Bundle 记录：`docs/designs/2026-09-13-deferred-capability-bundling.md`
- S1：`docs/designs/2026-08-31-v2-contract-stability.md`
- S2：`docs/designs/2026-08-31-payload-extraction-path.md`

## Global Constraints

- 主仓与 `wiki/`：**只本地 commit，禁止 `git push`**。
- 零运行时依赖；只读解析；scratch 仅 `temp/`。
- 代码/注释/commit 英文；前缀 `refactor:` / `fix:` / `feat:` / `test:` / `docs:` / `chore:`。
- 不恢复 Wave A 已删符号；不碰 `external/`、`UnrealEngine/`、`dist/`、`build/`。
- 禁止 `skip`/`xfail` 伪装；语义键新增不 bump `format_version`。
- 测试结构门禁：`tests/test_core.py` 顶层 `test_*` 数量当前为 **14**；新增顶层函数须同步 `test_test_suite_structure_gate` 并说明理由。
- 基线预期（A/B 后）：ruff 绿；pytest 全绿（当前 236 passed）；不得引入新的 ucas 缺口失败。
- UE 源码相对路径引用；不提交本机 UE 绝对路径。

## Explicit Non-Goals

| Forbidden | Reason |
| --- | --- |
| `git push` 任意分支（主仓或 wiki） | 用户 standing rule |
| 实现 `--diff` / Pak 全产品 / C++ skeleton / batch 编排增强 | 产品向 deferred，仅记录 |
| 购买或伪造 Zen/cooked unversioned 大样本 | 既有产品决策 |
| 关闭 T15/T13 | 已 DEFER |
| 把 `--batch` 从 current 改回 deferred | 源码与 CLI 已是 live v2 |

---

## 调研结论摘要（执行前证据）

### 已核实残留

1. **主仓未推送：** `cf671a3c` / `5e41ba3e` / `7d1275c1`（parse-hardening）。本计划不 push。
2. **Gate C wiki：** `wiki/` 为嵌套仓库；`631f378` 已在本地 wiki master（与 origin 同步）；工作树另有 **7 个未提交文件**（Gate K/L 文案残留：删除 translator/body_builder/cpp_code/`--clean-logs` 旧描述）。内容方向正确，缺 commit。
3. **S1 三项落地动作：**
   - schema payload id 漂移**已修**（`^payload:(export|import):[0-9]+$`）；
   - `x-stability: experimental` 标注**未做**；
   - `docs/agents/` experimental 消费指引**未做**；
   - Phase 6 后 **`format_version: 2.0` 冻结声明未发出**。
4. **batch 口径漂移：** `cli.py` live `--batch`/`--batch-format`；README / agent-dev-reference / wiki CLI 页已正确；`2026-08-31-v1-retirement-plan.md` §5 与 `2026-09-13-deferred-capability-bundling.md` D-BATCH 仍写 deferred。
5. **G2：** 契约已冻结；`parse_package_document` 仍无缓存；六工具各自重 parse。
6. **Bundle 1 前置：**
   - `src/uasset_read/iostore.py` 已有 `.utoc` TOC 解析（header/directory index/chunk/block）；
   - 无 `ZenPackageReader`；`fixture_gaps.zen_package=missing`；
   - `iostore_container` 标 available（`global.utoc/.ucas` 已提交；大 `.ucas` 不在 git）；
   - UE 源码锚点：`FZenPackageSummary`（`AsyncLoading2.h:302`）、`FExportMapEntry`、`FExportBundleEntry`、IoStore `IoStore.h`。
7. **Bundle 2 前置：** editor `.usmap` unversioned 为 partial；无完整 `SchemaProvider`；cooked unversioned fixtures 无。
8. **产品向 open questions（只记录）：** batch 真实消费者、`--diff` 目标、C++ skeleton 是否复活、ucas 是否正式成为 Bundle 1 fixture 目标、loose-sidecar route A 是否切片 — 见 bundling 文档；**本计划不回答/不实现**。

---

## Wave A — 文档与门禁收尾（立即执行）

### Task A1: S1 冻结声明 + 契约稳定性收尾

**Files:**

- Modify: `docs/designs/contract/package_document_v2.schema.json`（experimental `$defs` 加 `x-stability`）
- Modify: `docs/designs/2026-08-31-v2-contract-stability.md`（status、落地动作勾选、payload 漂移注记为已修）
- Modify: `docs/designs/README.md`（S1 行 status → current；仍 bind 的规则）
- Modify: `docs/agents/issue-tracker.md` 或新建短节：experimental 键不得进跨版本 golden
- Modify: `README.md`（Refactor status 补一句 format_version 冻结）
- Modify: `docs/release-notes/changelog.md`（Unreleased 段记 freeze）

**Interfaces:**

- Consumes: Phase 6 已完成；schema 已含 payload id 修正。
- Produces: 对外 stable 域冻结承诺；experimental 域明确可演进。

- [x] **Step A1.1: 标注 experimental 子 schema**

在 `package_document_v2.schema.json` 中，为下列 experimental 区域的子 schema 增加 `"x-stability": "experimental"`（stable 不加标注）：

- `objects[].properties`
- `objects[].semantic`
- `objects[].coverage`
- 顶层 `payloads`

不改变任何约束关键字；`jsonschema` 校验必须仍通过现有契约测试。

- [x] **Step A1.2: 发出 format_version 冻结声明**

在 `2026-08-31-v2-contract-stability.md` 增加执行记录段（英文或中文与该文一致），明确：

1. Phase 6 已完成，`format_version: "2.0"` 对 **stable 域** 冻结为兼容承诺。
2. 此后 stable 破坏性变更必须 bump major（`"3.0"`）。
3. experimental 域增删改**不** bump。
4. payload id schema 漂移已修（记录 commit hash）。

同步：`docs/designs/README.md` S1 行 → `current`；`Still binds` 改为“冻结规则 + experimental 分级”；去掉“freeze declaration not yet emitted”。

- [x] **Step A1.3: 消费方指引**

在 `docs/agents/issue-tracker.md`（或 `agent-dev-reference.md` 的工作规范节）增加一条：

> `objects[].properties` / `semantic` / `coverage` 与顶层 `payloads` 是 experimental：不得作为跨版本 golden 的稳定断言面；stable 信封字段见 S1。

- [x] **Step A1.4: Commit A1**

```powershell
git add docs/designs/contract/package_document_v2.schema.json docs/designs/2026-08-31-v2-contract-stability.md docs/designs/README.md docs/agents/ README.md docs/release-notes/changelog.md
git commit -m "docs: freeze PackageDocument 2.0 stable contract and annotate experimental fields"
```

---

### Task A2: 修正 batch / deferred 口径（docs-only）

**Files:**

- Modify: `docs/designs/2026-09-13-deferred-capability-bundling.md`（D-BATCH 行 + bundle 3）
- Modify: `docs/designs/2026-08-31-v1-retirement-plan.md`（§5 / 文首注记：batch 已以 v2 形态回归；diff 仍 deferred）
- Modify: `docs/designs/README.md`（若索引行仍暗示 batch deferred）

**Interfaces:**

- Consumes: `cli.py` live `--batch`；README 与 agent-dev-reference 已正确。
- Produces: 设计索引与 bundling 记录不再与源码矛盾。

- [x] **Step A2.1: Rewrite D-BATCH rows**

将 D-BATCH 状态改为：**current（v2 CLI live `--batch`/`--batch-format`；uasset_read.batch report）**。D-DIFF 仍 deferred。Bundle 3 收窄为 **D-DIFF only**（或标注 batch 已出包）。

v1 retirement §5：保留 historical 叙事，但文首 execution note 增加：

> Residual note 2026-09-13: `--batch` is live again on the v2 CLI (directory walk + `uasset_read.batch`). Only `--diff` remains deferred among the old workflow pair.

- [x] **Step A2.2: Commit A2**

```powershell
git add docs/designs/2026-09-13-deferred-capability-bundling.md docs/designs/2026-08-31-v1-retirement-plan.md docs/designs/README.md
git commit -m "docs: mark v2 --batch as current and keep only --diff deferred"
```

---

### Task A3: Wiki Gate C 残留提交（本地 only）

**Files:**

- Modify (already dirty): `wiki/01-Getting-Started/Overview.md`, `Quick-Start.md`, `wiki/02-Architecture/IR.md`, `wiki/03-Core-Modules/Exceptions.md`, `wiki/04-Advanced-Features/CPP-Generator.md`, `Kismet.md`, `wiki/06-Output/CLI.md`
- Modify: `docs/designs/2026-08-31-v1-retirement-plan.md`（Gate C 注记：wiki 残留已本地 commit；**remote push 仍 open**）

**Interfaces:**

- Consumes: 已核实的 wiki dirty diff（Gate K/L 文案）。
- Produces: wiki 工作树干净；Gate C 代码/文案侧关闭，**push 门禁保持 open 并写明**。

- [x] **Step A3.1: Review wiki dirty diff against source**

确认每个改动与 `src/uasset_read/kismet/`、CLI retired flags、K0 expression contract 一致；不得把 target 说成 current。

- [x] **Step A3.2: Commit wiki locally (no push)**

```powershell
Set-Location E:/Develop/uasset_read/wiki
git add 01-Getting-Started/Overview.md 01-Getting-Started/Quick-Start.md 02-Architecture/IR.md 03-Core-Modules/Exceptions.md 04-Advanced-Features/CPP-Generator.md 04-Advanced-Features/Kismet.md 06-Output/CLI.md
git commit -m "docs: finish Gate K/L wiki residual (remove translator body_builder cpp_code clean-logs claims)"
```

- [x] **Step A3.3: Update Gate C note in main repo**

In `2026-08-31-v1-retirement-plan.md` header note:

> Gate C 文档同步：wiki 内容已重写并在 wiki 仓库本地 commit（含 2026-09-13 K/L 残留）。**在 wiki remote push 之前，本项不得视为已关闭。** 主仓 push 不在本计划范围。

Commit main repo docs change.

---

### Task A4: Wave A gates

- [x] **A4.1** `ruff check` PASS。
- [x] **A4.2** `pytest -q` 全绿（≥236）。
- [x] **A4.3** schema 契约测试仍通过（`x-stability` 不破坏校验）。
- [x] **A4.4** `git status` 主仓仅预期提交；`wiki/` clean。

---

## Wave B — G2 PackageDocument 缓存（立即执行）

### Task B1: Implement parse-layer cache

**Files:**

- Modify: `src/uasset_read/package.py`（`parse_package_document`）
- Modify: `tests/test_core.py`（新顶层测试 + 结构门禁 N 递增）
- Modify: `tests/size-baseline.json`（若行数变化触发）
- Modify: `docs/designs/2026-08-31-agent-doc-cache-contract.md`（status → implemented + 执行记录）
- Modify: `docs/designs/README.md`（G2 行）

**Interfaces:**

- Consumes: G2 契约全文；`agent_tools` 已全部走 `parse_package_document`。
- Produces: 同 key 二次 parse 返回同一 `PackageDocument` 对象；API 签名不变。

- [x] **Step B1.1: Internal hashable wrapper**

```python
# package.py (sketch — match contract exactly)
from functools import lru_cache
from pathlib import Path
import os

@lru_cache(maxsize=8)
def _parse_cached(
    resolved: str,
    mtime_ns: int,
    size: int,
    depth: str,
    ids_key: tuple[str, ...] | None,
    tolerant: bool,
    mappings_path: str | None,
    game: str | None,
) -> PackageDocument:
    ...  # current body of parse_package_document, but take Path(resolved)

def parse_package_document(file_path, *, tolerant=True, mappings_path=None, game=None, depth="asset", object_ids=None) -> PackageDocument:
    path = Path(file_path).resolve()
    st = path.stat()  # missing file: same error as today (or preserve open_package_bundle errors)
    ids_key = None if object_ids is None else tuple(sorted(object_ids))
    return _parse_cached(
        str(path), st.st_mtime_ns, st.st_size,
        depth, ids_key, tolerant, mappings_path, game,
    )
```

Constraints:

- No containment hits; no TTL; no file watcher.
- Projection args stay out of key.
- Returned doc is shared and treated read-only (projection already promises non-mutation).
- Do **not** wrap agent tools; cache lives only at parse layer.

- [x] **Step B1.2: Preserve error paths**

Nonexistent path / directory must keep current structured behavior. Cache only after successful `stat`. Failed parses: **do not cache** (contract: only cache successful documents — implement `_parse_cached` so exceptions propagate and are not stored; `lru_cache` does not store exceptions — verify).

- [x] **Step B1.3: Tests (top-level `test_package_document_cache_is_process_local`)**

Add **one** new top-level test in `test_core.py` covering:

1. Same path/depth twice → `doc1 is doc2`.
2. After `os.utime` (or write+close a temp copy under `temp/` is forbidden for permanent tests — use `tests/samples` carefully): prefer a **temp file copy** via `tempfile` in the test (allowed; not committed) then touch mtime → different object.
3. Different `object_ids` / `depth` → different keys (not the same object as the default parse).
4. Agent tools still pass existing assertions without change (they inherit cache).

Bump structure gate: `assert len(funcs) == 14` → `15`, with comment that G2 needs an isolated process-local cache contract test.

- [x] **Step B1.4: Size baseline + docs**

Run size baseline test; update `tests/size-baseline.json` if required. Set G2 doc status `implemented`. Design index row update.

- [x] **Step B1.5: Commit B1**

```powershell
git add src/uasset_read/package.py tests/test_core.py tests/size-baseline.json docs/designs/2026-08-31-agent-doc-cache-contract.md docs/designs/README.md
git commit -m "feat: cache PackageDocument parses per path-stat-depth-key (G2)"
```

---

### Task B2: Wave B gates

- [x] **B2.1** ruff + full pytest green.
- [x] **B2.2** Contract checks: `is` identity; mtime invalidation; no signature change (`inspect.signature(parse_package_document)` unchanged).
- [x] **B2.3** No agent_tools edit required; if any test asserts re-parse side effects, fix the test not the contract.

---

## Wave C — Bundle 1: Zen package body + IoStore package path（research → bounded implement）

> **DEFERRED 2026-09-13（user: 先合并，不处理 iostore/zen）.** No C0–C4 work was executed. Re-open only under a new authorized plan.

### Task C0: Research note (scratch, not committed)

**Files:**

- Create: `temp/c0-zen-iostore-research.md`

- [ ] **Step C0.1: UE source map**

From engine checkout (relative paths only in committed docs):

| Symbol | Relative path | Use |
| --- | --- | --- |
| `FZenPackageSummary` | `Engine/Source/Runtime/CoreUObject/Public/Serialization/AsyncLoading2.h` | Header layout |
| `FExportMapEntry` | same | Export table |
| `FExportBundleEntry` / dependency bundles | same | Body routing |
| `FMappedName` / name map | CoreUObject Zen headers | Names |
| `FIoStoreTocHeader` / chunks / directory index | `Engine/Source/Runtime/Core/Internal/IO/IoStore.h` | Already implemented in `iostore.py` |
| Package trailer / bulk | `Engine/Source/Runtime/CoreUObject/Public/Serialization/PackageTrailer.h` | Cross-check only |

Record: magic/version gates for Zen detection (legacy negative version vs Zen layout), minimum fields for “list package objects”, and what “read one object without loading whole container” means for `.ucas` chunk ranges.

- [ ] **Step C0.2: Inventory existing IoStore tests and fixtures**

Map `tests/test_core.py` IoStore cases + `tests/samples` `global.utoc/.ucas` (and note large MyProject.ucas absent). Classify:

- TOC index: **current** (`iostore.py`)
- Package body from IoStore: **target**
- Zen loose package file: **target / fixture gap**

- [ ] **Step C0.3: GO / partial / NO-GO table**

| Deliverable | Gate |
| --- | --- |
| C1 IoStore chunk `read_at` range source (no full ucas load) | GO if TOC+blocks suffice with existing global container |
| C2 Detect Zen package header on a buffer | GO with synthetic bytes + optional real samples if present |
| C3 `ZenPackageReader` → PackageDocument (tables only, depth package) | GO with synthetic fixtures built from UE struct sizes; **honest partial** without real Zen .uasset |
| C4 End-to-end Zen blueprint semantic | NO-GO until `fixture_gaps.zen_package` filled by user samples |

Default expectation: land C1–C3; leave C4 and full cooked semantic as deferred.

### Task C1: IoStore package body source (bounded)

**Files:**

- Add/Modify: `src/uasset_read/iostore.py` or new `src/uasset_read/iostore_source.py` (prefer extend `iostore.py` if small; else split)
- Modify: `tests/test_core.py` (cases under existing IoStore top-level function if possible — **no new top-level file**)
- Modify: `tests/samples` only if asserting against committed `global.utoc` without loading full ucas

**Interfaces:**

- Consumes: `read_toc`, `IoStoreBlock` compressed sizes/offsets.
- Produces: `read_at(offset, size)` over `.ucas` using block map; compression **explicit capability reporting** (method table); encrypted/signed → structured error (already partially present).

- [ ] **Step C1.1: Implement range reader**

Do not copy whole `.ucas` into memory. Map requested logical chunk → block list → read compressed ranges → decompress only if codec available; if Oodle missing, return structured capability error (metadata still readable).

- [ ] **Step C1.2: Tests**

Synthetic TOC+fake ucas bytes for unit paths; optional integration with committed `global.utoc` that **must not** require the 259MB missing file (skip by absence is forbidden — structure tests so the large container is not required: use TOC-only assertions when ucas absent is a **diagnostic**, not a pytest skip. Prefer synthetic fixtures for decompress path).

### Task C2: Zen package header + tables reader (partial)

**Files:**

- Add: `src/uasset_read/parsers/zen_reader.py` (or `src/uasset_read/zen_reader.py` — match existing layout: parsers/ is fine)
- Modify: `src/uasset_read/package.py` (`open_package_bundle` / layout detection) — **only** when Zen magic/layout matches; else legacy path unchanged
- Modify: `tests/test_core.py` (synthetic Zen summary/import/export tables)
- Modify: `docs/designs/2026-08-26-...` Phase 5 status notes when partial lands
- Modify: `tests/samples/manifest.json` fixture_gaps text if reader exists but samples still missing (do not claim support without samples for semantic)

**Interfaces:**

- Consumes: C0 source map; bounded read helpers from `memory_safety` / archive patterns.
- Produces: `layout="zen"` PackageDocument at `depth=package` with import/export counts and ids; properties/semantic **not claimed** without fixtures.

- [ ] **Step C2.1: Layout detector**

Detect Zen vs legacy **only** from binary layout / version fields per UE source — never from filename.

- [ ] **Step C2.2: Table parse with bounds**

Parse summary offsets, name map, import/export maps with the same count/offset validation style as legacy reader. Fail closed with diagnostics.

- [ ] **Step C2.3: Synthetic fixture tests**

Build minimal Zen buffers in tests (struct layout from UE headers). Cover: good header, truncated tables, absurd counts, offset past EOF.

- [ ] **Step C2.4: Honest capability claim**

README + designs: “Zen package **tables** partial via synthetic fixtures; no Zen semantic samples.” Do not mark Phase 5 exit complete.

### Task C3: Wire CLI/agent only if zero API surprise

- [ ] **Step C3.1:** If `parse_package_document` can accept a Zen path without signature change, leave CLI unchanged.
- [ ] **Step C3.2:** Agent tools automatically work if document shape is valid; add one agent test only if a synthetic Zen file can be written under `temp/` at test time (not committed binary).

### Task C4: Wave C gates

- [ ] **C4.1** ruff + pytest green.
- [ ] **C4.2** No full-container load in unit path (assert read sizes / no `Path.read_bytes()` of whole ucas).
- [ ] **C4.3** README/canonical: Phase 5 still incomplete for “real .utoc/.ucas lists package objects end-to-end with semantic” unless C4 evidence exists.
- [ ] **C4.4** Commit with clear partial scope message.

```powershell
# example
git commit -m "feat: add IoStore range source and partial Zen package table reader"
```

---

## Wave D — Bundle 2: SchemaProvider / cooked unversioned（research → bounded implement）

> **DEFERRED 2026-09-13（same user decision as Wave C).** No D0–D2 work was executed.

### Task D0: Research note

**Files:**

- Create: `temp/d0-schemaprovider-research.md`

- [ ] **Step D0.1: UE SchemaProvider / unversioned serialization map**

Locate in engine checkout:

- Unversioned serialized property schema construction / `FProperty` schema ids
- How cooked packages store schema (usmap vs in-package)
- Existing project path: `parsers/property_parser.py` mapping-driven unversioned + `UnversionedOpaque`

- [ ] **Step D0.2: Gap table**

| Gap | Needed for | Fixture |
| --- | --- | --- |
| Full SchemaProvider equivalent for arbitrary cooked classes | Complete cooked unversioned | cooked unversioned + schema |
| Editor usmap path hardening | Already partial | `UnversionedTest.usmap` exists |
| Opaque tail honesty | Already required | keep |

- [ ] **Step D0.3: GO / partial / NO-GO**

Default: **GO on usmap path hardening + SchemaProvider-shaped interface behind mappings**; **NO-GO on claiming cooked/Zen unversioned complete** without samples.

### Task D1: Schema-facing unversioned hardening

**Files:**

- Modify: `src/uasset_read/parsers/property_parser.py` / unversioned helpers (only where evidence supports)
- Modify: `tests/test_unversioned_fixtures.py`
- Modify: docs: README unversioned bullet; designs index

**Interfaces:**

- Consumes: existing editor usmap fixtures; UE source for schema fragment layout.
- Produces: clearer diagnostics when schema incomplete; optional `SchemaProvider` protocol name if it reduces ambiguity — **no fake completeness**.

- [ ] **Step D1.1:** Document the current mapping-driven contract in code docs only if needed (prefer tests).
- [ ] **Step D1.2:** Add strict tests for: unmapped tail → `UnversionedOpaque`; mapped scalars; no tagged name-index fallback while claiming complete.
- [ ] **Step D1.3:** If cooked samples absent, stop at interface + editor path; do not invent cooked blobs.

### Task D2: Wave D gates

- [ ] **D2.1** ruff + pytest green.
- [ ] **D2.2** README still says unversioned **partial** unless real cooked samples land.
- [ ] **D2.3** Commit.

---

## Wave E — 收尾与记录

### Task E1: Product deferred ledger (no code)

- [x] **E1.1** Ensure `2026-09-13-deferred-capability-bundling.md` open questions remain listed; add one line: “2026-09-13 plan executed Waves A–B only; C/D deferred; Pak/diff/C++/batch-orchestration still out of scope.”
- [x] **E1.2** Design index: plan `current`; G2 implemented; S1 current; Wave C/D deferred in plan body.

### Task E2: Final gates

- [x] **E2.1** ruff PASS.
- [x] **E2.2** `pytest -q` full green on Windows + Python 3.14（237 passed，Wave B 后）.
- [x] **E2.3** `git status -sb` clean (except intentional untracked noise).
- [x] **E2.4** No push performed.
- [x] **E2.5** Wiki working tree clean; wiki still not pushed (local commit `a10946b` only).

## 执行记录（2026-09-13）

1. Wave A: `889330e8` S1 freeze; `2eccee42` batch口径; wiki `a10946b` + `33d4e248` Gate C note; `8d465eb3` docs size baseline.
2. Wave B: `c2151db4` G2 `lru_cache` parse cache + structure gate 15.
3. Closeout docs: `113a138d` plan status A+B current, C/D deferred.
4. **Merge:** local `master` fast-forwarded to `dev-0.6.0` tip `113a138d` (`git push . dev-0.6.0:master`). Working branch remains `dev-0.6.0`. **No remote push** (main or wiki).
5. Wave C/D: not executed (user deferred Zen/IoStore and SchemaProvider).

---

## Execution Order

```text
A1 → A2 → A3 → A4
  → B1 → B2
  → C0 → C1 → C2 → (C3) → C4
  → D0 → D1 → D2
  → E1 → E2
```

Recommended: subagent per wave (A, B, C, D), parent reviews between waves. Do not parallelize B with C (cache first keeps Zen work on a known tip). C and D may be sequential only.

## Self-Review Notes

- Spec coverage: A docs/gates; B G2; C Bundle 1 partial; D Bundle 2 partial; E record.
- Non-goals enforced: no push; no diff/Pak/C++/batch orchestration.
- Risks: Zen without samples over-claimed — controlled by partial language + no semantic claim; G2 sharing mutable docs — controlled by read-only contract + projection non-mutation; structure gate churn — one deliberate N bump with comment.
