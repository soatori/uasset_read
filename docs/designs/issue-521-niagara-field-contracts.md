# #521 Niagara Field Contracts

> Generated: 2026-08-02; Revised: 2026-08-04 (contract gap audit)
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
  "native_tail": { "offset": 0, "size": 0, "status": "opaque" }
}
```

### Field Sources

| Output Field | Source | Evidence |
|-------------|--------|----------|
| `node_class` | Resolved class name | all 9 migrated classes |
| `node_name` | Export `object_name` | e.g. `NiagaraNodeInput_170` |
| `tagged_properties` | Class-specific property map | see handler `_CLASS_PROPERTIES` |
| `native_tail` | OPAQUE_CLASS_PAYLOAD handler | remainder after tagged properties |

### Deferred Fields: `parameters`, `pin_references`

The Phase 4 plan schema listed `parameters` and `pin_references`. The
2026-08-04 audit confirmed these are NOT derivable from current evidence:
node parameter/pin data lives inside opaque structs (`NiagaraVariable`
with `parse_status: opaque`, `UnknownStruct` arrays such as `Outputs`,
`OutputVars`) and native tails. Deriving them requires opaque struct
parsing (tracked under #515) or UE-source-backed native decoding.
Follow-up issue created; see #521 Epic status.

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

## Notes

- All three handler families report `parse_status = "partial_metadata"`
  (handler projection over tagged properties); unproven native bytes
  remain explicitly opaque
- Native tail bytes contain serialized graph/script data that remains opaque
- This contract documents the evidence-verified field baseline; fields
  without fixture + UE-source evidence are not projected
