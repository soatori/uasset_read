# UE Wiki 配置说明

## 配置文件格式

`uewiki.config.json` 或 `uewiki.config.local.json`：

```json
{
  "uewiki_root": "E:/Develop/ue_wiki",
  "wiki_root": "E:/Develop/ue_wiki/wiki",
  "ue_source_root": "E:/Develop/lib/UnrealEngine/Engine",
  "codegraph_project_path": "E:/Develop/lib/UnrealEngine",
  "ue_version": "5.7",
  "index_output_dir": "build/uewiki",
  "remote": "https://github.com/<owner>/ue_wiki.git"
}
```

## 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `uewiki_root` | 是 | ue_wiki 项目根目录的绝对路径 |
| `wiki_root` | 否 | wiki 文档目录，默认为 `<uewiki_root>/wiki` |
| `ue_source_root` | 否 | UE Engine 目录路径，用于源码路径验证。未配置时跳过源码验证 |
| `codegraph_project_path` | 否 | CodeGraph 项目路径，用于输出 CodeGraph 建议 |
| `ue_version` | 否 | UE 版本号，默认 "5.7" |
| `index_output_dir` | 否 | 索引输出目录，默认 "build/uewiki" |
| `remote` | 否 | 远程 Git 仓库 URL，用于 fallback |

## 配置优先级

```text
1. --config <path> 参数
2. 当前项目 .claude/uewiki.config.json
3. ue_wiki/uewiki.config.local.json
4. %USERPROFILE%/.claude/uewiki.config.json
5. 环境变量 UEWIKI_ROOT / UE_SOURCE_ROOT / UEWIKI_REMOTE
6. 默认远程 Git 仓库 fallback
```

## 环境变量

| 变量 | 说明 |
|---|---|
| `UEWIKI_ROOT` | ue_wiki 项目根目录 |
| `UE_SOURCE_ROOT` | UE Engine 目录 |
| `UEWIKI_REMOTE` | 远程 Git 仓库 URL |

## 常见问题

### Q: validate 报 "ue_source_root 未配置"
A: 在配置文件中添加 `ue_source_root` 字段，指向 UE 的 Engine 目录。
如果不关心源码路径验证，可以忽略此警告。

### Q: 模块名验证失败
A: 确认模块名与 `.Build.cs` 文件名一致。
例如 `Engine` 模块对应 `Engine.Build.cs`，不是 `RuntimeEngine.Build.cs`。

### Q: 索引数据库在哪里
A: 默认在 `<uewiki_root>/build/uewiki/wiki-index.sqlite`。
通过 `index_output_dir` 配置项修改。

### Q: 如何在其他项目使用
A: 在项目 `.claude/` 目录下创建 `uewiki.config.json`，设置 `uewiki_root` 指向本项目。
或设置环境变量 `UEWIKI_ROOT`。

---

## CodeGraph 多项目配置

当 UE 源码范围过大导致 CodeGraph 查询超时时，可拆分为多个独立的 CodeGraph 项目。

### 配置示例

```json
{
  "codegraph_projects": {
    "default": "E:/Develop/lib/UnrealEngine",
    "rendering": "E:/CodeGraph/UE5-Rendering",
    "editor": "E:/CodeGraph/UE5-Editor",
    "gameplay": "E:/CodeGraph/UE5-Gameplay"
  },
  "codegraph_project_rules": {
    "rendering": [
      "Engine/Source/Runtime/RenderCore/",
      "Engine/Source/Runtime/Renderer/",
      "Engine/Source/Runtime/RHI/",
      "Engine/Source/Runtime/Slate/",
      "Engine/Source/Runtime/SlateCore/"
    ],
    "editor": [
      "Engine/Source/Editor/",
      "Engine/Source/Developer/"
    ],
    "gameplay": [
      "Engine/Source/Runtime/Engine/",
      "Engine/Source/Runtime/GameplayTags/",
      "Engine/Source/Runtime/GameplayTasks/"
    ]
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `codegraph_projects` | object | CodeGraph 项目名称到路径的映射 |
| `codegraph_projects.default` | string | 默认 CodeGraph 项目路径 |
| `codegraph_projects.<name>` | string | 特定领域的 CodeGraph 项目路径 |
| `codegraph_project_rules` | object | 源码路径前缀到项目名称的映射规则 |
| `codegraph_project_rules.<name>` | array | 该领域对应的源码路径前缀列表 |

### 工作原理

1. `pack` 命令根据页面的 `source_roots` 自动匹配最合适的 CodeGraph 项目
2. 匹配规则：按 `codegraph_project_rules` 中的路径前缀进行匹配
3. 如果无匹配规则，使用 `codegraph_projects.default`
4. 如果未配置 `codegraph_projects`，回退到 `codegraph_project_path`

### 建议拆分策略

- **Rendering**：渲染相关模块（RenderCore, Renderer, RHI, Slate）
- **Editor**：编辑器相关模块（Editor/*, Developer/*）
- **Gameplay**：游戏逻辑模块（Engine, GameplayTags, GameplayTasks）
- **Plugins**：插件模块（Plugins/*）

每个 CodeGraph 项目应独立初始化，避免单个项目过大导致查询超时。
