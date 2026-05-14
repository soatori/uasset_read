---
phase: 17
slug: 17-property-parsing-fix
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-04
---

# Phase 17 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| 文件数据 → 解析器 | 二进制数据从 .uasset 文件读取 | UE 资产二进制数据（非敏感） |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-17-01 | Tampering | parse_properties_from_export | mitigate | FArchive.seek 调用 validate_offset (line 251) | closed |
| T-17-02 | Denial of Service | 偏移计算 | accept | 简单加法运算，无循环风险 | closed |
| T-17-03 | Tampering | serialization_control | mitigate | FArchive.read_u8 → read(1) 边界验证 (line 226) | closed |
| T-17-04 | Denial of Service | 头部读取 | accept | 仅读取 1-2 bytes，无资源消耗风险 | closed |
| T-17-05 | Tampering | property_extensions | mitigate | FArchive.read_u8 → read(1) 边界验证 (line 226) | closed |
| T-17-06 | Denial of Service | Extensions 读取 | accept | 最多读取 3 bytes，无资源消耗风险 | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-17-01 | T-17-02 | 偏移计算为简单加法 (serial_offset + script_serial_offset)，无循环或递归风险 | gsd-security-auditor | 2026-05-04 |
| AR-17-02 | T-17-04 | 头部读取仅消耗 1-2 bytes，已有 FArchive 边界验证保护 | gsd-security-auditor | 2026-05-04 |
| AR-17-03 | T-17-06 | Extensions 读取最多 3 bytes，已有 FArchive 边界验证保护 | gsd-security-auditor | 2026-05-04 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-04 | 6 | 6 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-04