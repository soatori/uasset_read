# 代码库精简计划

> **Status**: target（待决策门批准）  
> **Date**: 2026-09-10  
> **Revision**: 2026-09-10 实际项目复核版——统一正式 size ratchet 口径，区分死参数与在用能力，并把 C++ 伪代码退役改为 canonical 决策门。  
> **Goal**: 在不暗中改写 package-first 权威架构、不丢失蓝图执行流/数据流可观察性、不削弱结构化失败诊断的前提下做减法。默认可直接执行的范围只有无消费者的 CLI 日志参数；日志清理、C++ 伪代码、Agent/IoStore/parent/mappings 均须先通过各自决策门。

---

## 0. 审查结论与决策状态

本计划不是新的仓库级架构。源码、测试和真实样本决定 current；
[`2026-08-26-package-first-uasset-parser-refactor.md`](2026-08-26-package-first-uasset-parser-refactor.md)
仍是唯一 authoritative target。

| 切口 | 当前事实 | 状态 |
| --- | --- | --- |
| 五个 CLI `--log-*` 参数 | 被 argparse 接受，但生产代码从不读取 | **默认可执行** |
| `project_logging.py` / `--clean-logs` | 仍有生产调用；只做旧日志清理，不配置全局 logging | **Gate L：产品退役决策** |
| C++ 伪代码生成链 | 仍是 Blueprint semantic JSON 的函数逻辑表示；canonical 明确保留为可选扩展 | **Gate K：canonical 目标变更** |
| `agent_tools` / `iostore` / `parent_resolver` / `mappings` | 产品能力或 deferred issue，不是死代码 | **Gate G：分别决策**（parent_resolver 已于 2026-09-10 退役） |
| C++ 伪代码生成链 | Gate K 已批准并执行 | **retired 2026-09-10**（K0 expression 契约） |
| projection 分页/预算、expressions/models 分包 | package-first 契约或维护性结构 | **不做** |

不得用“零内部 import”“体积较大”或“测试仍绿”代替产品退役决策。

---

## 1. 当前实现事实

### 1.1 核心路径

核心入口是：

```text
python -m uasset_read file.uasset
  -> parse_package_document(...)
  -> PackageDocument
  -> project_document(...)
  -> uasset_read.package JSON
```

蓝图 Kismet 当前路径是：

```text
legacy_reader
  -> extract_kismet_decompiled
  -> read_ufunction_script
  -> parse_bytecode_stream                 # bytes -> expressions
  -> FunctionBodyBuilder / JumpAnalyzer    # expressions -> C++ pseudocode/metric
  -> KismetDecompiledResult.to_dict()
  -> BlueprintFamilyHandler                # 白名单投影到 semantic.functions[]
```

`KismetDecompiledResult.to_dict()` 内含 `expressions`、`error_*`、
`script_metrics` 和 `fallback_reasons`，但 current `BlueprintFamilyHandler` 只公开：

```text
function_name / signature / cpp_code / bytecode_status / translation_status
```

因此，若只删除 `cpp_code` / `translation_status` 而不新增受控的表达式输出，公共
JSON 将只剩函数名、签名和状态，无法支撑“理解执行流和数据传递”的核心用途。

### 1.2 日志事实

current `project_logging.py` 不调用 `dictConfig`、`fileConfig` 或 `basicConfig`，也不安装
process-global handler。旧全局 logging 配置链已经随 v1 删除。

模块当前唯一职责是 `cleanup_project_logs(...)`；CLI 的 `--clean-logs` 仍调用它，并使用：

- `--log-dir`
- `--log-keep-latest`
- `--log-max-total-mb`

其余五个参数仅被 argparse 解析，从未读取：

- `--log-level`
- `--log-cleanup` / `--no-log-cleanup`
- `--log-max-bytes`
- `--log-backup-count`
- `--log-format`

删除这五个参数是死代码清理；删除 `--clean-logs` 及其三个输入参数是公开能力退役，二者不得混为同一 Phase。

---

## 2. 正式体积基线（2026-09-10）

### 2.1 唯一计数口径

`tests/test_size_baseline.py` 对 **Git tracked 文件的物理行**计数，包括空行。计划、提交和
PR 描述必须使用同一口径，禁止使用 `Get-Content | Measure-Object -Line`；后者在此调用
方式下漏计空行。

复测命令：

