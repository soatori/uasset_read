# D2：`semantic/` 包与 `v2/handlers.py` 职责边界

status: target

> **文档状态：current + target**（§1 为基线 `bd3309a7` current 事实，引用 `file:line`；§2-§4 为边界决策与收敛路径 target）。
> 关联：权威设计 `2026-08-26-package-first-uasset-parser-refactor.md`（Asset Handlers、Phase 4/6）；退役门禁见 `2026-08-31-v1-retirement-plan.md`（D1）；版本事实契约见 `2026-08-31-version-context-field-contract.md`（G1）。
> **2026-09-05 执行记录**：§1 描述的双注册表与 §2.2 的 `semantic/` 包均为 **historical 快照**——`semantic/` 已随 D1 Gate B 在 Phase 6（#621）删除，§4 阶段 0–2 已完成。仍有效的是 §2.1（领域语义只进 v2 handler）、§2.3（禁止桥接）、§2.4（类名字符串匹配，不预建索引）与 §4 阶段 3（第四个消费方出现时再提升 `package_data`）；§3 对照表仅作迁移历史参考。

## 1. 现状：两套互不相干的注册机制（historical 快照：基线 `bd3309a7` 源码追认）

### 1.1 v1 侧：`semantic/extensions.py` 类名注册表

- 注册表：`_REGISTRY: dict[str, Callable]`，键为精确 UE 类名（`semantic/extensions.py:16`；`register_extension:20-38`，重复注册抛 `ValueError`，并登记 `domain_format/domain_format_version` → `_DOMAIN_FORMATS:17`）。
- 接线方式：**import 副作用**。`semantic/__init__.py:18-31` 用 14 条形如 `import uasset_read.semantic.<domain>  # noqa: F401` 的语句触发各 domain 包的模块级 `register_extension(...)` 调用（全仓实测 18 处调用点，分布在 14 个 domain 包的 `__init__.py`，部分为 for 循环多类注册，如 `semantic/texture/__init__.py:9-22` 一次注册 6 个 Texture 类）。
- 触发链：任何 `import uasset_read.semantic.*` 都会先执行父包 `__init__`（Python 包语义），因此注册总在 v1 JSON 路径加载时发生。
- 消费链（唯一）：`semantic/builder.py:21` 引入 `get_extractor/get_domain_format` → `build_semantic_ir`（`builder.py:226`）先 `_select_primary_export`（`builder.py:191,247`，单主资产模型）再按主导出类名查表 → 结果合入 `SemanticIR.content` → `project_semantic/validate_semantic_document/render_semantic_json`（`core/__init__.py:211-222`）→ 仅 CLI `--legacy-json`/`--markdown`（`cli.py:420,489`）。
- 伴生注册：domain validator 同样以 import 副作用注册（`semantic/validator.py:31-36`，如 `semantic/texture/__init__.py:23`）。
- 契约形态：extractor 签名 `(package_ir, export_ir, coverage_model, evidence_list) -> dict`，输出 Semantic 1.x domain format（`uasset_read.<domain>_semantic` 1.0.0）。

### 1.2 v2 侧：`v2/handlers.py` Protocol 注册表

- 注册表：`_HANDLERS: list[AssetHandler]`（`v2/handlers.py:33`；`register_handler:36-38`）。协议：`supports(obj, context) + enrich(obj, context, all_objects, package_data)`（`handlers.py:17-29`）。
- 接线方式：**同一模块内显式实例注册**。`handlers.py:463-468`（UserDefinedEnum/UserDefinedStruct/DataTable/Texture/TexturePayload/Sound）、`690-693`（Material/MaterialInstance/Skeleton/Mesh）、`815-822`（AnimBlueprint/Blueprint 族）、`864`（Niagara）——共 13 个 handler 实例。
- 消费链：`LegacyPackageReader.read()` 在 `depth in ("asset","decode")` 逐对象调用 `run_handlers`（`v2/package/legacy.py:445-472`）；结果写入 `ObjectRecord.semantic/coverage`，失败降级为 `HANDLER_FAILURE` diagnostic 且不影响同包其他对象（`legacy.py:462-472`、`handlers.py:63-91`）。
- 上游：`v2/api.py:16` → CLI 默认 JSON（`cli.py:438-461`）与 Agent tools（`v2/agent_tools.py:17-18`）。
- 数据契约：handler 只读 `obj.properties`（normalize 后的属性袋，`legacy.py:603`）与 `package_data` tuple `(export_map, name_map, extras)`（`legacy.py:456`）；不触碰 archive。版本事实只经 `VersionContext`（G1；基线实际仅 `depth` 被读，`handlers.py:728,740`）。

### 1.3 交叉情况

两表零共享：`v2/handlers.py` 不 import `semantic/`；`semantic/*` 不 import `v2/handlers`（双向 grep 核实）。同名域（texture/data_table/…）在两侧是**重复实现**，输出契约不同（1.x domain format vs `objects[].semantic.kind`），语义内容不保证逐字段一致。

## 2. 决策（target）

