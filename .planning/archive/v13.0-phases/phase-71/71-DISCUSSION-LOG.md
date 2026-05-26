# Phase 71 — Discussion Log

**Date:** 2026-05-22
**Phase:** 71 — 执行流链式表达

## Key Finding

Phase 70 已在 `n2c/flow_extractor.py` 中实现链式提取算法（`extract_chains`），Phase 71 的核心算法**已就绪**。讨论聚焦于如何从 N2C 内部提取为公共 API 并替代 pair 格式。

## Discussion Areas

### 1. 链式暴露范围
**选项：** 标准 JSON 输出 / 独立 API / 替代 pair / 仅 N2C
**用户选择：** 标准 JSON 输出 + 独立 API + 替代 pair（三项全选）
**决策：** Phase 71 交付三件事：(1) 新 `build_execution_chains()` API，(2) 标准 JSON 输出加链式视图并替换旧字段，(3) 旧 API deprecated 但保持回退兼容。

### 2. 输出格式设计
**选项：** graph 级字段 / 顶层格式 / 仅 formatter
**用户选择：** 让 Claude 决定
**决策：** D-01 + D-02 + D-05 — 在 graph 级别添加 `execution_chains` 字段替代 `execution_flows`，新 API 返回 `{start_event, chains[], has_cycle}` 结构。

### 3. 迁移策略
**选项：** 一次性替换 / 双轨并行
**用户选择：** Phase 内一次性替换
**决策：** 所有 consumer 在本 phase 内迁移到链式 API。旧 `build_execution_flows()` 保留 deprecated 标记。

### 4. 分支处理
**选项：** 链终止于分支点 / 链内标注分支标签
**用户选择：** 每条链终止于分支点
**决策：** Branch/Sequence 拆分多条链，不复用 N2C 的 `_format: pairs` 回退。
