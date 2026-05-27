# 输出格式 PascalCase 对齐

## 背景

Phase 80 将 JSON/Text 输出格式与 CUE4Parse 字段名一一对齐，消除 snake_case 残留。

## 目标

1. `format_json_cue4parse()` — PascalCase 字段名、ExportTypes 结构
2. `format_text_full()` 重构 — dict→统一文本渲染
3. BlueprintText 统一到 Schema
4. JSON 输出与 CUE4Parse 字段名一一对应

## 架构

修改现有 formatter 模块，在 snake_case 输出旁增加 PascalCase 输出函数，逐步迁移默认行为。

关键文件：
- `src/uasset_read/formatters/json_formatter.py` — 新增 `format_json_cue4parse()`
- `src/uasset_read/formatters/text_formatter.py` — 重构 `format_text_full()`

## 验收标准

- JSON 输出与 CUE4Parse 字段名一一对应
- 无 snake_case 残留
- 向后兼容：旧格式函数仍可用
