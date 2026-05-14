# Phase 19: 连接关系重建 - Research

**Researched:** 2026-05-04
**Domain:** 节点连接关系构建（执行流、数据流、控制流）
**Confidence:** HIGH

## Summary

Phase 19专注于构建节点间连接图，输出清晰的执行流和数据流结构。研究基于UE源码EdGraphPin.cpp（第1838-1964行）的Pin序列化结构验证，以及现有代码build_connections_map()（第4990-5039行）、build_execution_flows()（第5180-5225行）的实现分析。

核心任务包括：
1. **LINK-01**：构建connections数组，支持name模式输出
2. **LINK-02**：扩展execution_flows起点类型（EnhancedInputAction、VariableSet、CustomEvent）
3. **LINK-03**：新增data_flows构建函数，处理非exec pins数据流

现有代码已实现基础框架（pin_lookup表构建、循环检测、控制流停止），Phase 19主要进行格式调整和功能扩展。

**Primary recommendation:** 扩展现有函数，避免重写核心算法。复用pin_lookup/node_lookup查找表模式，添加name格式转换层和起点类型识别逻辑。

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 连接引用解析 | 数据解析层 | — | 从linked_to_raw二进制数据构建连接关系 |
| 执行流追踪 | 数据解析层 | — | 沿exec pin连接构建执行链路图 |
| 数据流构建 | 数据解析层 | — | 从非exec pins提取数据传递关系 |
| 控制流标记 | 数据解析层 | — | 检测分支节点并标记branch_type |
| 格式输出 | 输出格式层 | — | 转换为用户友好JSON结构 |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### 连接引用格式
- **D-19-01:** Node引用保留node_guid格式 — 稳定可靠，现有代码已实现
- **D-19-02:** Pin引用使用pin_name格式 — 用户友好，需统一修改Phase 18输出
- **D-19-03:** 连接输出格式全局可选配置 — 支持guid模式和name模式切换
- **D-19-04:** 默认输出模式为name模式 — 符合REQUIREMENTS示例格式
- **D-19-05:** 查找失败时保留原始pin_id作为fallback — 便于调试，附带warning字段

#### 数据流定义
- **D-19-06:** 数据流包含所有非exec pins — pin_type.category != "exec"的pins构成数据流
- **D-19-07:** data_flows输出结构为 `{source, target}` — 符合REQUIREMENTS LINK-03示例
- **D-19-08:** data_flows组织为扁平列表 — 每条数据流独立记录
- **D-19-09:** 数据流与执行流独立分离 — 不标记关联关系，各自分析

#### 执行流起点类型
- **D-19-10:** 执行流起点类型扩展 — K2Node_Event、K2Node_EnhancedInputAction、K2Node_VariableSet、K2Node_CustomEvent
- **D-19-11:** 起点标识统一使用start_event字段 — 所有起点类型统一处理
- **D-19-12:** EnhancedInputAction各触发时机分别追踪 — Started/Triggered/Completed独立执行链路

#### 控制流分支处理
- **D-19-13:** 控制流节点标记停止 — Branch/Switch等不继续追踪分支路径
- **D-19-14:** 控制流节点输出branch_type字段 — if_then_else/switch/switch_enum/switch_string/switch_integer/macro_instance
- **D-19-15:** 循环检测标记停止 — 检测到已访问节点时停止，标记cycle_detected=true

### Claude's Discretion
- branch_type字段的具体枚举值
- cycle_detected字段的输出位置（节点层级或执行流层级）
- name模式下节点名冲突的处理策略

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. Phase 20将处理整合输出，Phase 21验证测试。

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LINK-01 | 构建节点连接映射，输出connections数组（from/to节点+Pin） | 现有build_connections_map()基础，需添加name模式支持 |
| LINK-02 | 构建执行流图，从Event节点开始追踪执行链路 | 现有build_execution_flows()基础，需扩展起点类型 |
| LINK-03 | 构建数据流图，输出Pin间数据传递关系 | 需新增build_data_flows()函数，复用pin_lookup模式 |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.10+ | 主语言 | 项目核心语言，支持match/case和类型提示 |
| dataclasses | 标准库 | 数据结构 | 现有代码使用，支持asdict()输出 |
| typing | 标准库 | 类型系统 | 类型提示增强，IDE支持 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.x | 测试框架 | 验证连接关系构建逻辑 |
| struct | 标准库 | 二进制解析 | 已完成，Phase 19不涉及 |
| json | 标准库 | 输出格式 | 格式化connections/data_flows |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pin_id查找 | node_guid查找 | pin_id更稳定但不用户友好 |
| 执行流图对象 | 扁平链路列表 | REQUIREMENTS明确要求扁平结构 |

