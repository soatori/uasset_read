# Blueprint 语义 JSON 输出设计

日期：2026-08-11

状态：已通过对话设计评审，等待书面规格复核

目标格式：`uasset_read.blueprint_semantic` `1.0.0`

## 1. 目标

为 Blueprint `.uasset` 提供一套适合 Agent 读取的紧凑语义 JSON。输出应优先表达：

- Blueprint 资产身份和继承关系；
- Graph、节点、数据 Pin 和执行端口；
- 函数、事件、变量、组件及其可靠来源；
- 完整的控制流和数据流；
- 复杂类型、有效默认值和已确认引用；
- 解析缺口及其影响范围。

输出不以还原编辑器界面为目标。节点坐标、原始 GUID、包表、偏移和完整原始属性只属于 debug 证据。C++ 风格翻译以后由 Markdown 报告生成，不进入本 JSON。

## 2. 范围

本设计只冻结 Blueprint 语义输出。非 Blueprint 资产继续使用现有 PackageIR 输出，后续单独设计，不能与本格式共用 Schema 或依靠字段形状猜测格式。

本设计不包含：

- 文件拆分、分页或按 Graph 外置；
- 第二套 compact Schema；
- JSON 内的 C++ 伪代码；
- 推测性连线或推测性 Blueprint 翻译；
- 无限制的 debug 原始包转储；
- 默认截取前 N 个节点的有损摘要。

## 3. 输出档位

只支持：

- `standard`：紧凑、确定、以语义为主；
- `debug`：与 standard 同构，在原位置增加可追溯证据。

debug 的严格超集通过投影不变量定义：

```text
project_debug(debug_document) == standard_document
```

`project_debug` 只能：

1. 将顶层 `mode` 规范化为 `standard`；
2. 删除 Schema 明确标记为 debug-only 的 `evidence` 或 `extensions`；
3. 按 standard 规则省略由此产生的空证据字段。

debug 不得增加、删除、替换或重排 standard 的 Graph、Node、Pin、Port、Flow、Type、Variable、Component、Coverage 或聚合 Diagnostic。解析只执行一次，档位仅影响证据渲染。

## 4. 顶层结构

```json
{
  "$schema": "uasset-read://blueprint-semantic/1.0.0/schema.json",
  "format": "uasset_read.blueprint_semantic",
  "format_version": "1.0.0",
  "mode": "standard",
  "asset": {
    "package": "/Game/Blueprints/BP_MyActor",
    "name": "BP_MyActor",
    "kind": "blueprint",
    "generated_class": "BP_MyActor_C",
    "parent_class": "/Script/Engine.Actor",
    "saved_by_engine": "5.4.0"
  },
  "types": {},
  "symbols": {},
  "constants": {},
  "variables": [],
  "components": [],
  "graphs": [],
  "coverage": [],
  "diagnostics": []
}
```

除必需头、`asset` 和 `graphs` 外，空的顶层集合省略。不得输出可由数组直接计算的 `NodeCount`、Pin 数量、边数量或 Graph 名称摘要。

## 5. ID、引用与确定性

- Graph ID 使用可读的 Blueprint URI，例如 `blueprint://graph/EventGraph`。
- Node ID 使用 `blueprint://graph/<Graph>/<Kind>/<Name>/<Ordinal>`，例如 `blueprint://graph/EventGraph/node/call/SetActorLocation/0`。
- 数据 Pin 和控制 Port 使用所属 Node 的语义端点 ID，例如 `input.Target`、`input.NewLocation`、`exec.in` 和 `exec.out`。
- Type、Symbol、Constant 和 Component ID 在对应顶层表中唯一，例如 `t0`、`s0`、`k0`、`c0`。
- 局部 ID 仅对当前文档有效，不是跨版本持久标识。
- 所有本地引用必须闭合，不允许悬空。
- 跨资产引用使用带 `kind` 的外部引用和规范对象路径，不能伪装为本地 ID。

