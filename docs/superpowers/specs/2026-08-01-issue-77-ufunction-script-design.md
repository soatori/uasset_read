# Issue #77 UE5 UFunction Script parsing design

## Context

Issue #77 tracks the inability to recover verifiable Blueprint function
implementations from real UE5 assets. The current pipeline can enumerate
functions and graph nodes, but it does not successfully read Kismet Script from
the owning `Function` export. Automatic BPGC ordinal mapping, serial scanning,
and graph-topology enrichment can then make output look more complete than the
underlying bytecode result.

The verified UE 5.8 serialization path is:

1. `UObject` serializes tagged script properties and records their export-local
   start and end offsets.
2. `UStruct::Serialize` serializes `SuperStruct`, legacy or array-form
   `Children`, and version-gated `FField` properties.
3. `FStructScriptLoader` reads `BytecodeBufferSize` and
   `SerializedScriptSize`, then deserializes expressions from the current
   position.
4. `UFunction::Serialize` calls `Super::Serialize` before its own flags and
   replication metadata.

Therefore, `ScriptSerializationStartOffset` and
`ScriptSerializationEndOffset` delimit tagged properties; neither is a Kismet
bytecode address. Each `UFunction` owns its own Script. UE 5.8 does not serialize
a BPGC-level table containing a function count, a size array, and concatenated
per-function bytecode.

## Goal

For UE 5.0 through UE 5.8 64-bit assets, recover each Blueprint function's
serialized Kismet expressions from its own `Function/UFunction` export, build
correct statement and jump addresses, translate the resulting AST into code,
and expose failures without substituting heuristic data.

## Non-goals

- Reconstructing Blueprint visual layout.
- Improving serial-scan heuristics until they resemble a native parser.
- Treating graph topology as proof that Kismet bytecode parsed successfully.
- Supporting UE4 or 32-bit Script memory layouts in this issue.
- Expanding Material, Texture2D, or unrelated asset-type parsers.
- Completing every possible `EExprToken` before the real acceptance matrix
  identifies that token as reachable.

## Chosen approach

Add a dedicated native `UFunction` reader and a dual-cursor Kismet archive.
Keep the existing AST and code-generation layers, correcting individual token
transfers only where engine serialization and real assets demonstrate a gap.

This is preferred over patching more offsets into `bytecode_extractor.py`,
because native `UStruct` navigation, Kismet expression transfer, and fallback
policy are separate responsibilities. It is also preferred over a wholesale
rewrite of all CoreUObject serializers, because Issue #77 only needs the
serialization prefix required to reach and interpret `UFunction::Script`.

## Architecture

### Native function reader

Create `src/uasset_read/kismet/ufunction_reader.py`. Its public entry point is:

```python
def read_ufunction_script(
    archive: FArchive,
    export: ObjectExport,
    summary: PackageFileSummary,
    name_map: list[str],
    import_map: list[ObjectImport],
    export_map: list[ObjectExport],
) -> FunctionScriptReadResult:
    ...
```

The function accepts only exports whose resolved class is `Function` or
`UFunction`. It copies exactly the export's serial range into a `ByteArchive`,
so every relative read is bounded by `serial_size` and diagnostics can report
both export-local and package-absolute offsets.

The reader always begins at `serial_offset` and consumes the applicable
serialization-control prefix and tagged-property stream through its `None`
terminator. `script_serialization_start_offset` and
`script_serialization_end_offset` are diagnostic cross-checks only: when they
are present, the measured tagged-property range must match them, but they are
never used as the payload seek origin. This preserves the repository-wide
`SerialOffset/SerialSize` payload rule while still detecting a corrupt export
map. The reader never searches the remaining bytes for a plausible Script
header.

From the native start, the reader mirrors the relevant `UStruct::Serialize`
order:

1. `SuperStruct` package index.
2. `Children`, using the `FFrameworkObjectVersion::RemoveUField_Next` gate.
3. `SerializeProperties`, using the `FCoreObjectVersion::FProperties` gate.
4. `BytecodeBufferSize` and `SerializedScriptSize`.
5. Exactly `SerializedScriptSize` bytes of serialized expressions.

Version decisions come from `PackageFileSummary.file_version_ue4`,
`file_version_ue5`, `file_version_licensee`, and exact custom-version GUID
values. Package summaries currently retain each `FGuid` as four serialized
little-endian `uint32` words, so Kismet version lookup uses the corresponding
serialized keys rather than comparing those bytes directly with canonical UE
GUID text. A missing custom version has the UE loading value `-1`; it is not
silently treated as version `0`. `saved_by_engine_version.minor` is diagnostic
context, not a substitute for a custom-version gate.

The native reader requires the UE Script VM serialization floor
`file_version_ue4 >= 399` (`VER_UE4_CASE_PRESERVING_FNAME`) and
`file_version_licensee >= 0`. Older layouts fail with
`unsupported_serialization_version` rather than entering a partially compatible
decoder.

### Native field reader

Create `src/uasset_read/kismet/native_fields.py` for the `FField` and
`FProperty` records that precede Script. It owns no bytecode behavior. It
returns structured property declarations used both to advance the archive and
to improve function signatures and property-pointer resolution.

Create `src/uasset_read/kismet/value_types.py` with the shared lossless
`FNameRef` (`NameIndex`, `Number`, and resolved base name) before native-field
parsing. The later dual-cursor archive reuses this model rather than declaring
a second incompatible name type.

Each declaration retains raw package indices for binary diagnostics and an
aligned list of optional names resolved through the import/export maps. Index
zero remains a legitimate null where UE permits it; nonzero invalid indices
fail rather than becoming guessed names. C++ type mapping
uses these resolved names (including object class, struct, enum, signature
function, and container inner types); it never invents a concrete type from an
unresolved integer. A `ByteProperty` whose Enum reference is null maps to
`uint8`, matching the legal non-enum serializer path.

The initial source-backed property families are:

- scalar numeric and boolean properties;
- name, string, and text properties;
- object, class, interface, weak, lazy, soft-object, and soft-class properties;
- struct and enum properties;
- array, set, map, and optional properties;
- delegate, multicast delegate, and field-path properties.

The shared `FField` prefix also mirrors package flags: filtered-editor-only
packages omit `FlagsPrivate`, and uncooked editor packages may carry the
metadata-present boolean plus `TMap<FName, FString>`. Each property class
mirrors its UE serializer, including recursively serialized inner fields for
array, set, map, enum, and optional properties. Unknown property classes return
`unsupported_native_field` with the type name and exact offsets. They are not
skipped by guessing a length. If the real acceptance matrix reaches another
property class, support requires its UE source layout and a focused unit test
before that asset can pass.

The `FProperty` base reads the replication condition only when
`FReleaseObjectVersion::PropertiesSerializeRepCondition >= 21`; packages below
that gate retain an absent condition rather than consuming a byte.

### Dual-cursor Kismet archive

Refactor `src/uasset_read/kismet/archive.py` so expression parsing tracks two
positions:

- `serialized_offset`: bytes consumed from the serialized Script payload;
- `bytecode_index`: address in the reconstructed in-memory Script buffer.

`StatementIndex` always records `bytecode_index`. Jump and execution-flow
operands are compared against these logical statement addresses.

The archive exposes explicit transfer methods corresponding to UE script
serialization operations, including:

```python
xfer_token()
xfer_fname()
xfer_object_pointer()
xfer_field_pointer()
xfer_code_skip()
xfer_ansi_string()
xfer_unicode_string()
```

Each method advances the serialized cursor by the disk representation and the
logical cursor by the reconstructed Script representation. UE5 pointer-sized
logical operands use eight bytes for the supported 64-bit target. FName keeps
both `NameIndex` and `Number`. FField pointers deserialize through the
version-gated `FFieldPath` representation instead of an extra invented boolean.

