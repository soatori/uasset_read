---
title: Property Parsers
section: parsers
---

# Property Parsers

`parsers/` contains **40+** property type parsers and dispatch mechanisms, covering basic types, integer variants, object references, composite types, special types, and Verse types.

<!-- data-api="parse_property_value" -->
```python
parse_property_value(archive, tag, name_map, ...) → PropertyValue
# Dispatch based on PropertyTag.type_name
```

## Supported Property Types

| Type | Parse Function | Description |
|------|----------------|-------------|
| `BoolProperty` | `parse_bool_property` | Boolean |
| `IntProperty` | `parse_int_property` | 32-bit integer |
| `FloatProperty` | `parse_float_property` | 32-bit floating point |
| `StrProperty` | `parse_str_property` | FString |
| `NameProperty` | `parse_name_property` | FName |
| `ObjectProperty` | `parse_object_property` | Object reference |
| `SoftObjectProperty` | `parse_soft_object_property` | Soft object reference |
| `ArrayProperty` | `parse_array_property` | Array |
| `StructProperty` | `parse_struct_property` | Struct |
| `MapProperty` | `parse_map_property` | Map |
| `SetProperty` | `parse_set_property` | Set |
| `EnumProperty` | `parse_enum_property` | Enum |
| `TextProperty` | `parse_text_property` | FText |
| `DelegateProperty` | `parse_delegate_property` | Delegate |
| `UInt16Property` | `parse_uint16_property` | 16-bit unsigned integer |
| `UInt32Property` | `parse_uint32_property` | 32-bit unsigned integer |
| `UInt64Property` | `parse_uint64_property` | 64-bit unsigned integer |
| `WeakObjectProperty` | `parse_weak_object_property` | Weak object reference |
| `LazyObjectProperty` | `parse_lazy_object_property` | Lazy-loaded object |
| `ClassProperty` | `parse_class_property` | Class reference |
| `SoftClassProperty` | `parse_soft_class_property` | Soft class reference |
| `AssetObjectProperty` | `parse_asset_object_property` | Asset object reference |
| `MulticastDelegateProperty` | `parse_multicast_delegate_property` | Multicast delegate |
| `MulticastInlineDelegateProperty` | `parse_multicast_inline_delegate_property` | Inline multicast delegate |
| `MulticastSparseDelegateProperty` | `parse_multicast_sparse_delegate_property` | Sparse multicast delegate |
| `FieldPathProperty` | `parse_field_path_property` | Field path |
| `InterfaceProperty` | `parse_interface_property` | Interface reference |
| `DoubleProperty` | `parse_double_property` | 64-bit floating point |
| `GuidProperty` | `parse_guid_property` | GUID |
| `OptionalProperty` | `parse_optional_property` | Optional property |
| `AnsiStrProperty` | `parse_ansi_str_property` | ANSI string |
| `Utf8StrProperty` | `parse_utf8_str_property` | UTF-8 string |
| `VerseStringProperty` | `parse_verse_string_property` | Verse string |
| `VerseClassProperty` | `parse_verse_class_property` | Verse class reference |
| `VerseFunctionProperty` | `parse_verse_function_property` | Verse function reference |
| `VerseDynamicProperty` | `parse_verse_dynamic_property` | Verse dynamic property |
| `VerseCellProperty` | `parse_verse_cell_property` | Verse cell |
| `VerseValueProperty` | `parse_verse_value_property` | Verse value type |

## Custom Property Registry

<!-- data-api="register_custom_property" -->
```python
register_custom_property(type_name: str, handler) → None
handle_custom_property(archive, tag, context) → PropertyValue
```

> [!TIP]
> When adding a new property type parser, register it with the dispatcher via `register_custom_property`.
>
> **Related Sections**: [[Serializers]] · [[Models]]
