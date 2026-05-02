---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: 蓝图图解析
status: in_progress
last_updated: "2026-05-02T02:00:00Z"
progress:
  total_phases: 5
  completed_phases: 0
  active_phase: null
  total_plans: 0
  completed_plans: 0
  percent: 0
---

---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: 蓝图图解析
status: in_progress
last_updated: "2026-05-02T02:00:00Z"
progress:
  total_phases: 5
  completed_phases: 0
  active_phase: null
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# uasset_read v2.0 路线图

** milestone:** v2.0 —— 蓝图图解析
** 创建日期：** 2026-05-02
** 状态：** 进行中

## Phases

- [x] **Phase 6: 导出表修复** - 修复 OuterIndex/TemplateIndex 解析 bug ✓ 2026-05-02
- [x] **Phase 7: 蓝图图核心解析** - UEdGraph/UEdGraphNode/UEdGraphPin 基础解析 ✓ 2026-05-02
- [ ] **Phase 8: 蓝图图输出增强** - JSON/文本输出格式增强
- [ ] **Phase 9: 高级属性类型** - StructProperty/MapProperty/SetProperty/EnumProperty/TextProperty/DelegateProperty
- [ ] **Phase 10: 依赖分析** - ImportMap + SoftObjectPaths 依赖图

## Phase Details

### Phase 6: 导出表修复

**Goal:** 修复 v1.0 中导出表解析的 OuterIndex 缺失 bug，确保正确读取 FObjectExport 结构

**Depends on:** Nothing (Foundation phase for v2.0)

**Requirements:** BUG-01, BUG-02, BUG-03

**Success Criteria** (what must be TRUE):
1. 解析器正确读取 FObjectExport.TemplateIndex 字段（当 file_version_ue4 >= 506 时）
2. 解析器正确读取 FObjectExport.OuterIndex 字段（所有版本），导出表偏移正确
3. 导出表解析失败时返回清晰错误信息（包含文件偏移、期望值、实际值）

**Plans:** 2 plans in 2 waves

Plans:
- [ ] 06-01-PLAN.md — 实现修复：ErrorContext扩展、ObjectExport扩展、read_export_map重构
- [ ] 06-02-PLAN.md — 测试验证：单元测试、功能测试、Lyra资产对比验证

**UI hint:** no

---

### Phase 7: 蓝图图核心解析

**Goal:** 实现蓝图图结构的基础解析（Graph → Node → Pin）

**Depends on:** Phase 6

**Requirements:** GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04, GRAPH-05, GRAPH-06, GRAPH-07, GRAPH-08, GRAPH-09

**Success Criteria** (what must be TRUE):
1. 解析器能识别 UEdGraph 导出类型（ClassIndex 包含 "EdGraph"）
2. 解析器能提取 UEdGraph 基本信息（Schema、GraphGuid、Nodes 数量）
3. 解析器能解析 UEdGraphNode 基类字段（NodeGuid、NodePosX/Y、NodeComment、Pins）
4. 解析器能解析 UEdGraphPin 完整结构（PinId、PinName、Direction、PinType、DefaultValue、LinkedTo 原始数据、SubPins、ParentPin）
5. 解析器能构建引脚连接映射（LinkedTo PinId → 目标节点/引脚）— **推迟到 Phase 8（D-01）**

**Plans:** 3 plans in 3 waves

Plans:
- [x] 07-01-PLAN.md — 数据结构定义 + EdGraph 检测（GRAPH-01, GRAPH-02） ✓
- [x] 07-02-PLAN.md — Node/Pin 核心解析（GRAPH-03, GRAPH-04） ✓
- [x] 07-03-PLAN.md — 节点类型特定解析器 + 测试（GRAPH-05~09） ✓

**UI hint:** no

---

### Phase 8: 蓝图图输出增强

**Goal:** 完善 JSON 和文本输出格式，包含蓝图图数据和连接映射

**Depends on:** Phase 7

