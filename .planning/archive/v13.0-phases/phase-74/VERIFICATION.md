---
phase: 74
title: Phase 74 验证计划
status: Planned
created: 2026-05-25
---

# Phase 74 验证计划

## 当前验证状态

Phase 74 目前只建立计划文档和预期失败测试，不实施解析器主路径修改。

## 必须满足的验收标准

| 验收项 | 标准 |
|--------|------|
| PinReference null | 只消费 4B bool |
| PinReference non-null | 消费 24B，即 bool + OwningNode + PinGuid |
| Owning pin body | header 后 body 从 PinName 开始 |
| ParentPin / RefPassThrough | 与 SerializePin 规则一致 |
| LinkedTo 主路径 | 样本资产不再依赖 salvage 恢复关键连接 |
| 回归 | 全量 `pytest tests/ -q` 通过 |

## 执行记录模板

实现 Phase 74 后在此追加：

```text
Date:
Commit/branch:
Command:
Result:
LinkedTo failures:
P73 recovery events:
Notes:
```

## 参考证据

- UE `UEdGraphPin::SerializePinArray` / `SerializePin`
- UE `UEdGraphPin::Serialize`
- CUE4Parse `UEdGraphPin.SerializePinArray`
- CUE4Parse `UEdGraphPinReference`
- CUE4Parse `FArchive.ReadBoolean`
