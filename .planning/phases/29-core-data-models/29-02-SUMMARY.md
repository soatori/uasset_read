---
phase: "29-core-data-models"
plan: 02
status: complete
completed: "2026-05-11"
---

# Plan 29-02 Summary: Node Type Subclasses

## Objective
创建 `models/node_types.py` 定义 5 个 UEdGraphNode 子类，并更新模块导出。

## What Was Built
- `src/uasset_read/models/node_types.py` — 5 @dataclass inheriting UEdGraphNode:
  - K2NodeCallFunction: function_reference (Optional[FMemberReference]), b_defaults_to_pure
  - K2NodeEvent: event_reference (Optional[FMemberReference]), b_override_function
  - K2NodeKnot: no extra fields (base class only)
  - EdGraphNodeComment: comment_color (Tuple), node_width, node_height, font_size
  - K2NodeEnhancedInputAction: input_action_path (str)
- Updated `models/__init__.py` to export all 5 node types
- Updated `src/uasset_read/__init__.py` for backward-compatible re-exports

## Key Details
- All subclasses use Optional[FMemberReference] for reference fields (avoids required constructor args)
- Each class has `from_archive` classmethod stub (Phase 31)
- Inheritance verified: isinstance(K2NodeCallFunction(), UEdGraphNode) → True

## Verification
- 5 node types importable from `uasset_read` ✓
- Inheritance chain correct ✓
- from_archive stubs present ✓
