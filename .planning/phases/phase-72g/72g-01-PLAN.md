# Phase 72-G — 复杂 StructProperty 解析 + Pin 连接映射修复

| 字段 | 值 |
|------|-----|
| Milestone | v13.0 |
| Status | Planned |
| Inserted | 2026-05-23 |
| Source | BP_FirstPersonCharacter vs FirstPersonCCharacter 三方对照分析 |
| Research | RESEARCH.md (HIGH confidence, CUE4Parse + UE C++ verified) |

## 目标

修复反复出现、多次修复仍未彻底解决的顽固解析问题，将 BP_FirstPersonCharacter.uasset 解析覆盖率从 ~56% 提升至 >90%。

## 根因总结（基于 RESEARCH.md）

### M-01: Complex StructProperty 解析失败 (🔴 High)

**根因（已验证）：**
1. **缺少专用快速解析器** — CUE4Parse 对 Vector/Rotator 直接读取 3 float，Python 依赖 PropertyTags 循环
2. **类型名提取复杂** — UE5 `FPropertyTypeNameNode` 链式格式，`_extract_struct_type_from_tag()` 可能提取失败
3. **BodyInstance 自定义序列化** — UE C++ `operator<<` 只序列化部分属性，其他通过 tagged properties

**证据：** CUE4Parse FScriptStruct.cs Line 174-178（Vector/Rotator 快速路径），UE BodyInstance.cpp Line 422-438（自定义 Serialize）

### M-02: Pin 连接映射输出为空 (🔴 High)

**根因（已验证）：**
1. **缺少数据填充验证** — `read_pin_array()` 异常时返回空数组，但未记录异常原因
2. **linked_to_raw 未验证非空** — `build_connections_map()` Line 657: `for linked_pin_ref in (pin.linked_to_raw or [])`
3. **缺少位置一致性验证** — LinkedTo 读取后位置可能错位

**证据：** graph.py Line 463-468（try/except 返回 []），flow_builder.py Line 657（未检查 linked_to_raw 非空）

### M-03: Blueprint.functions 列表为空 (⚠️ Medium)

**根因（已验证）：**
1. **仅依赖 Fallback 路径** — `_extract_functions_from_graphs()` 注释明确说明是 Fallback
2. **缺少 BPGC 属性提取** — 未从 BlueprintGeneratedClass 属性提取 UbergraphFunction/FunctionList
3. **member_name 解析为 "None"** — FMemberReference 序列化可能失败

**证据：** variable_extractor.py Line 489（仅从 graphs 提取），CUE4Parse BlueprintNodeExtractor.cs Line 234-243（BPGC 属性提取）

### M-04: 函数参数信息缺失 (⚠️ Medium)

**根因：** 依赖 M-01/M-02/M-03 的修复。Pin 数据完整性是参数提取的前提。

---

## 修复方案（基于 CUE4Parse 参考）

### Wave 1: M-02 LinkedTo 验证日志 + 非空检查 (LOW risk)

**任务：**
1. `graph.py` Line 461-468 — 添加 LinkedTo 读取验证日志
2. `flow_builder.py` Line 630 — 添加 linked_to_count 非空检查警告
3. 单元测试验证 LinkedTo 数据填充

**代码示例：**
```python
# graph.py Line 461-468
linkedto_start = archive.tell()
try:
    linked_to = read_pin_array(archive, name_map, export_map, import_map, linker)
    logger.debug(f"LinkedTo: {len(linked_to)} refs at pos {linkedto_start}")
except Exception as e:
    logger.error(f"LinkedTo read failed at pos {linkedto_start}: {e}")
    linked_to = []

# flow_builder.py Line 630
linked_to_count = sum(len(pin.linked_to_raw or []) for node in graph.nodes for pin in node.pins)
if linked_to_count == 0:
    warnings.append("WARNING: No LinkedTo data — connections will be empty")
```

### Wave 2: M-01 Vector/Rotator 专用解析 (MEDIUM risk)

**任务：**
1. `parsers/property_types.py` — 添加 Vector/Rotator 快速解析路径
2. 单元测试验证 `_extract_struct_type_from_tag()` 对 UE5 格式的提取
3. 偏移追踪日志验证嵌套读取正确性

**代码示例：**
```python
# property_types.py parse_struct_property() 开头添加
if struct_type == "Vector":
    x = archive.read_f32()
    y = archive.read_f32()
    z = archive.read_f32()
    return StructValue(struct_type="Vector", fields={"X": x, "Y": y, "Z": z})

if struct_type == "Rotator":
    pitch = archive.read_f32()
    yaw = archive.read_f32()
    roll = archive.read_f32()
    return StructValue(struct_type="Rotator", fields={"Pitch": pitch, "Yaw": yaw, "Roll": roll})
```

### Wave 3: M-03 BPGC 属性提取路径 (MEDIUM risk)

**任务：**
1. `blueprint/variable_extractor.py` — 添加 BPGC 属性提取路径
2. 从 UbergraphFunction/FunctionList 提取函数引用
3. 修复 FMemberReference.member_name 解析

**代码示例：**
```python
# variable_extractor.py extract_blueprint_metadata()
for prop in properties:
    if prop.name == "UbergraphFunction":
        # 提取函数引用
        func_ref = prop.value  # FPackageIndex
        # ...
    elif prop.name == "FunctionList":
        for func_idx in prop.value:
            # ...
```

### Wave 4: M-04 参数提取验证 (LOW risk, 依赖前 Wave)

**任务：**
1. 验证 Pin 数据完整性修复后参数提取工作正常
2. 添加参数提取单元测试

---

## 验收标准

- [ ] `RelativeLocation` 提取为 `{X: float, Y: float, Z: float}`
- [ ] `RelativeRotation` 提取为 `{Pitch: float, Yaw: float, Roll: float}`
- [ ] EventGraph `connections` 数组 > 0（非空）
- [ ] `Blueprint.functions` 包含 Move/Aim/JumpStart/JumpEnd
- [ ] 每个函数输出包含 `parameters` 列表（参数名 + 类型）
- [ ] 回归测试通过，无新增 failures

## 修复顺序

| Wave | 问题 | 风险 | 依赖 | 预期工作量 |
|------|------|------|------|-----------|
| 1 | M-02 LinkedTo 验证 | LOW | 无 | 1-2 h |
| 2 | M-01 Vector/Rotator | MEDIUM | Wave 1 | 2-3 h |
| 3 | M-03 BPGC 属性提取 | MEDIUM | Wave 1 | 2-4 h |
| 4 | M-04 参数验证 | LOW | Wave 1-3 | 1 h |

## 参考

- `.planning/phases/phase-72g/RESEARCH.md` — 根因分析详细报告
- CUE4Parse FScriptStruct.cs Line 174-178 — Vector/Rotator 快速解析
- CUE4Parse UEdGraphPin.cs Line 86 — LinkedTo 序列化
- UE BodyInstance.cpp Line 422-438 — 自定义 Serialize