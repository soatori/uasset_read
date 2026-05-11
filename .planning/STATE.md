---
gsd_state_version: 1.0
milestone: v6.0
milestone_name: milestone
status: executing
last_updated: "2026-05-11T17:15:00Z"
progress:
  total_phases: 10
  completed_phases: 3
  total_plans: 5
  completed_plans: 5
  percent: 100
---

# v6.0 模块化重构 — 当前状态

## 已完成

- ~~Phase 27: 项目结构初始化~~ ✓ Complete (constants.py, exceptions.py)
- ~~Phase 28: 核心序列化模块~~ ✓ Complete (archive.py, serializers/)
- ~~Phase 28a: 测试基线修复~~ ✓ Complete — 411 passed, 47 skipped
- ~~Phase 29: 核心数据模型~~ ✓ Complete (models/core.py, node_types.py, blueprint.py, result.py)

## 当前焦点: Phase 30 — 属性解析模块

### 下一步

1. **Phase 30: 属性解析模块** (PropertyParser, property type handlers)
2. Phase 29b: 属性与图数据模型 (PropertyTag, FunctionReference, 图连接结构)
3. Phase 30: 属性解析模块
4. Phase 31: 蓝图图解析模块 (等价迁移 Phase 7/18-22)
5. Phase 32: 输出格式化模块 (等价迁移 Phase 14/20)
6. Phase 33: 入口与测试适配 + 删除旧 uasset_read.py
7. Phase 34: 等价验证 (新旧输出逐字段对比)

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