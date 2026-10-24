# Issue #662 — UE4 Graph Fixture Origin

Every number below was read back from the files on disk by the v2 reader.
Nothing here is asserted from the asset's name.

## Source

- **Repository**: <https://github.com/MarcedForLife/UnrealBPInspect> (UnrealBPInspect)
- **Pin commit**: `8436dcadbd53d0a6d64e725805066d4e3f98f29c` (inventory date 2026-06-21).
  The committed file is byte-identical to
  `git show 8436dca:samples/ue_4.27/Helm_BP.uasset` in the pinned clone.
- **Upstream path**: `samples/ue_4.27/Helm_BP.uasset` (upstream filename kept byte-for-byte)
- **Provenance**: solo-author personal-prototype sample per the peer README — not game
  content, not Epic EULA content
- **License**: Apache-2.0 — `LICENSE` present at the pin commit; verdict recorded in
  `docs/reference/external-peer-inventory.md`
- **Coordinator ruling**: accepted as the #662 primary candidate provenance on 2026-10-24
  (revocable); a user-supplied UE4 editor save stays the fallback if it is revoked.
- **Version pin**: both stored engine-version fields read `0.0.0.0`, so the engine version
  comes from the upstream folder label `4.27` plus the structural evidence below, not from
  the package name. What the file itself proves: legacy layout, `LegacyFileVersion -7`,
  `FileVersionUE4 522`, `FileVersionUE5 0`, `PackageFlags 0x40000`, `TotalHeaderSize 141,365`,
  package name `/Game/Helm_BP` (editor save, not cooked).

## Files

| File | Size | SHA-256 | Export class | exports/assets |
| --- | --- | --- | --- | --- |
| `Helm_BP.uasset` | 169,179 B | `78f8f6c81e24d5ec8d252237ba443baabafe4cac0b8637bf484d3ae2d94caad1` | Blueprint | 47 / 2 |

Asset-role exports: `export:0` (`Blueprint`, `Helm_BP`) and `export:1`
(`BlueprintGeneratedClass`, `Helm_BP_C`). 49 imports, 271 names.

## Structural verification (measured)

- 3 `EdGraph` exports; 11 `K2Node` exports over 7 classes: CallFunction 2,
  CommutativeAssociativeBinaryOperator 1, DynamicCast 1, FunctionEntry 2, FunctionResult 1,
  VariableGet 3, VariableSet 1. Node distribution: `EventGraph` 0, `GetSteeringAngle` 6,
  `UserConstructionScript` 5.
- 26 pins decode (15 + 11 + 0 per graph); 8 of the 11 nodes carry a nonzero editor position;
  18 pin-link records (10 + 8), of which 2 target pins outside the package.
- Custom-version table: 8 entries — the "empty custom-version table" reading is not a
  general property, so the gate has to be evaluated per package.

## Pin-name gate (measured)

- Phase-A pre-1010 path ran: with `FileVersionUE5 == 0` the pins array is located by the
  tag-scan tail on every node export, not by a recorded 1010+ script offset.
- PinsStoreFName / FString-to-FName gate: this package stores pin names as FName indices —
  the 4-byte name read yields real pin names for all 26 decoded pins (`self`, `A`, `B`,
  `ReturnValue`, `then`, `execute`, `WinchConstraintInstance`, `WheelConstraint`,
  `ChildActor`, `AsWinch Constraint BP`), which only an index-based read can produce.
- Still open on this fixture: pin 4/5 of `K2Node_VariableSet_0` fails on an FText field
  (`Invalid FText history_type=101 at pos 164326`), three name reads inside that pin region
  land outside the 271-entry name table and are recovered as default names, one 65-byte
  `EdGraphPinType` payload is consumed as opaque, and 13 exports leave editor-only trailing
  bytes. So UE4 node/pin decoding is proven for what this fixture proves; complete UE4 pin
  coverage is not claimed.

## Verification / gate

- `tests/samples/manifest.json` → `samples[]` entry carries SHA-256, size, real export and
  asset counts; `fixture_gaps.ue4_graph_nodes.status` is `available` only while this fixture,
  its CAPABILITIES row and this file all exist.
- `tests/test_samples.py::test_manifest_matches_every_real_sample` fails on a missing file, a
  size change, a hash mismatch, or an ORIGIN doc quoting a hash the manifest does not track.
- `tests/test_samples.py::test_real_sample_proves_claimed_capability` pins the measured
  summary-tier row (`kind` / `blueprint_type` / `name`, `partial`).
- `tests/test_samples.py::test_fixture_gap_statuses_pin_the_capability_boundary` fails if the
  corpus on disk and the status disagree, or if the carrier loses its CAPABILITIES row.

## Related

- Issue: #662 (parent: #657 Phase 1)
- Design: `docs/designs/2026-10-23-issue-662-fixture-acquisition-plan.md`