节点 ID 的 `<Graph>`、`<Kind>` 和 `<Name>` 使用 ASCII slug；原始名称保留在 `name` 或 `label`，不能因 slug 化丢失语义。`<Ordinal>` 从零开始，按确定性的序列化源顺序分配，用于区分同一 Graph 中相同类型和名称的节点。缺少语义名称时使用已确认的源类型名；不得使用坐标或推测名称。

实现校验使用以下约束：`Graph ID` 匹配 `^blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*$`；`Node ID` 匹配 `^blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*/node/[a-z][a-z0-9-]*/[A-Za-z][A-Za-z0-9_.-]*/[0-9]+$`；端点 ID 必须匹配 `input.<Name>`、`output.<Name>` 或 `exec.<Role>`。名称不能包含 `/`、空格或未转义 URI 保留字符。

节点 ID 是当前文档内的可读引用，不是跨版本持久身份。原始 Unreal GUID 不作为普通 Flow 引用；如果可靠读取，应放在 `source.guid` 作为精确追溯证据。GUID 使用单一规范：四个 UE `FGuid` 分量按原顺序拼接为 32 个十六进制字符，禁止在实现中混用 `System.Guid` 的字节序转换。无法读取 GUID 时不得伪造；可保留语义 ID 并产生对应 coverage/diagnostic。

规范节点 ID 示例：

```text
blueprint://graph/EventGraph/node/event/BeginPlay/0
blueprint://graph/EventGraph/node/branch/IsValid/0
blueprint://graph/EventGraph/node/call/SetActorLocation/0
blueprint://graph/Function_TakeDamage/node/variable-set/Health/0
```

Pin/Port 端点示例：

```text
blueprint://graph/EventGraph/node/call/SetActorLocation/0/pin/exec.in
blueprint://graph/EventGraph/node/call/SetActorLocation/0/pin/input.NewLocation
```

ID 只允许 ASCII 字符；Graph、Node、Pin 和 Port 的显示名称单独保留，供人和 Agent 阅读。普通模式不输出坐标、原始 Export 名称或完整调试属性；debug 可在同一语义对象下增加 `source.guid`、`source.export_name`、序列化索引和原始名称。

同一输入字节、解析器版本、配置和限制必须产生字节一致输出。无语义顺序的集合按规范键排序；参数、Sequence、Switch case、多链接执行顺序等有语义顺序的集合保留源顺序并输出 `ordinal`。JSON 使用 UTF-8、LF、固定键顺序和有限浮点编码，禁止 NaN/Infinity。

## 6. Graph 是唯一实现源

```json
{
  "id": "blueprint://graph/EventGraph",
  "name": "EventGraph",
  "kind": "event_graph",
  "nodes": [],
  "control_flow": {},
  "data_flow": {}
}
```

`kind` 至少支持 `event_graph`、`function`、`macro`、`construction_script` 和 `collapsed_graph`。

不在顶层重复输出 `functions`、`events` 或另一套函数实现：

- 事件是 Event Graph 的入口节点，并出现在 `control_flow.entries`；
- 函数参数由 `function_entry` 节点表达；
- 函数结果由全部 `function_result` 节点表达；
- 函数局部变量仅在 `FunctionEntry.LocalVariables` 或可靠编译属性证实时输出；
- 宏和折叠图通过已确认 Graph 引用和端口绑定关联，不同时展开为第二份实现。

函数 Graph 必须只有一个规范入口，可有多个结果节点。所有结果节点的公共签名必须兼容；不兼容时保留节点、标记签名 coverage，并产生聚合诊断。

## 7. Node

