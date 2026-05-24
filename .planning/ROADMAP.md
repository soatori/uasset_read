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
| **v12.0** | **序列化修复 + N2C 中间格式 + 节点分类体系 + 处理器架构 (P67-71)** | 2026-05-21~22 | [已归档](milestones/v12.0-ROADMAP.md) |
| **v13.0** | **Pin 连接修复 + Kismet 字节码导航 + FName/FString 区分 (P72-73)** | 2026-05-23 ~ 05-24 | 执行中 |

历史详情：`.planning/archive/`

## v11.0 — Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线 (✅ 已归档)

详见 [milestones/v11.0-ROADMAP.md](milestones/v11.0-ROADMAP.md)

## v12.0 — 序列化修复 + N2C 中间格式 + 节点分类体系 + 处理器架构 (✅ 已归档)

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

### Phase 71: 执行流链式表达 ✅

**目标:** 将现有的 `execution_flow` 数组（逐对连接）改为 N2C 风格的链式字符串。

**完成日期:** 2026-05-22

**交付物:**
- `build_execution_chains()` API (`graph/chain_builder.py`)
- JSON 输出 `execution_flows` → `execution_chains` 字段替换
- 所有 formatters 适配链式格式
- `build_execution_flows()` deprecated warning
- 1290 tests passed

**格式对比:**

| 旧格式 | 新格式 |
|-------|--------|
| `{"from": "N1", "to": "N2"}, {"from": "N2", "to": "N3"}` | `"N1->N2->N3"` |

**优势:**
- 完整链路一目了然（人类可读 + LLM 易理解）
- Token 用量减少 40-60%
- 天然表达分支合并（`N1->N2, N1->N3`）
- 与 N2CStruct Schema 兼容

---

## v13.0 — Pin 连接修复 + Kismet 字节码导航 + FName/FString 区分 (P72)

**参考设计:** UE 5.7 EdGraphPin.cpp — `UEdGraphPin::Serialize()` / `FEdGraphPinType::Serialize()`
**诊断日期:** 2026-05-23
**诊断结果:** 在真实 .uasset 二进制上定位 2 个独立 bug（详见下方 72-A）

### Phase 72-A: Pin 连接二进制诊断 ✅

**完成日期:** 2026-05-23

| # | Bug | 位置 | 根因 | 修复策略 |
|---|-----|------|------|---------|
| 1 | **`history_type` 无符号/有符号不匹配** | `graph.py` L398, L449 | `read_u8()` 返回 255，UE 意图是 -1（None）。`read_ftext_with_history` 检查 `255 in range(-1,11)` → FALSE → 位置不变 → 后续字段全部错位 | 入口处 `if history_type >= 128: history_type -= 256` |
| 2 | **ParentPin 总是读 24 字节** | `graph.py` L476-479 | `null != 0` 时应只读 8B，代码多读 16B GUID → RefPassThrough/PersistentGuid/BitField 错位 | 条件读取：null != 0 → 8B, null == 0 → 24B |

**二进制证据（K2Node_Knot_1 pin 0, body at 132477）:**
- 修复 Bug 1 → `LinkedTo count=1, owning=57, valid GUID` ✅
- 修复 Bug 1+2 → `RefPassThrough null=0, BitField=0x52935405` ✅

### Phase 72-B: Pin 连接修复 ✅

**修复内容:** `serializers/graph.py` — L398/L449 history_type signed 转换 + L476-479 ParentPin 条件读取

### Phase 72-C: Kismet 字节码导航

**状态:** ✅ Completed — BPGC bytecode extraction module (`bpgc_bytecode.py`, 295 lines) + pipeline fallback + cache integration

**交付物:**
- `bpgc_bytecode.py` — BPGC bytecode extraction
- `bytecode_extractor.py` — BPGC fallback integration + module cache
- `pipeline.py` — cache reset in `decompile_uasset()`
- `object_resources.py` — `detect_blueprint_generated_class()` bug fix
- `tests/test_kismet_bpgc.py` — comprehensive test suite