**Installation:**
无需新增依赖，使用现有Python标准库和pytest框架。

## Architecture Patterns

### System Architecture Diagram

```
linked_to_raw (dict格式)
    ↓
pin_lookup表构建（pin_id → (node_guid, pin_name)）
    ↓
    ├─→ build_connections_map()
    │     ├─ 遍历output pins
    │     ├─ 查找linked_to_raw中的目标pin
    │     ├─ 格式转换（name模式或guid模式）
    │     └─ 输出connections数组
    │
    ├─→ build_execution_flows()
    │     ├─ 识别起点节点（Event/EnhancedInputAction/VariableSet/CustomEvent）
    │     ├─ _trace_execution_from_event()追踪
    │     │     ├─ 循环检测（visited set）
    │     │     ├─ 控制流节点停止
    │     │     └─ 沿exec pin连接查找下一节点
    │     └─ 输出execution_flows数组
    │
    └─→ build_data_flows() [新增]
          ├─ 遍历所有pins（排除exec类型）
          ├─ 查找linked_to_raw中的数据目标
          ├─ 构建数据传递关系
          └─ 输出data_flows数组
```

### Recommended Project Structure

Phase 19修改集中在uasset_read.py的输出格式函数区域：

```
uasset_read.py
├── 第4980-5039行：build_connections_map() — 修改为支持name模式
├── 第5180-5225行：build_execution_flows() — 扩展起点类型识别
├── 第5228-5315行：_trace_execution_from_event() — 添加起点类型标记
├── 第5318-5330行：_get_event_name() — 扩展为_get_start_event_name()
├── 新增：build_data_flows() — 构建数据流
├── 新增：FORMAT_CONFIG全局配置 — name/guid模式切换
└── 第5060-5086行：format_graphs_json() — 添加data_flows输出调用

tests/test_output_formatting.py
├── 第795-828行：test_build_connections_map_* — 扩展name模式测试
├── 第846-895行：test_build_execution_flows_* — 添加起点类型测试
└── 新增：test_build_data_flows_* — 数据流构建测试
```

### Pattern 1: Pin Lookup Table构建

**What:** 从graph.nodes构建查找表，支持pin_id → (node_guid, pin_name)和pin_guid → (node_guid, pin_name)双向查找

**When to use:** 所有连接关系构建函数都需要使用查找表解析linked_to_raw中的Pin引用

**Example:**
```python
# 现有代码模式（build_connections_map L5009-5013）[VERIFIED: uasset_read.py]
pin_lookup: Dict[str, Tuple[str, str]] = {}
for node in graph.nodes:
    for pin in node.pins:
        pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

# Phase 18新格式支持（linked_to_raw为dict格式）
# 需要添加pin_guid → pin_id查找层
guid_to_id: Dict[str, str] = {}
for node in graph.nodes:
    for pin in node.pins:
        guid_to_id[pin.pin_id] = pin.pin_id  # pin_id即为FGuid hex
```

### Pattern 2: Name模式格式转换

**What:** 将内部node_guid + pin_name转换为用户友好的node_name + pin_name格式

**When to use:** D-19-04要求默认输出name模式，需在所有连接输出处添加转换层

