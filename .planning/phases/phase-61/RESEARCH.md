# Phase 61: Kismet 表达式系统 - Research

**Date:** 2026-05-19
**Goal:** 理解 CUE4Parse Kismet 实现，为 Python 化提供结构化参考

## 1. EExprToken 枚举体系

### EExprToken（主枚举，~110 个值）

按语义分组（CUE4Parse `EExprToken.cs`）：

| 分组 | Token 范围 | 数量 | 说明 |
|------|-----------|------|------|
| 变量引用 | 0x00-0x02, 0x48, 0x6C | 5 | Local/Instance/Default/LocalOut/SparseData |
| 控制流 | 0x06-0x07, 0x4C-0x4F, 0x53, 0x5B, 0x6E-0x72 | 13 | Jump/JumpIfNot/PushPop/ComputedJump/EndOfScript/AutoRTFM |
| 赋值操作 | 0x0F, 0x14, 0x43-0x44, 0x5F-0x60, 0x64 | 7 | Let/LetBool/LetDelegate/LetObj/LetWeakObjPtr/LetValueOnPersistentFrame |
| 常量字面量 | 0x1D-0x2B, 0x2C-0x37, 0x41 | 17 | Int/Float/String/Object/Name/Vector/Rotator/Transform/Int64/Double 等 |
| 函数调用 | 0x1B-0x1C, 0x45-0x46, 0x63, 0x68 | 6 | Virtual/Final/LocalVirtual/LocalFinal/MulticastDelegate/CallMath |
| 类型转换 | 0x13, 0x2E, 0x38, 0x52, 0x54-0x55 | 6 | MetaCast/DynamicCast/Cast/ObjToInterface/CrossInterface/InterfaceToObj |
| 上下文操作 | 0x12, 0x19-0x1A, 0x51 | 4 | ClassContext/Context/Context_FailSilent/InterfaceContext |
| 容器操作 | 0x31-0x40, 0x65-0x66, 0x6B | 10 | SetArray/SetMap/SetSet/MapConst/ArrayConst 等 + End 标记 |
| 委托操作 | 0x43-0x44, 0x4B, 0x5C-0x5D, 0x61-0x63 | 9 | LetMulticast/LetDelegate/InstanceDelegate/Add/Clear/Bind/Remove/Call |
| 结构体/属性 | 0x2F-0x30, 0x33, 0x42, 0x6D | 6 | StructConst/EndStruct/PropertyConst/StructMemberContext/FieldPathConst |
| 特殊/调试 | 0x09, 0x0B-0x0C, 0x11, 0x15-0x16, 0x17, 0x18, 0x2A, 0x2D, 0x4A, 0x50, 0x5A, 0x5E, 0x69, 0x6A | 16 | Assert/Nothing/Self/Skip/NoObject/NoInterface/Breakpoint/Tracepoint/SwitchValue/Instrumentation |
| 游戏特定 | 0x6E, 0x6F, 0xF9, 0xFD, 0xFE | 5 | WuWa/DeltaForce/2XKO/Borderlands4 自定义 token |
| 保留/未使用 | 0x03, 0x05, 0x08, 0x0A, 0x0D-0x0E, 0x10, 0x47, 0x49, 0x56-0x59 | 11 | 空白槽位 |

### ECastToken（子枚举，8 个值）

用于 EX_Cast 的转换类型：ObjectToInterface/ObjectToBool/InterfaceToBool/DoubleToFloat/FloatToDouble + 2 个重复槽位。

### 辅助枚举

- EScriptInstrumentationType（15 个值）— 仪器化事件类型
- EBlueprintTextLiteralType（5 个值）— 文本字面量类型
- EAutoRtfmStopTransactMode（3 个值）— RTFM 事务模式

## 2. KismetExpression 类族结构

### 基类设计

```
KismetExpression (abstract)
├── Token: EExprToken (property)
├── StatementIndex: int (field)
└── WriteJson(writer, serializer, bAddIndex) — JSON 序列化

KismetExpression<T> : KismetExpression (generic)
└── Value: T — 泛型值字段
```

