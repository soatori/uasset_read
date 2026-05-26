# BP_FirstPersonCharacter 解析差距分析报告

**测试文件：** `E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset`
**UE 版本：** UE5 (FileVersionUE5=1017)
**测试日期：** 2026-05-20
**测试目的：** 验证当前解析输出是否足以支撑 "蓝图节点文本 → C++ 翻译"

---

## 1. 当前能提取的

| 能力 | 状态 | 示例 |
|------|------|------|
| 包元数据 | ✅ | PackageName, UE Version=1017, Imports=73, Exports=69 |
| 蓝图描述 | ✅ | "The character you control in the game, includes firing logic" |
| 父类 | ✅ | `/Script/Engine.Character` |
| 组件列表 | ✅ | Arrow, CameraComponent, CapsuleComponent, CharacterMovementComponent, SkeletalMeshComponent |
| 函数图列表 | ✅ | EventGraph, Aim, Move, UserConstructionScript |
| 节点名称+类型 | ✅ | `K2Node_CallFunction_8428` (AddControllerYawInput), `K2Node_EnhancedInputAction_1` (IA_MouseLook) |
| 节点坐标 | ✅ | NodePosX/Y 精确值 |
| 注释框文本 | ✅ | "Camera Input", "Movement Input", "Jump Input", "Up/Down", "Left/Right" |
| Function 函数名 | ✅ | Aim, Move, ExecuteUbergraph_BP_FirstPersonCharacter, InpActEvt_* |
| InputAction 绑定 | ✅ | IA_MouseLook, IA_Move, IA_Look, IA_Jump |

## 2. 关键差距

### GAP-01: 函数引用解析失败 — 无法获取 "调用的是什么函数"

**现象：**
```
K2Node_CallFunction:
  function_reference: FMemberReference(
    member_parent=None,        # ← 应该是 ACharacter 或 UKismetSystemLibrary
    member_name='None',        # ← 应该是 'AddControllerYawInput'
    b_self_context=True
  )
```

但从文本格式输出可以看到，**Export 的 PropertyTag 层是有正确信息的**：
```
K2Node_CallFunction_8428:
  FunctionReference.MemberName: 'AddControllerYawInput'   ← 有值
K2Node_CallFunction_8429:
  FunctionReference.MemberName: 'AddControllerPitchInput'  ← 有值
```

**根因：** `read_k2node_call_function()` → `read_fmember_reference()` 读取时 `archive.read_name()` 返回 'None'。
脚本序列化层（script_serial）的 PropertyTag 解析是正确的，但**节点特有字段二次读取**（`create_node_from_archive`）时 archive 位置不对或 FName 序列化格式与 UE5.8 不匹配。

**影响：** Agent 只能从节点导出名称（`K2Node_CallFunction_8428`）猜测意图，无法知道实际调用哪个 UE 函数。**无法翻译 C++**。

### GAP-02: Pin 连接全部为空 — 无法获取数据流

**现象：**
```
所有节点的 pins[].linked_to_raw = []
所有节点的 pins[].pin_type.pin_category = 'None'
所有节点的 pins[].pin_type.pin_subcategory = 'None'
```

**根因：** `read_ue_graph_pin()` 中 `read_pin_array()` 在读取 LinkedTo 数组时返回空列表。
可能原因：
1. Pin array count 读取为 0（archive 位置偏移）
2. UE5.8 的 SerializePinArray 格式变更（增加/减少了字段）

**影响：** Agent 不知道 A 节点的输出连接到 B 节点的哪个输入。**无法生成 `=` 赋值或函数调用链**。

### GAP-03: StructProperty 解析为 UnknownStruct — 缺失变量类型信息

**现象：**
```
RelativeLocation: StructValue(struct_type='UnknownStruct', fields={}, property_type='StructProperty')
RelativeRotation: StructValue(struct_type='UnknownStruct', fields={}, property_type='StructProperty')
BlueprintGuid: StructValue(struct_type='UnknownStruct', fields={}, property_type='StructProperty')
```

**根因：** 无 UScriptStruct 映射表（.usmap / umap），无法将 struct GUID 解析为已知结构体（Vector, Rotator, Guid 等）。

**影响：** Agent 无法知道 `RelativeLocation` 是 `FVector` 类型。**C++ 翻译缺少类型声明**。

### GAP-04: ParseError — 部分属性解析中途失败

**现象：**
```
CategoryName: ParseError: Cannot read 3328 bytes at position 136084, only 2300 bytes remaining
BodyInstance: ParseError: Size 16777216 exceeds remaining 1224 bytes
RelativeLocation: ParseError: Invalid size -1067974656 (negative)
```

