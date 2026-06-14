# K2Node 节点类型语义参考

> **UE 源码对照**: `Editor/BlueprintGraph/Classes/K2Node_*.h` (100+ 类), `Runtime/Engine/Classes/Kismet/` (运行时)
> **最后对齐**: UE 5.7 (2026-06)

## 概述

K2Node 是 UE 蓝图图系统中的节点基类（`UK2Node : UEdGraphNode`）。每个 K2Node 子类代表一种特定的蓝图节点语义，在 `.uasset` 中通过 `class_name` 字段标识。解析器通过 class_name 分派到不同的反序列化逻辑。

---

## 节点类型分类与语义

### 1. 函数调用类

| K2Node 类名 | 语义 | 源码路径 | 解析器支持 |
|-------------|------|---------|-----------|
| `K2Node_CallFunction` | 调用蓝图/C++ 函数 | BlueprintGraph/K2Node_CallFunction.h | ✅ 完整 |
| `K2Node_CallFunctionOnMember` | 调用成员变量上的函数 | BlueprintGraph/K2Node_CallFunctionOnMember.h | ✅ 基础 |
| `K2Node_CallParentFunction` | 调用父类重写函数 | BlueprintGraph/K2Node_CallParentFunction.h | ✅ 完整 |
| `K2Node_CallArrayFunction` | 数组操作函数（Add/Remove 等） | BlueprintGraph/K2Node_CallArrayFunction.h | ✅ 完整 |
| `K2Node_CallDataTableFunction` | DataTable 行查询 | BlueprintGraph/K2Node_CallDataTableFunction.h | ✅ 完整 |
| `K2Node_CallMaterialParameterCollectionFunction` | 材质参数集合操作 | BlueprintGraph/... | ⚠️ 基础 |
| `K2Node_Message` | 接口消息调用 | BlueprintGraph/K2Node_Message.h | ✅ 完整 |
| `K2Node_GenericCreateObject` | 通用对象创建 | BlueprintGraph/K2Node_GenericCreateObject.h | ⚠️ 基础 |
| `K2Node_ConstructObjectFromClass` | 从 Class 引用构造对象 | BlueprintGraph/... | ⚠️ 基础 |

### 2. 事件与委托类

| K2Node 类名 | 语义 | 解析器支持 |
|-------------|------|-----------|
| `K2Node_Event` | 事件节点（BeginPlay/Tick 等） | ✅ 完整 |
| `K2Node_CustomEvent` | 自定义事件节点 | ✅ 基础 |
| `K2Node_InputAction` | 输入动作事件（Enhanced Input） | ✅ 完整 |
| `K2Node_InputActionEvent` | 输入动作事件（旧版） | ⚠️ 基础 |
| `K2Node_InputAxisEvent` | 输入轴事件 | ⚠️ 基础 |
| `K2Node_InputKeyEvent` | 按键事件 | ⚠️ 基础 |
| `K2Node_InputTouchEvent` | 触摸事件 | ⚠️ 基础 |
| `K2Node_InputVectorAxisEvent` | 向量轴事件 | ⚠️ 基础 |
| `K2Node_ActorBoundEvent` | Actor 绑定事件 | ⚠️ 基础 |
| `K2Node_ComponentBoundEvent` | 组件绑定事件 | ⚠️ 基础 |
| `K2Node_GeneratedBoundEvent` | 生成绑定事件 | ⚠️ 基础 |
| `K2Node_WidgetAnimationEvent` | Widget 动画事件 | ⚠️ 基础 |
| `K2Node_CallDelegate` | 调用（广播）委托 | ✅ 完整 |
| `K2Node_AddDelegate` | 绑定委托（Add Dynamic） | ✅ 完整 |
| `K2Node_AssignDelegate` | 赋值委托（单播） | ✅ 完整 |
| `K2Node_RemoveDelegate` | 解绑委托 | ⚠️ 基础 |
| `K2Node_ClearDelegate` | 清除所有绑定 | ⚠️ 基础 |
| `K2Node_CreateDelegate` | 创建委托绑定 | ⚠️ 基础 |
| `K2Node_DelegateSet` | 委托集操作 | ⚠️ 基础 |

