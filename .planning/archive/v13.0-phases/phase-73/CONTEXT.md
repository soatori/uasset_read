---
phase: 73
title: BP_FirstPersonCharacter Pin 序列化边界对齐修复
status: planned
created: "2026-05-24"
source:
  - .planning/P72-DIAGNOSIS-COMPLETE.md
  - .planning/P72-ROOT-CAUSE-ANALYSIS.md
  - .claude/worktrees/error-report/references/BP_FirstPersonCharacter-解析错误报告.md
  - temp/linkedto_summary.py
---

# Phase 73 上下文

## 阶段定位

Phase 73 是 Phase 72-I 之后的纠偏阶段。目标不是继续扩大 FString 容错，而是修复 BP_FirstPersonCharacter.uasset 中 Pin 读取的字段边界错位，使 LinkedTo、节点连接、函数图和关键属性能稳定解析。

当前快速修复已经让 LinkedTo 从 0 提升到 24 条引用，但日志仍显示大量 “把二进制数据误读为 FString” 的症状。这说明错误仍在上游字段边界，而不是 `read_fstring()` 返回值本身。

## 已确认事实

用当前工作区代码运行 `temp/linkedto_summary.py`，结果可复现：

| 指标 | 当前值 |
|------|--------|
| Graphs | 4 |
| Nodes | 37 |
| Pins | 62 |
| Pins with LinkedTo | 22 (35.5%) |
| Total LinkedTo refs | 24 |
| Aim LinkedTo 覆盖 | 5/9 pins (55.6%) |
| Move LinkedTo 覆盖 | 7/13 pins (53.8%) |
| EventGraph LinkedTo 覆盖 | 10/39 pins (25.6%) |
| UserConstructionScript LinkedTo 覆盖 | 0/1 pins |

## 根因修正

旧诊断报告中“FString 内部 null -> 返回空字符串 -> 位置偏移”的表述不够准确。

更准确的链路是：

```text
更早字段读取错位
  -> 后续把 GUID / PinReference / 数组 / 对象引用等二进制数据当作 FString
  -> read_fstring() 读到看似合法但实际错误的 length（如 256、4096、8448、9216）
  -> 按错误 length 消费大量字节
  -> LinkedTo count 在错误位置读取到垃圾值
  -> read_pin_array() 失败或恢复到错误的 0-count 候选
  -> 连接覆盖率只能部分恢复
```

关键点：

- `read_fstring()` 返回 `""` 或截断值，不会额外改变文件指针；指针已经按 length 消费。
- 内部 null 通常是“当前位置已经错了”的证据，不是单独根因。
- Phase 72 的 FString 截断补丁可以保留为输出容错，但不能视作根本修复。

## 主要故障面

| ID | 故障面 | 现象 | 优先级 |
|----|--------|------|--------|
| P73-01 | Pin 字段边界不可观测 | 无法判断 LinkedTo 前哪个字段第一次错位 | P0 |
| P73-02 | DefaultTextValue/FText 容错不回退 | FText tolerant 路径可能消费未知字节后继续 | P0 |
| P73-03 | LinkedTo 恢复候选过宽 | count=0 候选容易误判，导致“看似恢复”但连接丢失 | P0 |
| P73-04 | PinReference 格式验证不足 | owning_node / GUID / null marker 未做强校验 | P1 |
| P73-05 | PropertyTag 级联错位仍存在 | NodeComment、SCS、组件 Transform、Movement 属性缺失 | P1 |
| P73-06 | 连接输出缺少质量门禁 | 有 linked_to_raw 但缺少完整 graph connections 对标 | P1 |

## 约束

- 不能通过扩大扫描窗口掩盖根因；恢复逻辑必须有强校验。
- 所有二进制诊断脚本放在 `temp/`。
- 新增测试优先使用可重复的最小二进制片段；集成测试可在样本资产存在时运行，否则 skip。
- 文档和提交说明使用中文。

## 参考资产

- 主测试资产：`E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset`
- 错误报告：`.claude/worktrees/error-report/references/BP_FirstPersonCharacter-解析错误报告.md`
- 当前统计脚本：`temp/linkedto_summary.py`

## 阶段验收

硬性验收：

- Pin 字段级追踪能定位每个失败 Pin 的第一个错位字段。
- EventGraph LinkedTo refs 明显高于当前 12 条，并能解释剩余空连接是否为真实空连接。
- `read_pin_array()` 不再把弱校验的 count=0 当作成功恢复。
- FString 内部 null 日志减少，且每条都能归类为真实空串、错位读取或待支持格式。
- 新增 Phase 73 回归测试覆盖 FText 回退、PinReference 校验、LinkedTo 恢复误判。

目标验收：

- Total LinkedTo refs >= 40，或与 UE 编辑器参考连接数差异有逐项解释。
- EventGraph connections >= 9。
- Move/Aim 函数图连接链完整。
- 关键属性 NodeComment、Camera Transform、CharacterMovement 属性不再受 Pin 错位级联影响。