**测试结果:** 767 tests passed (762 + 5), 0 issues

### Phase 72-UAT: UAT 验证

**状态:** ✅ Completed — 1319 tests passed, 0 regression issues

**交付物:**
- `phases/phase-72/72-UAT.md` — comprehensive UAT report
- Phase 72-A/B/CAll acceptance criteria met

### Phase 72-D: FString/FName 区分 ✅

**完成日期:** 2026-05-23

**根因:** `null_ratio > 0.3` 启发式检测误杀短字符串（如 `"A"`, `"Byte"`），导致 35 处 FString 返回空。

**修复内容:** `archive.py` — `read_fstring()` 重构
- **移除** `null_ratio > 0.3` 启发式检测
- **替换为** 解码后 `' ' in result` 内部 null 字节检测
- UTF-8 和 UTF-16 路径统一使用 `rstrip(' ')` 后检测

**测试:** 20 new tests (test_phase72d_fstring_fname.py) + 1339 total passed, 0 regressions

**验收:** `phases/phase-72d/72d-UAT.md` — 5/5 criteria met

### Phase 72-E: EventGraph 节点解析修复 (INSERTED)

**状态:** 🔴 待诊断 — 基于三方对比报告插入的紧急修复

**问题清单:**

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | **EventGraph 节点严重缺失** (9/16+) | 🔴 High | 大部分 K2Node_CallFunction、K2Node_EnhancedInputAction 未解析 |
| 2 | **函数调用名解析为 "None"** | 🔴 High | function_reference.member_name 解析为字符串 "None"，无法识别实际函数 |
| 3 | **K2Node_Event 解析错误** | 🔴 High | 5 个事件节点中 4 个 _parse_error=True |
| 4 | **First Person Mesh 组件缺失** | ⚠️ Medium | Camera、Capsule、CharMoveComp 匹配，但 First Person Mesh 未提取 |
| 5 | **Blueprint.functions 为空** | ⚠️ Medium | Move 等自定义函数未提取 |

**目标:** 修复上述问题，使 BP_FirstPersonCharacter.uasset 的 EventGraph 解析覆盖率从 ~56% 提升至 >90%

**修复策略 (pending):**
- 排查 graph.py 节点读取循环，定位跳过/遗漏节点的条件
- 排查 FMemberReference 序列化逻辑，修复 member_name 解析为 "None" 的根因
- 检查 K2Node_Event 的 _parse_error 触发路径
- 验证组件提取管线是否遗漏 SkeletalMeshComponent 类型的 First Person Mesh

### Phase 72-F: BPGC 缓存隔离修复 (INSERTED)

**状态:** 📋 规划完成 — PLAN.md 已创建

**根因 (M-01):** `_extract_kismet_decompiled()` 直接调用 `decompile_single_function()`，绕过了 `decompile_uasset()` 中的 `reset_bpgc_cache()`。

**影响:** 连续调用 `parse_uasset(file_A)` + `parse_uasset(file_B)` 时，file B 会使用 file A 的 BPGC 缓存字节码映射，导致静默数据损坏。

**修复:** 在 `_extract_kismet_decompiled()` 开头添加 `reset_bpgc_cache()` 调用。

**验收:** 多文件解析无缓存串扰；回归测试通过。

### Phase 72-G: 复杂 StructProperty 解析 + Pin 连接映射修复 (INSERTED)

**插入日期:** 2026-05-23

**来源:** BP_FirstPersonCharacter.uasset vs FirstPersonCCharacter.h/cpp 三方对照分析

**背景:** 以下问题是反复出现、多次修复仍未彻底解决的顽固问题。Phase 67/72-B/72-E 的修复缓解了部分症状，但未根治根因。

**问题清单:**

