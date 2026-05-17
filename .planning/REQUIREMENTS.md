# Requirements: uasset_read v9.0

**Defined:** 2026-05-17
**Core Value:** 从蓝图函数图中提取完整函数调用链，使 JSON 输出可翻译为等价的 C++ 函数实现

## v9.0 Requirements

### 函数图识别

- [ ] **FUNC-01**: 能区分 EventGraph 和 Function Graph（函数图 vs 事件图）
- [ ] **FUNC-02**: 能识别 FunctionEntry 节点作为函数入口

### 函数内执行流

- [ ] **FLOW-01**: 能从 FunctionEntry 开始按 exec 连线追踪函数内调用顺序
- [ ] **FLOW-02**: 能识别 CallFunction 节点的函数名、参数名+类型+连接来源
- [ ] **FLOW-03**: 能区分 impure 函数（有执行流）和 pure 函数（纯数据流，无执行流）

### 数据流追踪

- [ ] **DATA-01**: 能追踪数据流从纯函数返回值 → 调用节点输入参数
- [ ] **DATA-02**: 能处理 Knot 节点的数据传递（中继连接）
- [ ] **DATA-03**: 能处理 SubPin 展开的结构体字段级数据流

### 输出增强

- [ ] **OUT-01**: JSON 输出中包含 function_graphs 数组（每个函数的调用链）
- [ ] **OUT-02**: 调用链包含节点顺序、函数名、参数值来源
- [ ] **OUT-03**: 现有 EventGraph 输出格式不变（向后兼容）

### 测试

- [ ] **TEST-01**: BP_FirstPersonCharacter 的 Move 函数调用链正确输出
- [ ] **TEST-02**: Aim 函数调用链正确输出
- [ ] **TEST-03**: Jump/StopJumping 调用链正确输出
- [ ] **TEST-04**: 纯函数（GetActorForwardVector 等）识别为数据提供者

## v2 Requirements

### 变量追踪

- **VAR-01**: 识别 Get/Set Variable 节点，追踪局部变量声明和修改
- **VAR-02**: 推断局部变量类型

### 控制流

- **CTRL-01**: 识别 Branch/DoOnce 等控制流节点，生成 if/while 结构
- **CTRL-02**: 识别 MultiGate/Sequence 节点

## Out of Scope

| Feature | Reason |
|---------|--------|
| C++ 代码生成 | 目标是可读的调用链数据，不是代码生成 |
| 蓝图字节码反编译 | 超出当前解析范围 |
| Cooked 资产解析 | 不含图数据 |
| 修改 .uasset | 只读工具 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FUNC-01 | Phase 52 | Pending |
| FUNC-02 | Phase 52 | Pending |
| FLOW-01 | Phase 53 | Pending |
| FLOW-02 | Phase 53 | Pending |
| FLOW-03 | Phase 53 | Pending |
| DATA-01 | Phase 54 | Pending |
| DATA-02 | Phase 54 | Pending |
| DATA-03 | Phase 54 | Pending |
| OUT-01 | Phase 55 | Pending |
| OUT-02 | Phase 55 | Pending |
| OUT-03 | Phase 55 | Pending |
| TEST-01 | Phase 53/54 | Pending |
| TEST-02 | Phase 53/54 | Pending |
| TEST-03 | Phase 53/54 | Pending |
| TEST-04 | Phase 53/54 | Pending |

**Coverage:**
- v9.0 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-17*
*Last updated: 2026-05-17 after v9.0 milestone start*
