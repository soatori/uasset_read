# Phase 61: Kismet 表达式系统 - PLAN

**Goal:** 构建 Kismet 字节码反编译器的底层数据结构和读取原语：EExprToken 枚举、KismetExpression 类族、FKismetPropertyPointer、FKismetArchive。

**Mode:** default
**Scope:** 纯数据模型 + 读取器，不含单元测试（D-05）。
**Upstream:** 61-CONTEXT.md, RESEARCH.md, DISCUSSION-LOG.md
**Downstream:** Phase 62（字节码→表达式树构建）

## 前置验证

- [x] CONTEXT.md 存在且标记 Ready for planning
- [x] RESEARCH.md 完成（CUE4Parse 三文件已分析）
- [x] DISCUSSION-LOG.md 完成（5 项决策已记录）

## 任务分解

### Wave 1: 枚举定义 + 基类（串行，互为依赖）

#### 1.1 `kismet/tokens.py` — EExprToken + 辅助枚举
- 定义 `EExprToken(enum.IntEnum)`，base 为 byte 范围 0x00-0xFF
- 包含所有 ~110 个有效 token 值 + 空白槽位注释（与 CUE4Parse EExprToken.cs 对齐）
- 定义 `ECastToken(enum.IntEnum)` — 8 个值
- 定义 `EScriptInstrumentationType(enum.IntEnum)` — 15 个值
- 定义 `EBlueprintTextLiteralType(enum.IntEnum)` — 5 个值
- 定义 `EAutoRtfmStopTransactMode(enum.IntEnum)` — 3 个值
- 文件路径：`src/uasset_read/kismet/tokens.py`

#### 1.2 `kismet/expressions/base.py` — KismetExpression 基类
- `KismetExpression` 抽象基类：`Token` property (返回 EExprToken), `StatementIndex` field, `to_dict() -> dict` 方法（替代 CUE4Parse 的 WriteJson）
- `KismetExpression[T]` 泛型基类：继承 KismetExpression，添加 `Value: T` 字段
- `to_dict()` 默认实现返回 `{"Inst": self.Token.name, "StatementIndex": self.StatementIndex}`
- 文件路径：`src/uasset_read/kismet/expressions/base.py`

#### 1.3 `kismet/property_pointer.py` — FKismetPropertyPointer + FFieldPath
- **`FFieldPath` dataclass**（完整实现，非 stub）：
  - `Path: list[str]` — FName 解析后的名称列表（CUE4Parse 使用 `FName[]`，此处简化为 str list）
  - `ResolvedOwner: Optional[FPackageIndex]` — UE5 新增字段
  - `from_archive(cls, archive: FArchive, name_map: list[str]) -> Self` classmethod
  - 读取逻辑：`ReadArray(read_fname_kismet)` → 如果第一个元素是 "None" 则清空 Path → 检查版本读取 ResolvedOwner
- **`FKismetPropertyPointer` dataclass**：
  - `bNew: bool`, `Old: Optional[FPackageIndex]`, `New: Optional[FFieldPath]`
  - `from_archive(cls, archive: FArchive, name_map: list[str]) -> Self` classmethod
  - **Phase 61 简化方案**：统一使用 `New: FFieldPath` 路径（UE5 默认），`Old` 路径留待后续完善
  - `__str__()` 方法：返回 `New.Path[0]` 如果可用，否则 `"None"`
- 文件路径：`src/uasset_read/kismet/property_pointer.py`

### Wave 2: 表达式子类（可并行，每组独立文件）

> 所有子类遵循 D-01：细粒度 dataclass + `from_archive()` classmethod 延迟导入模式
> 每个表达式类的构造函数接收 `archive: FKismetArchive`，读取对应字段

#### 2.1 `kismet/expressions/variables.py` — 变量引用表达式
- `EX_VariableBase` 抽象基类：`Variable: FKismetPropertyPointer`
- `EX_LocalVariable(EX_VariableBase)`, `EX_InstanceVariable(EX_VariableBase)`, `EX_DefaultVariable(EX_VariableBase)`, `EX_LocalOutVariable(EX_VariableBase)`, `EX_ClassSparseDataVariable(EX_VariableBase)`
- 每个子类定义 `Token` property + `from_archive()` 构造函数