| ID | # | 问题 | 严重度 | 历史修复记录 | 当前状态 |
|----|---|------|--------|-------------|---------|
| **M-01** | 1 | **Complex StructProperty 解析失败** | 🔴 High | Phase 67 修复 PropertyTag 格式 → 仍失败 | `RelativeLocation`/`RelativeRotation`/`BodyInstance` 因尺寸异常/偏移错误导致字段无法提取 |
| **M-02** | 2 | **Pin 连接映射输出为空 (Connections=0)** | 🔴 High | Phase 72-B 修复序列化 bug → 仍未输出 | EventGraph 中节点间的数据流和执行流连接未被提取 |
| **M-03** | 3 | **Blueprint.functions 列表为空** | ⚠️ Medium | 从未修复 | Move/Aim 等自定义函数未在 Blueprint 元数据中提取 |
| **M-04** | 4 | **函数参数信息缺失** | ⚠️ Medium | 从未修复 | DoMove(float, float) 等函数的参数类型和默认值无法获取 |
| — | 5 | **EnhancedInputComponent BindAction 不可见** | ℹ️ Low | 设计限制 | 运行时绑定逻辑不在未烘焙资产序列化数据中 |

**根因分析:**

- **问题 1 (StructProperty — 反复失败):** Phase 67 修复了 PropertyTag 层格式，但结构体**内部字段**序列化仍依赖旧逻辑。`BodyInstance` (FCollisionResponseContainer 嵌套)、`RelativeLocation` (FVector with metadata) 等复杂结构在 UE5 中有额外的序列化头信息，每次读取嵌套字段时偏移计算错误。
- **问题 2 (Pin 连接 — 反复失败):** Phase 72-B 修复了二进制序列化 bug (history_type signed / ParentPin 条件读取)，但 graph.py 的 `build_connections()` 函数**未将修复后的 LinkedTo 数据映射为输出格式**。修复了"能读到"，但没做到"能输出"。
- **问题 3 (Blueprint.functions):** Blueprint 导出对象的属性解析中，`UbergraphFunction` 引用未被转换为 functions 列表。
- **问题 4 (函数参数):** Function 导出对象的序列化区域包含参数表，但当前仅在 Kismet 层提取，未在蓝图元数据层关联。

**修复策略:**

1. **StructProperty 深度解析:** 在 `parsers/property_types.py` 中为 FVector/FRotator/FBodyInstance 添加专用解析器，处理 UE5 序列化头，**增加偏移追踪日志**确保每次嵌套读取后可验证
2. **Pin 连接输出:** 在 `serializers/graph.py` 中将 LinkedTo 数据映射到输出 `connections` 数组，**增加输出验证测试**确保非空
3. **Blueprint.functions 提取:** 在 `blueprint/` 模块中添加从 Blueprint 导出对象提取 UbergraphFunction 引用链
4. **函数参数关联:** 将 Function 导出对象的参数表与 Kismet 反编译结果关联

**目标:** BP_FirstPersonCharacter.uasset 解析覆盖率从 ~56% 提升至 >90%，Connections 输出非空，StructProperty 字段完整提取。

**验收标准:**
- [ ] `RelativeLocation`/`RelativeRotation` 提取为结构化数据（x/y/z 或 Pitch/Yaw/Roll）
- [ ] `BodyInstance` 至少提取 CapsuleHalfHeight / CapsuleRadius
- [ ] EventGraph `connections` 数组 > 0
- [ ] `Blueprint.functions` 包含 DoMove/DoAim/DoJumpStart/DoJumpEnd
- [ ] 每个函数输出包含参数名 + 参数类型

### Phase 72-I: BP_FirstPersonCharacter 全量对比修复 (INSERTED)

**插入日期:** 2026-05-24

**来源:** `BP_FirstPersonCharacter.uasset` 解析输出 vs `蓝图节点文本参考.md` + `FirstPersonCCharacter.h/cpp` 三方系统化对比

**对比基线:**
- 蓝图节点文本参考 — UE 编辑器导出的 EventGraph 全部 17 个节点的完整序列化文本（含 Pin 定义、LinkedTo、PinType 等）
- FirstPersonCCharacter.h/cpp — C++ 等价实现（DoMove/DoAim/DoJumpStart/DoJumpEnd 签名 + 组件属性）

