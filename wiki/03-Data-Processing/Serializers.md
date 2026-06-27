---
title: 序列化模块
section: serializers
---

# 序列化模块

> 序列化模块负责从二进制流中读取包的 Summary、导入/导出表、属性标签和图结构。

## 模块概览

| 模块 | 职责 | 关键函数/类 |
|------|------|-------------|
| `package_summary.py` | PackageFileSummary、NameTable | `read_package_summary` `read_name_table` |
| `object_resources.py` | ImportMap、ExportMap、PackageIndex | `read_import_map` `read_export_map` `resolve_class_name` |
| `property_tags.py` | PropertyTag 读取、控制标志 | `read_property_tag` `parse_ctrl_flags` |
| `graph.py` | UEdGraph/Node/Pin 读取 | `read_ue_graph` `read_ue_graph_node` `read_ue_graph_pin` |

## PackageIndex 编码

- **正数**：导出索引（1-based）
- **负数**：导入索引（-1-based）
- **零**：空引用

---

**相关章节**: [[解析管线]] · [[属性解析器]] · [[数据模型]] · [[对象链接器]]
