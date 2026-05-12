---
gsd_state_version: 1.0
milestone: v6.0
milestone_name: 模块化重构（阶段 28-35）— 进行中
status: executing
last_updated: "2026-05-13T00:50:00Z"
progress:
  total_phases: 31
  completed_phases: 26
  total_plans: 98
  completed_plans: 96
  percent: 98
---

# v6.0 模块化重构 — 当前状态

## 已归档（Phase 27-29）

Phase 27-29 已完成并归档到 `milestones/v6.0-ARCHIVE.md`:
- ✓ Phase 27: 项目结构初始化 (`constants.py`, `exceptions.py`)
- ✓ Phase 28: 核心序列化模块 (`FArchive`, `serializers/`)
- ✓ Phase 28a: 测试基线修复
- ✓ Phase 29: 核心数据模型 (`models/core.py`, `node_types.py`, `blueprint.py`, `result.py`)

---

## 已完成（Phase 30-35a）

### Phase 30: 属性解析模块 ✓ Complete
- 完成: 3 plans (property dataclasses + 14 type parsers + blueprint module)

### Phase 31: 蓝图图解析模块 ✓ Complete
- 完成: 6 plans (serializers/graph.py + from_archive delegates + graph/ module + test fixes)

### Phase 32: 输出格式化模块 ✓ Complete
- 完成: 3 plans (JSON + Text/Markdown + test adaptation, 107 passed)

### Phase 33: 入口与测试适配 + 删除旧 `uasset_read.py` ✓ Complete

### Phase 33a: UE5 序列化问题修复 ✓ Complete
**关键修复：UE5 序列化容错模式**
- UE5.0 蓝图文件的 `FText` 和 `PropertyTag` 序列化格式与 UE4 存在差异
- 添加 `tolerant` 参数到相关函数，CLI 支持 `--tolerant/--strict`
- **结果**: 383 passed, 71 skipped, 0 failed

### Phase 34: 等价验证 ✓ Complete
- 完成: 新旧输出逐字段对比
- **结果**: 397 passed, 71 skipped, 147 差异已分类，0 待修复 bug

### Phase 35a: 快速修复 ✓ Complete
- UAT 收尾项：`start_event` fallback, 脚本清理, `logging` 迁移
- **结果**: 397 passed, 71 skipped, 0 failed

---

## 当前焦点: Phase 35b — Pin 连接深度调试与修复

**状态**: 🟢 PLAN.md 已创建  
**创建日期**: 2026-05-13  
**优先级**: P0 - 阻塞

**问题来源**:
- AUDIT-REPORT.md FINDING-2/5
- Phase 22 VERIFICATION.md
- Phase 35 UAT Test 3

**核心问题**:
- `read_pin_array` 返回空列表 (`array_count=0`)
- `pins_offset` 动态扫描定位不准确
- UE5 `UEdGraphPin` 序列化格式版本差异未覆盖
- `FText` 跳过逻辑影响后续字段位置

**计划任务**:
- 35b-01: 调试环境搭建 (二进制分析工具 + DEBUG_PIN_PARSING 增强)
- 35b-02: `read_bool_ue5()` 修复 (UE5 PinType bool 占 1 byte)
- 35b-03: `BitField` 读取修复 (UE5 需要 u32，之前错误用 u8)
- 35b-04: `FText` `b_has_culture` 1-byte bool 修复
- 35b-05: `execution_flows` / `data_flows` 集成测试验证

**产出文档**:
- `.planning/phases/35b-pin-connection-debug/35b-PLAN.md` — 完整计划
- `.planning/phases/35b-pin-connection-debug/35b-CONTEXT.md` — 问题上下文

**成功标准**:
- `pin.linked_to_raw` 非空，包含连接引用
- `execution_flows` 能追踪从 Event 到 CallFunction 的完整链路
- `data_flows` 能提取非 exec pins 的数据传递关系
- BP_FirstPersonCharacter.uasset 的 EventGraph 能输出 `IA_Jump → Jump → StopJumping` 执行链路
- 全部测试通过 (411+ passed, 0 failed)

---

## v6.0 范围边界

- **包含**: 等价迁移 `uasset_read.py` 全部功能 (~7,957 行 → ~15 模块)
- **不包含**: BulkData 解析 (v7.0)、UberGraph 增强 (v8.0)、字节码反编译 (v8.0)、.umap 解析 (v9.0)