### 子类分类（~90 个具体类）

| 模式 | 数量 | 示例 |
|------|------|------|
| 零字段（无参构造） | ~20 | EX_Nothing, EX_True, EX_False, EX_EndOfScript |
| 单值（KismetExpression<T>） | ~12 | EX_IntConst(int), EX_FloatConst(float), EX_NameConst(FName) |
| 单字段 + ReadExpression | ~15 | EX_Return, EX_InterfaceContext, EX_SoftObjectConst |
| 多字段 + ReadExpressionArray | ~30 | EX_FinalFunction, EX_Context, EX_Let, EX_StructConst |
| 继承子类（扩展父类） | ~10 | EX_CallMath:EX_FinalFunction, EX_ClassContext:EX_Context |
| 基类抽象（共享模式） | 4 | EX_VariableBase, EX_LetBase, EX_CastBase, EX_Jump |

### 关键模式

1. **EX_VariableBase** — Local/Instance/Default/LocalOut/SparseData 共享 `FKismetPropertyPointer Variable`
2. **EX_LetBase** — LetBool/LetDelegate/LetMulticastDelegate/LetObj/LetWeakObjPtr 共享 Variable+Assignment
3. **EX_CastBase** — DynamicCast/MetaCast/ObjToInterface/CrossInterface/InterfaceToObj 共享 ClassPtr+Target
4. **EX_Jump** — Jump/JumpIfNot/Skip 共享 CodeOffset；JumpIfNot/Skip 额外读取子表达式

## 3. FKismetArchive 设计要点

### 核心方法

| 方法 | 说明 |
|------|------|
| `ReadExpression()` | 读取 1 byte token → match/case 分派 → 构造对应 KismetExpression |
| `ReadExpressionArray(endToken)` | 循环读取直到遇到 endToken，返回 KismetExpression[] |
| `XFERSTRING()` | ASCII 字符串读取（找 null 终止符） |
| `XFERUNICODESTRING()` | UTF-16 字符串读取（找 double-null 终止符） |
| `ReadFName()` | 覆盖基类，Kismet 上下文中的 FName 读取 |

### 实现特征

- **数据源**：内部持有 `byte[] _data`，Position/Index 双指针追踪
- **Expression 索引**：`ReadExpression()` 在读取 token 前保存 `index = Index`，赋值给 `expression.StatementIndex`
- **ReadExpressionArray 模式**：先读表达式，检查是否为 endToken，不是则加入列表继续
- **游戏特定 token**：通过 `Versions.Game` 条件分派（WuWa/DeltaForce/2XKO/Borderlands4）

## 4. FKismetPropertyPointer

版本敏感的数据结构：
- UE4.25+：使用 `FFieldPath? New`
- 旧版本：使用 `FPackageIndex? Old`
- 游戏判定：`Ar.Game >= EGame.GAME_UE4_25`

本项目中，FPackageIndex 已有定义（`serializers/object_resources.py`），FFieldPath 需要新增。

## 5. Python 化映射策略

### 已确认决策（来自 DISCUSSION-LOG）

- D-01: 细粒度子类，独立文件
- D-02: FKismetArchive 继承 FArchive
- D-03: 优先本地 CUE4Parse 参考
- D-04: IntEnum (base=byte)
- D-05: Phase 61 不加测试

### Python 文件组织建议

