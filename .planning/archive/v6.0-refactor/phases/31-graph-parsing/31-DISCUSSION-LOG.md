# Phase 31: 蓝图图解析模块 - Discussion Log

**Date:** 2026-05-12
**Mode:** discuss --batch

## Areas Discussed

### 1. 图解析模块归属
**Question:** 图解析函数应该放在哪个目录？
**Options:** (a) 新建 graph/ 目录 (b) 放入 parsers/ (c) serializers/ + parsers/ 分离
**Decision:** 1a — 新建 `src/uasset_read/graph/` 目录（与 parsers/ 同级）
**Rationale:** 图解析是一个独立域，与属性解析平级，单独目录更清晰。

### 2. from_archive 实现策略
**Question:** models/core.py 中的 from_archive stub 如何实现？
**Options:** (a) 直接在 dataclass 内实现 (b) 委托给 serializers 独立函数 (c) 混合
**Decision:** 2b — 模型保留 stub，内部调用 serializers/graph.py 中的独立函数
**Rationale:** 保持 Phase 29 D-06 的数据/序列化解耦原则，一致性强。

### 3. 执行流/数据流构建归属
**Question:** build_execution_flows 等函数归属哪里？
**Options:** (a) 与图解析一起 (b) Phase 32 formatters (c) 独立 analysis/ 模块
**Decision:** 3a — 放在 `graph/flow_builder.py`，与图解析同域
**Rationale:** 这些是图分析能力，不是格式化，与图解析放在一起更合理。

### 4. 节点类型扩展机制
**Question:** 节点类型分派用哪种模式？
**Options:** (a) match/case 硬编码 (b) 注册表模式 (c) 工厂模式
**Decision:** 4c — 工厂模式（NodeFactory.create）
**Rationale:** 比 match/case 更易扩展新类型，比注册表更简单直接。

## Deferred Ideas

- UberGraph/事件分发图增强 (v8.0)
- 字节码反编译 (v8.0)
- .umap 解析 (v9.0)
