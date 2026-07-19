# CLAUDE.md

本文件是 Claude Code 在本仓库工作的项目规范。

## 基本规则

- 所有对话、代码注释、错误提示和文档使用中文；输出专业、简洁。
- 结构化代码问题优先使用 `codegraph_*` 工具；仓库根目录存在 `.codegraph/`。
- 项目：`uasset_read` 是 Python 3.10+、零运行时依赖的 Unreal `.uasset` 解析器，专注未烘焙/编辑器保存资产（含完整蓝图数据）。禁止 `pip install`。
- Windows 路径使用 `E:/Develop/...` 或双反斜杠；测试样本位于 `E:\Develop\lib\Samples`。

## 常用命令

```bash
# 解析
python run.py file.uasset                       # JSON（默认）
python run.py file.uasset --markdown            # Markdown + Mermaid
python run.py file.uasset --strict              # 遇警告停止
python run.py file.uasset --tolerant             # 容错模式（默认）
python run.py --batch-dir path/to/dir/           # 批量导出
python run.py --list-formats                     # 列出格式
python run.py file1.uasset --diff file2.uasset   # 对比

# 测试与质量
python -m pytest tests/ -v
python -m pytest tests/ -v -m "not slow"
python -m pytest tests/ -v --cov=uasset_read
python -m pytest tests/{模块}/test_x.py::test_y -v
python -m pytest tests/ -v -m quality
```

pytest 标记：`integration`、`quality`、`regression`、`slow`；`pytest.ini` 已设置 `pythonpath = src`。

## 测试脚本规则

以下规则约束新增和迁移；历史测试不因本规则自动删除或批量迁移。

| 场景 | 位置 | 规则 |
|---|---|---|
| 修改现有测试 | `tests/{模块}/test_*.py` | 优先复用并合并已有测试 |
| 正式测试 | `tests/{模块}/test_{功能}.py` | 仅保留长期维护、可重复运行且有持续价值的测试 |
| 核心基准测试 | `tests/core/` | 只保留最小核心回归集，最多 5 个 |
| 小功能/临时测试 | `temp/test_{用途}.py` | 一次性验证、局部排查或低复用功能；不纳入正式套件 |

### 数量与整理要求

- `tests/` 下正式 `test_*.py` 总数不得超过 **20 个**；达到上限必须先合并重复覆盖、删除过时测试或迁移低价值测试。
- 核心基准测试不得超过 **5 个**，只覆盖解析主链路、关键安全边界和最重要的用户可见输出；模块细节不得借此目录绕过限制。
- `tests/` 下全部测试用例（`test_*` 函数）总数不得超过 **100 个**；达到上限必须先合并同场景用例、删除低价值测试或迁移至 `temp/`。
- 同模块、同输入类型、同输出目标或同类边界条件，优先合并到已有脚本；无清晰隔离需求不得重复建文件。
- 特殊功能或新功能只有在具备独立边界、独立输入输出或独立回归价值时，才可创建独立测试文件。
- 新建独立文件前必须评估现有脚本：检查重复覆盖、可合并用例、过时用例和错误归类，并说明复用、合并、迁移、删除或新建理由。
- 整理测试时保持行为覆盖不下降：先合并用例并保留关键回归断言，再删除重复/失效脚本；归类调整需同步更新路径、导入和命令。
- `temp/` 测试应在任务结束时删除、归档为文档证据或升级为正式测试，不得成为第二套长期测试套件。
- 新增正式测试的提交说明必须列出模块、核心名额占用、当前总数和新增后总数；超限方案不得合并。
- 测试目录按功能模块对应 `src/uasset_read/`；命名为 `test_{功能描述}.py`，函数命名为 `test_{场景}_{预期结果}()`。

## 核心架构

```text
.uasset → FArchive → Serializers → Parsers → ParseResult
                                      ↓
                          IR Builder → PackageIR → JSON/Markdown Renderers
```

完整管线：`parse_package()` → `ParseResult` → `build_package_ir()` → `PackageIR` → `renderer.render(ir, options)`。渲染器只接收 IR，不访问 `ParseResult`。

关键模块：

- `archive.py`：FArchive 二进制读取层；`parse_uasset.py`：解析入口。
- `core/__init__.py`：`parse_single`、`parse_batch`、`diff_single`，供 CLI 和脚本共用。
- `ir_builder.py`、`models/ir.py`、`models/result.py`：结果到 IR 的构建和模型。
- `objects/`：跨 export 的 UObject 注册与引用解析。
- `serializers/graph.py` → `graph/flow_builder.py` → `blueprint/` → `kismet/`：蓝图图与字节码链路。
- `cpp_gen/`：蓝图结果到 C++ 类骨架；`renderers/`：通过 `RENDERER_REGISTRY` 注册输出格式。

顶层废弃导出已全部移除，新增代码不得重新引入。

状态：包级 `success | partial | failed`；Export 级状态必须通过 `validate_parse_status()`。`strict` 遇警告停止，`tolerant`（默认）遇错继续并标记 `partial`；`export_count > 300` 时自动跳过完整蓝图解析。

## 约束、分支与提交

- 只支持未烘焙/编辑器保存资产；只读，不修改或写入资产；零运行时依赖。
- 二进制格式必须参考 `E:\Develop\lib\UnrealEngine`，禁止猜测；临时文件放 `temp/`。
- 详细约束见 [.claude/rules/constraints.md](.claude/rules/constraints.md)。
- `develop` 为日常开发，`master` 为发布分支，`wiki/master` 维护 Wiki。
- `master` 只允许 `src/`、CI、README、`CLAUDE.md`、`pytest.ini`、`run.py`、`tests/`、指定 `docs/` 和 `.claude/rules/`；排除 `wiki/`、`scripts/`、`.claude/skills/`、`temp/` 等开发文件。
- 提交格式：`<type>: <简要描述>`，类型为 `feat`、`fix`、`refactor`、`test`、`docs`、`chore`、`release`。

## 文档与工具

- `wiki/`：开发指南；`docs/formats/uasset/`：UE 格式参考；`docs/designs/`、`docs/reference/`、`docs/release-notes/`：设计、参考和发布文档。
- Issue tracker 为 GitHub Issues（`gh` CLI），详见 `docs/agents/issue-tracker.md`。
