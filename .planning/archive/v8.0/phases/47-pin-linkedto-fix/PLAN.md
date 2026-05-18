# Phase 47: Pin LinkedTo 修复 — PLAN.md

**Date:** 2026-05-15
**Phase:** 047-pin-linkedto-fix
**Goal:** `linked_to_raw` 从空数组变为实际 Pin 引用列表，`connections > 0`，`execution_flows[].nodes` 非空

---

## 根因

`read_ed_graph_pin_type()` 中布尔序列化方式错误：使用 `read_bool_1byte()` (1B) 代替 `read_bool()` (4B)，且 `FEdGraphPinType` 模型缺少 3 个字段（`is_const`, `is_uobject_wrapper`, `b_serialize_as_single_precision_float`）。总计约 15 字节偏移（5 fields x 3B each），导致后续 `linked_to` 数组读取位置错位。

当前状态验证：4 graphs, 37 nodes, 30 pins, **0** pins with `linked_to_raw` non-empty。

---

## 任务

### Task 1: 模型增强 — `FEdGraphPinType` 添加缺失字段

**文件:** `src/uasset_read/models/core.py`

在 `FEdGraphPinType` dataclass 中添加：

```python
is_const: bool = False
is_uobject_wrapper: bool = False
b_serialize_as_single_precision_float: bool = False
```

同时确认 `is_reference` 和 `is_weak_pointer` 字段已存在（当前代码在 `read_ed_graph_pin_type()` 中赋值但未在模型声明中定义——需补充为 dataclass fields）。

**附带修复:** `pin_subcategory_object` 类型不一致——模型声明 `Optional[str]` 但序列化器赋值 `int` (L69 `read_i32()`)。修正为 `Optional[int] = None`。

### Task 2: 修正 `read_ed_graph_pin_type()` 布尔读取方式

**文件:** `src/uasset_read/serializers/graph.py` L78-94

将 5 个布尔字段的读取从 `read_bool_1byte()` 改为 `read_bool()`：

| 行 | 字段 | 当前 | 修复后 |
|----|------|------|--------|
| 79 | `is_reference` | `read_bool_1byte()` | `read_bool()` |
| 80 | `is_weak_pointer` | `read_bool_1byte()` | `read_bool()` |
| 88 | `is_const` | `read_bool_1byte()` | `read_bool()` |
| 91 | `is_uobject_wrapper` | `read_bool_1byte()` | `read_bool()` |
| 94 | `b_serialize_as_single_precision_float` | `read_bool_1byte()` | `read_bool()` |

**对照 UE 源码:** `EdGraphPin.cpp` L163-345 `FEdGraphPinType::Serialize()` — UE5 中这些 bool 走 `FArchive::operator<<(bool&)` = `uint32` (4B)。

**注意:** `archive.read_bool()` 已存在（L189-196），读取 `uint32`。不需要新方法。

### Task 3: 验证修复 — 运行解析确认 linked_to_raw 非空

修复后运行：

```bash
python -c "
from uasset_read import parse_uasset
result = parse_uasset('E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset')
total = sum(len(n.pins) for g in result.graphs for n in g.nodes)
linked = sum(1 for g in result.graphs for n in g.nodes for p in n.pins if p.linked_to_raw)
print(f'Total pins: {total}, with links: {linked}')
assert linked > 0, 'linked_to_raw still empty after fix'
"
```

预期：`linked > 0`。

### Task 4: 新增测试

**文件:** `tests/test_phase47_pin_linkedto.py`

- 解析 `BP_FirstPersonCharacter.uasset`
- 断言至少一个 pin 的 `linked_to_raw` 非空
- 断言 `connections` 数组（通过 `build_connections_map`）非空
- 断言至少一条 execution flow 的 `nodes` 非空

---

## 验证标准

1. `uasset-read BP_FirstPersonCharacter.uasset` 解析成功
2. `linked_to_raw` 不再全为空（至少 > 0 个 pin 有连接）
3. `connections > 0`（图连接数组非空）
4. `execution_flows[].nodes` 至少一条 flow 非空
5. 现有 520 tests 无回归

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/uasset_read/models/core.py` | Edit | `FEdGraphPinType` 添加 5 个字段 |
| `src/uasset_read/serializers/graph.py` | Edit | `read_ed_graph_pin_type()` 5 处 `read_bool_1byte()` → `read_bool()` |
| `tests/test_phase47_pin_linkedto.py` | Create | 验证 linked_to_raw 非空 |

---

## 风险

- **字节偏移确认:** 如果修复后 `linked_to_raw` 仍为空，需要二进制诊断（在 `read_ue_graph_pin()` 中添加 tell() 日志，确认 `read_pin_array()` 读取位置的 array_count 是否 > 0）。
- **其他序列化路径不受影响:** 此修复仅影响 `FEdGraphPinType`。PropertyTag 或其他结构的偏移问题留给后续 phase。
- **UE4 兼容:** 不处理。测试资产为 UE5.7。

---

## 执行顺序

1 → 2 → 3 → 4（顺序执行，Task 3 验证 Task 1+2 正确性后再写测试）

*Created: 2026-05-15*