### 3. 变量与属性类

| K2Node 类名 | 语义 | 解析器支持 |
|-------------|------|-----------|
| `K2Node_VariableGet` | 读取变量 | ✅ 完整 |
| `K2Node_VariableSet` | 写入变量 | ✅ 完整 |
| `K2Node_VariableSetRef` | 通过引用写入变量 | ⚠️ 基础 |
| `K2Node_LocalVariable` | 局部变量声明 | ⚠️ 基础 |
| `K2Node_MakeVariable` | 创建结构体/容器变量 | ⚠️ 基础 |
| `K2Node_StructMemberGet` | 读取结构体成员 | ⚠️ 基础 |
| `K2Node_StructMemberSet` | 写入结构体成员 | ⚠️ 基础 |
| `K2Node_SetVariableOnPersistentFrame` | 持久帧变量写入 | ⚠️ 基础 |
| `K2Node_EditorPropertyAccess` | 编辑器属性访问 | ⚠️ 基础 |
| `K2Node_GetClassDefaults` | 获取 CDO 属性 | ⚠️ 基础 |

### 4. 控制流类

| K2Node 类名 | 语义 | 解析器支持 |
|-------------|------|-----------|
| `K2Node_IfThenElse` | 条件分支（Branch） | ✅ 完整 |
| `K2Node_Switch` | Switch 基类 | ⚠️ 基础 |
| `K2Node_SwitchEnum` | 枚举 Switch | ⚠️ 基础 |
| `K2Node_SwitchInteger` | 整数 Switch | ⚠️ 基础 |
| `K2Node_SwitchName` | Name Switch | ⚠️ 基础 |
| `K2Node_SwitchString` | 字符串 Switch | ⚠️ 基础 |
| `K2Node_Select` | Select（内联选择） | ⚠️ 基础 |
| `K2Node_MultiGate` | 多门序列（Sequence） | ⚠️ 基础 |
| `K2Node_DoOnceMultiInput` | 单次执行 | ⚠️ 基础 |
| `K2Node_ExecutionSequence` | 执行序列（顺序执行多输出） | ⚠️ 基础 |
| `K2Node_Timeline` | 时间轴节点 | ⚠️ 基础 |

### 5. 函数结构类

| K2Node 类名 | 语义 | 解析器支持 |
|-------------|------|-----------|
| `K2Node_FunctionEntry` | 函数入口 | ✅ 完整 |
| `K2Node_FunctionResult` | 函数返回值 | ✅ 完整 |
| `K2Node_FunctionTerminator` | 函数终结器（基类） | ⚠️ 基础 |
| `K2Node_Tunnel` | 函数参数/返回隧道 | ⚠️ 基础 |
| `K2Node_TunnelBoundary` | 隧道边界 | ⚠️ 基础 |

### 6. 类型转换与运算类

| K2Node 类名 | 语义 | 解析器支持 |
|-------------|------|-----------|
| `K2Node_DynamicCast` | 对象动态类型转换（Cast） | ⚠️ 基础 |
| `K2Node_ClassDynamicCast` | 类动态转换 | ⚠️ 基础 |
| `K2Node_CastByteToEnum` | Byte→Enum 转换 | ⚠️ 基础 |
| `K2Node_ConvertAsset` | Asset→Object 转换 | ⚠️ 基础 |
| `K2Node_EnumLiteral` | 枚举字面量 | ⚠️ 基础 |
| `K2Node_EnumEquality` | 枚举相等比较 | ⚠️ 基础 |
| `K2Node_EnumInequality` | 枚举不等比较 | ⚠️ 基础 |
| `K2Node_BitmaskLiteral` | 位掩码字面量 | ⚠️ 基础 |
| `K2Node_Literal` | 字面量常量 | ⚠️ 基础 |
| `K2Node_MathExpression` | 数学表达式 | ⚠️ 基础 |
| `K2Node_CommutativeAssociativeBinaryOperator` | 交换二元运算符 | ⚠️ 基础 |
| `K2Node_PromotableOperator` | 可提升运算符 | ⚠️ 基础 |
| `K2Node_EaseFunction` | 缓动函数 | ⚠️ 基础 |
| `K2Node_GenericToText` | 通用值转文本 | ⚠️ 基础 |
| `K2Node_GetEnumeratorName` | 获取枚举名 | ⚠️ 基础 |
| `K2Node_GetEnumeratorNameAsString` | 枚举名转字符串 | ⚠️ 基础 |
| `K2Node_GetNumEnumEntries` | 获取枚举项数 | ⚠️ 基础 |
| `K2Node_ForEachElementInEnum` | 遍历枚举元素 | ⚠️ 基础 |

