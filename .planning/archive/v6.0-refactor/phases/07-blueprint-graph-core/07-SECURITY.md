---
phase: 07
slug: blueprint-graph-core
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-02
---

# Phase 7 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| ExportMap → EdGraph 检测 | class_index 解析可能返回异常类名 | PackageIndex / validated |
| SerialOffset → Node data | 偏移定位可能超出文件边界 | int64 / boundary checked |
| Nodes array count | 大数组可能导致内存耗尽 | int32 / capped at 5000 |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-07-01-01 | Tampering | resolve_class_name | mitigate | 范围检查 0 <= index < len(map) (L1772-1777) | closed |
| T-07-01-02 | Tampering | extract_blueprint_graphs | mitigate | PKG_Cooked标志检查 (L1836) | closed |
| T-07-01-03 | Tampering | linked_to_raw | accept | D-01原始数据，Phase 8验证 | closed |
| T-07-02-01 | Tampering | archive.seek(serial_offset) | mitigate | validate_offset()边界验证 (L243-251) | closed |
| T-07-02-02 | Tampering | pins_count | mitigate | MAX_PINS_PER_NODE=1000 (L66) | closed |
| T-07-02-03 | Tampering | nodes_count | mitigate | MAX_NODES_PER_GRAPH=5000 (L67) | closed |
| T-07-02-04 | Tampering | linked_to_count | mitigate | MAX_LINKEDTO_PER_PIN=100 (L68) | closed |
| T-07-03-01 | Tampering | match/case fallback | mitigate | unknown_type fallback (L2186-2188) | closed |
| T-07-03-02 | Tampering | FMemberReference | mitigate | resolve_class_name范围检查 (L2235-2237) | closed |
| T-07-03-03 | Tampering | CommentColor | mitigate | 读取4个float，不影响解析 | closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-07-01 | T-07-01-03 | linked_to_raw保存原始数据，格式验证推迟到Phase 8实现 | Security Auditor | 2026-05-02 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-02 | 10 | 10 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-02