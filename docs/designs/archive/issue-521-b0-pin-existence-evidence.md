# Issue #521 B0a — Pin Existence Evidence

status: historical

> Status: diagnostic evidence (2026-08-05)
> Fixture: `tests/samples/NM_BPSystemEvent.uasset`
> SHA-256: `B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF`
> UE checkout: `E:/Develop/lib/UnrealEngine` @ `7deeb413d3dc1fc034f48d1aacc0861301829d32` (5.8.0-release) — verified before audit
> Script: `temp/inspect_521_node_tails.py` (read-only; parse output unchanged — `tests/temp/test_issue_521_niagara_coverage.py` + `tests/temp/test_issue_521_niagara_evidence.py` green after run)
> Report: `temp/b0a_report.txt`

## Method

Handler-recorded native tails (offset/size) were hex-inspected for pin markers:
FName-index-shaped int32 clusters, repeated 16-byte GUID blocks, ASCII name
fragments. No decoding was attempted by the committed script. The element
identification below additionally used byte-level struct.unpack walks of the
array payloads (inline diagnostics, not committed) cross-checked against the
pinned UE 5.8 checkout.

## Fixture package-version facts (input for the B0b gate)

The fixture is **not** a 5.8 package; B0b must version-check every cited code path.

- `FileVersionUE4` = 522, `FileVersionUE5` = 1004, `LicenseeVersion` = 0, legacy file version = -8.
- Engine version record: `5.0.0` changelist `16433597`, branch `++UE5+Release-5.0`.
- Property tags use the legacy (pre-`PROPERTY_TAG_COMPLETE_TYPE_NAME` = 1012) format.
- Custom versions (7, GUIDs matched against the pinned checkout):
  `FUE5MainStreamObjectVersion` = 59, `FReleaseObjectVersion` = 44,
  `FBlueprintsObjectVersion` = 10, `FFrameworkObjectVersion` = 37,
  `FUE5ReleaseStreamObjectVersion` = 33, `FEditorObjectVersion` = 40,
  `FNiagaraCustomVersion` = 70.

## Per-node-class tail inventory

Common node-tail shape (all 25 `NiagaraNode*` exports): `int32 0`, `int32 PinCount`,
then per pin `{int32 OwningNode, FGuid PinGuid, …full pin body…}`. The `OwningNode`
value equals the owning node's own PackageIndex in every pin checked; each PinGuid
appears twice per pin (once in the pin reference, once in the pin body), which is the
source of the "repeated 16-byte blocks" markers in the report. Pin names are
name-table FNames (e.g. `Value`, `Input`, `A`, `B`, `Result`, `Add`, `OutputMap`,
`Source`, `Dest`, `Local.Module.Event`, `InputPin`, `OutputPin`, `Selector`,
`NiagaraFloat if True/False`, `NiagaraParameterMap if true/false`). Pin types resolve
to the `NiagaraParameterMap` (PackageIndex −26) and `NiagaraFloat` (−23) imports via
`PinSubCategoryObject`.

