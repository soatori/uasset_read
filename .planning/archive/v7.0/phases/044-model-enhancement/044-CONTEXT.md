# Phase 44: 模型增强 — UEdGraphPin linked_to_objects — CONTEXT.md

**Date:** 2026-05-14
**Phase:** 044-model-enhancement
**Goal:** 在 `UEdGraphPin` 数据模型中添加 `linked_to_objects` 字段，将连接引用从原始 dict 升级为 `UObjectInstance` 实际对象引用。

---

## 位置与依赖

| 项目 | 状态 |
|------|------|
| 里程碑 | v7.0 (UE FLinkerLoad 对象图重建) |
| 依赖 Phase 41 | ✅ 已完成 — link/ 模块 |
| 依赖 Phase 42 | ✅ 已完成 — 集成入口 |
| 依赖 Phase 43 | ✅ 已完成 — PackageIndex 增强 |
| 下一阶段 | Phase 45 — 图序列化 |

## 领域问题

### 当前设计

`UEdGraphPin` 在 `src/uasset_read/models/core.py` 定义：
- `linked_to_raw: List[dict]` — 存储原始连接信息，每个元素为 `{"owning_node": owning_node_name, "pin_guid": pin_guid}`
- `sub_pins: List[dict]` — 子引脚引用数组，格式同上
- `parent_pin: Optional[dict]` — 父引脚引用，格式同上

### 问题

当前 `linked_to_raw` 中只有节点名称字符串和引脚 GUID，没有指向实际 `UObjectInstance` 的引用。引脚连接目标的 owning node 实际上是一个 `FPackageIndex`（int32），可以通过 linker 解析为实际对象。

### 解决方案

在数据模型中新增字段：
- `linked_to_objects: List[Optional[UObjectInstance]]` — 并行于 `linked_to_raw`，存储解析后的对象引用
- `sub_pins_objects: List[Optional[UObjectInstance]]` — 并行于 `sub_pins`
- `parent_pin_object: Optional[UObjectInstance]` — 对应 `parent_pin`
- `ref_pass_through_object: Optional[UObjectInstance]` — 对应 `ref_pass_through`

当 `linker` 参数提供时，读取过程中通过 `linker.resolve_package_index()` 解析 `owning_node_index` 得到 `UObjectInstance`。

## 决策点

### 向后兼容策略

保持完全向后兼容：
- `linked_to_raw` 保留，不删除
- 新增 `linked_to_objects` 默认为空列表
- 只有当 `linker` 参数传入 `read_ue_graph_pin` / `read_ue_graph_node` / `read_ue_graph` 时才会填充 `linked_to_objects`
- 没有 linker 时，`linked_to_objects` 保持为空，不影响现有代码

### 存储方式 — 并行数组 vs 增强 dict

选择**并行数组**：
- `linked_to_raw[i]` 对应 `linked_to_objects[i]`
- 不改变现有 `linked_to_raw` 的结构
- 不破坏已有代码对 `linked_to_raw` 的访问
- 索引对齐便于查找

### 导入导出

`UEdGraphPin` 需要导入 `UObjectInstance` 类型提示，使用 `TYPE_CHECKING` 条件导入避免循环依赖。

## 规范引用

- `.planning/ROADMAP.md` — Phase 44 定义: `UEdGraphPin linked_to_objects`
- `.planning/STATE.md` — v7.0 目标: `PackageIndex → UObjectInstance 实际引用`
- `src/uasset_read/models/core.py` — `UEdGraphPin` 当前定义
- `src/uasset_read/serializers/graph.py` — `read_ue_graph_pin` / `read_pin_reference` 读取逻辑
- `src/uasset_read/link/linker.py` — `PackageLinker.resolve_package_index()`
- `src/uasset_read/link/object_instance.py` — `UObjectInstance` 数据类

## 代码上下文

### 当前调用链

```
read_ue_graph()
  → read_ue_graph_node()
    → read_ue_graph_pin()
      → read_pin_array()
        → read_pin_reference()
          → returns dict {"owning_node": name, "pin_guid": guid}
```

所有入口已经接受 `linker: Optional[PackageLinker] = None` 参数（Phase 43 集成完成）。

### 需要修改的文件

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `src/uasset_read/models/core.py` | 模型增强 | 添加 `linked_to_objects` 等字段，添加 TYPE_CHECKING 导入 |
| `src/uasset_read/serializers/graph.py` | 解析增强 | 在 `read_pin_reference` / `read_pin_array` / `read_ue_graph_pin` 中使用 linker 解析对象引用 |
| `src/uasset_read/models/__init__.py` | 无变化 | `UEdGraphPin` 已导出 |

### 验收标准

1. **向后兼容**: 所有现有测试通过，没有回归
2. **功能正确**: 当传入 linker 时，`linked_to_objects` 被正确填充，每个元素是 `Optional[UObjectInstance]`
3. **空安全**: 解析失败时存入 `None`，不抛出异常
4. **类型正确**: mypy 类型检查通过

## 延期想法

- 未来可以考虑将 `linked_to_raw` 和 `linked_to_objects` 合并为一个 dataclass，但这会破坏性改变 API，不做
- 未来可以添加 `find_linked_pin()` 方法通过 GUID 在目标节点查找引脚，这超出当前范围，留给 Phase 45 或后续

---

*Created: 2026-05-15 | Mode: plan*