**Example:**
```python
# REQUIREMENTS示例格式（LINK-01）
{
    "connections": [
        {
            "from": {"node": "K2Node_EnhancedInputAction_5", "pin": "Started"},
            "to": {"node": "K2Node_CallFunction_1193", "pin": "execute"}
        }
    ]
}

# 实现逻辑（添加node_name查找）
node_name_lookup: Dict[str, str] = {}
for node in graph.nodes:
    # 从导出表object_name或class_name派生节点名
    node_name_lookup[node.node_guid] = f"{node.class_name}_{idx}"

# 格式转换函数
def format_pin_ref(guid: str, pin_name: str, mode: str) -> dict:
    if mode == "name":
        return {"node": node_name_lookup[guid], "pin": pin_name}
    else:
        return {"node_guid": guid, "pin_name": pin_name}
```

### Pattern 3: 执行流起点识别

**What:** 扩展起点节点类型识别，从单一K2Node_Event扩展到4种类型

**When to use:** build_execution_flows()开始阶段，识别所有执行流起点

**Example:**
```python
# 现有代码（build_execution_flows L5210-5211）[VERIFIED: uasset_read.py]
event_nodes = [n for n in graph.nodes if n.class_name == "K2Node_Event"]

# Phase 19扩展（D-19-10）
START_EVENT_TYPES = frozenset({
    "K2Node_Event",
    "K2Node_EnhancedInputAction",
    "K2Node_VariableSet",
    "K2Node_CustomEvent"
})

start_nodes = [n for n in graph.nodes if n.class_name in START_EVENT_TYPES]
```

### Pattern 4: EnhancedInputAction触发时机追踪

**What:** 为EnhancedInputAction节点的不同触发时机（Started/Triggered/Completed）分别构建执行链路

**When to use:** D-19-12要求各触发时机独立追踪，需识别output exec pins并分别处理

**Example:**
```python
# K2Node_EnhancedInputAction典型pins结构
# Started (exec output) → 连接到Jump开始
# Triggered (exec output) → 连接到持续动作
# Completed (exec output) → 连接到结束动作

# 实现逻辑（D-19-12）
for node in graph.nodes:
    if node.class_name == "K2Node_EnhancedInputAction":
        # 遍历output exec pins，分别为每个触发时机构建执行流
        for pin in node.pins:
            if pin.direction == 1 and pin.pin_type.pin_category == "exec":
                # pin.pin_name即为触发时机（Started/Triggered/Completed）
                flow = _trace_execution_from_pin(node, pin, pin_lookup, node_lookup)
                execution_flows.append({
                    "start_event": f"{node.class_name}.{pin.pin_name}",
                    "nodes": flow
                })
```

### Pattern 5: 数据流构建

**What:** 从非exec pins提取数据传递关系，构建data_flows数组

**When to use:** 新增build_data_flows()函数，处理LINK-03需求

**Example:**
```python
# 实现逻辑（D-19-06/D-19-07）
def build_data_flows(graph: UEdGraph, mode: str = "name") -> List[Dict]:
    data_flows: List[Dict] = []
    
    # 复用pin_lookup模式
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    for node in graph.nodes:
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)
    
    # 遍历所有output pins，排除exec类型
    for node in graph.nodes:
        for pin in node.pins:
            if pin.direction == 1:  # Output
                if pin.pin_type and pin.pin_type.pin_category != "exec":
                    # 构建数据流关系
                    for linked_pin_id in pin.linked_to_raw:
                        # linked_to_raw为dict格式：{"owning_node": str, "pin_guid": str}
                        target_guid = linked_pin_id.get("pin_guid")
                        if target_guid in pin_lookup:
                            target_node_guid, target_pin_name = pin_lookup[target_guid]
                            data_flows.append({
                                "source": format_pin_ref(node.node_guid, pin.pin_name, mode),
                                "target": format_pin_ref(target_node_guid, target_pin_name, mode)
                            })
    
    return data_flows
```

### Anti-Patterns to Avoid

- **反模式1：直接修改linked_to_raw格式**
  Phase 18已完成linked_to_raw为dict格式，Phase 19应复用而非修改序列化逻辑
  
- **反模式2：重写执行流追踪算法**
  现有_trace_execution_from_event()已实现循环检测和控制流停止，应扩展起点识别而非重写
  
- **反模式3：忽略控制流节点branch_type标记**
  D-19-14要求添加branch_type字段，不能仅停止追踪而不输出分支信息
  