```json
{
  "id": "blueprint://graph/EventGraph/node/call/SetActorLocation/0",
  "label": "调用 SetActorLocation",
  "kind": "call",
  "status": "recognized",
  "symbol": "s0",
  "execution": {"model": "immediate"},
  "data_pins": {
    "input.Target": {"name": "Target", "direction": "input", "type": {"$type": "t1"}},
    "input.NewLocation": {"name": "NewLocation", "direction": "input", "type": {"$type": "t0"}},
    "input.bSweep": {"name": "bSweep", "direction": "input", "type": "bool"}
  },
  "control_ports": {
    "exec.in": {"name": "execute", "direction": "input", "role": "execute"},
    "exec.out": {"name": "then", "direction": "output", "role": "then"}
  },
  "defaults": {"input.bSweep": false}
}
```

常见 `kind` 包括 event、custom_event、function_entry、function_result、call、variable_get、variable_set、branch、switch、sequence、macro、cast、make_struct、break_struct、delegate_bind、delegate_unbind、delegate_call、literal 和 reroute。

`status` 语义为：

- `recognized`：语义类别和关键引用已确认；默认值，可省略；
- `partial`：已确认部分语义，保留 `source_type` 和缺失能力；
- `opaque`：自定义或插件节点，只保留 `source_type`、确认引用、Pin、Port 和全部确认连线。

节点可输出 `enabled_state: enabled | disabled | development_only`。默认 `enabled` 省略。disabled、development-only、orphaned 或 non-compiling 连接不得进入普通可执行 Flow；它们只以明确状态或 debug 证据出现。

`execution.model` 仅在可靠证据存在时输出，允许 `immediate`、`latent`、`async_callback`、`event_source` 和 `stateful`。控制边的 `transition` 可为 `immediate`、`resume` 或 `callback`。不得因端口名为 `Completed` 而推断 latent 或 async。

已识别引用角色包括 struct_type、enum_type、target_type、member、object、class、function、macro_graph 和 asset。`target`、`refs`、`symbol` 均使用封闭的判别结构，不接受任意裸字符串。

## 8. 数据 Pin

数据 Pin 与执行 Port 分离。数据 Pin 声明至少包含 ID、原始语义名称、图方向和类型；按需增加：

- `path`：拆分结构路径的 segment 数组；
- `access: read | write | read_write`；
- `signature_role: parameter | return`；
- `parameter_mode: in | out | inout`；
- `type_var`、`resolved_type` 和 `resolution`；
- delegate、selector、container 或 alias/pass-through 语义。

图方向始终表示 Blueprint Pin 方向；API 参数方向由 `signature_role` 和 `parameter_mode` 表示。FunctionEntry 的图输出可以是 API 输入，FunctionResult 的图输入可以是 API out/return。

保留：

- 所有数据流端点；
- 有有效默认值的输入 Pin；
- 公共函数/事件签名 Pin；
- ref、out、delegate、wildcard、selector、container Pin；
- 对语义有影响的 hidden Pin。

省略未连接、无默认值且不承担签名或类型约束的 Pin。Advanced/UI 标记只进 debug。

拆分结构使用 `path: ["Transform", "Location", "X"]`，不使用点号拼接。连接权威性位于叶 Pin；未连接兄弟字段的默认值仍参与结构体组装。debug 在保留同一扁平 Pin 集的同时，通过 `evidence.pin_tree` 记录 ParentPin/SubPins 关系，不复制完整类型和连线。

Wildcard 保留声明态 `wildcard`、类型变量和已确认 resolved type，不能用解析后的类型覆盖声明态。Map 的 key/value wildcard 可以属于不同类型变量。

`ReferencePassThroughConnection` 和可靠 reroute 折叠用 alias/pass-through 关系表达，不伪造普通数据边。语义层是否折叠 reroute 在 standard/debug 中必须完全一致；debug 可在 evidence 中保留原始物理节点和两段连接。

Orphaned Pin 只有在需要说明残留连接或默认值时保留，并标记 non-compiling；其默认值不是运行时 `defaults`。

## 9. 控制流

