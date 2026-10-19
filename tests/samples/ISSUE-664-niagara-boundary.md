# Issue #664 — Niagara graph/script payload audit and decodable boundary

status: current (audit + product-boundary decision, 2026-10-18; worktree
`soatori/issue-664-niagara`, baseline `dev-0.6.0 @ cf29b070`).

Location note: design prose normally lives in the nested docs repository
(`docs/designs/`), which is a separate git repository not present in this
worktree and never committed to this repository (`CLAUDE.md`: CI forbids
`^docs/`). This report ships with the implementation on the issue branch so
the reviewer can move it into the docs repository at merge if desired.

Fixture: `tests/samples/NM_BPSystemEvent.uasset`
(Lyra `Content/Effects/NiagaraModules/NM_BPSystemEvent`, UE 5.0-era package —
`FileVersionUE4=522`, `FileVersionUE5=1004`, custom `FNiagaraCustomVersion=70`,
legacy file version `-8`; provenance `tests/samples/ORIGIN-issue-521-niagara.md`).

UE source: local checkout `5.8.1 release`, commit `71fe36aac5a8df5ccd66c763ffc902b29b6a9c43`.
All citations below are `file:line` at that commit, paths relative to the UE
source root. The fixture is 5.0-era; every layout claim is re-anchored against
fixture bytes (§3), and tagged properties are self-describing, so era deltas
in class members do not break decoding (§4).

## 1. Evidence baseline (measured, `depth="decode"`, `mode="normal"`)

Issue text says "40 unavailable graph projections"; the measured value in the
v4 envelope is **39** (39 Niagara-family objects each own one `graph`
projection; `EdGraphNode_Comment`/`MetaData` exports carry no niagara semantic
and request none). All other issue targets reproduce exactly:

| Target | Measured before #664 |
| --- | --- |
| `graph` projections `unavailable` | 39 / 39 |
| `niagara.domain` coverage `partial` | 39 (detail was "kind/name only") |
| `EXPORT_PAYLOAD_SKIPPED` | 25 (exports 5–29: all `NiagaraNode*`) |
| other diagnostics | `EXPORT_TRAILING_BYTES_UNCONSUMED` ×1 (`PackageMetaData`, `editor_only`), `PAYLOAD_TOC_OFFSET_INVALID` ×1 (summary field, out of scope) |

Root cause: `SKIP_CLASS_PREFIXES` in
`src/uasset_read/parsers/properties/tagged.py` blanket-skipped every
`NiagaraNode*` export (property stream **and** native tail seeked whole), and
the decode-depth graph pass was gated to Blueprint-family packages, so no
graph structure ever reached `objects[].semantic` or the projector.

## 2. UE source audit

**No Niagara graph/node class overrides `Serialize`.** `grep -c Serialize`
over `NiagaraGraph.cpp`, `NiagaraNode.cpp`, `NiagaraNodeFunctionCall.cpp`,
`NiagaraNodeSelect.cpp`, `NiagaraNodeReroute.cpp`,
`NiagaraNodeParameterMapSet.cpp`, `NiagaraNodeParameterMapGet.cpp` is `0` for
every file at the pinned commit (plus zero matches for
`UNiagaraNode*::Serialize` / `UNiagaraGraph::Serialize` across
`Engine/Plugins/FX/Niagara/Source`). A node export is therefore:

```
[UE::Serialize: tagged properties ... "None"] [optional object-GUID marker, 4B]
[pin array: int32 count, then per-pin records]
```

- `UNiagaraNode : public UEdGraphNode` —
  `Engine/Plugins/FX/Niagara/Source/NiagaraEditor/Public/NiagaraNode.h:28`.
  Node-specific state is `UPROPERTY` only, i.e. it rides the tagged stream
  (base member `FGuid ChangeId`, `NiagaraNode.h:274`).
