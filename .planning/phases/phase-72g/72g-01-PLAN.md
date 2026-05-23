# Phase 72-G — 复杂 StructProperty 解析 + Pin 连接映射修复

| 字段 | 值 |
|------|-----|
| Milestone | v13.0 |
| Status | Planned |
| Inserted | 2026-05-23 |
| Source | BP_FirstPersonCharacter vs FirstPersonCCharacter 三方对照分析 |

## 目标

修复反复出现、多次修复仍未彻底解决的顽固解析问题，将 BP_FirstPersonCharacter.uasset 解析覆盖率从 ~56% 提升至 >90%。

## 问题与修复

### M-01: Complex StructProperty 解析失败 (🔴 High)

**历史:** Phase 67 修复了 PropertyTag 层格式 → StructProperty 内部字段仍失败

**症状:**
- `RelativeLocation` → `ParseError: Invalid size -1067974656 (negative)`
- `RelativeRotation` → `ParseError: Size 2113929216 exceeds remaining 204 bytes`
- `BodyInstance` → `ParseError: Size 2048 exceeds remaining 774 bytes`

**根因假设:** UE5 中 FVector/FRotator/FBodyInstance 等结构体在序列化时有额外的 header 信息（如 zero 标记、has value 标记），当前解析器直接按字段大小读取导致偏移错位。

**修复策略:**
1. 在 `parsers/property_types.py` 的 `parse_struct_property()` 中添加 UE5 struct header 检测
2. 为 FVector/FRotator 添加专用解析路径（已知布局：3×float32）
3. 为 BodyInstance (FBodyInstance) 添加零值跳过逻辑
4. **增加偏移追踪日志** — 每次嵌套读取前后记录 `archive.tell()`，可验证偏移正确性

### M-02: Pin 连接映射输出为空 (🔴 High)

**历史:** Phase 72-B 修复了序列化 bug → 仍未输出到 `connections` 数组

**症状:** EventGraph `connections: []` 始终为空，执行链仅通过 Ubergraph 间接推导

**根因假设:** Phase 72-B 修复了 `serializers/graph.py` 中 LinkedTo 数据的读取（`read_fedgraph_pin_type`），但 `build_connections()` 函数未将读取到的 LinkedTo 数据映射为输出格式中的 connections 数组。修复了"能读到"，但没做到"能输出"。

**修复策略:**
1. 验证 `serializers/graph.py` 中 pin 的 `linked_to` 字段在修复后非空
2. 在 `build_connections()` 中遍历所有节点的所有 pins，提取 linked_to 映射
3. 输出格式：`{"from_node": "N5", "from_pin": "Exec", "to_node": "N11", "to_pin": "Then"}`
4. **增加输出验证测试** — 确保对 BP_FirstPersonCharacter.uasset 输出 connections > 0

### M-03: Blueprint.functions 列表为空 (⚠️ Medium)

**症状:** `Blueprint.functions` 为空，Move/Aim 等自定义函数未提取

**修复策略:**
1. 从 Blueprint 导出对象属性中提取 `UbergraphFunction` 引用
2. 跟随引用链查找 Function 导出对象
3. 输出函数名 + 入口 ordinal

### M-04: 函数参数信息缺失 (⚠️ Medium)

**症状:** DoMove(float, float) 等函数的参数类型和默认值无法获取

**修复策略:**
1. 从 Function 导出对象的序列化区域提取参数表
2. 将参数表与 Kismet 反编译结果关联
3. 输出：`{"name": "DoMove", "params": [{"name": "Right", "type": "float"}, {"name": "Forward", "type": "float"}]}`

### M-05: EnhancedInputComponent BindAction 不可见 (ℹ️ Low)

**状态:** 设计限制 — 运行时绑定逻辑不在未烘焙资产序列化数据中

**处理方式:** 在输出中添加 `warnings` 说明此限制，而非标记为错误

## 验收标准

- [ ] `RelativeLocation`/`RelativeRotation` 提取为结构化数据（x/y/z 或 Pitch/Yaw/Roll）
- [ ] `BodyInstance` 至少提取 CapsuleHalfHeight / CapsuleRadius
- [ ] EventGraph `connections` 数组 > 0
- [ ] `Blueprint.functions` 包含 DoMove/DoAim/DoJumpStart/DoJumpEnd
- [ ] 每个函数输出包含参数名 + 参数类型
- [ ] 回归测试通过，无新增 failures

## 修复顺序

1. **M-02 (Pin 连接)** — 最可能快速修复，已有序列化数据只需映射到输出
2. **M-01 (StructProperty)** — 需要深入诊断 UE5 struct header 格式
3. **M-03 (Blueprint.functions)** — 跟随现有引用链即可
4. **M-04 (函数参数)** — 依赖 M-03 的函数发现

## 风险

- M-01 可能需要参考 UE5 源码中 FBodyInstance 的 Serialize() 实现
- M-02 可能在 pin 序列化层还有未发现的 bug
- 总体工作量估计：1-2 个迭代