```json
"control_flow": {
  "entries": [{"node": "blueprint://graph/EventGraph/node/event/BeginPlay/0", "port": "exec.out"}],
  "edges": [
    {
      "from": {"node": "blueprint://graph/EventGraph/node/event/BeginPlay/0", "port": "exec.out"},
      "to": {"node": "blueprint://graph/EventGraph/node/call/SetActorLocation/0", "port": "exec.in"},
      "transition": "immediate",
      "ordinal": 0
    }
  ]
}
```

每条执行边同时引用源和目标 Port。Port 独立声明，即使未连接也可保留语义重要端口：Switch 的空 case、Sequence 输出、Gate/MultiGate/Loop 的入口和出口。

- Branch 端口 role 使用 true/false；
- Switch 保留 selector 类型、类型化 case、default port、case 顺序和字符串大小写规则；
- Sequence、MultiGate 和有序 fan-out 使用 ordinal；
- Loop、Gate、DoOnce 等 stateful 语义只来自已识别节点或已解析宏；
- latent continuation 使用 resume；
- async delegate callback 使用 callback；
- Broadcast 不生成到潜在监听事件的静态控制边；
- 同一源端口存在多个有效链接时保留源执行顺序。

宏实例通过目标 Graph 引用和实例 Port 到 Tunnel Port 的 bindings 表达。目标图不可解析时实例为 partial，不按显示名猜测内部循环或状态行为。

## 10. 数据流

```json
"data_flow": {
  "edges": [
    {
      "from": {"node": "blueprint://graph/EventGraph/node/variable-get/TargetLocation/0", "pin": "value"},
      "to": {"node": "blueprint://graph/EventGraph/node/call/SetActorLocation/0", "pin": "input.NewLocation"}
    }
  ]
}
```

LinkedTo 的双向序列化只生成一条规范边。边身份是完整的两个端点，不能因节点相同而合并。只允许 output 到 input 的有效连接；mutable ref/inout 的写回语义由 Pin `access` 和 alias 关系补充。

解析失败、同名猜测、候选匹配和孤立 GUID 不得生成权威边。debug 可以在 `evidence.hypotheses` 中记录候选，但必须标记 `confirmed: false`。

## 11. 类型系统

`TypeRef` 是严格联合：

- 基础类型枚举字符串，如 `bool`、`int`、`float`、`string`、`name`；
- 复杂类型引用，如 `{"$type":"t0"}`。

顶层 `types` 只定义实际使用的复杂类型。对象键就是 Type ID，条目不重复输出 `id`；每项具有 `kind` 和规范限定身份。支持：

- struct、enum、object、class、interface、delegate；
- array、set、map；
- ref、const、soft、weak、lazy、optional、fixed_array、field_path；
- UObject wrapper、bitmask enum、single/multicast delegate。

object 保存 PropertyClass；class 同时保存类对象类型和 MetaClass；interface 保存接口类；delegate 保存签名和 single/multicast；enum 保存身份、underlying type 和枚举项完整性；用户结构体使用规范路径，不启发式剥离 GUID。

Map 明确定义：主 `FEdGraphPinType` 是 key，`PinValueType` terminal 是 value。value terminal 的 const、weak 和 UObject wrapper 不能丢失，也不能误解为第二层容器。

容器和修饰符采用唯一规范嵌套顺序。递归命名类型通过名义 Type ID 成环，不用递归内容哈希建立身份。所有 `$type` 必须闭合；未解析目标产生类型 coverage 和诊断，不能降级成无约束 object。

Set 按元素规范编码排序；Map 用 entry 数组表达并按 key 的规范编码排序；struct 字段按声明顺序；array 保持运行时顺序。

## 12. 默认值

`nodes[].defaults` 是输入 Pin ID 到 `RuntimeValue` 的映射。只有未连接、未 ignored、可确认的运行时输入值才出现。

选择算法：

