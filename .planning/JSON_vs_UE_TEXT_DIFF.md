# JSON vs UE文本格式差异分析 (历史归档)

> **注意:** 本文档为 v2.0 时期的差异分析报告。其中列出的 ParseError、Pin缺失、连接关系缺失等问题，
> 已在 Phase 18-22（节点属性深度解析）中全部修复。
> 请勿基于本文档做出现行决策。

**资产**: BP_FirstPersonCharacter.uasset
**日期**: 2026-05-04
**目的**: 历史参考 — 对比当时JSON输出与UE编辑器文本格式的差异

---

## 1. 整体差异概览

| 项目 | JSON输出 | UE文本格式 | 状态 |
|------|----------|------------|------|
| 导出对象数量 | 69个 | ~20个可见 | ✓ 识别完整 |
| 节点名称 | 不完全匹配 | 精确匹配 | ⚠ 需研究 |
| 节点属性 | ParseError | 完整解析 | ❌ 完全缺失 |
| Pin信息 | 无 | 完整 | ❌ 完全缺失 |
| 节点连接 | 无 | LinkedTo完整 | ❌ 完全缺失 |
| NodeGuid | 无 | 有 | ❌ 缺失 |
| 节点位置 | 无 | NodePosX/Y | ❌ 缺失 |

---

## 2. 节点名称对比

### 2.1 JSON中的节点命名问题

| JSON节点名 | UE文本节点名 | 问题 |
|------------|--------------|------|
| `K2Node_CallFunction_8428` | `K2Node_CallFunction_11` | 编号不一致 |
| `K2Node_CallFunction_8429` | `K2Node_CallFunction_6` | 编号不一致 |
| `K2Node_CallFunction_12` | `K2Node_CallFunction_5` | 编号不一致 |
| `InpActEvt_IA_Jump_K2Node_EnhancedInputActionEvent_2` | `K2Node_EnhancedInputAction_5` | 格式不同 |
| `InpActEvt_IA_Look_K2Node_EnhancedInputActionEvent_5` | `K2Node_EnhancedInputAction_2` | 格式不同 |

**问题分析**:
- JSON节点编号（8428、8429等）来自 `ExportMap.SerialOffset` 或内部索引，不是UE编辑器显示的节点ID
- InputAction事件节点使用了 `InpActEvt_...` 前缀格式，而非直接的 `K2Node_EnhancedInputAction`

### 2.2 缺失的关键节点

JSON中**未找到**以下UE文本中的节点：
- `K2Node_CallFunction_1193` (Jump函数调用)
- `K2Node_CallFunction_9386` (StopJumping函数调用)
- `K2Node_CallFunction_4` (Move函数调用 - 触摸输入版本)
- `K2Node_EnhancedInputAction_3` (IA_Move)
- `K2Node_EnhancedInputAction_0` (IA_MouseLook)
- `K2Node_Event_2/3/4/5` (触摸接口事件)

---

## 3. 属性解析失败分析

### 3.1 ParseError统计

| 节点类型 | 错误类型 | 失败属性 |
|----------|----------|----------|
| K2Node_CallFunction | Size阈值超限 | FunctionReference |
| K2Node_EnhancedInputAction | Size阈值超限 | InputAction |
| K2Node_Event | Size阈值超限 | EventReference |
| K2Node_FunctionEntry | 负数Size | ExtraFlags |
| K2Node_Knot | 负数Size | NodePosX |
| EdGraphNode_Comment | Size阈值超限 | CommentColor, NodeComment |

### 3.2 典型错误示例

```json
// K2Node_CallFunction_33 (对应UE文本中的K2Node_CallFunction_12)
{
  "name": "K2Node_CallFunction_12",
  "properties": [
    {
      "name": "ParseError",
      "value": "Property parsing aborted: Size 1048576 exceeds remaining 42740 bytes at FunctionReference"
    }
  ]
}

// K2Node_EnhancedInputAction_44 (对应UE文本中的K2Node_EnhancedInputAction_1)
{
  "name": "ParseError",
  "value": "Property parsing aborted: Size 13196391 exceeds remaining 29084 bytes at InputAction"
}

// K2Node_Event_48 (对应UE文本中的K2Node_Event_3)
{
  "name": "ParseError",
  "value": "Property parsing aborted: Size 16777216 exceeds remaining 13796 bytes at EventReference"
}
```