#### 2.2 `kismet/expressions/literals.py` — 数值/布尔常量
- `EX_IntConst(KismetExpression[int])`, `EX_FloatConst(KismetExpression[float])`, `EX_ByteConst(KismetExpression[byte])`, `EX_IntConstByte(KismetExpression[byte])`
- `EX_Int64Const(KismetExpression[int])`, `EX_UInt64Const(KismetExpression[int])`, `EX_DoubleConst(KismetExpression[float])`
- `EX_IntZero(KismetExpression)`, `EX_IntOne(KismetExpression)`, `EX_True(KismetExpression)`, `EX_False(KismetExpression)`
- 零参数：读取单个数值即可

#### 2.3 `kismet/expressions/string_consts.py` — 字符串常量
- `EX_StringConst(KismetExpression[str])` — 使用 `XFERSTRING()` 读取
- `EX_UnicodeStringConst(KismetExpression[str])` — 使用 `XFERUNICODESTRING()` 读取
- `EX_TextConst` — 读取 `FScriptText`（含 EBlueprintTextLiteralType 分派）
- `EX_SoftObjectConst(KismetExpression[KismetExpression])` — 读取一个子表达式
- `FScriptText` dataclass：`TextLiteralType`, `SourceString`, `KeyString`, `Namespace`, `StringTableAsset`, `TableIdString`

#### 2.4 `kismet/expressions/vector_consts.py` — 向量/变换常量
- `EX_VectorConst`, `EX_RotationConst`, `EX_TransformConst`, `EX_Vector3fConst`
- 复用项目已有的 `VectorValue`, `RotatorValue`, `ScaleValue` 和 `FTransform` 读取逻辑
- 或简化为读取对应的基础数值（float x3/x4/x7）

#### 2.5 `kismet/expressions/control_flow.py` — 控制流表达式
- `EX_Jump`：`CodeOffset: uint`，`to_dict()` 添加 ObjectPath
- `EX_JumpIfNot(EX_Jump)`：`BooleanExpression: KismetExpression`
- `EX_Skip(EX_Jump)`：`SkipExpression: KismetExpression`
- `EX_ComputedJump`：`CodeOffsetExpression: KismetExpression`
- `EX_PushExecutionFlow`：`PushingAddress: uint`
- `EX_PopExecutionFlow`（零字段）
- `EX_PopExecutionFlowIfNot`：`BooleanExpression: KismetExpression`
- `EX_EndOfScript`（零字段）
- `EX_SkipOffsetConst(KismetExpression[uint])`

#### 2.6 `kismet/expressions/assignments.py` — 赋值表达式
- `EX_Let`：`Property: FKismetPropertyPointer`, `Variable: KismetExpression`, `Assignment: KismetExpression`
- `EX_LetBase` 抽象基类：`Variable: KismetExpression`, `Assignment: KismetExpression`
- `EX_LetBool(EX_LetBase)`, `EX_LetDelegate(EX_LetBase)`, `EX_LetMulticastDelegate(EX_LetBase)`, `EX_LetObj(EX_LetBase)`, `EX_LetWeakObjPtr(EX_LetBase)`
- `EX_LetValueOnPersistentFrame`：`DestinationProperty: FKismetPropertyPointer`, `AssignmentExpression: KismetExpression`

#### 2.7 `kismet/expressions/functions.py` — 函数调用表达式
- `EX_EndParmValue`（零字段）— 标记可选函数参数默认值结束
- `EX_EndFunctionParms`（零字段）— 标记函数参数列表结束，`read_expression_array()` 的关键 endToken
- `EX_FinalFunction`：`StackNode: FPackageIndex`, `Parameters: list[KismetExpression]`（使用 `read_expression_array(EExprToken.EX_EndFunctionParms)`）
- `EX_CallMath(EX_FinalFunction)` — 继承，仅覆盖 Token
- `EX_LocalFinalFunction(EX_FinalFunction)` — 继承，仅覆盖 Token
- `EX_VirtualFunction`：`VirtualFunctionName: str`, `Parameters: list[KismetExpression]`
- `EX_LocalVirtualFunction(EX_VirtualFunction)` — 继承
- `EX_CallMulticastDelegate`：`StackNode: FPackageIndex`, `Delegate: KismetExpression`, `Parameters: list[KismetExpression]`

