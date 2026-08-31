# Phase 6: 删除旧路径 — 迁移计划

status: target

> **状态：未开始。需要 Phase 5 完成 + 调用方迁移后执行。**

## 前置条件

- Phase 5 (Zen & Container Streaming) 完成
- 所有公共 API 调用方已切换到 v2 PackageDocument
- v2 测试覆盖 ≥ v1 同等覆盖

## 需要删除的旧路径

按依赖顺序从外到内删除：

### 1. 旧 Semantic 1.x 输出格式（最后删除）

| 路径 | 替代 | 删除条件 |
| ------ | ------ | ---------- |
| `semantic/builder.py` → `build_semantic_ir()` | v2 `PackageDocument` | 所有调用方切换到 v2 |
| `semantic/render.py` → `render_semantic_json()` | v2 `PackageDocument.to_dict()` | 同上 |
| `semantic/projection.py` → `project_semantic()` | v2 `projection.py` | 同上 |
| `semantic/validator.py` → `validate_semantic_document()` | v2 diagnostics | 同上 |
| `semantic/models.py` → `SemanticIR` 等 | v2 `document.py` + `object_model.py` | 同上 |

**注意**：`semantic/extensions.py` 中的 extractor 注册机制可以迁移到 v2 `handlers.py`，不是直接删除。

### 2. 旧 IR 层（Semantic 依赖）

| 路径 | 替代 | 删除条件 |
| ------ | ------ | ---------- |
| `ir_builder.py` → `build_package_ir()` | v2 adapter | Semantic 1.x 删除后 |
| `models/ir.py` → `PackageIR` / `ExportIR` | v2 `PackageDocument` / `ObjectRecord` | 同上 |
| `renderers/base.py` / `markdown_renderer.py` | v2 projection | 同上 |

### 3. 旧 Renderer 层

| 路径 | 替代 | 删除条件 |
|------|------|----------|
| `renderers/markdown_renderer.py` | v2 projection (raw view) | 如果不再需要 markdown 输出 |
| `renderers/__init__.py` | — | 清理 |

### 4. 旧单主资产逻辑

| 路径 | 替代 | 删除条件 |
|------|------|----------|
| `semantic/builder.py` → `_select_primary_export()` | v2 所有 exports 一等对象 | Phase 1 已绕过 |
| `core/__init__.py` → `_parse_and_render()` 中的 Semantic 管线 | v2 `parse_package_document()` | 调用方迁移后 |

### 5. 旧日志配置

| 路径 | 替代 | 删除条件 |
|------|------|----------|
| `project_logging.py` → `configure_project_logging()` | v2 diagnostics (不配置全局日志) | Phase 1 已绕过 |
| `core/__init__.py` → `_configure_logging()` | v2 不调用 | 同上 |

### 6. 旧 Compatibility Shim

| 路径 | 替代 | 删除条件 |
|------|------|----------|
| `core/__init__.py` → `parse_single()` 返回字符串 | v2 返回 PackageDocument | CLI 切换到 --v2 |
| `core/__init__.py` → `parse_batch()` 旧格式 | v2 batch API | 同上 |

## 不删除（保留为可选）

| 路径 | 原因 |
| ------ | ------ |
| `kismet/` | Blueprint/Kismet 扩展保留为可选能力 |
| `graph/` | Blueprint graph 分析保留 |
| `cpp_gen/` | C++ skeleton 生成保留 |
| `blueprint/` | Blueprint 组件提取保留 |
| `pak/` | Pak 读取保留（Phase 5 适配） |
| `iostore/` | IoStore 读取保留（Phase 5 适配） |
| `serializers/package_summary.py` | v2 LegacyPackageReader 仍使用 |
| `serializers/object_resources.py` | v2 LegacyPackageReader 仍使用 |
| `serializers/property_tags.py` | v2 property 读取仍使用 |
| `parsers/property_parser.py` | v2 property 读取仍使用 |

## 迁移检查清单

删除前必须确认：

- [ ] v2 测试覆盖所有旧路径的等价功能
- [ ] CLI `--v2` 输出与旧 `--json` 输出在语义上等价（不要求字节相同）
- [ ] Python API `parse_package_document()` 替代 `parse_single()`
- [ ] Agent tool 实现完成
- [ ] README 和 Wiki 中的示例全部更新为 v2 API
- [ ] 无外部调用方依赖旧 `SemanticIR` / `PackageIR` 类型

## 执行顺序

```
Phase 5 完成
  ↓
调用方迁移（CLI --v2、Python API、Agent tools）
  ↓
Phase 6 执行：
  1. 删除 semantic/ 旧路径（保留 extensions.py 中的 extractor 逻辑迁移到 handlers.py）
  2. 删除 ir_builder.py 和 models/ir.py
  3. 删除 renderers/ 旧路径
  4. 清理 core/__init__.py 中的旧管线
  5. 清理 project_logging.py
  6. 更新 pyproject.toml 的 exports
```
