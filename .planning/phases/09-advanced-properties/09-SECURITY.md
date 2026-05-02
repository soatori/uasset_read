---
phase: 09
slug: advanced-properties
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-02
---

# Phase 9 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| PropertyTag → 高级属性解析 | TypeName参数解析可能返回异常类型名 | FName / validated |
| TypeName → 参数解析 | 括号解析可能返回异常类型名 | str / format checked |
| StructProperty → 递归解析 | depth参数防止无限递归 | int / capped at 5 |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-09-01-01 | Tampering | type_dispatch lambda | mitigate | 参数数量验证，统一6参数签名 (L3635-3656) | closed |
| T-09-01-02 | Tampering | StructValue.fields | accept | MAX_DEPTH=5已限制 | closed |
| T-09-01-03 | Tampering | MapValue.entries | accept | 键类型分派已实现 | closed |
| T-09-02-01 | Denial of Service | parse_struct_property | mitigate | MAX_DEPTH=5检查 (L3183) | closed |
| T-09-02-02 | Denial of Service | PropertyTag循环 | mitigate | MAX_PROPERTY_COUNT=10_000 (L46) | closed |
| T-09-02-03 | Tampering | _extract_*_from_tag | mitigate | 括号检查，异常返回默认值 (L3027-3118) | closed |
| T-09-02-04 | Tampering | MapProperty键分派 | mitigate | 键类型验证，未知返回None (L3279-3321) | closed |
| T-09-03-01 | Tampering | Mock数据构造 | mitigate | struct.pack确保正确格式 (tests L164-197) | closed |
| T-09-03-02 | Tampering | 测试覆盖 | accept | Wave 3基础覆盖完成 | closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-09-01 | T-09-01-02 | StructValue.fields递归解析受MAX_DEPTH=5限制，超过抛出ParseError | Security Auditor | 2026-05-02 |
| R-09-02 | T-09-01-03 | MapValue.entries键类型分派已实现，未知类型返回None | Security Auditor | 2026-05-02 |
| R-09-03 | T-09-03-02 | Wave 3完成基础测试覆盖，后续Lyra资产验证补充 | Security Auditor | 2026-05-02 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-02 | 9 | 9 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-02