# BP_FirstPersonCharacter.uasset 解析对比报告

> 生成日期：2026-05-27
> 源文件：`E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset`
> 对比基准：`docs/references/蓝图节点文本参考.md` + `docs/references/测试对照C++类/`
> 解析版本：dev-0.3.0

---

## 一、解析概况

| 项目 | 值 |
|------|------|
| 蓝图路径 | `/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter` |
| 父类 | `TP_FirstPersonCharacter` |
| UE 版本 | 5.5（PackageVersion = 1017） |
| PackageFlags | `0x00040000` |
| ImportMap 条目 | 54 |
| ExportMap 条目 | 29 |
| 解析图表 | 2（EventGraph + UserConstructionScript） |
| EventGraph 节点数 | 9 |
| Kismet 字节码 | 5 个函数通过 BPGC fallback 恢复 |

### 警告信息

```
[P73-PROPTRACE] Suspicious PropertyTag '/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter_143' size=1 exceeds struct boundary
[P73-PROPTRACE] Suspicious PropertyTag '/Script/CoreUObject_143' size=1 exceeds struct boundary
```

Struct 解析存在边界偏移问题，PropertyTag 读取越界。

### Kismet 恢复的函数

| 函数名 | 表达式数 | 方式 |
|--------|---------|------|
| `ExecuteUbergraph_BP_FirstPersonCharacter` | 3 | BPGC bytecode scan |
| `Primary Thumbstick` | 6 | BPGC bytecode scan |
| `Secondary Thumbstick` | 6 | BPGC bytecode scan |
| `Touch Jump Start` | 7 | BPGC bytecode scan |
| `Touch Jump End` | 7 | BPGC bytecode scan |

---

## 二、解析器输出的 EventGraph 节点

| # | 节点名 | 类型 | 说明 | 位置 |
|---|--------|------|------|------|
| 1 | `EdGraphNode_Comment_0` | Comment | "Touch Inputs for First Person Character" | (752, 608) |
| 2 | `K2Node_CallFunction_1` | CallFunction | `DoMove` | (1120, 672) |
| 3 | `K2Node_CallFunction_2` | CallFunction | `DoJumpStart` | (1136, 1072) |
| 4 | `K2Node_CallFunction_3` | CallFunction | `DoJumpEnd` | (1136, 1232) |
| 5 | `K2Node_CallFunction_4` | CallFunction | `DoAim` | (1120, 864) |
| 6 | `K2Node_Event_5` | Event | `Primary Thumbstick` | (816, 672) |
| 7 | `K2Node_Event_6` | Event | `Touch Jump Start` | (816, 1072) |
| 8 | `K2Node_Event_7` | Event | `Touch Jump End` | (816, 1232) |
| 9 | `K2Node_Event_8` | Event | `Secondary Thumbstick` | (816, 864) |

### 解析器输出的连接关系

```
Primary Thumbstick.then ──────→ DoMove.execute
  ├─ Axis_X ──────────────────→ DoMove.Right
  └─ Axis_Y ──────────────────→ DoMove.Forward

Secondary Thumbstick.then ────→ DoAim.execute
  ├─ Axis_X ──────────────────→ DoAim.Yaw
  └─ Axis_Y ──────────────────→ DoAim.Pitch

Touch Jump Start.then ────────→ DoJumpStart.execute
Touch Jump End.then ──────────→ DoJumpEnd.execute
```

### Default__BP_FirstPersonCharacter_C 默认实例属性

| 属性 | 类型 | 值 |
|------|------|------|
| `FirstPersonMesh` | ObjectProperty | Export #29 |
| `FirstPersonCameraComponent` | ObjectProperty | Export #5 |
| `JumpAction` | ObjectProperty | Import #30 → `IA_Jump` |
| `MoveAction` | ObjectProperty | Import #33 → `IA_Move` |
| `LookAction` | ObjectProperty | Import #31 → `IA_Look` |
| `MouseLookAction` | ObjectProperty | Import #32 → `IA_MouseLook` |
| `Mesh` | ObjectProperty | Export #28 |
| `CharacterMovement` | ObjectProperty | Export #7 |
| `CapsuleComponent` | ObjectProperty | Export #6 |

---

## 三、蓝图节点文本参考中的节点

参考文档记录了 **20+ 个节点**，分为两套输入系统：

### A. Enhanced Input 系统（参考文档有，解析输出缺失）

