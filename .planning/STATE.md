---
gsd_state_version: 1.0
milestone: v6.0
milestone_name: failed
status: archived
last_updated: "2026-05-14T00:00:00.000Z"
progress:
  total_phases: 12
  completed_phases: 10
  failed_phases: 2
  total_plans: 35
  completed_plans: 31
  percent: 89
---

# v6.0 模块化重构 — 已归档（失败）

## 状态: ❌ FAILED

**失败日期**: 2026-05-14
**失败阶段**: Phase 35-35e
**归档文档**: [v6.0-FAILED-ARCHIVE.md](milestones/v6.0-FAILED-ARCHIVE.md)

---

## 已完成阶段 (10/12)

| Phase | 名称 | 状态 |
|-------|------|------|
| 27-29 | 项目初始化与核心模块 | ✅ |
| 30 | 属性解析模块 | ✅ |
| 31 | 蓝图图解析模块 | ✅ |
| 32 | 输出格式化模块 | ✅ |
| 33/33a | 入口与 UE5 修复 | ✅ |
| 34 | 等价验证 | ✅ |
| 35a | 快速修复 | ✅ |
| 35c | 安全性修复 | ✅ |
| 35d | 逻辑与质量修复 | ✅ |

---

## 失败阶段 (2/12)

### Phase 35b: Pin 连接深度调试 — ⏭️ 已跳过（合并至 35e）

### Phase 35e: Pin Offset 根因诊断 — ❌ FAILED

**失败原因**: 执行严重偏离目标，字节对齐问题复杂度高，修复引入新问题

**遗留问题**:
- `linked_to_raw` 始终为空
- `data_flows` 无法正确构建
- PayloadTocOffset 解析错误

---

## 下一里程碑: v7.0 文档整理

**目标**: 压缩并整理项目文档，建立 UE 源码参考库

**范围**:
- 清理 .planning 目录
- 归档已完成阶段文档
- 建立 UE C++ 序列化函数参考
- 重构版本阈值判断框架