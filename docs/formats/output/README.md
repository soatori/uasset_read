# JSON 输出文档入口

> **状态：路由页。** 此处原先描述的旧 JSON renderer 与 package schema 已不是当前实现，也不是目标架构，因此旧字段说明已移除。

## 当前（v2）

三个入口（CLI 默认、Python API、Agent tool）共用同一 package-first `PackageDocument`，唯一顶层 format 为 `uasset_read.package`，`format_version: 2.0`：

- [Package-first UAsset parser refactor](../../designs/2026-08-26-package-first-uasset-parser-refactor.md)
- 实现：`src/uasset_read/v2/`（`projection.py` 决定顶层字段与 view/depth，`document.py` 定义 `PackageDocument`，`object_model.py` 定义 `ObjectRecord`/`ObjectStatus`）
- 每个 export 都保留在 `objects[]` 中，不存在单 primary export 选择。

## 已删除

Semantic JSON 1.x 与 v1 pipeline 已随 Phase 6 从 `src/` 删除，`src/uasset_read/semantic/` 不再存在；`--legacy-json` 等 retired flag 直接报错退出。[Semantic JSON 1.x 格式](../uasset/semantic-json.md) 仅作为 historical 格式记录保留，不得当作当前实现。
