<!-- generated-by: gsd-doc-writer -->
# 贡献指南

感谢您对本项目的关注！Unreal Engine `.uasset` 文件解析器是一个开源项目（MIT 许可），欢迎所有开发者参与贡献。

## 行为准则

本项目致力于营造一个开放、尊重他人的社区环境。在参与贡献之前，请确保您理解并遵守基本的开源行为准则——友善交流、尊重他人意见、对事不对人。

## 开发环境设置

1. **Fork 本仓库**，然后克隆到您的本地机器：

   ```bash
   git clone https://github.com/soatori/uasset_read.git
   cd uasset_read
   ```

2. **创建 Python 虚拟环境**（Python >= 3.10）：

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .venv\Scripts\activate      # Windows
   ```

3. **安装开发依赖**：

   ```bash
   pip install -e ".[dev]"
   ```

   这将安装项目本身（零运行时依赖）以及 `pytest>=7.0` 和 `pytest-cov>=4.0`。

4. **验证安装**：

   ```bash
   uasset-read --help
   python -m pytest tests/ -v
   ```

## 编码标准

- **PEP 8**：遵循 PEP 8 代码风格指南，使用 4 空格缩进。
- **类型注解**：所有函数和方法都应包含类型注解。本项目使用 Python 3.10+，可以利用 `match` 语句和现代类型语法。
- **零注释策略**：对于显而易见的代码，不编写注释。仅在逻辑复杂、涉及 UE 二进制格式细节或需要解释设计决策的地方添加注释。
- **命名约定**：UE 相关结构体、枚举、标志位使用与 UE C++ 源码一致的名称（如 `FObjectExport`、`PropertyTag`、`CPF_Edit`）。Python 函数和变量使用 `snake_case`。
- **导入顺序**：标准库 → 第三方库（本项目无） → 本地模块，各组之间空一行。

## 分支与 PR 流程

1. **分支命名**：从 `master` 分支创建功能分支，格式为：
   - `feat/description` — 新功能
   - `fix/description` — 缺陷修复
   - `docs/description` — 文档更新
   - `chore/description` — 维护性变更

2. **提交信息**：使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

   ```
   type(scope): description

   type 可选值：feat, fix, docs, test, refactor, chore
   scope 可选值：parsers, models, serializers, graph, link, formatters, cli, pipeline
   ```

   示例：
   ```
   feat(parsers): add MapProperty nested type parsing
   fix(link): correct ImportMap offset calculation for UE5.3
   docs(roadmap): update Phase 49 status
   ```

3. **提交 PR**：
   - 推送到您的 fork，在 GitHub 上创建 Pull Request，目标分支为 `master`。
   - PR 标题遵循提交信息格式。
   - PR 描述应包含：变更概述、测试验证结果、相关 issue 引用（如有）。
   - 确保所有测试通过后再提交 PR。

## 添加新功能

本项目的架构是模块化的管道：`.uasset → FArchive → Deserializer → Models → OutputFormatter`。添加新功能时，请遵循以下指引：

### 新增属性解析器

1. 在 `src/uasset_read/parsers/` 中创建解析器函数（如 `parse_struct_property()`）。
2. 在分派器中注册新类型映射。
3. 添加对应的数据模型类到 `src/uasset_read/models/`。
4. 编写测试用例，覆盖正常路径和边界情况。

### 新增节点类型

1. 在 `src/uasset_read/models/` 中定义新的 K2Node 数据类（继承自 `UEdGraphNode` 或使用 `dataclass`）。
2. 在 `graph/` 解析器中添加节点识别逻辑。
3. 确保在 `__init__.py` 中导出新符号。

### 新增输出格式

1. 在 `src/uasset_read/formatters/` 中实现格式化函数（如 `format_graphviz()`）。
2. 在 `cli.py` 的 `--format` 参数中添加新选项。
3. 更新 CLI 帮助文本。

详细的模块结构和职责划分请参考 [ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 测试要求

- **所有测试必须通过**：提交 PR 前，运行 `python -m pytest tests/ -v` 确保零失败。
- **测试文件命名**：`test_*.py`，放置在 `tests/` 目录下，与源码结构对应。
- **测试覆盖**：新增解析器必须包含至少一个真实 `.uasset` 数据的测试用例。无法提供真实资产时，使用构造的字节序列模拟 FArchive 输入。
- **运行单个测试**：

  ```bash
  python -m pytest tests/test_archive.py -v
  python -m pytest tests/test_archive.py::TestFArchive::test_read_int32 -v
  ```

- **覆盖率**：本项目使用 `pytest-cov`。运行覆盖率检查：

  ```bash
  python -m pytest tests/ --cov=uasset_read --cov-report=term-missing
  ```

## 报告问题

### Bug 报告

请在 [GitHub Issues](https://github.com/soatori/uasset_read/issues) 中创建新 Issue，并包含以下信息：

- **问题描述**：发生了什么，期望行为是什么。
- **重现步骤**：提供导致问题的 `.uasset` 文件（或最小复现样本）和执行的命令。
- **环境信息**：Python 版本、操作系统、UE 版本（如果已知）。
- **错误输出**：完整的 traceback 或错误信息。

### 功能请求

- 说明您希望支持哪种 UE 特性或属性类型。
- 提供相关的 UE C++ 源码引用（如果可能），如 `FObjectExport` 在 UE 源码中的位置。
- 说明该功能的优先级和使用场景。

## GSD 工作流阶段

本项目采用 GSD（Goal-Driven Software Development）工作流，将开发分解为多个 Phase。了解 Phase 状态有助于避免重复工作：

- **规划文件**：所有 Phase 的规划文档位于 `.planning/` 目录。
- **ROADMAP.md**：50 阶段的路线图，查看整体进度。
- **STATE.md**：当前里程碑的详细状态。
- **当前状态**：v8.0 进行中 — Phase 47 已完成，Phase 48/50 部分完成，Phase 49 待启动。

如果您想参与某个 Phase，请先阅读对应的 PLAN 文件（如 `.planning/phase-49/PLAN.md`），确认该 Phase 尚未被他人认领。

## 文件组织

```
src/uasset_read/    # 源代码
tests/              # 测试用例
.planning/          # Phase 规划文档
temp/               # 缓存和临时文件（已 git 忽略）
uasset_read_cpp/    # C++ 参考代码（已 git 忽略）
UnrealEngine/       # UE 源码参考（已 git 忽略）
LyraStarterGame/    # Lyra 示例资产（已 git 忽略）
```

> 所有缓存、临时性生成文件统一放在 `temp/` 目录，已在 `.gitignore` 中排除。请勿将临时文件提交到版本库。

## 许可

本项目采用 MIT 许可。提交贡献即表示您同意将您的代码以 MIT 许可发布。