1. **权威提取层是 `v2/handlers.py` 的 `AssetHandler` Protocol**。新增或修改任何领域语义只进 v2 handler，输出只能是 `objects[].semantic`（一个 envelope，无新顶层 format——AGENTS.md 目标不变量）。
2. **`semantic/` 整包定位为 v1 legacy adapter 专属**：它唯一职责是让 `--legacy-json` 继续吐出 Semantic 1.x；不再演进（feature freeze），随 D1 退役计划整体删除。
3. **禁止桥接**：不引入"v1 extractor → v2 handler"或反向的适配层/双注册宏/共享 extractor 内核。两边重复实现是迁移期的可接受成本，最终以删除一侧收敛（权威设计"不保留永久双实现"）。
4. **`supports` 匹配保持类名字符串现状**：`_REGISTRY` 的精确类名 dict 优于 v2 的线性 list 扫描是事实，但在 handler 数量达到性能可观测问题之前不预建索引（不为单一实现抽框架）。

## 3. v1 域 → v2 handler 覆盖对照（诚实清单）

| v1 domain 包 | v1 注册类（节选） | v2 handler 现状 | 差距 |
| --- | --- | --- | --- |
| `user_defined` | UserDefinedEnum/Struct | `UserDefinedEnumHandler`、`UserDefinedStructHandler` | 基本对齐（v2 从属性袋重建） |
| `data_table` / `curve_table` | DataTable / CurveTable | `DataTableHandler`（三类合一，`handlers.py:256-301`） | CurveTable 真实 fixture 缺（#626） |
| `texture` | 6 个 Texture* 类（`texture/__init__.py:9-16`） | `TextureHandler`+`TexturePayloadHandler`：仅 Texture2D/TextureCube | RenderTarget/Array/Volume 未覆盖；payload 仅 ImportedSize 摘要 |
| `sound` | SoundCue/Wave 等 | `SoundHandler`：SoundWave/SoundCue/SoundAttenuation | 扩展声音类（SoundMix/Class/Submix 等 v1 `_TYPE_MAP` 有项）未覆盖 |
| `material` | Material/MaterialInstance/MaterialInstanceConstant（3 处调用） | `MaterialHandler`、`MaterialInstanceHandler` | 对齐面窄，v1 更深字段未比对（Gate A parity 范畴） |
| `skeleton` / `mesh` | Skeleton / Static+SkeletalMesh | `SkeletonHandler`、`MeshHandler` | v2 骨名来自 name_map 正则（`handlers.py:574-578`），是简化实现 |
| `blueprint` / `anim_blueprint` | Blueprint/GeneratedClass 族 4 类 | `BlueprintFamilyHandler`（asset 浅 summary；decode 深度：graph/node/pin 解码 + declaration + SCS components + NewVariables names + VarType + Kismet） | **已迁移（Phase 4.5）**：fixture 测试 `tests/test_blueprint_decode.py` 覆盖 StackOBot/BP_CombatCharacter/ABP_RifleAnimLayers/ALS_AnimBP。已含 VarType（`FEdGraphPinType`）类型解码与 Kismet 反编译（fixture 测试：`tests/test_blueprint_decode.py`）。仍未迁移：C++ skeleton、parent-asset 解析（属 D1 deferred） |
| `niagara` | NiagaraSystem/Emitter/Script（`niagara/__init__.py:8`） | `NiagaraHandler` 覆盖 14 个 script/node 类，**不含 NiagaraSystem/NiagaraEmitter** | 两个顶层类未覆盖 |
| `anim` | AnimSequence/ Montage 族 | 无 | 未迁移 |
| `movie` | LevelSequence 族 | 无 | 未迁移 |
| `standalone` | 杂项单资产 | 无 | 未迁移 |

## 4. 收敛路径（与 D1 门禁对齐，不引入新抽象）

- **阶段 0（立即生效）**：feature freeze。`semantic/extensions.py` 不新增注册；code review 检查项：新语义 PR 不得触碰 `semantic/`（validator/extractor 修 bug 除外，只修不扩）。
- **阶段 1（Phase 4 推进）**：§3 中"未覆盖/未迁移"行按权威设计 handler 顺序补 v2 handler（Data/manifest → Texture/Sound → Skeleton/Mesh → Material/Niagara graph → Blueprint/AnimBlueprint 扩展），每个新 handler 带真实样本 + 缺失/partial 样本 + 明确 coverage（权威设计 Phase 4 退出条件）。迁移以 D1 Gate A 的逐域三态清单为准。
- **阶段 2（D1 Gate B 时点）**：`--legacy-json` 移除的同一原子变更中删除 `semantic/` 整包、其 domain schemas 与 domain validator 注册；不留"注册表壳"。
- **阶段 3（收尾）**：`run_handlers` 的 `package_data` tuple 若出现第四个消费方再提升为命名数据类；当前保持 tuple（单一 reader 构造，无第二实现）。

## 5. 验收

- 本文 §1 的接线图每条边都有 `file:line` 依据；后续修改两表任一注册机制时必须同步更新本文。
- "域已迁移"声明只在 v2 handler + fixture 测试 + parity 清单三件齐备后可用；否则文档与 release notes 保持 partial/unavailable 表述。