#### 2.8 `kismet/expressions/casts.py` — 类型转换表达式
- `EX_CastBase` 抽象基类：`ClassPtr: FPackageIndex`, `Target: KismetExpression`
- `EX_Cast`：`ConversionType: ECastToken`, `Target: KismetExpression`（不走 CastBase）
- `EX_MetaCast(EX_CastBase)`, `EX_DynamicCast(EX_CastBase)`, `EX_ObjToInterfaceCast(EX_CastBase)`, `EX_CrossInterfaceCast(EX_CastBase)`, `EX_InterfaceToObjCast(EX_CastBase)`

#### 2.9 `kismet/expressions/context.py` — 上下文表达式
- `EX_Context`：`ObjectExpression: KismetExpression`, `Offset: uint`, `RValuePointer: FKismetPropertyPointer`, `ContextExpression: KismetExpression`
- `EX_Context_FailSilent(EX_Context)` — 继承
- `EX_ClassContext(EX_Context)` — 继承
- `EX_InterfaceContext`：`InterfaceValue: KismetExpression`
- `EX_StructMemberContext`：`Property: FKismetPropertyPointer`, `StructExpression: KismetExpression`

#### 2.10 `kismet/expressions/containers.py` — 容器表达式
- `EX_SetArray`：版本分支（CHANGE_SETARRAY_BYTECODE）→ `AssigningProperty` 或 `ArrayInnerProp`，`Elements: list[KismetExpression]`
- `EX_EndArray`（零字段）
- `EX_SetMap`：`MapProperty: KismetExpression`, `Elements: list[KismetExpression]`
- `EX_EndMap`（零字段）
- `EX_SetSet`：`SetProperty: KismetExpression`, `Elements: list[KismetExpression]`
- `EX_EndSet`（零字段）
- `EX_ArrayConst`：`InnerProperty: FKismetPropertyPointer`, `Elements: list[KismetExpression]`
- `EX_EndArrayConst`（零字段）
- `EX_MapConst`：`KeyProperty: FKismetPropertyPointer`, `ValueProperty: FKismetPropertyPointer`, `Elements: list[KismetExpression]`
- `EX_EndMapConst`（零字段）
- `EX_SetConst`：`InnerProperty: FKismetPropertyPointer`, `Elements: list[KismetExpression]`
- `EX_EndSetConst`（零字段）
- `EX_ArrayGetByRef`：`ArrayVariable: KismetExpression`, `ArrayIndex: KismetExpression`

#### 2.11 `kismet/expressions/structs.py` — 结构体表达式
- `EX_StructConst`：`Struct: FPackageIndex`, `StructSize: int`, `Properties: list[KismetExpression]`
- `EX_EndStructConst`（零字段）
- `EX_BitFieldConst`：`InnerProperty: FKismetPropertyPointer`, `ConstValue: byte`
- `EX_PropertyConst`：`Property: FKismetPropertyPointer`

#### 2.12 `kismet/expressions/delegates.py` — 委托表达式
- `EX_AddMulticastDelegate`：`Delegate: KismetExpression`, `DelegateToAdd: KismetExpression`
- `EX_ClearMulticastDelegate`：`DelegateToClear: KismetExpression`
- `EX_BindDelegate`：`FunctionName: str`, `Delegate: KismetExpression`, `ObjectTerm: KismetExpression`
- `EX_RemoveMulticastDelegate`：`Delegate: KismetExpression`, `DelegateToAdd: KismetExpression`
- `EX_InstanceDelegate`：`FunctionName: str`

