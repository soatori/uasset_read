# 解析质量体系：Diagnostic.reason 与样本基线门禁

status: target

> 关联：S1 `2026-08-31-v2-contract-stability.md`；权威 package-first 设计；证据 `temp/sample_parse/REVIEW.md`（33 类扫库，957 诊断中 905 为无分类 trailing）。
> 本设计不改 process-global logging；不改 `format_version`。

## 1. 目标

1. 用可选 `reason` 区分预期残量与可疑 recovery，使 unexpected 成为 CI 主信号。
2. 在 tracked fixtures 上建立 `quality_baseline.json` 门禁。
3. 深度解析修复（Niagara / BP name 集群 / RefSkeleton）不在本文实现范围，只定度量口径。

## 2. reason 值域（封闭）

bulk_expected | editor_only | known_unimplemented | recovered_corruption | conservative_complete | unexpected

规则：code 不变；`reason=None` 时 JSON 省略；不替代 `effect`；未知归 unexpected。

## 3. 接线点

- trailing: `legacy_reader` EXPORT_TRAILING_BYTES_UNCONSUMED + `TrailingContext` 上下文分类（class 桶规则 + `Default__*_C` CDO / AnimBlueprint generated-data 按 object name + Outer 归 known_unimplemented）
- recovery: archive `fstring_all_null` / `name_index_out_of_range` / `fname_index_shift_recovered` → recovered_corruption
- table: TABLE_PAYLOAD_RESIDUE / TABLE_ROWS_TRUNCATED → conservative_complete

## 4. 基线门禁

`tests/samples/quality_baseline.json`：按样本 allowed max（code×reason）与 forbidden_codes。默认种子：FirstPerson_DT_WeaponList、FirstPerson_T_GridChecker_A、FirstPerson_BS_Idle_Walk_Run、ALS_Mannequin_Skeleton、BP_CombatCharacter。

## 5. 成功标准

- 分类后 unexpected 为主要人工信号
- 门禁可红绿
- 无 format major bump

## 6. 非目标

Niagara/RefSkeleton 实现；库级日志；temp 全量扫库进 CI。
