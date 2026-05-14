# Phase 44: 模型增强 - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

将 `UEdGraphPin` 的 `linked_to_raw` 字段替换为 `linked_to_objects: List[Optional[UObjectInstance]]`，使引脚连接引用直接指向 UObjectInstance 实例而非原始字典。配合 Phase 41-43 的 linker 基础设施，实现真正的对象图导航。

</domain>

<decisions>
## Implementation Decisions

### 字段设计
- **D-01:** `linked_to_raw` 字段替换为 `linked_to_objects: List[Optional[UObjectInstance]]`，breaking change — 所有依赖 `linked_to_raw` 的代码需要迁移
- **D-02:** 类型签名明确为 `List[Optional[UObjectInstance]]`，允许 None 值（NULL 引脚用 Sentinel 对象替代，见下方）

### NULL 引脚处理
- **D-03:** NULL 条目使用 Sentinel 对象（`NullPinInstance`）而非 None，调用者可统一调用方法无需判空
- **D-04:** Sentinel 对象应为 `UObjectInstance` 的轻量子类或标记实例，提供 `is_null` property

### 引脚→节点对象映射
- **D-05:** 通过 `owning_node_index`（PackageIndex 编码的 i32）直接解析为 `UObjectInstance`，不需要 GUID 查找表
- **D-06:** `read_pin_reference` 函数添加 `linker: Optional[PackageLinker]` 参数，使用 `linker.resolve_package_index(PackageIndex(owning_node_index))` 获取目标对象

### 填充时机与方式
- **D-07:** 在序列化时填充 — `read_pin_reference`/`read_pin_array`/`read_ue_graph_pin` 添加 `linker` 参数，与现有 `read_ue_graph_node` 的 linker 参数传递模式一致
- **D-08:** `read_ue_graph_pin` 中 NULL pin body 仍需消费字节以推进文件位置，但 `linked_to_objects` 中存入 Sentinel 对象

### Claude's Discretion
- Sentinel 对象的具体实现方式（子类 vs 标记实例 vs dataclass 包装）由实现者决定

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 数据模型
- `src/uasset_read/models/core.py` — UEdGraphPin 当前定义，`linked_to_raw` 字段需替换
- `src/uasset_read/models/__init__.py` — 模块导出，需确认无外部依赖 linked_to_raw

### Linker 基础设施
- `src/uasset_read/link/linker.py` — PackageLinker.resolve_package_index() 用于节点索引解析
- `src/uasset_read/link/object_instance.py` — UObjectInstance 定义，Sentinel 对象需兼容此接口

### 序列化器
- `src/uasset_read/serializers/graph.py` — read_pin_reference(), read_pin_array(), read_ue_graph_pin() 需添加 linker 参数
- `src/uasset_read/serializers/graph.py:325-375` — read_pin_reference / read_pin_array 当前实现

### 调用链
- `src/uasset_read/serializers/graph.py:867` — read_ue_graph_node 中调用 read_ue_graph_pin 需传递 linker
- `src/uasset_read/graph/flow_builder.py` — 使用 linked_to_raw 的代码需要迁移到 linked_to_objects

### 路线图
- `.planning/ROADMAP.md` — Phase 44 定义：模型增强，UEdGraphPin linked_to_objects
- `.planning/REQUIREMENTS.md` — LINK-04 需求追溯

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PackageLinker.resolve_package_index()` — 已将 PackageIndex 解析为 UObjectInstance，read_pin_reference 可直接复用
- `PackageIndex` class — `src/uasset_read/serializers/object_resources.py` 中已有，owning_node_index → PackageIndex → UObjectInstance
- `read_ue_graph_node(linker=...)` — 已有 linker 参数传递模式，read_ue_graph_pin 沿用此模式

### Established Patterns
- 序列化函数统一使用 `linker: Optional[PackageLinker] = None` 参数（如 `read_fmember_reference`, `read_k2node_call_function`）
- `_rcn()` / `_gac()` 辅助函数处理 linker/non-linker 分支，新增 pin 解析可沿用
- `UEdGraphPin.from_archive()` 延迟导入 serializer，保持解耦

### Integration Points
- `read_ue_graph_pin` 被 `read_ue_graph_node` 调用（graph.py:867），需确保 linker 参数传递到位
- `graph/flow_builder.py` 多处使用 `pin.linked_to_raw`，需迁移到新字段
- `parse_uasset_with_linker()`（Phase 42）调用图序列化时需传入 linker

</code_context>

<specifics>
## Specific Ideas

- Sentinel 对象可考虑 `NullPinInstance` 命名，与 UE 的 null pin 概念对齐
- `linked_to_objects` 中每个条目对应一个连接的引脚所在的节点对象（UObjectInstance），而非引脚本身
- owning_node_index > 0 → export，< 0 → import，= 0 → null（与 PackageIndex 编码一致）

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 44-模型增强*
*Context gathered: 2026-05-14*
