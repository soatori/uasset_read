---
title: Agent Quick Reference Index
section: agent-index
---

# Agent Quick Reference Index

> [!NOTE]
> This document has been optimized for AI Agents. All tables use structured formats, and API signatures are annotated with `data-api` comments. Agents can locate APIs by grepping `<!-- data-api="function_name" -->`.
>
> **0.4.1 Changes**: `exporter/`, `n2c/`, `agent/` modules have been removed. New additions: `core.py` (parse_single/parse_batch), `renderers/`, `models/ir.py`.
> **0.5.0 Changes**: `formatters/` directory has been emptied; all formatting functionality has migrated to the `renderers/` system.
> **0.5.1.19 Changes**: New `--full-parse`, `--hex-view` CLI flags; new AnimDataModel/SoundAttenuation asset type parsers.

## Quick Navigation by Task Type

| Agent Task | Section | Key Files |
|------------|---------|-----------|
| Parse .uasset file | [[Parsing Pipeline]] | `parse_uasset.py` / `core.py` |
| Read binary fields | [[FArchive]] | `archive.py` |
| Add new property type parser | [[Property Parsers]] | `parsers/` |
| Modify blueprint output format | [[Blueprint Parsing]] | `blueprint/` |
| Modify graph analysis logic | [[Graph Analysis]] | `graph/` |
| Fix Kismet decompilation | [[Kismet Decompilation]] | `kismet/` |
| Modify C++ code generation | [[C++ Code Generation]] | `cpp_gen/` |
| Add new output format | [[Renderer System]] | `renderers/` |
| Version compatibility adaptation | [[Version Management]] | `versioning.py` |
| Cross-package reference fixes | [[Object Linker]] | `link/` |
| PAK/IoStore container support | [[PAK]] / [[IoStore]] | `pak/` / `iostore/` |
| Add test cases | [[Testing Guide]] | `tests/` |
| Compare with UE source code | [[UE Source Comparison]] | `docs/formats/uasset/` |

> [!WARNING] Removed Tasks
> - ~~N2C Schema changes~~ → `n2c/` has been completely removed
> - ~~Add new export format (old)~~ → Use [[Renderer System]] instead
> - ~~Formatter-related~~ → `formatters/` has been emptied; functionality migrated to `renderers/`

## Complete API Classification Index

### Parsing Entry Points (3)

<!-- data-api="parse_package" -->
| Function | Description |
|----------|-------------|
| `parse_package` | Standard package parsing entry point, supports provider abstraction |
| `parse_uasset` | Delegates to parse_package, backward compatible |
| `parse_uasset_with_linker` | Full parsing with object graph linker |

### Property Parsers (38+)

#### Basic Types
`parse_bool_property` · `parse_int_property` · `parse_float_property` · `parse_double_property` · `parse_str_property` · `parse_name_property` · `parse_utf8_str_property` · `parse_ansi_str_property` · `parse_guid_property`

#### Integer Variants
`parse_uint16_property` · `parse_uint32_property` · `parse_uint64_property`

#### Object References
`parse_object_property` · `parse_soft_object_property` · `parse_weak_object_property` · `parse_lazy_object_property` · `parse_class_property` · `parse_soft_class_property` · `parse_asset_object_property` · `parse_interface_property` · `parse_field_path_property`

#### Compound Types
`parse_array_property` · `parse_struct_property` · `parse_map_property` · `parse_set_property` · `parse_enum_property`

#### Special Types
`parse_text_property` · `parse_delegate_property` · `parse_multicast_delegate_property` · `parse_multicast_inline_delegate_property` · `parse_multicast_sparse_delegate_property` · `parse_optional_property`

#### Verse Types
`parse_verse_string_property` · `parse_verse_class_property` · `parse_verse_function_property` · `parse_verse_dynamic_property` · `parse_verse_cell_property` · `parse_verse_value_property`

### Blueprint & Graph (17+)

#### Blueprint Metadata
`extract_blueprint_metadata` · `extract_blueprint_variables` · `extract_components` · `parse_component_transform` · `extract_component_transforms` · `read_blueprint_variable` · `parse_property_flags_to_labels`

#### Graph Extraction
`extract_blueprint_graphs` · `build_execution_flow_entries` · `build_data_flows` · `build_connections_map` · `build_execution_chains` · `format_graphs_json` · `format_pin_ref`

#### Graph Formatting
`build_function_graphs`

### Kismet Decompilation (11+)

#### Extraction
`extract_bytecode_bytes` · `parse_bytecode_stream` · `extract_and_parse` · `FKismetArchive` · `EXPR_CLASS_MAP`

