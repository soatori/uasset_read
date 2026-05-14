# Phase 18: Pin序列化解析 - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

解析Pin二进制数据，构建高层JSON结构（不暴露字节细节）。Phase 18专注于修正LinkedTo/SubPins/ParentPin解析顺序、添加缺失字段（PinToolTip/DefaultObject/DefaultTextValue）、解析Flags bit位为命名字段、整理JSON输出格式。

**Requirements:** PIN-01~05 (pin基础信息、PinType、默认值、连接引用、显示属性)

**范围锚点：** 仅修复和增强Pin解析，不添加新的节点类型处理或蓝图功能扩展。

</domain>

<decisions>
## Implementation Decisions

### LinkedTo解析修正
- **D-18-01:** LinkedTo解析修正顺序 — 先读OwningNode引用(FPackageIndex int32)再读PinId(FGuid 16字节)，符合UE源码EdGraphPin.cpp第1838-1964行序列化顺序
- **D-18-02:** LinkedTo输出格式为结构化对象 `{"node": "NodeName", "pin_id": "GUID"}`，符合REQUIREMENTS PIN-04规范
- **D-18-08:** LinkedTo引用失败处理 — 输出原始FPackageIndex值 + 记录警告到ParseResult.errors

### SubPins与ParentPin解析
- **D-18-09:** SubPins解析修正顺序 — 与LinkedTo相同处理：先读ParentNode引用再读PinId，输出结构化对象
- **D-18-10:** ParentPin添加节点引用 — 输出结构化对象 `{"node": "...", "pin_id": "..."}`

### Flags bit位解析
- **D-18-03:** Flags bit位解析为命名字段 — hidden, not_connectable, advanced_view, orphaned
- **D-18-11:** 输出所有flags字段 — 包括default_value_is_read_only, default_value_is_ignored

### 缺失字段处理
- **D-18-04:** 缺失字段完整实现 — PinToolTip (FString)、DefaultObject (UObject引用)、DefaultTextValue (FText)
- **D-18-12:** PinToolTip空值输出null而非省略
- **D-18-13:** DefaultObject保留FPackageIndex索引 + 添加object_name字段输出解析后的对象名
- **D-18-14:** DefaultTextValue解析为字符串，空值输出null

### JSON输出整理
- **D-18-05:** 清理内部字段 — 移除linked_to_raw、auto_default_value、flags(uint8)等内部字段
- **D-18-06:** PinType结构保持现有格式 — category, sub_category, sub_category_object, container_type, is_reference, is_const
- **D-18-07:** Direction输出为语义化字符串 — "input", "output", "none"
- **D-18-15:** Pin JSON分组结构输出 — 基础信息(id/name/direction)、类型信息(pin_type)、默认值(default_*)、连接(linked_to/sub_pins/parent_pin)、显示属性(flags)；仅输出非空字段
- **D-18-16:** PinId输出为UE标准GUID格式 — 带分隔符：`13FD260E-4EE1-8FD0-AA5F-7085F9B509D6`

### Claude's Discretion
- 确切分组字段顺序
- 非空字段判断阈值（空字符串 vs null）
- 警告信息格式

</decisions>

<specifics>
## Specific Ideas

**UE源码参考关键点：**
- EdGraphPin.cpp第1838-1964行：UEdGraphPin::Serialize完整序列化顺序
- EdGraphPin.cpp第2298-2325行：ExportText_PinReference/ExportText_PinArray格式
- LinkedTo格式：`LinkedTo=(NodeName GUID,)` — 节点名+空格+GUID

**测试资产验证：**
- BP_FirstPersonCharacter.uasset (UE 5.7)
- 验证Jump执行流程连接：IA_Jump → Jump → StopJumping

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### UE 5.7 源码参考（只读）
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Private\EdGraph\EdGraphPin.cpp` — Pin序列化核心（第1838-1964行Serialize函数，第2298-2325行ExportText_PinReference格式）
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Public\EdGraph\EdGraphPin.h` — UEdGraphPin结构定义（第76-225行）

### 项目研究文档
- `.planning/research/UE_TEXT_FORMAT_SOURCE.md` — UE文本格式生成源码研究（完整调用链、序列化顺序、输出格式）
- `.planning/REQUIREMENTS.md` — v4.0需求定义（PIN-01~05规范，输出设计原则）
- `.planning/ROADMAP.md` — Phase 18目标和Success Criteria（第77-88行）

### Prior Phase Context
- `.planning/phases/17-property-parsing-fix/17-CONTEXT.md` — Phase 17偏移计算修复、属性解析基础

</canonical_refs>

<code_context>
## Existing Code Insights

### 需修改的位置
1. **`read_ue_graph_pin()` (第2577-2687行)** — LinkedTo/SubPins解析逻辑需修正顺序
2. **`UEdGraphPin` dataclass (第1208-1225行)** — 添加缺失字段：pin_tool_tip, default_object_index, default_text_value
3. **`build_connections_map()` (第4755行)** — 使用修正后的linked_to数据

### 已实现可复用
- `read_ed_graph_pin_type()` (第2496-2574行) — PinType解析完整，无需修改
- FArchive.read_bool() — Bool读取正确（Phase 16修复）
- FGuid hex转换 — 现有pin_id_bytes.hex()逻辑

### Integration Points
- Pin解析入口：`read_ue_graph_node()`调用`read_ue_graph_pin()`循环
- 输出格式化：format_json_pin()需更新以清理内部字段
- 连接映射：build_connections_map()使用新的linked_to结构

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Phase 19将处理连接关系重建，Phase 20整合输出。

</deferred>

---

*Phase: 18-Pin序列化解析*
*Context gathered: 2026-05-04*