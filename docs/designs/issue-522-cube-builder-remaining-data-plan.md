# 修复计划：#522 CubeBuilder 剩余数据

> 状态：计划中（2026-08-02）  
> 范围：验证材质、碰撞和 LOD 的真实序列化归属；仅解析可由源码和夹具证明属于 `CubeBuilder` 的数据。

## 当前基线

- `CubeBuilder` 通过精确的 `PropertyMetadataHandler` 输出 `layer`、`polygon_count` 和 `vertex_payload_size`，状态为 `partial_metadata`。
- 后续提交已增加顶点位置与 `FBuilderPoly` 多边形拓扑的解码；旧合并计划将它们列为未完成，已不准确。
- 夹具为 `tests/samples/FirstPerson_Lvl_FirstPerson.umap` 中的 `CubeBuilder_3`，其 SHA-256 和元数据契约由 `tests/test_issue_522_cube_builder_metadata.py` 固定。

## 工作量估算

| 阶段 | 估算 | 说明 |
| --- | --- | --- |
| Phase 1：二进制证据重建 | 2-4 小时 | 文档化已知的偏移、字段和剩余区间 |
| Phase 2：材质归属调查 | 2-4 小时 | 以待复核的归属假设为起点 |
| Phase 3：碰撞与 LOD 归属 | 1-2 小时 | 同上，文档化后关闭 |
| Phase 4：回归验证 | 1-2 小时 | 全量回归 + Issue 整理 |
| **总计** | **6-12 小时（1-1.5 天）** | 反射数据已证明预期结论 |

## 待复核的归属假设

> 下列结论来自先前的 Clay jmap / CUE4Parse 调查，但本文未固定其版本、路径或可复查链接。因此它们只是 Phase 1-3 的待验证假设，不能作为关闭 #522 的证据。

**材质归属假设：** `FBuilderPoly` 可能只含 `VertexIndices`、`Direction`、`ItemName`、`PolyFlags`，而材料可能存储在 `UModel` 的 `FBspSurf.Material` 中，通过 `FBspSurf.iBrushPoly` 关联回编辑器多边形。Phase 2 必须以匹配版本源码和夹具验证此假设。

**碰撞归属假设：** 碰撞可能位于 `UBrushComponent → BrushBodySetup: UBodySetup`，而不在 CubeBuilder 序列化路径中。Phase 3 必须记录匹配版本源码的精确路径和夹具证据。

**LOD 归属假设：** LOD 可能是 `StaticMesh` / 构建管线的关注点，而非 CubeBuilder 数据；Phase 3 必须验证后才能从 #522 验收中移除。

## 首要原则

Issue 描述中的”材质、碰撞、LOD”并不自动意味着这些字段写入 `CubeBuilder` export。它们可能属于 `UBrush`、`UModel`、组件或最终构建产物。必须先确认所有权；未序列化在此 export 中的数据不能通过猜测补齐。

## 与 #515 的关联

若 CubeBuilder 剩余尾部数据中包含 opaque StructProperty，则其解析依赖 #515 的优先级排序和实现进度。当前不将此类数据视为 CubeBuilder 特有问题。

## BrushBuilder 额外属性

先前反射调查提到 BrushBuilder 可能具有以下 protected UPROPERTY 字段；在未固定来源前，它们仅作为 Phase 1 的核查项：

- `BitmapFilename`
- `ToolTip`
- `NotifyBadParams`
- `MergeCoplanars`

这些字段是否在 `CubeBuilder_3` 夹具中出现需在 Phase 1 中确认。若出现则纳入范围，否则记录为”夹具中未出现”。

## 阶段 1：重建当前二进制证据

1. 为 `CubeBuilder_3` 记录 tagged-property 结束偏移、export serial 范围、已解码顶点/多边形字段和剩余原始区间。**必须断言 `tail_offset` 和 `tail_size` 的实际字节数**，为后续工作创建硬回归边界。
2. 将每个已消耗字节区间对应到 `CubeBuilder`、`UBrush`、`FBuilderPoly` 或其父类的匹配 UE 版本源码。
3. 在聚焦测试中断言顶点数、polygon count、拓扑索引和 raw-tail 边界，防止后续扩展重新解释已确认数据。
4. 确认 BrushBuilder 额外属性（`BitmapFilename`、`ToolTip` 等）是否在夹具的 tagged 属性中出现。

验收：现有元数据测试保持通过，且已解码部分能与原始 serial 范围对齐；`tail_offset` 和 `tail_size` 有明确断言值。

## 阶段 2：材质归属与最小实现

### 驳回路径（预期结论）

1. 以匹配版本的 `FBuilderPoly`/`UModel` 源码和夹具确认 `CubeBuilder_3` 是否分配了材质。
2. 若证据表明材质不在 CubeBuilder 中：在 #522 中记录归属链、源码路径、版本和夹具观察结果。
3. 若需要材质解析：创建独立 Issue 处理 `UModel`/`FBspSurf` 解析，不在本 handler 中伪造字段。

### 实现路径（仅在证据证实在 CubeBuilder 内时）

1. 先添加红测试，公开最小材料引用（对象路径或名称和 polygon/slot 关系）。
2. 保留不可解析字段的 raw fallback。

## 阶段 3：碰撞与 LOD 归属

### 驳回路径（预期结论）

1. 以匹配版本源码和夹具确认碰撞、LOD 的实际序列化路径。
2. 只有证据充分时，才在 #522 中记录它们不属于 CubeBuilder 序列化。
3. 若需要碰撞解析：建议创建独立 Issue 处理 `UBrushComponent`/`UBodySetup`。

### 实现路径（仅在证据证实在 CubeBuilder 内时）

1. 检查是否存在明确字段边界、值语义和真实夹具实例。
2. 若存在：为各自创建独立实现切片和测试。

## 阶段 4：状态与回归

1. 继续使用精确类匹配；不得改变 `CubeBuilderHelper`、`GeomModifier_*` 或 `BrushBuilder*` 的 skip 行为。
2. 每个新增字段先在 `tests/temp/` 用固定夹具验证，再迁移为正式回归测试。
3. 运行 #522 元数据、顶点、拓扑测试和完整测试集；验证标准 JSON 的 `partial_metadata`/`partial` 状态只在新增证据充分时变化。
4. 只有顶点、拓扑和已证实属于 `CubeBuilder` 的剩余字段均有测试时关闭 #522。

## 关闭模板

当所有阶段完成时，更新 #522 Issue 包含以下内容：

1. 已解码字段列表（含字段名、值类型、测试覆盖）
2. 已证实不存在的字段列表（含源码依据和归属链）
3. 最终 `parse_status` 值
4. 关联 Issue 链接（如 `UModel`/`UBrushComponent` 解析 Issue）

## 单 Fixture 局限性

所有已固定的仓库内证据来自单一夹具（`CubeBuilder_3` in `FirstPerson_Lvl_FirstPerson.umap`）。该实例可能未分配材质，Phase 2 可能产生假阴性；若需要以“不存在”作为结论，必须补充第二个相关夹具或匹配版本源码的明确证明，并在 #522 中注明局限性。

## 验收标准

- 每个新增材质/碰撞/LOD 字段都有夹具、UE 源码、字节或 tagged-property 边界证据。
- 没有证据的数据仍保持 opaque/raw，不会造成 archive 偏移错位。
- 已有 `CubeBuilder_3` 元数据契约和其他 builder 类的 skip 边界不回归。
- Phase 1 断言 `tail_offset` 和 `tail_size` 实际值。
- 关闭时提供完整关闭模板内容。
