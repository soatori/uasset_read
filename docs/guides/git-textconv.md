# Git Textconv 集成

通过 Git textconv 驱动，将 `.uasset` 二进制文件在 `git diff` 中显示为人类可读的文本摘要。

## 快速安装

### Windows（推荐）

```powershell
.\scripts\install-git-textconv.ps1
```

### 手动安装

```bash
git config diff.uasset-read.textconv "python scripts/git-textconv-uasset.py"
```

### 卸载

```powershell
.\scripts\install-git-textconv.ps1 -Uninstall
# 或手动
git config --local --unset diff.uasset-read.textconv
```

## 工作原理

1. `.gitattributes` 将 `*.uasset` 和 `*.umap` 文件关联到 `uasset-read` diff 驱动
2. 运行 `git diff` 时，Git 调用 textconv 脚本（`scripts/git-textconv-uasset.py`）将每个 `.uasset` 文件解析为结构化文本
3. `difflib` 计算文本差异并输出 unified diff 格式

## 使用方式

### 查看单个文件的 diff

```bash
git diff -- '*.uasset'
```

### 查看两个特定版本的 diff

```bash
git diff HEAD~3 HEAD -- path/to/file.uasset
```

### 使用 CLI 内置 diff

```bash
python run.py file1.uasset --diff file2.uasset
python run.py file1.uasset --diff file2.uasset --diff-context 5
```

### 使用 text renderer 单独查看

```bash
python run.py file.uasset --text
```

## 输出格式

Text renderer 输出的结构化摘要包含：

- **包头信息** — 包名、类型、版本、导出/导入数量
- **Import/Export 表** — 对象名、类名、大小
- **蓝图数据** — 父类、函数、事件、变量
- **动画数据** — 状态机、通知、混合组
- **诊断信息** — 解析警告和错误

字段按字母排序，确保同一资产不同版本的 diff 行号对齐。

## 注意事项

- textconv 驱动使用容错模式，单个 export 解析失败不会中断整个 diff
- 首次对大资产运行 diff 可能需要数秒（解析开销）
- 仅支持未烘焙/编辑器保存的资产（与主解析器一致）
