# Repository Instructions

These rules apply to every human or agent working in this repository.

## Documentation Authority

- **Implemented behavior:** inspect `src/`, `tests/`, and real sample results. Do not infer implementation from a design document.
- **Target architecture:** [`docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`](docs/designs/2026-08-26-package-first-uasset-parser-refactor.md) is the only authoritative repository-wide refactor design.
- **Design status index:** read [`docs/designs/README.md`](docs/designs/README.md) before using an older design.
- **Binary format facts:** trace them to Unreal Engine source. External reports and third-party parsers are corroborating evidence only.
- Always distinguish `current`, `target`, `historical`, and `superseded` in documentation and task summaries.

The package-first design is not implemented merely because it is documented. Do not update README features or Wiki API examples until source and tests support the claim.

## Target Invariants

- The public document boundary is a package, not a selected primary asset.
- Every export remains addressable; `bIsAsset` adds a role and never filters other objects.
- Legacy and Zen packages use separate binary readers and converge on one object model.
- Tagged and unversioned properties use separate readers and converge on one value model.
- Domain semantics live under an object; they do not own or overwrite the package envelope.
- JSON, CLI, Python, and Agent tools project from the same `PackageDocument`.
- Large payloads are referenced and extracted on demand, not embedded by default.
- Library code returns structured diagnostics and does not configure process-global logging.
- Public package output (v4 target, `format_version: "4.0"`, frozen contract `docs/designs/contract/package_document_v4.schema.json`) is one full document per input package with exactly the `normal` and `debug` modes. Debug adds evidence only; after stripping that evidence and normalizing `mode`, it equals normal. View/depth/selection/pagination/`max_bytes` are not public output surfaces. C++ projection is retired; Blueprint instruction IR/CFG and static semantics remain targets. Public signatures: `parse_package_document(file_path, *, tolerant=True, mappings_path=None, game=None, depth="decode", object_ids=None)`, `project_document(document, *, mode="normal")` (sole envelope producer), `write_projected_document(document, output_path, *, mode="normal")`, `inspect_package(file_path, *, mode="normal")`; `extract_payload()` stays a separate binary operation. Target only — do not claim v4 is implemented before source and tests say so.

## Development Rules

- Use Python 3.10+ and keep core behavior cross-platform.
- Prefer the standard library and existing project code. Dependencies are allowed only at a documented capability boundary and must fail gracefully when optional.
- The first v2 milestone is read-only. Writer support requires a separate approved design.
- Use bounded reads, validated counts, explicit offsets, and structured failure states at all binary trust boundaries.
- Add the smallest strict test that proves non-trivial behavior. Do not swallow broad exceptions in aggregate tests.
- Temporary scripts and generated investigation output belong under `temp/` and must not become runtime dependencies.
- Preserve unrelated work in a dirty tree.

## Agent Task Mode and Loop Boundaries

- Classify the request before choosing a workflow. Read-only questions, diagnosis, audits, documentation/status checks, and explanations terminate with an evidence report; they are not implementation tasks.
- In read-only mode, do not invoke writing-plans, subagent-driven-development, dispatching, branch-finishing, code-review, or full-suite verification workflows unless the user explicitly requests that workflow.
- Plan discovery is opt-in. Inspect `.superpowers/sdd/` or `docs/superpowers/plans/` only when the user supplies an exact plan path or explicitly asks to execute/replay a plan. Never glob those directories to guess the active task.
- A plan marked `completed`, `historical`, `superseded`, or having all task checkboxes checked is evidence, not executable work. Do not rerun its commands; create a new plan only for a new request.
- An identical tool/query/path may not be repeated. After one changed, narrower retry produces no new evidence, stop and report the missing state or blocker instead of searching again.
- For documentation-only changes, verify with `git diff --check` and targeted document assertions. Run the full test suite only when source/tests changed or the user explicitly requests it.

## Code Navigation

When `.codegraph/` exists, use CodeGraph before broad text search to understand symbols, callers, and impact. This is a code-understanding rule, not a reason to discover tools or plans during a documentation-only task. Use `rg` for exact text, documentation, and non-indexed files.

## Documentation Changes

- Update the canonical design first when a repository-wide target decision changes.
- Keep binary format reference in `docs/formats/`, product design in `docs/designs/`, current user guidance in `README.md`/`wiki/`, and Agent guidance in this file plus `docs/reference/agent-dev-reference.md`.
- Superseded repository-wide designs move to `docs/designs/archive/`, retain a visible archive banner, and link to the canonical design.
- Do not hardcode a developer's UE checkout path in committed documentation. Use paths relative to the Unreal Engine source root.
- OpenWiki repository generation is enabled only when a root `.openwikiignore` exists. Until then, maintain the existing Markdown and Wiki directly.
