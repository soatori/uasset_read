# #521 Niagara Field Contracts

> Generated: 2026-08-02; Revised: 2026-08-05 (B2 pin projection results)
> Fixture: `tests/samples/NM_BPSystemEvent.uasset`
> SHA-256: `B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF`

## NiagaraGraph Contract

### Output Schema

```json
{
  "graph_name": "<FName string>",
  "node_exports": [{ "export_index": 0, "class": "<string>" }],
  "tagged_properties": {},
  "native_tail": { "offset": 0, "size": 0, "status": "opaque" }
}
```

### Actual Properties from Fixture

| Property Name | Type | Description |
|--------------|------|-------------|
| `ChangeId` | StructProperty (Guid) | Tracks graph change history |
| `LastBuiltTraversalDataChangeId` | StructProperty (Guid) | Last built traversal data version |
| `CachedUsageInfo` | ArrayProperty (opaque struct) | Cached script usage information |
| `VariableToScriptVariable` | MapProperty (Int→Int) | Variable mapping to script variables |
| `Nodes` | ArrayProperty (object refs) | UEdGraph::Nodes — graph node references |

### Field Sources

| Output Field | Source | Evidence |
|-------------|--------|----------|
| `graph_name` | Export `object_name` | `NiagaraGraph_1` |
| `node_exports` | `Nodes` property, PackageIndex-resolved | 25 entries, all NiagaraNode* classes |
| `tagged_properties` | All tagged properties | 5 properties parsed |
| `native_tail` | OPAQUE_CLASS_PAYLOAD handler | remainder after tagged properties |

### Nodes Index Semantics (verified against internal export table)

`Nodes` entries are object references serialized as `PackageIndex`:
positive value = export index + 1 (1-based), negative = import, 0 = null.
Resolution: `export_index = value - 1`.

Fixture composition (28 refs): 25 `NiagaraNode*` nodes + 3 `EdGraphNode_Comment`.
Comment nodes are valid references but out of contract scope (not projected).

Composition pinned by tests (`test_niagara_graph_has_node_exports`):

| Class | Count |
|-------|-------|
| NiagaraNodeFunctionCall | 1 |
| NiagaraNodeInput | 1 |
| NiagaraNodeOp | 5 |
| NiagaraNodeOutput | 1 |
| NiagaraNodeParameterMapGet | 5 |
| NiagaraNodeParameterMapSet | 5 |
| NiagaraNodeReroute | 5 |
| NiagaraNodeSelect | 1 |
| NiagaraNodeStaticSwitch | 1 |

### Removed Field: `script_exports`

The original contract claimed `script_exports` was "derived from `Nodes`
property — references to NiagaraScript exports". This was disproven by the
2026-08-04 audit: under verified PackageIndex semantics, all 28 `Nodes`
entries resolve to graph nodes (25 NiagaraNode* + 3 EdGraphNode_Comment);
none reference a NiagaraScript. The graph holds no script reference in its
tagged properties. The graph→script relationship is only observable
indirectly (e.g. `NiagaraNodeFunctionCall.FunctionScript` object refs).

### Fallback Behavior

- Missing property: field omitted, no fabricated default
- Invalid object reference (null, import, out-of-range, unresolvable class): omitted from `node_exports`
- Unknown version: preserve raw bytes in `native_tail`

---

## NiagaraScript Contract

### Output Schema

```json
{
  "script_name": "<FName string>",
  "script_usage": "<string>",
  "tagged_properties": {},
  "native_tail": { "offset": 0, "size": 0, "status": "opaque" }
}
```

### Actual Properties from Fixture

| Property Name | Type | Description |
|--------------|------|-------------|
| `Usage` | EnumProperty | value_name: `ENiagaraScriptUsage::Module` |
| `ExposedVersion` | StructProperty (Guid) | Exposed version information |
| `VersionData` | ArrayProperty (opaque struct) | Version compatibility data |
| `RapidIterationParameters` | StructProperty (NiagaraParameterStore) | Rapid iteration parameter set |

### Field Sources

| Output Field | Source | Evidence |
|-------------|--------|----------|
| `script_name` | Export `object_name` | `NM_BPSystemEvent` |
| `script_usage` | `Usage` property `value_name` | `ENiagaraScriptUsage::Module` |
| `tagged_properties` | All tagged properties | 4 properties parsed |
| `native_tail` | OPAQUE_CLASS_PAYLOAD handler | remainder after tagged properties (bytecode region) |

### Removed Fields: `target_environment`, `graph_export_ref`