- **反模式4：将数据流与执行流混合**
  D-19-09明确要求独立分离，data_flows应独立于execution_flows构建

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pin引用查找 | 新的查找算法 | 现有pin_lookup表 | 已验证稳定，复用降低风险 |
| 循环检测 | 新的检测逻辑 | 现有visited set模式 | 已在Phase 8验证有效 |
| 控制流节点识别 | 新的节点类型列表 | 现有CONTROL_FLOW_NODES frozenset | 已定义6种类型，直接复用 |
| 格式转换 | 自定义转换函数 | 统一format_pin_ref() | 所有连接输出使用同一转换层 |

**Key insight:** Phase 19主要是功能扩展和格式调整，核心算法已稳定验证。复用现有模式降低风险，避免引入新的边界检查问题。

## Runtime State Inventory

> Skip: Phase 19为纯代码逻辑扩展，无运行时状态依赖。

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — 无数据库或持久化状态 | N/A |
| Live service config | None — 无外部服务依赖 | N/A |
| OS-registered state | None — 无OS级注册 | N/A |
| Secrets/env vars | None — 无配置文件依赖 | N/A |
| Build artifacts | None — 无编译产物依赖 | N/A |

**Nothing found:** Phase 19为纯Python代码扩展，所有状态在内存中构建。

## Common Pitfalls

### Pitfall 1: linked_to_raw格式误解

**What goes wrong:** 误以为linked_to_raw为pin_id字符串列表，导致查找失败

**Why it happens:** Phase 18将linked_to_raw改为dict格式（`{"owning_node": str, "pin_guid": str}`），但旧代码注释仍描述为字符串列表

**How to avoid:** 
1. 检查read_pin_reference()函数返回格式（第2681-2731行）
2. 使用`linked_pin_id.get("pin_guid")`而非直接字符串
3. 添加类型注释明确dict格式

**Warning signs:** 
- 查找失败warning数量异常增加
- connections数组为空但节点有pins
- AttributeError: 'str' object has no attribute 'get'

### Pitfall 2: 执行流起点类型遗漏

**What goes wrong:** EnhancedInputAction节点未识别为起点，执行流缺失

**Why it happens:** 现有代码仅识别K2Node_Event，未扩展起点类型列表

**How to avoid:**
1. 创建START_EVENT_TYPES frozenset（包含4种类型）
2. 修改event_nodes识别逻辑为`class_name in START_EVENT_TYPES`
3. 添加单元测试验证每种起点类型

**Warning signs:**
- execution_flows数组为空但graph有EnhancedInputAction节点
- Jump输入动作执行流程缺失
- 测试资产验证失败

### Pitfall 3: 控制流节点branch_type缺失

**What goes wrong:** 控制流节点停止追踪但未输出branch_type字段

**Why it happens:** 现有代码仅在flow中添加`{"stopped_at": "control_flow_node"}`，未满足D-19-14要求

**How to avoid:**
1. 定义BRANCH_TYPE_MAP映射节点类型到branch_type枚举
2. 在_trace_execution_from_event()停止时添加branch_type字段
3. 区分if_then_else/switch*/macro_instance类型

**Warning signs:**
- 输出JSON缺少branch_type字段
- 控制流节点仅显示stopped_at
- REQUIREMENTS验证失败

### Pitfall 4: Name模式节点名冲突

**What goes wrong:** 多个节点生成相同node_name（如多个K2Node_CallFunction）

**Why it happens:** 节点名派生逻辑未考虑同名节点数量，导致冲突

**How to avoid:**
1. 使用`f"{class_name}_{idx}"`或添加guid后缀区分
2. 实现节点名计数器处理冲突
3. Claude's Discretion区域需明确策略

**Warning signs:**
- JSON输出有重复node字段值
- 连接引用无法区分目标节点
- 用户友好性下降

### Pitfall 5: EnhancedInputAction触发时机遗漏

**What goes wrong:** 仅追踪Started触发时机，遗漏Triggered和Completed执行链路

**Why it happens:** 将EnhancedInputAction视为单一起点，未识别多个output exec pins

