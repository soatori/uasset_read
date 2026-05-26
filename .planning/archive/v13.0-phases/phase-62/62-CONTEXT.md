# Phase 62: 字节码 → 表达式树 - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

将 ScriptBytecode 字节流反序列化为 KismetExpression 表达式树/列表。入口：从 UStruct（K2Node_FunctionEntry + 事件图节点）的 ScriptBytecode 属性读取字节数组 → FKismetArchive 逐条 read_expression() → 构建完整表达式列表。

Phase 62 交付：字节码→表达式列表（带嵌套子树），控制流 token（JMP/JumpIfNot/Push/Pop）的 CodeOffset 被读取但不在此阶段结构化。控制流结构化留给 Phase 63（表达式树→C++ 翻译阶段）。

**不包含：** 控制流 CFG 构建、C++ 伪代码翻译、端到端 golden-path 测试。

</domain>

<decisions>
## Implementation Decisions

### 字节码入口发现
- **D-01:** ScriptBytecode 从函数图（K2Node_FunctionEntry）和事件图（EventGraph）节点中提取。覆盖两种入口点，确保完整的字节码解析范围。
- **D-02:** ScriptBytecode 的序列化格式参考 CUE4Parse UStruct.cs：头部为 `bytecodeBufferSize` (int) + `serializedScriptSize` (int)，随后是 `byte[]` 数据段。需要先读取两个 int header，再用 serializedScriptSize 长度的字节数组构建 FKismetArchive。

### 控制流结构化
- **D-03:** 采用 CUE4Parse BlueprintDecompilerUtils 的方式——在表达式树遍历阶段处理 JMP/Label，不在 Phase 62 预构建 CFG。Phase 62 负责把字节码读成带嵌套子树的表达式列表，JMP 的 CodeOffset 作为属性存储。控制流结构化（JMP/CMP/POP → if/while/for）留给 Phase 63。

### 表达式树连接策略
- **D-04:** 遵循 CUE4Parse ReadExpressionArray() 模式：循环调用 read_expression() 直到遇到 EX_EndOfScript。每个表达式的 from_archive() 自动递归读取子节点（如 EX_Call 读取参数、EX_Context 读取左右子表达式、EX_JumpIfNot 读取 BooleanExpression）。最终得到 `list[KismetExpression]`。

### 错误处理策略
- **D-05:** FKismetArchive 支持可切换模式：默认严格模式（未知 token 抛 ParseError），可通过构造参数切换为容错模式（跳过未知字节到下一个已知边界继续解析）。与项目现有 FArchive tolerant 模式一致。

### Claude's Discretion
- ScriptBytecode 属性的具体读取路径（从 PropertyTag → PropertyValue → 字节数组提取）由实现者根据 Phase 61 已有的属性解析链路自行判断
- 表达式列表的输出格式（flat list vs 带层级关系的树结构）由实现者判断，建议同时支持两种视图

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### CUE4Parse 参考（本地）
- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Objects\UObject\UStruct.cs` §18-66 — ScriptBytecode 字段定义 + 反序列化逻辑（bytecodeBufferSize + serializedScriptSize header + byte[] 读取）
- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Assets\Readers\FKismetArchive.cs` — FKismetArchive 构造函数（接收 byte[]）+ ReadExpression() switch 分派 + ReadExpressionArray() 循环读取
- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Kismet\KismetExpression.cs` §654-696 — EX_Jump / EX_JumpIfNot 实现（CodeOffset 读取 + 递归子表达式）
- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Objects\UObject\UClass.cs` §108-339 — DecompileBlueprintToPseudo() 反编译入口点

### 项目内部参考
- `src/uasset_read/kismet/archive.py` — Phase 61 实现的 FKismetArchive（read_expression / read_expression_array / xfer_string/unicode）
- `src/uasset_read/kismet/tokens.py` — EExprToken 枚举定义
- `src/uasset_read/kismet/expressions/` — Phase 61 实现的 ~90 个表达式子类
- `src/uasset_read/kismet/__init__.py` — kismet 模块导出符号
- `.planning/phases/phase-61/61-CONTEXT.md` — 上游 Phase 61 决策（表达式类族设计、字节码读取策略）
- `.planning/ROADMAP.md` — v11.0 里程碑路线图，Phase 61-64 依赖关系
- `.planning/STATE.md` — v11.0 里程碑状态

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **FKismetArchive** (`kismet/archive.py`): Phase 61 已实现，提供 read_expression()（单条读取+ EXPR_CLASS_MAP 分派）、read_expression_array()（循环到 end_token）、xfer_string/unicode_string。Phase 62 直接复用。
- **EXPR_CLASS_MAP** (`kismet/expressions/__init__.py`): token → expression class 映射，read_expression() 的核心分派表。
- **PropertyTag + PropertyValue 解析链**: 现有 `parsers/` 模块已支持 TArray<byte> 属性解析，ScriptBytecode 的提取可复用此链路。

### Established Patterns
- **dataclass + from_archive**: 所有数据模型使用 @dataclass 装饰器，通过 from_archive() classmethod 延迟导入序列化逻辑。
- **match/case 类型分派**: 项目中广泛使用 match/case 进行类型分派（如 FKismetArchive.read_expression() 中的 EXPR_CLASS_MAP 查找）。
- **tolerant 模式**: FArchive 已有 `_tolerant` 标志控制容错行为，FKismetArchive 应遵循相同模式。

### Integration Points
- Phase 62 的输出（表达式列表）供 Phase 63 的 AST→C++ 翻译使用
- ScriptBytecode 属性需要从已有的属性解析链路中提取（PropertyTag → PropertyValue → bytes）
- 与 PackageLinker (v7.0) 集成：通过 UObjectInstance 外壳访问节点属性

</code_context>

<specifics>
## Specific Ideas

用户确认：
- 函数图 + 事件图都需要覆盖（不仅限于 K2Node_FunctionEntry）
- 控制流采用 CUE4Parse 的遍历阶段处理方式，不在 Phase 62 做 CFG 结构化
- 错误处理需要可切换模式（严格/容错），与项目现有 FArchive tolerant 模式一致
- ScriptBytecode 的具体序列化格式需要查 CUE4Parse UStruct.cs（两个 int header + byte[]）

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 62-字节码 → 表达式树*
*Context gathered: 2026-05-20*
