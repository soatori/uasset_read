# issue-615/618/619 sample provenance (added 2026-09-01)

Exact copies of the source files below. All four are uncooked editor-state
legacy packages; they unblock fixture evidence for #615 (StringTable),
#618 (BlendSpace), and #619 (PhysicsAsset / PhysicalMaterial). No semantic
capability is claimed by this addition.

## ALSCommunity_Mannequin_PhysicsAsset.uasset

- Source project: ALS Community version (dyanikoglu/ALS-Community), file
  `Content/AdvancedLocomotionV4/CharacterAssets/MannequinSkeleton/PhysicsAssets/Mannequin_PhysicsAsset.uasset`.
- License: MIT (project LICENSE, © 2020 Doğa Can Yanıkoğlu & LongmireLocomotion).
  The referenced Mannequin skeleton itself remains tracked separately as
  `ALS_Mannequin_Skeleton.uasset`.
- Size: 133,851 bytes. SHA-256:
  `84da89566a4d8086c0e976f0073bee2e27b053f5bb050c7d0fae14cf560cb14e`

## FirstPerson_BS_Idle_Walk_Run.uasset

- Source project: Unreal Engine First Person sample, file
  `Content/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run.uasset`.
  Same provenance class as the existing `FirstPerson_*` fixtures
  (see ORIGIN-issue-522-cube-builder.md).
- Size: 52,333 bytes. SHA-256:
  `bc71af8768b569695d4bcb69c79867f998e085693f5e8230854d228de359f5bb`

## IntroToUnreal_StrT_Titles.uasset

- Source project: Intro To Unreal course sample project, file
  `Content/DemoTemplate/_Core/DevCom/StrT_Titles.uasset`.
  Same provenance class as the existing `IntroToUnreal_*` fixtures.
- Size: 3,649 bytes. SHA-256:
  `8cf4e70d63eddbda69d1910af6a9726cd2bb8cf3da5a28d833b6f8cbc00810c7`

## Lyra_PM_Concrete.uasset

- Source project: Lyra Starter Game, file
  `Content/PhysicsMaterials/PM_Concrete.uasset`.
  Same provenance class as the existing `Lyra_*` fixtures.
- Size: 1,302 bytes. SHA-256:
  `b863b78d876ec3077c2f4915829d53711fe47cce55158f2c029bd9559f3c5d67`

## Main-export class verification

Each file was parsed with `parse_package_document(depth="object")`; the
single/multi `bIsAsset` main export classes are `PhysicsAsset`, `BlendSpace`,
`StringTable`, and `PhysicalMaterial` respectively, matching the manifest
`asset_type_hint` values.