- Pin path (shared with Blueprint): `UEdGraphNode::Serialize`
  (`Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphNode.cpp:212`) writes
  the pin block at `:258–261`, inside `#if WITH_EDITOR` (`:232`), gated by
  `FBlueprintsObjectVersion::EdGraphPinOptimized` (enum value 4; fixture
  `FBlueprintsObjectVersion=10` → guard passes) →
  `UEdGraphPin::SerializeAsOwningNode` (`EdGraphPin.cpp:993`) →
  `SerializePinArray` (`EdGraphPin.cpp:2063`, count then per-pin
  `SerializePin` `:2132`) → full pin body `UEdGraphPin::Serialize`
  (`EdGraphPin.cpp:1838`). `LinkedTo` is serialized inside the pin body
  (`EdGraphPin.cpp:1886`) as (owning-node package index, pin GUID) pairs.
  Editor-tail fields are additionally `!Ar.IsFilterEditorOnly()`
  (`EdGraphPin.cpp:1859/:1895`) → **the pin path exists only in editor-saved
  packages; cooked packages carry none of it** (same boundary as `K2Node_`).
- `UNiagaraGraph : public UEdGraph` (`NiagaraGraph.h:235`): no `Serialize`
  override, so its graph state is tagged properties from `UEdGraph`
  (`Nodes` UPROPERTY, `Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraph.h:74–79`)
  plus Niagara's own members.

Related custom `Serialize` implementations elsewhere in the plugin (why the
remaining skip list stays):
`UNiagaraScript::Serialize` (`Niagara/Private/NiagaraScript.cpp:1638`),
`UNiagaraEmitter::Serialize` (`Niagara/Private/NiagaraEmitter.cpp:491`),
`UNiagaraMeshRendererProperties::Serialize`
(`Niagara/Private/NiagaraMeshRendererProperties.cpp:590`), struct-level
`FNiagaraTypeDefinition::Serialize` / `FNiagaraVariableBase::Serialize`
(`Niagara/Private/NiagaraModule.cpp:1569 / :1732`).

## 3. Byte-level verification (lineage + reproduction)

`docs` repo record `issue-521-b0-gate-decision.md` (historical, UE 5.0
fixture vs 5.8 source) byte-walked all 25 `NiagaraNode*` tails: 99 pins,
76/76 links resolved, zero residual bytes, GUID-marker locate
(`property_stream_end + 4`). This implementation reproduces that walk through
the production reader (`read_blueprint_graphs` on the same fixture):

- 1 graph (`NiagaraGraph`, `export:4`), **28 nodes** (25 `NiagaraNode*` +
  3 `EdGraphNode_Comment`), **99 pins**, **76 edges**, `parse_errors == []`,
  0 reader diagnostics, `unresolved_links == 0`, `ambiguous_links == 0`.

## 4. Decodable boundary per high-frequency node kind