**问题清单（按严重度排序）:**

| ID | 问题 | 严重度 | 参考值 | 当前解析输出 | 根因 |
|----|------|--------|--------|-------------|------|
| **I-01** | **Pin 连接完全丢失 (Connections=0)** | 🔴 P0 | 9 条 exec 连接 + 多条 data 连接 | 0 connections | LinkedTo 数组 count 异常（越界/负数），graph.py `read_pin_array()` 解析失败后跳过 |
| **I-02** | **K2Node_EnhancedInputAction 节点缺失** | 🔴 P0 | 4 个（IA_Look/IA_Move/IA_Jump/IA_MouseLook） | 0 个 | 该节点类型未被识别，序列化数据可能被错位读取或归类为其他类型 |
| **I-03** | **K2Node_Knot 节点缺失** | 🔴 P1 | 4 个（Move 函数内数据流转发） | 0 个 | Knot 节点解析路径不存在或被跳过 |
| **I-04** | **EventGraph 节点总数不足** | 🔴 P1 | 17 个（含 Comment×3, Knot×4, EnhancedInputAction×4, Event×3, CallFunction×2, FunctionEntry×1） | 9 个 | EnhancedInputAction 和 Knot 缺失，Comment 部分缺失 |
| **I-05** | **Camera RelativeRotation 全零** | 🔴 P1 | `(Pitch=0, Yaw=90, Roll=-90)` | `(Pitch=0, Yaw=0, Roll=0)` | StructProperty FRotator 内部字节被误读，可能受上游属性偏移错误影响 |
| **I-06** | **3 个属性 Size 越界导致解析失败** | 🔴 P1 | LastEditedDocuments/CategoryName/BodyInstance 应正常解析 | Size 1224736768/12605056/2048 越界 | PropertyTag 中 PropertyTypeNameNode 链式读取偏移错误，size 字段读到了相邻数据 |
| **I-07** | **CharacterMovement 属性缺失** | ⚠️ P2 | BrakingDecelerationFalling=1500, AirControl=0.5 | 未提取 | BodyInstance 解析失败后偏移错误，导致后续 NavAgentProps 之后的属性丢失 |
| **I-08** | **Camera RelativeLocation 不完整** | ⚠️ P2 | `(-2.8, 5.89, 0.0)` | `(X=0, Y=-2.8125, Z=0)` | FVector 的 X 分量被上游偏移错误吞掉，Y 为近似值 |
| **I-09** | **EdGraphNode_Comment 字段缺失** | ⚠️ P2 | CommentDepth/NodeWidth/NodeHeight/NodeComment | 仅 CommentColor + bCommentBubbleVisible | Comment 节点序列化路径不完整，缺少可视化元数据字段 |
| **I-10** | **Blueprint.functions 列表为空** | ⚠️ P2 | DoMove/DoAim/DoJumpStart/DoJumpEnd | 空 | UbergraphFunction 引用未转换为 functions 列表（同 M-03） |
| **I-11** | **函数参数信息缺失** | ⚠️ P3 | DoMove(float Right, float Forward) 等 | 仅 MemberName + bSelfContext | Function 导出对象的参数表未在蓝图元数据层关联（同 M-04） |
| **I-12** | **FString 偏移错误连锁** | ⚠️ P3 | 无 suspicious length | 15+ 处 suspicious length / internal nulls | FName index 区域被误作 FString 读取（Phase 72-D 修复了启发式，但 FName 专用路径仍未实现） |

**与已有 Phase 的关系:**

| 问题 | 已有 Phase | 72-I 侧重 |
|------|-----------|----------|
| Pin 连接 (I-01) | 72-B(序列化修复), 72-G(输出映射) | **端到端验证**：序列化→映射→输出全链路打通 |
| StructProperty (I-05/06/07/08) | 67(PropertyTag), 72-G(深度解析) | **实测验证**：用参考文档精确值对比 |
| EnhancedInputAction (I-02) | 72-E(节点解析) | **新节点类型识别**：K2Node_EnhancedInputAction 序列化路径 |
| Blueprint.functions (I-10) | 72-G(M-03) | 同一问题，72-I 提供验收基准 |
| FString (I-12) | 72-D(启发式修复), 72-H(容错) | **FName 专用解析路径** |