```bash
python -c "
import subprocess, pathlib
tracked=subprocess.run(['git','ls-files','-z'],capture_output=True,check=True).stdout.decode().split('\0')
for prefix in ('src/','tests/','docs/'):
    suffix='.md' if prefix == 'docs/' else '.py'
    files=[f for f in tracked if f.startswith(prefix) and f.endswith(suffix)]
    lines=sum(len(pathlib.Path(f).read_bytes().splitlines()) for f in files)
    print(prefix, len(files), lines)
"
```

当前正式基线：

| 范围 | tracked 文件数 | 物理行数 | `size-baseline.json` |
| --- | ---: | ---: | ---: |
| `src/**/*.py` | 79 | **23,246** → Phase A 后 **23,228** | 23,228 |
| `tests/**/*.py` | 13 | **5,930** → Phase A 后 **5,949** | 5,949 |

`23,228` / `5,949`（Phase A 实施后）当前既是实测值，也是 ratchet ceiling；两种身份不矛盾。Phase A 之前的官方口径仍是 23,246 / 5,930。

### 2.2 相关模块物理行数

| 模块 | 行数 |
| --- | ---: |
| `agent_tools.py` | 451 |
| `iostore.py` | 437 |
| `parent_resolver.py` | 120 |
| `project_logging.py` | 91 |
| `cli.py` | 410 |
| `kismet/translator.py` | 769 |
| `kismet/body_builder.py` | 435 |
| `kismet/jump_analyzer.py` | 648 |
| `kismet/decompile_bridge.py` | 281 |
| `kismet/result.py` | 105 |
| `kismet/expressions/` | 2,107 / 17 文件 |
| `mappings.py` | 407 |
| `projection.py` | 464 |
| `models/` | 686 / 9 文件 |

三个伪代码生成器文件合计 **1,852 物理行**。删除 `project_logging.py` 加这三个文件时，
文件数是 **79 -> 75**；bridge/result/handler/CLI 的净改动必须实施后实测，不能预先伪精确承诺。

### 2.3 Ratchet 规则

- 每个删除 Phase 后把 `src_python.max_lines` 和 `min_files` 重设为实施后的精确值。
- 删除测试或新增替代测试后，同步重设 `tests_python` 的精确值。
- 新增/修改设计文档时也必须检查 `docs_markdown`；不能只管源码基线。
- wheel 先构建实测，再收紧 `wheel_bytes.max_bytes`，不按源码行数估算。
- `min_files` 是防止未跟踪子树绕过门禁的 floor，不是“文件越多越好”的目标。

当前工作树基线运行结果是 `207 passed, 1 failed`；唯一失败为
`test_docs_tree_within_baseline`（tracked docs 45,145 行，ceiling 45,144）。本计划纳入 Git 后
还会增加一个文档文件及其物理行，Phase 0 必须先按最终文档树实测并更新 `docs_markdown`。

---

## 3. 与权威设计和同伴契约的边界

1. **Canonical**：任何改变 repository-wide target 的决策先改 canonical design，再改实现。本计划不能用“产品决策”一句话覆盖 canonical。
2. **Logging**：canonical 当前要求显式文件日志能力与 dry-run 清理。Gate L 若批准，必须更新其 Logging and Debugging、Decisions、测试策略和 Source Pointers，不只是删一个文件名。
3. **Kismet/C++**：canonical 当前明确写有“Blueprint/Kismet/C++ 生成保留为可选扩展”。Gate K 若批准，必须先改该 Decision、Phase 4/迁移完成条件、README 当前能力说明。
4. **G4** [`2026-08-31-projection-layering.md`](2026-08-31-projection-layering.md)：projection 的 view/depth/selection/pagination/max_bytes/truncation 行为不变。
5. **S1** [`2026-08-31-v2-contract-stability.md`](2026-08-31-v2-contract-stability.md)：`objects[].semantic` 是 experimental。其内部字段删除 **不 bump `format_version`**，但必须记录 breaking note 并同步消费者文档。
6. **G2/S2**：Agent cache 与 payload extraction 契约在 Agent 产品面退役前仍绑定。
7. **#623/#624/#625**：deferred 不等于 canceled。mappings/IoStore/Pak 前置 issue 与 fixture/manifest 声明必须同步处置。
8. **D1/#642**：`kismet` 是 permanent v2 internal；即使 Gate K 通过，也只删除文本生成器，不删除 bytecode extractor、expression tree、UFunction reader 或 token definitions。
9. **Ponytail** [`2026-09-08-ponytail-audit-cleanup-plan.md`](2026-09-08-ponytail-audit-cleanup-plan.md)：其 Task 5 当前保留 `--clean-logs`，与本计划默认 Phase A 一致；若 Gate L/K 通过，必须在执行前把 companion 中对应未完成步骤标记为 canceled/superseded，不能只靠本文件的所有权表覆盖。

