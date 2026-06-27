---
title: Serializer Module
section: serializers
---

# Serializer Module

> The serializer module is responsible for reading the package Summary, Import/Export tables, Property Tags, and graph structures from the binary stream.

## Module Overview

| Module | Responsibility | Key Functions/Classes |
|--------|---------------|----------------------|
| `package_summary.py` | PackageFileSummary, NameTable | `read_package_summary` `read_name_table` |
| `object_resources.py` | ImportMap, ExportMap, PackageIndex | `read_import_map` `read_export_map` `resolve_class_name` |
| `property_tags.py` | PropertyTag reading, control flags | `read_property_tag` `parse_ctrl_flags` |
| `graph.py` | UEdGraph/Node/Pin reading | `read_ue_graph` `read_ue_graph_node` `read_ue_graph_pin` |

## PackageIndex Encoding

- **Positive**: Export index (1-based)
- **Negative**: Import index (-1-based)
- **Zero**: Null reference

---

**Related sections**: [[Parsing Pipeline]] · [[Property Parser]] · [[Data Model]] · [[Object Linker]]