**根因：** StructProperty 反序列化时 size 字段读取错误（实际是 struct name 或其他字段被误解析为 size）。

**影响：** 组件属性不完整。对 C++ 翻译影响较小（主要是初始值）。

### GAP-05: ExecuteUbergraph 字节码未提取

**现象：** `ExecuteUbergraph_BP_FirstPersonCharacter` 的 SerialSize=5977，这是包含 Kismet 字节码的 Function export。
但当前管线**未提取 ScriptBytecode**。

**根因：** `parse_uasset()` 的默认路径不走 `Function` 类型 Export 的 script_serial 解析（v11.0 Phase 61-63 正在构建此能力）。

**影响：** Agent 只能看到"有 ExecuteUbergraph 函数"，但看不到内部的 if/for/变量赋值逻辑。
**这是蓝图 → C++ 翻译中 70%+ 的逻辑所在**。

### GAP-06: 执行流只有 FunctionEntry，无后续节点

**现象：**
```json
"execution_flows": [{
  "start_event": "FunctionEntry.Aim",
  "nodes": [{"node_type": "K2Node_FunctionEntry", "function_name": "Aim"}]
}]
```

每个图的执行流只有入口节点，没有后续节点。

**根因：** `build_execution_flows()` 依赖 `pin.linked_to_raw`（GAP-02）来追踪执行 pin 的连接，由于 connected_to 为空，执行流无法延伸。

**影响：** Agent 不知道函数体内节点的执行顺序。

### GAP-07: 函数签名全空

**现象：**
```json
"signature": {"return_type": "", "parameters": []}
```

**根因：** 函数图提取时未解析 Function 节点的输入/输出 Pin 作为参数。

**影响：** C++ 翻译缺少函数声明。

## 3. 跨工具对比

| 能力 | uasset_read (当前) | CUE4Parse | UE 5.8 MCP | UnrealBridge |
|------|:---:|:---:|:---:|:---:|
| 包元数据 | ✅ | ✅ | ❌ | ❌ |
| 组件列表 | ✅ | ✅ | ✅ | ✅ |
| 节点名称 | ✅ | ✅ | ✅ | ✅ |
| **函数引用** | ❌ (GAP-01) | ✅ | ✅ | ✅ |
| **Pin 连接** | ❌ (GAP-02) | ✅ | ✅ | ✅ |
| **Struct 字段** | ❌ (GAP-03) | ✅ (需.usmap) | ✅ | ✅ |
| **Kismet 字节码** | ❌ (GAP-05) | ✅ | ❌ | ❌ |
| **执行流追踪** | ❌ (GAP-06) | ✅ (via 字节码) | ❌ | ❌ |
| 注释框文本 | ✅ | ❌ | ❌ | ❌ |
| 节点坐标 | ✅ | ❌ | ❌ | ❌ |

## 4. 结论

**当前输出仅够 Level 0（节点骨架），不足以翻译 C++。**

要达成"节点文本 → C++ 翻译"目标，必须解决的优先级：

| 优先级 | 差距 | 修复方向 | 预计工作量 |
|--------|------|---------|-----------|
| **P0** | GAP-01: 函数引用 | 修复 FMemberReference 读取，或直接从 PropertyTag 层提取 | 小（1-2h） |
| **P0** | GAP-02: Pin 连接 | 修复 read_pin_array 的 archive 位置/格式 | 中（2-4h） |
| **P1** | GAP-05: ExecuteUbergraph 字节码 | Phase 61-63 已完成字节码解析，需要集成到 parse_uasset | 中（Phase 64） |
| **P1** | GAP-03: Struct 映射 | 加载 UE5 .usmap 或硬编码常见 struct | 小（1-2h） |
| **P2** | GAP-06: 执行流 | 修复 GAP-02 后自动解决 | 依赖 GAP-02 |
| **P2** | GAP-07: 函数签名 | 从 Function 节点的 Input/Output Pin 提取 | 小（1h） |
| **P3** | GAP-04: ParseError | StructProperty size 解析修复 | 中（2-4h） |

**修复 P0 后**，Agent 将能获得 "节点名称 + 函数调用 + Pin 连接"（Level 2），足以生成基础 C++ 调用代码。
**修复 P0 + P1 后**，Agent 将获得完整的蓝图逻辑（包括 ExecuteUbergraph 中的控制流），可翻译为完整 C++ 函数体。
