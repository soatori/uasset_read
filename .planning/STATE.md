---
gsd_state_version: 1.0
milestone: v8.0
milestone_name: BP-to-CPP 翻译能力
status: in_progress
last_updated: "2026-05-15T10:00:00.000Z"
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 2
  completed_plans: 2
  percent: 50
---

# v8.0 — BP-to-CPP 翻译能力

## 问题: v7.0 解析结果无法支撑 BP→C++ 翻译

对比 `BP_FirstPersonCharacter.uasset` 解析 JSON 与等价 C++ 实现
(`FirstPersonCCharacter.cpp/h`)，发现 6 个结构性 gap：

| 当前 | 目标 |
|------|------|
| ~~linked_to_raw 全空~~ | ✅ Phase 47 已修复 |
| 无组件数值属性 | 组件位置/旋转/缩放/标志可提取 |
| CallFunction pins 不完整 | 函数签名可推断 |
| EnhancedInput 触发事件不可见 | BindAction ETriggerEvent 可区分 |

## Phase 分解

| Phase | 名称 | 状态 |
|-------|------|------|
| 47 | Pin LinkedTo 修复 | ✅ 完成 |
| 48 | 组件属性递归解析 | ✅ 完成 |
| 49 | 函数调用引脚解析 | 🔴 未开始 |
| 50 | EnhancedInput 语义增强 | 🔴 未开始 |

## Phase 47: Pin LinkedTo 修复 ✅

**修复:** `FEdGraphPinType` 5 个布尔字段 `read_bool_1byte()` → `read_bool()` (1B → 4B)，
修复约 15 字节偏移，使 `linked_to` 数组读取位置正确。

**结果:** `linked_to_raw` 从 0/30 pins → 16/43 pins，connections 非空，
execution_flows 有 7 条 flow 含 nodes 数组。

**测试:** 6/6 passed，0 新回归。

## Phase 48: 组件属性递归解析 ✅

**实现:** `component_extractor.py` — 从 ExportMap 发现 SCS 组件，提取变换
(Loc/Rot/Scale) 和标量属性(Float/Int/Bool/Byte/Enum/Struct)。
`_post_process()` 集成到解析管线，`ParseResult.components` 字段。

**JSON 序列化:** `_format_components()` 将 dataclass 变换值转换为 dict，
`format_json_summary()` 添加 `components_count`。

**测试:** 22 passed, 0 regressions。21 个失败均为预先存在（asset version -9）。

## 关键发现

### Gap G1: linked_to_raw 全为空（P0）

`BP_FirstPersonCharacter.uasset` 的 30 个 pin 全部 `linked_to_raw=[]`。
导致 `build_connections_map()` 返回 0 连接，`build_execution_flows()`
虽然识别到 5 个起点但 `nodes=[]`（无法追踪后续节点）。

根因在 `read_ue_graph()` / `read_ue_graph_pin()` 中的序列化偏移计算。
UE5 的 UEdGraphNode 使用 `nodes_count == 0` + `outer_index` 收集模式，
节点 pins 数组的实际二进制读取位置可能与预期不一致。

### Gap G2: 组件属性值缺失（P0）

C++ 构造函数中的关键数值在 JSON 中完全不可见：
- `FirstPersonCameraComponent` 的 RelativeLocation=(-2.8, 5.89, 0.0)
- `FirstPersonFieldOfView = 70.0f`
- `AirControl = 0.5f`
- `BrakingDecelerationFalling = 1500.0f`

这些值存在于 ExportMap 的 PropertyTag 中，但当前解析器只提取了
Blueprint 元数据层，没有递归解析组件对象的序列化属性。

## 验证标准 — JSON 可翻译性

- ~~Phase 47: connections > 0, execution_flows[].nodes 非空~~ ✅ 已完成
- ~~Phase 48: components 数组包含数值属性（位置/旋转/缩放/标志）~~ ✅ 已完成
- Phase 49: CallFunction 节点输出 parameters 数组（参数名+类型）
- Phase 50: input_bindings 数组与 C++ BindAction 对应

JSON 输出需达到"人工可对照 C++ 头文件/构造函数/函数体逐行翻译"的程度。

*Created: 2026-05-15*