---

## 4. 执行计划

### Phase 0 — 文档、决策与基线

- [x] 将本计划和 `docs/designs/README.md` 纳入同一评审。
- [x] 用 §2.1 的正式命令复测 src/tests/docs。
- [x] 把 `docs_markdown.min_files/max_lines` 更新为纳入本计划后的精确值。
- [x] 运行 `python -m pytest -q`，记录基线通过数及任何既有失败。
- [x] 确认本轮只执行 Phase A，还是另有 Gate L / Gate K 的明确批准记录。
- [ ] 若批准 Gate L/K，先更新 canonical 和 companion 文档，再改代码。

**退出条件**：文档状态一致；正式 size test 全绿；产品决策与实现范围无歧义。

### Phase A — 删除五个无消费者的 CLI 参数（默认执行）

从 `cli.py` 删除：

- [x] `--log-level`
- [x] `--log-cleanup` / `--no-log-cleanup`
- [x] `--log-max-bytes`
- [x] `--log-backup-count`
- [x] `--log-format`

保留：

- `--clean-logs`
- `--log-dir`
- `--log-keep-latest`
- `--log-max-total-mb`
- `project_logging.py`

同时把仍保留参数的 help 改成真实语义：它们只给 `--clean-logs` 使用，不声称 CLI 当前会写新日志。

验证：

- [x] 参数搜索确认五个 destination 没有消费者。
- [x] 新增/保留测试：五个删除参数被 argparse 拒绝。
- [x] `tests/test_cli.py` 的 `--clean-logs` 路径仍通过。
- [x] 全套测试通过（214 passed）。
- [x] 精确收紧 src/tests/wheel ratchet。

风险：低。只删除无消费者的兼容参数；仍需在 release note 中记录 CLI 参数移除。

### Gate L — 退役旧日志清理能力（默认不执行）

只有在产品明确不再负责清理旧版本日志后才能执行。

前置条件：

- [ ] canonical 的 CLI logging/cleanup target 已修改。
- [ ] README、Wiki CLI、Quick Start、Public API 和 agent-dev-reference 已列入同步清单。
- [ ] 明确这是一项 CLI/API breaking removal，而不是修复全局 logging 违规。
- [ ] 决定是否提供迁移提示（例如直接删除旧 `log/` 目录由用户自行负责）。

批准后的实现范围：

- 删除 `src/uasset_read/project_logging.py`。
- 删除 `cleanup_project_logs` import、`_handle_clean_logs` 和 `--clean-logs`。
- 删除 `--log-dir`、`--log-keep-latest`、`--log-max-total-mb`。
- 将现有 clean-logs 成功测试改成“旧参数被拒绝”的契约测试。
- 更新 canonical、README、Wiki、agent reference、design index 和 release note。
- 精确收紧 ratchet；文件数减少 1。

### Gate K — 退役 C++ 伪代码生成链（**已批准，2026-09-10 执行**）

Gate K 不是纯重构。它改变 canonical target 和 Blueprint semantic experimental 字段，必须有明确批准记录。

#### K0：先定义替代输出契约

批准删除伪代码时，`semantic.functions[]` 至少保留：

| 字段 | 输出规则 |
| --- | --- |
| `function_name` / `signature` / `bytecode_status` | 所有函数结果 |
| `expression_count` | 成功解析时提供 |
| `expression_types` | 成功解析时提供顶层 expression 类型的有序列表；与 expressions 一一对应，`depth=asset` 最多 128 项 |
| `expressions` | `depth=decode` 时提供完整序列化 expression tree；继续受 `max_bytes` 控制 |
| `expressions_truncated` | `depth=asset` 的类型列表超过 128 项时为 `true`；否则为 `false` |
| `error_code` / `error_message` / `error_context` | 失败时提供 |
| `script_metrics` / `fallback_reasons` / `bytecode_confidence` | 有证据时保留 |

`depth=asset` 不强制输出完整 expression tree，但不能只留下函数名和状态；至少输出
`expression_count`、有序 `expression_types` 和 `expressions_truncated`。`depth=decode` 是检查执行流和数据流的正式入口。

**K0 契约状态：已批准并写入 canonical（2026-09-10）。** 若团队日后拒绝该公共表达式表示，不得静默回退到 `cpp_code`；需新的产品决策。

