# MCP 配置目录

本目录包含 UE 5.8 Unreal MCP（官方插件 friendly name；源码、命令和配置标识为 `ModelContextProtocol`）的配置和文档。

## 文件说明

- `ue58-mcp-setup.md` - 完整的 UE 5.8 MCP 配置指南
- `quick-start.md` - 当前项目的快速连接与只读验证步骤
- `../../.mcp.json` - 项目根目录的 MCP 服务器配置文件
- `../../skills/ue-mcp/` - 项目内可跟踪的 UE MCP skill 源目录
- `../../.claude/skills/ue-mcp/` - Claude Code 运行时安装副本

## 快速开始

1. 阅读 `ue58-mcp-setup.md` 了解详细配置步骤
2. 确保 UE 编辑器中已启用 Unreal MCP 和目标 Toolset 插件
3. 启动 MCP 服务器或启用 Auto Start
4. 从生成客户端配置的项目根目录重启 agent

## 配置文件位置

MCP 配置文件位于项目根目录：`E:\Develop\uasset_read\.mcp.json`。

JSON 格式客户端配置（Claude Code、Cursor、VS Code、Gemini）可以由 Unreal MCP 安全 merge。Codex CLI 的 TOML 配置是 write-once；如果配置过期，需要手动删除旧文件后再重新生成。

## Skill 维护位置

`skills/ue-mcp/` 是 canonical source，应该纳入版本控制；`.claude/skills/ue-mcp/` 是运行时安装副本。修改 skill 时先改 `skills/ue-mcp/`，再同步到 `.claude/skills/ue-mcp/` 并分别运行 quick_validate。

## Skill 使用入口

在 Claude Code 中用 `/ue-mcp` 或 `$ue-mcp` 触发该 skill。适用场景包括连接 Unreal MCP、确认工具集、选择 Toolset、只读检查编辑器状态、对照 Blueprint 结构、查看 UE 日志、运行明确授权的编辑器工具调用。

## 支持的工具集

- **EditorToolset** - 编辑器自动化、场景/Actor/资产/蓝图等子工具
- **AutomationTestToolset** - 测试自动化
- **LiveCodingToolset** - 实时编码
- **PluginToolset** - 插件管理
- **ConfigSettingsToolset** - 配置管理

## 故障排除

如果遇到问题，请查看：
1. UE编辑器输出日志
2. `LogModelContextProtocol` 日志类别
3. `ue58-mcp-setup.md` 中的故障排除部分
4. MCP Inspector，使用 Streamable HTTP 连接 `http://127.0.0.1:8000/mcp`
