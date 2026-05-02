---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: 蓝图图解析
status: ready_to_plan
last_updated: "2026-05-02T19:00:00Z"
progress:
  total_phases: 5
  completed_phases: 2
  active_phase: 9
  total_plans: 3
  completed_plans: 3
  percent: 40
shipped:
  date: null
  branch: null
  remote: null
---

# 项目状态

**项目：** uasset_read
**初始化：** 2026-04-27
**里程碑：** v2.0 —— 蓝图图解析
**状态：** Ready to plan - Phase 9 上下文已收集

## 当前阶段

**Phase 9: 高级属性类型** - 上下文已收集

## 阶段状态

| # | 阶段 | 状态 | 计划 | 验证 | 安全 | 进度 |
|---|------|------|------|------|------|------|
| 1 | 核心解析 | ✓ 完成 | 8/8 | ✓ | - | 100% |
| 2 | 属性解析 | ✓ 完成 | 3/3 | ✓ | - | 100% |
| 3 | 蓝图提取 | ✓ 完成 | 4/4 | ✓ | - | 100% |
| 4 | 输出与 CLI | ✓ 完成 | 5/5 | ✓ | ✓ | 100% |
| 5 | 优化与安全 | ✓ 完成 | 5/5 | ✓ | ✓ | 100% |
| 6 | 导出表修复 | ✓ 完成 | 2/2 | ✓ | ✓ | 100% |
| 7 | 蓝图图核心 | ✓ 完成 | 3/3 | ✓ | TBD | 100% |
| 8 | 蓝图图输出 | ◆ 上下文收集 | TBD | TBD | TBD | 0% |
| 9 | 高级属性 | ◆ 上下文收集 | TBD | TBD | TBD | 0% |
| 10 | 依赖分析 | ⏳ 待启动 | TBD | TBD | TBD | 0% |

## v2.0 进度

### 快照
- **里程碑：** v2.0 —— 蓝图图解析
- **起始点：** v1.0 完成（5/5 阶段，2026-05-02）
- **当前状态：** Phase 6 完成（导出表修复）

### 覆盖率
- **v2.0 需求总数：** 29
- **已映射：** 29
- **未映射：** 0 ✓

### 阶段规划
- **Phase 6：** ✓ 完成 - 导出表修复（BUG-01~03）- OuterIndex/TemplateIndex 修复
- **Phase 7：** 蓝图图核心解析（GRAPH-01~10）- Graph→Node→Pin
- **Phase 8：** 蓝图图输出增强（GRAPH-11~12, OUT2-01~04）- JSON/文本
- **Phase 9：** 高级属性类型（ADVP-01~06）- Struct/Map/Set/Enum/Text/Delegate
- **Phase 10：** 依赖分析（DEPS-01~04）- ImportMap + SoftObjectPaths

## 近期活动

| 日期 | 动作 | 结果 |
|------|------|------|
| 2026-05-02 | Phase 7 Wave 1 完成 | 数据结构定义 + EdGraph 检测 |
| 2026-05-02 | Phase 7 Wave 2 完成 | Node/Pin 核心解析实现 |
| 2026-05-02 | Phase 7 Wave 3 完成 | 节点类型解析器 + 测试 |
| 2026-05-02 | Phase 7 验证通过 | 5/5 must-haves, 105 tests pass |
| 2026-05-02 | Phase 8 上下文收集完成 | 连接映射 + 执行流 + CLI 标志决策 |
| 2026-05-02 | Phase 9 上下文收集完成 | 高级属性解析策略决策 |

## 下一步动作

```
/gsd-plan-phase 9 — 创建 Phase 9 规划（高级属性类型）
```

### Phase 9 决策要点

1. **StructProperty 递归解析** - 深度限制 5 + 未知字段处理
2. **MapProperty 全键类型支持** - 基本类型/枚举/Struct/Object 四种键
3. **专用 dataclass 设计** - StructValue/MapValue/SetValue/EnumValue/TextValue/DelegateValue
4. **UE4 + UE5 双支持** - 使用 Phase 2 D-05/D-06 版本检查模式

## v2.0 技术展望

### Phase 6 修复（当前）

```
FObjectExport 结构（UE5 格式）：
- ClassIndex (i32)
- SuperIndex (i32)
- OuterIndex (i32)
- ObjectName (FName)
- ObjectFlags (u32)
- SerialSize (i64)
- SerialOffset (i64)
- ScriptSerialSize (i64, UE5 only)
- ScriptSerialOffset (i64, UE5 only)
- TemplateIndex (i32, UE4 >= 506) ← BUG-01
```

### Phase 7 蓝图图解析

```
Graph → Nodes → Pins → Connections
  ↓
JSON 输出：
{
  "graphs": [
    {
      "graph_name": "Ubergraph",
      "nodes": [...],
      "connections": [...]
    }
  ]
}
```

### Phase 9 高级属性

```
StructProperty → 嵌套结构（递归深度 5）
MapProperty → 键值对数组
SetProperty → 唯一元素集
EnumProperty → 类型名 + 值名
TextProperty → FText 结构
DelegateProperty → 函数引用
```

### Phase 10 依赖图

```
{
  "imports": [
    {"class": "Class", "package": "Path", "object": "Name"}
  ],
  "soft_references": [
    {"asset_path": "/Game/Path.Asset"}
  ],
  "circular_deps": [
    ["A", "B", "A"]
  ]
}
```

---

*最后更新：2026-05-02 - v2.0 状态初始化完成*
