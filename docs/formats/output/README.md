# JSON 输出文档入口

> **状态：路由页。** 此处原先描述的旧 JSON renderer 与 package schema 已不是当前实现，也不是目标架构，因此旧字段说明已移除。

## 当前 v0.5.5

当前默认 JSON 使用 Semantic 1.x：

- [Semantic JSON 1.x 格式](../uasset/semantic-json.md)
- 实现：`src/uasset_read/semantic/`
- 注意：当前实现选择单个 primary export，不能作为多资产目标模型。

## 目标 v2

目标使用 package-first `PackageDocument`、`objects[]`、对象关系和分层 view/depth：

- [Package-first UAsset parser refactor](../../designs/2026-08-26-package-first-uasset-parser-refactor.md)

目标设计尚未实现。验证当前输出时必须读取源码和测试，不能从目标示例推断 CLI 已支持相关字段。
