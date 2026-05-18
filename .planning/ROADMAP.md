# 路线图

## 里程碑

- ✅ **v7.0** — Phases 41-46 + 44a-c (shipped 2026-05-14)
- ✅ **v8.0** — Phases 47-51 (shipped 2026-05-17)
- ✅ **v9.0** — Phases 52-55 (函数调用链解析, shipped 2026-05-17)
- 🔄 **v10.0** — Phases 56-60 (Blueprint-to-C++ 代码生成参考)

## Phases

<details>
<summary>✅ v7.0 — UE FLinkerLoad 对象图重建 (SHIPPED 2026-05-14)</summary>

- [x] Phase 41: link/ 模块 (1/1 plans)
- [x] Phase 42: 集成入口 (1/1 plans)
- [x] Phase 43: PackageIndex (1/1 plans)
- [x] Phase 44: 模型增强 (1/1 plans)
- [x] Phase 44a: 移除旧版本兼容代码
- [x] Phase 44b: 替换直接字节读取
- [x] Phase 44c: 清理测试工具
- [x] Phase 45: 图序列化 linker 变体
- [x] Phase 46: 测试验证 (432 passed, 0 new failures)

详见 `.planning/milestones/v7.0-ROADMAP.md`
</details>

<details>
<summary>✅ v8.0 — BP-to-CPP 翻译能力 (SHIPPED 2026-05-17)</summary>

- [x] Phase 47: Pin LinkedTo 修复 (linked_to_raw 0/30→16/43 pins)
- [x] Phase 48: 组件属性递归解析 (components[] 含数值属性)
- [x] Phase 49: 函数调用引脚解析 (K2Node_CallFunction parameters 数组)
- [x] Phase 50: EnhancedInput 语义增强 (trigger_events 从 pins 提取)
- [x] Phase 51: 二进制输出清理 (ZERO \x00 escapes in JSON)

详见 `.planning/milestones/v8.0-ROADMAP.md`
</details>

<details>
<summary>✅ v9.0 — 函数调用链解析 (SHIPPED 2026-05-17)</summary>

- [x] Phase 52: 函数图节点解析 (2 plans) (completed 2026-05-17)
  - [x] 52-01-PLAN.md — K2NodeFunctionEntry 数据模型 + 序列化支持 + function_reference 修复
  - [x] 52-02-PLAN.md — START_EVENT_TYPES 扩展 + 执行流集成 + is_function_graph 判断
- [x] Phase 53: 函数内执行流追踪 (FunctionEntry → CallFunction 链) (2/2 plans complete 2026-05-17)
  - [x] 53-01-PLAN.md — _get_start_event_name 前缀统一 + pure function 标记
  - [x] 53-02-PLAN.md — 4 个新测试（FunctionEntry 前缀/执行流/pure/Knot）
- [x] Phase 54: 数据流追踪 (Pure 函数返回值 → 参数输入) (3/3 plans complete 2026-05-17)
  - [x] 54-01-PLAN.md — 测试基础设施（fixture + 6 个测试骨架）
  - [x] 54-02-PLAN.md — 核心追踪函数（DATA_BOUNDARY_NODES + is_boundary_node + _resolve_knot_chain）
  - [x] 54-03-PLAN.md — 数据标注增强（_trace_data_source + _extract_call_function_parameters 增强 + Pure 函数 data_providers）
- [x] Phase 55: JSON 输出增强 (function_graphs 数组) (1/1 plan complete 2026-05-17)
  - [x] 55-PLAN.md — build_function_graphs + output_version 5.0 + CLI flag + 7 tests

详见 `.planning/milestones/v9.0-ROADMAP.md`
</details>

<details>
<summary>v10.0 — Blueprint-to-C++ 代码生成参考 (IN PROGRESS)</summary>

