# uasset-read

| 字段 | 值 |
|------|-----|
| Skill 名称 | uasset-read |
| 版本 | v3.0 |
| 分类 | Unreal Engine 资产解析 |
| 触发词 | uasset、.uasset、蓝图解析、蓝图图、parse_uasset、uasset_read |
| 自包含 | ✓ 可移动到其他项目独立使用 |

---

## 安装

将此skill目录复制到目标项目的 `.claude/skills/` 下即可使用：

```bash
# 复制整个skill目录
cp -r .claude/skills/uasset-read /path/to/target-project/.claude/skills/

# 或在目标项目中手动创建
mkdir -p /path/to/target-project/.claude/skills/uasset-read/scripts
cp scripts/uasset_read.py /path/to/target-project/.claude/skills/uasset-read/scripts/
```

脚本位置：`scripts/uasset_read.py`（约5900行，零外部依赖）

---

## Skill 说明

### 能做什么

- 解析 UE .uasset 蓝图文件，提取：
  - 蓝图变量（名称、类型、默认值）
  - 组件列表（SkeletalMesh、Camera等）
  - EventGraph 执行流程（函数调用链）
- 输出格式：JSON / Markdown / 精简摘要（--summary可减少70%+ token）
- 提供蓝图→C++转换参考（函数名、参数类型）

### 不能做什么

- **不解析 Cooked 资产** — Cooked资产已剥离蓝图数据，无法提取EventGraph
- **不生成完整C++代码** — 仅提供参考级别信息，需手动补充细节
- **不反编译蓝图字节码** — 专注于编辑器保存的未烘焙资产
- **不解析 Verse 脚本** — 仅关注蓝图层，不涉及Verse代码

---

## 快速开始

```python
# 从skill内置脚本导入
import sys
sys.path.insert(0, ".claude/skills/uasset-read/scripts")
from uasset_read import parse_uasset

# 或将脚本复制到项目根目录后直接导入
# from uasset_read import parse_uasset

# 解析蓝图文件
result = parse_uasset("path/to/BP_MyBlueprint.uasset")

# 检查解析状态
if result.is_success:
    print(f"解析成功: {result.summary.package_name}")

    # 查看执行流程
    for graph in result.graphs:
        print(f"图: {graph.graph_name}")
else:
    for error in result.errors:
        print(f"错误: {error}")
```

---

## 输出格式

API版本：output_version: "3.0" (Phase 14冻结)

| 字段 | 含义 |
|------|------|
| status.status | 解析状态：success/fail/error (JSend style) |
| graphs_summary | 执行流程概览（顶层，含function_name和params） |
| exports | 导出对象列表（蓝图类、组件等） |

**输出函数：**
- `format_json_full(result)` — 完整JSON输出
- `format_json_summary(result)` — 精简JSON（移除imports/errors等）
- `format_markdown(result)` — Markdown格式（人类和AI友好）

---

## 知识库索引

| 文件 | 内容 |
|------|------|
| [blueprint-semantics.md](knowledge/blueprint-semantics.md) | 蓝图概念：EventGraph、变量、组件 |
| [node-types.md](knowledge/node-types.md) | K2Node类型参考（Event、CallFunction、Variable等） |
| [pin-type-mapping.md](knowledge/pin-type-mapping.md) | Pin类型→JSON类型映射 |
| [cpp-conversion.md](knowledge/cpp-conversion.md) | 蓝图→C++转换参考 |
| [common-patterns.md](knowledge/common-patterns.md) | 常见蓝图模式（BeginPlay、输入绑定） |
| [troubleshooting.md](knowledge/troubleshooting.md) | 故障排除（Cooked资产、解析失败） |

---

## 示例索引

| 文件 | 场景 |
|------|------|
| [basic-usage.md](examples/basic-usage.md) | CLI和Python API基础调用 |
| [blueprint-analysis.md](examples/blueprint-analysis.md) | EventGraph分析流程 |
| [cpp-conversion.md](examples/cpp-conversion.md) | 蓝图→C++转换示例 |
| [troubleshooting.md](examples/troubleshooting.md) | 错误处理场景 |

---

## 测试资产

示例使用 FirstPerson 模板资产（UE Samples）：

```
E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset
```