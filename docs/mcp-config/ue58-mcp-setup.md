# UE 5.8 Unreal MCP 配置指南

## 概述

本指南帮助您为 UE 5.8 项目配置 Unreal MCP 服务器，以便通过 Claude Code 或其他 MCP 客户端控制 UE 编辑器。官方文档和插件浏览器中的 friendly name 是 **Unreal MCP**；源码、控制台命令、C++ 符号和设置项使用 `ModelContextProtocol`。

## 前置条件

- UE 5.8 已安装
- Claude Code CLI 或其他 MCP 兼容客户端已安装
- 项目已打开在UE编辑器中

## 配置步骤

### 步骤1：在UE编辑器中启用插件

1. 打开UE编辑器
2. 转到 `Edit → Plugins`
3. 搜索并启用以下插件：
   - **Unreal MCP** - 核心 MCP 服务器（内部标识为 `ModelContextProtocol`）
   - **ToolsetRegistry** - 工具集注册表，Unreal MCP 依赖它，通常会自动启用
   - **EditorToolset** - 编辑器工具集（推荐）
   - **AutomationTestToolset** - 自动化测试工具集（可选）
   - **LiveCodingToolset** - 实时编码工具集（可选）

4. 重启UE编辑器使插件生效

### 步骤2：启动MCP服务器

在UE编辑器中打开输出日志（`Window → Output Log`），执行以下控制台命令：

```cpp
// 启动MCP服务器（默认端口8000）
ModelContextProtocol.StartServer

// 或指定端口
ModelContextProtocol.StartServer 8000
```

也可以在 `Edit → Editor Preferences → General → Model Context Protocol` 中启用 Auto Start Server。默认端点是 `http://127.0.0.1:8000/mcp`，默认 port 是 `8000`，默认 path 是 `/mcp`。

验证服务器启动成功：
```cpp
// 检查服务器状态
ModelContextProtocol.RefreshTools
```

### 步骤3：生成客户端配置

在UE编辑器输出日志中执行：

```cpp
// 为 Claude Code 生成配置
ModelContextProtocol.GenerateClientConfig ClaudeCode

// 或为所有支持的客户端生成配置
ModelContextProtocol.GenerateClientConfig All
```

此命令会在项目根目录生成客户端配置文件。支持的客户端名称包括 `ClaudeCode`、`Cursor`、`VSCode`、`Gemini`、`Codex` 和 `All`。

JSON 格式配置（Claude Code、Cursor、VS Code、Gemini）会与已有配置合并，因此可重复生成。Codex CLI 的 TOML 配置是 write-once，命令不会覆盖已有文件；如配置过期，需要手动删除旧文件后再生成。

### 步骤4：验证配置

1. 检查项目根目录是否存在 `.mcp.json` 文件
2. 文件内容应类似：

```json
{
  "mcpServers": {
    "unreal-mcp": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp",
      "description": "UE 5.8 Unreal MCP Server"
    }
  }
}
```

### 步骤5：重启Claude Code

1. 关闭当前Claude Code会话
2. 在项目根目录重新启动Claude Code
3. MCP 服务器将自动连接

必须从生成客户端配置的项目或工作区根目录启动 agent，否则客户端可能找不到 Unreal MCP 配置。

## 可用工具集

配置成功后，您可以通过以下工具集控制UE编辑器：

| 工具集 | 用途 |
|--------|------|
| `EditorToolset.EditorAppToolset` | 编辑器状态、视口、选择、Content Browser、PIE |
| `editor_toolset.toolsets.*` | Actor、场景、资产、材质、蓝图、表格、网格体等子工具 |
| `AutomationTestToolset.AutomationTestToolset` | 自动化测试发现和执行 |
| `LiveCodingToolset.LiveCodingToolset` | 实时编码编译 |
| `PluginToolset` | 插件管理 |
| `ConfigSettingsToolset` | 配置设置管理 |

UE 5.8 默认使用 Tool Search 模式：先 `list_toolsets`，再 `describe_toolset`，最后通过 `call_tool` 调用。当前 MCP 包装器中，`toolset_name` 使用完整 Toolset 名，`tool_name` 使用短工具名，例如 `toolset_name = editor_toolset.toolsets.scene.SceneTools`、`tool_name = get_current_level`。

## 常用控制台命令

| 命令 | 用途 |
|------|------|
| `ModelContextProtocol.StartServer [port]` | 启动MCP服务器 |
| `ModelContextProtocol.StopServer` | 停止MCP服务器 |
| `ModelContextProtocol.RefreshTools` | 刷新工具列表 |
| `ModelContextProtocol.GenerateClientConfig <Client>` | 生成客户端配置 |

## 命令行参数

| 参数 | 用途 |
|------|------|
| `-ModelContextProtocolStartServer` | 编辑器或 commandlet 启动时强制启动服务器 |
| `-ModelContextProtocolPort=N` | 覆盖监听端口，合法范围 `1..65535` |

## Skill 维护路径

项目内 UE MCP skill 的 canonical source 是 `skills/ue-mcp/`，Claude Code 运行时副本是 `.claude/skills/ue-mcp/`。修改 skill 时先更新源目录，再同步到运行时副本，并分别运行 skill 校验。

## 故障排除

### 服务器无法启动

1. 检查插件是否正确启用
2. 查看输出日志中的错误信息
3. 确认端口8000未被占用

### 工具不可用

1. 执行 `ModelContextProtocol.RefreshTools` 刷新工具列表
2. 检查对应的Toolset插件是否启用
3. 查看 `LogModelContextProtocol` 日志

### 连接失败

1. 确认MCP服务器正在运行
2. 检查防火墙设置
3. 验证 `.mcp.json` 配置文件内容
4. 确认 agent 从生成配置的项目根目录启动

## 安全注意事项

- MCP 服务器默认仅监听本地回环地址（127.0.0.1）
- Unreal MCP 仅支持 HTTP/SSE，不支持 stdio 或 WebSocket
- Unreal MCP 没有认证层，不要暴露到本机之外
- Tool 调用会同步到 Unreal game thread 串行执行，不要发起相互依赖的重叠调用
- 定期更新UE版本以获取安全补丁

## 参考资源

- [Epic UE 5.8 Unreal MCP 文档](https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor?lang=en-US)
- [Unreal Engine 5.8 发布公告](https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available)
- [EpicGames unreal-mcp 技能](https://raw.githubusercontent.com/EpicGames/unreal-engine-skills-for-claude-code-plugin/main/skills/unreal-mcp/SKILL.md)
