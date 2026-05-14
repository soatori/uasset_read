# Phase 44: 模型增强 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-14
**Phase:** 44-模型增强
**Areas discussed:** 字段设计, NULL 引脚处理, 引脚映射, 填充时机

---

## 字段设计

| Option | Description | Selected |
|--------|-------------|----------|
| 新增字段 | 新增 linked_to_objects 字段，保留 linked_to_raw 不变 | |
| 替换原有字段 | linked_to_raw 改类型为 List[Optional[UObjectInstance]]，breaking change | ✓ |
| property 计算 | linked_to_objects 为 property 动态解析 | |

**User's choice:** 替换原有字段 — linked_to_raw 直接改为 linked_to_objects
**Notes:** 这是 breaking change，依赖 linked_to_raw 的代码需要迁移

---

## NULL 引脚处理

| Option | Description | Selected |
|--------|-------------|----------|
| 保留 None 占位 | linked_to_objects 中保留 None 占位，与原始数组一一对应 | |
| 跳过 NULL | 跳过 NULL 条目，列表中只有实际连接的对象 | |
| Sentinel 对象 | 使用 Sentinel 对象（NullPinInstance）而非 None | ✓ |

**User's choice:** Sentinel 对象
**Notes:** 调用者可统一调用方法而无需判空，具体实现方式由 Claude 决定

---

## 引脚→节点对象映射

| Option | Description | Selected |
|--------|-------------|----------|
| GUID 查找表 | 在 PackageLinker 中构建 {pin_guid: UObjectInstance} 查找表 | |
| 节点索引直接解析 | owning_node_index 直接解析为 UObjectInstance | ✓ |
| 后处理名称匹配 | 通过 owning_node 名称匹配 UObjectInstance | |

**User's choice:** 节点索引直接解析 — 使用 owning_node_index (PackageIndex) 直接解析
**Notes:** 与现有 PackageLinker.resolve_package_index() 模式一致

---

## 填充时机与方式

| Option | Description | Selected |
|--------|-------------|----------|
| 序列化时填充 | read_pin_reference/Array/Pin 添加 linker 参数，序列化时直接填充 | ✓ |
| 后处理批量填充 | 保持序列化器不变，parse_uasset_with_linker 后处理 | |
| 延迟计算 property | linked_to_objects 作为 property 延迟计算 | |

**User's choice:** 序列化时填充 — 与现有 linker 参数传递模式一致
**Notes:** read_ue_graph_node 已有 linker 参数，read_ue_graph_pin 沿用

---

## Claude's Discretion

- Sentinel 对象的具体实现方式（子类 vs 标记实例 vs dataclass 包装）

## Deferred Ideas

无
