# PackageDocument v2 契约稳定性分级（S1）

status: target

> 对照 `docs/designs/contract/package_document_v2.schema.json` 给字段分级 stable / experimental，并决定版本字段去留。分级依据：Phase 6（删除旧路径）之前，payload 与 semantic 域尚未定型，保持 experimental。

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
| `payloads` | **experimental** | 本轮 fabricate 提取正被撤回为 `PAYLOAD_EXTRACTION_DEFERRED`（见 [`2026-08-31-payload-extraction-path.md`](2026-08-31-payload-extraction-path.md)），descriptor 来源与 `status` 语义待定型 |

### `objects[]`（schema `:162-224`）

| 字段 | 级别 | 理由 |
|---|---|---|
| `id` / `table_index` / `name` / `class` / `roles` / `serial_region` / `status` | stable | 对象身份与分层状态，"All objects are addressable" 不变量的载体 |
| `properties` | **experimental** | 值模型只覆盖 tagged 路径；unversioned reader（Phase 2 目标）落地前 `PropertyValue` 树形状可能变 |
| `semantic` | **experimental** | Phase 4 handler 域；`kind` discriminator 下各域字段逐个在动 |
| `coverage` | **experimental** | `feature` 字符串词汇表由各 handler 自定，无契约（如 `handler.SoundHandler` vs `texture.srgb`，见 `src/uasset_read/v2/handlers.py`） |
| `flags` | stable | raw/debug-only 原始值，语义即 EObjectFlags |

## 已发现的 schema/实现漂移（记录，随撤回变更一并修）

- **payload id 模式不匹配**：schema 要求 `"^payload:[0-9]+$"`（`:283`），实际 id 是 `payload:export:<i>`（`src/uasset_read/v2/package/legacy.py:489`，工具侧解析同样按此假设：`agent_tools.py:197-198`）。schema 应改为 `"^payload:(export|import):[0-9]+$"`。本文档不改文件，列为 follow-up。

## 落地动作

1. schema `$defs` 内为 experimental 子 schema 加 `"x-stability": "experimental"` 标注（`x-` 前缀不影响校验），stable 不加标注即为默认。
2. `docs/agents/` 消费方指引：experimental 键不得进入跨版本 golden 断言。
3. Phase 6 完成时输出一次 `format_version` 冻结声明。
