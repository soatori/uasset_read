---
phase: "29-core-data-models"
plan: 01
status: complete
completed: "2026-05-11"
---

# Plan 29-01 摘要：核心数据模型

## 目标
创建 `models/core.py` 定义 5 个核心 UE 蓝图数据类，并建立模块导出。

## 已构建内容
- `src/uasset_read/models/core.py` — 5 @dataclass: FEdGraphPinType, UEdGraphPin, UEdGraphNode, UEdGraph, FMemberReference
- `src/uasset_read/models/__init__.py` — flat exports for all 5 core classes
- `src/uasset_read/__init__.py` — backward-compatible re-exports

## 关键细节
- All fields match uasset_read.py:1878-1971 exactly
- Each class has `from_archive` classmethod stub (Phase 31 implementation)
- UEdGraphPin.pin_type typed as Optional[FEdGraphPinType]
- UEdGraphNode has class_name: str and node_data: Optional[Any] per D-04/D-05/D-11
- All classes use Python 3.10+ type hints with TYPE_CHECKING for FArchive

## 验证结果
- `from uasset_read import FEdGraphPinType, UEdGraphPin, UEdGraphNode, UEdGraph, FMemberReference` ✓
- `asdict()` works on all dataclasses ✓
- Field names match legacy definitions exactly ✓
