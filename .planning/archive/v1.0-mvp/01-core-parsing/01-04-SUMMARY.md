---
phase: 01-core-parsing
plan: 04
subsystem: parsing
tags: [byte-swapping, utf-8, farchive, tdd]

# 依赖图
requires:
  - phase: 01-core-parsing
    provides: FArchive, PackageFileSummary, name table parsing
provides:
  - 大端序文件的正确字节交换
  - 字节交换文件中 UTF-8 字符串内容保持不变
  - 数值的类型特定字节序处理
affects: [core-parsing, phase-2]

# 技术追踪
tech-stack:
  added: []
  patterns: [byte-order-aware-reading, tdd-per-feature]

key-files:
  created: []
  modified:
    - uasset_read.py
    - tests/test_uasset_read.py

key-decisions:
  - "原始字节读取从不反转 - UTF-8、GUIDs、SavedHash 与字节序无关"
  - "类型特定方法根据 byte_swapping 标志使用格式字符串（'>' 或 '<'）"

patterns-established:
  - "模式：字节交换仅通过格式字符串应用于数值类型，不应用于原始字节"

requirements-completed: [CORE-01, CORE-02]

# 指标
duration: 5min
completed: 2026-04-28
---
# 阶段 01 计划 04：字节交换修复摘要

**修复关键的字节交换 bug，大端序文件中 UTF-8 字符串数据被错误反转**

## 性能

- **时长：** 5 min
- **开始：** 2026-04-28T04:46:22Z
- **完成：** 2026-04-28T04:51:13Z
- **任务：** 3（TDD: RED -> GREEN -> verified）
- **修改文件：** 2

## 成果
- FArchive.read() 不再反转原始字节（UTF-8、GUIDs、SavedHash 保持不变）
- 类型特定方法（read_i32、read_u32、read_i64、read_u64、read_f32）使用字节交换感知格式字符串
- 全部 17 个测试通过，包括 3 个字节交换行为新测试

## 任务提交

每个任务原子提交（遵循 TDD 模式）：

1. **任务 1-3：字节交换修复** - `9ad8ae8`（修复）
   - RED：为原始字节和类型特定方法添加失败测试
   - GREEN：修复 FArchive.read() 和类型特定方法
   - Verified：所有测试通过，包括新字符串内容测试

_注意：任务 1、2 和 3 是同一 bug 修复的相互依赖部分，遵循 TDD 流程一起提交_

## 创建/修改文件
- `uasset_read.py` - 修复 FArchive.read() 和类型特定方法以正确处理字节序
- `tests/test_uasset_read.py` - 添加 3 个字节交换行为新测试

## 决策
- 原始字节读取（read()）从不反转 - UTF-8 编码与字节序无关
- byte_swapping=True 时类型特定方法使用 '>' 格式，否则使用 '<'
- 字节交换在类型级别控制，不在原始字节级别

## 与计划的偏差

无 —— 计划完全按预期执行。TDD 流程正确遵循：
1. 为任务 1 和 2 添加失败测试
2. 实现 FArchive.read() 修复（任务 1）
3. 实现类型特定方法修复（任务 2）
4. 添加任务 3 测试（由于修复已到位，已通过）

## 遇到的问题
- 测试中 cleanup_test_file 有 PermissionError - 通过确保 cleanup 前 archive.close() 修复
- 测试清理顺序重要 - 临时文件删除前必须关闭 archive

## 下一阶段准备
- 核心解析完成，字节交换 bug 已修复
- 全部 17 个测试通过
- 准备阶段 2（属性解析）规划

---
*阶段：01-core-parsing*
*完成：2026-04-28*

## 自检：通过

- SUMMARY.md 存在
- uasset_read.py 存在
- tests/test_uasset_read.py 存在
- 提交 9ad8ae8 存在
- 全部 17 个测试通过