1. 只处理数据输入 Pin；
2. 存在确认入边时省略残留默认值；
3. `bDefaultValueIsIgnored=true` 时不进入语义默认值；
4. scalar/string/name/enum/struct/container 优先解析 `DefaultValue`；
5. object/class/interface/soft/weak 优先解析 `DefaultObject`，再接受可验证路径或 None；
6. text 优先解析结构化 `DefaultTextValue`；
7. `AutogeneratedDefaultValue` 仅作为 debug 比较证据；
8. `false`、`0`、空字符串和空容器按字段存在性保留，不能用 truthiness 判断。

`FBPVariableDescription.DefaultValue == ""` 不能直接解释为显式空字符串；它与 Pin 的实际空字符串默认值语义不同。

复杂值使用判别 wrapper，例如 enum、object、null、struct、text 和 raw。FText 区分 localized、invariant、string_table 和 raw history。无法解析的值使用有界 raw wrapper，包含 expected type、格式、原始长度、保留内容、是否截断及截断时的稳定摘要；不能退化成普通字符串。

## 13. 变量、函数和委托

变量采用逐字段来源矩阵：

- 身份：VarGuid 优先，规范名次之；
- Blueprint 声明：NewVariables；
- 编译后类型、PropertyFlags 和复制信息：GeneratedClass 自身声明的 FProperty；
- 运行时类默认值：CDO 中实际存在的值；
- 继承变量：仅在父声明链确认后输出。

CDO 缺少字段表示未序列化差异，不表示 null、零值或继承值。来源冲突按固定优先级选择 standard 值，输出 `VARIABLE_SOURCE_CONFLICT`，debug 保留全部证据。普通 PropertyFallback 不得被猜测为 Blueprint 变量。

函数签名联合 FunctionEntry、全部 FunctionResult 和 UFunction/FProperty 声明。ref/out/inout/return/const 优先由 `CPF_Parm`、`CPF_OutParm`、`CPF_ReturnParm`、`CPF_ReferenceParm` 和 `CPF_ConstParm` 确认。调用节点默认参数是本次调用值，不是函数声明默认参数。

函数、变量 flags 只有在对应来源完整时才可解释。standard 使用紧凑规范 flag 名集合；当 flag scope coverage 完整时，列表中缺失表示 false；来源不完整时输出 coverage partial，不能把缺失解释为 false。debug 额外保存固定宽度十六进制 raw mask 和未知位。

Override、interface implementation 和同名新函数必须通过 owner、父类链或 ImplementedInterfaces 证实。RPC 和 replication 使用稳定语义枚举；未知原始值不能映射为 none。RepNotify 只有在 flag 和有效函数名同时成立时输出。

Delegate type 包含签名和 single/multicast。节点 operation 区分 create、bind、add、remove、assign、clear 和 broadcast。CreateDelegate 保留 handler 和目标对象；事件 OutputDelegate 作为普通数据 Pin 保留。

## 14. Components 与 SCS

```json
{
  "id": "c0",
  "name": "Mesh",
  "type": {"$type": "t10"},
  "origin": "scs_owned",
  "parent": "c1",
  "socket": "WeaponSocket",
  "transform": {"location": [0, 0, 50]},
  "properties": {
    "mode": "effective",
    "values": {"StaticMesh": {"object": "/Game/..."}}
  }
}
```

来源规则：

- `scs_owned`：当前类 SimpleConstructionScript → USCS_Node → ComponentTemplate；
- `scs_inherited`：父类 SCS 加 InheritableComponentHandler override；
- `native`：native 类/CDO default subobject 或明确 native-parent 证据；
- BlueprintGeneratedClass.ComponentTemplates：仅关联动态 AddComponent 节点，不进入静态 components。

Parent、owner、native-parent 标记和 AttachToName 共同决定父子与 socket；不得按名称猜测。组件父引用必须闭合且层级无环。支持 ComponentClassOverrides，避免子 Blueprint 替换组件类后仍输出父类类型。

`properties.mode: delta` 只有在存在可标识 baseline 时允许，并必须记录 baseline kind、引用和稳定 identity；删除或重置属性显式表达。没有完整模板/CDO/archetype 基线时使用 `effective`，字段缺失表示未观测，组件 coverage 必须标记不完整。

