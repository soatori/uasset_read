# Unknown Asset Handling Enhancements

日期：2026-06-04

## 概述

将未知 property/class 的处理从"返回 None 或跳过"升级为结构化 fallback，
降低信息丢失，为后续 class handler registry 扩展奠定基础。

## 变更

### 新增数据模型 (`models/fallback.py`)

- `PropertyFallback` — 未知/损坏 property 的结构化容器
- `StructFallback` — 未知 struct 的 fallback（参考 CUE4Parse FStructFallback）
- `GenericUObject` — 通用 UObject fallback（参考 CUE4Parse generic UObject）
- `ExportParseStatus` — export 级解析状态枚举
- `FallbackReason` — fallback 原因枚举

### Property 分派器改造

- 未知 property type 不再返回 `None`，而是返回 `PropertyFallback`
- 包含 raw bytes、reason、error_message 等诊断信息
- `PropertyValue.value` 现在可能为 `PropertyFallback` 实例

### Class Handler Registry

- 新增 `ClassHandlerRegistry` 支持精确 class handler 查找
- `ClassHandler` 抽象基类定义 `can_handle`/`parse`/`fallback_policy` 接口
- `FallbackPolicy` 枚举：GENERIC_UOBJECT / SKIP / RAISE / PROPERTY_FALLBACK
- 现有 skip list 改造为 registry 的 fallback policy 之一

### 公共 API

- `__all__` 新增: `PropertyFallback`, `StructFallback`, `GenericUObject`,
  `ExportParseStatus`, `FallbackReason`, `ClassHandlerRegistry`, `ClassHandler`,
  `HandlerResult`, `FallbackPolicy`, `get_class_registry`

## 兼容性

- 向后兼容：现有 `PropertyValue` 的 `value` 字段为 `Any` 类型
- Skipped/BinaryOrNative property 保持原有 dict 格式不变
- 所有现有测试通过

## 测试

- 新增 38 个单元测试（fallback 模型 8 个 + unknown property 6 个 + class registry 13 个 + error context 9 个 + API 2 个）
- 509 个现有测试全部通过
