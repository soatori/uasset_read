# Phase 60: 验证与测试 — PLAN.md

**Goal**: 基于真实蓝图资产（BP_FirstPersonCharacter）验证端到端 C++ 参考输出的正确性

**Requirements**: TEST-01 (golden-path 集成测试), TEST-02 (Move/Aim 函数匹配), TEST-03 (Jump/StopJumping 事件调用链)

**Depends on**: Phase 58 (函数体逻辑翻译), Phase 59 (组件初始化代码)

---

## Context Summary

Phase 60 是 v10.0 的收官阶段，验证 Phase 56-59 所有模块协同工作。核心验证目标：

- **Move 函数**: `K2Node_FunctionEntry_0` → `K2Node_CallFunction_7445` (GetActorRightVector + AddMovementInput) → `K2Node_CallFunction_7346` (GetActorForwardVector + AddMovementInput)
  - 期望 C++ 输出: `AddMovementInput(GetActorRightVector(), LeftRight); AddMovementInput(GetActorForwardVector(), ForwardBackward);`

- **Aim 函数**: `K2Node_CallFunction_11` (Aim, 参数 Yaw:float/Pitch:double) + EnhancedInputAction 节点
  - 期望 C++ 输出: `if (GetController()) { AddControllerYawInput(Yaw); AddControllerPitchInput(Pitch); }`

- **Jump/StopJumping**: `K2Node_CallFunction_1193` (Jump) + `K2Node_CallFunction_9386` (StopJumping) + `K2Node_EnhancedInputAction_5`
  - 期望 C++ 输出: `Super::Jump();` / `Super::StopJumping();`

**现有代码**: `cpp_gen/` 模块 13 个文件已完成，包含类型映射、骨架提取、函数体提取/格式化、构造函数生成等。

**测试模式**: 参考 `tests/test_cpp_skeleton_e2e.py`（mock + 真实 .uasset 双模式）和 `tests/fixtures/data_flow_fixture.py`（fixture 设计）。

**决策记录** (60-CONTEXT.md):
- D-60-01: pytest 集成测试
- D-60-02: BP_FirstPersonCharacter 作为测试数据源
- D-60-03: 逐行比对精度
- D-60-04: 只覆盖核心函数 (Move/Aim/Jump)
- D-60-05: 单独测试文件 `test_phase60_verification.py`
- D-60-06: `scope="module"` fixture 预加载
- D-60-07: 功能描述式测试命名
- D-60-08: 失败输出详细 diff
- D-60-09: 全部通过
- D-60-10: 中间 IR 可见

---

## Task Breakdown

### Task 1: 测试基础设施 — Fixture + 预加载管道

**输出**: `tests/fixtures/phase60_verification_fixture.py` + `tests/conftest.py` 注册

**内容**:
- 创建 `@pytest.fixture(scope="module")` 加载 BP_FirstPersonCharacter.uasset
- 通过 `parse_uasset_with_linker()` 获取完整蓝图数据
- 提取 function_graphs JSON 输出（Phase 55 输出）
- 缓存解析结果供所有测试共享
- 路径: `UASSET_DIR = Path(r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson")`
- 自动跳过: 文件不存在时 `pytest.skip()`

**验证标准**: fixture 成功加载并缓存 JSON，不抛出异常

---

### Task 2: Golden-Path 集成测试 (TEST-01)

**输出**: `tests/test_phase60_verification.py` 中的 `TestGoldenPathVerification` 类

**内容**:
- `test_end_to_end_json_to_cpp_mapping()`: 验证端到端管道完整运行
  - 从 `.uasset` → `parse_uasset_with_linker()` → 提取 function_graphs → C++ 格式化
  - 验证输出包含所有三个核心函数的 C++ 代码片段
- `test_output_contains_move_function()`: 输出中包含 Move 相关 C++ 语句
- `test_output_contains_aim_function()`: 输出中包含 Aim 相关 C++ 语句
- `test_output_contains_jump_functions()`: 输出中包含 Jump/StopJumping 相关 C++ 语句

**验证标准**: 4 个测试全部通过，输出中包含 Move/Aim/Jump 的 C++ 代码

---

### Task 3: Move/Aim 函数逐行匹配测试 (TEST-02)

**输出**: `tests/test_phase60_verification.py` 中的 `TestMoveAimFunctionMatching` 类

**内容**:

