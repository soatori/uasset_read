---
phase: 08
slug: blueprint-graph-output
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-02
---

# Phase 8 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| 输入 → 输出格式化 | UEdGraph数据来自Phase 7解析，已验证 | UEdGraph dataclass / trusted |
| 输入 → 执行流追踪 | UEdGraph数据来自Phase 7解析，已验证 | UEdGraph dataclass / trusted |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-08-01-01 | Denial of Service | build_connections_map() | accept | MAX_NODES_PER_GRAPH=5000已限制 | closed |
| T-08-01-02 | Information Disclosure | format_graphs_json() | accept | 无敏感数据，仅蓝图结构 | closed |
| T-08-02-01 | Denial of Service | build_execution_flows() | mitigate | visited set循环检测 (L3963) | closed |
| T-08-02-02 | Denial of Service | _trace_execution_from_event() | accept | MAX_NODES_PER_GRAPH=5000已限制图大小 | closed |
| T-08-03 | Denial of Service | format_text_full() | accept | 简单字符串拼接，图大小已限制 | closed |
| T-08-04 | Denial of Service | main() --graph 分支 | accept | 简单条件分支，无复杂计算 | closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-08-01 | T-08-01-01 | build_connections_map为简单dict遍历，Phase 7已限制图大小上限5000节点 | Security Auditor | 2026-05-02 |
| R-08-02 | T-08-01-02 | format_graphs_json输出蓝图结构，无敏感数据（密码、密钥等） | Security Auditor | 2026-05-02 |
| R-08-03 | T-08-02-02 | _trace_execution_from_event受限于MAX_NODES_PER_GRAPH=5000 | Security Auditor | 2026-05-02 |
| R-08-04 | T-08-03 | format_text_full为纯字符串格式化，图大小已受Phase 7限制 | Security Auditor | 2026-05-02 |
| R-08-05 | T-08-04 | CLI --graph分支为简单argparse条件，无安全敏感操作 | Security Auditor | 2026-05-02 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-02 | 6 | 6 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-02