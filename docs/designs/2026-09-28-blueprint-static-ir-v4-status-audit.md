# v4 Package Output and Blueprint Static IR Current-State Audit

status: current audit (not a target design and not an implementation claim)

Date: 2026-09-28

Scope: review of the two 2026-09-28 plans:

- `docs/superpowers/plans/2026-09-28-package-output-normal-debug-plan.md`
- `docs/superpowers/plans/2026-09-28-blueprint-static-parsing-completion-plan.md`

## Executive conclusion

The v4 output shell is partially landed. The Blueprint plan's newly requested
static-IR records are not implemented. C++ projection/translation remains out
of scope and has been retired.

The current implementation has a useful base IR: typed graph/node/Pin data,
ordered Kismet instructions, recursive operands, bytecode CFG, calls, variable
accesses, components, and v4 normal/debug envelopes. It does not yet provide
the complete, lossless and auditable Blueprint IR required by the companion
plan.

## 1. Confirmed landed v4 work

The supplied verification report records the following as completed:

- v4 schema and the `normal`/`debug` modes;
- one `project_document()` envelope producer;
- default `decode` parsing, CLI `--debug`, and the writer;
- deletion of C++ projection/rendering;
- schema and normal/debug parity probes for eight representative samples;
- `T_ParserBulk` `.uexp` physical mapping, with reported offset `0`;
- a reported full-suite result of `96 passed`, plus `compileall` and
  `git diff --check` success.

These results establish the v4 envelope direction, but do not prove that the
Blueprint semantic producers satisfy the new companion-plan fields.

## 2. Blueprint static IR status

| Capability | Status | Current evidence |
| --- | --- | --- |
| Node/Pin identity | Partial | `GraphId`, `NodeId`, Pin GUID, Pin names, directions, categories, defaults, and node metadata exist. There is no single public record enforcing `graph_id + node_id + pin_guid` for every connection. |
| Complete Exec/Data links | Not complete | Output is Pin-local resolved adjacency plus counts. Serialized null, unresolved, ambiguous, and import-owned references are not retained one-for-one. See `src/uasset_read/serializers/graph_pin.py:125` and `src/uasset_read/parsers/blueprint/graph.py:60`. |
| `GraphLinkRecord` | Not implemented | No such producer or model exists under `src/`. |
| Variables/default values | Partial | `VariableDefinition`, Pin defaults, type/category fields, and variable accesses exist. Container/object/reference details and complete per-asset coverage are not guaranteed. |
| Components/object relations | Partial | Component name/class/object ID and package-level outer/class/generated/default relations exist; complete parent-child component structure and component defaults are not projected. |
| Function signatures | Not complete | `FunctionDeclaration` is emitted, but current construction supplies empty parameters, no return type, no flags, and no native fields. See `src/uasset_read/parsers/blueprint/correlation.py:318`. |
| Full function expressions | Partial | Ordered instructions, mnemonic Opcode, recursive operands, expressions, reads/writes, call target, and jump target exist. Raw Opcode, explicit stable reference records, and complete typed expression coverage are missing. |
| CFG | Core implemented, integration incomplete | Basic blocks, conditional edges, jumps, loop-back edges, computed jumps, and Return termination exist in `control_flow.py`. Exec Pin links are not unified with bytecode CFG, and Switch/Sequence/Latent semantics are not represented as dedicated records. |
| Type conversion | Partial | Pin-type and Cast-related expression data are parsed, but the public Pin/type shape does not retain every container, object, reference, and struct detail required by the design. |
| External references | Not implemented | No `external_refs`, qualified key, origin, source evidence, or stable joined call-reference record exists. Name-only resolution can still select the first candidate. See `src/uasset_read/parsers/blueprint/correlation.py:221`. |
| Runtime boundary markers | Not implemented | No dedicated `external` or `runtime_external` records are emitted for UE/plugin internals or runtime-only World/Actor behavior. Runtime state is not fabricated, which is correct. |
| Unresolved/opaque content | Partial | `OpaqueOperand`, `parse_status`, `ByteRegion`, and structured diagnostics exist, but links and external references are not uniformly represented with status and reason fields. |
| Debug provenance | Not implemented for Blueprint records | Top-level v4 debug arrays exist, but nested `debug_evidence`, raw Pin GUID/index evidence, connection ranges, raw Opcode, and source-node reasons are absent. |

## 3. v4 normal/debug contract defects

The current Blueprint projection still emits `serialized_start` and
`serialized_end` in common output:

- `src/uasset_read/parsers/blueprint/bytecode.py:275`;
- `src/uasset_read/parsers/blueprint/correlation.py:1182`;
- `src/uasset_read/projection.py:40` does not remove these fields or nested
  `debug_evidence`.

Therefore the current output does not satisfy the intended rule:

> normal contains static IR without physical/debug evidence; debug adds the
> evidence and remains parity-equivalent after evidence removal.

## 4. Acceptance and test status

The focused Blueprint test modules were removed by the sample-first cleanup
(`bb192a20` / `308c348e`). The current checkout does not contain:

- `tests/test_contract_v4.py`;
- `tests/test_blueprint_cfg.py`;
- the former standalone Blueprint graph/correlation/operand test modules.

`tests/test_size_baseline.py` currently enforces a maximum of two tracked test
modules. Consequently, a green aggregate suite cannot prove the missing
GraphLinkRecord, external-reference, source-node, or nested debug-evidence
contracts.

The supplied report also records these fixture gaps:

- CurveTable representatives are `unavailable` and produce zero CSV rows;
- DataTable representatives remain `represented/partial`;
- the v4 representative-fixture acceptance therefore is not complete.

## 5. Documentation consistency

README still contains claims about v3 output, retired CLI flags, and C++
projection that conflict with the current v4 source. The conflicting claims
are reported at `README.md:9` and require a separate documentation cleanup.

## 6. Current-checkout note

The supplied report states that the worktree is clean. A live read-only check
at the time of this audit showed existing modifications in documentation,
sample manifests, test files, and baselines, while no Blueprint source change
was present. Those changes were not made by this audit and were preserved.

The supplied `96 passed` result should therefore be treated as historical
verification until the full suite is rerun from the intended clean baseline.

## Final acceptance verdict

| Area | Verdict |
| --- | --- |
| v4 envelope direction | Partially accepted |
| v4 normal/debug Blueprint evidence contract | Not accepted |
| Complete Blueprint static IR | Not accepted |
| Complete Pin connection preservation | Not accepted |
| External-reference model | Not accepted |
| Readable bytecode CFG core | Accepted as a base capability, not as complete Blueprint CFG |
| C++ translation exclusion | Accepted |
| Representative fixture acceptance | Not accepted |
| Documentation consistency | Not accepted |

## Required next implementation boundary

The next implementation should remain limited to static Blueprint IR:

1. add one `GraphLinkRecord` per serialized link, with unresolved/ambiguous
   status and raw debug evidence;
2. add conservative `ExternalReferenceRecord` resolution and stable keys;
3. add complete function-signature fields and source-node reasons;
4. move offsets/raw Opcode/GUID evidence out of normal and into debug;
5. add the smallest acceptance coverage possible within the two-module test
   limit, using StackOBot, BP_CombatCharacter, and UE5.8 TestBlueprint;
6. rerun v4 schema/parity, fixture, full-suite, compileall, and documentation
   checks.

C++ translation, Unreal/plugin function-body recovery, runtime World/Actor
state, and physical/timer/rendering simulation remain outside this boundary.
