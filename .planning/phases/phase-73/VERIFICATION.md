---
phase: 73
title: 验证计划
status: planned
created: "2026-05-24"
---

# Phase 73 验证计划

## 基线

当前可复现基线：

```text
Graphs: 4
Nodes: 37
Pins: 62
Pins with LinkedTo: 22 (35.5%)
Total LinkedTo refs: 24
```

## 必跑验证

```bash
python temp/linkedto_summary.py
python temp/phase73_pin_trace.py --asset E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset
python -m pytest tests/test_phase73_*.py -v
python -m pytest tests/ -v
```

## 验收表

| 项目 | 基线 | 目标 | 状态 |
|------|------|------|------|
| Total LinkedTo refs | 24 | >= 40 或逐项解释缺口 | 待验证 |
| EventGraph LinkedTo refs | 12 | >= 18 或逐项解释缺口 | 待验证 |
| EventGraph connections | 未确认 | >= 9 | 待验证 |
| FString all-null/truncated 日志 | 大量 | 显著下降并可归类 | 待验证 |
| LinkedTo recovery 误判 | 未统计 | 0 个弱 count=0 成功 | 待验证 |
| Phase 73 专项测试 | 无 | 全通过 | 待验证 |

## 失败处理

如果目标连接数未达到，不直接扩大扫描窗口。必须输出缺失连接表，包含：

- graph 名称
- node 名称和 class
- pin 名称和 pin guid
- LinkedTo 期望数量
- 实际读取位置
- 第一个错位字段
- 恢复失败原因