#### K1：删除生成器

批准 K0 契约并先更新 canonical 后，删除：

| 文件 | 当前物理行 |
| --- | ---: |
| `kismet/translator.py` | 769 |
| `kismet/body_builder.py` | 435 |
| `kismet/jump_analyzer.py` | 648 |
| **合计** | **1,852** |

不删除：

- `bytecode_extractor.py`
- `ufunction_reader.py`
- `native_fields.py`
- `tokens.py`
- `expressions/`
- `kismet/archive.py`
- `decompile_bridge.py`

#### K2：瘦身 bridge/result/handler

`decompile_bridge.py` 继续负责：

```text
FUNCTION_EXPORT_CLASSES
  -> read_ufunction_script
  -> parse_bytecode_stream
  -> build_native_function_signature
  -> 每个 Function/UFunction 一条结果
```

删除：

- `FunctionBodyBuilder`
- `JumpAnalyzer`
- `_collect_pipeline_translation_warnings`
- `cpp_code`
- `translation_status`
- `structured_rate`

保留：

- `bytecode_status in {parsed, no_script, failed}`
- native signature；无法生成时使用 `void {name}()`
- `expressions`
- `error_*`
- `script_metrics`
- `fallback_reasons`
- `bytecode_confidence`
- 每个失败函数仍追加结果，不能因 outer exception 从列表消失

`kismet/result.py` 删除 translation status pair 校验，但继续验证 `bytecode_status` 词汇表并序列化 expressions。

`BlueprintFamilyHandler` 不得采用“只删两个字段”的实现；必须按 K0 把表达式摘要、decode expression tree 和失败诊断投影到公共 semantic。

#### K3：替代测试

删除 translator 专属测试的同一提交必须增加最小严格替代覆盖：

- [ ] 合成或真实函数字节码解析出非空、有序 expressions。
- [ ] `KismetDecompiledResult` 的 `parsed` / `no_script` / `failed` 三种序列化。
- [ ] 失败结果保留 `error_*`、`script_metrics`、`fallback_reasons`。
- [ ] handler 在 `depth=asset` 输出摘要，在 `depth=decode` 输出 expressions。
- [ ] `project_document`/CLI JSON 实际包含 K0 字段并遵守 `max_bytes`。
- [ ] 真实 `BP_CombatCharacter` 样本不仅检查函数名/状态，还检查至少一个函数具有可观察的表达式信息。
- [ ] 一个函数失败时其他函数仍保留。

全套测试通过只是必要条件；若上述断言缺失，现有套件无法证明函数逻辑没有退化。

### Gate G — 其他能力退役（默认不执行）

每项独立决策、独立 Phase、独立提交：

| 项 | 物理行 | 前置条件 | 状态（2026-09-10） |
| --- | ---: | --- | --- |
| `agent_tools.py` | 451 | README + agent-dev-reference + G2/S2 处置；保留 `models.payloads.extract_payload_bytes` 测试 | keep |
| `iostore.py` | 437 | #624 与 manifest/container fixture 策略同步处置 | keep |
| `parent_resolver.py` | 120 | 明确放弃 parent asset 解析并更新 D1/current 文档 | **retired 2026-09-10**（D1 §7） |
| `mappings.py` | 407 | #623、CLI `--mappings`、VersionContext 契约同步；优先 tidy 而非全删 | keep（tidy only） |

禁止因为“没有其他 `src/` import”直接删除公开入口模块。

---

## 5. 明确不做

| 候选 | 原因 |
| --- | --- |
| 删除/大砍 `projection.py` 分页、selection 与预算 | 破坏 G4、S1、CLI/Agent 输出契约 |
| `expressions/` 合并成少数大文件 | 不减少真实逻辑，破坏 token 分包和可维护性 |
| `models/` 合并成少数大文件 | 同上 |
| 把 bridge inline 到 `legacy_reader.py` | 增大已有大文件并削弱失败隔离/诊断可审性 |
| 删除整个 `test_payload_extraction.py` | 主体覆盖真实 payload 字节提取，不属于 Agent wrapper |
| 用目标百分比或文件数倒逼删除 | 体积是 ratchet，不是产品正确性的替代指标 |

Source/SliceReader 与 mappings 的等价 tidy 仍由 ponytail 计划管理；任何删除前重新验证 callers 与 canonical invariant。

---

## 6. 输出契约变更登记

