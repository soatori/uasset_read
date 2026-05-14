# Phase 19: 连接关系重建 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 19-连接关系重建
**Areas discussed:** 连接引用格式, 数据流定义, 执行流起点类型, 控制流分支处理

---

## 连接引用格式

### Node引用格式

| Option | Description | Selected |
|--------|-------------|----------|
| 保留node_guid | 稳定可靠，GUID不会变化。现有代码已实现。适合内部解析，但用户阅读不够友好。 | ✓ |
| 改为node_name | 用户友好，易于阅读。但节点名可能重复（如多个CallFunction_0）。需处理命名冲突。 | |
| 双字段格式 | 既有稳定性又有友好性。GUID为主键，name为显示标签。输出稍大但最完整。 | |

**User's choice:** 保留node_guid（推荐）

---

### Pin引用格式

| Option | Description | Selected |
|--------|-------------|----------|
| 使用pin_name | 语义清晰，易于理解。需从pin_lookup中解析pin_name。Phase 18已实现该格式。 | ✓ |
| 保留pin_id GUID | 稳定唯一，但不易读。与Phase 18修正后的格式不一致。 | |
| 双字段格式 | 既有唯一性又有语义。输出稍大但最完整。 | |

**User's choice:** 使用pin_name（推荐）

---

### Phase 18输出修改策略

| Option | Description | Selected |
|--------|-------------|----------|
| 转换层 | Phase 19将pin_id转换为pin_name，不影响Phase 18的原始数据。保持向后兼容。 | |
| 统一修改Phase 18 | 统一修改Phase 18输出格式为pin_name。彻底一致，但需更新Phase 18代码。 | ✓ |
| 可选配置 | 两个格式并存，用户选择输出格式。复杂度较高。 | |

**User's choice:** 统一修改Phase 18

---

### 查找失败处理

| Option | Description | Selected |
|--------|-------------|----------|
| 保留原始pin_id | 现有代码已实现。保留原始pin_id作为fallback，便于调试。 | |
| 省略失败连接 | 简化输出，不显示失败连接。可能丢失调试信息。 | |
| 输出warning标记 | 明确显示失败状态。用户可见错误信息。 | |

**User's choice:** 全局可选配置（用户自定义）
**Notes:** 用户选择"两种格式可选"，后澄清为"全局可选配置"——整体连接输出格式可配置（guid模式或name模式）。

---

### 全局配置默认值

| Option | Description | Selected |
|--------|-------------|----------|
| name模式默认 | 默认输出pin_name，符合REQUIREMENTS示例格式。用户友好。 | ✓ |
| guid模式默认 | 默认输出node_guid + pin_id，稳定可靠。向后兼容现有代码。 | |

**User's choice:** name模式默认

---

## 数据流定义

### 数据流类型

| Option | Description | Selected |
|--------|-------------|----------|
| 非exec pins | 清晰的语义分离：exec pins构成执行流，其他pins构成数据流。符合REQUIREMENTS设计。 | ✓ |
| 仅输出pins | 仅输出pins（direction=1）构成数据流，input pins为数据接收端。 | |
| 完整路径追踪 | 数据流包含完整路径：source → target，追踪所有非exec连接。 | |

**User's choice:** 非exec pins（推荐）

---

### 数据流结构

| Option | Description | Selected |
|--------|-------------|----------|
| {source, target} | 符合REQUIREMENTS示例格式，清晰语义化。source/target分别表示数据来源和去向。 | ✓ |
| {from, to} | 与connections结构一致，统一格式。但语义不如source/target清晰。 | |
| 扩展格式（含pin_type） | 包含完整pin信息：node、pin、pin_type。便于分析数据类型流向。 | |

**User's choice:** {source, target}（推荐）

---

### 数据流组织

| Option | Description | Selected |
|--------|-------------|----------|
| 扁平列表 | 每条数据流独立记录，包含source和target。简单清晰，符合REQUIREMENTS示例。 | ✓ |
| 按节点分组 | 每个节点的输入/输出数据流组织在一起。便于查看节点的数据依赖。 | |
| 按类型分组 | 每个数据类型分组（float/string/object等），便于分析类型传递路径。 | |

