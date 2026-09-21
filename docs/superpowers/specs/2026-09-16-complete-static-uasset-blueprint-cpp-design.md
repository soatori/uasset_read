# Complete Static UAsset Parsing and Blueprint C++ Projection

status: target

> **2026-09-21 implementation marker:** This specification remains a target. On
> the checked-out `dev-0.6.0` branch, the v3 envelope and Tasks 1–4 foundations
> exist (`src/uasset_read/projection.py:17,220-223`,
> `src/uasset_read/sources.py:11`, `src/uasset_read/layout.py:148`, and
> `src/uasset_read/models/byte_ranges.py:129`), but the complete static
> Blueprint IR/CFG/correlation, Material graph, C++/type-aware projection, and
> canonical writer are not current behavior. The corresponding Task 5–9
> implementation is only on the unmerged `compose/static-uasset-task5-12`
> branch; Tasks 10–12 have no current implementation. Do not read this target
> specification as an implementation claim.

## Decision

Adopt an in-place, modular rewrite of the parser core. Keep `PackageDocument` as the only package-level document boundary, but replace the current monolithic read/enrich path with independent source, container, layout, property, object, Blueprint, Kismet, Material, analysis, and projection modules.

The implementation is pure Python 3.10+ and has no runtime bridge to CUE4Parse, UAssetAPI, UAssetGUI, UnrealBPInspect, FModel, or Unreal Editor. Those projects remain external comparison evidence only.

Backward compatibility is not a requirement for the refactored output. The package document moves to the new major format version `format_version: "3.0"` (an envelope field, not state on `PackageDocument`) while retaining the package-first model and explicit capability states. One input package has one canonical serialized output document; type-specific projections are embedded in that document as `projections[]` records with explicit status/completeness and provenance, physical `sidecars[]` are created only when a payload or size boundary makes a single physical file unsafe, and the committed contract is `docs/designs/contract/package_document_v3.schema.json`.

## Goal

Parse Unreal assets and packages as completely as the bytes and available metadata allow, and expose enough static Blueprint semantics to generate useful equivalent C++ declarations and migration-oriented C++ function bodies.

“Complete” means every requested region is either decoded, preserved as an opaque/payload region, or reported as unavailable with a reason. It does not mean executing Blueprint/gameplay code or reconstructing information removed by cooking, encryption, or missing native implementation bodies.

## Evidence and Blueprint Header View

Epic’s Blueprint Header View is an editor plugin that produces C++-style declarations for Blueprint variables, functions, Actor Components, and Event Dispatchers. Epic’s documentation explicitly states that the generated header contains declarations and that function implementations still need to be converted manually. It is therefore a useful declaration-format and semantic-scope reference, but not a complete Blueprint decompiler.

References:

