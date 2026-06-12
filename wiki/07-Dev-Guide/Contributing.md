---
title: 开发规范
section: contributing
---

# 开发规范

## 代码风格

- **Python 版本**: 3.10+，使用 `match/case`、类型注解
- **代码注释**: 使用中文
- **错误提示**: 使用中文
- **文档格式**: 统一使用中文 Markdown 格式
- **布局规范**: 遵循 src 布局（`src/uasset_read/`）

## 项目结构

解析器镜像 UE 内部的 `FArchive` 序列化管线：

```
.uasset → FArchive → Deserializer → Models → IR Builder → Renderers → Output
                ↓
          GraphParser · BlueprintParser · DependencyGraphBuilder
          PackageLinker · KismetDecompiler · PakFileReader
          IR Builder → Renderers
```

### 模块职责

| 模块 | 路径 | 职责 |
|------|------|------|
| FArchive | `archive.py` | 二进制读取器，支持字节交换、mmap |
| 常量 | `constants.py` | 版本号、属性类型阈值、CPF/PropertyTag 标志 |
| 异常 | `exceptions.py` | `UAssetError`、`VersionError`、`ParseError`、`ErrorContext` |
| 主解析器 | `parse_uasset.py` | `parse_package()`、`parse_uasset()` 入口 |
| 包管理 | `package.py` | `PackageBundle`、`PackageProvider`（文件系统/Pak/IoStore） |
| 序列化 | `serializers/` | `PackageFileSummary`、`ImportMap`、`ExportMap`、`PropertyTag` |
| 数据模型 | `models/` | `UEdGraph/Node/Pin`、属性值模型、`ParseResult`、IR 中间表示 |
| 属性解析器 | `parsers/` | 40+ 种属性类型解析器 + 分发器 + 自定义属性注册表 |
| 蓝图 | `blueprint/` | 变量/变换/组件/元数据提取 |
| 图分析 | `graph/` | 执行流/数据流追踪、链构建器、Pin 追踪报告 |
| Kismet | `kismet/` | 字节码提取器、`EExprToken` → AST → C++ 翻译器 |
| 链接器 | `link/` | `PackageLinker` 两阶段对象图重建 |
| PAK | `pak/` | `FPakInfo/PakEntry`、`PakFileReader`、AES 解密 |
| IoStore | `iostore/` | IoStore 容器读取器、Chunk ID、偏移/大小结构 |
| IR | `ir_builder.py`、`models/ir.py` | 包级中间表示构建器 |
| 渲染器 | `renderers/` | 可插拔 `IRenderer` ABC + 格式注册表（5 种渲染器） |

## 临时文件

> [!IMPORTANT]
> 临时文件必须放在 `temp/` 目录下，禁止放在项目根目录。根目录只保留项目源码、配置文件和文档。

## Git 工作流

- **开发分支**: `0.4.5-dev`（随版本更新）
- **主分支**: `master`
- **提交前**: 运行 `python -m pytest tests/ -v` 确保测试通过
- **PR 要求**: 包含测试覆盖

## 依赖管理

- **运行时依赖**: 零依赖
- **PAK 支持**: AES 解密需要 `cryptography`，LZ4/Zstd 解压需要 `lz4`/`zstandard`（均为可选）
- **禁止添加**: 不要向主 `dependencies` 添加第三方包

## 开发命令

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行测试并生成覆盖率报告
python -m pytest tests/ -v --cov=uasset_read

# 仅运行集成测试
python -m pytest tests/ -v -m integration
```

## CodeGraph 使用规范

本项目使用 CodeGraph MCP 服务器进行代码智能检索。

| 问题 | 工具 |
|------|------|
| "X 在哪里定义？" | `codegraph_search` |
| "谁调用了 Y？" | `codegraph_callers` |
| "Y 调用了什么？" | `codegraph_callees` |
| "X 如何到达 Y？" | `codegraph_trace` |
| "改了 Z 会影响什么？" | `codegraph_impact` |
| "看 Y 的签名/源码" | `codegraph_node` |
| "一次性看多个相关符号" | `codegraph_explore` |
| "获取某任务/区域的上下文" | `codegraph_context` |

**使用原则：**
- 回答结构化问题先用 `codegraph_context`，再用一次 `codegraph_explore` 获取源码
- 追踪调用链用 `codegraph_trace`（一次调用返回完整路径）
- 不要对已确认的 codegraph 结果再用 grep 验证
- 索引延迟时读具体文件而非猜测

## 外部参考

- `docs/formats/uasset/` — UE .uasset 格式文档（60+ 个 Markdown 文件）
- `external/CUE4Parse/` — 参考 C# 实现，用于交叉验证解析逻辑
- `docs/reference/` — 蓝图节点文本参考、UE 加载流程、CUE4Parse 对照索引

## 关键约束

> [!WARNING]
> - **仅支持未烘焙/编辑器保存的资产**: Cooked 资产的图数据已被剥离
> - **只读**: 仅解析，不支持修改或写入
> - **必须参考 UE 源码**: 格式理解必须追溯到 UE C++ 源码，禁止猜测二进制格式
