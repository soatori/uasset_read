# uasset_read

Python 工具读取 Unreal Engine .uasset 文件（未烘焙蓝图），让 AI agent 直接解析内容。

**技术栈**: Python 3.10+，零运行时依赖 | **架构**: `.uasset → FArchive → 序列化 → 数据模型 → 属性解析 → 蓝图图 → 格式化输出`

**源码参考**: `E:\Develop\lib\UnrealEngine` (UE 5.7，只读)

## 里程碑

| 版本 | 范围 | 日期 |
|------|------|------|
| v1.0 | MVP | 2026-04-28 |
| v2.0 | 蓝图图解析 | 2026-05-02 |
| v5.1 | src layout + pyproject.toml | 2026-05-07 |
| v6.0 | ✅ 模块化重构 | 2026-05-13 |
| **v7.0** | 📋 UE FLinkerLoad 对象图重建 + 技术债清理 | 规划中 |

**历史**: [archive/v6.0-refactor/](archive/v6.0-refactor/ARCHIVE-INDEX.md) | **详情**: [ROADMAP.md](ROADMAP.md)

## Out of Scope

导出纹理/模型 | 修改 .uasset | Cooked 资产 | 蓝图字节码反编译 | C++ 代码生成 | MCP Server

## 技术债

- **Phase 44a**: 移除旧版本/UE4 兼容代码
- **Phase 44b**: 替换直接字节读取为 FArchive 方法
- **Phase 44c**: 清理废弃测试工具

## 关键决策

零依赖 ✓ | 参考 UE 源码 ✓ | JSON 优先 ✓ | FArchive 管道模式 ✓ | v7.0 增量采用 ✓

## v7.0 架构

```
src/uasset_read/
├── archive.py          # FArchive 二进制读取（不变）
├── link/               # NEW: linker.py, object_instance.py, result.py
├── serializers/        # Package/Import/Export/PropertyTag
├── models/             # dataclasses (+UObjectInstance 引用)
├── parsers/            # 属性类型解析器
├── blueprint/          # 元数据提取
├── graph/              # 图解析 (+linker 变体)
├── formatters/         # JSON/Text/Markdown
└── cli.py              # CLI 入口
```

*Updated: 2026-05-14*