#### 2.13 `kismet/expressions/special.py` — 特殊表达式
- `EX_Return`：`ReturnExpression: KismetExpression`
- `EX_Assert`：`LineNumber: ushort`, `DebugMode: bool`, `AssertExpression: KismetExpression`
- `EX_Nothing`（零字段）
- `EX_NothingInt32(KismetExpression[int])`
- `EX_Self`（零字段）
- `EX_NoObject`（零字段）
- `EX_NoInterface`（零字段）
- `EX_SwitchValue`：`EndGotoOffset: uint`, `IndexTerm: KismetExpression`, `Cases: list[FKismetSwitchCase]`, `DefaultTerm: KismetExpression`
- `FKismetSwitchCase` struct：`CaseIndexValueTerm: KismetExpression`, `NextOffset: uint`, `CaseTerm: KismetExpression`
- `EX_InstrumentationEvent`：`EventType: EScriptInstrumentationType`, `EventName: Optional[str]`
- `EX_DeprecatedOp4A`（零字段）
- `EX_Breakpoint`（零字段）
- `EX_Tracepoint`（零字段）
- `EX_WireTracepoint`（零字段）
- `EX_FieldPathConst`：`Value: KismetExpression`
- `EX_ObjectConst(KismetExpression[FPackageIndex])`
- `EX_NameConst(KismetExpression[str])` — 使用 ReadFName

#### 2.14 `kismet/expressions/rtfm.py` — AutoRTFM 表达式
- `EX_AutoRtfmTransact`：`Id: int`, `CodeOffset: uint`, `Parameters: list[KismetExpression]`
- `EX_AutoRtfmStopTransact`：`Id: int`, `Mode: EAutoRtfmStopTransactMode`
- `EX_AutoRtfmAbortIfNot`（零字段）

### Wave 3: 模块整合（串行，依赖 Wave 2）

#### 3.1 `kismet/expressions/__init__.py` — 统一导出
- 导入所有表达式类，建立 `EXPR_CLASS_MAP: dict[EExprToken, type[KismetExpression]]`
- 按 token 枚举值映射到对应类，供 FKismetArchive.ReadExpression 使用
- 未实现的游戏特定 token（0x6E, 0x6F, 0xF9, 0xFD, 0xFE）不在 MAP 中，触发 `ParseError`

#### 3.2 `kismet/__init__.py` — 模块入口
- 导出 `EExprToken`, `ECastToken`, `KismetExpression`, `FKismetArchive`, `FKismetPropertyPointer`
- 更新 `src/uasset_read/__init__.py` 的 `__all__` 列表，添加 kismet 模块导出

### Wave 4: FKismetArchive 读取器（串行，依赖 Wave 3）

#### 4.0 `kismet/archive.py` — FKismetArchive 初始化策略
- **问题**：`FArchive.__init__(self, path: str)` 需要真实文件路径（打开文件、mmap），但 Kismet 字节码是从 .uasset 中提取的内存字节块，无独立文件
- **方案**：FKismetArchive 构造函数接受 `data: bytes` + `name: str` + `name_map: list[str]`
  - 将 bytes 写入 `io.BytesIO`，覆盖 `FArchive` 的 `_file`、`_file_size`、`_use_mmap = False`
  - 添加 `self._name_map: list[str]` 属性供 `read_fname_kismet()` 使用
  - `self._path = name`（仅用于日志/调试，不实际打开文件）
  - **不修改** `FArchive` 源码，仅覆盖初始化后的内部状态
- 构造函数签名：`__init__(self, data: bytes, name: str, name_map: list[str])`

#### 4.1 `kismet/archive.py` — FKismetArchive 方法实现
- 继承 `FArchive`，添加 kismet 特定方法：
  - `read_expression() -> KismetExpression` — 读取 1 byte token → EXPR_CLASS_MAP 查找 → 构造实例 → 设置 StatementIndex
  - `read_expression_array(end_token: EExprToken) -> list[KismetExpression]` — 循环直到 endToken
  - `xfer_string() -> str` — ASCII null-terminated 字符串读取
  - `xfer_unicode_string() -> str` — UTF-16 null-terminated 字符串读取
  - `read_fname_kismet() -> str` — Kismet 上下文中的 FName 读取（复用 `self._name_map` + `FArchive.read_name()` 逻辑）