#### Translation
`KismetTranslator` · `MathFunctionCleaner` · `TypeRegistry` · `line_cpp` · `FunctionBodyBuilder` · `StructuredControlFlow`

#### Pipeline
`decompile_uasset` · `decompile_single_function` · `KismetDecompiledResult`

### Serialization (18+)

#### Summary
`read_package_summary` · `read_name_table` · `build_version_container`

#### Import/Export
`read_import_map` · `read_export_map` · `resolve_class_name` · `get_asset_class` · `detect_blueprint` · `resolve_parent_class` · `get_asset_class_with_linker` · `resolve_class_name_with_linker` · `detect_blueprint_with_linker` · `resolve_parent_class_with_linker` · `build_imports_list`

#### PropertyTag
`read_property_tag` · `parse_ctrl_flags` · `parse_ue511_ctrl_flags`

#### Graph Serialization
`read_ue_graph` · `read_ue_graph_node` · `read_ue_graph_pin` · `read_ed_graph_pin_type` · `read_fmember_reference` · `create_node_from_archive`

#### Safety
`detect_circular_deps` · `validate_package_index`

### Formatting & Rendering (0.4.1+)

#### Core API
`parse_single` · `parse_batch` · `list_formats` · `BatchResult`

#### Renderer System
`IRenderer` · `RenderOptions` · `get_renderer` · `list_formats` · `register_renderer` · `RENDERER_REGISTRY`

#### Renderer Implementations
`JSONRenderer` · `MarkdownRenderer`

#### Formatters (Deprecated)
`format_json_full` · `format_json_summary` · `format_text_full` · `format_markdown` · `format_blueprint_translation_text` · `format_blueprint_ue_text`
> [!WARNING] Deprecated
> The above functions are still exported via the root package for backward compatibility, but new code should use `parse_single()` or the renderer system.

### C++ Code Generation (15+)

#### IR
`CppClassIR` · `CppProperty` · `CppMethodIR` · `CppHeaderMeta` · `CppCallParameter` · `CppCallStatement`

#### Extraction
`extract_cpp_class_skeleton` · `extract_cpp_constructor` · `extract_cpp_functions`

#### Formatting
`format_cpp_header` · `format_cpp_class_json` · `format_cpp_call_statements` · `format_cpp_default_value` · `format_cpp_transform` · `format_cpp_component_init` · `format_cpp_input_action_load` · `format_cpp_constructor` · `build_constructor_sections`

#### Type Mapping
`ue_path_to_cpp_type` · `ue_package_path_to_cpp_class` · `cpf_flags_to_uproperty_marks` · `UE_TO_CPP_TYPE_MAP` · `ENGINE_CLASS_PATHS` · `CPF_TO_UPROPERTY_MAP`

### Containers & Raw Files (12+)

#### PAK
`PakFileReader` · `FPakInfo` · `FPakEntry` · `FPakDirectoryEntry` · `FPakCompressedBlock` · `decompress_block` · `decompress_entry` · `read_fstring`

#### IoStore
`IoStoreReader` · `FIoChunkId` · `FIoOffsetAndSize`

#### Raw Files
`parse_raw_file` · `parse_json_descriptor` · `parse_ini_file` · `parse_locres` · `parse_locmeta` · `parse_audio_metadata`

### Version Management (3)

<!-- data-api="VersionContainer" -->
| Function/Class | Description |
|----------------|-------------|
| `VersionContainer` | Unified version query data class |
| `build_version_container` | Built from Summary |
| `EUEVersion` | UE version threshold enum |

### Linker (3)

<!-- data-api="PackageLinker" -->
| Function/Class | Description |
|----------------|-------------|
| `PackageLinker` | Two-phase object graph reconstruction |
| `UObjectInstance` | Lightweight UE object representation |
| `LinkerParseResult` | Full link parsing result |

### Package Management (7)

<!-- data-api="PackageBundle" -->
| Function/Class | Description |
|----------------|-------------|
| `PackageBundle` | Package bundle data class |
| `PackageArchive` | Virtual archive (.uasset + .uexp merged) |
| `PackageProvider` | Provider base class |
| `FileSystemPackageProvider` | File system provider |
| `PakPackageProvider` | PAK container provider |
| `IoStorePackageProvider` | IoStore container provider |
| `open_package_bundle` | Factory function |

### Utility Parsers (6)

<!-- data-api="parse_default_value" -->
| Function | Description |
|----------|-------------|
| `parse_default_value` | Parse default value |
| `format_variable_type` | Format variable type string |
| `get_struct_size` | Get struct size |
| `resolve_name_from_index` | Resolve name from index |
| `read_validated_count` | Read validated count |
| `make_enum_value` | Create enum value |
