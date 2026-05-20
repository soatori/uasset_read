# Phase 64: 集成与验证 - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

将 Phase 61-63 的独立组件（EExprToken 表达式系统 → ScriptBytecode 字节码提取 → KismetExpression AST → C++ 伪代码翻译）串联成端到端 pipeline，并提供 golden-path 端到端测试验证。

**交付两个入口：**
1. `parse_uasset()` / `parse_uasset_with_linker()` 管线内嵌 — 解析 Blueprint 时自动触发 Kismet 反编译，结果写入 `ParseResult.decompiled_functions`
2. 独立 `decompile_uasset(path)` 函数 — 专门用于 Kismet 反编译，不修改现有 parse_uasset() 行为

**输出格式：** 结构化 JSON（函数签名、参数、局部变量列表） + C++ 伪代码字符串（多行，带缩进）

**不包含：** CLI 入口（留给后续 phase）、新的解析/翻译能力（Phase 61-63 已覆盖）

</domain>

<decisions>
## Implementation Decisions

### Pipeline 集成点
- **D-01:** 双入口策略 — `parse_uasset()` 管线内嵌（在 blueprint 元数据提取之后触发 kismet 反编译） + 独立 `decompile_uasset(path)` 函数。两者共享底层反编译逻辑，避免代码重复。
- **D-02:** `parse_uasset()` 中 kismet 反编译的触发时机：在 `extract_blueprint_metadata()` 之后、`extract_component_transforms()` 之前。与现有 blueprint 提取链路保持一致。

### 返回结果结构
- **D-03:** `ParseResult` 新增 `decompiled_functions` 字段 — 与 `blueprint_metadata` 同级。类型为 `list[KismetDecompiledResult]`，每个元素包含：`function_name`、`signature`（参数列表+返回值）、`local_variables`（类型注册表快照）、`cpp_code`（C++ 伪代码字符串）、`expressions`（原始表达式列表，用于调试）。
- **D-04:** 新增 `KismetDecompiledResult` dataclass（位于 `kismet/result.py` 或 `models/kismet.py`）— 封装单个函数的反编译结果，支持 `to_dict()` 序列化。

### 测试策略
- **D-05:** Golden file 对比测试 — Phase 64 新编写（不复用 Phase 63 的 131 个 golden file）。覆盖完整的 `.uasset → C++` 端到端链路，包括 pipeline 集成部分。Golden file 存储在 `tests/golden/kismet/` 目录。
- **D-06:** Golden file 覆盖场景：if/else 分支、for 循环、while 循环、函数调用、数学表达式美化、变量类型推断、结构化控制流回退到 goto。

### 输出格式
- **D-07:** 结构化 JSON + C++ 伪代码字符串双输出。JSON 部分（函数签名、参数、局部变量）用于机器消费（下游工具、测试断言）；C++ 字符串用于人类查看和 golden file 对比。
- **D-08:** `decompile_uasset(path)` 返回 `list[KismetDecompiledResult]`，支持 `to_json()` 和 `to_cpp_string()` 两种视图。

### CLI 策略
- **D-09:** Phase 64 不添加 CLI 入口。优先验证核心 API 功能。CLI 入口（如 `--decompile` 标志）留给后续 phase。

### 错误处理
- **D-10:** Kismet 反编译失败时不阻断 parse_uasset() 主管线 — 与现有 blueprint_metadata 提取的 tolerant 模式一致。失败时 `decompiled_functions` 返回空列表，错误信息记录到 `result.status.warnings`。

### Claude's Discretion
- `KismetDecompiledResult` 的具体字段命名和 `to_dict()` 结构由实现者自行判断
- Golden file 的具体命名约定（建议 `{blueprint_name}_{function_name}.cpp`）由实现者判断
- `decompile_uasset()` 的参数设计（是否支持 tolerant 模式、是否返回 linker 结果）由实现者判断

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### CUE4Parse 参考（本地）
- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Objects\UObject\BlueprintDecompiler\BlueprintDecompilerUtils.cs` — DecompileBlueprintToPseudo() 完整反编译流程（入口点→字节码提取→翻译→输出）
- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Objects\UObject\UClass.cs` §108-339 — DecompileBlueprintToPseudo() 反编译入口点

