# Models

> 来源：开发文档 `docs/dev-guide.html` → `section#models`

## 核心模型

| 模型 | 说明 |
|------|------|
| `UEdGraph` / `UEdGraphNode` / `UEdGraphPin` | 蓝图图/节点/引脚 |
| `FEdGraphPinType` / `FMemberReference` | 引脚类型/成员引用 |
| `PropertyTag` / `PropertyValue` | 属性标签/属性值基类 |
| `StructValue` / `MapValue` / `SetValue` / `EnumValue` | 复合属性值 |
| `TextValue` / `DelegateValue` | 特殊属性值 |
| `ParseResult` / `StatusInfo` | 解析结果/状态 |

## 蓝图模型

| 模型 | 说明 |
|------|------|
| `BlueprintMetadata` | 蓝图元数据（变量、函数、事件） |
| `BlueprintVariable` | 蓝图变量 |
| `BlueprintFunction` | 蓝图函数 |
| `BlueprintEvent` | 蓝图事件 |
| `FunctionParameter` | 函数参数 |

## 变换模型

| 模型 | 说明 |
|------|------|
| `VectorValue` | 三维向量 (X, Y, Z) |
| `RotatorValue` | 旋转 (Pitch, Yaw, Roll) |
| `ScaleValue` | 缩放 (X, Y, Z) |