**根本原因**: UE 5.7 格式的属性Size编码发生变化，阈值检测过于严格

---

## 4. 缺失的关键信息

### 4.1 FunctionReference (函数调用节点)

**UE文本格式**:
```
FunctionReference=(MemberName="Jump",bSelfContext=True)
FunctionReference=(MemberName="Move",MemberGuid=B96BAB4744AF0F8F393A3DB6EADCB59F,bSelfContext=True)
```

**JSON缺失**:
- `MemberName` - 函数名（Jump/StopJumping/Move/Aim）
- `MemberGuid` - 函数GUID（蓝图自定义函数）
- `bSelfContext` - 是否自上下文调用

### 4.2 EventReference (事件节点)

**UE文本格式**:
```
EventReference=(MemberParent="/Script/Engine.BlueprintGeneratedClass'/Game/Input/Touch/BPI_TouchInterface.BPI_TouchInterface_C'",MemberName="Primary Thumbstick",MemberGuid=97FB41A24EDF9FFD7D921D9A90178379)
bOverrideFunction=True
```

**JSON缺失**:
- `MemberParent` - 事件所属类（蓝图接口）
- `MemberName` - 事件名
- `MemberGuid` - 事件GUID
- `bOverrideFunction` - 是否覆盖函数

### 4.3 InputAction (输入动作节点)

**UE文本格式**:
```
InputAction="/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Jump.IA_Jump'"
```

**JSON缺失**:
- InputAction资产路径（软引用）
- 可通过导入表推断，但未直接关联到节点

### 4.4 CustomProperties Pin (引脚信息)

**UE文本格式**:
```
CustomProperties Pin (PinId=13FD260E4EE18FD0AA5F7085F9B509D6,PinName="execute",PinType.PinCategory="exec",LinkedTo=(K2Node_EnhancedInputAction_5 6412140B4E7EF6147A86BA8D2AFE9BA4,),...)
```

**JSON完全缺失**:
- `PinId` - 16字节GUID
- `PinName` - 引脚名（execute/then/self/Axis_X等）
- `PinType.PinCategory` - 类型分类（exec/object/real/struct）
- `PinType.PinSubCategory` - 子类型（double/float/self）
- `PinType.PinSubCategoryObject` - 对象类型路径
- `LinkedTo` - 连接目标（节点名+PinId）
- `Direction` - 方向（EGPD_Output）
- `DefaultValue` - 默认值
- `bHidden/bNotConnectable/bAdvancedView` - 显示属性

### 4.5 节点基础属性

**UE文本格式**:
```
NodePosX=3136
NodePosY=-1040
NodeGuid=F923268743B7B52D669FFB960CA79833
ErrorType=1
AdvancedPinDisplay=Hidden
```

**JSON缺失**:
- `NodePosX/NodePosY` - 编辑器位置坐标
- `NodeGuid` - 节点唯一标识符（16字节GUID）
- `ErrorType` - 错误类型标记
- `AdvancedPinDisplay` - 高级引脚显示状态

### 4.6 注释节点属性

**UE文本格式**:
```
CommentColor=(R=0.050980,G=0.050980,B=0.050980,A=1.000000)
NodeComment="Camera Input"
NodeWidth=1440
NodeHeight=544
CommentDepth=-2
```

**JSON缺失**:
- `CommentColor` - RGBA颜色
- `NodeComment` - 注释文本
- `NodeWidth/NodeHeight` - 尺寸
- `CommentDepth` - 层级深度

---

## 5. 节点连接关系缺失

### 5.1 UE文本中的完整连接链

**Jump输入 → Jump函数**:
```
K2Node_EnhancedInputAction_5
  Pin "Started" (6412140B4E7EF6147A86BA8D2AFE9BA4)
    → LinkedTo=K2Node_CallFunction_1193 Pin "execute" (13FD260E4EE18FD0AA5F7085F9B509D6)

K2Node_Event_4 (Touch Jump Start)
  Pin "then" (5B51114047AD12FFBCC0B4B41D99E92B)
    → LinkedTo=K2Node_CallFunction_1193 Pin "execute"
```

**JSON缺失**: 无法构建任何执行流程链

### 5.2 数据流连接

