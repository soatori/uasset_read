# Issue #656 — UE5.3.2 graph carrier (connected-edge acceptance)

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
- Size: 33,795 B
- SHA-256: `82dd37cbedf0c06063b45b329338997a44c3de80b5e51dcd3a98a040eadc4f77`
- Legacy package; `FileVersionUE4=522`, `FileVersionUE5=1009`.
- 17 exports, 2 asset-role exports, 24 imports, 137 names.

## Structural verification (measured)

- `BP_GraphFixture` is an Actor Blueprint and compiles successfully in UE 5.3.2.
- EventGraph: 3 `K2Node_Event` nodes and 2 `K2Node_CallFunction` nodes, 28 pins,
  and one connected execution edge represented by 2 reciprocal serialized link
  records. Both records resolve by owner and pin GUID. Event positions are
  `(0,0)`, `(0,208)`, and `(0,416)`; call-node positions are `(-240,48)` and
  `(-240,256)`.
- `UserConstructionScript`: 1 node and 1 pin.
- Both graphs have no parse errors; decode produced no `BLUEPRINT_*` diagnostics.
- Asset-depth diagnostics: 8 `EXPORT_TRAILING_BYTES_UNCONSUMED` entries with
  reason `editor_only` (4,281 bytes total).

## Acceptance boundary

This real UE5.3.2, file-version-1009 save satisfies the connected-edge minimum
for the UE5.3.2 band: the Event BeginPlay node connects to a Print String call,
and both serialized link records resolve to decoded pins. The manifest gap is
now `available` for this band. It does not provide a direct UE5.2 save or broad
coverage of other graph node and pin types. The Blueprint's overall semantic
status remains partial because editor-only export tails are still opaque.
