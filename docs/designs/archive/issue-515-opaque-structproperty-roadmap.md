# 修复计划：#515 Opaque StructProperty 后续路线图

status: historical

> 状态：计划中（2026-08-02）  
> 范围：为每种已证实的结构建立独立、可验收的解析契约；不把 `opaque` 本身视为错误。

## 当前基线

- `EditedDocumentInfo` 已支持：仅通过零大小 tagged-struct fallback 解析，未知或无边界数据仍保留原始降级行为。
- `MovieSceneDoubleChannel`、`MovieSceneFrameRange` 与 `MovieSceneFloatChannel` 已有实现和覆盖；聚焦回归测试通过。
- 仓库样本中仍有大量、彼此无关的 `opaque` StructProperty，因此不能为它们增加一个通用二进制解码器。
- B1-pre（2026-08-05，源自 #521 收尾路线图）：扫描脚本 `temp/scan_opaque_structs.py` 已扩展至 `partial_metadata` 导出（此前结构性遗漏；commit `28725871`）；新增 Niagara 结构候选及筛选结果见 `issue-515-candidates.md` 的 Niagara Intake 一节。筛选结论：`NiagaraVariable` 与两个数组元素结构（`FNiagaraGraphScriptUsageInfo`、`FVersionedNiagaraScriptData`）通过选择门槛，各自建立 #515 子 Issue；其余五个 Niagara 结构（`NiagaraVariableMetaData`、`NiagaraVariant`、`NiagaraTypeDefinition`、`StaticSwitchTypeData`、`NiagaraParameterStore`）经字节级校验已被 tagged fallback 完整解码，不作为 opaque 候选收录。

## Slice Log

### 2026-08-05 — FExpressionInput material-input family: COMPLETE

- Decoded (native layout, `SerializeExpressionInput` / `SerializeMaterialInput`,
  `MaterialShared.cpp:439-487`, UE `5.8.0-release` @ `7deeb413d`):
  - `ExpressionInput` — 36 bytes (Expression, OutputIndex, InputName, Mask, MaskR/G/B/A).
  - `ScalarMaterialInput` — base 40 bytes + float constant (tag.size 44).
  - `ColorMaterialInput` — base 40 bytes + FColor (44) or FLinearColor (56).
  - `VectorMaterialInput` — base 40 bytes + FVector3f (52) or FVector3d (64).
- These structs have a custom `Serialize`, so the tagged fallback is never valid
  for them: unrecognized sizes or failed decodes stay `opaque` and consume the
  payload, instead of falling through to the tagged loop.
- Tests: `tests/test_issue_515_material_inputs.py` (6 synthetic byte-layout
  cases), `tests/temp/test_issue_515_material_inputs_real_sample.py`
  (25 family structs in `tests/samples/StarterContent_M_Wood_Walnut.uasset`,
  all `parse_status: success`).
- Commits: `242b66e7` (decoder), `d8278880` (real-sample acceptance).

### Remaining candidates (each needs its own evidence-backed slice)

| Candidate | Count / fixture | Notes |
| --- | --- | --- |
| `NiagaraVariable` | 12 × `NM_BPSystemEvent.uasset` | offset-based payload; adjacent to #521 |
| `UnknownStruct` (FCurveMetaData values) | 126 × `CiciToon_SK_Mannequin.uasset` | zero-size tagged; needs type-name resolution |
| `MeshSectionInfoMap` value type | correctness gap, not opacity | map values decode as `IntProperty`; `FMeshSectionInfo` fields not recovered (map value struct names are reflection-only, absent from the stream) |

## 目标与非目标

目标是逐个结构类型在真实夹具上公开最小且可验证的字段，并明确何时必须保留 `opaque` 或 raw fallback。

非目标：

- 不承诺一次性解析所有未知结构。
- 不根据属性名称、长度或相邻字节猜测 native layout。
- 不将未知数据的 `parse_status` 从 `opaque` 提升为 `partial_metadata`。

## 工作量估算

| 阶段 | 估算 | 说明 |
| --- | --- | --- |
| Phase 1：候选清单扫描 | 2-3 天 | 扫描脚本开发 + 候选筛选 + Issue 创建 |
| Phase 2：每个结构实现切片 | 1-2 天/结构 | 取决于复杂度和 UE 源码可用性 |
| Phase 3：回归与收尾 | 1 天 | 全量回归 + Issue 整理 |
| **总计** | **取决于 Phase 1 结果** | 若有 50+ opaque 类型则需长期迭代 |

