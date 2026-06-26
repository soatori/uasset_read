---
title: 测试指南
section: testing
---

# 测试指南

## 测试分层

```
tests/
├── 单元测试（无外部依赖，CI 每次运行）
├── 集成测试（@pytest.mark.integration，需要真实资产文件）
│   ├── test_real_asset_coverage.py    — 20+ 资产 / 10+ 类型
│   ├── test_engine_content.py         — Engine 内置资产
│   ├── test_known_failures.py         — 已知失败回归
│   ├── test_formatter_outputs.py      — 多资产 × 多格式化器
│   └── test_asset_type_depth.py       — 多类型深度字段验证
└── fixtures/                          — 已知失败记录
```

## 运行测试

```python
python -m pytest tests/ -v                                    # 单元测试
UE_SAMPLE_ROOT=/path python -m pytest tests/ -v -m integration # 集成测试
python -m pytest tests/ -v --cov=uasset_read                   # 覆盖率报告
```

## 覆盖率要求

- 核心解析模块覆盖率 **≥ 90%**
- 新增代码不得降低总体覆盖率
- 新功能必须配套至少一个单元测试
- 解析器变更需补充集成测试

## UE 5.8 MCP 实时真值对照

UE 5.8 已内置官方 Experimental Unreal MCP server。对声明“UE 保真”的变更，测试对照应在现有离线测试之外增加一层 Editor 实时真值采集，而不是只对照静态 C++ 参考或只跑 `pytest`。

### 适用范围

必须采集 MCP 真值的变更：

- Blueprint 变量、函数、图、节点、引脚、连接关系。
- `blueprint.components`、组件层级、相对 Transform、材质/网格引用。
- Enhanced Input / Input Action / Input Mapping Context 输出。
- SoftObjectPath、依赖图、资产类名、加载状态、编译状态。
- 声称修复真实样本输出缺失、错名、空字段或 UE 可见数据不一致的问题。

可不采集 MCP 真值的变更：

- 纯二进制 reader 边界检查、异常信息、内部工具函数。
- 无 Editor 可见状态的低层容器解析，例如 Pak/IoStore header 校验。
- 只影响输出排版且已有固定 fixture 覆盖的变更。

### 环境基线

本地 UE 5.8 安装基线：

- Engine: `D:\Program Files\Epic Games\Engine\UE_5.8`
- MCP server 插件: `Engine\Plugins\Experimental\ModelContextProtocol`
- MCP client/toolset 插件: `Engine\Plugins\Experimental\Toolsets\MCPClientToolset`
- Toolset 聚合插件: `Engine\Plugins\Experimental\Toolsets\AllToolsets`

官方 server 默认配置：

- URL: `http://127.0.0.1:8000/mcp`
- URL path: `/mcp`
- Port: `8000`
- `tools/list` 默认只暴露 `list_toolsets`、`describe_toolset`、`call_tool`
- Tool 调用运行在 game thread；只支持 HTTP / SSE，不支持 stdio 或 WebSocket
- 只应绑定 loopback；不要暴露到非本机网络

### 采集流程

1. 在测试项目中启用 `ModelContextProtocol`。需要现成工具集时同时启用 `AllToolsets`，重启 Editor。
2. 启动 server：在 Editor 控制台执行 `ModelContextProtocol.StartServer`，或用 `-ModelContextProtocolStartServer` 启动。
3. 连接 `http://127.0.0.1:8000/mcp`，先保存 `tools/list` 响应。
4. 调用 `list_toolsets`，保存运行时实际可用 toolset 名称。不要假设所有本地插件都已注册。
5. 对目标 toolset 调用 `describe_toolset`，保存 schema。
6. 用只读工具采集目标资产的 Editor 实时数据。若现有 toolset 不能覆盖字段，补项目专用只读 `UToolsetDefinition` 或 Python Toolset，不用可变更资产的通用脚本替代。
7. 运行 `python run.py <asset> --json` 和必要的 `--markdown` / `--cpp-skeleton`。
8. 对照 MCP 真值与解析器输出，记录差异分类。

### 对照字段准则

MCP 真值至少覆盖以下字段后，才能作为真实样本验收证据：

| 分类 | MCP 真值字段 | 解析器输出字段 |
|------|--------------|----------------|
| 资产身份 | package path、asset name、asset class、generated class | `summary.package_name`、`exports[].object_name`、`exports[].class_name` |
| Blueprint | variables、functions、graphs、compile/load status | `blueprint.variables`、`blueprint.functions`、`graphs`、`status` |
| 图结构 | graph name/guid、node title/class/guid、pin name/type/guid、links | `graphs[].nodes[]`、`pins[]`、`linked_to_raw` |
| 组件 | SCS/component name、class、parent、relative transform、key properties | `blueprint.components[]`、`transforms`、`properties` |
| 输入 | Input Action、trigger event、mapping context、bound function | Markdown Input Action 表、`blueprint.functions`、相关 properties |
| 引用 | soft object paths、materials、meshes、dependency package paths | `soft_object_path_list`、`imports`、`depends_map` |

### 通过/失败判定

- `P0`: MCP 可见且解析器输出缺失关键对象、组件 Transform 全空、图/引脚连接缺失、Input Action 绑定缺失，必须修复或标注为明确不支持。
- `P1`: 名称、枚举前缀、默认值、引用路径与 Editor 不一致，但结构仍可用，应建立 issue 或补测试。
- `P2`: 排序、展示字段、摘要层级与 Editor 不一致，可接受但需记录。

MCP 不可用时，相关测试必须 `skip` 或只生成“未采集”报告；不得把 Editor 未启动误判为解析器通过。MCP 采集结果也不能直接替代单元测试，修复后仍需补最小 fixture 或真实样本集成测试。

### 证据留存

每次真实样本验收应至少保存：

- UE 版本、插件启用列表、MCP endpoint、启动方式。
- `tools/list`、`list_toolsets`、目标 `describe_toolset` 响应。
- 目标资产路径和 Editor 采集 JSON。
- `run.py` 输出 JSON/Markdown。
- 差异表，明确 `editor-only stripped`、`cooked asset`、`unsupported parser field`、`parser defect` 四类原因之一。
