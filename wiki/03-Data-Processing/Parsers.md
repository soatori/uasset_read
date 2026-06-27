---
title: 属性解析器
section: parsers
---

# 属性解析器

`parsers/` 包含 **40+** 种属性类型解析器和分发机制，涵盖基础类型、整型变体、对象引用、复合类型、特殊类型和 Verse 类型。

<!-- data-api="parse_property_value" -->
```python
parse_property_value(archive, tag, name_map, ...) → PropertyValue
# 根据 PropertyTag.type_name 分发
```

## 支持的属性类型

| 类型 | 解析函数 | 说明 |
|------|----------|------|
| `BoolProperty` | `parse_bool_property` | 布尔值 |
| `IntProperty` | `parse_int_property` | 32 位整数 |
| `FloatProperty` | `parse_float_property` | 32 位浮点 |
| `StrProperty` | `parse_str_property` | FString |
| `NameProperty` | `parse_name_property` | FName |
| `ObjectProperty` | `parse_object_property` | 对象引用 |
| `SoftObjectProperty` | `parse_soft_object_property` | 软对象引用 |
| `ArrayProperty` | `parse_array_property` | 数组 |
| `StructProperty` | `parse_struct_property` | 结构体 |
| `MapProperty` | `parse_map_property` | 映射 |
| `SetProperty` | `parse_set_property` | 集合 |
| `EnumProperty` | `parse_enum_property` | 枚举 |
| `TextProperty` | `parse_text_property` | FText |
| `DelegateProperty` | `parse_delegate_property` | 委托 |
| `UInt16Property` | `parse_uint16_property` | 16 位无符号整数 |
| `UInt32Property` | `parse_uint32_property` | 32 位无符号整数 |
| `UInt64Property` | `parse_uint64_property` | 64 位无符号整数 |
| `WeakObjectProperty` | `parse_weak_object_property` | 弱对象引用 |
| `LazyObjectProperty` | `parse_lazy_object_property` | 延迟加载对象 |
| `ClassProperty` | `parse_class_property` | 类引用 |
| `SoftClassProperty` | `parse_soft_class_property` | 软类引用 |
| `AssetObjectProperty` | `parse_asset_object_property` | 资产对象引用 |
| `MulticastDelegateProperty` | `parse_multicast_delegate_property` | 多播委托 |
| `MulticastInlineDelegateProperty` | `parse_multicast_inline_delegate_property` | 内联多播委托 |
| `MulticastSparseDelegateProperty` | `parse_multicast_sparse_delegate_property` | 稀疏多播委托 |
| `FieldPathProperty` | `parse_field_path_property` | 字段路径 |
| `InterfaceProperty` | `parse_interface_property` | 接口引用 |
| `DoubleProperty` | `parse_double_property` | 64 位浮点 |
| `GuidProperty` | `parse_guid_property` | GUID |
| `OptionalProperty` | `parse_optional_property` | 可选属性 |
| `AnsiStrProperty` | `parse_ansi_str_property` | ANSI 字符串 |
| `Utf8StrProperty` | `parse_utf8_str_property` | UTF-8 字符串 |
| `VerseStringProperty` | `parse_verse_string_property` | Verse 字符串 |
| `VerseClassProperty` | `parse_verse_class_property` | Verse 类引用 |
| `VerseFunctionProperty` | `parse_verse_function_property` | Verse 函数引用 |
| `VerseDynamicProperty` | `parse_verse_dynamic_property` | Verse 动态属性 |
| `VerseCellProperty` | `parse_verse_cell_property` | Verse 单元格 |
| `VerseValueProperty` | `parse_verse_value_property` | Verse 值类型 |

## 自定义属性注册表

<!-- data-api="register_custom_property" -->
```python
register_custom_property(type_name: str, handler) → None
handle_custom_property(archive, tag, context) → PropertyValue
```

> [!TIP]
> 新增属性类型解析器时，通过 `register_custom_property` 注册到分发器。
>
> **相关章节**: [[Serializers]] · [[Models]]