- `target_environment` was claimed "derived from Usage". Disproven: the
  `Usage` enum (`ENiagaraScriptUsage`: System/Emitter/Module/Function/…)
  encodes script role, not target platform/environment. No
  TargetEnvironment property exists in the fixture.
- `graph_export_ref` was claimed derivable from "corresponding
  NiagaraGraph export" object name. Disproven: the script carries no
  object reference to its source graph (fixture names show no
  correspondence: script `NM_BPSystemEvent` vs graph `NiagaraGraph_1`),
  and name-based matching is fabrication. The graph↔script link is only
  observable from the graph/node side.

### Fallback Behavior

- Missing property: field omitted, no fabricated default
- Bytecode in native_tail: always `status: "opaque"`, never decoded
- Unknown version: preserve raw bytes in `native_tail`

---

## NiagaraNode* Contract

### Output Schema (all 9 migrated node classes)

```json
{
  "node_class": "<NiagaraNode* class name>",
  "node_name": "<FName string>",
  "tagged_properties": {},
  "parameters": [{ "name": "<string>", "type_definition": {} }],
  "pins": [{ "pin_id": 0, "pin_name": "<FName>", "pin_direction": "Input|Output",
             "linked_to": [0, ...], "source_connection_count": 0 }],
  "native_tail": { "offset": 0, "size": 0, "status": "decoded|opaque" }
}
```

### Field Sources

| Output Field | Source | Evidence |
|-------------|--------|----------|
| `node_class` | Resolved class name | all 9 migrated classes |
| `node_name` | Export `object_name` | e.g. `NiagaraNodeInput_170` |
| `tagged_properties` | Class-specific property map | see handler `_CLASS_PROPERTIES` |
| `pins` | Native tail pin records (B2) | 99 pins across 25 NiagaraNode* exports; 76 LinkedTo edges resolved |
| `native_tail` | OPAQUE_CLASS_PAYLOAD handler | remainder after tagged properties; status `decoded` when pins present, `opaque` otherwise |

### B2 Pin Projection Results

All 25 NiagaraNode* exports now decode pin records from their native tails.
Pin layout is byte-verified against the B0b gate decision document
(`issue-521-b0-gate-decision.md`). Key metrics:

- **Total pins decoded:** 99
- **LinkedTo edges resolved:** 76 (100% of edges in fixture)
- **Pin resolution:** 25/25 node exports (100%)
- **Version-delta compliance:** UE 5.0 fixture; `bSerializeAsSinglePrecisionFloat` absent

Pin fields: `pin_id` (unique per-node integer), `pin_name` (FName string),
`pin_direction` ("Input" or "Output"), `linked_to` (list of target pin IDs),
`source_connection_count` (integer).

### Parameters Projection Results (#525)

Node classes with `FNiagaraVariable` properties project a `parameters` array
containing `{name, type_definition}` records extracted from decoded NiagaraVariable
tagged properties.

| Class | Property | UE source | Extraction |
|---|---|---|---|
| NiagaraNodeInput | `Input` | `NiagaraNodeInput.h:53` | Single struct → wrap in list |
| NiagaraNodeOutput | `Outputs` | `NiagaraNodeOutput.h:19` | Array → iterate elements |
| NiagaraNodeSelect | `OutputVars` | `NiagaraNodeUsageSelector.h:15` (inherited) | Array → iterate elements |
| NiagaraNodeStaticSwitch | `OutputVars` | `NiagaraNodeUsageSelector.h:15` (inherited) | Array → iterate elements |

Remaining classes (FunctionCall, Op, ParameterMapGet, ParameterMapSet, Reroute) have
no `FNiagaraVariable` UPROPERTY members and produce `"parameters": []`.

Output schema per node export:

```json
{
  "parameters": [
    { "name": "<FName string>", "type_definition": { "UnderlyingType": "<FName string>", "Class": <int32>, "Flags": <int32> } }
  ]
}
```

- `type_definition` preserves the raw decoded `FNiagaraTypeDefinition` record
- `Class` is a serialized FPackageIndex (UStruct* reference); resolution to a human-readable name is a future enhancement
- `DataBlob` (typed variable value bytes) is intentionally excluded from the parameters projection

Terminal state: **Achieved** — parameter names and types derived from fixture evidence
with UE source backing.

---

## Execution Flow Disposition (A2)

**Terminal state:** explicitly out of scope of Epic #521.

