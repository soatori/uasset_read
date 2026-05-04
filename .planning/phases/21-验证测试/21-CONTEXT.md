# Phase 21: 验证测试 - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

验证JSON输出与UE编辑器信息一致，确保正确性。Phase 21专注于节点数量匹配、执行流程验证、数据流验证、节点属性验证。使用真实资产集成测试，精确匹配预期值。

**Requirements:** TEST-01~04 (节点数量匹配、连接关系验证、数据流验证、节点属性验证)

**范围锚点：** 仅验证现有输出正确性，不添加新解析功能或修改输出结构。

</domain>

<decisions>
## Implementation Decisions

### 测试方法
- **D-21-01:** 集成测试（真实资产） — 解析BP_FirstPersonCharacter.uasset，验证解析结果符合预期
- **D-21-02:** 不使用mock数据单元测试 — 验证目标是解析正确性而非格式化逻辑

### 测试资产
- **D-21-03:** 使用BP_FirstPersonCharacter.uasset（UE 5.7） — 路径：`E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset`
- **D-21-04:** 单资产验证 — 不添加额外测试资产，专注于一个完整验证场景

### 验证标准
- **D-21-05:** 精确匹配标准 — 节点数量、执行流程、数据流必须完全匹配expected值
- **D-21-06:** 不允许动态范围差异 — 严格确保正确性

### 测试文件组织
- **D-21-07:** 新建专用测试文件 — `tests/test_phase21_verification.py`
- **D-21-08:** 不扩展现有文件 — 便于追踪和隔离验证测试

### Expected数据来源
- **D-21-09:** C++源码对照 — 使用FirstPersonC源码作为expected数据权威参考
  - `E:/Develop/lib/UnrealEngine/Samples/FirstPersonC/Source/FirstPersonC/FirstPersonCCharacter.h`
  - `E:/Develop/lib/UnrealEngine/Samples/FirstPersonC/Source/FirstPersonC/FirstPersonCCharacter.cpp`
- **D-21-10:** 关键对照函数：
  - `DoJumpStart()` → `Jump()`
  - `DoJumpEnd()` → `StopJumping()`
  - `MoveInput(ActionValue)` → `DoMove(Right, Forward)` → `AddMovementInput`

### Claude's Discretion
- 确切节点数量expected值（需解析确定）
- 执行流程深度（是否追踪到AddMovementInput层级）
- 数据流匹配模式（参数名映射）

</decisions>

<specifics>
## Specific Ideas

**C++源码对照关键点：**
```cpp
// Jump输入绑定（SetupPlayerInputComponent）
EnhancedInputComponent->BindAction(JumpAction, ETriggerEvent::Started, this, &AFirstPersonCCharacter::DoJumpStart);
EnhancedInputComponent->BindAction(JumpAction, ETriggerEvent::Completed, this, &AFirstPersonCCharacter::DoJumpEnd);

// Jump执行函数
void AFirstPersonCCharacter::DoJumpStart() { Jump(); }
void AFirstPersonCCharacter::DoJumpEnd() { StopJumping(); }

// Move输入绑定
EnhancedInputComponent->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AFirstPersonCCharacter::MoveInput);

// Move执行函数
void AFirstPersonCCharacter::MoveInput(const FInputActionValue& Value) {
    FVector2D MovementVector = Value.Get<FVector2D>();
    DoMove(MovementVector.X, MovementVector.Y);  // X→Right, Y→Forward
}

void AFirstPersonCCharacter::DoMove(float Right, float Forward) {
    AddMovementInput(GetActorRightVector(), Right);
    AddMovementInput(GetActorForwardVector(), Forward);
}
```

**Expected验证模式：**
- TEST-02: Jump执行流程 — IA_Jump(Started) → DoJumpStart → Jump
- TEST-02: Jump结束流程 — IA_Jump(Completed) → DoJumpEnd → StopJumping
- TEST-03: 数据流 — ActionValue_X → Right参数, ActionValue_Y → Forward参数

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Expected数据权威参考（C++源码）
- `E:/Develop/lib/UnrealEngine/Samples/FirstPersonC/Source/FirstPersonC/FirstPersonCCharacter.h` — 函数声明（DoJumpStart/DoJumpEnd/DoMove）
- `E:/Develop/lib/UnrealEngine/Samples/FirstPersonC/Source/FirstPersonC/FirstPersonCCharacter.cpp` — 函数实现（Jump → StopJumping调用链）

### 项目规范文档
- `.planning/REQUIREMENTS.md` — v4.0需求定义（TEST-01~04规范）
- `.planning/ROADMAP.md` — Phase 21目标和Success Criteria（第126-135行）

### Prior Phase Context
- `.planning/phases/18-Pin序列化解析/18-CONTEXT.md` — Phase 18 Pin解析修正、LinkedTo格式
- `.planning/phases/19-连接关系重建/19-CONTEXT.md` — Phase 19 connections/execution_flows/data_flows构建
- `.planning/phases/20-整合输出/20-CONTEXT.md` — Phase 20 output_version 4.0、blueprint结构重组

### 测试资产
- `E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset` — UE 5.7蓝图测试资产

</canonical_refs>

<code_context>
## Existing Code Insights

### 测试框架和资产
- pytest框架 — 现有17个测试文件，391 tests passed
- FIRST_PERSON_CHARACTER_PATH — 已在test_exportmap_properties.py:43定义
- 测试资产访问 — `get_test_asset_path()` fixture返回BP_FirstPersonCharacter路径

### 已实现可复用
- `parse_uasset()` — 主解析入口，返回ParseResult
- `format_json_full()` — 输出完整JSON结构（Phase 20重组后）
- `build_execution_flows()` — 执行流构建（Phase 19）
- `build_data_flows()` — 数据流构建（Phase 19）

### Integration Points
- 测试入口：`tests/test_phase21_verification.py`（新建）
- 验证调用：parse_uasset(asset_path) → format_json_full(result) → 验证输出字段
- Expected值来源：C++源码函数映射 + 解析结果actual值对照

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Phase 21是v4.0最后一个阶段，完成后里程碑完成。

</deferred>

---

*Phase: 21-验证测试*
*Context gathered: 2026-05-04*