ChildActorComponent 只记录 child actor class，不展开子 Actor 组件。Construction Script 的 AddComponent、Spawn 和属性 Setter 保留为 Graph 节点，不折叠进静态组件，也不根据循环展开固定实例数量。

## 15. Standard 压缩和去重

压缩优先消除结构重复，不删除执行语义。

### 15.1 稀疏字段

省略：

- null、空数组、空对象和空备注；
- recognized、enabled 等规范默认状态；
- 未使用 UI 标记和坐标；
- 可计算 count；
- 未发生的 coverage 和 diagnostics。

`false`、`0`、空字符串、确认 null 等运行时值不属于“空字段”，必须保留。

### 15.2 Types

复杂类型全局只定义一次。基础类型直接内联，避免短值索引反而变长。

### 15.3 Symbols

重复至少两次的函数、变量、事件、委托和宏声明进入 `symbols`。对象键就是 Symbol ID，条目不重复输出 `id`。Symbol 保存 owner、member、dispatch kind 和稳定端口签名。只出现一次的目标可以内联，避免索引反而增加长度。

调用节点使用 `symbol` 后，Symbol 的 Pin/Port slot ID 自动进入该 Node 的局部端点命名空间；Flow 仍使用 `{node,pin}` 或 `{node,port}` 引用。节点不重复声明与 Symbol 完全一致的端点，只在 `pin_overrides`、`port_overrides` 和本地 `data_pins`、`control_ports` 中表达动态新增、split、wildcard 解析、隐藏语义 Pin 或其他实例差异。合并后的有效端点必须唯一且可由 semantic validator 机械计算。

本地函数 Symbol 可以引用实现 Graph；Symbol 是声明契约，不是第二份实现。

### 15.4 Constants

规范编码后较大且至少重复两次的完全相同 struct/container 值进入可选 `constants`。短字符串、数字和 bool 不 intern。阈值由格式配置固定并进入确定性输入；debug evidence 记录实际配置。

### 15.5 大型唯一值

大型且不重复的 literal、容器或 raw payload 使用有界 wrapper：

```json
{
  "$large": {
    "type": "array",
    "count": 12000,
    "original_bytes": 48000,
    "sha256": "...",
    "preview": []
  }
}
```

有界化必须同时产生对应 truncated coverage 和稳定 diagnostic。Graph、Node、Pin、Port、control flow、data flow 不得仅因 standard 输出长度主动截断。解析器安全限制一旦触发，也必须进入 coverage，且删除所有指向被裁对象的悬空引用。

### 15.6 文本布局

standard 使用紧凑可读 JSON：顶层、Graph 和 Node 分层换行，小型 Pin、Port、Edge、TypeRef 和 Diagnostic 叶对象尽量单行；使用紧凑分隔符但不完全 minify。该布局只影响文本，不改变数据契约。

## 16. Coverage 与 Diagnostics

Coverage 描述“损失了什么”，Diagnostic 描述“为什么”。两者不复制长消息。

`coverage` 只记录非 complete scope：

```json
{
  "scope": "graph:blueprint://graph/EventGraph/nodes",
  "status": "truncated",
  "reason": "max_nodes",
  "declared": 6000,
  "emitted": 4096,
  "omitted": 1904
}
```

状态为 `partial | unavailable | truncated`。v1 固定按 asset kind 适用的 coverage scope；coverage 整体省略才表示全部适用 scope complete。不适用 scope 不输出。字段适用且 coverage 非完整时，字段缺失表示 unknown；coverage 完整时，缺失才表示自然为空或不存在。JSON null 只表示确认的运行时 null。

Blueprint v1 的规范 scope 包括：`asset`、`types`、`symbols`、`variables`、`components`、`graphs`，以及每个 Graph 的 `nodes`、`signature`、`locals`、`control_flow`、`data_flow`。某 Graph kind 不具有 signature 或 locals 时对应 scope 不适用。`constants` 只在发生值提取时适用；`diagnostics` 和 debug `evidence` 只在各自缓冲或限制实际启用时适用。实现可以增加更细的子 scope，但不能用新子 scope 改变上述父 scope 的 complete 含义；新增强制顶层 scope 属于格式版本变化。

