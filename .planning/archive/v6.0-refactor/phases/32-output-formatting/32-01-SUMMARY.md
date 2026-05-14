---
wave: 1
plan: 32-01
status: complete
created: 2026-05-12
---

# 32-01 SUMMARY: JSON 格式化模块迁移

## 完成内容

1. **formatters 模块结构创建**
   - `src/uasset_read/formatters/__init__.py` — 公共导出 + Phase 31 re-export
   - `src/uasset_read/formatters/json_formatter.py` — 5 个 JSON 格式化函数
   - `src/uasset_read/formatters/helpers.py` — 3 个辅助函数
   - `src/uasset_read/formatters/text_formatter.py` — placeholder (Wave 2)
   - `src/uasset_read/formatters/markdown_formatter.py` — placeholder (Wave 2)
   - `src/uasset_read/formatters/schemas/__init__.py` — D-09 预留目录

2. **JSON 格式化函数迁移**
   - `format_json_full` — 完整 JSON 输出，output_version="4.0"
   - `format_json_summary` — 精简 JSON 摘要
   - `format_exports_list` — 导出列表格式化
   - `format_properties_list` — 属性列表格式化
   - `format_blueprint_dict` — 蓝图元数据字典 + Phase 26 增强函数

3. **辅助函数迁移**
   - `build_status_info` — 状态三元分类 (success/fail/error)
   - `build_schema_info` — 字段语义注释
   - `resolve_fpackage_index` — PackageIndex 解析

4. **D-02 决策验证**
   - `format_json_full` 输出不再包含 `imports`, `soft_references`, `circular_deps` 字段

5. **Phase 31 re-export**
   - `build_graphs_summary`, `format_graphs_json`, `format_pin_ref`, `_derive_node_name`

## 验证

- `python -c "from uasset_read import format_json_full, format_json_summary, build_status_info; print('OK')"` ✓
- `format_json_full` output_version="4.0" ✓
- D-02 字段移除验证通过 ✓

## 关键文件

- `src/uasset_read/formatters/json_formatter.py` (367 行)
- `src/uasset_read/formatters/helpers.py` (89 行)
- `src/uasset_read/formatters/__init__.py` (58 行)

## Commit

- `cd5f6e3` — feat(32-01): create formatters module with json_formatter and helpers