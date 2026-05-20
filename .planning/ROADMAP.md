# 路线图

## 里程碑

| 版本 | 范围 | 日期 | 状态 |
|------|------|------|------|
| v1.0–v6.0 | MVP → 模块化重构 | 2026-04-28 ~ 05-13 | 已归档 |
| v7.0 | UE FLinkerLoad 对象图重建 | 2026-05-14 | 已归档 |
| v8.0 | BP-to-CPP JSON 可翻译性 (P47-51) | 2026-05-17 | 已归档 |
| v9.0 | 函数调用链解析 (P52-55) | 2026-05-17 | 已归档 |
| v10.0 | Blueprint-to-C++ 代码生成参考 (P56-60) | 2026-05-18 | [已归档](milestones/v10.0-ROADMAP.md) |
| **v11.0** | **Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线 (P61-66)** | 计划中 | **活跃** |
| **v12.0** | **N2C 中间格式 + 节点分类体系 + 处理器架构 (P67-70)** | 计划中 | 待启动 |
| **v13.0+** | **可选增强：多语言 / 参考注入 / Knot 追踪 / 深度控制** | 待定 | 讨论中 |

历史详情：`.planning/archive/`

## v11.0 — Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线 (PLANNED)

**参考设计:** CUE4Parse — KismetExpression / FKismetArchive / BlueprintDecompilerUtils
**差距分析:** `.planning/phases/phase-64/64-GAP-REPORT.md`

- [x] Phase 61: Kismet 表达式系统 — EExprToken + KismetExpression 类族 + FKismetArchive (4 waves)
- [x] Phase 62: 字节码 → 表达式树 — ScriptBytecode → KismetExpression AST (1 plan, 6 tasks)
- [x] Phase 63: 表达式树 → C++ 伪代码 — AST 翻译 + 控制流恢复 + MathFunctionCleaner (1 plan, 131 tests)
- [x] Phase 64: Kismet 集成验证 — pipeline 集成 + 端到端 golden-path 测试 (64-01/02) ✅ 2026-05-20
- [x] Phase 65: 图解析器修复 — FMemberReference + Pin 连接 + Struct 映射 + 函数签名 (2 plans) ✅ 2026-05-20
- ⏭️ Phase 66: Agent 翻译管线 — ~~BP 节点 JSON → C++ 代码生成~~ → 目标合并至 v12.0 中间格式

**依赖:** 61 → 62 → 63 → 64; 65 → 67; 66 ⏭️ 跳过（目标合并至 v12.0）

Plans:
- [x] 64-01-PLAN.md — KismetDecompiledResult + decompile_uasset() pipeline ✅
- [x] 64-02-PLAN.md — _post_process integration + golden file tests ✅
- [x] 65-01-PLAN.md — FMemberReference + Pin 连接修复 (Wave 1: Task 1+2+3) ✅
- [x] 65-02-PLAN.md — Struct 映射 + 函数签名修复 (Wave 2: Task 4+5+6) ✅
- [ ] 66-01-PLAN.md — AgentTranslationPipeline integration (Wave 1) 📋
- [ ] 66-02-PLAN.md — CppFileWriter output formatter (Wave 1) 📋
- [ ] 66-03-PLAN.md — Golden file integration test (Wave 2) 📋

## v12.0 — N2C 中间格式 + 节点分类体系 + 处理器架构 (NEXT)

**Phase 66 已跳过。** 原始"Agent 翻译管线 C++ 生成"目标调整为"提供 Agent 可理解的中间格式输出"，由本里程碑的 N2CStruct 中间格式直接实现。

**参考设计:** NodeToCode (protospatial) — `N2CNodeTypeRegistry` / `N2CNodeProcessor` 模式 / `N2CStruct` JSON Schema / 执行流链式表达

**目标:** 将 NodeToCode 的核心架构模式移植到 Python 独立解析器，将 graph.py 输出转化为 Agent 可理解的结构化 JSON。

### Phase 67: N2CNodeTypeRegistry — K2Node 语义类型注册表

**目标:** 建立完整的 K2Node 类 → 语义类型映射表，覆盖 UE 引擎全部 100+ 种 K2Node。

