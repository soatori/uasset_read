# Test Samples

This directory contains tracked `.uasset` fixtures for integration tests.

## Sources

### uasset-rs samples

The `uasset_rs_UE410_SimpleRefsSoftRef.uasset` fixture is sourced from
[uasset-rs](https://github.com/jorgenpt/uasset-rs) at commit
`b1d5a7f5b4414ae3e443b882bed3eb51caf21596`.

Licensed under the **MIT** and **Apache-2.0** licenses.
See <https://github.com/jorgenpt/uasset-rs/blob/main/LICENSE-MIT> and
<https://github.com/jorgenpt/uasset-rs/blob/main/LICENSE-APACHE>.

### UnrealBPInspect sample

The `Helm_BP.uasset` fixture (issue #662 UE4 graph carrier) is sourced from
[UnrealBPInspect](https://github.com/MarcedForLife/UnrealBPInspect) at commit
`8436dcadbd53d0a6d64e725805066d4e3f98f29c`, path `samples/ue_4.27/Helm_BP.uasset`.

Licensed under the **Apache-2.0** license.
See <https://github.com/MarcedForLife/UnrealBPInspect/blob/main/LICENSE>.
Provenance and measured structural numbers: `ORIGIN-issue-662-ue4-graph.md`.

### UE 5.3.2 graph fixture (issue #656)

`UE53GraphFixture_BP_GraphFixture.uasset` is a first-party editor save created
for this repository task at the user's direction with UE 5.3.2 (CL 29314046).
It was authored in a Blank Blueprint project with Starter Content disabled and
does not use Marketplace or Epic example assets. It is a partial 1009-band
carrier: EventGraph nodes, pins, and positions are present, but no pins are
connected, so the full graph gap remains missing. Provenance and measured
structure: `ORIGIN-issue-656-ue53-graph.md`.

### MyProject UE 5.8.2 user fixtures (issue #662)

The five `Issue662_*.uasset` fixtures (SkeletalMesh, AnimComposite,
AnimLayerInterface, MaterialFunction, MaterialParameterCollection) are
user-provided first-party content: the user is the author of these
self-created assets, saved with the UE 5.8.2 editor in their own project,
copied from `MyProject Content/ParserFixtures/Issue662/` — no third-party
license applies. Provider verification (engine build 5.8.2.56702186, SHA-256
match to the originals) plus independent re-measurement and the measured
structural numbers: `ORIGIN-issue-662-ue58-user-fixtures.md`.