**How to avoid:**
1. 检查EnhancedInputAction所有output exec pins
2. 为每个触发时机分别调用_trace_execution_from_pin()
3. 输出格式包含触发时机标识（如"IA_Jump.Started"）

**Warning signs:**
- Jump持续动作或结束动作执行流缺失
- EventGraph流程不完整
- 测试验证（TEST-02）失败

## Code Examples

### 现有代码参考（VERIFIED）

#### Pin Lookup构建（build_connections_map L5009-5013）
```python
# [VERIFIED: uasset_read.py 第5009-5013行]
pin_lookup: Dict[str, Tuple[str, str]] = {}
for node in graph.nodes:
    for pin in node.pins:
        pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)
```

#### 控制流节点定义（L4980-4987）
```python
# [VERIFIED: uasset_read.py 第4980-4987行]
CONTROL_FLOW_NODES = frozenset({
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",
})
```

#### 循环检测（_trace_execution_from_event L5248-5256）
```python
# [VERIFIED: uasset_read.py 第5248-5256行]
visited: Set[str] = set()
while current_node:
    if current_node.node_guid in visited:
        flow.append({
            "node_guid": current_node.node_guid,
            "node_type": current_node.class_name,
            "cycle_detected": True
        })
        break
    visited.add(current_node.node_guid)
```

#### Exec Pin查找（_find_next_exec_node L5306-5314）
```python
# [VERIFIED: uasset_read.py 第5306-5314行]
for pin in node.pins:
    if pin.direction == 1:  # Output
        if pin.pin_type and pin.pin_type.pin_category == "exec":
            for linked_pin_id in pin.linked_to_raw:
                if linked_pin_id in pin_lookup:
                    target_node_guid, _ = pin_lookup[linked_pin_id]
                    return node_lookup.get(target_node_guid)
```

### UE源码参考（VERIFIED）

#### Pin序列化顺序（EdGraphPin.cpp L1838-1964）
```cpp
// [VERIFIED: UE 5.7 源码 EdGraphPin.cpp 第1838-1964行]
bool UEdGraphPin::Serialize(FArchive& Ar)
{
    Ar << OwningNode;      // L1844
    Ar << PinId;           // L1845
    Ar << PinName;         // L1847-1856 (version dependent)
    Ar << PinToolTip;      // L1870
    Ar << Direction;       // L1871
    PinType.Serialize(Ar); // L1872
    Ar << DefaultValue;    // L1873
    Ar << DefaultObject;   // L1875
    Ar << DefaultTextValue;// L1876
    
    // LinkedTo通过SerializePinArray处理
    UEdGraphPin::SerializePinArray(Ar, LinkedTo, this, EPinResolveType::LinkedTo); // L1886
    
    // SubPins/ParentPin处理
    UEdGraphPin::SerializePinArray(Ar, SubPins, this, EPinResolveType::SubPins);   // L1889
    SerializePin(Ar, ParentPin, INDEX_NONE, this, EPinResolveType::ParentPin, ...);// L1891
    
    // BitField解析（显示属性）
    uint32 BitField = 0;
    BitField |= bHidden << 0;
    BitField |= bNotConnectable << 1;
    BitField |= bAdvancedView << 4;
    BitField |= bOrphanedPin << 5;
    Ar << BitField;        // L1923
}
```

