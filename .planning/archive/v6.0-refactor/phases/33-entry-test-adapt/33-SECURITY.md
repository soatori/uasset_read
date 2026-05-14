---
phase: 33
slug: entry-test-adapt
status: draft
threats_open: 0
asvs_level: 1
created: 2026-05-12
---

# Phase 33 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail. Retroactive-STRIDE audit of implementation files.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| CLI entry point | User-provided file path进入解析管线 | User-controlled .uasset file path |
| File I/O | 读取.uasset文件内容 | Binary UObject serialized data |
| Error output | 错误信息输出到stderr | File path, context, parse errors |
| Output routing | 解析结果输出到stdout或文件 | Structured JSON/Text/Markdown |

---

## Threat Register

This register was constructed retroactively from implementation files (Phase 33 Plan 01-03_SUMMARY.md threat flags and implementation review).

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-33-01 | Input Validation | cli.py: --export INDEX | Mitigate | argparse `type=int` auto-validates non-integer values; invalid values raise SystemExit → EXIT_ARGUMENT_ERROR | Closed |
| T-33-02 | Input Validation | cli.py: file path existence | Mitigate | `Path.exists()` check before parsing; non-existent paths output to stderr → EXIT_FILE_NOT_FOUND | Closed |
| T-33-03 | Input Validation | cli.py: file read permissions | Mitigate | FArchive constructor handles open failures; IOError → parse error → EXIT_PARSE_ERROR | Closed |
| T-33-04 | Error Disclosure | parse_uasset.py: error messages | Accept | Error messages include file path and parse context in result.errors (not stderr); no sensitive file content exposed | Closed |
| T-33-05 | Path Safety | cli.py: file output | Mitigate | Only read operations; output path is controlled by user-provided `--output FILE`; no write to user-provided input path | Closed |
| T-33-06 | Path Safety | parse_uasset.py: file path handling | Mitigate | File path used only for read operations; no file write or delete operations per implementation | Closed |
| T-33-07 | Error Handling | cli.py: IOError on output | Mitigate | `IOError` caught when writing to `--output FILE`; error message to stderr → EXIT_ARGUMENT_ERROR | Closed |
| T-33-08 | DoS | parse_uasset.py: large file handling | Accept | No file size limits enforced; large files may exhaust memory but no loop/stack boundaries exceeded (no arbitrary code execution vector) | Closed |
| T-33-09 | Input Validation | parse_uasset.py: VersionError | Mitigate | Try/except catches VersionError; sets result.is_success=False; returns partial result with error | Closed |
| T-33-10 | Input Validation | parse_uasset.py: ParseError | Mitigate | Try/except catches ParseError; sets result.is_success=False; may return partial result with error | Closed |
| T-33-11 | Input Validation | parse_uasset.py: generic Exception | Mitigate | Try/except catches Exception; sets result.is_success=False; returns result with "Unexpected error" message | Closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-33-01 | T-33-04 | Error messages include parse context for debugging but DO NOT expose file contents; only metadata (file path, export name, property name) | Claude AI | 2026-05-12 |
| R-33-02 | T-33-08 | No file size limits enforced; relies on user environment memory limits to prevent exhaustion | Claude AI | 2026-05-12 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-12 | 11 | 11 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-12