Nested expression terminators are consumed by the recursive parser but omitted
from their parent's child list. For example, `EX_EndFunctionParms` advances
both cursors and closes a call expression; it is not emitted later as a
top-level statement. ANSI and UTF-16 transfer methods likewise consume their
terminators themselves.

Version-gated literal widths are part of the same transfer contract. In
particular, `EX_VectorConst`, `EX_RotationConst`, and `EX_TransformConst` use
the UE5 large-world-coordinate double layout when
`file_version_ue5 >= UE5_LARGE_WORLD_COORDINATES` (`1004`);
`EX_Vector3fConst` remains float-based.

Expression parsing succeeds only when all three conditions hold:

```text
serialized_offset == SerializedScriptSize
bytecode_index == BytecodeBufferSize
last expression token == EX_EndOfScript
```

An unknown token fails at its exact serialized and logical offsets. Tolerant
mode may convert this exception into a structured function failure, but it must
not skip one byte because the unknown token's operand length is not known.
Private placeholder opcodes without a source-backed operand layout and
`EX_Max` therefore cannot masquerade as successful expressions or an end of
script.

### Extraction and pipeline integration

`src/uasset_read/kismet/bytecode_extractor.py` becomes a small orchestration
layer around `read_ufunction_script()` and expression parsing. The production
path has one bytecode source: `function_export`.

Remove automatic BPGC extraction, ordinal function mapping, cache state, and
retry logic. Remove `bpgc_bytecode.py` from public Kismet exports. Move serial
scanning to `src/uasset_read/kismet/diagnostics.py` behind an explicit API:

```python
def scan_function_export_for_diagnostics(...) -> list[BytecodeCandidateDiagnostic]:
    ...
```

Diagnostic candidates cannot construct `KismetDecompiledResult` and cannot be
consumed by the normal parse, IR, or renderer paths.

`kismet/pipeline.py` and `pipeline/post_process.py` filter true
`Function/UFunction` exports instead of all values in the current broad
`USTRUCT_TYPES` set. `K2Node_FunctionEntry` and `K2Node_FunctionResult` remain
graph nodes and never become decompiled functions.

## Result and status model

Native extraction returns:

```python
@dataclass
class FunctionScriptReadResult:
    status: Literal["extracted", "no_script", "failed"]
    serialized_script: bytes = b""
    bytecode_buffer_size: int = 0
    serialized_script_size: int = 0
    serialized_start: int | None = None
    native_fields: list[NativeFieldDeclaration] = field(default_factory=list)
    failure: FunctionScriptFailure | None = None
```

`FunctionScriptFailure` carries the stable code/message, function identity,
package/export offsets, optional logical bytecode index, declared sizes, and
remaining serialized bytes described below. The pipeline projects that failure
into the public error fields without discarding the native reader's context.

`KismetDecompiledResult` retains `bytecode_status` and adds an independent
`translation_status`:

```text
bytecode_status: parsed | no_script | failed
translation_status: complete | partial | failed | not_applicable
```

The combinations have these meanings:

- `parsed + complete`: Script and AST are complete and all AST nodes used by
  the function translated successfully.
- `parsed + partial`: Script and AST are complete, but code generation contains
  an explicitly unsupported construct.
- `failed + not_applicable`: Script extraction or expression parsing failed, so
  bytecode translation was not attempted.
- `no_script + not_applicable`: the native Script header proves that the
  function has no serialized Script.

Graph-topology enrichment may continue producing inferred `cpp_code` for
compatibility, but it must retain `logic_source=graph_topology` and cannot
change either status. Bytecode-derived code uses
`logic_source=current_asset` and `bytecode_source=function_export`.

IR, JSON, Markdown, and the JSON schema expose the same status values. A package
is not fully successful when any true Function result is `failed`, or when any
parsed function has `translation_status=partial/failed`. `no_script` is neutral
and does not reduce package status. This rule is applied by the shared
result-status computation, not only by an individual renderer.