### 项目内部参考
- `src/uasset_read/kismet/__init__.py` — kismet 模块导出符号（Phase 61-63 完整导出）
- `src/uasset_read/kismet/translator.py` — KismetTranslator, MathFunctionCleaner, TypeRegistry
- `src/uasset_read/kismet/body_builder.py` — FunctionBodyBuilder, to_function_body
- `src/uasset_read/kismet/structured_flow.py` — StructuredControlFlow, StructuredBlock
- `src/uasset_read/kismet/bytecode_extractor.py` — extract_bytecode_bytes, parse_bytecode_stream, extract_and_parse
- `src/uasset_read/parse_uasset.py` — 主解析管线，_post_process 函数（集成点参考）
- `src/uasset_read/models/result.py` — ParseResult 数据结构（decompiled_functions 字段添加位置）
- `src/uasset_read/__init__.py` — 公共 API 导出（Phase 63 符号尚未导出，Phase 64 需要补充）
- `.planning/ROADMAP.md` — v11.0 路线图，Phase 61-64 依赖关系
- `.planning/STATE.md` — v11.0 里程碑状态
- `.planning/phases/phase-61/61-CONTEXT.md` — Phase 61 决策（表达式类族设计）
- `.planning/phases/phase-62/62-CONTEXT.md` — Phase 62 决策（字节码提取策略）
- `.planning/phases/phase-63/63-CONTEXT.md` — Phase 63 决策（翻译器设计）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **KismetTranslator** (`kismet/translator.py`): 已实现的 C++ 翻译器，提供 line_cpp() 和类型注册表。Phase 64 直接复用。
- **FunctionBodyBuilder** (`kismet/body_builder.py`): 已实现的函数体组装器，提供 to_function_body()。Phase 64 直接复用。
- **StructuredControlFlow** (`kismet/structured_flow.py`): 已实现的控制流结构化。Phase 64 直接复用。
- **bytecode_extractor** (`kismet/bytecode_extractor.py`): extract_and_parse() 函数提供完整的字节码→表达式列表转换。Phase 64 直接复用。
- **ParseResult** (`models/result.py`): 现有结果数据结构，decompiled_functions 字段需要添加。

### Established Patterns
- **parse_uasset 后处理模式**: `_post_process()` 函数中串联 blueprint 元数据提取、图提取等步骤。Kismet 反编译应遵循相同模式。
- **tolerant 模式**: FArchive 和 parse_uasset 已有 tolerant 标志控制容错行为。Kismet 反编译失败不应阻断主管线。
- **dataclass + to_dict()**: 所有数据模型使用 @dataclass，提供 to_dict() 序列化。KismetDecompiledResult 应遵循相同模式。
- **零运行时依赖**: Python 3.10+，不引入新依赖。

### Integration Points
- `parse_uasset()` 的 `_post_process()` 函数中新增 kismet 反编译调用
- `ParseResult` dataclass 新增 `decompiled_functions` 字段
- `__init__.py` 补充 Phase 63 符号导出（KismetTranslator, FunctionBodyBuilder 等）
- 新增 `decompile_uasset()` 独立函数（可在 `parse_uasset.py` 或新建 `kismet/pipeline.py`）
- Golden file 测试需要 `tests/golden/kismet/` 目录

</code_context>

<specifics>
## Specific Ideas

用户明确要求：
- 双入口策略：parse_uasset 内嵌 + 独立 decompile_uasset()
- Golden file 对比测试需要新编写（不复用 Phase 63 的 131 个）
- 输出格式为结构化 JSON + C++ 伪代码字符串
- 暂不添加 CLI 入口
- ParseResult 返回结果字段由 Claude 决定 → 选择 decompiled_functions 字段

</specifics>

<deferred>
## Deferred Ideas

- CLI 入口（`--decompile` 标志或 `uasset-decompile` 子命令）— 留给后续 phase
- Markdown 格式反编译报告 — 用户选择了 JSON + 字符串，Markdown 报告暂不实现

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 64-集成与验证*
*Context gathered: 2026-05-20*