**Move 函数验证** (`test_move_function_body_matches_cpp_reference`):
- 从 function_graphs 中提取 Move 函数图 (`K2Node_FunctionEntry_0` / "Move")
- 通过 `CppFunctionBodyExtractor` 提取执行流
- 通过 `CppFunctionBodyFormatter` 格式化为 C++ 文本
- 与期望输出逐行比对:
  ```cpp
  void AFirstPersonCCharacter::Move(double LeftRight, double ForwardBackward)
  {
      AddMovementInput(GetActorRightVector(), LeftRight);
      AddMovementInput(GetActorForwardVector(), ForwardBackward);
  }
  ```
- 使用 `difflib.unified_diff` 输出详细差异

**Aim 函数验证** (`test_aim_function_body_matches_cpp_reference`):
- 从 function_graphs 中提取 Aim 函数（通过 `K2Node_CallFunction_11` 或函数名匹配）
- 格式化后与期望输出比对:
  ```cpp
  void AFirstPersonCCharacter::Aim(float Yaw, double Pitch)
  {
      if (GetController())
      {
          AddControllerYawInput(Yaw);
          AddControllerPitchInput(Pitch);
      }
  }
  ```

**中间 IR 调试输出**: 测试失败时打印 `CppMethodIR` 和 `CppStatementIR` 内容

**验证标准**: 2 个测试全部通过，生成 C++ 与参考实现逐行一致

---

### Task 4: Jump/StopJumping 事件调用链测试 (TEST-03)

**输出**: `tests/test_phase60_verification.py` 中的 `TestJumpEventChain` 类

**内容**:

**Jump 事件链** (`test_jump_event_chain_translates_to_super_call`):
- 从 function_graphs 中追踪 Jump 事件: `K2Node_EnhancedInputAction_5.Started` → `K2Node_CallFunction_1193` (Jump)
- 验证 `FunctionReference.MemberName == "Jump"` 且 `bSelfContext == True`
- 格式化后验证输出包含 `Super::Jump();`

**StopJumping 事件链** (`test_stop_jumping_event_chain_translates_to_super_call`):
- 追踪 StopJumping 事件: `K2Node_EnhancedInputAction_5.Completed` → `K2Node_CallFunction_9386` (StopJumping)
- 验证 `FunctionReference.MemberName == "StopJumping"` 且 `bSelfContext == True`
- 格式化后验证输出包含 `Super::StopJumping();`

**Touch 事件备用路径** (`test_touch_jump_fallback_event`):
- 验证 `K2Node_Event_4` (Touch Jump Start) → `K2Node_CallFunction_1193` (Jump) 的备用事件路径
- 确保事件驱动的函数调用链不遗漏

**验证标准**: 3 个测试全部通过

---

### Task 5: 失败诊断与修复循环

**输出**: 测试通过或失败诊断报告

**内容**:
- 运行 `pytest tests/test_phase60_verification.py -v`
- 如果任何测试失败:
  - 检查 difflib 输出的实际 vs 期望差异
  - 定位是提取器 (`CppFunctionBodyExtractor`) 还是格式化器 (`CppFunctionBodyFormatter`) 的问题
  - 修复后重新运行
- 如果测试通过: 记录测试结果，更新 REQUIREMENTS.md 和 ROADMAP.md

**验证标准**: 所有测试通过或明确定位到上游 Phase 的 bug

---

## Execution Strategy

**Wave 1** (Task 1): 创建 fixture 基础设施 — 可并行
**Wave 2** (Tasks 2, 3, 4): 编写三个测试类 — 可并行（依赖 Task 1 的 fixture）
**Wave 3** (Task 5): 运行测试并修复 — 串行

**单 agent 执行**: 由于测试编写高度关联（共享 fixture、相同的断言模式），由一个 agent 顺序执行比并行更高效。

---

## Verification Loop

1. 运行 `pytest tests/test_phase60_verification.py -v --tb=long`
2. 检查所有测试通过
3. 验证 `pytest` 收集到至少 9 个测试（4 + 2 + 3 = 9）
4. 更新 `REQUIREMENTS.md` 中 TEST-01/02/03 状态为 `Done`
5. 更新 `ROADMAP.md` Phase 60 状态

**成功标准**:
- 全部 9+ 测试通过
- REQUIREMENTS.md 中 TEST-01/02/03 标记为 Done
- 无遗留失败
