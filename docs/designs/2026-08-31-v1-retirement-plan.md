# D1：v1 pipeline 退役计划

status: target

> **文档状态：target**（退役决策与门禁；文中"现状"段落为基线 `bd3309a7` 的 current 事实，引用 `file:line`）。
> 关联：`docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`（Phase 6 删除旧路径）；Issue #621；本文与 `2026-08-31-semantic-handlers-boundary.md`（D2）、`2026-08-31-version-context-field-contract.md`（G1）配套。
> **本轮不删任何代码**，只冻结退役契约。

## 1. 双轨现状（current）

两条独立管线并存，CLI 在入口分流：

```text
v1（仅 --legacy-json / --markdown / --batch）：
  parse_single (core/__init__.py)
    -> parse_uasset_with_linker (pipeline/core.py:394)   [format=json]
    -> build_package_ir (ir_builder.py:740)              [core/__init__.py:198]
    -> build_semantic_ir -> project_semantic -> validate_semantic_document
       -> render_semantic_json                           [core/__init__.py:211-222]
    -> MarkdownRenderer                                  [core/__init__.py:225-227]

v2（默认输出）：
  parse_package_document (v2/api.py:16)
    -> LegacyPackageReader.read (v2/package/legacy.py:293)
    -> run_handlers (v2/handlers.py:46, legacy.py:455)
    -> project_document (v2/projection.py:67)            [cli.py:438-461]
```

CLI 证据：默认走 v2 的判定在 `cli.py:420`（`if not args.legacy_json and not args.markdown:`）；`--legacy-json` 帮助文本已标 deprecated（`cli.py:92-95`）；v1-only flag 在 v2 路径被显式忽略并告警（`cli.py:421-437`）；否则落到 `parse_single`（`cli.py:489-504`）。Agent tools 只走 v2（`v2/agent_tools.py:17-18`）。

## 2. v1 模块清单与替代映射（从源码 grep 核实）

### 2.1 v1 专属（退役对象）

| v1 模块 | 规模/入口证据 | v2 替代 | 状态 |
| --- | --- | --- | --- |
| `core/__init__.py` 中 `_parse_and_render`/`parse_single`/`parse_batch`/`diff_single` | `core/__init__.py:145-227,74,251,466` | `v2/api.py:16 parse_package_document` + `v2/projection.py` | 替代（batch/diff 见 deferred） |
| `pipeline/`（`core.py:394` parse_uasset_with_linker、`stages.py`、`post_process.py`、`config.py`） | 共约 1800 行 | `v2/package/legacy.py:293 LegacyPackageReader.read` | 替代 |
| `ir_builder.py`（`build_package_ir:740`，2082 行） | v1 PackageIR 构建 | `legacy.py:169-215 _build_object_record_direct` → `v2/object_model.ObjectRecord` | 替代 |
| `models/ir.py`（PackageIR/ExportIR） | v1 IR 模型 | `v2/document.py:44 PackageDocument` + `v2/object_model.py` | 替代 |
| `semantic/` 整包（builder/projection/validator/render/canonical/coverage/diagnostics/references + 14 个 domain 包，18 处 `register_extension` 调用） | `semantic/__init__.py:12-31`；`semantic/builder.py:226` | `v2/handlers.py` Protocol + `run_handlers`；投影 `v2/projection.py` | 部分替代，见 D2 §3 域映射 |
| `renderers/markdown_renderer.py`（渲染 PackageIR，已随 v1 删除） | `--markdown` | 无 v2 替代 | **wontfix**（产品决策已下，见 §5）：旧版输出格式不重建，v2 只投影 `PackageDocument` JSON |
| `link/`（PackageLinker、parent asset 解析、`normalize_world_partition_path`，被 `ir_builder.py:1094,1514` 使用） | `--include-parent-assets` | **无 v2 替代**（v2 不做跨包加载） | **deferred**：依赖 loose sidecar/容器 fixture（#627） |
| `graph/` + `kismet/` + `blueprint/`（约 30+ 文件，深度图/字节码/C++ skeleton） | 由 `semantic/{blueprint,anim_blueprint}` 与 `ir_builder.py:909,1293` 驱动 | v2 仅 `BlueprintFamilyHandler` 浅 summary + decode 级节点/边粗提取（`handlers.py:696-822`） | **deferred**：Blueprint v2 深解码属权威设计 Phase 4.5，不被 #623-#627 阻塞，属实现排期 |
| `versioning.py VersionContainer`（`versioning.py:24`；消费者 `link/linker.py`、`models/result.py`、`parsers/property_types.py`、`pipeline/stages.py`） | v1 版本容器 | `v2/version.py VersionContext`（G1 契约） | 替代（property_types/stages 属 v1 侧，随之退役） |
| `serializers/graph*.py`（graph/graph_node/graph_pin/graph_helpers） | v1 图序列化 | 无（v2 handlers 不读 archive） | 随 graph/ 退役 |
| `schemas/*_semantic.schema.json`（12 个 Semantic 1.x domain schema + 1 个 `semantic.schema.json` envelope，共 13 文件） | `src/uasset_read/schemas/` | `docs/designs/contract/package_document_v2.schema.json`（v2 envelope）；semantic 内容改用 `objects[].semantic.kind` discriminator | 随 Semantic 1.x 删除 |
| CLI `--legacy-json`、`--output-level`、`--verbose/--schema/--hex-view/--full-parse` v1 语义、`--batch`、`--diff` | `cli.py:92-95,118-145,393-395,463-487` | v2 对应：`--depth/--limit/--max-bytes`（`cli.py:98-115`）；**batch/diff 无 v2 替代** | batch/diff **deferred** |
| `batch_worker.py` + `parse_batch` 隔离进程模型 | `core/__init__.py:15`（import） | 无 | **deferred**（v2 reader 尚无 batch 编排需求证据） |

