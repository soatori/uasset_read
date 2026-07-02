# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 行为规则

- **语言**：所有对话、代码注释、错误提示、文档统一使用中文
- **输出**：专业简洁，避免冗余
- **CodeGraph**：优先使用 `codegraph_*` 工具回答结构化问题（详见全局 CLAUDE.md）

## 项目概述

**uasset_read** — 虚幻引擎 `.uasset` 文件的 Python 解析器，零运行时依赖。专注未烘焙/编辑器保存的资产（含完整蓝图数据）。版本 0.5.1.19 | Python 3.10+ | 禁止 `pip install`。

## 常用命令

```bash
# 解析
python run.py file.uasset                        # JSON 输出（默认）
python run.py file.uasset --markdown             # Markdown + Mermaid
python run.py file.uasset --strict               # 遇警告停止
python run.py file.uasset --tolerant             # 容错模式（默认）
python run.py --batch-dir path/to/dir/           # 批量导出

# 测试
python scripts/test_matrix.py smoke              # L0 烟雾测试（最快）
python scripts/test_matrix.py unit               # L0+L1 单元测试
python scripts/test_matrix.py all                # 全量测试
python -m pytest tests/test_pak_handling.py -v   # 单个文件
python -m pytest tests/ -v --cov=uasset_read     # 覆盖率

# 质量
python scripts/test_matrix.py quality            # 质量门禁
```

**Windows 路径**：使用正斜杠 `E:/Develop/...` 或双反斜杠。**测试样本**：`E:\Develop\lib\Samples`。**pytest 标记**：`integration`、`quality`、`regression`、`slow`。

## 核心架构

解析器镜像 UE 内部的 `FArchive` 序列化管线：

```
.uasset → FArchive → Serializers → Parsers → Linker → IR Builder → Renderers
```

### 关键模块

- **archive.py** — `FArchive` 二进制读取层，镜像 UE 的 FArchive 接口
- **parse_uasset.py** — 主入口，`parse_package()` 返回 `ParseResult`
- **core.py** — 高层 API（`parse_single`、`parse_batch`），CLI 和脚本共用
- **ir_builder.py** — `ParseResult` → `PackageIR`，渲染器只接收 IR
- **models/ir.py** — IR 数据结构：`PackageIR → ExportIR → GraphIR → NodeIR → PinIR`
- **models/result.py** — `ParseResult` 容器（summary、linker、graphs、blueprint）
- **objects/** — UObject 实例注册表，跨 export 的对象引用解析

### 蓝图解析链

```
serializers/graph.py → graph/flow_builder.py
  → blueprint/variable_extractor.py → kismet/（字节码 → AST → C++）
```

### C++ 生成子系统

`cpp_gen/` 将蓝图解析结果转换为 C++ 类骨架：类型映射、UPROPERTY 宏、构造函数格式化、函数体提取。

### 渲染器系统

渲染器通过 `RENDERER_REGISTRY` 自动注册。新增格式：在 `renderers/` 实现 `IRenderer` 子类 → 调用 `register_renderer()` → 在 `renderers/__init__.py` 添加 import。

### 动画蓝图支持

- **AnimBlueprintGeneratedClass** — 完整解析 BakedStateMachines / AnimNotifies / AnimNodeData
- **AnimSequence** — 深度元数据提取（不含压缩轨迹数据）
- **AnimMontage** — 混合参数 / 通知 / 同步组解析
- **动画子图** — StateMachine / State / Transition / Conduit 类型识别

### 容错模式

- **strict**：遇警告停止
- **tolerant**（默认）：遇错继续，标记 partial
- **轻量解析**：export_count > 300 时自动跳过完整蓝图解析

## 分支管理与提交规范

### 分支策略

| 分支 | 用途 |
|---|---|
| `develop` | **日常开发**（默认工作分支），包含完整文件 |
| `master` | **发布分支**，仅 src/CI/README/tests/docs |
| `wiki/master` | Wiki 专用，独立维护 |

### master 文件白名单

允许：`src/`、`.github/workflows/`、`README.md`、`CLAUDE.md`、`pytest.ini`、`run.py`、`tests/`、`docs/formats/`、`docs/designs/`、`docs/reference/`、`docs/agents/`、`docs/release-notes/`、`.claude/rules/`

排除：`wiki/`、`scripts/`、`.claude/skills/`、`.claude/workflows/`、`.claude/agents/`、`temp/`、`docs/guides/`、`docs/superpowers/`、`docs/reports/`

### 版本发布流程

从 develop 合并到 master 时排除仅开发文件（wiki/scripts/.claude/skills 等），CI 会自动校验白名单合规。

### 提交信息格式

`<type>: <简要描述>` — 类型：`feat`、`fix`、`refactor`、`test`、`docs`、`chore`、`release`

## 关键约束

见 [.claude/rules/constraints.md](.claude/rules/constraints.md)。核心：
- 仅支持未烘焙/编辑器保存的资产
- 只读，不支持修改或写入
- 零运行时依赖
- 必须参考 UE 源码（`E:\Develop\lib\UnrealEngine`），禁止猜测二进制格式
- 临时文件放 `temp/`

## 文档与工具

- `wiki/` — 开发指南 | `docs/formats/uasset/` — UE 格式参考（60+ 文件）
- `docs/designs/` — 设计规格 | `docs/reference/` — 技术参考 | `docs/release-notes/` — 发布说明

**Issue tracker**：GitHub Issues（gh CLI）。详见 `docs/agents/issue-tracker.md`。