- [x] Phase 56: C++ 类骨架提取 (4/4 waves complete)
  - [x] 56-01-PLAN.md — cpp_type_mapper + cpp_uproperty_mapper + unit tests (类型映射引擎) ✓ completed 2026-05-18
  - [x] 56-02-PLAN.md — extract_cpp_skeleton + cpp_json_ir + skeleton extraction tests (核心骨架提取) ✓ completed 2026-05-18
  - [x] 56-03-PLAN.md — cpp_header_formatter + golden-path e2e test (头文件输出 + 端到端验证) ✓ completed 2026-05-18
  - [x] 56-04 (Wave 4) — CLI integration + real .uasset e2e tests (--cpp-skeleton flag + BP_FirstPersonCharacter validation) ✓ completed 2026-05-18

- [x] Phase 58: 函数体逻辑翻译 (2/2 plans complete)
</details>

---

*Updated: 2026-05-18 (v10.0 Phase 56 complete)*

## Phase Details

### Phase 56: C++ 类骨架提取
**Goal**: 从蓝图 PackageSummary、ExportMap 和组件列表导出完整的 C++ 类声明骨架，包括继承链、组件 UPROPERTY 和变量 UPROPERTY
**Depends on**: Nothing (first phase of v10.0; builds on v9.0 function_graphs output)
**Requirements**: CPP-01, CPP-02, CPP-03
**Success Criteria** (what must be TRUE):
  1. 运行 CLI 后，输出的 C++ 类声明包含完整父类继承链（如 `class AMyCharacter : public ACharacter`），继承链从蓝图 `GeneratedClass` 追溯至引擎基类
  2. 输出中所有蓝图组件均生成了 `UPROPERTY` 声明，包含正确的指针类型、变量名和可见性标记（如 `VisibleAnywhere`, `BlueprintReadOnly`, `Instanced`）
  3. 输出中所有蓝图变量均生成了 `UPROPERTY` 声明，包含正确的 C++ 类型名（如 `FVector`, `float`, `bool`）、默认值和 Blueprint 可见性标记
  4. 生成的 .h 骨架文件可直接作为 C++ 头文件模板使用，无需手动补遗漏的组件或变量声明
**Plans**: 3 plans
Plans:
- [x] 56-01-PLAN.md — cpp_type_mapper + cpp_uproperty_mapper + unit tests (类型映射引擎) ✓
- [x] 56-02-PLAN.md — extract_cpp_skeleton + cpp_json_ir + skeleton extraction tests (核心骨架提取) ✓
- [x] 56-03-PLAN.md — cpp_header_formatter + golden-path e2e test (头文件输出 + 端到端验证) ✓

### Phase 57: 函数签名映射
**Goal**: 从 v9.0 function_graphs 输出提取完整函数签名，生成等价 C++ 函数声明和调用语句
**Depends on**: Phase 56
**Requirements**: FUNC-01, FUNC-02, FUNC-03
**Success Criteria** (what must be TRUE):
  1. 每个蓝图函数图节点输出为完整的 C++ 函数声明，包含函数名、参数名、参数 C++ 类型、返回值类型、`const` 修饰符和参数方向（值传递/引用/`const&`）推断
  2. 函数调用节点（CallFunction/K2Node_CallFunction）输出为等价 C++ 调用语句格式（如 `Super::Jump();` 或 `Target->SomeFunction(Arg1, Arg2)`），包含 `MemberParent` 推导的类名前缀
  3. 每个函数声明包含正确的 `UFUNCTION` 宏及类别说明符（`BlueprintCallable`, `BlueprintPure`, `BlueprintImplementableEvent`），基于函数图元数据自动推断
  4. 开发者能从输出中直接复制函数声明到 .h 文件、函数调用到 .cpp 文件，无需补充签名信息
