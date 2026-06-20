# UE 5.8 Unreal MCP 快速配置

## 已完成的配置

✅ 创建了 `.mcp.json` 配置文件  
✅ 创建了完整的配置文档  
✅ 配置了 Claude Code 连接 UE 5.8 MCP 服务器  
✅ 准备了项目内 skill 源目录 `skills/ue-mcp/` 和运行时副本 `.claude/skills/ue-mcp/`

## 下一步操作

### 1. 在UE编辑器中启用插件

打开 UE 编辑器，转到 `Edit → Plugins`，搜索并启用：

- **Unreal MCP** (必需；源码和命令标识为 `ModelContextProtocol`)
- **ToolsetRegistry** (依赖插件，通常会自动启用)
- **EditorToolset** (推荐)
- **AutomationTestToolset** (用于测试自动化)
- **LiveCodingToolset** (用于实时编码)

重启UE编辑器使插件生效。

### 2. 启动MCP服务器

在UE编辑器输出日志中执行：

```cpp
ModelContextProtocol.StartServer
```

也可以在 `Editor Preferences → General → Model Context Protocol` 中启用 Auto Start。默认服务地址是 `http://127.0.0.1:8000/mcp`。

### 3. 生成客户端配置（可选）

如果需要重新生成配置：

```cpp
ModelContextProtocol.GenerateClientConfig ClaudeCode
```

支持的目标包括 `ClaudeCode`、`Cursor`、`VSCode`、`Gemini`、`Codex` 和 `All`。JSON 配置会与已有配置合并；Codex CLI 的 TOML 配置是 write-once，旧配置需要手动删除后再生成。

### 4. 重启Claude Code

关闭当前 Claude Code 会话，在项目根目录重新启动：

```bash
cd E:\Develop\uasset_read
claude
```

## 验证连接

连接成功后，您可以使用以下命令测试：

- `list_toolsets` - 列出当前编辑器实际暴露的工具集
- `describe_toolset`，例如 `editor_toolset.toolsets.scene.SceneTools` - 查看具体 Toolset 的工具 schema
- `call_tool`，例如 `toolset_name = editor_toolset.toolsets.scene.SceneTools` 且 `tool_name = get_current_level` - 用短工具名调用只读工具

## 常用工具

| 工具 | 用途 |
|------|------|
| `EditorToolset.EditorAppToolset` | 编辑器状态、视口、Content Browser、PIE |
| `editor_toolset.toolsets.scene.SceneTools` | 关卡、场景、Actor 查询与操作 |
| `editor_toolset.toolsets.blueprint.BlueprintTools` | Blueprint 图、变量、父类、CDO、Graph DSL |
| `AutomationTestToolset.AutomationTestToolset` | 自动化测试发现和执行 |
| `LiveCodingToolset.LiveCodingToolset` | 实时代码编译 |

## Skill 维护

- `skills/ue-mcp/` 是项目内可跟踪源目录。
- `.claude/skills/ue-mcp/` 是 Claude Code 运行时安装副本。
- 修改后对两个目录分别运行 `quick_validate.py`，并保持内容同步。

## 使用 skill

- 在 Claude Code 中显式使用 `/ue-mcp` 或 `$ue-mcp`，用于 UE MCP 连接、工具发现、编辑器只读检查、Blueprint 对照、日志诊断和安全执行编辑器任务。
- skill 被触发后，先确认 MCP 连接：`list_toolsets`。
- 选中 Toolset 后先读 schema：`describe_toolset <完整 Toolset 名>`。
- 调用工具时使用完整 `toolset_name` 加短 `tool_name`，例如 `toolset_name = editor_toolset.toolsets.scene.SceneTools`、`tool_name = get_current_level`。
- 写入场景、资产、插件配置、PIE、测试运行或 AgentSkill 资产前，先做只读查询并确认用户授权。

## 详细文档

完整的配置指南请查看：`docs/mcp-config/ue58-mcp-setup.md`

## 故障排除

如果遇到问题：

1. 检查UE编辑器输出日志
2. 确认插件已正确启用
3. 验证MCP服务器正在运行
4. 查看 `LogModelContextProtocol` 日志
5. 用 MCP Inspector 通过 Streamable HTTP 连接 `http://127.0.0.1:8000/mcp`
