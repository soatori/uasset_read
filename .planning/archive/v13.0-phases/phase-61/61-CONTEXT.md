# Phase 61: Kismet 表达式系统 - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>
## Phase Boundary

构建 Kismet 字节码反编译器的底层数据结构和读取原语：EExprToken 枚举定义、KismetExpression 类族（细粒度子类）、FKismetArchive（FArchive 子类）。交付物为纯数据模型+读取器，不含单元测试。此阶段不涉及字节码→表达式树构建（Phase 62）或表达式树→C++ 翻译（Phase 63）。

</domain>

<decisions>
## Implementation Decisions

### 表达式类族设计
- **D-01:** KismetExpression 采用细粒度子类方案 — 一个基类 + 多个独立 dataclass 子类文件（如 `literal.py`, `variable.py`, `function_call.py`, `binary_op.py`, `control_flow.py`, `cast.py`, `delegate.py`, `container.py` 等），每个子类独立定义。遵循现有 `node_types.py` 模式（dataclass + `from_archive()` 延迟导入）。

### 字节码读取策略
- **D-02:** FKismetArchive 继承 FArchive（位于新 `kismet/archive.py`），复用 FArchive 的 `read_u8/i32/f32/fstring` 等原语，添加 kismet-specific 方法（`read_expression()`, `read_expression_array()`, `xfer_string()`, `xfer_unicode_string()`）。保持与项目现有扩展风格一致。

### CUE4Parse 参考获取
- **D-03:** 优先从 `E:\Develop\lib\CUE4Parse` 本地 CUE4Parse 源码获取 EExprToken 枚举和 KismetExpression 类族定义（`CUE4Parse/UE4/Kismet/EExprToken.cs` + `KismetExpression.cs` + `FKismetArchive.cs`），用 UE 源码（`E:\Develop\lib\UnrealEngine`）验证关键 token 定义。
- **D-04:** EExprToken 枚举约 0x00~0xFF 共 ~110 个有效值 + ECastToken 子枚举。Python 化时使用 `enum.IntEnum` 或 `enum.IntFlag`（base type `byte`）。

### 测试边界
- **D-05:** Phase 61 不包含单元测试。测试从 Phase 62（字节码→表达式树）开始引入。

### Claude's Discretion
- 子类文件的具体分组方式（哪些 token 归入哪些文件）由实现者自行判断，建议按语义类别分组。
- FKismetArchive 的具体方法命名（Python 风格 vs C# 风格）由实现者判断，建议遵循项目现有 FArchive 命名风格（`read_*` 前缀）。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### CUE4Parse 参考（本地）
- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Kismet\EExprToken.cs` — EExprToken 枚举完整定义（~110 个 token 值）+ ECastToken + EScriptInstrumentationType + EBlueprintTextLiteralType
- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Kismet\KismetExpression.cs` — KismetExpression 基类 + 所有子类实现（1500+ 行，含构造函数、JSON 序列化）
- `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Assets\Readers\FKismetArchive.cs` — FKismetArchive 读取器 + ReadExpression() switch 分派 + ReadExpressionArray() + XFERSTRING/XFERUNICODESTRING

### UE 源码参考
- `E:\Develop\lib\UnrealEngine` — UE 5.7 源码树，用于验证 EExprToken 定义和 FKismetArchive 行为

### 项目内部参考
- `src/uasset_read/archive.py` — 现有 FArchive 类，FKismetArchive 的父类
- `src/uasset_read/models/node_types.py` — K2Node 子类模式（dataclass + from_archive），KismetExpression 子类应遵循相同模式
- `src/uasset_read/serializers/graph.py` — K2Node 读取函数模式参考
- `.planning/ROADMAP.md` — v11.0 里程碑路线图，Phase 61-64 依赖关系
- `.planning/STATE.md` — v11.0 里程碑状态，Phase 分解表

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **FArchive** (`archive.py`): 成熟的二进制读取器，支持字节交换、mmap、容错模式。FKismetArchive 直接继承，复用所有 `read_u8/i32/f32/fstring` 等原语。
- **K2Node 类族** (`models/node_types.py`): 5 个 K2Node 子类（K2NodeCallFunction, K2NodeEvent, K2NodeKnot, EdGraphNodeComment, K2NodeEnhancedInputAction, K2NodeFunctionEntry），展示了 dataclass + from_archive 延迟导入模式。
- **CONTROL_FLOW_NODES / START_EVENT_TYPES** (`constants.py`): 已有的控制流节点常量集合，Phase 63+ 翻译器可能参考。
- **CPF_* 位掩码** (`constants.py`): 蓝图变量标志，可能在表达式变量读取中使用。

### Established Patterns
- **dataclass + from_archive**: 所有数据模型使用 `@dataclass` 装饰器，通过 `from_archive()` classmethod 延迟导入序列化函数，避免循环依赖。
- **序列化器解耦**: 数据模型（models/）与序列化逻辑（serializers/）分离，D-06 决策。
- **match/case 类型分派**: class_name 字段用于 match/case 分派，KismetExpression 的 read_expression() 也应采用类似模式。

### Integration Points
- FKismetArchive 的 `read_expression()` 输出 KismetExpression 树，供 Phase 62 的字节码→AST 构建使用。
- Phase 61 创建的 `kismet/` 模块与现有 `archive.py`, `serializers/`, `models/` 并行，不修改已有模块。
- EExprToken 枚举需映射为 Python `enum.IntEnum`（base=byte），与 UE 的 `enum class EExprToken : uint8` 对齐。

</code_context>

<specifics>
## Specific Ideas

用户明确要求：
- CUE4Parse 参考优先使用本地 `E:\Develop\lib\CUE4Parse`（已确认存在且包含完整 Kismet 文件）
- 其次使用 `E:\Develop\lib\CUE4Parse` 而非在线 GitHub
- 最终用 UE 源码验证

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 61-Kismet 表达式系统*
*Context gathered: 2026-05-19*
