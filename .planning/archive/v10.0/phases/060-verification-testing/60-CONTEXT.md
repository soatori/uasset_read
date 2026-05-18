# Phase 60: 验证与测试 - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

## Phase Boundary

验证端到端 C++ 生成输出的正确性 — 确保 v10.0 所有模块（Phase 56-59）协同工作，JSON → C++ 输出与真实蓝图资产（BP_FirstPersonCharacter）的 C++ 实现一致。

**Requirements**: TEST-01 (golden-path 集成测试), TEST-02 (Move/Aim 函数匹配), TEST-03 (Jump/StopJumping 事件调用链)

**Depends on**: Phase 58 (函数体逻辑翻译), Phase 59 (组件初始化代码)

## Implementation Decisions

### 验证策略

- **D-60-01: 验证方式** — pytest 集成测试
  - 自动化回归测试，CI 可跑
  - 需要预定义期望输出

- **D-60-02: 测试数据来源** — BP_FirstPersonCharacter
  - 已有 `reference/蓝图节点文本参考.md`
  - 真实资产，覆盖 Move/Aim/Jump

- **D-60-03: 匹配精度标准** — 逐行比对
  - 生成的 C++ 与参考实现完全一致
  - 不允许格式、命名差异

- **D-60-04: 验证范围** — 核心函数
  - 只覆盖 ROADMAP.md 中明确提到的 Move/Aim/Jump
  - 不验证组件初始化细节（Phase 59 已有独立测试）

### 测试组织

- **D-60-05: 测试文件组织** — 单独测试文件 `tests/test_phase60_verification.py`
  - 独立 Phase 60 测试，避免与现有测试混淆

- **D-60-06: Fixture 设计** — 预生成 fixture
  - 预加载 BP_FirstPersonCharacter.uasset 并缓存 JSON 输出
  - 使用 `pytest.fixture(scope="module")` 避免重复解析

- **D-60-07: 测试命名风格** — 功能描述式
  - `test_move_function_body`, `test_jump_event_chain` 等清晰命名
  - 不使用 Requirement ID 或 Phase 标记式

### 失败处理

- **D-60-08: 失败输出** — 详细 diff
  - 输出实际 vs 期望的完整 diff
  - 高亮差异行，方便定位问题

- **D-60-09: 回归要求** — 全部通过
  - 所有测试通过后才可推进 Phase 60 完成
  - 不允许部分通过

- **D-60-10: 调试策略** — 中间 IR 可见
  - 输出中间 IR（CppClassIR/CppMethodIR/CppStatementIR）帮助定位问题
  - pytest 失败时打印 IR 内容

### Claude's Discretion

None — 所有决策由用户明确选择。

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### C++ 生成参考

- `.planning/ROADMAP.md` Phase 60 section — 验证目标与 Success Criteria
- `.planning/phases/058-function-body-translation/58-CONTEXT.md` — 函数体翻译决策（D-58-01 to D-58-06）
- `.planning/phases/059-component-initialization/59-CONTEXT.md` — 组件初始化决策（D-59-01 to D-59-06）

### 测试资产参考

- `reference/蓝图节点文本参考.md` — BP_FirstPersonCharacter 蓝图节点完整数据
  - Move 函数: `K2Node_FunctionEntry_0` + `K2Node_CallFunction_7445/7346/8029/8520`
  - Aim 函数: `K2Node_CallFunction_11` + EnhancedInputAction 节点
  - Jump/StopJumping: `K2Node_CallFunction_1193/9386` + `K2Node_EnhancedInputAction_5`

### 现有测试参考

- `tests/test_cpp_skeleton_e2e.py` — 端到端骨架测试模式
- `tests/test_cpp_gen.py` — C++ 生成测试模式
- `tests/fixtures/data_flow_fixture.py` — fixture 设计参考

## Existing Code Insights

### Reusable Assets

- **cpp_gen 模块** (13 个文件) — 类型映射、骨架提取、函数体、构造函数等
  - `src/uasset_read/cpp_gen/extractors/cpp_function_body_extractor.py` — 函数体提取
  - `src/uasset_read/cpp_gen/formatters/cpp_function_body_formatter.py` — 函数体格式化
  - `src/uasset_read/cpp_gen/cpp_constructor_formatter.py` — 构造函数格式化

- **测试 fixture 模式** — `tests/fixtures/data_flow_fixture.py`
  - 可复用 fixture 设计模式

### Established Patterns

- **pytest fixture scope="module"** — 预加载资产避免重复解析
- **逐行比对** — 使用 `assert actual == expected` 或 difflib

### Integration Points

- **CLI 入口** — `uasset-read --cpp-skeleton file.uasset` 获取 JSON IR
- **parse_uasset_with_linker** — 获取完整蓝图数据（含 function_graphs）

## Specific Ideas

参考实现（来自 Phase 59 CONTEXT.md 的 C++ 参考代码）：

```cpp
// Move 函数期望输出
void AFirstPersonCCharacter::Move(double LeftRight, double ForwardBackward)
{
    AddMovementInput(GetActorRightVector(), LeftRight);
    AddMovementInput(GetActorForwardVector(), ForwardBackward);
}

// Aim 函数期望输出
void AFirstPersonCCharacter::Aim(float Yaw, double Pitch)
{
    if (GetController())
    {
        AddControllerYawInput(Yaw);
        AddControllerPitchInput(Pitch);
    }
}

// Jump/StopJumping 期望输出
void AFirstPersonCCharacter::Jump()
{
    Super::Jump();
}

void AFirstPersonCCharacter::StopJumping()
{
    Super::StopJumping();
}
```

## Deferred Ideas

None — 讨论保持在 phase scope 内。

---

*Phase: 60-验证与测试*
*Context gathered: 2026-05-18*