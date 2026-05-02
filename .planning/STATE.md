---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: 蓝图图解析
status: in_progress
last_updated: "2026-05-02T12:00:00Z"
progress:
  total_phases: 5
  completed_phases: 1
  active_phase: 7
  total_plans: 2
  completed_plans: 2
  percent: 20
shipped:
  date: null
  branch: null
  remote: null
---

# 项目状态

**项目：** uasset_read
**初始化：** 2026-04-27
**里程碑：** v2.0 —— 蓝图图解析
**状态：** 进行中 - Phase 7 上下文已收集，待规划

## 当前阶段

**Phase 7: 蓝图图核心解析** - 上下文已收集

## 阶段状态

| # | 阶段 | 状态 | 计划 | 验证 | 安全 | 进度 |
|---|------|------|------|------|------|------|
| 1 | 核心解析 | ✓ 完成 | 8/8 | ✓ | - | 100% |
| 2 | 属性解析 | ✓ 完成 | 3/3 | ✓ | - | 100% |
| 3 | 蓝图提取 | ✓ 完成 | 4/4 | ✓ | - | 100% |
| 4 | 输出与 CLI | ✓ 完成 | 5/5 | ✓ | ✓ | 100% |
| 5 | 优化与安全 | ✓ 完成 | 5/5 | ✓ | ✓ | 100% |
| 6 | 导出表修复 | ✓ 完成 | 2/2 | ✓ | TBD | 100% |
| 7 | 蓝图图核心 | ⏳ 待启动 | TBD | TBD | TBD | 0% |
| 8 | 蓝图图输出 | ⏳ 待启动 | TBD | TBD | TBD | 0% |
| 9 | 高级属性 | ⏳ 待启动 | TBD | TBD | TBD | 0% |
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
| 2026-05-02 | Phase 6 执行完成 | 导出表修复实现 |
| 2026-05-02 | Phase 6 验证通过 | 27 测试通过，无回归 |
| 2026-05-02 | Phase 6 完成提交 | 3 commits（实现、文档、验证） |

## 下一步动作

```
/gsd-discuss-phase 7 — 收集 Phase 7 上下文（蓝图图核心解析）
```

### Phase 6 规划要点

1. **OuterIndex 修复** - 在 read_export_map() 中正确读取字段偏移
2. **TemplateIndex 条件读取** - 检查 `summary.file_version_ue4 >= 506`
3. **错误上下文增强** - 添加 offset、phase、operation 字段
4. **版本检测** - 区分 UE4/UE5 文件格式

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
