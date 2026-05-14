---
phase: 06
slug: export-table-fix
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-02
---

# Phase 6 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| 输入文件 → FArchive | 不可信的 .uasset 文件，可能损坏或恶意构造 | Binary data / untrusted |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-06-01 | Tampering | read_export_map | mitigate | 偏移验证 + 错误上下文 (L1202) | closed |
| T-06-02 | Tampering | PackageGuid | mitigate | 读取但不存储 (L1639-1641) | closed |
| T-06-03 | Denial of Service | export_count | mitigate | MAX_EXPORT_COUNT=1,000,000 (L41) | closed |
| T-06-04 | Information Disclosure | ErrorContext | accept | 错误信息用于诊断，无敏感数据 | closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-06-01 | T-06-04 | ErrorContext包含偏移/版本信息用于诊断，不包含敏感数据（密码、密钥等），仅为调试上下文 | Security Auditor | 2026-05-02 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-02 | 4 | 4 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-02