**Requirements:** GRAPH-11, GRAPH-12, OUT2-01, OUT2-03, OUT2-04 (OUT2-02 推迟到 Phase 9)

**Success Criteria** (what must be TRUE):
1. JSON 输出包含蓝图图层级结构（Graph → Nodes → Pins）
2. JSON 输出包含执行流路径（从 Event → CallFunction 链路）
3. JSON 输出包含完整的蓝图图数据（与 blueprint 字段同级的 graphs 字段）
4. CLI 支持 --graph 标志仅输出蓝图图数据
5. 文本输出包含图结构摘要（节点数、连接数、执行流概览）

**Plans:** 4 plans in 4 waves

Plans:
- [ ] 08-01-PLAN.md — 连接映射构建（GRAPH-11, OUT2-01）
- [ ] 08-02-PLAN.md — 执行流追踪（GRAPH-12）
- [ ] 08-03-PLAN.md — 文本输出扩展（OUT2-03）
- [ ] 08-04-PLAN.md — CLI --graph 标志（OUT2-04）

**UI hint:** yes

---

### Phase 9: 高级属性类型

**Goal:** 实现高级属性类型的完整解析（StructProperty、MapProperty、SetProperty、EnumProperty、TextProperty、DelegateProperty）

**Depends on:** Phase 7

**Requirements:** ADVP-01, ADVP-02, ADVP-03, ADVP-04, ADVP-05, ADVP-06

**Success Criteria** (what must be TRUE):
1. 解析器能提取 StructProperty 值（嵌套结构体解析，递归深度限制 5）
2. 解析器能提取 MapProperty 值（键值对数组，支持基本类型键）
3. 解析器能提取 SetProperty 值（唯一元素集）
4. 解析器能提取 EnumProperty 值（枚举类型名 + 枚举值名）
5. 解析器能提取 TextProperty 值（FText：Namespace、Key、SourceString）
6. 解析器能提取 DelegateProperty 值（函数引用：对象 + 函数名）

**Plans:** 3 plans in 3 waves

Plans:
- [ ] 09-01-PLAN.md — 数据类定义 + type_dispatch 扩展（ADVP-01~06）
- [ ] 09-02-PLAN.md — 六种高级属性解析函数实现（ADVP-01~06）
- [ ] 09-03-PLAN.md — 单元测试 + Lyra 资产验证（ADVP-01~06）

**UI hint:** no

---

### Phase 10: 依赖分析

**Goal:** 构建 ImportMap + SoftObjectPaths 依赖图，检测循环依赖

**Depends on:** Phase 7

**Requirements:** DEPS-01, DEPS-02, DEPS-03, DEPS-04

**Success Criteria** (what must be TRUE):
1. 解析器能从 ImportMap 构建依赖列表（包路径、类名、对象名）
2. 解析器能从 SoftObjectPaths 构建软引用依赖列表（AssetReference）
3. 解析器能检测循环依赖（ImportMap 中的相互引用）
4. JSON 输出包含依赖图结构（imports、soft_references、circular_deps）

**Plans:** TBD

**UI hint:** no

---

## Phase Summary

| Phase | Goal | Requirements | Success Criteria Count |
|-------|------|--------------|------------------------|
| 6 - 导出表修复 | 修复 OuterIndex/TemplateIndex 解析 bug | BUG-01, BUG-02, BUG-03 | 3 |
| 7 - 蓝图图核心 | UEdGraph/Node/Pin 基础解析 | GRAPH-01~09 (10→Phase8) | 5 |
| 8 - 蓝图图输出 | JSON/文本输出增强 | GRAPH-11~12, OUT2-01~04 | 5 |
| 9 - 高级属性 | Struct/Map/Set/Enum/Text/Delegate 解析 | ADVP-01~06 | 6 |
| 10 - 依赖分析 | ImportMap + SoftObjectPaths 依赖图 | DEPS-01~04 | 4 |

---

## Progress Table

