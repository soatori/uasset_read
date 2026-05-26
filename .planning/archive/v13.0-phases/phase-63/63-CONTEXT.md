# Phase 63: 表达式树 → C++ 伪代码 - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

将 Phase 62 产出的 `list[KismetExpression]` 翻译为可读的 C++ 伪代码。交付三个核心能力：(1) 每个表达式类型的 `line_cpp()` 方法 — 单行字符串输出，(2) `to_function_body()` — 组装完整函数体（带缩进、结构化控制流），(3) MathFunctionCleaner — 将 `UKismetMathLibrary::Add_IntInt(a, b)` 美化为 `a + b`。

此阶段不涉及 Phase 64 的 pipeline 集成或端到端 golden-path 测试。

</domain>

<decisions>
## Implementation Decisions

### 输出格式
- **D-01:** 同时提供两种输出 API — `line_cpp()` (单个表达式的单行 C++ 字符串) 和 `to_function_body()` (完整函数体，带缩进、分号、花括号)。满足不同使用场景：快速行级查看 vs 完整函数还原。

### 控制流恢复
- **D-02:** 双路径控制流还原 — `line_cpp()` 保留 `goto Label_X` 格式（简单可靠，与 CUE4Parse 对齐）；`to_function_body()` 尝试结构化还原为 `if/for/while` 块结构（识别 Push/Pop/JumpIfNot 模式，构建结构化 AST，消除 goto）。
- **D-03:** 结构化算法不需要完美 — 优先处理常见模式（if/else、for 循环、while 循环），无法识别时回退到 goto。不阻塞在边缘情况。

### MathFunctionCleaner
- **D-04:** MathFunctionCleaner 在翻译时内联执行 — 在 `EX_FinalFunction`/`EX_CallMath` 的 `line_cpp()` 方法内部调用，与 CUE4Parse `GetLineExpression` 内调用 `MathFunctionCleaner` 的方式一致。不做独立后处理。
- **D-05:** MathFunctionCleaner 覆盖范围对齐 CUE4Parse：`KismetMathLibrary`、`KismetStringLibrary`、`KismetSystemLibrary`、`KismetArrayLibrary`、`BlueprintMapLibrary`、`BlueprintSetLibrary` 及各类库的函数映射。

### 类型映射
- **D-06:** 变量类型混合策略 — 优先从上游 blueprint 元数据（BlueprintVariable、函数签名中的参数类型）推断，获取不到时回退 `auto`。需要维护一个类型注册表（`TypeRegistry`），在翻译开始时从 blueprint 信息初始化。
- **D-07:** 类型注册表接口：`register_variable(name, type)` + `lookup(name) -> str | None`。初始化为空时所有变量用 `auto`。

### 继承 Phase 62 决策
- 字节码提取使用 FArchive 二进制导航，非 PropertyTag 解析
- USTRUCT_TYPES = ["Function", "UFunction", "K2Node_FunctionEntry", "K2Node_FunctionResult"]
- 容错模式：连续 10 次未知 token 终止

### Claude's Discretion
- 结构化控制流算法的具体实现方式（递归下降 vs 工作列表）由 planner 自行判断
- 类型注册表的具体数据结构和填充策略由实现者自行判断

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### CUE4Parse 参考（本地）
- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Kismet\KismetExpression.cs` — KismetExpression 基类 + 所有子类实现 + `GetLineExpression` 翻译函数（1500+ 行，核心参考）
- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Objects\UObject\BlueprintDecompiler\BlueprintDecompilerUtils.cs` — MathFunctionCleaner / FinalFunctionCleaner / GetPropertyType / GetLineExpression 完整实现

### UE 源码参考
- `E:\Develop\lib\UnrealEngine` — UE 5.7 源码树，用于验证 KismetMathLibrary 等内置函数命名

### 项目内部参考
- `src/uasset_read/kismet/expressions/__init__.py` — 所有表达式类 + EXPR_CLASS_MAP
- `src/uasset_read/kismet/archive.py` — FKismetArchive（字节码读取器）
- `src/uasset_read/kismet/tokens.py` — EExprToken + ECastToken 枚举
- `src/uasset_read/kismet/property_pointer.py` — FKismetPropertyPointer + FFieldPath
- `src/uasset_read/blueprint/core.py` — Blueprint 变量/函数元数据提取（类型推断来源）
- `src/uasset_read/blueprint/variables.py` — BlueprintVariable 数据结构
- `.planning/ROADMAP.md` — v11.0 路线图，Phase 61-64 依赖关系
- `.planning/phases/phase-61/61-CONTEXT.md` — Phase 61 决策（表达式类族设计、字节码读取策略）
- `.planning/phases/phase-62/PLAN.md` — Phase 62 计划（字节码提取 + 表达式列表输出）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **EXPR_CLASS_MAP** (`kismet/expressions/__init__.py`): 90+ 个 KismetExpression 子类已定义，每个都有 `from_archive()` 和 `to_dict()`，Phase 63 需为每个类添加 `line_cpp()` 方法
- **BlueprintMetadata/BlueprintVariable** (`blueprint/core.py`): 提供变量名和类型信息，可作为类型注册表的初始数据来源
- **CPF_* 标志** (`constants.py`): 变量属性标志，可用于判断变量是否为 out/ref 参数
- **K2Node 类族** (`models/node_types.py`): 已有的节点类型模式可参考

### Established Patterns
- **dataclass + from_archive**: 所有数据模型使用 `@dataclass`，Phase 63 不修改现有表达式类结构，而是添加 `line_cpp(self, type_registry=None) -> str` 方法
- **match/case 分派**: Phase 61/62 大量使用 match/case，Phase 63 的翻译器也可采用类似模式
- **零运行时依赖**: Python 3.10+，不引入新依赖

### Integration Points
- `line_cpp()` 方法添加到每个 KismetExpression 子类中（或统一的 `KismetTranslator` 类）
- 类型注册表从 blueprint/core.py 的变量提取结果初始化
- 输出通过 `to_function_body()` 组装为完整字符串，供 Phase 64 的 pipeline 集成使用

</code_context>

<specifics>
## Specific Ideas

用户明确要求同时提供两种 API（line_cpp + to_function_body）和控制流双路径（goto + 结构化），体现对灵活性的重视。

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 63-表达式树 → C++ 伪代码*
*Context gathered: 2026-05-20*