| K2Node 类别 | 示例类型 | 语义类型枚举值 |
|-------------|----------|--------------|
| Function Calls | CallFunction, CallArrayFunction, CallDelegate | `CallFunction`, `CallArrayFunction`, `CallDelegate` |
| Variables | VariableGet, VariableSet, LocalVariable | `VariableGet`, `VariableSet`, `LocalVariable` |
| Events | Event, CustomEvent, ComponentBoundEvent | `Event`, `CustomEvent`, `ComponentBoundEvent` |
| Flow Control | IfThenElse, ExecutionSequence, MultiGate | `Branch`, `Sequence`, `MultiGate` |
| Switches | SwitchInteger, SwitchString, SwitchEnum | `SwitchInt`, `SwitchString`, `SwitchEnum` |
| Structs | MakeStruct, BreakStruct, StructMemberGet | `MakeStruct`, `BreakStruct`, `StructMemberGet` |
| Containers | MakeArray, MakeMap, MakeSet | `MakeArray`, `MakeMap`, `MakeSet` |
| Casting | DynamicCast, ClassDynamicCast | `DynamicCast`, `ClassDynamicCast` |
| Delegates | AddDelegate, CreateDelegate, ClearDelegate | `AddDelegate`, `CreateDelegate`, `ClearDelegate` |
| Async/Latent | AsyncAction, BaseAsyncTask | `AsyncAction`, `BaseAsyncTask` |
| Math/Logic | MathExpression, EnumLiteral, BitmaskLiteral | `MathExpression`, `EnumLiteral`, `BitmaskLiteral` |
| Misc | SpawnActor, Timeline, FormatText, GetSubsystem | `SpawnActor`, `Timeline`, `FormatText`, `GetSubsystem` |

**实现方式:**
- 注册表类 `N2CNodeTypeRegistry`（单例），支持类名映射 + 继承回退
- 语义类型枚举 `N2CNodeType`（对应 NodeToCode 的 `EN2CNodeType`）
- 在 graph.py 的节点解析中使用注册表替代 switch/case

**来源:** `N2CNodeTypeRegistry.cpp` — 1025 行，100+ 种类型映射，继承回退机制

### Phase 68: 节点处理器架构 — 每个语义类型专门的 Processor

**目标:** 将节点属性提取逻辑从统一的 switch/case 拆分为独立的 Processor 类。

**现有 switch/case 问题:** 随节点类型增长而膨胀，难以测试和维护。

**Processor 模式:**

| Processor 类 | 职责 | 对应 NodeToCode 实现 |
|-------------|------|---------------------|
| `N2CFunctionCallProcessor` | 提取函数名、owner 类、latent 标志 | `N2CFunctionCallProcessor.cpp` |
| `N2CEventProcessor` | 提取事件签名、输入/输出参数 | `N2CEventProcessor.cpp` |
| `N2CFlowControlProcessor` | 提取 Branch/Sequence/DoOnce/Loop 控制流参数 | `N2CFlowControlProcessor.cpp` |
| `N2CVariableProcessor` | 提取变量名、作用域、默认值 | （类似模式） |
| `N2CStructProcessor` | 提取 Struct Make/Break 的类型信息 | （类似模式） |
| `N2CContainerProcessor` | 提取 Array/Map/Set 的容器类型信息 | （类似模式） |

**接口设计:**
```python
class N2CNodeProcessor(ABC):
    """节点处理器基类"""

    @abstractmethod
    def process(self, node: K2NodeData, out_def: N2CNodeDefinition) -> None:
        """提取节点特有属性到输出定义"""

    @abstractmethod
    def supported_types(self) -> list[N2CNodeType]:
        """此处理器支持的语义类型列表"""
```

**工厂分发:**
```python
processor = N2CProcessorFactory.get(node_type)
if processor:
    processor.process(node, out_def)
else:
    fallback_process(node, out_def)
```

### Phase 69: N2CStruct JSON Schema — Agent 可理解的结构化输出

**目标:** 设计专有的序列化格式，针对 LLM/Agent 消费优化，减少 60-90% token 用量。

**核心设计原则（来自 NodeToCode 经验）:**
- 短 ID 替代完整 GUID（`"N1"` vs `"4A3B2C1D..."`）
- 执行流链式表达：`"execution": ["N1->N2->N3"]` 而非逐对连接
- 数据流紧凑映射：`"data": {"N1.P2": "N2.P1"}`
- 扁平化 Pin 信息，去除冗余字段
- 结构化输出 Schema 约束 LLM 返回格式