#### Pin引用格式（SerializePin逻辑推断）
```cpp
// [CITED: EdGraphPin.cpp L2132-2296 SerializePin实现]
// Pin引用序列化格式：
// 1. bNullPtr (bool/uint8) - 空引用标记
// 2. OwningNode (FPackageIndex/int32) - 节点引用
// 3. PinGuid (FGuid 16 bytes) - Pin唯一标识
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| linked_to_raw为字符串列表 | linked_to_raw为dict格式 | Phase 18 (2026-05-04) | 包含owning_node信息，查找更准确 |
| 仅K2Node_Event起点 | 4种起点类型 | Phase 19 (planned) | 支持输入动作、变量设置等执行流 |
| 执行流单一链路 | EnhancedInputAction多触发链路 | Phase 19 (planned) | 完整反映输入动作生命周期 |
| 无数据流输出 | data_flows独立构建 | Phase 19 (planned) | 区分执行流和数据流关系 |
| 仅停止标记 | branch_type字段输出 | Phase 19 (planned) | 明确控制流分支类型 |

**Deprecated/outdated:**
- linked_to_raw字符串列表格式：Phase 18已改为dict格式，旧代码需更新查找逻辑
- 单一起点类型识别：Phase 19扩展为多类型，需修改event_nodes识别
- stopped_at标记：Phase 19改为branch_type字段，提供更多信息

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | linked_to_raw dict格式包含pin_guid字段 | 现有代码分析 | 查找失败，需验证Phase 18输出 |
| A2 | EnhancedInputAction有Started/Triggered/Completed三个exec output pins | Pattern 4 | 执行流不完整，需检查测试资产 |
| A3 | 节点名可通过导出表object_name派生 | Pattern 2 | Name模式冲突，需明确派生规则 |
| A4 | 控制流节点类型已完整定义在CONTROL_FLOW_NODES | Pattern 3 | 遗漏节点类型，需验证UE源码 |

**需要用户确认的Claude's Discretion项:**
1. branch_type枚举值定义（if_then_else/switch_enum等命名规范）
2. cycle_detected输出位置（节点层级或执行流层级）
3. name模式节点名冲突处理策略（计数器或guid后缀）

## Open Questions

1. **Name模式节点名派生规则**
   - What we know: REQUIREMENTS示例使用`K2Node_EnhancedInputAction_5`格式
   - What's unclear: 如何处理同名节点（多个K2Node_CallFunction）
   - Recommendation: 使用`f"{class_name}_{export_idx}"`从导出表索引派生，或添加guid后缀

2. **EnhancedInputAction pins结构验证**
   - What we know: 现有代码已解析K2NodeEnhancedInputAction（第1419-1430行）
   - What's unclear: 具体有多少exec output pins及其pin_name值
   - Recommendation: 解析测试资产BP_FirstPersonCharacter.uasset验证IA_Jump节点pins

3. **cycle_detected输出层级**
   - What we know: 现有代码在节点信息中添加cycle_detected字段（第5254行）
   - What's unclear: D-19-15要求的输出位置是否需要调整
   - Recommendation: 保持节点层级，符合现有格式

## Environment Availability

> Step 2.6: 外部依赖检查

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | 核心解析 | ✓ | 3.14.3 | — |
| pytest | 测试验证 | ✓ | 9.0.3 | — |
| UE 5.7源码 | 参考验证 | ✓ | E:\Develop\lib\UnrealEngine | — |
| 测试资产 | 验证数据 | ✓ | BP_FirstPersonCharacter.uasset | — |

**Missing dependencies with no fallback:**
None — 所有依赖已验证可用。

**Missing dependencies with fallback:**
None — 无需外部服务或工具。

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | 无（直接运行） |
| Quick run command | `python -m pytest tests/test_output_formatting.py -x` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LINK-01 | 构建connections数组（name模式） | unit | `pytest tests/test_output_formatting.py::test_build_connections_map_name_mode -x` | ❌ Wave 0 |
| LINK-01 | 处理查找失败warning | unit | `pytest tests/test_output_formatting.py::test_build_connections_map_warning -x` | ✓ 已存在 |
| LINK-02 | 执行流起点类型识别 | unit | `pytest tests/test_output_formatting.py::test_execution_flows_start_types -x` | ❌ Wave 0 |
| LINK-02 | EnhancedInputAction多触发追踪 | unit | `pytest tests/test_output_formatting.py::test_enhanced_input_flows -x` | ❌ Wave 0 |
| LINK-02 | 循环检测标记 | unit | `pytest tests/test_output_formatting.py::test_execution_flow_cycle_detection -x` | ✓ 已存在 |
| LINK-03 | 数据流构建 | unit | `pytest tests/test_output_formatting.py::test_build_data_flows -x` | ❌ Wave 0 |
| LINK-03 | exec pins过滤 | unit | `pytest tests/test_output_formatting.py::test_data_flows_excludes_exec -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_output_formatting.py -x`
- **Per wave merge:** `python -m pytest tests/test_output_formatting.py -v`
- **Phase gate:** 全套测试通过，加上测试资产验证（BP_FirstPersonCharacter.uasset）

### Wave 0 Gaps
- [ ] `test_build_connections_map_name_mode()` — 验证LINK-01 name模式输出
- [ ] `test_execution_flows_start_types()` — 验证LINK-02起点类型扩展
- [ ] `test_enhanced_input_flows()` — 验证LINK-02 EnhancedInputAction多触发
- [ ] `test_build_data_flows()` — 验证LINK-03数据流构建
- [ ] `test_data_flows_excludes_exec()` — 验证LINK-03 exec过滤
- [ ] `test_control_flow_branch_type()` — 验证D-19-14 branch_type输出

*(现有测试基础设施覆盖部分功能，需添加5-6个新测试)*

## Security Domain

> Skip: Phase 19为纯数据处理逻辑，无安全敏感操作。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Python类型系统 + dataclasses |
| V6 Cryptography | no | — |

### Known Threat Patterns

无安全威胁 — Phase 19为纯数据结构构建逻辑，处理已解析的内存数据，不涉及外部输入、网络通信或敏感数据处理。

## Sources

### Primary (HIGH confidence)
- [VERIFIED: uasset_read.py 第4990-5039行] — build_connections_map()现有实现
- [VERIFIED: uasset_read.py 第5180-5225行] — build_execution_flows()现有实现
- [VERIFIED: uasset_read.py 第5228-5315行] — _trace_execution_from_event()追踪逻辑
- [VERIFIED: uasset_read.py 第4980-4987行] — CONTROL_FLOW_NODES定义
- [VERIFIED: uasset_read.py 第2681-2731行] — read_pin_reference()dict格式
- [VERIFIED: UE 5.7源码 EdGraphPin.cpp L1838-1964] — Pin序列化结构验证
- [VERIFIED: tests/test_output_formatting.py 第795-895行] — 现有测试覆盖

### Secondary (MEDIUM confidence)
- [CITED: .planning/phases/18-Pin序列化解析/18-CONTEXT.md] — Phase 18 linked_to_raw格式决策
- [CITED: REQUIREMENTS.md 第78-116行] — LINK-01~03规范定义
- [CITED: ROADMAP.md 第96-105行] — Phase 19 Success Criteria

### Tertiary (LOW confidence)
None — 所有核心实现已通过源码验证。

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 无新增依赖，使用现有Python标准库
- Architecture: HIGH — 现有代码已验证稳定，复用模式明确
- Pitfalls: HIGH — 基于Phase 18实际问题和现有代码审查
- Validation: HIGH — 测试框架已存在，需添加特定测试

**Research date:** 2026-05-04
**Valid until:** 稳定实现（无外部依赖变更风险）

---

## 附录：代码位置索引

| 函数/结构 | 文件位置 | 说明 |
|-----------|---------|------|
| build_connections_map() | uasset_read.py:4990-5039 | 连接映射构建（需扩展name模式） |
| build_execution_flows() | uasset_read.py:5180-5225 | 执行流构建（需扩展起点类型） |
| _trace_execution_from_event() | uasset_read.py:5228-5315 | 执行流追踪核心逻辑 |
| _get_event_name() | uasset_read.py:5318-5330 | 事件名提取（需扩展为起点名） |
| CONTROL_FLOW_NODES | uasset_read.py:4980-4987 | 控制流节点类型frozenset |
| UEdGraphPin | uasset_read.py:1260-1302 | Pin数据结构定义 |
| read_pin_reference() | uasset_read.py:2681-2731 | Pin引用解析（dict格式） |
| format_graphs_json() | uasset_read.py:5060-5086 | JSON输出格式化入口 |
| K2NodeEnhancedInputAction | uasset_read.py:1419-1430 | EnhancedInputAction数据结构 |
| test_build_connections_map_* | tests/test_output_formatting.py:795-828 | 连接构建现有测试 |
| test_build_execution_flows_* | tests/test_output_formatting.py:846-895 | 执行流现有测试 |

---

*Phase 19: 连接关系重建 — Research Complete*
*Ready for planning: 核心算法稳定，扩展任务明确*