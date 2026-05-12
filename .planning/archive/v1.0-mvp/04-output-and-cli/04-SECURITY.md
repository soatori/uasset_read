---
phase: 04
slug: output-and-cli
status: verified
threats_open: 0
asvs_level: 1
created: "2026-05-02T00:30:00Z"
---

# Phase 4 — Security

> Phase 4 添加 CLI 接口，但无网络操作或外部依赖。安全风险与 Phase 1-3 相同（低风险）。

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| CLI → File System | 用户通过 CLI 提供 .uasset 文件路径 | 文件路径（用户输入） |
| CLI → stdout/stderr | 解析结果输出到终端或文件 | 结构化数据（JSON/YAML文本） |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-04-01 | Tampering | CLI file argument | mitigate | argparse 验证 + Path.exists() 检查 | closed |
| T-04-02 | Tampering | --output flag path | mitigate | argparse 验证 + Path 操作 | closed |
| T-04-03 | Tampering | Unicode output | mitigate | UTF-8 编码控制 (D-28), json.dumps ensure_ascii=False | closed |
| T-04-04 | Denial of Service | Large file output | accept | 输出大小限制推迟到 Phase 5 (D-29) | closed |

**Mitigation Details:**

- **T-04-01/T-04-02:** argparse 处理命令行参数，Path.exists() 验证文件存在。非有效路径返回退出码2。
- **T-04-03:** 所有输出使用 UTF-8 编码，避免 Unicode 注入问题。
- **T-04-04:** 大文件输出内存消耗推迟到 Phase 5 性能优化阶段。当前阶段专注正确性。

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| A-04-01 | T-04-04 | 大文件输出 DoS 风险推迟到 Phase 5 | gsd-secure-phase | 2026-05-02 |

**Reasoning:** Phase 4 专注输出格式化和 CLI 实现。Phase 5 专门处理性能优化（SAFE-01 至 SAFE-05），大文件处理和内存限制将在此阶段解决。

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-02 | 4 | 4 | 0 | gsd-secure-phase |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-02

---

## Summary

Phase 4 安全审查完成。所有威胁已缓解或接受。

- **风险等级:** 低（无网络操作，无外部依赖）
- **开放威胁:** 0
- **接受风险:** 1（大文件 DoS 推迟到 Phase 5）

Phase 4 可安全推进。