### 7. 容器操作类

| K2Node 类名 | 语义 | 解析器支持 |
|-------------|------|-----------|
| `K2Node_MakeArray` | 创建数组 | ⚠️ 基础 |
| `K2Node_MakeMap` | 创建 Map | ⚠️ 基础 |
| `K2Node_MakeSet` | 创建 Set | ⚠️ 基础 |
| `K2Node_MakeContainer` | 创建容器（基类） | ⚠️ 基础 |
| `K2Node_GetArrayItem` | 获取数组元素 | ⚠️ 基础 |
| `K2Node_MapForEach` | Map 遍历 | ⚠️ 基础 |
| `K2Node_SetForEach` | Set 遍历 | ⚠️ 基础 |

### 8. 结构体操作类

| K2Node 类名 | 语义 | 解析器支持 |
|-------------|------|-----------|
| `K2Node_MakeStruct` | 创建结构体 | ⚠️ 基础 |
| `K2Node_BreakStruct` | 分解结构体 | ⚠️ 基础 |
| `K2Node_SetFieldsInStruct` | 设置结构体字段 | ⚠️ 基础 |
| `K2Node_InstancedStruct` | 实例化结构体 | ⚠️ 基础 |
| `K2Node_StructOperation` | 结构体操作基类 | ⚠️ 基础 |

### 9. 图组织与辅助类

| K2Node 类名 | 语义 | 解析器支持 |
|-------------|------|-----------|
| `K2Node_Knot` | 重定向节点（Reroute） | ✅ 完整 |
| `K2Node_Composite` | 折叠图（Composite） | ⚠️ 基础 |
| `EdGraphNode_Comment` | 注释节点 | ✅ 完整 |
| `K2Node_Self` | Self 引用 | ⚠️ 基础 |
| `K2Node_TemporaryVariable` | 临时变量 | ⚠️ 基础 |

### 10. 宏与异步类

| K2Node 类名 | 语义 | 解析器支持 |
|-------------|------|-----------|
| `K2Node_MacroInstance` | 宏实例调用 | ✅ 完整 |
| `K2Node_AsyncAction` | 异步动作 | ⚠️ 基础 |
| `K2Node_BaseAsyncTask` | 异步任务基类 | ⚠️ 基础 |
| `K2Node_LatentGameplayTaskCall` | 延迟游戏任务调用 | ⚠️ 基础 |

### 11. 特定领域类

| K2Node 类名 | 语义 | 解析器支持 |
|-------------|------|-----------|
| `K2Node_SpawnActorFromClass` | 从 Class 生成 Actor | ✅ 完整 |
| `K2Node_CreateWidget` | 创建 UMG Widget | ✅ 完整 |
| `K2Node_GetDataTableRow` | 获取 DataTable 行 | ✅ 完整 |
| `K2Node_LoadAsset` | 异步加载资产 | ✅ 完整 |
| `K2Node_EnhancedInputAction` | Enhanced Input 动作 | ✅ 完整 |
| `K2Node_GetInputAxisValue` | 获取输入轴值 | ⚠️ 基础 |
| `K2Node_GetInputAxisKeyValue` | 获取输入轴键值 | ⚠️ 基础 |
| `K2Node_GetInputVectorAxisValue` | 获取向量轴值 | ⚠️ 基础 |
| `K2Node_GetSubsystem` | 获取子系统 | ⚠️ 基础 |
| `K2Node_AddComponent` | 添加组件 | ⚠️ 基础 |
| `K2Node_AddComponentByClass` | 按类添加组件 | ⚠️ 基础 |
| `K2Node_PlayMontage` | 播放动画蒙太奇 | ⚠️ 基础 |
| `K2Node_PlayAnimation` | 播放动画 | ⚠️ 基础 |
| `K2Node_GetSequenceBinding` | 获取序列绑定 | ⚠️ 基础 |
| `K2Node_AIMoveTo` | AI 移动 | ⚠️ 基础 |

