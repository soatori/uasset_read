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

## 已完成

- ~~Phase 27: 项目结构初始化~~ ✓ Complete (constants.py, exceptions.py)
- ~~Phase 28: 核心序列化模块~~ ✓ Complete (FArchive, serializers/)
- ~~Phase 28a: 测试基线修复~~ ✓ Complete — 380 passed, 62 skipped
- ~~Phase 29: 核心数据模型~~ ✓ Complete (models/core.py, node_types.py, blueprint.py, result.py)
- ~~Phase 30: 属性解析模块~~ ✓ Complete (3 plans: property dataclasses + 14 type parsers + blueprint module)
- ~~Phase 31: 蓝图图解析模块~~ ✓ Complete (6 plans: serializers/graph.py + from_archive delegates + graph/ module + test fixes)
- ~~Phase 32: 输出格式化模块~~ ✓ Complete (3 plans: JSON + Text/Markdown + test adaptation, 107 passed)

## 当前焦点: Phase 35 — v6.0 里程碑完成 (next)

### 已完成

- ✅ Phase 34: 等价验证 — 397 passed, 71 skipped, 147 差异已分类，0 待修复 bug
- ✅ Phase 33: 入口与测试适配 + 删除旧 uasset_read.py
- ✅ Phase 33a: UE5 序列化问题修复
- ✅ Phase 35a: 快速修复 (UAT 收尾项：start_event fallback, 脚本清理, logging 迁移) — 397 passed, 71 skipped

### 下一步

1. Phase 35b: Pin 连接深度调试与修复 (linked_to_raw 根因修复) — **PLAN.md 已创建**
2. Phase 35c: v6.0 里程碑完成与发布准备

### Phase 35b - Pin 连接深度调试与修复

**状态**: 🟢 PLAN.md 已创建  
**创建日期**: 2026-05-13  
**优先级**: P0 - 阻塞

**问题来源**:
- AUDIT-REPORT.md FINDING-2/5
- Phase 22 VERIFICATION.md
- Phase 35 UAT Test 3

**核心问题**:
- `read_pin_array` 返回空列表 (array_count=0)
- `pins_offset` 动态扫描定位不准确
- UE5 UEdGraphPin 序列化格式版本差异未覆盖
- `FText` 跳过逻辑影响后续字段位置

**计划任务**:
- 35b-01: 调试环境搭建 (二进制分析工具 + DEBUG_PIN_PARSING 增强)
- 35b-02: read_ue_graph_pin 字段序列化顺序验证与修复
- 35b-03: read_pin_array 修复 (array_count 正确读取)
- 35b-04: FText 跳过逻辑修复
- 35b-05: execution_flows / data_flows 集成测试验证

**产出文档**:
- `.planning/phases/35b-pin-connection-debug/35b-PLAN.md` — 完整计划
- `.planning/phases/35b-pin-connection-debug/35b-CONTEXT.md` — 问题上下文

**成功标准**:
- `pin.linked_to_raw` 非空，包含连接引用
- `execution_flows` 能追踪从 Event 到 CallFunction 的完整链路
- `data_flows` 能提取非 exec pins 的数据传递关系
- BP_FirstPersonCharacter.uasset 的 EventGraph 能输出 IA_Jump → Jump → StopJumping 执行链路
- 全部测试通过 (411+ passed, 0 failed)

**相关修复记录**:
- Phase 35a - 快速修复 (不包含根因修复，属于 Phase 35b)
- Phase 33a - UE5 序列化问题修复 (FText, PropertyTag, 偏移校验 - 部分相关)

### Phase 33a 修复记录

**关键修复：UE5 序列化容错模式**

UE5.0 蓝图文件的 FText 和 PropertyTag 序列化格式与 UE4 存在差异：

- FText history_type 需要支持 0xFF (None), 0 (Base), 1-254 (Custom)
- PropertyTag size 可能为负数或超出边界，容错模式下接受

**修复内容：**

- serializers/graph.py: read_ftext_with_history() 函数 + read_ue_graph_pin 更新
- archive.py: validate_size() tolerant 参数
- serializers/property_tags.py: read_property_tag() tolerant 参数
- parse_uasset.py: tolerant 参数 (默认 True)
- cli.py: --tolerant/--strict 标志

**测试结果：** 383 passed, 71 skipped, 0 failed

### Phase 28a 修复记录

**关键发现：UE5 节点序列化格式变化**

UE5 将 `NodePosX`, `NodePosY`, `NodeGuid` 作为 PropertyTags 存储在 `script_serial` 区域，而非 pins 解析后的裸 i32 字段。

**修复内容：**

- uasset_read.py: 在 PropertyTags 循环中提取 NodePosX/NodePosY/NodeGuid/NodeComment
- build_graphs_summary: 过滤空 flow (EnhancedInputAction Started/Ongoing)
- test_property_parsing.py: 12 个测试更新为 FPropertyTypeName 格式
- test_output_formatting.py: mock 数据连接方向修复

**测试结果：** 411 passed, 47 skipped

### v6.0 范围边界

- **包含**: 等价迁移 uasset_read.py 全部功能 (~7,957 行 → ~15 模块)
- **不包含**: BulkData 解析 (v7.0)、UberGraph 增强 (v8.0)、字节码反编译 (v8.0)、.umap 解析 (v9.0)
