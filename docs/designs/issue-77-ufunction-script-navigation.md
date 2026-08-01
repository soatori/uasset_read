# Design: UFunction Script Navigation Fix (Issue #77)

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

1. **UStruct::Serialize**顺序:
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

- [ ] Each real Function/UFunction export outputs exactly one result: success from function_export, confirmed no_script, or structured failure
- [ ] Functions with Script show bytecode_source=function_export with complete expression stream ending in EX_EndOfScript
- [ ] decompiled_functions no longer contains K2Node_FunctionEntry/Result pseudo-functions
- [ ] bytecode_status=failed entries do not produce or imply verified cpp_code
- [ ] Top-level status summarizes function failures (no "all functions failed but package success")
- [ ] Version matrix regression tests pass for all 6 samples
- [ ] BP_FirstPersonCharacter: 15 failures correctly classified, implemented functions recovered from real UFunction Script
- [ ] BP_ShooterCharacter: no Property_-7 / Property_23265280 fallback garbage
- [ ] JSON, Markdown, and internal results have consistent function status/source/errors
- [ ] Focused regression and full pytest pass

## Non-Goals

- Rebuild Blueprint visual layout
- Make serial scan "smarter" to replace native serialization
- Introduce BPGC per-function bytecode table (doesn't exist in UE source)
- Handle Material/Texture2D asset parser issues
