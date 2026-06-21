# 输出格式精简设计

**日期**: 2026-06-21  
**目标**: JSON 输出精简为 C++ 翻译参考，去掉冗余信息  
**影响范围**: 仅 `json` 和 `markdown` 格式  
**状态**: ✅ 已完成

## 完成内容

- [x] JSON 去掉 name_map, imports, linker, resolved_depends_map 等冗余字段
- [x] JSON export 去掉 ue_export_raw, diagnostics, outer_index_resolved, super_index_resolved
- [x] Markdown 去掉重复的 Linker 小节
- [x] 测试 100% 通过
