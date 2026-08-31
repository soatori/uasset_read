# Design: UFunction Script Navigation Fix (Issue #77)

status: historical

## Problem Statement

The current parser cannot stably read serialized Kismet Script from real UFunction exports. The root cause is that the parser does not follow UE's native serialization order:

```
UObject -> UStruct -> UFunction -> FStructScriptLoader
```

Instead, the parser:

1. Misuses `script_serialization_start_offset` as Script start (it's actually for property-range semantics)
2. Assumes a BPGC function table layout that doesn't exist in UE 5.8
3. Uses ordinal mapping/serial scan to guess function attribution
4. Has incorrect FName/FFieldPath operand formats

## UE Serialization Order (UE 5.0-5.8)

Based on UE source verification:

1. **UStruct::Serialize** order:
   - Super::Serialize (parent class)
   - SuperStruct
   - Children (child functions/structs)
   - SerializeProperties (tagged property serialization)
   - FStructScriptLoader (bytecode)

2. **UFunction::Serialize** calls Super::Serialize, so each function's Script is located within its own UStruct serialization section.

3. **FStructScriptLoader** reads:
   - BytecodeBufferSize (i32)
   - SerializedScriptSize (i32)
   - Expression stream (until EX_EndOfScript)

4. **Key insight**: `script_serialization_start_offset` / `script_serialization_size` describe the tagged property range, NOT the bytecode location.

## Design Goals

### P1-A: Native UFunction Script Navigation

Implement navigation that follows UE's serialization order:

- For each Function/UFunction export, locate the FStructScriptLoader within its UStruct section
- Distinguish BytecodeBufferSize vs SerializedScriptSize
- Script must belong to the current Function export (no BPGC ordinal mapping)
- Use `script_serialization offsets` only for their real property-range semantics

### P1-B: Basic Operand Format Alignment

- EX_VirtualFunction, EX_LocalVirtualFunction: function names as FName (not FString)
- FFieldPath: TArray<FName> + version-gated owner
- Tests for FName.Number, owner present/absent, and version branches

### P1-C: Output and Status Semantics

- `decompiled_functions` only represents real UFunction exports (not K2Node_FunctionEntry/Result)
- Status values: `function_export`, `no_script`, `failed`, `graph_topology`
- Graph topology completion must be explicitly marked as inference
- Top-level status must aggregate function-level failures

## Implementation Plan

### Phase 1: Reproduce Version Matrix

Copy required assets from `E:\Develop\lib\Samples`:

- UE 5.0: Lyra GA_Hero_Jump
- UE 5.2: Cropout BP_Villager
- UE 5.6: FirstPerson BP_FirstPersonCharacter, StackOBot BP_MovingPlatform
- UE 5.7: GameAnimationSample BFL_HelpfulFunctions
- UE 5.8: FirstPerson BP_ShooterCharacter

Record hashes and version evidence for each.

### Phase 2: Implement Navigation Fix

1. **Modify `bytecode_extractor.py`**:
   - Remove BPGC fallback as primary path
   - Implement proper UStruct serialization navigation
   - Use `script_serialization_start_offset` only for property-range semantics

2. **Modify `expressions/functions.py`**:
   - Fix EX_VirtualFunction to read FName (not FString)
   - Fix EX_LocalVirtualFunction similarly

3. **Modify `property_pointer.py`**:
   - Fix FFieldPath to read TArray<FName> with Number
   - Implement version-gated owner serialization

### Phase 3: Add Tests

1. **Unit tests** for navigation logic
2. **Integration tests** for each version in the matrix
3. **Acceptance tests** for the specific cases in the issue

### Phase 4: Output Validation

1. Verify decompiled_functions only contains real UFunction exports
2. Verify status values are correct
3. Verify top-level status aggregates function failures

## Acceptance Criteria

- [x] Each real Function/UFunction export outputs exactly one result: success from function_export, confirmed no_script, or structured failure
- [x] Functions with Script show bytecode_source=function_export with complete expression stream ending in EX_EndOfScript
- [x] decompiled_functions no longer contains K2Node_FunctionEntry/Result pseudo-functions
- [x] bytecode_status=failed entries do not produce or imply verified cpp_code
- [ ] Top-level status summarizes function failures (no "all functions failed but package success")
- [x] Version matrix regression tests pass for all 6 samples
- [x] BP_FirstPersonCharacter: all 12 Function exports recovered from their own UFunction Script
- [x] BP_ShooterCharacter: no Property_-7 / Property_23265280 fallback garbage
- [x] JSON, Markdown, and internal results have consistent function status/source/errors
- [ ] Focused regression and full pytest pass

## Non-Goals

- Rebuild Blueprint visual layout
- Make serial scan "smarter" to replace native serialization
- Introduce BPGC per-function bytecode table (doesn't exist in UE source)
- Handle Material/Texture2D asset parser issues

## Task 4 Acceptance Evidence (2026-08-08)

### Hard gate

The six-sample test now fails unless all of the following remain true:

- all six required paths exist and retain their exact Function export counts;
- at least one parsed function exists;
- every parsed function reports `bytecode_source=function_export` and
  `logic_source=current_asset`;
- no function reports `bytecode_status=failed`;
- every remaining `no_script` function reports
  `error_code=confirmed_no_script` and four zero-valued Script header metrics;
- Aim, Move, and every Shooter function do not present graph topology as parsed
  bytecode;
- decompiled names exactly equal the real Function export names, with no
  `K2Node_` pseudo-functions;
- rendered JSON rejects `Property_-7`, `Property_23265280`,
  `fallback_or_serial_scan`, `serial_scan_recovery`, and
  `bpgc_bytecode_extraction`.

### TDD evidence

Baseline command:

```powershell
$env:PYTHONPATH='src'; pytest -q tests/temp/test_issue_77_real_samples.py
```

Before strengthening the assertions, the informational suite reported
`32 passed`, but its printed matrix was only `73 parsed / 0 no_script / 3 failed`.

After writing the hard assertions and before changing production code, the same
command was RED with `4 failed, 32 passed`. It proved:

- three native Script decode failures: Cropout `ExecuteUbergraph_BP_Villager`,
  Cropout `Get Current Resources`, and GameAnimation
  `DebugDraw_MultiLineGraph`;
- parsed FirstPerson/StackOBot results whose verified Function Script had been
  replaced with `logic_source=graph_topology`.

The decoder failures were traced to two native layout mismatches against
`Engine/Source/Runtime/CoreUObject/Public/UObject/ScriptSerialization.inl`:

1. `EX_MapConst` omitted the serialized `int32` element count. In
   `Get Current Resources`, bytes 86-89 are the zero count, but the old parser
   treated them as an `EX_LocalVariable` and overran at byte 95.
2. Modern `EX_SetArray` serializes its target as an expression. The old parser
   treated the leading `EX_LocalVariable` token as an `FFieldPath` count,
   producing a false count of 256 in the other two failures.

The minimal fixes read the missing map count, decode the SetArray target
expression, and prevent graph inference from overwriting already-parsed native
bytecode. No serial scan, ordinal mapping, BPGC table, K2Node pseudo-function,
or alternate bytecode source was introduced.

### Final matrix

All paths resolve below `E:\Develop\lib\Samples`:

| UE | Relative sample path | Expected | Parsed | No Script | Failed |
| --- | --- | ---: | ---: | ---: | ---: |
| 5.0 | `LyraStarterGame/Content/Characters/Heroes/Abilities/GA_Hero_Jump.uasset` | 7 | 7 | 0 | 0 |
| 5.2 | `CropoutSampleProject/Content/Blueprint/Villagers/BP_Villager.uasset` | 30 | 30 | 0 | 0 |
| 5.6 | `FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset` | 12 | 12 | 0 | 0 |
| 5.6 | `StackOBot/Content/StackOBot/Blueprints/GameElements/BP_MovingPlatform.uasset` | 8 | 8 | 0 | 0 |
| 5.7 | `GameAnimationSample/Content/Blueprints/Data/BFL_HelpfulFunctions.uasset` | 10 | 10 | 0 | 0 |
| 5.8 | `FirstPersonC/Content/Variant_Shooter/Blueprints/BP_ShooterCharacter.uasset` | 9 | 9 | 0 | 0 |
| **Total** | **6 assets** | **76** | **76** | **0** | **0** |

Final required command result: `36 passed in 3.03s`.

The combined #77 reader, dual-cursor/FName, pipeline/status/provenance, and real
sample run produced `257 passed in 3.76s`.

Repository-wide `pytest -q` produced `45 passed, 1 failed`. The sole failure is
the unrelated Markdown benchmark expectation for a `## Status` heading. The
same focused benchmark failure reproduces unchanged at the pre-Task-4 baseline
commit `4072ad3f`, so it is not a Task 4 regression and was not modified.

### Task 4 paths and commit

Implementation and regression paths:

- `src/uasset_read/kismet/expressions/containers.py`
- `src/uasset_read/kismet/semantic.py`
- `tests/temp/test_issue_77_kismet_archive.py`
- `tests/temp/test_decompiled_function_provenance.py`
- `tests/temp/test_issue_77_real_samples.py`
- `docs/designs/issue-77-ufunction-script-navigation.md`
- `.superpowers/sdd/task-4-report.md`

Commit subject: `test: enforce native UFunction sample acceptance (#77)`.
