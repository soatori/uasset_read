# JSON 输出文档入口

> **状态：路由页。** 此处原先描述的旧 JSON renderer 与 package schema 已不是当前实现，也不是目标架构，因此旧字段说明已移除。

## 当前（v4）

三个入口（CLI 默认、Python API、Agent tool）共用同一 package-first `PackageDocument`，唯一顶层 format 为 `uasset_read.package`，`format_version: 4.0`（2026-09-28 v4 amendment，冻结契约见 [`package_document_v4.schema.json`](../../designs/contract/package_document_v4.schema.json)）：

- [Package-first UAsset parser refactor](../../designs/2026-08-26-package-first-uasset-parser-refactor.md) — Output Contract 以 `format_version: "4.0"` 为唯一目标；恰好 `normal`/`debug` 两个模式，每输入包一份完整文档，无分页/字节预算层
- 实现：`projection.py` 决定顶层字段与 `mode`（`FORMAT_VERSION = "4.0"`），`models/document.py` 定义 `PackageDocument`，`models/object_model.py` 定义 `ObjectRecord`/`ObjectStatus`，`parsers/legacy_reader.py` 为 Legacy reader
- 每个 export 都保留在 `objects[]` 中，不存在单 primary export 选择。

历史：`format_version: "2.0"` 的 stable-envelope 冻结（S1）与 v3 契约均已淘汰（v3 契约文件已在 v4 冻结时删除），归档于 [`docs/designs/archive/2026-08-31-v2-contract-stability.md`](../../designs/archive/2026-08-31-v2-contract-stability.md)。

## 已删除

Semantic JSON 1.x 与 v1 pipeline 已随 Phase 6 从 `src/` 删除，`src/uasset_read/semantic/` 不再存在；`--legacy-json` 等 retired flag 直接报错退出。[Semantic JSON 1.x 格式](../uasset/semantic-json.md) 仅作为 historical 格式记录保留，不得当作当前实现。
