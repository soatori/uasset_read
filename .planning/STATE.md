---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: 蓝图图解析
status: in_progress
last_updated: "2026-05-02T06:00:00Z"
progress:
  total_phases: 5
  completed_phases: 0
  active_phase: 6
  total_plans: 0
  completed_plans: 0
  percent: 0
shipped:
  date: null
  branch: null
  remote: null
---

# 项目状态

**项目：** uasset_read
**初始化：** 2026-04-27
**里程碑：** v2.0 —— 蓝图图解析
**状态：** 进行中 - Phase 6 待启动

## 当前阶段

**Phase 6: 导出表修复** - 待启动

## 阶段状态

| # | 阶段 | 状态 | 计划 | 验证 | 安全 | 进度 |
|---|------|------|------|------|------|------|
| 1 | 核心解析 | ✓ 完成 | 8/8 | ✓ | - | 100% |
| 2 | 属性解析 | ✓ 完成 | 3/3 | ✓ | - | 100% |
| 3 | 蓝图提取 | ✓ 完成 | 4/4 | ✓ | - | 100% |
| 4 | 输出与 CLI | ✓ 完成 | 5/5 | ✓ | ✓ | 100% |
| 5 | 优化与安全 | ✓ 完成 | 5/5 | ✓ | ✓ | 100% |
| 6 | 导出表修复 | ⏳ 待启动 | TBD | TBD | TBD | 0% |
| 7 | 蓝图图核心 | ⏳ 待启动 | TBD | TBD | TBD | 0% |
| 8 | 蓝图图输出 | ⏳ 待启动 | TBD | TBD | TBD | 0% |
| 9 | 高级属性 | ⏳ 待启动 | TBD | TBD | TBD | 0% |
| 10 | 依赖分析 | ⏳ 待启动 | TBD | TBD | TBD | 0% |

## v2.0 进度

### 快照
- **里程碑：** v2.0 —— 蓝图图解析
- **起始点：** v1.0 完成（5/5 阶段，2026-05-02）
- **当前状态：** v2.0 路线图已创建，待阶段规划

### 覆盖率
- **v2.0 需求总数：** 29
- **已映射：** 29
- **未映射：** 0 ✓

### 阶段规划
- **Phase 6：** 导出表修复（BUG-01~03）- OuterIndex/TemplateIndex 修复
- **Phase 7：** 蓝图图核心解析（GRAPH-01~10）- Graph→Node→Pin
- **Phase 8：** 蓝图图输出增强（GRAPH-11~12, OUT2-01~04）- JSON/文本
- **Phase 9：** 高级属性类型（ADVP-01~06）- Struct/Map/Set/Enum/Text/Delegate
- **Phase 10：** 依赖分析（DEPS-01~04）- ImportMap + SoftObjectPaths

## 近期活动

