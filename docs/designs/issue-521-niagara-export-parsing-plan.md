# 修复计划：#521 Niagara 导出类型解析

> 状态：计划中（2026-08-02）  
> 范围：把原 Epic 拆成 Graph、Script 和节点族的字段级工作；不以”支持 Niagara”作为不可验证的完成条件。

## 当前基线

- 夹具：`tests/samples/NM_BPSystemEvent.uasset`，其来源与 SHA-256 由 `tests/temp/test_issue_521_niagara_evidence.py` 固定。
- 当前 tolerant 解析结果为 `partial`，包含 28 个跳过的 Niagara 导出，其中包括 `NiagaraGraph`、`NiagaraScript` 和多种节点类。
- 现有证据只证明跳过现状，尚未证明任一类的 native payload 布局；不能直接将 `Niagara*` 前缀改为通用属性解析。
- `NiagaraSystem` 已路由至 `OPAQUE_CLASS_PAYLOAD`（非 `SKIP_UNSUPPORTED`），可获得 tagged 属性解析机会。

## 工作量估算

| 阶段 | 估算 | 说明 |
| --- | --- | --- |
| Phase 1：证据与边界 | 1-2 天 | 扩展现有测试，交叉验证 UE 源码 |
| Phase 1.5：额外 fixture（如需） | 1 天 | 若单一 fixture 证据不足时执行 |
| Phase 2：NiagaraGraph | 2-3 天 | UE 源码分析 + handler 创建 |
| Phase 3：NiagaraScript | 2-3 天 | 与 Phase 2 类似；opaque tail 处理直接 |
| Phase 4：6 个节点族 | 5-8 天 | 每个类型需独立源码分析 + handler |
| Phase 5：验证与整理 | 1 天 | 测试运行 + Issue 整理 |
| **总计** | **11-17 天** | 严重依赖 UE 源码可用性 |

## 交付拆分

| 子范围 | 最小公开数据 | 明确不做 |
| --- | --- | --- |
| NiagaraGraph | Graph 标识、可验证的节点/脚本引用和已解析 tagged 属性 | 未证实的原生尾部 |
| NiagaraScript | Script 标识、可验证引用和元数据 | VM bytecode、HLSL 或编译产物反编译 |
| 节点族 | 节点类别、名称、已证实的引脚/参数引用 | 根据对象顺序推断执行连线 |

## 阶段 0：类路由迁移

在开始证据阶段之前，必须完成以下类路由变更：

1. 将目标类（`NiagaraGraph`、`NiagaraScript`、节点族）从 `_SKIP_CLASSES` 迁移至 `_OPAQUE_CLASSES`（`class_serialization_strategy.py`）。
2. 评估 `class_specific_skip.py` 中 `SKIP_CLASS_PREFIXES` 的 `NiagaraNode` 前缀条目——若已迁移单个类至 `_OPAQUE_CLASSES`，需确认前缀匹配不会覆盖已迁移的类。
3. 运行完整测试集确认路由变更不影响非 Niagara 导出。

验收：迁移后的目标类进入 opaque 路径（tagged 属性可解析），其他 Niagara 类保持 skip 行为。

## 阶段 1：证据与边界

1. 将现有证据测试扩展为结构化清单：每个 Niagara export 的类、对象名、serial offset/size、属性结束位置和 parse status。
2. 针对 `NiagaraGraph`、`NiagaraScript` 和一个节点族代表，查阅匹配 UE 版本的序列化源码；记录 tagged-property 结束点以及 native tail 的所有权。
3. 为每个子范围形成独立字段契约：输入夹具、输出键、值的来源、支持的版本与 fallback 行为。
4. 如果夹具版本无法与可审阅源码对应，则停止在证据测试阶段，不进入解码实现。

### “可审计源码”定义

对应的 `Serialize()` 函数或 `FProperty` 声明必须在与夹具序列化版本匹配的 UE 引擎版本标签（如 5.3、5.4）的源码中可定位。Niagara 是插件而非核心引擎代码，需确认插件源码可用性。

### 节点族前置检查

在 Phase 4 开始前，验证夹具中至少一个节点实例具有非空 tagged 属性（不仅是 native tail）。若所有节点均为纯原生数据，tagged-property-only 方法将产生空结果，需重新评估范围。

验收：证据测试能稳定枚举目标导出，且不改变当前 `skip_unsupported` 行为。

## 阶段 1.5：额外 Fixture（条件执行）

若 Phase 1 单一夹具证据不足（例如目标类仅有 trivial 或部分填充的导出），执行此阶段：

1. 从 UE 示例项目或 Epic 公开示例内容中获取额外 Niagara 资产。
2. 扩展结构化清单覆盖新夹具。
3. 交叉验证新旧夹具的证据一致性。

