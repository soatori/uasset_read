# Issue #656 — UE5.2–5.3 graph carrier (partial)

## Source

- First-party Blueprint fixture authored for this repository task at the user's
  direction; no third-party license or external asset applies.
- Saved with Unreal Engine 5.3.2, changelist `29314046`
  (`++UE5+Release-5.3`); compatible version 5.3.0 changelist `27405482`.
- Created in a new Blank Blueprint project with Starter Content disabled. The
  fixture does not reference Marketplace or Epic example assets.
- Project asset path: `UE53GraphFixture/Content/ParserFixtures/BP_GraphFixture.uasset`.

## Package facts

- File: `UE53GraphFixture_BP_GraphFixture.uasset`
- Size: 22,347 B
- SHA-256: `4708f1e1f3d1ad71d7ce1b5d8685e97818592e7b32a3c1d608ef6e577b0c18c9`
- Legacy package; `FileVersionUE4=522`, `FileVersionUE5=1009`.
- 13 exports, 2 asset-role exports, 16 imports, 105 names.

## Structural verification (measured)

- `BP_GraphFixture` is an Actor Blueprint and compiles successfully in UE 5.3.2.
- EventGraph: 3 `K2Node_Event` nodes, 8 pins, and 0 links. Stored positions are
  `(0,0)`, `(0,208)`, and `(0,416)`.
- `UserConstructionScript`: 1 node and 1 pin.
- Both graphs have no parse errors; decode produced no `BLUEPRINT_*` diagnostics.
- Asset-depth diagnostics: 6 `EXPORT_TRAILING_BYTES_UNCONSUMED` entries with
  reason `editor_only`.

## Acceptance boundary

This is a real UE5.3.2, file-version-1009 node-bearing carrier, not a complete
graph fixture. Its EventGraph has no connected pins, so it does not satisfy the
positive link requirement for UE5.2/5.3 graph acceptance. Keep
`fixture_gaps.ue5_2_5_3_graph.status` as `missing` until a saved revision has a
connected EventGraph edge whose endpoints decode and resolve. If the asset is
updated, remeasure this file's hash, size, positions, links, and diagnostics.
