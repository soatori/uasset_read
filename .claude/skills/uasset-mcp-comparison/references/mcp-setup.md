# MCP 配置参考

## 快速配置

### 使用配置脚本

```bash
python "C:\Users\cbsjz\.config\mimocode\skills\unreal-mcp\scripts\configure-unreal-mcp.py" \
    -ProjectPath "path/to/project" \
    -Target claude
```

### 手动配置

1. **.uproject 插件配置**
```json
{
  "Plugins": [
    {"Name": "ModelContextProtocol", "Enabled": true, "TargetAllowList": ["Editor"]},
    {"Name": "ToolsetRegistry", "Enabled": true, "TargetAllowList": ["Editor"]},
    {"Name": "EditorToolset", "Enabled": true, "TargetAllowList": ["Editor"]}
  ]
}
```

2. **DefaultEngine.ini Auto Start**
```ini
[/Script/ModelContextProtocol.ModelContextProtocolSettings]
bAutoStartServer=True
ServerPort=8000
bEnableToolSearch=True
```

3. **启动编辑器**
```powershell
Start-Process -FilePath "D:\Program Files\Epic Games\Engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" `
    -ArgumentList "path/to/project.uproject -ModelContextProtocolStartServer"
```

## MCP 路径格式

```
/Game/<子目录>/<资产名>.<资产名>
```

示例：
- `/Game/Blueprints/BP_Character.BP_Character`
- `/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter.BP_FirstPersonCharacter`

## 常用 MCP 工具

| 工具 | 用途 |
|---|---|
| `BlueprintTools.list_graphs` | 列出蓝图所有图 |
| `BlueprintTools.list_variables` | 列出蓝图变量 |
| `BlueprintTools.get_graph` | 获取图详情 |

## 故障排除

### MCP 服务器未启动
- 检查端口 8000 是否被占用
- 查看编辑器日志 `LogModelContextProtocol`
- 手动执行 `ModelContextProtocol.StartServer 8000`

### 返回 0 个图
- 确认蓝图路径正确（不含 `.uasset` 后缀）
- 确认项目已在编辑器中打开
- 检查蓝图是否有效（非空/未损坏）
