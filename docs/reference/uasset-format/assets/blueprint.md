# 蓝图资产文档

蓝图资产类型 (UBlueprint/UBlueprintGeneratedClass) 相关文档导航。

## 子文档

| 文档 | 内容 | 说明 |
|------|------|------|
| [blueprint-source.md](blueprint-source.md) | 源资产结构 | UBlueprint 核心属性和字段 |
| [blueprint-compilation.md](blueprint-compilation.md) | 编译机制 | 蓝图编译流程和触发时机 |
| [blueprint-generated-class.md](blueprint-generated-class.md) | 生成类结构 | UBlueprintGeneratedClass 核心字段 |

## 核心源码

- Runtime/Engine/Classes/Engine/Blueprint.h — UBlueprint 主类定义
- Runtime/Engine/Classes/Engine/BlueprintGeneratedClass.h — 生成类定义
- Runtime/Engine/Private/Blueprint.cpp — 编译机制实现

## 相关文档

- [Import/Export 表结构](../import-export-tables.md) — 对象引用机制
- [属性序列化](../serialization/property-tag.md) — 属性存储结构