| 日期 | 动作 | 结果 |
|------|------|------|
| 2026-04-27 | 项目初始化 | PROJECT.md、config.json 创建 |
| 2026-04-27 | 研究完成 | STACK.md、FEATURES.md、ARCHITECTURE.md、PITFALLS.md 写入 |
| 2026-04-27 | 研究综合 | SUMMARY.md 写入 |
| 2026-04-27 | 需求定义 | 37 个 v1 需求映射到 5 阶段 |
| 2026-04-27 | v1.0 路线图创建 | 5 阶段定义配成功标准 |
| 2026-04-28 | 阶段 1 上下文收集 | 01-CONTEXT.md 创建，含 18 项决策 |
| 2026-04-28 | 文档汉化完成 | 所有规划文档翻译为中文 |
| 2026-04-28 | 阶段 1 规划完成 | 01-01-PLAN.md 创建，4 任务，覆盖 8 需求 |
| 2026-04-28 | 阶段 1 执行完成 | uasset_read.py（719 行）、tests（549 行）创建 |
| 2026-04-28 | 阶段 1 验证通过 | 4/4 truths 验证，13 测试通过 |
| 2026-04-28 | SavedHash gap 修复 | 01-03-PLAN.md 执行完成，14 测试通过 |
| 2026-04-28 | Gap Closure 执行 | 01-04~01-08 执行完成，28 测试通过 |
| 2026-04-28 | Lyra 文件解析成功 | Character_Default.uasset 解析成功 |
| 2026-05-01 | 阶段 2 上下文收集 | 02-CONTEXT.md 创建，含 27 项决策 |
| 2026-05-01 | 阶段 2 规划完成 | 02-01~02-03 计划创建 |
| 2026-05-01 | 阶段 2 执行完成 | PropertyTag 解析、基本类型、Array 属性 |
| 2026-05-01 | 阶段 2 验证通过 | 9/9 truths 验证，62 测试通过 |
| 2026-05-01 | 阶段 3 上下文收集 | 03-CONTEXT.md 创建 |
| 2026-05-01 | 阶段 3 规划完成 | 03-01~03-03 计划创建 |
| 2026-05-01 | 阶段 3 执行完成 | FEdGraphPinType、BlueprintVariable、extract_blueprint_metadata |
| 2026-05-01 | 阶段 3 验证通过 | 83 测试通过 |
| 2026-05-01 | 阶段 4 上下文收集 | 04-CONTEXT.md 创建 |
| 2026-05-01 | 阶段 4 规划完成 | 04-00~04-04 计划创建 |
| 2026-05-01 | 阶段 4 执行完成 | format_json_full/text_full、CLI argparse |
| 2026-05-01 | 阶段 4 验证通过 | 94 测试通过 |
| 2026-05-02 | 阶段 4 UAT 通过 | 10/10 测试通过 |
| 2026-05-02 | 阶段 4 安全审查通过 | 4 威胁已缓解 |
| 2026-05-02 | 阶段 5 Wave 1 完成 | mmap 大文件支持 |
| 2026-05-02 | 阶段 5 Wave 2 完成 | 边界验证增强 |
| 2026-05-02 | 阶段 5 Wave 3 完成 | 循环计数限制 |
| 2026-05-02 | 阶段 5 Wave 4 完成 | 部分结果改进 |
| 2026-05-02 | 阶段 5 验证通过 | SAFE-01~05 全部覆盖 |
| 2026-05-02 | 项目完成 | v1.0 milestone 达成（5/5 阶段） |
| 2026-05-02 | v2.0 研究完成 | SUMMARY.md 包含蓝图图解析分析 |
| 2026-05-02 | v2.0 需求定义 | 29 个 v2.0 需求定义完成 |
| 2026-05-02 | v2.0 路线图创建 | 5 阶段（Phase 6-10）定义 |
| 2026-05-02 | Phase 6 上下文收集 | 06-CONTEXT.md 创建，21 项决策 |

## 项目参考

参见：
- `.planning/PROJECT.md`（2026-05-02 更新）
- `.planning/REQUIREMENTS.md`（2026-05-02 需求定义）
- `.planning/research/SUMMARY.md`（2026-05-02 研究综合）
- `.planning/ROADMAP.md`（本文档）

**核心价值：** 让 AI agent 能直接读取 .uasset 文件内容，无需人工介入 UE 编辑器
**当前重点：** v2.0 蓝图图解析（Phase 6-10）
**下步动作：** `/gsd-plan-phase 6` - 规划 Phase 6 (导出表修复)

## 关键决策

| 决策 | 状态 | 影响 |
|------|------|------|
| Python 3.10+ 零运行时依赖 | 已决定 | 部署更简单 |
| 专注于未 cooked 资产 | 已决定 | 完整蓝图数据可用 |
| v1.0 采用分层管道 | 已完成 | 基础架构稳定 |
| v2.0 复用现有架构 | 已决定 | 无需重构 |
| 新增组件集成模式 | 已决定 | GraphParser、AdvancedPropParser |
| FObjectExport 版本敏感 | 已决定 | TemplateIndex 条件读取 |

## 下一步动作

```
/gsd-plan-phase 6 —— 规划 Phase 6 (导出表修复)
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
