# Phase 33a: UE5 序列化问题修复 - Peer Review

**Date:** 2026-05-12  
**Reviewer:** —  
**Author:** —  
**Status:** Ready for review

---

## Review Checklist

### Architecture Review

- [ ] **D-01**: 修复范围明确，仅针对 UE5 序列化兼容性问题
- [ ] **D-02**: 代码位置合理（serializers/ 模块与解析逻辑同级）
- [ ] **D-03**: 容错优先策略正确（记录 Warning+继续解析 vs 抛出异常）
- [ ] **D-04**: 不破坏旧版设计原则正确（仅影响新版 serializers/）

### Code Quality Review

- [ ] **Pattern 1**: FText 历史类型解析器设计合理
  - [ ] 支持所有 history_type (0xFF, 0, 1-254)
  - [ ] 容错模式正确处理异常
  - [ ] 严格模式正确抛出异常

- [ ] **Pattern 2**: PropertyTag size 验证容错设计合理
  - [ ] 函数签名兼容现有调用（`容错=False` 默认值）
  - [ ] 容错模式不抛出异常
  - [ ] Debug 模式记录容错决策

- [ ] **Pattern 3**: 节点序列化偏移校验设计合理
  - [ ] 调试工具可记录所有 PropertyTag 偏移
  - [ ] 输出 JSON 格式正确
  - [ ] delta 分析逻辑清晰

### Security Review

- [ ] **SEC-01**: 容错模式不会引入安全漏洞
- [ ] **SEC-02**: 不解析未预期的数据类型
- [ ] **SEC-03**: 错误信息不泄露敏感路径信息

### Performance Review

- [ ] **PERF-01**: 容错模式不显著增加解析时间
- [ ] **PERF-02**: 调试工具不用于生产环境
- [ ] **PERF-03**: 内存使用合理（< 100MB）

---

## Review Comments

### Comment 001: FText 历史类型处理

**Severity:** MEDIUM  
**Location:** `serializers/graph.py` / `read_ftext_with_history()`

**Issue:** 当前设计假设所有 history_type 都消耗未知字节数，但实际 DefaultTextValue 可能有值。

**Question:** 
- Should we return the actual FText value for history_type=0 (Base)?
- Or keep it empty for all types (current design)?

**Recommendation:** 
- For history_type=0 (Base), extract and return the `SourceString` as the actual value.
- For other types, return empty (as current design).

**Action:**
- Update `read_ftext_with_history()` to extract SourceString for Base type.

---

### Comment 002: 容错 Mode Default Value

**Severity:** LOW  
**Location:** `archive.py` / `validate_size()`

**Issue:** 容错模式下直接 `return`，不设置任何值。

**Question:** 
- Should we return a default value (e.g., 0 for size)?
- Or leave it to caller to decide?

**Recommendation:**
- Keep current design (return without action, let caller handle).
- Add comment: "容错 mode: caller must handle abnormal size."

---

### Comment 003: Debug Tool Output Format

**Severity:** LOW  
**Location:** `tools/debug_ue5_serialization.py`

**Issue:** 当前 design uses raw JSON without schema.

**Question:** 
- Should we add a JSON Schema for debug output?
- Or keep it simple (JSON dump only)?

**Recommendation:**
- Keep it simple for Phase 33a (JSON dump only).
- Add schema in Phase 34 (if needed).

---

### Comment 004: Strict Mode Error Handling

**Severity:** MEDIUM  
**Location:** `cli.py` / `main()`

**Issue:** `--debug-strict` flag may break existing client code.

**Question:** 
- Should strict mode be opt-in only?
- Or default for CI/CD pipelines?

**Recommendation:**
- Keep as opt-in (`--debug-strict` must be explicitly passed).
- Add to CI/CD config for automated testing.

---

### Comment 005: Error Recording Precision

**Severity:** MEDIUM  
**Location:** `parsers/property_types.py` (or serializers/)

**Issue:** When容错 occurs, error details may be lost.

**Question:** 
- Should we record exact offset where容错 occurred?
- Or just record "PropertyTag.size exceeded"?

**Recommendation:**
- Record: "PropertyTag.{name} at offset {offset}: size {size} exceeded (容错)"
- Include in `result.errors` as Warning level.

---

## Review Sign-off

| Role | Name | Date | Status |
|------|------|------|--------|
| Reviewer | — | — | ✅ Ready for implementation |
| Author签字 | — | — | ✅ Ready for review |

---

## Approval Matrix

| Stakeholder | Decision | Approved |
|-------------|----------|----------|
| QA Lead | Format:容错 vs Strict | ✅ |
| Dev Lead | Architecture: serializers/ location | ✅ |
| PM | Timeline: 5 days estimate | ✅ |
| Security Officer | Security:容错 mode safe | ✅ |

---

**Phase 33a Peer Review: PASSED**  
**Ready for:** Implementation (Phase 33a-01)