**N2CStruct Schema:**
```json
{
  "version": "1.0.0",
  "metadata": {
    "Name": "BP_FirstPersonCharacter",
    "BlueprintType": "Normal",
    "BlueprintClass": "FirstPersonCharacter"
  },
  "graphs": [{
    "name": "ExecuteUbergraph",
    "graph_type": "EventGraph",
    "nodes": [{
      "id": "N1",
      "type": "CallFunction",
      "name": "Print String",
      "member_parent": "KismetSystemLibrary",
      "member_name": "PrintString",
      "comment": "",
      "pure": false,
      "latent": false,
      "input_pins": [...],
      "output_pins": [...]
    }],
    "flows": {
      "execution": ["N1->N2->N3"],
      "data": {"N1.P2": "N2.P1"}
    }
  }],
  "structs": [],
  "enums": []
}
```

**LLM 输出 Schema（来自 CodeGen_CPP.md prompt）:**
```json
{
  "graphs": [{
    "graph_name": "ExampleGraph",
    "graph_type": "Function",
    "graph_class": "MyCharacter",
    "code": {
      "graphDeclaration": "...",
      "graphImplementation": "...",
      "implementationNotes": "..."
    }
  }]
}
```

**双向序列化:** `to_n2c_json()` / `from_n2c_json()` 确保可逆转换

### Phase 70: 执行流链式表达

**目标:** 将现有的 `execution_flow` 数组（逐对连接）改为 N2C 风格的链式字符串。

**现有格式:**
```json
"execution_flow": [
  {"from": "node_uuid_1", "to": "node_uuid_2"},
  {"from": "node_uuid_2", "to": "node_uuid_3"}
]
```

**N2C 格式:**
```json
"execution": ["N1->N2->N3"]
```

**优势:**
- 完整链路一目了然（人类可读 + LLM 易理解）
- Token 用量减少 40-60%
- 天然表达分支合并（`N1->N2, N1->N3`）
- 与 N2CStruct Schema 兼容

**实现:**
- 从现有的 execution_flow 图数据中通过 DFS/BFS 提取线性链
- 分支点拆分为多条链（Branch: `N1->N2`, `N1->N3`）
- 作为 N2CStruct 输出的一部分，不替代现有格式（向后兼容）

---

## v13.0+ — 可选增强（待定/讨论中）

**参考设计:** NodeToCode 高级功能 — 结构体/枚举自动提取、参考代码注入、多语言输出、遍历深度控制、Knot 节点追踪

> 以下为可选增强，待 v12.0 完成后根据实际需求优先级讨论是否纳入。

### 结构体/枚举提取（N2CStruct / N2CEnum）

从节点中提取使用到的类型定义（结构体成员、枚举值），与 graph 数据一起输出。
- **来源:** NodeToCode 的 `FN2CStruct` / `FN2CEnum` + `ProcessBlueprintStruct()` / `ProcessBlueprintEnum()`
- **价值:** LLM 翻译时能引用完整的类型定义，而非猜测字段
- **当前状态:** `extract_blueprint_variables` 有基础能力，但与图解析分离

### 参考代码注入

允许用户提供现有 `.h`/`.cpp` 文件作为风格参考，LLM 翻译时自动融入 prompt。
- **来源:** NodeToCode 的 `ReferenceSourceFilePaths` + `PrependSourceFilesToUserMessage()`
- **价值:** 保持生成代码与项目编码风格一致
- **实现方式:** 在 AgentTranslationPipeline 的 system prompt 中添加 `<referenceSourceFiles>` 段

### 多语言输出

支持 C++、Python、C#、JavaScript、Swift、伪代码等多种翻译目标语言。
- **来源:** NodeToCode 的 `EN2CCodeLanguage` 枚举 + 各语言专用 prompt（`CodeGen_CPP.md`, `CodeGen_Python.md` 等）
- **价值:** 不同场景不同输出需求（学习用伪代码、生产用 C++）
- **当前状态:** Phase 66 仅计划 C++ 输出

### 遍历深度控制

可配置图遍历深度（最高可配置层），防止深层嵌套导致 token 爆炸。
- **来源:** NodeToCode 的 `CurrentDepth` / `ParentDepth` 追踪
- **价值:** 控制 LLM 输入量，避免超大 Blueprint 翻译失败
- **实现方式:** 在 graph 解析时添加 depth 参数和截断策略

### Knot 节点追踪

追踪穿过 Knot 节点的连接，还原真实的节点间数据流。
- **来源:** NodeToCode 的 `TraceConnectionThroughKnots()`
- **价值:** Blueprint 中 Knot 节点纯粹是视觉辅助，语义上应穿透
- **当前状态:** 未处理，Knot 可能阻断数据流链

---

*Updated: 2026-05-20 (v12.0 P67-70 NEXT, Phase 66 跳过合并至中间格式)*