# #521 Niagara Field Contracts

> Generated: 2026-08-02
> Fixture: `tests/samples/NM_BPSystemEvent.uasset`
> SHA-256: `B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF`

## NiagaraGraph Contract

### Output Schema

```json
{
  "graph_name": "<FName string>",
  "node_exports": [{ "export_index": 0, "class": "<string>" }],
  "script_exports": [{ "export_index": 0, "class": "<string>" }],
  "tagged_properties": {},
  "native_tail": { "offset": 0, "size": 0, "status": "opaque" }
}
```

### Actual Properties from Fixture

| Property Name | Type | Description |
|--------------|------|-------------|
| `ChangeId` | unknown | Tracks graph change history |
| `LastBuiltTraversalDataChangeId` | unknown | Last built traversal data version |
| `CachedUsageInfo` | unknown | Cached script usage information |
| `VariableToScriptVariable` | unknown | Variable mapping to script variables |
| `Nodes` | unknown | Graph node references |

### Field Sources

| Output Field | Source | Evidence |
|-------------|--------|----------|
| `graph_name` | Export `object_name` | `NiagaraGraph_1` |
| `node_exports` | Derived from `Nodes` property | References to NiagaraNode* exports |
| `script_exports` | Derived from `Nodes` property | References to NiagaraScript exports |
| `tagged_properties` | All tagged properties | 5 properties parsed |
| `native_tail` | OPAQUE_CLASS_PAYLOAD handler | offset: 0, size: 2293 |

### Fallback Behavior

- Missing property: keep `parse_status = "opaque"`, do not fabricate default
- Invalid object reference: omit from `node_exports`/`script_exports`
- Unknown version: preserve raw bytes in `native_tail`

---

## NiagaraScript Contract

### Output Schema

```json
{
  "script_name": "<FName string>",
  "script_usage": "<string>",
  "target_environment": "<string>",
  "graph_export_ref": { "export_index": 0, "class": "<string>" },
  "tagged_properties": {},
  "native_tail": { "offset": 0, "size": 0, "status": "opaque" }
}
```

### Actual Properties from Fixture

| Property Name | Type | Description |
|--------------|------|-------------|
| `Usage` | unknown | Script usage enum value |
| `ExposedVersion` | unknown | Exposed version information |
| `VersionData` | unknown | Version compatibility data |
| `RapidIterationParameters` | unknown | Rapid iteration parameter set |

### Field Sources

| Output Field | Source | Evidence |
|-------------|--------|----------|
| `script_name` | Export `object_name` | `NM_BPSystemEvent` |
| `script_usage` | `Usage` property | Script usage enum |
| `target_environment` | Derived from `Usage` | Target platform/environment |
| `graph_export_ref` | Export `object_name` | Corresponding NiagaraGraph export |
| `tagged_properties` | All tagged properties | 4 properties parsed |
| `native_tail` | OPAQUE_CLASS_PAYLOAD handler | offset: 0, size: 2393 |

### Fallback Behavior

- Missing property: keep `parse_status = "opaque"`, do not fabricate default
- Bytecode in native_tail: always `status: "opaque"`, never decoded
- Unknown version: preserve raw bytes in `native_tail`

---

## Notes

- Both exports currently have `parse_status = "opaque"` via OPAQUE_CLASS_PAYLOAD routing
- Tagged properties are parsed but full business logic interpretation is deferred
- Native tail bytes contain serialized graph/script data that remains opaque
- This contract documents the field inventory baseline for future opaque-to-success migration