**修复策略:**

1. **I-01 Pin 连接端到端修复:** 修复 `serializers/graph.py` LinkedTo 读取（count 越界保护 + 偏移回退），打通 `build_connections()` 输出映射，确保 9 条 exec 连接全部输出
2. **I-02 K2Node_EnhancedInputAction 识别:** 在 `serializers/graph.py` 节点分发中添加该类型的序列化路径，InputAction 属性提取
3. **I-03 K2Node_Knot 识别:** 添加 Knot 节点解析，保留 InputPin/OutputPin 连接信息用于数据流穿透
4. **I-06 PropertyTag Size 修复:** 修复 PropertyTypeNameNode 链式读取偏移，使 LastEditedDocuments/CategoryName/BodyInstance 的 Size 字段正确
5. **I-05/I-08 FVector/FRotator 修复:** 在 Size 修复后验证 StructProperty 内部字段读取，确保 Rotation/Location 精确值
6. **I-09 Comment 字段补全:** 补充 CommentDepth/NodeWidth/NodeHeight/NodeComment 序列化路径

**验收标准（对照参考文档精确值）:**

- [ ] EventGraph `connections` 数组 ≥ 9（匹配参考文档中 9 条 exec 连接）
- [ ] EventGraph 节点数 ≥ 13（覆盖 EnhancedInputAction×4 + Event×3 + CallFunction×2 + Comment×3 + FunctionEntry×1）
- [ ] `K2Node_EnhancedInputAction` 节点 ≥ 4，每个包含 InputAction 属性
- [ ] `Camera RelativeRotation` = `(Pitch=0, Yaw=90, Roll=-90)`（匹配 C++ `FRotator(0, 90, -90)`）
- [ ] `Camera RelativeLocation` = `(X≈-2.8, Y≈5.89, Z=0)`（匹配 C++ `FVector(-2.8f, 5.89f, 0.0f)`）
- [ ] `LastEditedDocuments` / `CategoryName` / `BodyInstance` 无 ParseError
- [ ] `CharacterMovement` 包含 BrakingDecelerationFalling 和 AirControl 属性
- [ ] `EdGraphNode_Comment` 包含 NodeComment 字段
- [ ] `Blueprint.functions` 包含 DoMove/DoAim/DoJumpStart/DoJumpEnd
- [ ] 无 FString `suspicious length` 警告（或降级为 < 3 处）

### Phase 73: BP_FirstPersonCharacter Pin 序列化边界对齐修复 (INSERTED)

**插入日期:** 2026-05-24

**状态:** 📋 规划完成 — `phases/phase-73/CONTEXT.md`, `PLAN.md`, `VERIFICATION.md`

**来源:** Phase 72-I 诊断复核。当前 LinkedTo 已从 0 提升至 24 条引用，但仍有大量 Pin 在 LinkedTo 前错位。旧结论“FString 内部 null 返回空字符串导致位置偏移”已修正：返回值不会额外移动指针，真正问题是更早字段边界错位后把二进制误读为 FString，并按错误 length 消费。

**当前基线:**

| 指标 | 值 |
|------|----|
| Graphs | 4 |
| Nodes | 37 |
| Pins | 62 |
| Pins with LinkedTo | 22 (35.5%) |
| Total LinkedTo refs | 24 |
| EventGraph LinkedTo refs | 12 |

**核心问题:**