```
src/uasset_read/kismet/
├── __init__.py          # 导出 EExprToken, KismetExpression, FKismetArchive
├── tokens.py            # EExprToken, ECastToken, 辅助枚举
├── expressions/         # 细粒度表达式子类
│   ├── __init__.py      # 统一导出所有表达式类
│   ├── base.py          # KismetExpression 基类 + KismetExpression[T]
│   ├── variables.py     # EX_LocalVariable, EX_InstanceVariable, EX_DefaultVariable, EX_LocalOutVariable, EX_ClassSparseDataVariable
│   ├── literals.py      # EX_IntConst, EX_FloatConst, EX_StringConst, EX_NameConst, EX_Bool, EX_IntZero/One, EX_ByteConst, EX_Int64Const, EX_UInt64Const, EX_DoubleConst
│   ├── string_consts.py # EX_StringConst, EX_UnicodeStringConst, EX_TextConst, EX_SoftObjectConst
│   ├── vector_consts.py # EX_VectorConst, EX_RotationConst, EX_TransformConst, EX_Vector3fConst
│   ├── control_flow.py  # EX_Jump, EX_JumpIfNot, EX_Skip, EX_ComputedJump, EX_PushExecutionFlow, EX_PopExecutionFlow, EX_PopExecutionFlowIfNot, EX_EndOfScript
│   ├── assignments.py   # EX_Let, EX_LetBool, EX_LetDelegate, EX_LetObj, EX_LetWeakObjPtr, EX_LetMulticastDelegate, EX_LetValueOnPersistentFrame
│   ├── functions.py     # EX_VirtualFunction, EX_FinalFunction, EX_LocalVirtualFunction, EX_LocalFinalFunction, EX_CallMath, EX_CallMulticastDelegate
│   ├── casts.py         # EX_Cast, EX_MetaCast, EX_DynamicCast, EX_ObjToInterfaceCast, EX_CrossInterfaceCast, EX_InterfaceToObjCast
│   ├── context.py       # EX_Context, EX_Context_FailSilent, EX_ClassContext, EX_InterfaceContext, EX_StructMemberContext
│   ├── containers.py    # EX_SetArray, EX_SetMap, EX_SetSet, EX_ArrayConst, EX_MapConst, EX_SetConst + End 标记
│   ├── structs.py       # EX_StructConst, EX_EndStructConst, EX_BitFieldConst, EX_PropertyConst
│   ├── delegates.py     # EX_AddMulticastDelegate, EX_ClearMulticastDelegate, EX_BindDelegate, EX_RemoveMulticastDelegate, EX_InstanceDelegate
│   ├── special.py       # EX_Return, EX_Assert, EX_Nothing, EX_Self, EX_NoObject, EX_NoInterface, EX_SwitchValue, EX_InstrumentationEvent
│   └── rtfm.py          # EX_AutoRtfmTransact, EX_AutoRtfmStopTransact, EX_AutoRtfmAbortIfNot
├── archive.py           # FKismetArchive
└── property_pointer.py  # FKismetPropertyPointer
```

### 继承关系映射

```
KismetExpression (base.py)
├── EX_VariableBase → variables.py (EX_LocalVariable, EX_InstanceVariable, EX_DefaultVariable, EX_LocalOutVariable, EX_ClassSparseDataVariable)
├── EX_LetBase → assignments.py (EX_LetBool, EX_LetDelegate, EX_LetMulticastDelegate, EX_LetObj, EX_LetWeakObjPtr)
├── EX_CastBase → casts.py (EX_MetaCast, EX_DynamicCast, EX_ObjToInterfaceCast, EX_CrossInterfaceCast, EX_InterfaceToObjCast)
├── EX_Jump → control_flow.py (EX_JumpIfNot, EX_Skip)
├── KismetExpression[T] → literals.py (EX_IntConst, EX_FloatConst, EX_NameConst, 等)
└── 直接继承 → 各文件按语义分组
```

## 6. 风险与注意事项

1. **FPackageIndex 读取**：CUE4Parse 的 `new FPackageIndex(Ar)` 在 Kismet 上下文中使用，本项目已有 FPackageIndex，但需要确认 Kismet 字节码流中的读取方式是否与主 package 一致
2. **FFieldPath**：UE4.25+ 使用，需要新增 dataclass + 序列化器
3. **FName 读取**：FKismetArchive 覆盖 ReadFName，需要在 Python 中同样处理
4. **XFERSTRING/XFERUNICODESTRING**：CUE4Parse 使用底层 byte[] 搜索 null 终止符，Python 中需要在 FArchive 上实现类似行为
5. **游戏特定 token**：本项目暂不处理游戏特定 token（WuWa/Borderlands4 等），但需要预留扩展点

---

*Research completed: 2026-05-19*
*Sources: CUE4Parse EExprToken.cs, KismetExpression.cs, FKismetArchive.cs*