| 节点名 | 类型 | 说明 |
|--------|------|------|
| `K2Node_EnhancedInputAction_2` | InputAction | `IA_Look`（输入动作：注视） |
| `K2Node_EnhancedInputAction_3` | InputAction | `IA_Move`（输入动作：移动） |
| `K2Node_EnhancedInputAction_5` | InputAction | `IA_Jump`（输入动作：跳跃） |
| `K2Node_EnhancedInputAction_0` | InputAction | `IA_MouseLook`（输入动作：鼠标注视） |
| `K2Node_CallFunction_1193` | CallFunction | `Jump`（Character 方法） |
| `K2Node_CallFunction_9386` | CallFunction | `StopJumping`（Character 方法） |
| `K2Node_CallFunction_5` | CallFunction | `Move`（自定义函数） |
| `K2Node_CallFunction_4` | CallFunction | `Move`（自定义函数，另一实例） |
| `K2Node_CallFunction_11` | CallFunction | `Aim`（自定义函数） |
| `K2Node_CallFunction_6` | CallFunction | `Aim`（自定义函数，另一实例） |
| `K2Node_CallFunction_7` | CallFunction | `Aim`（自定义函数，鼠标路径） |

### B. 自定义 Move 函数内部实现（参考文档有，解析输出缺失）

| 节点名 | 类型 | 说明 |
|--------|------|------|
| `K2Node_FunctionEntry_0` | FunctionEntry | `Move` 函数入口（`Left/Right` + `Forward/Backward` 参数） |
| `K2Node_CallFunction_7445` | CallFunction | `AddMovementInput`（Right 向量路径） |
| `K2Node_CallFunction_7346` | CallFunction | `AddMovementInput`（Forward 向量路径） |
| `K2Node_CallFunction_8520` | CallFunction | `GetActorRightVector` |
| `K2Node_CallFunction_8029` | CallFunction | `GetActorForwardVector` |
| `K2Node_Knot_1~4` | Knot | Reroute 转接节点（4 个） |

### C. 参考文档中的注释框

| 节点名 | 注释内容 |
|--------|---------|
| `EdGraphNode_Comment_1` | "Camera Input" |
| `EdGraphNode_Comment_4` | "Movement Input" |
| `EdGraphNode_Comment_0` | "Jump Input - Jump can be configured in the CharacterMovementComponent" |
| `EdGraphNode_Comment_5` | "Left/Right" |
| `EdGraphNode_Comment_6` | "Forward / Backward" |

### D. Touch Interface 事件（两者都有，但细节不同）

| 功能 | 参考文档节点 | 解析输出节点 | Guid 匹配 |
|------|------------|-------------|-----------|
| Primary Thumbstick | `K2Node_Event_2` | `K2Node_Event_5` | 不匹配 |
| Secondary Thumbstick | `K2Node_Event_3` | `K2Node_Event_8` | 不匹配 |
| Touch Jump Start | `K2Node_Event_4` | `K2Node_Event_6` | 不匹配 |
| Touch Jump End | `K2Node_Event_5` | `K2Node_Event_7` | 不匹配 |

**所有同名事件的 NodeGuid 均不相同**，说明两套文件来自不同的蓝图保存状态。

---

## 四、参考文档连接逻辑（完整版）

```
─── Enhanced Input 路径 ───

IA_Look.Triggered   ──→ Aim(Yaw=ActionValue.X, Pitch=ActionValue.Y)
IA_Move.Triggered   ──→ Move(Left/Right=ActionValue.X, Forward/Backward=ActionValue.Y)
IA_Jump.Started     ──→ Jump()
IA_Jump.Completed   ──→ StopJumping()
IA_MouseLook.Triggered ──→ Aim(Yaw=ActionValue.X, Pitch=ActionValue.Y)

─── Touch Interface 路径 ───

Primary Thumbstick    ──→ Move(Left/Right=Axis.X, Forward/Backward=Axis.Y)
Secondary Thumbstick  ──→ Aim(Yaw=Axis.X, Pitch=Axis.Y)
Touch Jump Start      ──→ Jump()
Touch Jump End        ──→ StopJumping()

─── Move 自定义函数内部 ───

Move(FunctionEntry)
  ├─ Left/Right ──→ Knot_1→Knot_2 ──→ ScaleValue of AddMovementInput(#7445)
  │                                     self.GetActorRightVector() → WorldDirection
  └─ Forward/Backward ──→ Knot_3→Knot_4 ──→ ScaleValue of AddMovementInput(#7346)
                                              self.GetActorForwardVector() → WorldDirection
```

---

## 五、与 C++ 对照类对比

### 5.1 类结构对照

