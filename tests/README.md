# 测试目录结构

## 当前规模

本目录当前包含 16 个 `test_*.py` 文件，`python -m pytest --collect-only -q`
在本地收集到 94 个测试用例。集成测试在样本资产、Unreal Editor 或 MCP
不可用时会按测试自身条件 skip。

默认测试套件只保留必项回归和当前公开能力验收。历史补充或功能探索测试放在
仓库根目录 `temporary_tests/`，需要时显式运行，不参与默认 `testpaths = tests`
收集。

## 目录分层

| 目录 | 重点 |
|---|---|
| `core/` | 核心 API 错误处理、工具函数 |
| `integration/` | 真实样本、输出验收、UE/MCP 对照 |

根目录下保留跨模块测试：代码质量、入口质量、冒烟导入测试。

大部分子目录（`archive/`、`blueprint/`、`cpp/`、`graph/`、`ir/`、`kismet/`、`linker/`、`misc/`、`serialization/`、`structs/`）已清空，保留目录结构供未来扩展。

仓库根目录 `temporary_tests/` 保留默认套件外的辅助测试，例如历史 API 清理、
cue4parse 差距补充、覆盖率/质量总表、内部算法矩阵、映射表展开测试、
非当前 JSON/Markdown 主合同的专项输出测试等。
这些测试可用于专项验证，但不作为必项测试门禁。

## Integration 测试组织

`tests/integration/sample_assets.py` 是真实样本的唯一共享定义入口：

- 使用 canonical `ThirdPerson` / `ThirdPersonC` 路径描述样本。
- 当前本地样本仍可能落在历史目录 `ThirtPerson` / `ThirtPersonC` 下，helper 会兼容解析。
- 新增真实样本时优先加入这里，再在验收或代表性矩阵中引用 label。

## 标记

| 标记 | 说明 |
|---|---|
| `integration` | 需要外部样本资产、Editor、MCP 或较慢真实路径 |
| `slow` | 慢速或大样本测试 |
| `quality` | 输出质量门禁 |

## 常用命令

```bash
# 运行所有测试
python -m pytest tests/ -v

# 带覆盖率
python -m pytest tests/ -v --cov=uasset_read

# 收集测试数量
python -m pytest --collect-only -q
```

样本根目录默认是 `E:\Develop\lib\Samples`。可通过 `UE_SAMPLE_ROOT` 或
`--sample-root` 覆盖；缺失样本时可用 `--allow-missing-assets` 跳过资产测试。

## MCP 集成

普通测试不会启动 Unreal Editor。只有设置 `UE_MCP_AUTO_LAUNCH=1` 时，MCP
对照测试才允许自动启动 Editor。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `UE_MCP_URL` | `http://127.0.0.1:8000/mcp` | MCP 端点 |
| `UE_MCP_AUTO_LAUNCH` | `0` | 设为 `1` 才允许自动启动 Editor |
| `UE_MCP_STARTUP_TIMEOUT` | `300` | 自动启动等待秒数 |
| `UE_EDITOR_EXE` | 无 | UnrealEditor.exe 显式路径 |

## 添加测试

1. 先放到最贴近责任边界的目录。
2. 涉及真实样本时，先更新 `tests/integration/sample_assets.py`。
3. 用户可见 JSON/Markdown 行为优先放入 `test_acceptance.py` 或相邻输出验收文件。
4. 外部 MCP/Editor 依赖必须可 skip，不能让默认测试套件因为服务未启动而失败。
