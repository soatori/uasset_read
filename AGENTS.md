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

## Development Rules

- Use Python 3.10+ and keep core behavior cross-platform.
- Prefer the standard library and existing project code. Dependencies are allowed only at a documented capability boundary and must fail gracefully when optional.
- The first v2 milestone is read-only. Writer support requires a separate approved design.
- Use bounded reads, validated counts, explicit offsets, and structured failure states at all binary trust boundaries.
- Add the smallest strict test that proves non-trivial behavior. Do not swallow broad exceptions in aggregate tests.
- Temporary scripts and generated investigation output belong under `temp/` and must not become runtime dependencies.
- Preserve unrelated work in a dirty tree.

## Code Navigation

When `.codegraph/` exists, use CodeGraph before broad text search to understand symbols, callers, and impact. Use `rg` for exact text, documentation, and non-indexed files.

## Documentation Changes

- Update the canonical design first when a repository-wide target decision changes.
- Keep binary format reference in `docs/formats/`, product design in `docs/designs/`, current user guidance in `README.md`/`wiki/`, and Agent guidance in this file plus `docs/reference/agent-dev-reference.md`.
- Superseded repository-wide designs move to `docs/designs/archive/`, retain a visible archive banner, and link to the canonical design.
- Do not hardcode a developer's UE checkout path in committed documentation. Use paths relative to the Unreal Engine source root.
- OpenWiki repository generation is enabled only when a root `.openwikiignore` exists. Until then, maintain the existing Markdown and Wiki directly.