| C++ 元素 | 声明位置 | 蓝图中的体现 |
|----------|---------|-------------|
| `AFirstPersonCCharacter` 类 | `FirstPersonCCharacter.h:22` | 父类 `TP_FirstPersonCharacter`（对应 C++ 基类变体） |
| `FirstPersonMesh` | `h:28` | Default 实例 ObjectProperty → Export #29 |
| `FirstPersonCameraComponent` | `h:32` | Default 实例 ObjectProperty → Export #5 |
| `JumpAction` | `h:38` | Default 实例 → Import #30 `IA_Jump` |
| `MoveAction` | `h:42` | Default 实例 → Import #33 `IA_Move` |
| `LookAction` | `h:46` | Default 实例 → Import #31 `IA_Look` |
| `MouseLookAction` | `h:50` | Default 实例 → Import #32 `IA_MouseLook` |
| `DoAim(float, float)` | `h:65` | `BlueprintCallable` — 解析输出中 `K2Node_CallFunction_4` 调用 |
| `DoMove(float, float)` | `h:69` | `BlueprintCallable` — 解析输出中 `K2Node_CallFunction_1` 调用 |
| `DoJumpStart()` | `h:73` | `BlueprintCallable` — 解析输出中 `K2Node_CallFunction_2` 调用 |
| `DoJumpEnd()` | `h:77` | `BlueprintCallable` — 解析输出中 `K2Node_CallFunction_3` 调用 |
| `MoveInput(FInputActionValue)` | `h:58` | 对应蓝图 `Move` 函数逻辑，解析输出中未直接出现 |
| `LookInput(FInputActionValue)` | `h:61` | 对应蓝图 `Look` 逻辑，解析输出中未直接出现 |
| `SetupPlayerInputComponent` | `h:82` | 输入绑定逻辑，蓝图中以 EventGraph 节点形式体现 |

### 5.2 C++ 输入绑定 vs 蓝图连接

| C++ 绑定代码（`SetupPlayerInputComponent`） | 蓝图等价 | 解析输出状态 |
|---------------------------------------------|---------|-------------|
| `JumpAction → Started → DoJumpStart()` | `IA_Jump.Started → Jump()` | 参考文档有，解析输出无 |
| `JumpAction → Completed → DoJumpEnd()` | `IA_Jump.Completed → StopJumping()` | 参考文档有，解析输出无 |
| `MoveAction → Triggered → MoveInput()` | `IA_Move.Triggered → Move()` | 参考文档有，解析输出无 |
| `LookAction → Triggered → LookInput()` | `IA_Look.Triggered → Aim()` | 参考文档有，解析输出无 |
| `MouseLookAction → Triggered → LookInput()` | `IA_MouseLook.Triggered → Aim()` | 参考文档有，解析输出无 |

### 5.3 C++ 方法实现 vs 蓝图逻辑

| C++ 方法 | 实现逻辑 | 蓝图对照 |
|----------|---------|---------|
| `DoAim(Yaw, Pitch)` | `AddControllerYawInput(Yaw)` + `AddControllerPitchInput(Pitch)` | `K2Node_CallFunction_4`（解析输出）/ `K2Node_CallFunction_11/6/7`（参考文档） |
| `DoMove(Right, Forward)` | `AddMovementInput(GetActorRightVector(), Right)` + `AddMovementInput(GetActorForwardVector(), Forward)` | `K2Node_CallFunction_1`（解析输出，直接调用）/ `Move` 函数内部 `K2Node_CallFunction_7445/7346/8520/8029`（参考文档） |
| `DoJumpStart()` | `Jump()` | `K2Node_CallFunction_2`（解析输出）/ `K2Node_CallFunction_1193`（参考文档） |
| `DoJumpEnd()` | `StopJumping()` | `K2Node_CallFunction_3`（解析输出）/ `K2Node_CallFunction_9386`（参考文档） |

---

## 六、差异根因分析

### 6.1 两套不同的蓝图保存状态

| 特征 | 解析输出（当前 uasset） | 参考文档 |
|------|------------------------|---------|
| 输入系统 | 仅 Touch Interface 事件 | Enhanced Input + Touch Interface 双系统 |
| 节点数量 | 9 | 20+ |
| 自定义函数 | 无 `Move` 函数内部实现 | 完整 `Move` 函数（FunctionEntry + 4 个 Knot + 4 个 CallFunction） |
| Jump 逻辑 | 调用 `DoJumpStart/DoJumpEnd` | 直接调用 `Jump/StopJumping` |
| Aim 逻辑 | 调用 `DoAim` | 调用 `Aim`（3 个实例） |
| Move 逻辑 | 调用 `DoMove` | 调用 `Move`（2 个实例）+ Move 函数内部实现 |
| 注释 | 1 个（"Touch Inputs..."） | 5 个（"Camera Input" / "Movement Input" / "Jump Input" / "Left/Right" / "Forward/Backward"） |
| 所有 NodeGuid | 与参考文档全部不匹配 | 内部一致 |

### 6.2 可能原因