**Rationale (evidence discipline):** Insufficient evidence today; no assertion is made
about whether Niagara graphs carry an executable control flow. The 2026-08-04 audit
found no fixture-visible exec-pin data, and the project attribution rule forbids
asserting graph semantics — including "pure dataflow" — without a version-fixed UE
source reference. A targeted audit of `EdGraphSchema_Niagara` at checkout commit
`7deeb413d3dc1fc034f48d1aacc0861301829d32` (5.8.0-release) on 2026-08-05 produced no
decisive exec-pin evidence: the schema header declares no exec-pin API (its only
`exec` hit is the cosmetic `FNiagaraConnectionDrawingPolicy::DefaultExecutionWireThickness`
wire-thickness field, `EdGraphSchema_Niagara.h:233`), `EdGraphSchema_Niagara.cpp`
implements no `CreateDefaultNodes`, and the exec-pin references found elsewhere in
NiagaraEditor are compile-time constructs (`FNiagaraCompilationNode::GetInputExecPin` /
`GetOutputExecPin`, `NiagaraGraphDigest.cpp:2027,2040`; `Signature.bRequiresExecPin`,
`NiagaraHlslTranslator.cpp:302`, `NiagaraAttributeTrimmer.cpp:134`) rather than
graph-level execution-order serialization.

**What this means:** Execution flow is neither projected nor inferred by this parser.
`node_exports` order is document order, not execution order.

**Re-open condition:** If version-fixed UE source evidence demonstrates that Niagara
graphs serialize execution-order semantics (e.g. exec pins in `UEdGraphSchema_Niagara`
or traversal-order serialization in `UNiagaraGraph`), open a new issue referencing
this section.

---

## Niagara Coverage Contract (A3)

Every Niagara class present in the fixture lands on an evidence-based terminal
state. Live enumeration is pinned by `tests/temp/test_issue_521_niagara_coverage.py`;
uncovered classes are exactly two and both are settled below.

| Class | Count | Terminal state | parse_status | Evidence |
|---|---|---|---|---|
| NiagaraGraph | 1 | field-level parse | partial_metadata | NiagaraGraphHandler; §NiagaraGraph above |
| NiagaraScript | 1 | field-level parse | partial_metadata | NiagaraScriptHandler; §NiagaraScript above |
| NiagaraNodeFunctionCall / Input / Op / Output / ParameterMapGet / ParameterMapSet / Reroute / Select / StaticSwitch | 25 | field-level parse | partial_metadata | NiagaraNodeHandler; §NiagaraNode* above |
| NiagaraScriptVariable | 11 | field-level parse | partial_metadata | NiagaraScriptVariableHandler; tagged properties verified against `UNiagaraScriptVariable` UPROPERTYs (`NiagaraScriptVariable.h:138-264`, checkout `7deeb413d3dc1fc034f48d1aacc0861301829d32`) and fixture probe |
| NiagaraScriptSource | 1 | evidence-backed skip | skipped | `UNiagaraScriptSource` (`NiagaraScriptSource.h:18-101`) holds compiled script source; bytecode decoding is out of scope (roadmap §Explicitly Out of Scope) |

The inner opaque structs of `NiagaraScriptVariable` (`NiagaraVariableMetaData`,
`NiagaraVariant`) and the `Outputs`/`OutputVars` element structs are owned by
the B1/#515 path and are not decoded here. The following structs are now decoded:

| Struct | parse_status | Commit | Issue |
|--------|--------------|--------|-------|
| `NiagaraVariable` | success | `84825a0e` (BinaryOrNative handler) | #527 |
| `NiagaraGraphScriptUsageInfo` | success | `6e47a4b9` (element PropertyTag fix) | #521 |
| `VersionedNiagaraScriptData` | success | `6e47a4b9` (element PropertyTag fix) | #521 |

---

## Notes

- All three handler families report `parse_status = "partial_metadata"`
  (handler projection over tagged properties); unproven native bytes
  remain explicitly opaque
- `NiagaraVariable`, `NiagaraGraphScriptUsageInfo`, and
  `VersionedNiagaraScriptData` are now decoded (`parse_status: success`);
  remaining inner structs (`NiagaraVariableMetaData`, `NiagaraVariant`,
  `Outputs`/`OutputVars` elements) are still opaque
- Pin projection (B2) is complete: 99 pins decoded from 25 NiagaraNode*
  native tails with 76 LinkedTo edges resolved at 100%
- Native tail bytes for nodes with pins are now `status: "decoded"`;
  nodes without pins remain `status: "opaque"`
- This contract documents the evidence-verified field baseline; fields
  without fixture + UE-source evidence are not projected
