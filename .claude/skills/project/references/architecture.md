# 核心架构

## 管线

```text
.uasset → FArchive → Serializers → Parsers → ParseResult
                                      ↓
                          IR Builder → PackageIR → JSON/Markdown Renderers
```

完整管线：`parse_package()` → `ParseResult` → `build_package_ir()` → `PackageIR` → `renderer.render(ir, options)`。渲染器只接收 IR，不访问 `ParseResult`。

## 关键模块

- `archive.py`：FArchive 二进制读取层；`parse_uasset.py`：解析入口。
- `core/__init__.py`：`parse_single`、`parse_batch`、`diff_single`，供 CLI 和脚本共用。
- `ir_builder.py`、`models/ir.py`、`models/result.py`：结果到 IR 的构建和模型。
- `objects/`：跨 export 的 UObject 注册与引用解析。
- `serializers/graph.py` → `graph/flow_builder.py` → `blueprint/` → `kismet/`：蓝图图与字节码链路。
- `cpp_gen/`：蓝图结果到 C++ 类骨架；`renderers/`：通过 `RENDERER_REGISTRY` 注册输出格式。

## 状态模型

- 包级：`success | partial | failed`
- Export 级状态必须通过 `validate_parse_status()`
- `strict` 遇警告停止，`tolerant`（默认）遇错继续并标记 `partial`
- `export_count > 300` 时自动跳过完整蓝图解析

## 重要函数

- `parse_single()` 返回格式化字符串，接受 `tolerant=True` 等参数
- `parse_package()` 返回 `ParseResult` 对象，可访问 errors/warnings 属性
- 批量测试应使用 `parse_package()` 以访问完整错误信息