| 变更 | Gate/Phase | 稳定性与版本处理 |
| --- | --- | --- |
| 移除五个无消费者的 CLI `--log-*` 参数 | A | CLI breaking note；不影响 package `format_version` |
| 移除 `--clean-logs` 与 cleanup API | L | 产品能力退役；同步 canonical/docs；不影响 package `format_version` |
| 移除 semantic.functions 的 `cpp_code` / `translation_status` / `structured_rate` | K | semantic experimental；按 S1 **不 bump** `format_version`，但记录 breaking note |
| 新增表达式摘要、decode expressions 与失败字段 | K | semantic experimental；schema/wiki/样本断言同步 |
| pagination / truncation / next_offset / max_bytes / fields / view / depth | — | 不变 |

---

## 7. 文档与消费方同步清单

### Phase A

- `README.md` CLI 参数表
- `wiki/06-Output/CLI.md`
- `docs/release-notes/changelog.md`

### Gate L

- canonical design：Logging and Debugging、Decisions、测试策略、Source Pointers
- `README.md`
- `wiki/01-Getting-Started/Quick-Start.md`
- `wiki/06-Output/CLI.md`
- `wiki/07-Dev-Guide/Public-API.md`
- `docs/reference/agent-dev-reference.md`
- design index、release note、相关 CLI 测试

### Gate K

- canonical design：Phase 4、Migration Completion Gate、Decisions、Source Pointers
- `README.md` 顶部能力说明、pipeline、module table、使用场景
- `wiki/02-Architecture/IR.md`
- `wiki/03-Core-Modules/Exceptions.md`
- `wiki/04-Advanced-Features/Kismet.md`
- `wiki/04-Advanced-Features/CPP-Generator.md`（归档或改为 retired 页面）
- `wiki/04-Advanced-Features/Blueprint.md`
- `wiki/07-Dev-Guide/Public-API.md`
- schema/示例（若枚举 semantic 字段）、release note、下游 golden
- ponytail 计划中仍指向 translator/body_builder/jump_analyzer 的未完成步骤

禁止使用“若有引用”作为验收；上表是当前仓库已核实的最小清单，实施时仍须再次 `rg`。

---

## 8. 执行与提交顺序

```text
Phase 0  文档状态 + 正式基线
  -> Phase A  五个死 CLI 参数（独立提交）

Gate L（可选）
  -> canonical/产品决策提交
  -> cleanup 代码 + 测试 + docs + ratchet 提交

Gate K（可选）
  -> canonical/K0 输出契约提交
  -> expressions/diagnostics 投影 + 替代测试
  -> 生成器删除 + bridge/result 瘦身 + docs + ratchet

Gate G（可选）
  -> 每项分别决策、实施和验证
```

不得：

- 把 Phase A 与 Gate L 混成“日志链删除”。
- 在同一提交中同时实施 Gate L 与 Gate K。
- 先删生成器、以后再补表达式公共输出或测试。
- 在 canonical、companion 与 README 仍声称保留能力时删除实现。
- 用预计行数写 ratchet；必须在最终 diff 上实测。

---

## 9. 验收标准

### 所有 Phase

- `python -m pytest -q` 全绿，无新增 skip/xfail。
- src/tests/docs/wheel ratchet 使用最终 tracked tree 实测并收紧。
- README/Wiki 只描述已实现 current；目标能力显式标 target/deferred/retired。
- 无 unrelated working-tree 变更被覆盖。

### Phase A

- 五个删除参数被拒绝。
- `--clean-logs` 及三个输入参数仍工作。
- 普通 parse/CLI JSON 行为不变。

### Gate L

- canonical 已批准不再提供文件日志与旧日志清理。
- 所有旧日志参数被明确拒绝。
- 库仍不配置 process-global logging。

### Gate K

- bytes -> expressions 能力和真实样本覆盖保留。
- `depth=asset` 至少公开表达式数量/类型摘要。
- `depth=decode` 可检查 expression tree，并受输出预算控制。
- parsed/no_script/failed 均有结构化、可见结果。
- `cpp_code` 消失不会让执行流和数据流变成不可观察。
- semantic experimental breaking note 与所有消费方同步完成。

---

## 10. 最小可交付切片

若当前只做一次低风险落地：

1. Phase 0：修正文档门禁并建立全绿基线。
2. Phase A：删除五个无消费者的 CLI 参数，保留 cleanup 能力。
3. 停止；Gate L、Gate K、Gate G 分别提交产品决策后再继续。

这能完成可信的小幅精简，同时不把目标架构变更伪装成普通 dead-code cleanup。