The same projections expose `script_metrics` with
`bytecode_buffer_size`, `serialized_script_size`,
`serialized_bytes_consumed`, and `bytecode_bytes_consumed`. These values make
the two closure invariants independently auditable in real-sample output.

## Error handling

Every native or expression failure contains:

- function export name and export index;
- resolved class name;
- package-absolute and export-relative serialized offsets;
- logical `bytecode_index` when expression parsing has begun;
- stable error code;
- the relevant declared and remaining sizes.

Required error codes include:

```text
invalid_script_property_range
unsupported_serialization_version
unsupported_native_field
invalid_script_size
truncated_script
unknown_expr_token
serialized_size_mismatch
bytecode_size_mismatch
missing_end_of_script
invalid_jump_target
```

Errors are preserved in function results and aggregated into package status.
No failure path silently returns an empty function body as success.

## Module changes

Create:

- `src/uasset_read/kismet/ufunction_reader.py`
- `src/uasset_read/kismet/value_types.py`
- `src/uasset_read/kismet/native_fields.py`
- `src/uasset_read/kismet/diagnostics.py`

Modify:

- `src/uasset_read/kismet/archive.py`
- `src/uasset_read/kismet/property_pointer.py`
- `src/uasset_read/kismet/expressions/assignments.py`
- `src/uasset_read/kismet/expressions/casts.py`
- `src/uasset_read/kismet/expressions/containers.py`
- `src/uasset_read/kismet/expressions/context.py`
- `src/uasset_read/kismet/expressions/control_flow.py`
- `src/uasset_read/kismet/expressions/delegates.py`
- `src/uasset_read/kismet/expressions/functions.py`
- `src/uasset_read/kismet/expressions/literals.py`
- `src/uasset_read/kismet/expressions/rtfm.py`
- `src/uasset_read/kismet/expressions/special.py`
- `src/uasset_read/kismet/expressions/string_consts.py`
- `src/uasset_read/kismet/expressions/structs.py`
- `src/uasset_read/kismet/expressions/variables.py`
- `src/uasset_read/kismet/expressions/vector_consts.py`
- `src/uasset_read/kismet/bytecode_extractor.py`
- `src/uasset_read/kismet/pipeline.py`
- `src/uasset_read/kismet/result.py`
- `src/uasset_read/kismet/semantic.py`
- `src/uasset_read/kismet/__init__.py`
- `src/uasset_read/pipeline/post_process.py`
- `src/uasset_read/ir_builder.py`
- `src/uasset_read/models/ir.py`
- `src/uasset_read/models/status.py`
- `src/uasset_read/renderers/json_renderer.py`
- `src/uasset_read/renderers/markdown_renderer.py`
- `schemas/package.schema.json`

Remove:

- `src/uasset_read/kismet/bpgc_bytecode.py`
- tests whose expected behavior treats the invented BPGC function table as an
  engine serialization contract.

## Test design

### Native serialization unit tests

Synthetic bounded export payloads cover:

- valid modern script-property start/end offsets;
- fallback tagged-property navigation for versions without offsets;
- offset cross-check failure without seeking from a script-property offset;
- legacy and array-form Children;
- zero and nonzero native FProperty declarations;
- cooked/uncooked FField metadata and filtered-editor-only flags;
- `0/0` no-Script headers;
- negative, oversized, and truncated Script sizes;
- exact custom-version branches;
- structured failure for an unsupported native field.

### Dual-cursor expression tests

Focused serialized expression fixtures cover:

- FName index and nonzero number;
- UObject and FField pointer representations whose serialized and logical
  widths differ;
- owner-present and owner-absent FFieldPath versions;
- `EX_VirtualFunction` and `EX_LocalVirtualFunction` parameter lists;
- consumption of nested terminators without top-level leakage;
- `EX_Jump`, `EX_JumpIfNot`, skip, push-flow, and pop-flow addresses;
- pre-LWC float and UE5 LWC double vector/rotation/transform constants;
- simultaneous physical-size, logical-size, and end-token validation;
- strict failure for unknown tokens in both strict and tolerant entry points.

