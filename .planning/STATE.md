---
gsd_state_version: 1.0
milestone: v7.0
milestone_name: UE 加载方式对齐 — 对象图重建
status: planning
last_updated: "2026-05-14T00:00:00.000Z"
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# v7.0 UE 加载方式对齐 — 对象图重建

## 状态: 📋 规划中

**创建日期**: 2026-05-14
**前置里程碑**: [v6.0 模块化重构](STATE.md) — ✅ 已完成

---

## 背景

v6.0 完成了模块化重构，但解析模式仍是**直接字节读取**：
- FArchive 顺序 seek/read，序列化器从已知偏移读取字段
- 对象引用（PackageIndex）仅解析为名字字符串，不是实际对象
- 无对象图概念，数据扁平化为 dataclass
- Outer 树（Package → Class → Properties 层级）未构建

**v6.0 Phase 35e 失败原因**: 试图通过字节级偏移修正解决 linked_to_raw 为空问题，但偏离了根本方向。真正的问题不是"差几个字节"，而是当前架构缺少 UE 编辑器的对象图重建机制。

---

## 目标

参考 UE 编辑器的 **FLinkerLoad 加载方式**，实现对象图重建：

| 当前 | 目标 |
|------|------|
| 文件 → FArchive → 扁平数据 | 文件 → FArchive → PackageLinker → UObjectInstance 对象图 |
| PackageIndex → 名字字符串 | PackageIndex → UObjectInstance 实际对象引用 |
| 无父子关系 | Outer 树可导航 |
| 重复解析 | 对象缓存，延迟加载 |

---

## Phase 分解

| Phase | 名称 | 目标 | 依赖 | 工作量 |
|-------|------|------|------|--------|
| **Phase 41** | link/ 模块基础设施 | 创建 UObjectInstance、PackageLinker、LinkerParseResult | 无 | 2h |
| **Phase 42** | 集成入口点 | parse_uasset_with_linker() 新增函数 | Phase 41 | 1h |
| **Phase 43** | PackageIndex 增强 | resolve_with_linker() 方法 | Phase 41 | 0.5h |
| **Phase 44** | 模型增强 | UEdGraphPin 新增 UObjectInstance 引用字段 | Phase 41 | 0.5h |
| **Phase 45** | 图序列化 linker 变体 | read_ue_graph_pin_with_linker() 等 | Phase 41, 44 | 2h |
| **Phase 46** | 测试与验证 | 单元测试 + 集成测试 + 回归测试 | Phase 42-45 | 3h |
| **总计** | | | | **~9h** |

---

## 关键设计决策

1. **不修改现有序列化器** — PackageLinker 坐于现有序列化器之上，复用它们读取头信息
2. **增量采用** — 新增 parse_uasset_with_linker() 作为并行入口点，现有 parse_uasset() 不变
3. **延迟加载** — preload(index) 按需反序列化属性，不一次性加载全部
4. **零回归** — 现有 373 个测试必须全部通过

## 验证标准

- [ ] 现有 373 测试全部通过（0 回归）
- [ ] linked_to_objects 非空且指向正确 Pin 对象
- [ ] Outer 树可导航：root → EdGraph → Node → Pin
- [ ] UE4/UE5 资产均正常工作
- [ ] parse_uasset() 行为完全不变