**Plans**: 5 plans
Plans:
- [ ] 57-01-PLAN.md — CppMethodIR/CppCallParameter/CppCallStatement data models + exports + unit tests
- [ ] 57-02-PLAN.md — extract_cpp_functions(): FunctionEntry/Event → CppMethodIR with UFUNCTION inference
- [ ] 57-03-PLAN.md — extract_cpp_call_statements(): CallFunction → CppCallStatement
- [ ] 57-04-PLAN.md — Extend cpp_header_formatter: method declarations in .h + call statements in .cpp
- [ ] 57-05-PLAN.md — Golden-path integration tests + full test suite verification

### Phase 58: 函数体逻辑翻译
**Goal**: 从 v9.0 执行流和数据流输出生成等价的 C++ 语句序列，覆盖控制流、赋值、内联表达式
**Depends on**: Phase 57
**Requirements**: BODY-01, BODY-02, BODY-03, BODY-04
**Success Criteria** (what must be TRUE):
  1. 执行流（execution pins + then 链）翻译为顺序 C++ 语句序列，节点执行顺序与流追踪结果一致
  2. 数据流（pure function 返回值 -> 参数输入）翻译为 C++ 赋值表达式或内联参数传递，变量名和类型正确映射
  3. 控制流节点（Branch/Sequence/ForEach 等）翻译为等价 C++ `if`/`for`/`do...while` 语句块，条件和循环体完整
  4. Pure 函数调用（如 `GetActorRightVector()`, `Multiply_VectorFloat`）翻译为内联 C++ 表达式（如 `GetActorRightVector() * Scale`），而非中间变量赋值
**Plans**: 2 plans ✓ completed 2026-05-18
Plans:
- [x] 58-01-PLAN.md — CppFunctionBodyExtractor: execution/data flow → CppStatement IR ✓
- [x] 58-02-PLAN.md — CppFunctionBodyFormatter: CppStatement IR → .cpp text ✓

### Phase 59: 组件初始化代码
**Goal**: 从组件层次结构和属性数据生成构造函数中的组件创建和初始化代码
**Depends on**: Phase 56
**Requirements**: COMP-01, COMP-02
**Success Criteria** (what must be TRUE):
  1. 每个蓝图组件生成对应的 `CreateDefaultSubobject<T>()` 调用，包含正确的模板类型参数和组件名称，放置于构造函数内
  2. 组件变换数据（位置/旋转/缩放）翻译为构造函数中的 `SetRelativeLocation()`/`SetRelativeRotation()`/`SetRelativeScale3D()` 调用，使用正确的 `FVector`/`FRotator` 字面量
  3. 组件属性（如 `CameraBoom->TargetArmLength = 400.0f`）翻译为构造函数中的默认值赋值语句，类型后缀正确（`f` 浮点标记等）
**Plans**: TBD

### Phase 60: 验证与测试
**Goal**: 基于真实蓝图资产（BP_FirstPersonCharacter）验证端到端 C++ 参考输出的正确性
**Depends on**: Phase 58, Phase 59
**Requirements**: TEST-01, TEST-02, TEST-03
**Success Criteria** (what must be TRUE):
  1. 存在 golden-path 集成测试（基于 `reference/蓝图节点文本参考.md`），运行 `pytest` 后全部通过，验证端到端 JSON 到 C++ 参考输出的映射
  2. BP_FirstPersonCharacter 的 Move/Aim 函数 JSON 输出经翻译后，生成的 C++ 实现片段与参考实现逐行匹配（函数签名、调用链、赋值语句）
  3. Jump/StopJumping 事件驱动的函数调用链翻译为正确的 C++ 事件处理代码，包含 `Super::Jump()` 调用和状态变更语句
**Plans**: TBD
**UI hint**: yes

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 56. C++ 类骨架提取 | 3/3 plans complete | Completed | 2026-05-18 |
| 57. 函数签名映射 | 5 plans created | Planned | - |
| 58. 函数体逻辑翻译 | 2/2 plans complete | Completed | 2026-05-18 |
| 59. 组件初始化代码 | 0/3 | Not started | - |
| 60. 验证与测试 | 0/3 | Not started | - |
