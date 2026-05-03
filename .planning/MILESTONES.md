# Milestones

里程碑历史记录。

---

## v2.0 — 蓝图图解析

**Shipped:** 2026-05-02
**PR:** #2 MERGED (2026-05-02 15:41 UTC)
**Phases:** 5 | **Plans:** 20 | **Tasks:** ~80
**Timeline:** 5 days (2026-04-28 → 2026-05-02)

**Scope:** Phase 6-10
- Phase 6: 导出表修复（BUG-01~03）
- Phase 7: 蓝图图核心解析（GRAPH-01~09）
- Phase 8: 蓝图图输出增强（GRAPH-11~12, OUT2-01~04）
- Phase 9: 高级属性类型（ADVP-01~06）
- Phase 10: 依赖分析（DEPS-01~04）

**Key Accomplishments:**
1. 修复导出表FObjectExport结构缺失字段（TemplateIndex/OuterIndex）
2. 实现蓝图图三层解析（Graph → Node → Pin），支持9种节点类型
3. 构建引脚连接映射和执行流追踪（Event → CallFunction）
4. 实现六种高级属性解析（Struct/Map/Set/Enum/Text/Delegate）
5. 构建ImportMap + SoftObjectPaths依赖图，检测循环依赖

**Stats:**
- Commits: 151
- Files changed: 108
- Lines: +29,424 / -2,479
- Tests: 62+ passing
- Main file: 4,901 lines

**Archived:**
- [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)
- [milestones/v2.0-REQUIREMENTS.md](milestones/v2.0-REQUIREMENTS.md)

---

## v1.0 — MVP

**Shipped:** 2026-05-02
**Phases:** 5 | **Plans:** 25
**Timeline:** 1 day (2026-04-27 → 2026-04-28)

**Scope:** Phase 1-5
- Phase 1: 核心解析（PackageFileSummary、NameMap、ImportMap、ExportMap）
- Phase 2: 属性解析（基本属性类型）
- Phase 3: 蓝图提取（蓝图元数据）
- Phase 4: 输出与CLI（JSON、文本、命令行工具）
- Phase 5: 优化与安全（边界验证、性能优化）

**Key Accomplishments:**
1. 实现完整.uasset文件头解析
2. 提取名称表、导入表、导出表
3. 解析基本属性类型（IntProperty、FloatProperty、BoolProperty等）
4. 提取蓝图元数据（父类、变量）
5. CLI工具可用，输出JSON和文本格式

**Stats:**
- Main file: ~3,000 lines
- Tests: 27+ passing

**Archived:**
- [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md) — 待创建

---

*Last updated: 2026-05-02*