Tagged properties are name+type tagged, so the decoder consumes whatever the
package era wrote. Columns: what decodes today (properties in the export
record; pins/links on the owning graph's semantic), and what stays out.

| Node kind | Fixture-decoded tagged fields (evidence) | 5.8 header members (`UPROPERTY`) | Pin tail |
| --- | --- | --- | --- |
| `NiagaraNodeFunctionCall` | `FunctionScript`, `FunctionDisplayName`, `CachedChangeId`, `ChangeId`, `NodePosX/Y`, `NodeGuid` | `SwitchParameter`, `PropagatedName`, `FunctionScript` (:61), `SelectedScriptVersion`, `Signature` (:76), `FunctionSpecifiers` (:79), `DebugState`, `BoundPinNames`, … (`Public/NiagaraNodeFunctionCall.h`) | decoded (shared reader) |
| `NiagaraNodeParameterMapGet` | `PinOutputToPinDefaultPersistentId` (`TMap<FGuid,FGuid>`), `ChangeId`, `NodePosX/Y`, `NodeGuid` | same, `NiagaraNodeParameterMapGet.h:73` | decoded |
| `NiagaraNodeParameterMapSet` | `ChangeId`, `NodePosX/Y`, `NodeGuid` (class declares no members) | no class `UPROPERTY`s (`Private/NiagaraNodeParameterMapSet.h`) | decoded |
| `NiagaraNodeReroute` | `ChangeId`, `NodePosX/Y`, `NodeGuid` (class declares no members) | no class `UPROPERTY`s (`Private/NiagaraNodeReroute.h`) | decoded |
| `NiagaraNodeSelect` | `SelectorPinType`, `SelectorPinGuid`, `OutputVars`, `OutputVarGuids`, `NumOptionsPerVariable`, `ChangeId`, `NodePosX/Y`, `NodeGuid` | `SelectorPinType` (:22), `SelectorPinGuid` (:25) only — the extra fixture fields are 5.0-era and gone by 5.8; the tagged stream still carries their names, so they decode per tag | decoded |
| `NiagaraNodeInput/Op/Output/StaticSwitch` | base fields (`ChangeId`, `NodePosX/Y`, `NodeGuid`) | — | decoded |
| `NiagaraGraph` | `ChangeId`, `LastBuiltTraversalDataChangeId`, `CachedUsageInfo`, `VariableToScriptVariable`, **`Nodes` (28 refs)**, `GraphGuid` | `UEdGraph.Nodes` + Niagara members | n/a (no native tail) |

Pins retained per node: id (GUID), name, direction, pin type
(category/subcategory/object), defaults, links (GUID-resolved), sub/parent pin
links — the shared `UEdGraphPin` model, same shape as Blueprint graphs.

## 5. Product boundary decision

**Promised** (implemented and sample-asserted in this change):

- Editor-saved Niagara packages decode node payloads (tagged properties) and
  the editor graph structure: nodes, pins, links, positions, and summary
  counts, attached to `objects[].semantic["graphs"]` on the owning
  `NiagaraGraph` and projected as one `represented` `graph` record
  (`node_count`/`pin_count`/`edge_count` summary only — capability-matrix
  rule `graph summary only; never a generated source body`).
- Tier stays **summary / `partial`** everywhere (#629): structural graph
  evidence is not Niagara script semantics.

**Not promised** (stays explicitly unavailable with structured diagnostics):

- Niagara script execution semantics, parameter/variable binding resolution,
  compile/traversal contexts — `niagara.domain` coverage remains `partial`
  with an honest detail string.
- `UNiagaraScript` compiled body (custom `Serialize`, `NiagaraScript.cpp:1638`),
  `NiagaraEmitter`, `NiagaraSystem`, `NiagaraMeshRendererProperties` payloads —
  still `EXPORT_PAYLOAD_SKIPPED` (`known_unimplemented`, now with
  `offset` + `size` = stable byte range). Zero remain in the tracked corpus.
- Cooked/stripped packages: pin path is `WITH_EDITOR`; no editor graph there.
- In the property pass, each node's pin tail is residue owned by exactly one
  `EXPORT_TRAILING_BYTES_UNCONSUMED` diagnostic (`known_unimplemented`,
  `offset+size` reaches the export window end); at `depth="decode"` that same
  region is decoded by the graph pass. This mirrors the existing `K2Node_`
  treatment (property pass + separate graph pass).

No claim of full Niagara editor-graph coverage is made anywhere in output,
docs, or README.

## 6. Implementation mapping

| File | Change |
| --- | --- |
| `src/uasset_read/parsers/properties/tagged.py` | `"NiagaraNode"` removed from `SKIP_CLASS_PREFIXES` (comment carries the §2 audit) |
| `src/uasset_read/parsers/legacy_reader.py` | graph pass family gate + owner fallback for package-rooted `NiagaraGraph` (`_NIAGARA_GRAPH_CLASSES`); `EXPORT_PAYLOAD_SKIPPED` gains `offset=window.start` |
| `src/uasset_read/parsers/asset_types/handlers_impl.py` | `NiagaraHandler` attaches decoded `graphs` at `depth="decode"`, adds `niagara.graph` coverage, honest `niagara.domain` detail; tier unchanged (summary) |
| `src/uasset_read/projections/registry.py` | `graph` projection content gains `node_count`/`pin_count`/`edge_count` when the semantic graphs carry them |
| `tests/test_samples.py` | folded #664 assertions (collection budget stays 111): decode-depth graph structure, per-kind fields, projection represented, skip/trailing disposition; #653 fold rewritten for decoded payloads |
| `tests/samples/quality_baseline.json` | regenerated aggregate (`tools/gen_quality_baseline.py`): +25 classified trailing warnings (2928→2953), new `known_unimplemented/NiagaraNode*` buckets |
| `README.md` | Niagara handler line states the decoded surface and the not-decoded script semantics |

## 7. Diagnostics disposition (`NM_BPSystemEvent`, decode depth)

| Code / reason | Before | After |
| --- | --- | --- |
| `EXPORT_PAYLOAD_SKIPPED` / `known_unimplemented` | 25 (no offset, whole window) | **0** |
| `EXPORT_TRAILING_BYTES_UNCONSUMED` / `known_unimplemented` | 0 | 25 (node pin tails; each `offset`+`size` = exact residue, reason stable) |
| `EXPORT_TRAILING_BYTES_UNCONSUMED` / `editor_only` | 1 (`PackageMetaData`) | 1 (unchanged) |
| `EXPORT_TRAILING_BYTES_UNCONSUMED` / `unexpected` | 0 | 0 |
| `PAYLOAD_TOC_OFFSET_INVALID` | 1 | 1 (out of scope, summary field) |
| `graph` projections | 39 `unavailable` | 38 `unavailable` + 1 `represented` |
| `niagara.domain` coverage | 39 `partial` ("kind/name only") | 39 `partial` (decode-honest detail) + 1 `niagara.graph` `present` |

## 8. Verification (worktree gate, 2026-10-18)

- Focused: `test_byte_accounting_registers_reader_consumed_structural_bytes`,
  `test_niagara_fixture_enriched_at_summary_tier` — pass.
- Full suite: `python -m pytest -q` → **111 passed** (collection budget exactly
  111; no test items added — assertions folded into existing sample-backed
  tests).
- `python -m ruff check src tests` → clean; `python -m pyright src/uasset_read`
  → 0 errors; `python -m compileall -q src tests` → clean;
  `git diff --check` → clean.
- `tests/samples/quality_baseline.json` regenerated with
  `tools/gen_quality_baseline.py` (aggregate 2928→2953 classified trailing
  warnings, +23,859 bytes, new `known_unimplemented/NiagaraNode*` buckets);
  `tests/size-baseline.json` `tests_python` 4031→4094 (measured, note
  appended); `src_python` 26444 within the 27309 ceiling.
- Environment note (pre-existing, unrelated to #664):
  `test_iostore_toc_fixture_headers_match_ue_struct_fields` fails in a fresh
  worktree **at pristine baseline** because the local-only fixture
  `tests/samples/containers/MyProject-Windows.ucas` (259 MB, gitignored at
  `.gitignore:119-121`, hash-pinned `committed: false`) is absent from new
  checkouts — proven by re-running it with this change stashed. Restored from
  the main checkout (untracked local fixture; no repository change) and the
  full suite passes.

## 9. Peer corroboration

None. The tracked peer inventory (`docs/reference/external-peer-inventory.md`)
records **no** peer coverage for Niagara graph/node layouts (`grep -i niagara`
= 0 hits), and `external/` is not mounted in this worktree — per the
peer-corroboration scheme this is a zero-coverage statement, not consensus:
UE C++ source plus the real fixture remain the only evidence for these
layouts.

## 10. Out of scope / follow-ups

- `UNiagaraScript` compiled body and `NiagaraSystem`/`NiagaraEmitter`
  payloads (custom `Serialize`) — need their own audits.
- Niagara variable/function signature semantics (`FNiagaraFunctionSignature`,
  `VariableToScriptVariable` binding resolution) — semantic tier work, needs
  fixtures asserting resolution.
- Reclassifying the node pin-tail trailing reason from `known_unimplemented`
  to `editor_only` (K2Node parity) is deliberately deferred: the reason×class
  provenance matrix lives in the docs repository (`docs/designs/2026-10-05-undecoded-classification-rules.md`
  Appendix A) and cannot be updated from this worktree.