## 阶段 1：建立候选清单和选择门槛

### Phase 1 交付物

- [x] 扫描脚本：`temp/scan_opaque_structs.py`
- [ ] 候选清单：`docs/designs/issue-515-candidates.md`
- [ ] 候选筛选验证：每个候选均具备 ✓fixture ✓UE 源码 ✓边界证明
- [ ] 为每个通过筛选的候选创建独立 Issue

### 执行步骤

1. 新增仅诊断性的扫描脚本，遍历受版本控制的样本，按 `struct_type` 统计 `opaque` 值、出现样本、`raw_size` 与外层属性路径。
2. 为每个候选记录：UE 版本、文件 SHA-256、至少一个可重现的属性路径，以及相应的 UE 源码类型或序列化函数。
3. 只选择同时满足以下条件的候选进入实现：有稳定夹具、可确定边界、可从源码或 tagged 属性证明字段语义。
4. 每个通过选择门槛的结构创建独立 Issue；#515 保留为进度追踪项。

### 候选优先级矩阵

| 维度 | 评估标准 | 权重 |
| --- | --- | --- |
| 频率 | 在版本控制样本中出现次数 | 高 |
| 影响 | 对用户可见数据的重要性 | 高 |
| 复杂度 | 解析难度（tagged fallback vs native parser） | 中 |
| 证据 | UE 源码文档化程度 | 高 |

### Native Parser 触发条件

当满足以下任一条件时需要 native parser（快速路径二进制解析器）：

- 结构体在 UE 源码中有固定二进制布局文档
- Tagged fallback 无法表达该结构体的二进制布局
- 性能需求要求原生解析

Tagged fallback 足够的条件：

- 结构体使用 PropertyTag 序列化
- 字段在 tag 流中自描述

验收：扫描结果不改变解析输出；候选表不把 `UnknownStruct` 或零边界值误报为可解析。

## 阶段 2：每个结构的实现切片

每个子 Issue 按下列顺序执行：

1. 在 `tests/temp/` 增加真实夹具回归用例，先断言当前行为和目标字段；固定夹具 SHA-256。Fixture 存放于 `tests/samples/`（版本控制）或 `tests/temp/`（临时验证）。
2. 记录 UE 源码证据、版本条件、字段类型和 byte/tagged-property 边界到对应设计文档。
3. 在 `src/uasset_read/parsers/property_types.py` 扩展既有 tagged fallback，或在证据证明需要 native parser 时新增专用解析器。
4. 对截断、未知版本、无效名称索引和缺失字段测试 raw fallback；禁止静默部分解码。
5. 仅在目标字段和 fallback 契约均通过后，把稳定测试从 `tests/temp/` 移入正式测试目录。

## 阶段 3：回归与收尾

1. 运行目标测试、现有 #515 覆盖和完整测试集。
2. 检查标准 JSON：目标结构含有已承诺字段；非目标结构的输出和状态不变。
3. 在 #515 中链接已完成的子 Issue、剩余候选和不适用原因。只有不存在待跟踪的已证实结构时才关闭 #515。

## 风险控制

| 风险 | 缓解措施 |
| --- | --- |
| UE 源码不可用 | 标记为 "deferred" 并说明原因；仅在源码可审计时推进实现 |
| Fixture 不稳定 | 文档化版本约束；UE 版本变更时更新 fixture |
| Parser 破坏回归 | 回滚并重新评估方案；Phase 3 全量回归验证 |
| 候选范围过大 | 使用优先级矩阵筛选"快速胜利"候选优先处理 |

## 验收标准

- 每项新增支持均有真实夹具（`tests/samples/` 下版本控制文件）、SHA-256、UE 版本和源码证据。
- 支持的字段有明确名称、值类型和版本范围。
- 损坏/未知数据保留 `opaque` 或 raw fallback，且不会导致包读取错位。
- 已完成的 `EditedDocumentInfo` 与 MovieScene 回归继续通过。
- 每个新增解析器均提供 `tests/temp/` 下至少 4 种测试场景（正常、截断、未知版本、无效数据）。