1. **文件版本不同**：解析器读取的 `.uasset` 与参考文档的来源文件可能来自 UE 项目的不同保存时间点（编译前后的状态差异）。
2. **蓝图编译状态**：UE 蓝图编译后，EventGraph 节点可能被重新编号或重组。
3. **解析遗漏**：当前解析器的 `--blueprint-text` 输出可能未完整遍历所有 `ExportMap` 中的 K2Node 导出项（EnhancedInputAction、FunctionEntry、Knot 等节点类型可能未被正确处理）。
4. **Parent Class 差异**：解析输出显示父类为 `TP_FirstPersonCharacter`，而 C++ 对照类继承自 `ACharacter`，说明可能存在中间类层。

---

## 七、解析器改进建议

### 7.1 节点类型覆盖

| 缺失节点类型 | 优先级 | 说明 |
|-------------|--------|------|
| `K2Node_EnhancedInputAction` | P0 | 增强输入动作节点，现代 UE5 项目核心输入方式 |
| `K2Node_FunctionEntry` | P0 | 自定义函数入口，蓝图函数库解析必需 |
| `K2Node_Knot` | P2 | Reroute 转接节点，影响数据流完整性 |
| `K2Node_Variable` | P2 | 变量读写节点 |
| `K2Node_MacroInstance` | P3 | 宏实例节点 |

### 7.2 连接关系完整性

- **LinkedTo 引脚解析**：当前 `--blueprint-text` 输出中的 `links=` 引用仅显示节点名+引脚名，应同时输出 PinId 以便交叉验证。
- **SubPin 展开**：Vector2D 等结构的 SubPin 展开逻辑已实现（`Axis_X`, `Axis_Y`），但需验证与参考文档中 `ActionValue_X/Y` 的一致性。

### 7.3 多 Graph 遍历

- 当前仅输出 `EventGraph` 和 `UserConstructionScript`，需确认是否遗漏其他函数图（如 `Move` 函数对应的独立 EdGraph）。
- `Blueprint.GeneratedClass.BPGC` 中的 `FuncMap` 应包含所有自定义函数图。

### 7.4 PropertyTag 边界问题

```
[P73-PROPTRACE] Suspicious PropertyTag size=1 exceeds struct boundary
```

Struct 属性的 `tag_end` 计算存在偏差，需对齐 CUE4Parse 的 `StructProperty` 解析逻辑。

---

## 八、总结

| 维度 | 评估 |
|------|------|
| 基础节点解析 | 通过 — `K2Node_Event`、`K2Node_CallFunction`、`EdGraphNode_Comment` 可正确解析 |
| 函数调用识别 | 通过 — `DoMove`、`DoAim`、`DoJumpStart`、`DoJumpEnd` 函数名正确提取 |
| 引脚连接关系 | 部分通过 — 基础 exec/data 连接正确，但 SubPin 和 LinkedTo 交叉引用不完整 |
| Enhanced Input 节点 | 缺失 — `K2Node_EnhancedInputAction` 未解析 |
| 自定义函数图 | 缺失 — `Move` 函数内部实现未解析 |
| Kismet 字节码 | 部分恢复 — 5 个函数通过 BPGC fallback 恢复，但仅 3-7 个表达式 |
| 与 C++ 对照 | 部分匹配 — 4 个 InputAction 变量、4 个 BlueprintCallable 方法在 Default 实例中存在 |

---

## 九、修正后的根因结论（2026-05-27）

经过 CUE4Parse 与本项目 CLI 双向验证，差异应拆成两类：

1. **资产状态差异**：`docs/references/BP_FirstPersonCharacter.uasset` 是 Touch-only 变体；外部 UE Sample 路径下的同名资产才包含 Enhanced Input、`Move`、`Aim` 等完整函数图。不能用完整版参考文本断言 Touch-only 资产解析缺节点。
2. **解析器核心风险**：`StructProperty` fallback 曾把未知 native/binary struct 误当 tagged struct 读取，导致伪 `PropertyTag` 名称和 `P73-PROPTRACE` 级联警告。修复方向已改为参考 CUE4Parse：PropertyTag value 以 `value_start + Size` 为硬边界；未知 struct 默认 opaque 跳过；只有 `MemberReference` 等明确 tagged fallback struct 才读取内部 PropertyTag。

验证结果：

| 资产 | CUE4Parse NodeCount | 本项目蓝图图表 |
|------|---------------------|----------------|
| 外部 UE Sample `BP_FirstPersonCharacter.uasset` | 41 | `Aim`、`EventGraph`、`Move`、`UserConstructionScript` |
| 仓库参考 `docs/references/BP_FirstPersonCharacter.uasset` | 12 | `EventGraph`、`UserConstructionScript` |

回归要求：两个资产执行 `--blueprint-text` 不应再出现 `[P73-PROPTRACE] Suspicious PropertyTag ... exceeds struct boundary`。