**User's choice:** 扁平列表（推荐）

---

### 数据执行关联

| Option | Description | Selected |
|--------|-------------|----------|
| 独立分离 | data_flows独立于execution_flows，不标记关联。简化输出，各自分析。 | ✓ |
| 标记关联执行流 | 每条数据流标记所属执行流ID，便于追踪数据跟随的执行路径。 | |
| 嵌入执行流 | 数据流嵌入execution_flows内部，作为节点属性的一部分。 | |

**User's choice:** 独立分离（推荐）

---

## 执行流起点类型

### 起点类型选择

| Option | Description | Selected |
|--------|-------------|----------|
| K2Node_Event | 现有已支持。蓝图事件入口点（BeginPlay、Tick等）。 | ✓ |
| K2Node_EnhancedInputAction | Enhanced Input系统动作节点。IA_Jump等需要作为执行流起点。 | ✓ |
| K2Node_VariableSet | 变量变化触发节点。需要在变量被修改时触发执行流。 | ✓ |
| K2Node_CustomEvent | 自定义事件节点。用户定义的事件触发入口。 | ✓ |

**User's choice:** 全选（四种节点类型均作为执行流起点）

---

### 起点标识格式

| Option | Description | Selected |
|--------|-------------|----------|
| 统一标识 | 统一使用start_event字段，包含节点名。所有起点类型统一处理。 | ✓ |
| 类型标识字段 | 使用entry字段标记起点类型（event/input_action/var_set/custom_event），便于分类分析。 | |
| 分类数组 | 每种起点类型输出为独立数组（events、input_actions、var_sets、custom_events）。 | |

**User's choice:** 统一标识（推荐）

---

### EnhancedInputAction触发时机

| Option | Description | Selected |
|--------|-------------|----------|
| 分别追踪 | Started、Triggered、Completed等输出pin分别追踪各自的执行链路。 | ✓ |
| 合并追踪 | 所有触发时机合并为同一执行流，不区分具体触发类型。 | |
| 仅主要输出 | 仅追踪主要的Started输出pin，忽略其他触发时机。 | |

**User's choice:** 分别追踪（推荐）

---

## 控制流分支处理

### 分支路径处理

| Option | Description | Selected |
|--------|-------------|----------|
| 标记停止 | 控制流节点仅标记为分支点，不继续追踪各分支路径。简化输出。 | ✓ |
| 追踪所有分支 | 追踪所有分支路径，每条分支记录完整链路。输出完整但较复杂。 | |
| 追踪主要分支 | 仅追踪主要分支（如IfThenElse的True分支），其他分支标记但不追踪。 | |

**User's choice:** 标记停止（推荐）

---

### 分支标记格式

| Option | Description | Selected |
|--------|-------------|----------|
| branch_type字段 | 在节点记录中添加branch_type字段（if_then_else/switch/switch_enum等）。 | ✓ |
| branch_pins字段 | 添加分支输出pin名称列表（如["True", "False"]），便于理解分支结构。 | |
| 无额外标记 | 仅在node_type中标识，无额外字段。最简化。 | |

**User's choice:** branch_type字段（推荐）

---

### 循环检测处理

| Option | Description | Selected |
|--------|-------------|----------|
| 标记停止 | 检测到循环时停止追踪，标记cycle_detected=true。现有代码已实现类似逻辑。 | ✓ |
| 允许循环 | 循环路径完整追踪，允许重复节点。可能导致无限循环。 | |
| 追踪一圈 | 循环路径追踪至第二次遇到同一节点为止，记录完整循环路径。 | |

**User's choice:** 标记停止（推荐）

---

## Claude's Discretion

- branch_type字段的具体枚举值
- cycle_detected字段的输出位置（节点层级或执行流层级）
- name模式下节点名冲突的处理策略

---

## Deferred Ideas

None — discussion stayed within phase scope.

---

*Phase: 19-连接关系重建*
*Discussion date: 2026-05-04*