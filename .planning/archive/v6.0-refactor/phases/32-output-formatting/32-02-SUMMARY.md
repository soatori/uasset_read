---
wave: 2
plan: 32-02
status: complete
created: 2026-05-12
---

# 32-02 SUMMARY: Text 和 Markdown 格式化模块迁移

## 完成内容

1. **text_formatter.py**
   - `format_text_full` — YAML 风格完整输出
   - `format_text_summary` — 精简摘要（每个 export 一行）

2. **markdown_formatter.py**
   - `format_markdown` — Markdown 输出（三节结构 + 表格）
   - `_build_mermaid_flowchart` — Mermaid graph LR 生成

3. **输出格式**
   - Text: Package header → Exports → Blueprint → Graphs → ERRORS
   - Markdown: Asset Overview 表格 → Blueprint Details → Graph Summary + Mermaid → Exports 表格

## 验证

- `python -c "from uasset_read import format_text_full, format_text_summary, format_markdown; print('OK')"` ✓

## 关键文件

- `src/uasset_read/formatters/text_formatter.py` (127 行)
- `src/uasset_read/formatters/markdown_formatter.py` (114 行)

## Commit

- `8af16b2` — feat(32-02): implement text_formatter and markdown_formatter