| 9 - 高级属性 | 0/3 | Ready to execute | 0% |
|-------|----------------|--------|-----------|
| 6 - 导出表修复 | 2/2 | Complete | 100% |
| 7 - 蓝图图核心 | 3/3 | Complete | 100% |
| 8 - 蓝图图输出 | 0/4 | Ready to execute | 0% |
| 9 - 高级属性 | 0/0 | Not started | - |
| 10 - 依赖分析 | 0/0 | Not started | - |

---

## v2.0 需求覆盖

| 需求 | 阶段 | 状态 |
|------|------|------|
| BUG-01 | Phase 6 | ✓ Complete |
| BUG-02 | Phase 6 | ✓ Complete |
| BUG-03 | Phase 6 | ✓ Complete |
| GRAPH-01 | Phase 7 | ✓ Complete |
| GRAPH-02 | Phase 7 | ✓ Complete |
| GRAPH-03 | Phase 7 | ✓ Complete |
| GRAPH-04 | Phase 7 | ✓ Complete |
| GRAPH-05 | Phase 7 | ✓ Complete |
| GRAPH-06 | Phase 7 | ✓ Complete |
| GRAPH-07 | Phase 7 | ✓ Complete |
| GRAPH-08 | Phase 7 | ✓ Complete |
| GRAPH-09 | Phase 7 | ✓ Complete |
| GRAPH-10 | Phase 8 | Deferred (D-01) |
| GRAPH-11 | Phase 8 | Pending |
| GRAPH-12 | Phase 8 | Pending |
| ADVP-01 | Phase 9 | Pending |
| ADVP-02 | Phase 9 | Pending |
| ADVP-03 | Phase 9 | Pending |
| ADVP-04 | Phase 9 | Pending |
| ADVP-05 | Phase 9 | Pending |
| ADVP-06 | Phase 9 | Pending |
| DEPS-01 | Phase 10 | Pending |
| DEPS-02 | Phase 10 | Pending |
| DEPS-03 | Phase 10 | Pending |
| DEPS-04 | Phase 10 | Pending |
| OUT2-01 | Phase 8 | Pending |
| OUT2-02 | Phase 9 | Deferred (高级属性需先实现) |
| OUT2-03 | Phase 8 | Pending |
| OUT2-04 | Phase 8 | Pending |

**覆盖率：** 14/29 需求已完成 ✓

---

## 技术架构

### 分层管道（v2.0 扩展）

```
.uasset → FArchive → Deserializer → Models → OutputFormatter
                    ↓ 新增组件
              GraphParser (Phase 7)
              AdvancedPropParser (Phase 9)
              DependencyGraphBuilder (Phase 10)
```

### 关键修复（Phase 6）

- FObjectExport.TemplateIndex 字段条件读取（file_version_ue4 >= 506）
- OuterIndex 正确读取（UE4/UE5 统一）
- 错误上下文增强（offset, phase, operation, context_name）

###蓝图图数据类（Phase 7）

```python
@dataclass
class UEdGraphPinRef:
    pin_name: str
    target_node: Optional[str]
    resolved_pin: Optional["UEdGraphPin"] = None

@dataclass
class UEdGraphPin:
    pin_id: str                      # Guid hex
    pin_name: str
    direction: str                   # EGPD_Input/EGPD_Output
    pin_type: "FEdGraphPinType"
    default_value: Optional[str]
    auto_default_value: Optional[str]
    linked_to: List["UEdGraphPinRef"]
    sub_pins: List["UEdGraphPin"]
    parent_pin: Optional["UEdGraphPin"]
    
@dataclass
class UEdGraphNode:
    node_guid: str
    node_pos_x: int
    node_pos_y: int
    node_comment: str
    pins: List["UEdGraphPin"]
    class_name: str                  # K2Node_Event, K2Node_CallFunction, etc.
    
@dataclass
class UEdGraph:
    graph_name: str
    graph_class: str
    nodes: List["UEdGraphNode"]
    is_ubergraph: bool
```

---

*最后更新：2026-05-02 - Phase 8 规划完成*