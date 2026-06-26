---
title: 格式化器
section: formatters
---

# 格式化器 (Formatters)

> [!WARNING] 已废弃
>
> `formatters/` 目录在 v0.5.0 后已清空，所有格式化功能已迁移到 `renderers/` 系统。本文档保留作为历史参考。

## 废弃说明

在 0.4.1 的 IR 架构中，格式化器被渲染器内部调用。当前版本中，`formatters/` 目录已无 Python 文件，所有输出格式化逻辑已完全迁移到渲染器系统。

**推荐使用**：
- `parse_single(format="json")` — JSON 输出
- `parse_single(format="markdown")` — Markdown 输出
- `get_renderer("json")` / `get_renderer("markdown")` — 直接使用渲染器

**相关章节**: [[渲染器系统]] · [[CLI 接口]]