总数已知时 `declared = emitted + omitted`；未知时不伪造计数。使用最小受影响 scope，避免祖先和后代重复覆盖。source/parser truncation、renderer truncation 和 debug evidence truncation 必须区分。

standard diagnostic 结构稳定聚合：

```json
{
  "code": "BP_LINK_UNRESOLVED",
  "scope": "graph:blueprint://graph/EventGraph/data_flow",
  "severity": "warning",
  "effect": "semantic_loss",
  "count": 3
}
```

聚合键固定为 code、canonical scope、severity 和 effect/recovery。message 不参与身份。debug 在同一项增加有序 `evidence.occurrences`，不能替换聚合项。诊断缓冲区自身丢项时，diagnostics scope 必须标记 truncated。

## 17. Debug evidence

debug 可在相应语义对象旁增加 `evidence`，包括：

- Package summary、NameMap、imports、exports；
- 原始 GUID、PinId、坐标和序列化顺序；
- PinCategory/SubCategory/SubCategoryObject、container terminal flags；
- DefaultValue、DefaultObject、DefaultTextValue、AutogeneratedDefaultValue；
- ParentPin/SubPins 树；
- SCS、InheritableComponentHandler、ComponentTemplate 和 CDO 比较来源；
- raw PropertyFlags/FunctionFlags 十六进制值；
- 原始引用、offset、recovery 和未确认 hypotheses；
- active limits 和扩展字段。

debug 不是无限输出。证据达到限制时，同样产生 coverage 和 diagnostic。扩展只允许放入 debug-only `extensions`，使用受控命名空间，不能影响 standard 语义。

## 18. 校验

格式同时提供：

1. JSON Schema Draft 2020-12：字段类型、判别联合、mode 条件和封闭对象；
2. semantic validator：ID 唯一、引用闭包、边方向、默认值/连接互斥、类型闭包、组件无环、Graph 签名一致、delta baseline 和 debug 投影等式。

通过 Schema 不是充分条件，二者都通过才是有效文档。

## 19. 验收测试

契约测试至少覆盖：

- standard/debug 投影逐值和逐顺序相等；
- 同一输入和不同容器插入顺序下输出字节确定；
- dangling node/pin/port/type/component 引用被拒绝；
- 截断计数、摘要和引用完整性；
- 字段缺失与 coverage 联合解释；
- branch、switch、sequence、loop、Gate、latent、async 和多入口事件；
- split Pin、wildcard type variables、pass-through、orphaned/disabled；
- Map 复杂 key/value 和 terminal 修饰；
- false、0、空字符串、null、FText、stale connected defaults；
- ref/out/inout/return、多 FunctionResult；
- delegate/multicast、interface implementation、parent override、RPC 和 RepNotify；
- SCS owned/inherited override、native component、class override、ChildActor 和动态 AddComponent template；
- 重复 Symbol、Type、Constant 去重以及大型唯一值有界化。

真实资产验收必须通过公开解析入口生成 standard/debug 文件，并检查实际文件大小、重复率、语义 validator 和关键 Graph 连线，不能只依据单元测试或提交记录判断完成。

## 20. 实施边界

实现应建立一个与渲染档位无关的 Blueprint Semantic IR，再分别投影为 standard 和 debug。解析器不得直接按档位丢失语义对象。

当前已有提取器中存在若干不能直接沿用的边界：Pin 自身 ID 字段读取不一致、失败连接被折叠为空、Map terminal 命名可能误导 key/value、普通 PropertyFallback 被推测为变量、组件尚非完整 SCS 解析。实施计划必须逐项建立可验证来源和回归资产，不能用 Schema 包装现有不可靠数据后宣称完成。
