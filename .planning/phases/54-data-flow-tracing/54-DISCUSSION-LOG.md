# Phase 54: 数据流追踪 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 54-数据流追踪
**Areas discussed:** 追踪方向, 输出结构, SubPin 处理, 追踪范围

---

## 追踪方向

| Option | Description | Selected |
|--------|-------------|----------|
| 正向追踪 (从 Pure 输出) | 从 Pure 函数输出 pin 开始，正向追踪到所有使用点。适合知道「哪些数据来自哪个 pure 函数」 | |
| 反向追踪 (从输入 pin) | 从 CallFunction 输入 pin 开始，向回追踪数据来源链。适合知道「这个参数值从哪来」。与 C++ 翻译需求更一致 | |
| 双向（分开输出） | 两个方向都支持，但分开输出。正向用于数据提供者分析，反向用于参数来源分析 | ✓ |

**User's choice:** 双向（分开输出）
**Notes:** 用户希望两种视角独立但互补，正向分析 Pure 函数输出去向，反向分析调用参数来源。

---

| Option | Description | Selected |
|--------|-------------|----------|
| 透明穿透（推荐） | Knot 在追踪中透明穿透，不作为独立节点出现在数据链中。遵循 Phase 52 D-02 决策 | ✓ |
| 保留为中继点 | Knot 作为「中继点」出现在链路中，便于调试和可视化数据流向 | |

**User's choice:** 透明穿透（推荐）
**Notes:** 遵循 Phase 52 D-02 决策，数据流直接穿透到下一个有意义的节点。

---

| Option | Description | Selected |
|--------|-------------|----------|
| 图边界停止（推荐） | 追踪到 EventGraph 边界或函数图边界即停止。不跨图追踪 | ✓ |
| 尝试跨图追踪 | 尝试跨图追踪数据流，但可能无法找到跨图引用 | |

**User's choice:** 图边界停止（推荐）
**Notes:** 不跨图追踪，避免无限递归和无法找到跨图引用的问题。

---

## 输出结构

| Option | Description | Selected |
|--------|-------------|----------|
| 新增两个数组 (推荐) | 新增 data_sources 数组（反向追踪）+ data_providers 数组（正向追踪）。与现有 data_flows 并存 | ✓ |
| 替换现有 data_flows | 替换现有 data_flows 数组，用新的结构包含来源链信息。向后兼容需处理 | |
| 仅参数级添加 source | 仅在 CallFunction 的 parameters 字段中添加 source 字段，不新建顶层数组。最小改动 | |

**User's choice:** 新增两个数组 (推荐)
**Notes:** 与现有 data_flows 并存，data_flows 记录直接连接，新数组记录来源链路。

---

| Option | Description | Selected |
|--------|-------------|----------|
| 数组链路（推荐） | 链路用数组表示，每个节点记录 pin 信息。如 [{node, pin}, {node, pin}, ...] | ✓ |
| 字符串路径 | 链路用字符串路径表示。如 "GetActorForwardVector.ReturnValue → Move.Direction" | |
| 嵌套对象 | 链路用嵌套对象表示，每个节点包含 next 字段指向下一节点 | |

**User's choice:** 数组链路（推荐）
**Notes:** 便于序列化和程序处理，结构清晰。

---

| Option | Description | Selected |
|--------|-------------|----------|
| 最小信息（node + pin） | 链路节点仅记录 node_name + pin_name，最紧凑 | |
| 扩展信息（+ type）（推荐） | 链路节点额外记录 node_type + pin_type，便于区分 Pure vs Impure 函数 | ✓ |
| 完整元数据 | 链路节点包含完整 function_reference 等元数据，便于跨图分析 | |

**User's choice:** 扩展信息（+ type）（推荐）
**Notes:** 便于区分函数类型和数据类型，不增加过多复杂度。

---

## SubPin 处理

| Option | Description | Selected |
|--------|-------------|----------|
| 透明映射（与 Knot 相同） | SubPin 透明映射到父 Pin，不单独追踪。父 Pin 作为结构体整体传递 | |
| 展开字段级追踪（推荐） | SubPin 展开为字段级追踪，记录「结构体.X 字段 → 目标.Y 字段」的数据流。满足 DATA-03 需求 | ✓ |
| 双模式并存 | 两种模式并存：父 Pin 链路记录整体流向，SubPin 链路记录字段级细节 | |

**User's choice:** 展开字段级追踪（推荐）
**Notes:** 满足 DATA-03 需求，记录细粒度数据流。

---

| Option | Description | Selected |
|--------|-------------|----------|
| 点分隔（parent.subfield） | SubPin 在链路中用 parent_pin.subfield 格式表示 | |
| 嵌套结构 {parent, field} | SubPin 在链路中用单独字段表示 {parent_pin, subfield}。结构更清晰 | ✓ |

**User's choice:** 嵌套结构 {parent, field}
**Notes:** 结构更清晰，便于程序解析。

---

| Option | Description | Selected |
|--------|-------------|----------|
| 第一级展开（推荐） | 仅展开直接子字段（第一级 SubPin）。不递归展开嵌套结构体 | ✓ |
| 全递归展开 | 递归展开所有层级 SubPin，支持深层嵌套结构体 | |

**User's choice:** 第一级展开（推荐）
**Notes:** 避免过度复杂化输出，满足大多数 C++ 翻译场景。

---

## 追踪范围

| Option | Description | Selected |
|--------|-------------|----------|
| 仅非 exec pin（推荐） | 仅追踪非 exec 类型 pin（包括 bool、int、float、string、struct、object、delegate 等）。符合 Phase 53 D-03 定义 | ✓ |
| 仅复杂类型 | 仅追踪 struct/object 类型 pin，忽略简单类型 | |
| 可配置范围 | 用户可配置追踪范围，通过 config 指定需要追踪的 pin_category | |

**User's choice:** 仅非 exec pin（推荐）
**Notes:** 符合 Phase 53 D-03 定义，覆盖所有数据类型。

---

| Option | Description | Selected |
|--------|-------------|----------|
| 仅 Pure 函数输出（推荐） | 正向追踪仅从标记为 pure 的 CallFunction 输出 pin 开始。Phase 53 D-03 已识别 pure 函数 | ✓ |
| 所有非 exec 输出 | 正向追踪从所有非 exec 输出 pin 开始，包括 impure 函数的返回值 | |

**User's choice:** 仅 Pure 函数输出（推荐）
**Notes:** 聚焦于 Pure 函数数据来源，Phase 53 已识别 pure 函数。

---

| Option | Description | Selected |
|--------|-------------|----------|
| 仅 CallFunction 输入（推荐） | 反向追踪仅从 CallFunction 输入 pin 开始，不包括 Event/VariableSet 等其他节点 | ✓ |
| 所有输入 pin | 反向追踪从所有方向=0 的非 exec pin 开始，覆盖更全面 | |

**User's choice:** 仅 CallFunction 输入（推荐）
**Notes:** 聚焦于函数调用参数来源分析，不扩大范围。

---

## Claude's Discretion

- 算法实现细节（正向/反向遍历逻辑）由 researcher 确定
- 具体函数命名和模块划分由 planner 决定
- SubPin 检测逻辑（如何识别 parent_pin → subfield 关系）由 researcher 确定

## Deferred Ideas

- 跨图数据流追踪 — 不在 v9.0 范围内，可能需要 Phase 55 或后续 milestone
- 嵌套结构体全递归展开 — 如有需求可后续扩展
- JSON function_graphs 独立数组输出 — Phase 55