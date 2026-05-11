---
gsd_state_version: 1.0
milestone: v6.0
milestone_name: milestone
status: executing
last_updated: "2026-05-11T04:20:05.871Z"
progress:
  total_phases: 10
  completed_phases: 1
  total_plans: 2
  completed_plans: 2
  percent: 100
---

# v6.0 模块化重构 — 当前状态

## 已完成

- ~~Phase 27: 项目结构初始化~~ ✓ Complete (constants.py, exceptions.py)
- ~~Phase 28: 核心序列化模块~~ ✓ Complete (archive.py, serializers/) — 提交 ce110d2

## 当前焦点: Phase 28a — 测试基线修复

### 下一步

1. ~~Phase 28: 核心序列化模块~~ ✓ Complete
2. **Phase 28a: 测试基线修复** (7个已知失败修复 + stash关键bug合并)
3. Phase 29: 核心数据模型 (UEdGraph, Node, Pin, ParseResult dataclasses)
4. Phase 29b: 属性与图数据模型 (PropertyTag, FunctionReference, 图连接结构)
5. Phase 30: 属性解析模块
6. Phase 31: 蓝图图解析模块 (等价迁移 Phase 7/18-22)
7. Phase 32: 输出格式化模块 (等价迁移 Phase 14/20)
8. Phase 33: 入口与测试适配 + 删除旧 uasset_read.py
9. Phase 34: 等价验证 (新旧输出逐字段对比)

### 已知缺陷 (Phase 28a 修复目标)

| # | 测试 | 根因 | 修复方向 |
|---|------|------|----------|
| 1 | test_output_formatting.py:1315 | `graph_name` vs `graph` 键名 | 统一为 `graph` |
| 2 | test_phase14_output_formats.py:132 | 同上 | 同上 |
| 3 | test_phase21_verification.py:130 | Jump 节点未找到 | stash: pin容错 |
| 4 | test_phase21_verification.py:163 | StopJumping 未找到 | stash: pin容错 |
| 5 | test_phase21_verification.py:224 | Move 数据流缺失 | stash: pin修复 |
| 6 | test_phase21_verification.py:304 | function_reference=None | stash: FText跳过逻辑 |
| 7 | test_skill_integration.py:186 | function_name为空 | execution_flows提取修复 |

### Stash 待合并内容 (stash@{0})

- `peek_i32()` 方法添加到 FArchive
- `ETextHistoryType` 枚举修复 (None=255)
- FText 跳过逻辑改进 + 错误处理
- Pin 读取容错 (loop 变量修复)

### 待处理

- Stash 中有 uasset_read.py 和 test_phase21_verification.py 的修改
- 7 个已知测试失败 (前置问题, 非 Phase 28 引起)

### v6.0 范围边界

- **包含**: 等价迁移 uasset_read.py 全部功能 (~7,957 行 → ~15 模块)
- **不包含**: BulkData 解析 (v7.0)、UberGraph 增强 (v8.0)、字节码反编译 (v8.0)、.umap 解析 (v9.0)