---

## 解析器分派机制

解析器通过 `class_name` 字段分派到特定的反序列化函数：

```
graph.py → read_node_data()
  ├─ "K2Node_CallFunction"      → read_k2node_call_function()
  ├─ "K2Node_Event"             → read_k2node_event()
  ├─ "K2Node_Knot"              → read_k2node_knot()
  ├─ "K2Node_FunctionEntry"     → read_k2node_functionentry()
  ├─ "K2Node_EnhancedInputAction" → read_k2node_enhanced_input()
  ├─ "K2Node_Message"           → read_k2node_message()
  ├─ "K2Node_CallDelegate"      → read_k2node_call_delegate()
  ├─ "K2Node_CallArrayFunction" → read_k2node_call_array_function()
  ├─ "K2Node_MacroInstance"     → read_k2node_macro_instance()
  └─ 其他 K2Node               → 通用 UEdGraphNode 反序列化
```

---

## 节点通用字段

所有 K2Node 继承自 `UEdGraphNode`，共享以下基础字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `node_guid` | FGuid (16 bytes) | 节点唯一标识 |
| `class_name` | FName | 节点类型名（如 "K2Node_CallFunction"） |
| `node_comment` | FString | 节点注释 |
| `b_comment_visible` | bool | 注释是否可见 |
| `schema_name` | FName | 图模式名 |
| `pins` | List[FPinConnection] | 引脚列表 |
| `advanced_pin_display` | (内部) | 高级引脚显示状态 |

---

## 关键节点语义详解

### K2Node_CallFunction

**语义**：调用一个函数。函数引用通过 `FMemberReference` 指定。

| 字段 | 类型 | 说明 |
|------|------|------|
| `function_reference` | FMemberReference | 目标函数引用 |
| `b_defaults_to_pure` | bool | 是否默认为纯函数 |

**纯函数判定**：`b_defaults_to_pure = true` 或目标函数标记为 `FUNC_Const`/`FUNC_Pure`。

### K2Node_Event

**语义**：事件入口节点。事件触发后执行执行链。

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_reference` | FMemberReference | 事件函数引用 |
| `b_override_function` | bool | 是否重写父类事件 |
| `b_internal_event` | bool | 是否为内部事件 |

### K2Node_VariableGet / VariableSet

**语义**：变量的读取/写入操作。

| 字段 | 类型 | 说明 |
|------|------|------|
| `variable_reference` | FMemberReference | 变量引用 |
| `b_linked_variable_get` | bool | 是否被其他节点链接读取 |

### K2Node_MacroInstance

**语义**：宏实例调用。宏在编译时展开为内联代码。

| 字段 | 类型 | 说明 |
|------|------|------|
| `macro_graph_reference` | FGuid | 宏图 GUID 引用 |
| `macro_name` | (computed) | 宏名称（从 graph 引用解析） |

**与函数的区别**：宏不支持 Latent 节点、支持多执行输出、编译时内联展开。

### K2Node_IfThenElse

**语义**：条件分支（Branch 节点）。

| 引脚 | 类型 | 说明 |
|------|------|------|
| `Condition` | bool (input) | 条件值 |
| `then` | exec (output) | 条件为 true 时执行 |
| `else` | exec (output) | 条件为 false 时执行 |

---

## 源码引用

- `Editor/BlueprintGraph/Classes/K2Node_*.h` — 所有 K2Node 子类定义
- `Editor/BlueprintGraph/Private/K2Node_*.cpp` — 序列化实现
- `Editor/BlueprintGraph/Public/EdGraphSchema_K2.h` — 图模式定义
- `Runtime/Engine/Classes/Kismet/` — 运行时 K2Node 支持
