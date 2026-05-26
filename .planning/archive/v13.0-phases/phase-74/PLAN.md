---
phase: 74
title: UE/CUE4Parse 对齐的 PinReference 主路径修复计划
status: Planned
created: 2026-05-25
---

# Phase 74 计划

## 目标

把 PinReference / UEdGraphPin 读取边界对齐 UE 源码和 CUE4Parse，实现后 `BP_FirstPersonCharacter.uasset` 的 `LinkedTo` 读取应主要走主路径，而不是依赖 `[P73-SUBPINS]` / salvage 恢复。

## 非目标

- 不重写整个 graph parser。
- 不修改 N2C、formatter、Kismet bytecode 的架构。
- 不通过扩大扫描窗口掩盖 offset 错位。
- 不删除 Phase 73 诊断能力。

## PLAN-74-01: PinReference null 语义测试先行

新增 `tests/test_phase74_pin_reference_layout.py`，以 xfail 形式锁定未来行为：

- null PinReference 只消费 4 字节 bool。
- non-null PinReference 消费 24 字节。
- `validate_pin_reference_at()` 对 4 字节 null ref 返回有效结构。
- `read_pin_array()` 中 null 元素不应吞掉后续元素。

## PLAN-74-02: Owning pin body 起点测试先行

同一测试文件锁定 owning pin body 布局：

- `read_ue_graph_node()` 读完 `bNullPtr + OwningNode + PinGuid` 后，`read_ue_graph_pin()` 的 archive 位置应已经位于 `PinName`。
- 传入 `header_owning_node/header_pin_id` 时，`read_ue_graph_pin()` 不再额外消费 `OwningNode + PinGuid`。
- 最小二进制样例中第一个字段必须按 `FName PinName` 解析。

## PLAN-74-03: 主路径实现

实现时只改 `src/uasset_read/serializers/graph.py`：

- `read_pin_reference()`:
  - 读取 4B bool。
  - `1` 立即返回 `None`。
  - `0` 继续读取 `OwningNode + PinGuid`。
  - 其他 bool 值视为无效结构。
- `validate_pin_reference_at()`:
  - 支持 4B null ref。
  - non-null ref 才要求 24B。
  - 返回结构中可包含 `serialized_size`，供数组验证递进使用。
- `read_ue_graph_pin()`:
  - 当收到 header 参数时，不再读取或丢弃内部 duplicate。
  - `pin_start_pos` 应对应 `PinName` 起点。
- `ParentPin` 和 `ReferencePassThroughConnection`:
  - 复用 `read_pin_reference()`。
  - null 时只消费 4B。

## PLAN-74-04: 端到端验收

强化或新增端到端断言：

- `BP_FirstPersonCharacter.uasset` 解析时 `LinkedTo read failed` 为 0，或以明确阈值记录例外。
- `[P73-SUBPINS]` / `[P73-SALVAGE]` 不参与关键连接恢复。
- EventGraph 关键执行边和数据边仍通过：
  - `IA_Move Triggered -> Move`
  - `IA_Look Triggered -> Aim`
  - `IA_MouseLook Triggered -> Aim`
  - `IA_Jump Started -> Jump`
  - `IA_Jump Completed -> StopJumping`
  - `ActionValue_X -> Left / Right`
  - `ActionValue_Y -> Forward / Backward`

## 验证命令

```bash
python -m pytest tests/test_phase74_pin_reference_layout.py tests/test_phase73_bp_first_person_e2e.py tests/test_phase73_linkedto_recovery.py -q
python -m pytest tests/ -q
```

Phase 74 实现前，`test_phase74_pin_reference_layout.py` 中的测试应保持 xfail。实现完成后移除 xfail，并要求全部通过。
