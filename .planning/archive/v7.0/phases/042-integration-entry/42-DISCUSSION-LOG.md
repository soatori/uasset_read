# Phase 42 Discussion Log

**Phase:** 42 — 集成入口
**Date:** 2026-05-14
**Mode:** --batch

## Areas Discussed

### 1. 返回类型
**Question:** 返回独立的 LinkerParseResult 还是扩展 ParseResult？
**Decision:** 保持独立的 LinkerParseResult
**Rationale:** 类型边界清晰，调用方明确知道拿到的是 linker 结果

### 2. 错误降级
**Question:** linker 链路失败时如何处理？
**Decision:** 搜集 errors 到结果中（类似 tolerant 模式）
**Rationale:** 与项目现有的容错模式一致，不隐藏问题也不强制 try/except

### 3. 结果聚合范围
**Question:** 新入口点是否也做 blueprint metadata / graphs / dependencies 提取？
**Decision:** 提取公共后处理为内部函数复用
**Rationale:** 避免 parse_uasset.py 中两套入口代码重复

### 4. API 签名
**Question:** 函数参数如何设计？
**Decision:** Claude 决定 — 与 parse_uasset() 保持一致签名 + preload_all=False
**Rationale:** 一致性好，preload_all 符合两阶段加载的惰性设计理念

## Deferred Ideas

None