- [Blueprint Header View overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/an-overview-of-the-blueprint-header-view-in-unreal-engine)
- [Blueprint vs C++](https://dev.epicgames.com/documentation/en-us/unreal-engine/coding-in-unreal-engine-blueprint-vs-cplusplus)
- [Blueprint Header View API](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/PluginIndex/BlueprintHeaderView)

The project will reproduce the useful declaration output and extend it with a separate static implementation projection based on Blueprint graphs and Kismet bytecode. It will not claim to reproduce Unreal’s private editor implementation.

## Scope

### Included

- Loose `.uasset` and `.umap` packages.
- `.uexp`, `.ubulk`, and `.uptnl` sidecars.
- Traditional Pak entries only when a validated FPak fixture is available; an IoStore wrapper with a `.pak` suffix is classified truthfully and is not treated as FPak evidence.
- IoStore/Zen package sources when the required index, chunk, compression, and key information is available.
- Legacy and Zen packages through separate binary readers.
- Tagged and unversioned properties through separate readers.
- All imports, exports, package tables, dependencies, object roles, offsets, and serialized regions.
- Blueprint graph nodes, pins, links, graph kinds, entrypoints, variables, components, and dispatchers.
- Kismet expressions and normalized bytecode instructions.
- Static basic-block/control-flow, call-target, and variable read/write analysis.
- Material expression nodes, pins, links, parameters, and material function references when editor data exists.
- One JSON/package document per input package, containing structured data plus C++ header/source and table projections from the same `PackageDocument`.

### Explicitly excluded

- `.uasset` writing or binary reconstruction.
- Runtime execution of Blueprint or game code.
- Native C++ function body recovery.
- Inventing editor graph data that cooking removed.
- Decrypting assets without a supplied key.
- Treating unknown compression or serialization variants as successfully decoded.
- Runtime dependency on another parser project or Unreal Editor.

## Architecture

```text
ByteSource / ContainerSource
        ↓
PackageLayoutDetector
        ↓
LegacyPackageReader | ZenPackageReader
        ↓
PackageTables + VersionContext
        ↓
TaggedPropertyReader | UnversionedPropertyReader
        ↓
ObjectRecord + OpaqueRegion + PayloadRef
        ↓
Blueprint / Kismet / Material domain decoders
        ↓
Static analysis IR
        ↓
PackageDocument
        ↓
JSON / CLI / Python / Agent / C++ projections
```

### Source and container layer

All binary readers consume a bounded random-access interface:

```python
class ByteSource(Protocol):
    def read_at(self, offset: int, size: int) -> bytes: ...
    def size(self) -> int | None: ...
    def describe(self) -> str: ...
```

The layer owns file composition, Pak lookup, IoStore chunk lookup, decompression, encryption status, and source diagnostics. It does not parse UObject properties or domain semantics.

### Package and object layer

`PackageDocument` remains the only public aggregate. Every export has a stable address such as `export:17`; `bIsAsset` adds a role and never filters other exports. `PackageTables`, `VersionContext`, `ObjectRecord`, relations, opaque regions, payload references, and diagnostics are independent models.

`LegacyPackageReader` and `ZenPackageReader` produce the same package/object model but never share format-specific offset assumptions. Package layout detection selects a reader based on validated bytes and source metadata, not only a UE major version or filename.

### Property layer

Tagged and unversioned readers share normalized value types but have separate parsing state machines. A `SchemaProvider` supplies unversioned field layouts. `NativeTailReader` and `OpaqueRegion` preserve bytes that are outside the tagged property stream or not yet understood. Every reader records start offset, end offset, consumed size, and failure reason.

### Blueprint graph model

The graph IR uses package/object identity in addition to Node GUID:

```text
BlueprintGraph
  graph_id
  graph_kind
  nodes[]
  pins[]
  links[]
  entrypoints[]
```

Pin resolution is owner-aware. Duplicate GUIDs and unresolved owners remain explicit diagnostics rather than being silently merged.

### Kismet instruction and control-flow model

The existing expression tree remains an input/compatibility projection, but the canonical internal model becomes:

```text
BytecodeInstruction
  statement_index
  logical_end
  serialized_start
  serialized_end
  opcode
  operands
  expression
  reads[]
  writes[]
  call_target
  jump_target_statement_index
  source_node_id

BasicBlock
  start_offset
  end_offset
  instructions[]

ControlFlowEdge
  source_block
  target_block
  kind: fallthrough | true | false | jump | loop_back | computed_jump | return
```

`exec_chains` becomes a derived summary from this model. It must not be described as runtime execution order.

`StatementIndex` and serialized file offsets are different coordinate systems. CFG construction and jump resolution use logical statement indexes; diagnostics and byte provenance use serialized ranges. One canonical instruction represents one top-level script statement. Nested Kismet expressions remain operand trees and are not flattened into additional CFG instructions.

### Static Blueprint analysis

The analyzer combines graph and bytecode information using Export/Object IDs, function identity, source-node metadata, and only then GUID-based evidence. It produces:

- event and function entrypoints;
- branch and loop paths;
- static call graph;
- variable read/write sets;
- unresolved calls and nodes;
- confidence and diagnostics for every correlation.

The analyzer does not evaluate game state or call Unreal functions.

### Material graph model

Material semantics include material properties, expression nodes, input/output pins, links, scalar/vector/texture parameters, material function calls, and editor/runtime capability markers. A cooked asset with no editor expression graph is explicitly `limited` or `unavailable` for that feature.

## C++ Projection

The C++ layer is a projection from the canonical semantic IR, never a second parser.

The projection modules live outside the parser package. Declaration correctness is checked against a committed normalized oracle for a user-owned Blueprint fixture; rendering tests must compare parent class, property types, function signatures, components, and dispatchers, not merely search for `UCLASS`/`UPROPERTY` tokens.

### Declaration mode

Produces C++-style header content containing:

- Blueprint parent class;
- `UPROPERTY`-style variables and types;
- `UFUNCTION`-style functions and signatures;
- components and construction declarations;
- event dispatchers;
- visibility and metadata where recoverable.

This is the project’s equivalent of Blueprint Header View.

### Migration mode

Produces C++ header/source content embedded in the canonical package document. Known control-flow, assignments, branches, loops, literals, pure operators, and resolvable function calls are rendered as C++ AST nodes. Unsupported or ambiguous operations are rendered as valid diagnostic-bearing migration statements and recorded in the projection diagnostics; no unknown symbol or behavior is fabricated.

The generator must distinguish:

- `translated`: semantics mapped to a known C++ construct;
- `represented`: preserved as a call/reference or explicit migration hook;
- `untranslated`: source information exists but no safe C++ mapping is known;
- `unavailable`: source bytes or editor data are absent.

Generated C++ is therefore an auditable migration artifact, not a promise of binary/runtime equivalence.

## Single-file output contract

The canonical output boundary is one serialized document for each input `.uasset` or `.umap` package. Package envelope data, every addressable object, semantic IR projections, type-aware projections, capability states, diagnostics, and payload references are represented in that document.

The document stores C++ header/source text, CSV-compatible table text, and structured JSON data as embedded projection records. These records are derived from the same `PackageDocument`; no projection reparses bytes or becomes a second source of truth. The first implementation does not expose a user-selected output split mode.

Automatic physical splitting is permitted only when required by a hard safety boundary, such as an oversized output or a large raw/compressed/bulk payload that cannot be safely represented in the text document. The main document remains authoritative and records each sidecar's relative path, size, hash, source range, and reason. Assets are not split merely because they have multiple graphs, functions, exports, or type-specific projections.

## Capability and error contract

The parser must never label a document complete merely because the package header opened. At package, object, domain, graph, function, and generated-code levels, report:

- status: `complete`, `partial`, `opaque`, `unavailable`, or `failed`;
- feature name;
- source range when known;
- diagnostic reason;
- recoverability;
- payload reference when raw bytes can be extracted.

Unknown bytes must be measurable. Trailing bytes, unsupported control bits, missing sidecars, missing IoStore chunks, encryption, and stripped cooked data are first-class outcomes.

Byte accounting is scoped. Every requested non-empty export window has a non-empty set of leaf regions that exactly tiles the window without gaps or overlaps. An empty region collection can never satisfy completeness. Each non-decoded leaf carries a reason and, when recoverable, a payload reference.

## Migration constraints

- Pure Python 3.10+ and standard library unless a documented optional capability is strictly required.
- No subprocess or FFI bridge to the reference projects.
- No source edits until the implementation plan is approved for execution.
- Tests must be added before implementation for each new parser boundary.
- Temporary probes and generated samples remain under `temp/`.
- Existing unrelated dirty files, including `docs/plans/2026-09-16-als-name-index-and-optin-docs.md` and `reference/`, must not be modified or staged.

## Acceptance gates

1. StackOBot Blueprint exposes all 31 exports, two graphs, three Kismet functions, 85 expressions, CFG blocks/edges, call targets, and variable reads/writes.
2. UE5.8 Blueprint exposes `K2Node_IfThenElse`, `EX_JumpIfNot`, and explicit true/false control-flow edges.
3. StackOBot Material exposes 42 exports, 39 material expressions, expression properties, and links where the package contains them.
4. Unversioned samples either decode through schema or expose bounded opaque fields; no field is guessed from position alone.
5. Loose sidecars and committed IoStore fixtures prove metadata/classification and available chunk reads; extraction/reparse is required only where committed bytes and codecs exist. Traditional Pak and real Zen-package parsing remain explicitly unverified until redistributable fixtures are added.
6. Generated declaration AST matches the normalized UE5.8 oracle for parent, variables/types, function signatures, components, and dispatchers; migration output contains a dual-offset traceable mapping for every top-level function instruction.
7. Every requested non-empty export range is exactly tiled by decoded, opaque, payload-addressable, or unavailable leaves with reasons where required.
8. Each sampled input package produces one canonical output document containing its package, object, semantic, projection, capability, and diagnostic data; no ordinary asset-family or graph boundary causes a split.
9. The complete test suite, structural baseline, size baseline, and sample quality gates pass.