**Move输入 → Move函数**:
```
K2Node_EnhancedInputAction_3
  ActionValue_X → K2Node_CallFunction_5 "Left / Right"
  ActionValue_Y → K2Node_CallFunction_5 "Forward / Backward"
```

**JSON缺失**: 无法识别数据流方向

---

## 6. 下一阶段研究方向

### Phase 18: 节点属性深度解析

| 优先级 | 任务 | 技术要点 |
|--------|------|----------|
| P0 | **修复属性Size阈值** | UE 5.7格式变化，放宽阈值检测 |
| P0 | **解析FunctionReference** | MemberName + MemberGuid + bSelfContext |
| P0 | **解析EventReference** | MemberParent + MemberName + MemberGuid |
| P0 | **解析InputAction软引用** | 资产路径提取 |
| P1 | **解析Pin数组** | CustomProperties Pin完整结构 |
| P1 | **解析LinkedTo连接** | 节点间连接关系 |
| P1 | **解析NodeGuid** | 16字节GUID格式 |
| P2 | **解析节点位置** | NodePosX/NodePosY (int32) |
| P2 | **解析注释节点** | CommentColor + NodeComment |

### Phase 19: 执行流程重建

| 任务 | 输入 | 输出 |
|------|------|------|
| 构建执行图 | Pin连接信息 | 执行流程链（exec → then） |
| 构建数据流图 | Pin连接信息 | 数据流向（参数传递） |
| 生成graphs_summary | 执行图+数据流图 | 函数调用链摘要 |

---

## 7. 具体修复建议

### 7.1 属性Size阈值调整

**当前代码** (`uasset_read.py:~4500`):
```python
MAX_REASONABLE_PROPERTY_SIZE = 13838  # 太严格
```

**建议修改**:
```python
# UE 5.7属性Size可能包含额外编码信息
# 临时放宽至 64KB 或完全移除阈值检测
MAX_REASONABLE_PROPERTY_SIZE = 65536

# 或使用动态阈值：基于 SerialSize 计算
max_reasonable = min(export.serial_size * 2, 1048576)
```

### 7.2 FunctionReference解析

**UE格式分析**:
```
FunctionReference=(MemberName="Jump",bSelfContext=True)
  → MemberName: FName索引 → name_map解析
  → bSelfContext: bool (1字节)
  → MemberGuid: 可选，16字节GUID
```

**需要新增**:
- `MemberReference` 结构体解析
- `bSelfContext` 字段识别
- `MemberGuid` GUID解析

### 7.3 Pin数组解析

**UE格式分析**:
```
CustomProperties Pin (PinId=...,PinName="...",...)
  → 固定前缀 "CustomProperties Pin "
  → 内部格式类似属性，但包含LinkedTo数组
```

**需要新增**:
- Pin数组迭代解析
- PinType嵌套结构解析
- LinkedTo连接数组解析
- ParentPin父子关系（SubPins）

---

## 8. 测试验证计划

### 8.1 验证节点

| 节点 | 验证内容 |
|------|----------|
| K2Node_CallFunction_1193 | FunctionReference.MemberName="Jump" |
| K2Node_CallFunction_9386 | FunctionReference.MemberName="StopJumping" |
| K2Node_EnhancedInputAction_5 | InputAction="/Game/Input/Actions/IA_Jump" |
| K2Node_Event_2 | EventReference.MemberName="Primary Thumbstick" |
| EdGraphNode_Comment_1 | NodeComment="Camera Input" |

### 8.2 验证连接

| 连接 | 验证 |
|------|------|
| IA_Jump Started → Jump execute | ✓ |
| IA_Move Triggered → Move execute | ✓ |
| ActionValue_X → Left/Right 参数 | ✓ |
| Touch Jump Start → Jump execute | ✓ |

---

## 9. 结论

当前 uasset_read v2.0 能正确识别：
- ✓ 导出对象列表（69个）
- ✓ 导入依赖（75个）
- ✓ 节点存在性（通过名称）

**无法提取**：
- ❌ 节点属性（全部ParseError）
- ❌ Pin信息（完全缺失）
- ❌ 连接关系（完全缺失）
- ❌ 函数/事件引用（缺失）

**Phase 18 核心目标**：修复属性解析，实现完整节点信息提取，构建执行流程图。