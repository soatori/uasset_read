---
name: uasset-mcp-comparison
description: Use when comparing uasset_read parser output against Unreal Editor MCP ground truth — validating graph names, variables, and structure accuracy. Use for batch testing multiple projects, validating parser improvements, or generating comparison reports for the issue tracker.
---

# uasset MCP 对比测试

## Overview

对比 uasset_read 解析器输出与 Unreal Editor MCP 实时数据，验证蓝图图名、变量等结构的解析准确性。

## 工作流

```
1. 配置项目 MCP → 2. 启动编辑器 → 3. 解析蓝图 → 4. MCP 对比 → 5. 生成报告 → 6. 创建 Issue
```

### Step 1: 配置项目 MCP

确保目标项目已启用 MCP 插件：

```python
# 使用配置脚本
python "C:\Users\cbsjz\.config\mimocode\skills\unreal-mcp\scripts\configure-unreal-mcp.py" \
    -ProjectPath "path/to/project" \
    -Target claude
```

或手动检查 `.uproject` 是否包含：
```json
{"Name": "ModelContextProtocol", "Enabled": true},
{"Name": "ToolsetRegistry", "Enabled": true},
{"Name": "EditorToolset", "Enabled": true}
```

### Step 2: 启动编辑器

```powershell
# 启动时启用 MCP 服务器
Start-Process -FilePath "D:\Program Files\Epic Games\Engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" `
    -ArgumentList "path/to/project.uproject -ModelContextProtocolStartServer"
```

等待编辑器加载完成（内存占用稳定后），验证 MCP 服务器：
```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/mcp" -Method Post `
    -Body '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' `
    -ContentType "application/json"
```

### Step 3: 解析蓝图

```bash
# 单文件解析
python run.py path/to/BP_SomeBlueprint.uasset

# 批量解析（带内存管理）
python scripts/quick_mcp_compare.py  # 或自定义脚本
```

### Step 4: MCP 对比

使用对比脚本：

```python
# 单项目对比
python scripts/mcp_compare.py --project ProjectName --blueprints BP1,BP2,BP3

# 多项目批量对比
python scripts/batch_mcp_compare.py --projects FirstPerson,ThirtPerson,GameAnimationSample
```

对比逻辑：
1. 获取解析器提取的图名列表
2. 调用 MCP `BlueprintTools.list_graphs` 获取真实图名
3. 计算匹配率

### Step 5: 生成报告

报告格式：
```
| 蓝图 | MCP 图数 | 解析图数 | 匹配 | 匹配率 |
|---|---|---|---|---|
| BP_Character | 24 | 24 | 24 | 100% |
| BP_AnimInstance | 101 | 71 | 68 | 67.3% |
```

保存到 `temp/<project>-mcp-comparison-report.json`

### Step 6: 创建 Issue（可选）

```bash
gh issue create --title "feat: <描述>" --body-file temp/comparison-report.md
```

## MCP 路径格式

```
/Game/<子目录>/<资产名>.<资产名>
```

示例：
- `/Game/Blueprints/BP_Character.BP_Character`
- `/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter.BP_FirstPersonCharacter`

## 常见问题

### MCP 返回 0 个图
- 检查蓝图路径是否正确（不含 `.uasset` 后缀）
- 确认项目已在编辑器中打开

### 匹配率低
- 动画蓝图（ABP）的 AnimGraph 嵌套子图可能未完全解析
- 检查是否有轻量模式跳过了部分解析

## 脚本参考

| 脚本 | 用途 |
|---|---|
| `scripts/mcp_compare.py` | 单项目 MCP 对比 |
| `scripts/batch_mcp_compare.py` | 多项目批量对比 |
| `scripts/quick_mcp_compare.py` | 快速对比（仅关键蓝图） |

## 相关 Skills

- `uasset-output-quality-test` - 解析器输出质量检测
- `bp-cpp-comparison` - 蓝图 vs C++ 对照验证
- `unreal-mcp` - Unreal MCP 配置和使用
