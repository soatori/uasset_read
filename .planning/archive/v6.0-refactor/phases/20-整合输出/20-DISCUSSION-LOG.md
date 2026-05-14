# Phase 20: 整合输出 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 20-整合输出
**Areas discussed:** 节点命名、字段映射、嵌套展开、蓝图结构、版本升级、变量提取、Graph类型

---

## 节点命名

| Option | Description | Selected |
|--------|-------------|----------|
| class_name + index | 与Phase 19连接引用格式一致，已实现 _derive_node_name() | ✓ |
| 提取语义名 | 如果有MemberName等字段可提取更友好的名称 | |
| 两者都输出 | 保持现有 class_name 字段，添加 node_name | |

**User's choice:** class_name + index
**Notes:** 推荐选项，与Phase 19连接格式一致，已有实现可复用

---

## 字段映射

| Option | Description | Selected |
|--------|-------------|----------|
| 双字段输出 | 新字段名 node_type/position，旧字段名保留但标记 deprecated | |
| 仅新字段 | 严格遵循 REQUIREMENTS 示例，不保留旧字段 | ✓ |
| 保持现有 | 保持 class_name/node_pos_x/node_pos_y，不改变 | |

**User's choice:** 仅新字段
**Notes:** 严格遵循REQUIREMENTS示例格式，不做向后兼容

---

## 嵌套展开

| Option | Description | Selected |
|--------|-------------|----------|
| 仅常用字段 | function_reference/event_reference 提升到节点顶层，其余保留在 node_data | ✓ |
| 全部展开 | 所有 node_data 字段展开到节点顶层 | |
| 保持嵌套 | 保持现有 node_data 嵌套结构 | |

**User's choice:** 仅常用字段
**Notes:** 推荐选项，function_reference/event_reference 提升到顶层便于查阅

---

## 蓝图结构

| Option | Description | Selected |
|--------|-------------|----------|
| 现有结构+新增 | graphs 保持顶层数组，添加 blueprint_name/variables 字段 | |
| 单一蓝图对象 | 合并为单一 blueprint 对象，graphs 内嵌 | ✓ |
| 分离蓝图和图 | 顶层输出 {blueprint: {...}, graphs: [...]} | |

**User's choice:** 单一蓝图对象
**Notes:** 符合REQUIREMENTS示例，graphs移入blueprint内部

---

## 版本升级

| Option | Description | Selected |
|--------|-------------|----------|
| 升级到 4.0 | 反映输出结构重大变化，符合语义版本规范 | ✓ |
| 保持 3.0 | 视为现有格式增强而非破坏性变更 | |

**User's choice:** 升级到 4.0
**Notes:** 输出结构变化较大（字段名、蓝图结构重组），升级版本号

---

## 变量提取

| Option | Description | Selected |
|--------|-------------|----------|
| 复用现有数据 | Phase 12 已实现 blueprint.variables，直接复用 | |
| 扩展变量信息 | 提取更多信息，如变量类型、默认值 | ✓ |
| 仅变量名 | 仅输出变量名列表，简化结构 | |

**User's choice:** 扩展变量信息
**Notes:** 输出变量类型和默认值，提供更完整的蓝图信息

---

## Graph类型

| Option | Description | Selected |
|--------|-------------|----------|
| 映射为语义名 | EdGraph→event, UberEdGraph→uber | ✓ |
| 保持原有 | 保持 EdGraph/UberEdGraph 原值 | |

**User's choice:** 映射为语义名
**Notes:** 推荐选项，符合REQUIREMENTS示例的graph_type字段

---

## Claude's Discretion

- 节点 pins 输出的详细程度（是否包含所有 Phase 18 字段）
- 变量默认值的格式（字符串 vs 结构化）
- 多蓝图资产的处理策略

---

## Deferred Ideas

None — discussion stayed within phase scope. Phase 21将处理验证测试。