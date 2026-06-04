# Agent 开发参考文档索引

> 本文档面向 AI Agent（Claude Code / 其他 LLM Agent），提供快速查阅 uasset_read 项目开发文档的索引。

## 核心参考

| 文档 | 路径 | 说明 |
|------|------|------|
| **开发指南** | `docs/guides/dev-guide.md` | 完整开发指南，解析管线、模块结构、测试要求 |
| 项目配置 | `CLAUDE.md` | Agent 会话级指令：语言、架构概览、测试规则、开发命令、关键约束 |
| 格式文档 | `docs/formats/uasset/` | 60+ 个 Markdown 文件，UE .uasset 格式详解，`Index.md` 为主入口 |

## 开发指南速查

打开 `docs/guides/dev-guide.md` 后，按以下方式快速定位：

### 按任务定位

| 你要做什么 | 跳转章节 |
|------------|----------|
| 解析 .uasset 文件 | [解析管线](../guides/dev-guide.md#架构) |
| 读取二进制字段 | [FArchive](../guides/dev-guide.md#模块结构) |
| 新增属性类型解析器 | [属性解析器](../guides/dev-guide.md#模块结构) |
| 修改蓝图输出格式 | [蓝图解析](../guides/dev-guide.md#模块结构) |
| 修改图分析逻辑 | [图分析](../guides/dev-guide.md#模块结构) |
| 修复 Kismet 反编译 | [Kismet 反编译](../guides/dev-guide.md#模块结构) |
| 修改 C++ 代码生成 | [C++ 代码生成](../guides/dev-guide.md#模块结构) |
| 新增导出格式 | [导出系统](../guides/dev-guide.md#模块结构) |
| 对照 UE 源码 | [UE 源码对照](../guides/dev-guide.md#外部参考) |
| 添加测试用例 | [测试指南](../guides/dev-guide.md#测试) |

### 按 API 分类定位

| API 分类 | 章节 | 符号数量 |
|----------|------|----------|
| 解析入口 | [解析管线](../guides/dev-guide.md#架构) | 3 |
| 属性解析器 | [属性解析器](../guides/dev-guide.md#模块结构) | 40+ |
| 蓝图与图 | [蓝图解析](../guides/dev-guide.md#模块结构) / [图分析](../guides/dev-guide.md#模块结构) | 20+ |
| Kismet 反编译 | [Kismet 反编译](../guides/dev-guide.md#模块结构) | 8+ |
| 序列化 | [序列化模块](../guides/dev-guide.md#模块结构) | 12+ |
| 格式化与导出 | [格式化器](../guides/dev-guide.md#模块结构) / [导出系统](../guides/dev-guide.md#模块结构) | 12+ |
| C++ 代码生成 | [C++ 代码生成](../guides/dev-guide.md#模块结构) | 10+ |
| 容器 | [PAK](../guides/dev-guide.md#模块结构) / [IoStore](../guides/dev-guide.md#模块结构) | 8+ |
| N2C 中间格式 | [N2C 中间格式](../guides/dev-guide.md#模块结构) | 8+ |
| Agent 管线 | [Agent 速查索引](../guides/dev-guide.md#模块结构) | 4 |

### Agent 解析提示

HTML 文档包含以下结构化标记，可直接 grep 提取：

- `data-api="函数名"` — 所有 API 签名块（33 个）
- `data-section="章节id"` — 所有 section 标签（29 个）
- `data-related="true"` — 相关章节交叉引用（11 组）
- `class="api-sig"` — API 签名块，内含函数名、参数、返回值
- `class="dep-tree"` — 依赖树，monospace 文本格式
- `class="nav-link"` — 侧边栏导航链接
- `<table>` — 所有表格，结构：第 1 列 = 键/名称，第 2 列 = 值/函数，第 3 列 = 说明

## 外部参考

| 资源 | 路径/链接 | 说明 |
|------|-----------|------|
| UE 格式文档 | `docs/formats/uasset/Index.md` | 60+ Markdown 文件，主索引 |
| CUE4Parse C# 参考 | `external/CUE4Parse/` | 交叉验证解析逻辑 |
| 蓝图节点参考 | `docs/reference/Blueprint_Node_Text_Reference.md` | 节点文本格式参考 |
| UE 加载流程 | `docs/reference/UE_uasset_Loading_Flow.md` | UE 内部 uasset 加载流程 |
| 蓝图转 C++ 指南 | `docs/reference/blueprint-to-cpp-guide.md` | 蓝图→C++ 转换指南 |

## 约束速记

- **仅未烘焙资产** — Cooked 资产图数据已剥离
- **只读** — 不支持修改/写入
- **零依赖** — 不向 `dependencies` 添加第三方包
- **参考 UE 源码** — 格式理解必须追溯 UE C++ 源码

## 工作规范

- 临时文件放 `temp/` 目录，不放项目根目录
- 代码注释使用中文，错误提示使用中文
- 新功能必须配套至少一个单元测试
- 核心模块覆盖率 ≥ 90%
