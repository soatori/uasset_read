# 源码体积预算报告

**生成日期**: 2026-06-11
**检查工具**: `scripts/quality/size_budget.py`

## 总体统计

- **总代码行数**: 41,641 行
- **文件数量**: 155 个
- **预算上限**: 35,000 行
- **状态**: ❌ 超出预算 6,641 行（119.0%）

## 大文件清单

### 硬限制违规（>1000 行）

| 文件 | 行数 | 状态 |
|------|------|------|
| src/uasset_read/cpp_gen/extract_cpp_skeleton.py | 1,354 | ❌ |
| src/uasset_read/kismet/translator.py | 1,158 | ❌ |
| src/uasset_read/serializers/package_summary.py | 1,070 | ❌ |
| src/uasset_read/blueprint/variable_extractor.py | 1,048 | ❌ |
| src/uasset_read/parsers/property_parser.py | 1,010 | ❌ |

### 软限制警告（>600 行）

| 文件 | 行数 | 状态 |
|------|------|------|
| src/uasset_read/ir_builder.py | 1,000 | ⚠️ |
| src/uasset_read/iostore/reader.py | 863 | ⚠️ |
| src/uasset_read/parse_uasset.py | 776 | ⚠️ |
| src/uasset_read/serializers/object_resources.py | 769 | ⚠️ |
| src/uasset_read/graph/flow_builder.py | 761 | ⚠️ |
| src/uasset_read/cpp_gen/formatters/cpp_json_ir.py | 726 | ⚠️ |
| src/uasset_read/link/linker.py | 711 | ⚠️ |
| src/uasset_read/parsers/property_types/structs.py | 686 | ⚠️ |
| src/uasset_read/serializers/graph/_common.py | 680 | ⚠️ |
| src/uasset_read/cpp_gen/formatters/cpp_header_formatter.py | 672 | ⚠️ |

## 改进计划

### 短期（v0.4.6）
- [ ] 拆分 `extract_cpp_skeleton.py`（1,354 行）→ 按骨架生成阶段拆分
- [ ] 拆分 `translator.py`（1,158 行）→ 按字节码类型分组拆分
- [ ] 拆分 `package_summary.py`（1,070 行）→ 按摘要节拆分
- [ ] 拆分 `variable_extractor.py`（1,048 行）→ 按变量类型拆分
- [ ] 拆分 `property_parser.py`（1,010 行）→ 按属性类别拆分

### 中期（v0.5.0）
- [ ] 将 `ir_builder.py`（1,000 行）控制在 600 行以内
- [ ] 将 `reader.py`（863 行）控制在 600 行以内
- [ ] 将 `parse_uasset.py`（776 行）控制在 600 行以内

### 长期
- 所有文件控制在 600 行以内
- 总代码行数控制在 35,000 行以内
- CI 集成 `--strict` 模式，阻止新增超限文件

## CI 集成

在 GitHub Actions 中添加体积检查：

```yaml
- name: Check size budget
  run: python scripts/quality/size_budget.py --strict
```