- 关键实现细节：
  - `read_expression()` 在读取 token 前保存 `self.tell()` 作为 StatementIndex
  - `read_expression_array()` 使用 `while True: expr = self.read_expression(); if expr.Token == end_token: break; result.append(expr)`
  - `xfer_string()` 逐字节读取直到 `\x00`，**不消耗** null 终止符（调用方负责 skip 1 byte）
  - `xfer_unicode_string()` 逐 2-byte 读取直到 `\x00\x00`，**不消耗** double-null 终止符（调用方负责 skip 2 bytes）
  - 与 CUE4Parse 行为对齐：CUE4Parse 的 `XFERSTRING`/`XFERUNICODESTRING` 返回后手动 `Position++`

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| FPackageIndex 在 Kismet 流中读取方式不同 | 所有使用 FPackageIndex 的表达式可能读偏 | 先验证 FPackageIndex 在 Kismet 上下文的读取逻辑是否与主 package 一致 |
| EX_SwitchValue 的 FKismetSwitchCase 嵌套读取复杂 | 可能读偏 | 严格对照 CUE4Parse 的 FKismetSwitchCase 构造函数 |
| 游戏特定 token 处理 | 解析非标准 .uasset 时崩溃 | 明确抛出 `ParseError("Unknown EExprToken")`，不静默跳过 |
| FFieldPath 版本分支 | UE4.25 之前版本使用 Old 路径 | Phase 61 仅实现 New 路径，标记 TODO，Phase 62+ 完善 |

## 文件清单

| 文件 | Wave | 说明 |
|------|------|------|
| `src/uasset_read/kismet/__init__.py` | 3 | 模块入口 |
| `src/uasset_read/kismet/tokens.py` | 1 | EExprToken + 辅助枚举 |
| `src/uasset_read/kismet/property_pointer.py` | 1 | FKismetPropertyPointer + FFieldPath |
| `src/uasset_read/kismet/archive.py` | 4 | FKismetArchive（初始化策略 + 方法实现） |
| `src/uasset_read/kismet/expressions/__init__.py` | 3 | 统一导出 + EXPR_CLASS_MAP |
| `src/uasset_read/kismet/expressions/base.py` | 1 | KismetExpression 基类 |
| `src/uasset_read/kismet/expressions/variables.py` | 2 | 5 个变量表达式 |
| `src/uasset_read/kismet/expressions/literals.py` | 2 | 10 个数/布尔常量 |
| `src/uasset_read/kismet/expressions/string_consts.py` | 2 | 4 个字符串常量 |
| `src/uasset_read/kismet/expressions/vector_consts.py` | 2 | 4 个向量/变换常量 |
| `src/uasset_read/kismet/expressions/control_flow.py` | 2 | 9 个控制流表达式 |
| `src/uasset_read/kismet/expressions/assignments.py` | 2 | 7 个赋值表达式 |
| `src/uasset_read/kismet/expressions/functions.py` | 2 | 8 个函数调用/结束标记表达式 |
| `src/uasset_read/kismet/expressions/casts.py` | 2 | 6 个类型转换表达式 |
| `src/uasset_read/kismet/expressions/context.py` | 2 | 5 个上下文表达式 |
| `src/uasset_read/kismet/expressions/containers.py` | 2 | 13 个容器表达式 |
| `src/uasset_read/kismet/expressions/structs.py` | 2 | 4 个结构体表达式 |
| `src/uasset_read/kismet/expressions/delegates.py` | 2 | 5 个委托表达式 |
| `src/uasset_read/kismet/expressions/special.py` | 2 | 16 个特殊表达式 |
| `src/uasset_read/kismet/expressions/rtfm.py` | 2 | 3 个 RTFM 表达式 |

## 验收标准

- [ ] `from uasset_read.kismet import EExprToken, KismetExpression, FKismetArchive` 可用
- [ ] `EExprToken.EX_LocalVariable == 0x00` 且 `EExprToken.EX_Max == 0xFF`
- [ ] `KismetExpression` 有 `Token` property 和 `to_dict()` 方法
- [ ] `FKismetArchive` 继承 `FArchive`，有 `read_expression()` 方法
- [ ] 所有 ~90 个表达式类已定义，Token 值与 CUE4Parse 对齐
- [ ] `EXPR_CLASS_MAP` 覆盖所有非游戏特定 token
- [ ] `python -c "from uasset_read.kismet import *"` 无错误
- [ ] 不修改已有模块（`archive.py`, `models/`, `serializers/`）— 新增 `kismet/` 模块

---

*Phase: 61-Kismet 表达式系统*
*Plan created: 2026-05-19*