| Node class | Export | Tail offset | Tail size | Markers found |
| --- | --- | --- | --- | --- |
| NiagaraGraph | NiagaraGraph_1 | 16059 | 4 | none (single zero int32) |
| NiagaraNodeFunctionCall | NiagaraNodeFunctionCall_17 | 16396 | 458 | 2 pins; 7 repeated 16-byte blocks; FName pin names `Value`, `Clamped Value`; LinkedTo → Op_4, MapSet_4 |
| NiagaraNodeInput | NiagaraNodeInput_170 | 17239 | 224 | 1 pin `Input` (EGPD source for reroute links) |
| NiagaraNodeOp | NiagaraNodeOp_1 | 17692 | 875 | 4 pins `A`, `B`, `Result`, `Add`; 13 repeated 16-byte blocks |
| NiagaraNodeOp | NiagaraNodeOp_2 | 18796 | 875 | 4 pins; 13 repeated blocks |
| NiagaraNodeOp | NiagaraNodeOp_4 | 19900 | 683 | 3 pins; 6 repeated blocks |
| NiagaraNodeOp | NiagaraNodeOp_52 | 20812 | 847 | 4 pins; 13 repeated blocks |
| NiagaraNodeOp | NiagaraNodeOp_73 | 21888 | 683 | 3 pins; 6 repeated blocks |
| NiagaraNodeOutput | NiagaraNodeOutput_1 | 23034 | 224 | 1 pin `OutputMap`; LinkedTo target present |
| NiagaraNodeParameterMapGet | NiagaraNodeParameterMapGet_1 | 23567 | 1550 | 6 pins (`Source`, `Local.Module.Event`, …); 36 repeated blocks |
| NiagaraNodeParameterMapGet | NiagaraNodeParameterMapGet_2 | 25426 | 1560 | 6 pins; 30 repeated blocks |
| NiagaraNodeParameterMapGet | NiagaraNodeParameterMapGet_3 | 27359 | 2701 | 10 pins; 87 repeated blocks |
| NiagaraNodeParameterMapGet | NiagaraNodeParameterMapGet_4 | 30401 | 2120 | 8 pins; 74 repeated blocks |
| NiagaraNodeParameterMapGet | NiagaraNodeParameterMapGet_7 | 32830 | 1526 | 6 pins; 49 repeated blocks |
| NiagaraNodeParameterMapSet | NiagaraNodeParameterMapSet_1 | 34552 | 916 | 4 pins (`Source`, `Dest`, `Local.Module.EventOccured`, `Add`); 23 repeated blocks |
| NiagaraNodeParameterMapSet | NiagaraNodeParameterMapSet_2 | 35664 | 1181 | 5 pins; 27 repeated blocks |
| NiagaraNodeParameterMapSet | NiagaraNodeParameterMapSet_3 | 37041 | 916 | 4 pins; 23 repeated blocks |
| NiagaraNodeParameterMapSet | NiagaraNodeParameterMapSet_4 | 38153 | 916 | 4 pins; 23 repeated blocks |
| NiagaraNodeParameterMapSet | NiagaraNodeParameterMapSet_7 | 39265 | 1214 | 5 pins; 25 repeated blocks |
| NiagaraNodeReroute | NiagaraNodeReroute_1 | 40675 | 464 | 2 pins `InputPin`/`OutputPin`; 19 repeated blocks |
| NiagaraNodeReroute | NiagaraNodeReroute_2 | 41335 | 464 | 2 pins; 19 repeated blocks |
| NiagaraNodeReroute | NiagaraNodeReroute_3 | 41995 | 464 | 2 pins; 19 repeated blocks |
| NiagaraNodeReroute | NiagaraNodeReroute_4 | 42655 | 464 | 2 pins; 19 repeated blocks |
| NiagaraNodeReroute | NiagaraNodeReroute_5 | 43315 | 464 | 2 pins; 19 repeated blocks |
| NiagaraNodeSelect | NiagaraNodeSelect_1 | 44453 | 1198 | 5 pins (`NiagaraFloat if True/False`, `Selector`, `NiagaraFloat`, `Add`); 48 repeated blocks |
| NiagaraNodeStaticSwitch | NiagaraNodeStaticSwitch_1 | 46290 | 972 | 4 pins (`NiagaraParameterMap if true/false`, `NiagaraParameterMap`, `Add`); 24 repeated blocks |
| NiagaraScript | NM_BPSystemEvent | 49651 | 4 | none (single zero int32) |
| NiagaraScriptSource | NiagaraScriptSource_1 | — | 0 | skipped export, no tail |
| NiagaraScriptVariable (×11) | _5,_7, _9,_11, _13,_15, _16,_18, _21,_24, _25 | 50234, 50802, 51303, 51845, 52387, 52888, 53389, 53890, 54432, 54974, 55516 | 4 each | none (single zero int32 each) |

Pin count total: 99 pins across the 25 nodes (2+1+18+1+36+22+10+5+4).

### Cross-verified LinkedTo connections (pin-level edges exist in the fixture)

Each entry was verified by matching the LinkedTo `{OwningNode, PinGuid}` pair against
the PinGuid recorded in the target node's pin body:

1. `NiagaraNodeReroute_1.InputPin` → node #7 (`NiagaraNodeInput_170`), PinGuid `34d05b1c-4050-45bb-8329-95ff0105ba11` = `Input` pin of NiagaraNodeInput_170.
2. `NiagaraNodeOp_1.Result` → node #29 (`NiagaraNodeSelect_1`), PinGuid `b4f1706a-aa59-4d0b-9643-a63275a895f0` = `NiagaraFloat if True` pin of NiagaraNodeSelect_1.
3. `NiagaraNodeSelect_1.NiagaraFloat` pin's LinkedTo PinGuid `a81fd90f-14d3-3c43-bf5c-c8c90f2d4f28` = the tagged `OutputVarGuids[0]` value of the same node (pin ↔ tagged-property cross-link).
4. `NiagaraNodeStaticSwitch_1.NiagaraParameterMap` → node #25 (`NiagaraNodeReroute_2`), PinGuid `52fa47e5-c073-48bb-8145-0326180583b6` = `InputPin` of NiagaraNodeReroute_2.

### Layout regions NOT yet mapped (B0b/B1 work, not guessable from fixture alone)

- The leading `int32 0` before the pin count in every node tail (comment nodes' tails are exactly the two zero int32s).
- The per-pin region between `PinFriendlyName` and `PinType`: two observed variants (plain pins: 14 constant bytes `ff 00 00 00 00 ff ff ff ff 00 00 00 00 00`; parameter/default-value pins: `i32(256) + u16(0)` + two FStrings — a 32-hex-digit ID string and the pin name string).
- A 5-byte `ff 00 00 00 00` marker immediately before the `LinkedTo` count on pins with connections.
- The pinned 5.8 pin serialization functions (`EdGraphPin.cpp` `UEdGraphPin::Serialize` line 1838, `SerializePinArray` line 2063, `SerializePin` line 2132; `EdGraphNode.cpp` `UEdGraphNode::Serialize` line 212, gated by `FBlueprintsObjectVersion::EdGraphPinOptimized` = 4, fixture value 10) match the observed structure but not these regions byte-for-byte; the exact writer layout for this fixture's UE5.0-era version must be fixed in B0b.

## Outputs/OutputVars element identification

All 7 `UnknownStruct` elements of the fixture are identified. Note the roadmap's
"(elements of `Outputs`/`OutputVars` arrays)" parenthetical is imprecise: the 7
occurrences span `CachedUsageInfo`, `Outputs`, `OutputVars`, `OutputVarGuids`, and
`VersionData` properties.

Mechanism note: in the legacy tag format an `ArrayProperty` tag carries only the
inner type name (`StructProperty`), not the element struct name — see
`LoadPropertyTagNoFullType` in `Engine/Source/Runtime/CoreUObject/Private/UObject/PropertyTag.cpp`
at the pinned commit. The element struct name is written inside the array payload as a
full per-element property tag (`name, type=StructProperty, size, array_index,
struct_name, struct_guid, has_property_guid`); the parser does not currently read
those element tags, hence `UnknownStruct`. Evidence below uses the element-tag struct
name plus payload field decoding plus the 5.8 member declarations.

| Element | Identified type | Evidence |
| --- | --- | --- |
| `NiagaraGraph_1.CachedUsageInfo[0]` | `FNiagaraGraphScriptUsageInfo` | Element-tag struct name index 98 = `NiagaraGraphScriptUsageInfo`; element size 544, payload field stream consumed 544/544: `BaseId:StructProperty(Guid)`, `UsageType:EnumProperty(ENiagaraScriptUsage)`, `UsageId:StructProperty(Guid)`, `CompileHash:StructProperty(NiagaraCompileHash)`, `CompileHashFromGraph:StructProperty(NiagaraCompileHash)`, `Traversal:ArrayProperty(ObjectProperty)` (25 node refs); array tag arithmetic 4+49+544=597 exact. Source (5.8): struct `NiagaraEditor/Public/NiagaraGraph.h:87`, member `TArray<FNiagaraGraphScriptUsageInfo> CachedUsageInfo` `NiagaraGraph.h:571`. Version delta: 5.8 member `ReferenceHashFromGraph` absent from the fixture stream. |
| `NiagaraNodeOutput_1.Outputs[0]` | `FNiagaraVariable` | Element-tag struct name index 106 = `NiagaraVariable`; payload = FName `Name`="OutputMap" + `FNiagaraTypeDefinition` tagged stream (`ClassStructOrEnum:ObjectProperty` = PackageIndex −26 → `NiagaraParameterMap` import; `UnderlyingType:UInt16Property` = 2 = `UT_Struct`; `Flags:ByteProperty` = 0) + trailing data blob (int32 count 1 + 1 byte); 4+49+111=164 exact. Source (5.8): `NiagaraNodeOutput.h:19` `TArray<FNiagaraVariable> Outputs`; `FNiagaraVariable`/`FNiagaraVariableBase` `Niagara/Public/NiagaraTypes.h:1460`/`:1281` (custom `Serialize` at `NiagaraModule.cpp:1732`/`:1763`). |
| `NiagaraNodeSelect_1.OutputVars[0]` | `FNiagaraVariable` | Same element layout; `Name`="NiagaraFloat" (name index 95), type PackageIndex −23 → `NiagaraFloat` import; 4+49+110=163 exact. Source (5.8): `TArray<FNiagaraVariable> OutputVars` in the shared base `NiagaraEditor/Private/NiagaraNodeUsageSelector.h:14-15` (UE5.0-era `UNiagaraNodeSelect` declares it directly; base class move is a version delta). |
| `NiagaraNodeSelect_1.OutputVarGuids[0]` | `FGuid` | Element-tag struct name index 70 = `Guid`; 16-byte binary payload `a81fd90f-14d3-3c43-bf5c-c8c90f2d4f28`; 4+49+16=69 exact; value equals the PinGuid of the same node's `NiagaraFloat` pin (see cross-verification 3). Source (5.8): `TArray<FGuid> OutputVarGuids` `NiagaraNodeUsageSelector.h:17-18`. |
| `NiagaraNodeStaticSwitch_1.OutputVars[0]` | `FNiagaraVariable` | Same element layout; `Name`="NiagaraParameterMap" (name index 100), type PackageIndex −26 → `NiagaraParameterMap` import; 4+49+110=163 exact. Source: as for `NiagaraNodeSelect_1.OutputVars[0]`. |
| `NiagaraNodeStaticSwitch_1.OutputVarGuids[0]` | `FGuid` | Element-tag struct name `Guid`; 16-byte payload `dffedb02-c620-f240-a912-1698e539e37d`; 4+49+16=69 exact. Source: as for `NiagaraNodeSelect_1.OutputVarGuids[0]`. |
| `NM_BPSystemEvent.VersionData[0]` (NiagaraScript) | `FVersionedNiagaraScriptData` | Element-tag struct name index 181 = `VersionedNiagaraScriptData`; payload field stream starts `Version:StructProperty(NiagaraAssetVersion)` (size 157), `VersionChangeDescription:TextProperty`, `ModuleUsageBitmask:IntProperty`, `Category:TextProperty`, `bSuggested:BoolProperty`; 4+49+2038=2091 exact. Source (5.8): struct `Niagara/Classes/NiagaraScript.h:619`, member `TArray<FVersionedNiagaraScriptData> VersionData` `NiagaraScript.h:873`. Version delta: 5.8 member `InlineOverviewDisplayName` (between `Category` and `bSuggested`) absent from the fixture stream. |

Task 9 intake mapping: `FNiagaraVariable`, `FNiagaraGraphScriptUsageInfo`,
`FVersionedNiagaraScriptData`, and the two `FGuid` arrays are the identified element
types (the `FGuid` elements need no struct decode beyond the 16-byte payload).

## Conclusion

**Pin structures FOUND in the fixture's node native tails → proceed to B0b with targets.**

- Pins are serialized inside each `NiagaraNode*` export's native tail as full pin
  records (count, OwningNode back-reference, persistent PinGuid, pin name, pin type,
  default values, `LinkedTo` arrays), with pin-level connections cross-verified between
  nodes and against the tagged `OutputVarGuids` properties.
- Targets for the B0b source audit: `UEdGraphNode::Serialize` →
  `UEdGraphPin::SerializeAsOwningNode` / `SerializePinArray` / `SerializePin`
  (`Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp`,
  `EdGraph/EdGraphNode.cpp` at the pinned commit), version-gated by
  `FBlueprintsObjectVersion::EdGraphPinOptimized`; plus the exact UE5.0-era writer
  layout for the unmapped regions listed above, and the fixture/package version
  gating deltas (fixture is UE5.0-era, checkout is 5.8).
- No pin-class exports exist in the fixture; all pin data is inline in the node tails.
- Execution-flow note: nothing in the tails indicates execution-order semantics;
  the A2 disposition (explicitly out of scope) is unaffected.