### 2.2 共享层（**不在**退役范围）

v2 直接复用、删除 v1 时必须保留或收编：`serializers/{package_summary,object_resources,property_tags}.py`（`legacy.py:16-30` 直接 import）、`parsers/property_parser.py:parse_properties_from_export`（`legacy.py:559`）、`package.py:PackageArchive`（`legacy.py:15`）、`archive.py`、`constants.py`、`exceptions.py`、`config.py`。注意 `parsers/property_types.py` 与 `pipeline/stages.py` 目前消费 v1 `VersionContainer`；property 分支收敛到 VersionContext（G1 §4）前不得删除 v1 侧胶水。

## 3. 移除前提条件（gates）

### Gate A — decode parity 验证范围

在删除任一 v1 模块前，必须对同一 fixture 集合完成 v2↔v1 对比并归档结论：

- 结构层：`objects` 数量/id/class/relations 与 v1 PackageIR export 枚举一致（package/object depth）。
- 语义层：`objects[].semantic` 对 v1 Semantic 1.x `content` 的逐域字段覆盖清单（每域"已覆盖/部分/放弃"三态，部分必须有 coverage/diagnostic 证据）。
- golden 仅用于识别回归，不作为 v2 schema 约束（权威设计 Phase 0）。
- 环境门禁沿用本机 Windows + Python 3.14 全绿；不得以 skip/xfail 模拟 parity。

### Gate B — `--legacy-json` 废弃时间线

1. **现在起**：help 文本已标 deprecated（`cli.py:94`）；发布说明每次列 usage 观察。
2. **v2 schema 稳定一个大版本后**方可移除：即 `package_document_v2.schema.json` 的 `format_version` 在当前大版本内不再发生破坏性变更，随后一个完整大版本周期（发布 N 移除、N+1 起 `--legacy-json` 报 explicit unsupported 错误退出码，而非静默降级）。
3. 移除动作 = 同时删 `semantic/`、`renderers/`、`pipeline/`、`ir_builder.py`、`link/`、`graph|kismet|blueprint`（未被 v2 收编部分）、`schemas/*_semantic*`、v1-only CLI flags、`versioning.py` 及 `core/` v1 入口；一次原子变更，不留半删状态。

### Gate C — Semantic 1.x 删除门禁

- 18 处 `register_extension`（14 域）全部处于三态之一：v2 handler 已接管（含 fixture 测试）、明确放弃并记录、或标记 deferred 且挂具体 fixture issue（#623 unversioned/USMAP、#624 Zen/IoStore、#625 Pak、#626 CurveTable、#627 loose sidecar）。
- `validate_semantic_document`（`semantic/validator.py:39`）与 domain validator 注册（`validator.py:31-36`）无任何非 `--legacy-json` 调用方（基线唯一调用点 `core/__init__.py:214`）。
- 文档同步：README/wiki 中 Semantic 1.x 输出全部降级为 historical（AGENTS.md 文档权威规则）。

### Gate D — 外部消费者

移除前核对 `docs/reference/agent-dev-reference.md` 与 wiki：Agent 工具链已全走 v2（基线 `v2/agent_tools.py` 无 v1 import，核实）；如发现下游解析 `--legacy-json` 文本的工具，先迁移。

## 4. 本轮不做的事

- 不删除、不移动任何源码文件；不改 CLI 行为。
- 不承诺 #623-#627 的 fixture 获取时间。
- markdown 已宣布放弃（旧版输出格式族整体废弃，见 §5）；batch/diff/parent-assets 仍标记 deferred，等待各自产品决策。
- 不引入新抽象层（如"退役 adapter 框架"）；映射表即契约。

## 5. 决策记录：旧版输出格式整体废弃（2026-09-05）

决策：**输出旧版格式的能力永久放弃，不在 v2 重建。** 本决策取代 §4 中"等待单独产品决策"对 markdown 的表述，并落实 #643 已提交的 wontfix 判定。

| 能力 | 载体 | 判定 | 理由 |
| ------ | ------ | ------ | ------ |
| Semantic 1.x JSON | `semantic/` 全目录、`--legacy-json` | **wontfix** | v2 `uasset_read.package` schema 已完全取代旧格式 |
| Markdown 渲染 | `renderers/markdown_renderer.py`、`--markdown` | **wontfix** | 属于被废弃的旧版输出格式；v2 唯一输出是 PackageDocument JSON |
| 格式注册表 | `core.list_formats`、`--list-formats` | **wontfix** | 只剩一种格式，注册表无对象可列 |

仍为 deferred（不是输出格式，属工作流/解析能力，各自等产品决策）：`--batch`（reader 级批量）、`--diff`（schema 化对比）、parent-assets（`link/` 已留基础设施，依赖 #627）。

落地事实（`git ls-files` 核实，非文档推断）：`semantic/`、`renderers/`、`schemas/`、`core/`、`pipeline/`、`ir_builder.py`、`batch_worker.py`、`blueprint/`、`bulk/` 在 `src/uasset_read/` 下均无 tracked 文件——即上述 wontfix 能力的代码已不存在，本决策只关闭"重建"预期，不产生删除工作。

CLI 契约：这五个 flag 由 `cli.py` 的 `retired` 集合显式拒绝（`parser.error`，退出码 2），`README.md` 第 37 行按此描述。维持显式拒绝而非静默忽略，是本决策唯一需要长期保留的兼容行为。
