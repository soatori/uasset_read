# Phase 47: Pin LinkedTo 修复 — CONTEXT.md

**Date:** 2026-05-15
**Phase:** 047-pin-linkedto-fix
**Goal:** 修复 `linked_to_raw` 全为空的问题，使 pin 连接关系完整可查，`connections > 0`，`execution_flows[].nodes` 非空

---

## 领域

修复 `FEdGraphPinType` 和 `UEdGraphPin` 的二进制序列化偏移问题。根因在 `serializers/graph.py` 的 `read_ed_graph_pin_type()` 函数——字段顺序和缺失字段导致约 4 字节偏移，进而使后续 `linked_to` 数组读取位置错误。

---

## 关键发现：UE 5.7 源码与 Python 实现字段顺序严重不匹配

### UE 5.7 FEdGraphPinType::Serialize (EdGraphPin.cpp L163-345)

```
1. PinCategory (FName)
2. PinSubCategory (FName)
3. PinSubCategoryObject (FPackageIndex / int32)
4. ContainerType (uint8)
5. [if Map: PinValueType (嵌套 FEdGraphPinType)]
6. bIsReference (bool → uint32 / 4B)        ← 当前 Python 用 read_bool_1byte() (1B)
7. bIsWeakPointer (bool → uint32 / 4B)      ← 当前 Python 用 read_bool_1byte() (1B)
8. PinSubCategoryMemberReference (FMemberReference)
   - MemberParent (FPackageIndex / int32)
   - MemberName (FString)
   - MemberGuid (FGuid / 16B)
9. bIsConst (bool → uint32 / 4B)            ← 当前 Python 缺失
10. bIsUObjectWrapper (bool → uint32 / 4B)  ← 当前 Python 缺失
11. bSerializeAsSinglePrecisionFloat (bool → uint8 / 1B, WITH_EDITOR only) ← 当前 Python 缺失
```

### 当前 Python 实现 (graph.py L59-94)

```
1. PinCategory (FName) ✓
2. PinSubCategory (FName) ✓
3. PinSubCategoryObject (int32) ✓
4. ContainerType (uint8) ✓
5. [if Map: PinValueType] ✓
6. bIsReference → read_bool_1byte() (1B)     ← 应该是 read_bool() (4B)
7. bIsWeakPointer → read_bool_1byte() (1B)   ← 应该是 read_bool() (4B)
   -- 跳过 MemberParent/Name/Guid (但实际读到了，因为位置错位) --
   -- 缺失 bIsConst --
   -- 缺失 bIsUObjectWrapper --
   -- 缺失 bSerializeAsSinglePrecisionFloat --
```

### 偏移量计算

- bIsReference: 1B vs 4B = -3B 偏移
- bIsWeakPointer: 1B vs 4B = -3B 偏移
- 缺失 bIsConst(4B) + bIsUObjectWrapper(4B) + bSerializeAsSinglePrecisionFloat(1B) = -9B
- 总计约 **-6 到 -9 字节**偏移（取决于版本条件分支）

---

## 决策

### 修复策略：严格对齐 UE 5.7 源码

- 修正 `read_ed_graph_pin_type()` 字段顺序，严格对照 UE 5.7 EdGraphPin.cpp L163-345
- 补充缺失字段：`bIsConst`, `bIsUObjectWrapper`, `bSerializeAsSinglePrecisionFloat`
- bool 字段使用 `read_bool()` (4-byte uint32)，非 `read_bool_1byte()`
- 不使用"直接字节读取"猜测——每个字段的读取方式必须有 UE 源码对应行支撑

### UE4 兼容性

不处理。只针对 UE5.7 测试资产。UE4 条件分支（`VER_UE4_EDGRAPHPINTYPE_SERIALIZATION` 等）不需要实现——UE5.7 始终走现代路径。

### 范围

Phase 47 **只修** `FEdGraphPinType` 序列化。PropertyTag CompleteTypeName、其他偏移问题留给后续 phase。

### 验证

修正后 `BP_FirstPersonCharacter.uasset` 的 JSON 输出中：
- `linked_to_raw` 不再全为空
- `connections > 0`
- `execution_flows[].nodes` 非空

---

## 规范引用

- `.planning/ROADMAP.md` — Phase 47 定义: Pin LinkedTo 修复
- `.planning/STATE.md` — v8.0 目标: JSON 可翻译性
- `E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp` — UE 5.7 源码
  - L163-345: `FEdGraphPinType::Serialize()`
  - L1838-1964: `UEdGraphPin::Serialize()`
  - L2063-2130: `UEdGraphPin::SerializePinArray()`
  - L2132-: `UEdGraphPin::SerializePin()`
- `src/uasset_read/serializers/graph.py` — `read_ed_graph_pin_type()` (L54-96), `read_ue_graph_pin()` (L345-515)
- `src/uasset_read/archive.py` — `read_bool()` (L189-196), `read_bool_1byte()` (L198-206)

---

## 代码上下文

### 需要修改的文件

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `src/uasset_read/serializers/graph.py` | 核心修复 | `read_ed_graph_pin_type()`: 修正字段顺序和 bool 类型 |
| `src/uasset_read/models/core.py` | 模型增强 | `FEdGraphPinType`: 添加缺失字段 |
| `tests/` | 新增测试 | 验证 linked_to_raw 非空 |

### 调用链

```
parse_uasset_with_linker()
  → read_ue_graph() [graph.py L867]
    → read_ue_graph_node() [graph.py L683]
      → read_ue_graph_pin() [graph.py L345]
        → read_ed_graph_pin_type() [graph.py L54]  ← 修复目标
        → read_pin_array() [graph.py L316]
          → read_pin_reference() [graph.py L273]
```

### 现有测试资产

- `tests/test_ue5_pin_integration.py` — UE5 pin 集成测试
- `tests/test_graph_parsing.py` — 图解析测试
- `tests/test_phase44_linker_objects.py` — linker 对象测试

---

## 延期想法

- PropertyTag CompleteTypeName 偏移问题 → 后续 phase
- 组件属性递归解析 → Phase 48
- 函数调用引脚解析 → Phase 49
- EnhancedInput 语义增强 → Phase 50

---

*Created: 2026-05-15 | Mode: plan*
