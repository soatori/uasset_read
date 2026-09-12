# PackageDocument v2 契约稳定性分级（S1）

status: current

> 对照 `docs/designs/contract/package_document_v2.schema.json` 给字段分级 stable / experimental，并决定版本字段去留。
>
> **2026-09-13 执行记录（Wave A / Task A1）：** Phase 6 已完成。`format_version: "2.0"` 对 **stable 域** 冻结为兼容承诺；experimental 域已在 schema 标注 `"x-stability": "experimental"`。此后 stable 破坏性变更必须 bump major（`"3.0"`）；experimental 增删改不 bump。

## format_version 决策：**不加新字段，复用现有 `format_version`**

信封已有版本字段且已被 schema 锁定：投影输出 `"format_version": "2.0"`（`src/uasset_read/v2/projection.py:175`），schema 以 const 约束（`package_document_v2.schema.json:13-15`），且在顶层 required 列表内（schema `:7`）。再加 `schema_version`/`contract_revision` 属于重复记账，拒绝。

升降级规则（canonical design §Schema 策略："Schema 版本只在不兼容公共契约变化时升级"）：

- **experimental 域内任何增删改**：不动 `format_version`。消费方对 experimental 字段的依赖以"pin + 特征探测"自保，版本字段不为它们背书。
- **stable 域 additive 变化**（新增可选键）：不 bump（schema `additionalProperties: false` 下加键是显式契约动作，评审即门禁）。
- **stable 域破坏性变化**：Phase 6 之前允许 minor 内直接改并记录 breaking note（尚未对外承诺稳定）；**Phase 6 完成后 `format_version` 冻结为稳定承诺**，此后破坏性变化才 bump major（"3.0"）。

## 字段分级

### 顶层（schema `:7-95`）

| 字段 | 级别 | 理由 |
|---|---|---|
| `format` / `format_version` | stable | 信封身份，const |
| `view` / `depth` | stable | 枚举定型（canonical §View 与 Depth） |
| `source` | stable | `kind/name/size` 三键定型（schema `:99-123`） |
| `package` | stable | PackageInfo 字段对应已验证的 summary 读取路径 |
| `objects`（容器） | stable | 数组 + 全 exports 是 package-first 的核心承诺 |
| `relations` | stable | kind 枚举定型（schema `:253-255`） |
| `dependencies` | stable | import 投影四键（schema `:268-278`） |
| `diagnostics`（条目结构） | stable | 必填四键定型（schema `:305-351`）；`code` 取值集合是开放集，**新增 code 不算破坏** |
| `summary` | stable | 键定型（schema `:365-393`） |
| `next_offset` / `truncation` / `debug` | stable | 截断可发现性契约（canonical §Selection 与 Pagination） |
| `payloads` | **experimental** | Descriptor 来源与 `status` 语义仍可演进（cooked sidecar 提取已实现，见 [`2026-08-31-payload-extraction-path.md`](2026-08-31-payload-extraction-path.md)）；schema 已标 `x-stability` |

### `objects[]`（schema `:162-224`）

| 字段 | 级别 | 理由 |
|---|---|---|
| `id` / `table_index` / `name` / `class` / `roles` / `serial_region` / `status` | stable | 对象身份与分层状态，"All objects are addressable" 不变量的载体 |
| `properties` | **experimental** | 值模型只覆盖 tagged 路径；unversioned reader（Phase 2 目标）落地前 `PropertyValue` 树形状可能变 |
| `semantic` | **experimental** | Phase 4 handler 域；`kind` discriminator 下各域字段逐个在动 |
| `coverage` | **experimental** | `feature` 字符串词汇表由各 handler 自定，无契约（如 `handler.SoundHandler` vs `texture.srgb`，见 `src/uasset_read/v2/handlers.py`） |
| `flags` | stable | raw/debug-only 原始值，语义即 EObjectFlags |

## 已发现的 schema/实现漂移（已修）

- ~~**payload id 模式不匹配**~~：schema 已改为 `"^payload:(export|import):[0-9]+$"`（与 `PayloadDescriptor.id` 一致）。

## 落地动作（2026-09-13 已执行）

1. [x] schema 内 experimental 子 schema 加 `"x-stability": "experimental"`（stable 不加标注即为默认）：`ObjectEntry.properties`、`ObjectEntry.semantic`、`ObjectEntry.coverage`、顶层 `payloads`。
2. [x] 消费方指引写入 `docs/reference/agent-dev-reference.md`：experimental 键不得进入跨版本 golden 断言。
3. [x] Phase 6 完成后输出 `format_version` 冻结声明（见文首执行记录；同步 README / changelog / design index）。

## 冻结声明（normative）

- **Envelope identity:** `"format": "uasset_read.package"`, `"format_version": "2.0"` — stable.
- **Stable fields** (default when not marked experimental): listed in the tables above under stable; breaking changes bump `format_version` major to `"3.0"`.
- **Experimental fields:** `objects[].properties`, `objects[].semantic`, `objects[].coverage`, top-level `payloads` (schema `"x-stability": "experimental"`). Additive or breaking changes inside these keys do **not** bump `format_version`.
- Consumers must not pin cross-version golden assertions on experimental keys.
