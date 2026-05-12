# uasset_read 路线图

**项目：** uasset_read — Unreal Engine .uasset 解析工具
**创建日期：** 2026-04-27
**当前里程碑：** v6.0 模块化重构

## 里程碑概览

- ✅ **v1.0 MVP** — 阶段 1-5（已发布 2026-05-02）— [归档](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 蓝图图解析** — 阶段 6-10（已发布 2026-05-02，通过 PR #2）— [归档](milestones/v2.0-ROADMAP.md)
- ✅ **v3.x 解析完善+Skill+兼容性** — 阶段 11-17（已发布 2026-05-04，通过 PR #4）— [归档](milestones/v3.x-ROADMAP.md)
- ✅ **v4.0 节点属性深度解析** — 阶段 18-22（已发布 2026-05-05）— [归档](milestones/v4.0-ROADMAP.md)
- ✅ **v5.0 原功能完善及后续重构计划** — 阶段 23-26（已归档 2026-05-06）— [归档](milestones/v5.0-ROADMAP.md)
- ✅ **v5.1 项目结构初始化** — 仅阶段 27（已归档 2026-05-07）— [归档](milestones/v5.1-ROADMAP.md)
- 🔵 **v6.0 模块化重构** — 阶段 28-35（进行中）
- ⬜ **v7.0 深度序列化解析** — 阶段 36-40（已规划）
- ⬜ **v8.0 蓝图完整解析** — 阶段 41-45（已规划）
- ⬜ **v9.0 全资产覆盖与JSON规范化** — 阶段 46-50（已规划）

## 阶段列表

> 已完成里程碑的详细信息已归档到 `milestones/` 和 `archive/` 目录。

- ✅ v1.0-v5.1（阶段 1-27）— 已归档，详见各 [milestones/*.md](milestones/)

### v6.0 模块化重构（阶段 28-35）— 进行中

**设计原则：** 等价迁移现有 uasset_read.py 功能，不新增能力。零兼容包袱。

- [x] Phase 27: 项目结构初始化 (constants.py, exceptions.py) — 已完成
- [x] Phase 28: 核心序列化模块 (FArchive, PackageFileSummary, ImportMap/ExportMap) — 已完成 2026-05-11
- [x] Phase 28a: 测试基线修复 (7个已知失败修复 + stash关键bug合并) — 已完成 2026-05-11
- [x] Phase 29: 核心数据模型 (UEdGraph, UEdGraphNode, UEdGraphPin, ParseResult dataclasses) — 已完成 2026-05-11
- [x] Phase 29b: 属性与图数据模型 — 已合并到 Phase 30 一并实现
- [x] Phase 30: 属性解析模块 (PropertyTag, 属性解析器, 蓝图变量提取) — 已完成 2026-05-11
- [x] Phase 31: 蓝图图解析模块 (图解析, 节点读取, 连接关系构建) — 已完成 2026-05-12
- [x] Phase 32: 输出格式化模块 (JSON/Text/Markdown 输出) — 已完成 2026-05-12
- [ ] Phase 33: 入口与测试适配 (CLI, __init__.py, 测试更新, 删除旧文件)
- [ ] Phase 34: 等价验证 (新旧输出逐字段对比，零回归)

**里程碑目标：**
- 将 7,957 行单文件重写为 ~15 个模块
- 所有测试适配并通过（修复 7 个已知失败）
- 等价迁移：JSON/Text/Markdown 输出与旧版完全一致

**范围边界（v6.0 不包含）：**
- ❌ BulkData 内容解析 → v7.0
- ❌ UberGraph/事件分发图增强 → v8.0
- ❌ UBlueprintGeneratedClass 字节码反编译 → v8.0
- ❌ .umap/World 资产解析 → v9.0

### v7.0 深度序列化解析（阶段 36-40）— 已规划

**UE 对应阶段：** Object Serialization (FLinkerLoad Tick/LoadAllObjects)

- [ ] Phase 36: 导出体数据解析 (ExportBody 完整反序列化)
- [ ] Phase 37: Preload 数据解析 (Preload 依赖链)
- [ ] Phase 38: 对象引用图构建 (跨对象引用关系)
- [ ] Phase 39: BulkData 元数据解析 (批量数据头/偏移/大小)
- [ ] Phase 40: 版本化序列化支持 (UE 版本兼容性矩阵)

### v8.0 蓝图完整解析（阶段 41-45）— 已规划

**UE 对应阶段：** FinalizeCreation + UClass/UBlueprint 生成

- [ ] Phase 41: UBlueprintGeneratedClass 深度解析 (生成类结构)
- [ ] Phase 42: UberGraph 解析 (完整 UberGraph 数据)
- [ ] Phase 43: 事件分发图解析 (EventDispatcher 完整链路)
- [ ] Phase 44: 蓝图字节码反编译 (Kismet bytecode 参考解析)
- [ ] Phase 45: 蓝图 JSON 输出完整性验证

### v9.0 全资产覆盖与JSON规范化（阶段 46-50）— 已规划

- [ ] Phase 46: .umap/World 资产解析
- [ ] Phase 47: AssetRegistry 标签解析
- [ ] Phase 48: JSON Schema 定义与验证
- [ ] Phase 49: 性能优化 (mmap, 并行解析, 缓存)
- [ ] Phase 50: 生产级验证 (压力测试, 边界资产覆盖)

## 阶段详情

> 已完成阶段（27-31）的详细信息见各 phase 目录的 `*-SUMMARY.md`。

| 阶段 | 一句话摘要 |
|------|-----------|
| 27 | 创建 src layout + constants.py + exceptions.py |
| 28 | FArchive + PackageFileSummary + ImportMap/ExportMap 独立模块 |
| 28a | 修复 7 个测试失败 + 合并 stash 关键 bug |
| 29 | UEdGraph/Node/Pin + 5 个节点类型子类 + ParseResult 等 dataclass |
| 29b | 已合并到 Phase 30 |
| 30 | 14 种属性解析器 + PropertyTag/PropertyValue + blueprint/ 模块 |
| 31 | serializers/graph.py + graph/ 模块 + legacy shim 修复 |

### Phase 32: 输出格式化模块 🔵
**目标**: 等价迁移 Phase 14/20 的 JSON/Text/Markdown 输出
**依赖**: Phase 31
**成功标准**: JSON/Text/Markdown 输出与旧版一致
**计划**: 32-01 JSON 格式化 → 32-02 Text/Markdown → 32-03 测试适配

### Phase 33: 入口与测试适配 🔵
**目标**: CLI 入口 + `__init__.py` 公共 API + 测试更新 + 删除旧 `uasset_read.py`
**依赖**: Phase 28-32
**成功标准**: `python -m uasset_read file.uasset` 正常 + 旧文件删除 + 全测试通过
**计划**: 33-01 parse_uasset.py → 33-02 CLI 入口 → 33-03 测试适配 + 旧文件删除

### Phase 34: 等价验证 🔵
**目标**: 新旧输出逐字段对比，确保零回归
**依赖**: Phase 33
**成功标准**: 同一 .uasset 文件，新旧 JSON/Text/Markdown 输出 diff 为空

## 进度总览

| Phase | 里程碑 | 需求数 | 计划完成数 | 状态 | 完成日期 |
|-------|-----------|--------------|----------------|--------|-----------|
| 1-5 | v1.0 MVP | 25 | 25 | 已完成 | 2026-05-02 |
| 6-10 | v2.0 蓝图图解析 | 20 | 20 | 已完成 | 2026-05-02 |
| 11-17 | v3.x 解析完善+Skill | 23 | 23 | 已完成 | 2026-05-04 |
| 18-22 | v4.0 节点属性深度解析 | 14 | 14 | 已完成 | 2026-05-05 |
| 23-26 | v5.0 原功能完善 | 16 | 8 | 已完成 | 2026-05-06 |
| 27 | v5.1 项目结构初始化 | 4 | 2 | 已完成 | 2026-05-07 |
| 28 | v6.0 模块化重构 | 3 | 4 | 已完成 | 2026-05-11 |
| 28a | v6.0 测试基线修复 | 5 | 5 | 已完成 | 2026-05-11 |
| 29 | v6.0 核心数据模型 | 2 | 3 | 已完成 | 2026-05-11 |
| 29b | v6.0 属性与图数据模型 | 1 | 0 | 已合并→30 | 2026-05-11 |
| 30 | v6.0 属性解析 | 6 | 3 | 已完成 | 2026-05-11 |
| 31 | v6.0 蓝图图解析 | 3 | 6 | 已完成 | 2026-05-12 |
| 32 | v6.0 输出格式化 | 3 | 3 | 规划完成 | - |
| 33 | v6.0 入口与测试适配 | 2 | 3 | 规划完成 | - |
| 34 | v6.0 等价验证 | 2 | 0 | 未开始 | - |
| 36-40 | v7.0 深度序列化 | 15 | 0 | 已规划 | - |
| 41-45 | v8.0 蓝图完整解析 | 15 | 0 | 已规划 | - |
| 46-50 | v9.0 全资产+JSON规范化 | 15 | 0 | 已规划 | - |

**总计:** 50 个阶段（30 已完成，20 待执行）

**v6.0 需求覆盖:** 17/17 需求已映射（100%）+ 3 新增（测试基线/拆分模型/等价验证）

---

*最后更新：2026-05-12 — Phase 31 UAT 验证完成（11/11 passed），411 passed 47 skipped（Phase 33 适配待执行）*
