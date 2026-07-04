# JSON 输出格式

uasset_read 解析器的标准 JSON 输出由 `JSONRenderer` 生成，描述 `.uasset` 文件解析后的完整结构。

## Schema

输出格式的 JSON Schema 定义在 [`schemas/package.schema.json`](../../../schemas/package.schema.json)。

## 顶层结构

```jsonc
{
  "$schema": "...",                     // Schema 引用（仅 include_schema=True 时）
  "status": { "status": "success" },    // 解析状态
  "summary": { ... },                   // 包头摘要（FPackageFileSummary）
  "exports": [ ... ],                   // 导出对象列表
  "blueprint": { ... },                 // 蓝图元数据（可选）
  "variables": [ ... ],                 // 蓝图变量列表（可选）
  "decompiled_functions": [ ... ],      // 反编译函数列表（可选）
  "execution_chains": [ ... ],          // 执行链列表（可选）
  "anim_blueprint": { ... },            // 动画蓝图数据（可选）
  "anim_sequence": { ... },             // 动画序列数据（可选）
  "anim_montage": { ... }               // 动画蒙太奇数据（可选）
}
```

## 主要字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | object | 解析状态（`success` / `partial` / `failed`） |
| `summary` | object | 包头信息：包名、类名、标志位、导入/导出计数、UE 版本 |
| `exports` | array | 导出对象列表，每个包含名称、类、序列化大小、属性、图 |
| `blueprint` | object | 蓝图父类、描述、接口、函数、事件、组件 |
| `variables` | array | 蓝图变量：名称、类型、种类、默认值、属性标志 |
| `decompiled_functions` | array | 反编译函数：签名、C++ 代码、参数、返回类型 |
| `execution_chains` | array | 执行链：事件名 + 节点 GUID 序列 |

## 导出对象内部结构

每个 export 包含：

- **object_name** / **object_class** / **serial_size** — 基本标识
- **properties** — 属性列表（name, type, value, array_index）
- **graphs** — 图列表，每个图包含：
  - `graph_name` / `graph_guid` / `graph_type`
  - `nodes` — 节点列表，每个节点包含 `node_guid`、`node_class`、`pins`、`execution_flow`
  - `execution_chains` — 执行链（node GUID 序列数组）
  - `subgraphs` — 递归子图

## 蓝图相关字段

`blueprint.functions` 和 `blueprint.events` 共享以下结构：

- **name** / **return_type** / **parameters** — 基本签名
- **implementation_status** — `decompiled` / `graph_only` / `metadata_only` / `missing`
- **function_graph** — 函数图数据（与 export 中 graph 结构相同）

## 动画数据

- **anim_blueprint** — 烘焙状态机、动画通知、同步组
- **anim_sequence** — 序列时长、速率缩放、通知、浮点曲线
- **anim_montage** — 混合模式、同步组、通知、浮点曲线