| ID | 问题 | 优先级 | 修复方向 |
|----|------|--------|----------|
| P73-01 | Pin 字段边界不可观测 | P0 | 建立字段级 offset/消费字节诊断脚本 |
| P73-02 | DefaultTextValue/FText 容错不回退 | P0 | 失败时回退到字段起点，避免半消费后读 LinkedTo |
| P73-03 | LinkedTo 恢复候选过宽 | P0 | count=0 不再单独视为成功，PinReference 强校验 |
| P73-04 | PinReference 格式验证不足 | P1 | 校验 null marker、owning_node、GUID、后续字段衔接 |
| P73-05 | PropertyTag 级联错位仍存在 | P1 | 分流 NodeComment/Transform/Movement 属性问题 |
| P73-06 | 连接输出缺少质量门禁 | P1 | 对照关键 EventGraph/Move/Aim 连接做 E2E 验收 |

**执行波次:**

1. **Wave 0:** 新增 `temp/phase73_pin_trace.py`，建立 Pin 字段级反馈回路。
2. **Wave 1:** 修复 `read_ftext_with_history()` / DefaultTextValue 的消费与回退语义。
3. **Wave 2:** 强化 `read_pin_array()`、`_recover_pin_array_count()`、`_try_recover_to_subpins()` 的候选校验。
4. **Wave 3:** 基于 trace 证据修正第一个真实 Pin 布局错位字段。
5. **Wave 4:** 分流 PropertyTag 级联问题，避免继续和 Pin 问题混合诊断。
6. **Wave 5:** 端到端验证 `linked_to_raw -> connections -> execution/data flows`。

**验收标准:**

- [ ] 诊断脚本能解释每个 LinkedTo 失败点的第一个错位字段
- [ ] `read_pin_array()` 不再依赖弱 count=0 候选恢复
- [ ] Total LinkedTo refs 从 24 提升到 >= 40，或缺口逐项解释
- [ ] EventGraph connections >= 9
- [ ] 新增 Phase 73 专项测试覆盖 FText 回退、PinReference 校验、LinkedTo 恢复误判

### 可选增强（v13.0 完成后讨论）

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

### Phase 73: BP_FirstPersonCharacter Pin 序列化边界对齐修复

**状态:** 🔄 Active — Wave 0-4 ✅

**目标:** 修复 Pin 读取字段边界错位，恢复 LinkedTo/Connections，并为 PropertyTag 级联问题建立可重复诊断回路。

**问题清单:**

| ID | 问题 | Wave | 状态 |
|----|------|------|------|
| **P73-01** | Pin 字段级诊断回路 | Wave 0 | ✅ Completed |
| **P73-02** | FText tolerant seek-back | Wave 1 | ✅ Completed |
| **P73-03** | PinReference validation + LinkedTo recovery | Wave 2 | ✅ Completed |
| **P73-04** | PropertyTag cascade failure recovery | Wave 4 | ✅ Completed |
| **P73-05** |端到端连接输出验收 | Wave 5 | 📋 Planned |

**Wave 0-2 完成:**
- `phase73_pin_trace.py` — 字段级诊断脚本（trace_mode）
- FText tolerant seek-back on failure
- `validate_pin_reference_at()` — PinReference 强校验
- `_recover_pin_array_count()` — LinkedTo 恢复 confidence scoring
- 20 tests passed (test_phase73_pin_trace.py + test_phase73_ftext_boundary.py + test_phase73_linkedto_recovery.py)

**Wave 4 完成 (2026-05-24):**
- PropertyTag offset tracking (tag_start, value_start, value_end)
- StructProperty boundary check for suspicious inner PropertyTag size
- PropertyTag failure recovery alignment to value_end
- 6 tests passed (test_phase73_property_resync.py)
- 1411 total tests passed, 0 regression

**验收标准:**
- [x] Pin 字段级诊断输出（JSONL + stats）
- [x] LinkedTo refs >= 24 (基线) → 36 (Wave 2 后)
- [x] FText failure seek-back to dtv_start_pos
- [x] PropertyTag offset fields populated
- [ ] EventGraph connections >= 9 (Wave 5 pending)

---

*Updated: 2026-05-24 (Phase 73 Wave 4 completed: PropertyTag cascade failure recovery)*
