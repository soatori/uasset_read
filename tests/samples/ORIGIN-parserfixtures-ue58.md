# ParserFixtures UE5.8.2 intake

## Source and provenance

- Source: user-owned `MyProject` Unreal project.
- Engine: Unreal Engine 5.8.2.
- Build profiles: `ParserFixtures 03 IoStore Tagged`, `ParserFixtures 02 Pak Tagged`.
- Content: project-owned ParserFixtures assets; no commercial-game assets.
- Native tools: UE 5.8.2 `UnrealPak.exe`, `read_toc()` from this repository.

## IoStore container set

| File | Size | SHA-256 | Status |
| --- | ---: | --- | --- |
| `ParserFixtures-Windows.utoc` | 103,802 B | `6dfe225641c00b422ccfe952883cc54d7e805d73700610a6d2990c5bb11a0890` | tracked |
| `ParserFixtures-Windows.ucas` | 201,912,080 B | `cb81dbd69aef940ae8a0caf9a6a3d6544ae255a8ac89a062a783da0f9a908818` | local-only; over GitHub limit |
| `ParserFixtures-global.utoc` | 806 B | `33f7d769dc4cb8b0b05f74a014f112e9ee58849417fda6459729d42d186ed92d` | tracked |
| `ParserFixtures-global.ucas` | 3,333,776 B | `c3dc3e25c0b38d0b57adadc396da4c83edaa8078b8ca22a5fdf3fddc7e5e12f5` | tracked |

`read_toc()` measured 623 chunks and 503 package files. The verified
ParserFixtures package list includes `TestBlueprint`, `TestMaterial`,
`TestDataTable`, `T_ParserBulk`, and related packages with chunk type
`ExportBundleData`.

Native `UnrealPak.exe IoStore -FindAndExtract` produced the paired Zen
artifacts under `tests/samples/zen/`:

- `ParserFixtures_TestBlueprint.uheader/.uexp`
- `ParserFixtures_TestMaterial.uheader/.uexp`
- `ParserFixtures_TestDataTable.uheader/.uexp`

These files prove fixture availability only. ZenPackageReader and IoStore
chunk decoding remain deferred.

## Traditional FPak

`ParserFixturesLegacy-Windows.pak` was created from the LooseTagged ParserFixtures
files with native UE 5.8.2 UnrealPak:

- 25 files;
- 5,745,176 B;
- SHA-256 `44a1a134aa515734f3d7cb6f7468e654c238d5c3036e1c24720a8abae1927518`;
- footer contains `5a6f12e1`;
- `UnrealPak -List` confirms the ParserFixtures mount point and 25 files.