### Pipeline and output tests

Tests assert that:

- only true Function exports produce `decompiled_functions`;
- production results never report BPGC or serial scan as bytecode sources;
- graph topology cannot upgrade a failed bytecode or translation status;
- function failure lowers package status to at least `partial`;
- `no_script` remains neutral;
- internal result, IR, JSON, Markdown, and schema values agree.

### Real asset matrix

The closeout matrix is:

| UE | Sample | Primary acceptance |
|---|---|---|
| 5.0 | Lyra `GA_Hero_Jump` (7 Function exports) | Function classification, Script bounds, end token |
| 5.2 | Cropout `BP_Villager` (30 Function exports) | Large function set, native fields, control flow |
| 5.6 | FirstPerson `BP_FirstPersonCharacter` (12 Function exports) | `Aim` and `Move` calls, parameter binding, jumps |
| 5.6 | StackOBot `BP_MovingPlatform` (8 Function exports) | EventGraph/Ubergraph control flow |
| 5.7 | GameAnimationSample `BFL_HelpfulFunctions` (10 Function exports) | Function-library and pure-function calls |
| 5.8 | FirstPerson `BP_ShooterCharacter` (9 Function exports) | FName/FFieldPath gates and removal of garbage fallback |

For every sample:

- every true Function export has exactly one native status;
- `function_export` is the only production bytecode source;
- every parsed function closes both cursors exactly and ends with
  `EX_EndOfScript`;
- every control-flow target resolves to a logical statement address;
- no K2Node pseudo-functions are emitted;
- failed functions never imply verified code;
- output contains no `Property_-7`, `Property_23265280`, unexplained
  `Unknown_*`, or wrapper calls into a failed Ubergraph.

Stream closure is necessary but is not a semantic oracle. Before Kismet
post-processing, the acceptance test independently derives a normalized
node-graph fingerprint for every user-authored function graph: callable member
references, variable reads/writes, literal/default-pin values, branch and
return structure, and reachable execution/data edges. It derives a second
fingerprint from the native Script AST/CFG and requires the graph semantics to
be represented by the Script result. The oracle helper cannot consume
`cpp_code`, semantic-enrichment output, or translator internals. Every
user-authored function graph maps to exactly one Function result; generated
functions without a source graph are counted separately and remain subject to
the structural Script invariants.

For named semantic assertions, `Aim` and `Move` must additionally preserve
their exact graph-known calls, yaw/pitch or movement parameter bindings,
pure-input sources, and serialized default values.

External sample tests remain opt-in for ordinary contributors. Closing Issue
#77 requires an explicit run of the complete matrix under
`E:\Develop\lib\Samples`; passing repository-only unit tests is insufficient.

The first full matrix run is an implementation feedback gate, not merely the
last ceremony. If it reaches a source-backed native field or expression layout
not covered by the initial implementation, development stops on that exact
failure, verifies the serializer in UE source, adds a minimal focused red test,
implements only that verified layout, and reruns the focused suite plus the
matrix. The loop continues until there is no unsupported field/token, closure
mismatch, translation failure, or semantic-oracle mismatch. Guessed byte skips
and blanket allowlists are forbidden.

## Delivery sequence

Implementation proceeds in independently reviewable stages:

1. Exact custom-version lookup and bounded UFunction navigation.
2. Native FField/FProperty prefixes, metadata, and recursive property families.
3. Dual-cursor transfer primitives and corrected FName/FFieldPath operands.
4. Expression terminators, versioned literals, invariants, and control-flow validation.
5. Pipeline fallback removal and function-only classification.
6. Result, IR, renderer, schema, and package-status propagation.
7. Multi-version real-sample semantic acceptance.

Each stage begins with a failing test, ends with focused green tests, and is
committed separately. The full suite and real matrix run after integration.
