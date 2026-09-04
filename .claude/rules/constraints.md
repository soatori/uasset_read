# Project Constraints

The authoritative target is `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`. These constraints govern new work; source and tests remain authoritative for current behavior.

## Core Constraints

- **Python and cross-platform** — Support Python 3.10+ on Windows, Linux, and macOS; do not depend on fixed drive letters or user directories.
- **Read-only first milestone** — v2 initially parses and extracts only. Binary writing requires a separate approved design and corruption-safety tests.
- **UE source reference required** — Binary layout decisions must trace to UE C++ source; external reports and third-party parsers are corroboration, not proof.
- **Bounded binary reads** — Validate ranges, counts, multiplication, recursion, and allocations before consuming untrusted data.
- **Unknown data is preserved** — Return an opaque region and diagnostic when data cannot be decoded; never silently skip and claim complete coverage.
- **Temp files in `temp/`** — Investigation scripts, intermediate output, generated debug data, and test artifacts belong under `temp/`.
- **Minimal implementation** — Reuse current code and the standard library before adding abstractions or dependencies.

## Architecture Constraints

- **Package-first** — The public document contains all exports. `bIsAsset` is a role, not a primary-object filter.
- **One object model** — Legacy and Zen readers converge on `PackageDocument`/`ObjectRecord`; they do not share incompatible binary layouts.
- **Property split** — Tagged and unversioned properties use separate readers and a common value model.
- **One output envelope** — Domain semantics live under `objects[].semantic`; no new top-level `uasset_read.<domain>_semantic` formats.
- **Layered status** — Keep package parse, object parse, semantic coverage, and payload availability distinct.
- **Payload references** — Large payloads are descriptors by default and are extracted only on explicit request with a byte limit.
- **Diagnostics over logs** — Library code returns structured diagnostics and must not configure process-global logging.
- **No permanent dual pipeline** — Compatibility adapters may exist during migration, then old builders/renderers are removed after callers move.

## Dependency Constraints

- Prefer the standard library and already-installed project code.
- Optional codecs, encryption, and MCP support belong behind capability boundaries; missing optional packages must not break core imports.
- A mandatory dependency requires a documented maintenance benefit, license review, and cross-platform CI evidence. Zero runtime dependencies is a preference, not an immutable product requirement.
- Do not vendor external reference repositories or generated caches into the release package.

## Output and Agent Constraints

- Default output is bounded and excludes raw blobs, full HexView data, and unlimited arrays.
- Raw/debug/decode data is selected explicitly through view, depth, object filters, pagination, and `max_bytes`.
- Agent tools call the Python document API directly; they do not parse CLI output.
- Stable ids use table kind and index. Display names and GUIDs are not guaranteed unique.
- Truncation and unsupported capabilities must be explicit and resumable.

## Peer corroboration constraints

Operational sub-rules for "UE source reference required" above. Full scheme: `docs/designs/2026-09-02-peer-corroboration-usage-scheme.md`. Tracked inventory (pin commits, licenses, verified coverage): `docs/reference/external-peer-inventory.md`.

- **Named peers only** — write `Corroborated (not proof): <Peer> <symbol>`. The bare plural `corroborated by peers` is banned and rejected by the CI `peer-evidence-hygiene` step.
- **Independence counts** — a consensus claim needs at least two independent implementations. UAssetGUI delegates to UAssetAPI, so the pair counts as one implementation.
- **Zero coverage is stated, not guessed** — when no peer decodes a type, record `No peer parser decodes this type` and keep the capability tier honest instead of inferring a layout.
- **Corroboration is never a support claim** — a `Corroborated` comment may only appear in summary-tier or implementation-ahead code. Version and asset-support claims still require UE source evidence, a real fixture, and structural assertions (Test Organization below).
- **Evidence must be tracked** — peer facts belong in the inventory, per-field conclusions in a committed design or review document. `temp/` is untracked and CI-blocked, so it cannot be the only carrier of a claim.
- **License red lines** — peers with no LICENSE file, or a NON-AI license, may not be transcribed into this repository or used to generate committed code. Use an independently licensed peer for the same corroboration.

## Test Organization

- Phase 0 deletes and replaces the legacy Python test suite in one atomic change; do not maintain parallel old/new suites.
- Keep all tracked files under `tests/samples/` and validate SHA-256, size, version, layout and sidecars through the manifest.
- Missing fixtures are manifest gaps. Do not use `skip`, `xfail`, long-lived failing tests, or broad exception swallowing to simulate coverage.
- Do not use `MagicMock` for UE binary structures. Use bounded bytes for reader tests and real fixtures for support claims.
- Structured diagnostics are authoritative; text logs are tested only for lifecycle and unwanted side effects.
- Do not add wall-clock benchmark thresholds. Test deterministic count/range/byte/resource limits instead.
- Do not add root-level or `scripts/` verification programs. Reusable behavior belongs in package APIs, `python -m uasset_read`, or Agent tools.
- The current blocking test environment is local Windows + Python 3.14. Linux, macOS and other Python versions are deferred and must not be claimed as verified.
- Version or asset-support claims require UE source evidence, a real fixture, structural assertions, and honest partial/unsupported states.

## Documentation Constraints

- Mark documents as current, target, historical, or superseded.
- Update the canonical design before changing a repository-wide target decision.
- Do not infer implementation status from issue closure or design approval.
- Do not commit machine-specific Unreal Engine source paths.