若 Phase 1 证据充分，跳过此阶段。

## 阶段 2：NiagaraGraph 最小切片

### 输出 Schema 定义

```json
{
  “graph_name”: “< FName string >”,
  “node_exports”: [{ “export_index”: <int>, “class”: “<string>” }],
  “script_exports”: [{ “export_index”: <int>, “class”: “<string>” }],
  “tagged_properties”: { ... },
  “native_tail”: { “offset”: <int>, “size”: <int>, “status”: “opaque” }
}
```

### 执行步骤

1. 先写红测试：仅断言源码已证明的 Graph 元数据和引用，不断言完整连线图。
2. 在已有 `ClassHandler` 注册路径新增精确的 `NiagaraGraph` handler；只投影已读 tagged 属性，并保存 native tail 的 offset/size 与明确状态。
3. 对缺失属性、无效对象引用和未知版本保持 `partial_metadata` 或既有 skip/raw 行为，不消费未证明的字节。
4. 与原证据测试同时运行，确认只有目标 Graph 导出改变状态或数据。

## 阶段 3：NiagaraScript 最小切片

### 输出 Schema 定义

```json
{
  “script_name”: “< FName string >”,
  “script_usage”: “<string>”,
  “target_environment”: “<string>”,
  “graph_export_ref”: { “export_index”: <int>, “class”: “<string>” },
  “tagged_properties”: { ... },
  “native_tail”: { “offset”: <int>, “size”: <int>, “status”: “opaque” }
}
```

### 执行步骤

1. 使用独立 handler 和独立测试，避免与 Graph 共享未经证明的二进制假设。
2. 只公开源码和夹具均能证明的引用/元数据；bytecode 继续作为 opaque tail。
3. 验证 Script 引用的导出索引、名称和包路径在 JSON 输出中稳定。

## 阶段 4：节点族切片

### 输出 Schema 定义（每个节点类型）

```json
{
  “node_class”: “<NiagaraNode* class name>”,
  “node_name”: “<FName string>”,
  “parameters”: [{ “name”: “<string>”, “type”: “<string>” }],
  “pin_references”: [{ “pin_name”: “<string>”, “connected_to”: <int|null> }],
  “native_tail”: { “offset”: <int>, “size”: <int>, “status”: “opaque” }
}
```

### 实现顺序

按以下顺序，每个节点族单独实现与验收：`NiagaraNodeInput`、`NiagaraNodeFunctionCall`、`NiagaraNodeParameterMapGet/Set`、`NiagaraNodeOp`、`NiagaraNodeOutput`、`NiagaraNodeReroute`。

每一项均须：

1. 有至少一个真实节点实例和源码布局证据。
2. 先添加失败测试，再实现精确 handler。
3. 只公开节点身份、已证实参数或引脚引用；没有连线来源时不生成执行流。
4. 回归检查其他 Niagara 类仍保持原有跳过策略。

## 阶段 5：验证与 Issue 整理

1. 运行所有 Niagara 聚焦测试和完整测试集。
2. 用固定夹具验证输出的 Graph/Script/节点字段，不以历史的”1,638 exports”或”39.3%”作为验收数据，除非补充可复现的统计命令、版本和数据集。
3. 将三个子范围建立为独立 GitHub Issue；#521 保持 Epic，直到每个字段级 Issue 都有完成或明确不适用结论。
4. 验收标准：所有 Niagara 聚焦测试通过；完整测试集通过；现有导出计数无回归；fixture 快照与三个子范围的预期输出匹配。

## 明确不在范围内

| 类/前缀 | 不做原因 |
| --- | --- |
| `NiagaraSystem` | 已路由至 opaque，不在本计划扩展范围 |
| `NiagaraDataInterface*` | 已在 skip 列表中，无足够证据推进；不以 `Niagara` 前缀扩大 handler |
| VM bytecode / HLSL | 编译产物反编译超出本项目范围 |

## 风险控制

| 风险 | 缓解措施 |
| --- | --- |
| UE 插件源码不可用 | Phase 1 终止，记录可从 tagged property 结构推断的内容，创建后续 Issue |
| 单一 fixture 证据不足 | 执行 Phase 1.5 获取额外 fixture |
| `NiagaraNode` 前缀覆盖 | Phase 0 确认前缀匹配与单类迁移的交互 |
| 跨 handler 引用验证 | Phase 4 前置检查：验证节点是否有非空 tagged 属性 |
| `partial_metadata` 未定义 | 在 Phase 2 开始前添加至 `ExportParseStatus` 枚举或定义为独立机制 |
