---
name: test-runner
description: Use when asked to run tests, check test status, verify test coverage, update test statistics in README, or detect flaky tests
---

# Test Runner

## Overview

运行测试、解析结果、自动更新文档中的测试统计。

## When to Use

- "运行测试"
- "测试通过吗"
- 修复后验证测试未回归
- 发布前质量门禁检查

## Inputs

- 用户指定的测试范围、失败用例或改动模块
- 未指定范围时，根据改动影响选择相关测试；发布前必须跑全量测试

## Outputs

- pytest 命令、通过/失败/跳过/xfail 统计
- 失败摘要和最小复现命令
- 测试通过后需要同步的文档统计

## 运行命令

### 基础运行

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行特定文件
python -m pytest tests/test_core_api.py -v

# 运行特定标记
python -m pytest tests/ -v -m regression
python -m pytest tests/ -v -m integration
```

### 双模式验证

项目使用 strict/tolerant 双模式测试（通过测试文件名或参数区分）。
具体模式见 `docs/guides/testing-requirements.md`。

## 结果解析

运行后提取统计（pytest 输出末尾行）：
```
X passed, Y failed, Z xfailed in N.NNs
```

## 自动更新统计

测试通过后自动更新以下文件中的测试统计：

| 文件 | 位置 |
|---|---|
| `CLAUDE.md` | "测试要点" 章节 |
| `README.md` | 项目介绍部分 |
| `README.zh-CN.md` | 中文介绍 |
| `docs/guides/dev-guide.md` | 测试章节 |

更新方式：只解析 pytest 最后一行 summary，再定点更新文档中的测试统计字段；不要用宽泛正则批量替换正文。

## Verification

- 失败时保留首个失败堆栈和复现命令
- 修复后优先重跑失败用例，再跑相关目录
- 发布前运行 `python -m pytest tests/ -v`

## 质量门禁

| 指标 | 要求 |
|---|---|
| 单元测试数 | ≥ 800 |
| 通过率 | 100% (xfail 除外) |
| 资产类型覆盖 | ≥ 12 种 |
| 回归测试 | 全部通过 |

## Flaky Test 检测

连续运行 3 次，检查是否有结果不一致（PowerShell 兼容）：

```powershell
1..3 | ForEach-Object { python -m pytest tests/ -q --tb=no }
```

结果不一致时列出候选 flaky 测试、运行次数和失败摘要；不要自动添加 `@pytest.mark.flaky`，除非用户明确要求。

## Boundaries

- 不为通过测试而跳过失败用例或放宽断言
- 不把环境缺失误报为代码通过；需明确标出未验证项
- 不使用 `pip install -e .` 安装项目本身

## Common Mistakes

- **忘记更新文档统计**：测试通过后忘记同步更新 CLAUDE.md / README.md 中的数字
- **误判 xfail 为失败**：xfail (expected failure) 是已知预期失败，不计入失败数
- **跳过回归测试**：`-m regression` 测试覆盖真实资产，跑完全量需要时间，但不应跳过
