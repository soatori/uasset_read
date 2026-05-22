# 路线图

## 里程碑

| 版本 | 范围 | 日期 | 状态 |
|------|------|------|------|
| v1.0–v6.0 | MVP → 模块化重构 | 2026-04-28 ~ 05-13 | 已归档 |
| v7.0 | UE FLinkerLoad 对象图重建 | 2026-05-14 | 已归档 |
| v8.0 | BP-to-CPP JSON 可翻译性 (P47-51) | 2026-05-17 | 已归档 |
| v9.0 | 函数调用链解析 (P52-55) | 2026-05-17 | 已归档 |
| v10.0 | Blueprint-to-C++ 代码生成参考 (P56-60) | 2026-05-18 | [已归档](milestones/v10.0-ROADMAP.md) |
| **v11.0** | **Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线 (P61-66)** | 2026-05-20 | [已归档](milestones/v11.0-ROADMAP.md) |
| **v12.0** | **序列化修复 + N2C 中间格式 + 节点分类体系 + 处理器架构 (P67-71)** | 计划中 | 待启动 |
| **v13.0+** | **可选增强：多语言 / 参考注入 / Knot 追踪 / 深度控制** | 待定 | 讨论中 |

历史详情：`.planning/archive/`

## v11.0 — Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线 (✅ 已归档)

详见 [milestones/v11.0-ROADMAP.md](milestones/v11.0-ROADMAP.md)

## v12.0 — 序列化修复 + N2C 中间格式 + 节点分类体系 + 处理器架构 (NEXT)

**参考设计:** NodeToCode (protospatial) — `N2CNodeTypeRegistry` / `N2CNodeProcessor` 模式 / `N2CStruct` JSON Schema / 执行流链式表达
**参考设计:** CUE4Parse — FPropertyTag UE5 格式分支 / FStructFallback 错误恢复 / FString 验证

**目标:** 先修复序列化层问题确保输入数据完整性，再将 NodeToCode 的核心架构模式移植到 Python 独立解析器，将 graph.py 输出转化为 Agent 可理解的结构化 JSON。

### Phase 67: 序列化格式修复 — UE5.4+ PropertyTag 兼容 + FString 健壮性

**目标:** 修复解析 `BP_FirstPersonCharacter.uasset` 等 UE5 蓝图时出现的 6 类错误，确保后续 N2C 格式有干净的输入数据。

**参考:** CUE4Parse 的 `FPropertyTag` 构造函数（line 142-173）和 `FScriptStruct` 结构映射（line 70-425）。

**问题清单（6 项）：**

| # | 错误 | 根因 | 修复策略 |
|---|------|------|----------|
| 1 | **FString 读到二进制数据**（35处） | `null_ratio > 0.3` 启发式过于激进，将合法短字符串（如单字符枚举名）误判为二进制 | 移除启发式检测，改用 CUE4Parse 的 null termination 验证（读取后检查末尾 null 字节） |
| 2 | **LastEditedDocuments: Size 16777216** | 缺少 `PROPERTY_TAG_COMPLETE_TYPE_NAME`（UE5.4+）格式分支，FName 对被误读为 size | 添加 UE5 新格式分支：`FPropertyTypeNameNode` 链式读取替代双 FName |
| 3 | **SCS_Node CategoryName: Cannot read 3328 bytes** | #2 导致的连锁偏移错误 | 修复 #2 后自动修复 |
| 4 | **BodyInstance: Size 524288** | #2 导致的连锁偏移错误 | 修复 #2 后自动修复 |
| 5 | **RelativeLocation: Invalid size -1067974656** | #2 导致的连锁偏移错误 | 修复 #2 后自动修复 |
| 6 | **RelativeRotation 字段错位** | #5 的连锁反应 | 修复 #2 后自动修复 |

**修复内容：**

1. **`serializers/property_tags.py` — `read_property_tag()`**
   - 添加 `summary.is_ue5_4+` 版本检查
   - UE5.4+ 分支：读取 `FPropertyTypeNameNode` 链（`FName + int32 InnerCount`，递归直到 remaining==0）
   - UE5.4+ 分支：读取 `PropertyTagFlags` 字节后解析扩展字段
   - 参考 CUE4Parse `FPropertyTag(FAssetArchive Ar, bool readData)` 构造函数 line 136-233

2. **`archive.py` — `read_fstring()`**
   - 移除 `null_ratio > 0.3` 启发式检测
   - 添加 null termination 验证（UTF-8 检查末尾 `b'\x00'`，UTF-16 检查末尾 `b'\x00\x00'`）
   - 非 null 终止时记录 warning 但仍返回读取结果（tolerant 模式）
   - 参考 CUE4Parse `FArchive.ReadFString()` line 449-507

3. **`parsers/property_types.py` — `parse_struct_property()`**
   - 添加 try/finally 块确保解析失败后 seek 到 `pos + tag.size`
   - 参考 CUE4Parse `FPropertyTag` line 228-231 的 `finally: Ar.Position = finalPos`

**验证：** 重新解析 `BP_FirstPersonCharacter.uasset`，上述 6 类错误清零（或降级为 warning 不影响后续属性读取）。

### Phase 68: N2CNodeTypeRegistry — 126 种 K2Node 语义类型注册表 ✅

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

### Phase 69: 节点处理器架构 — 每个语义类型专门的 Processor

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

### Phase 70: N2CStruct JSON Schema — Agent 可理解的结构化输出

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

### Phase 71: 执行流链式表达

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

*Updated: 2026-05-21 (v12.0 P67-71: 序列化修复 + N2C 中间格式，Phase 编号顺延)*
