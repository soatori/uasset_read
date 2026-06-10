# 多会话并发测试规范

> 背景：参见 [Issue #104](https://github.com/.../issues/104) — 2026-06-10 多会话并发测试导致系统内存耗尽。

## 核心规则

1. **同一时间只有一个会话可以运行 `test_matrix.py all`。**
2. **`all` / `all-with-large` 强制串行**（`-n 1`），禁止多进程并行。
3. 不要手动给 `all` suite 传 `-n N`（N > 1），会被自动覆盖。

违反规则的后果：每个 pytest 进程独立加载资产到内存，多进程叠加可导致系统内存耗尽 → 系统强制重启。

## 测试分级与资源消耗

| 测试级别 | 命令 | 峰值内存 | 并发限制 |
|---------|------|---------|---------|
| `smoke` | `test_matrix.py smoke` | < 1 GB | 无限制 |
| `unit` | `test_matrix.py unit` | < 2 GB | 无限制 |
| `integration` | `test_matrix.py integration` | 5-10 GB | 最多 2 个会话 |
| `all` | `test_matrix.py all` | < 1 GB（GC fixture） | **仅 1 个会话，强制 -n 1** |
| `all --include-large` | `test_matrix.py all --include-large` | 5-15 GB | **仅 1 个会话，强制 -n 1，需 ≥ 16 GB RAM** |

> **峰值内存数据来源**：`all` suite 含 ~1000 个 integration 测试。
> 无 GC 时峰值 ~44 GB（Python 堆只增不缩）；
> 有 conftest.py `_gc_after_heavy_test` fixture 时，每测试后 GC，峰值降至单测试内存（< 500 MB）。

## 超大文件处理策略

### 资产大小分级与处理方式

| 级别 | 大小 | 解析行为 | 测试行为 |
|-----|------|---------|---------|
| small | < 10 MB | 正常解析 | 默认包含 |
| medium | 10-100 MB | 正常解析，batch 日志提示 | 默认包含 |
| large | 100-500 MB | batch 前打印警告，内存检查更频繁 | `@pytest.mark.large`，默认跳过 |
| huge | > 500 MB | **硬跳过**，记入 `skipped_large` | 不纳入常规测试 |

### 为什么 > 500 MB 要硬跳过

解析后 IR 内存占用约为原始文件的 3-5 倍。一个 500 MB 的 .uasset 解析后可能占用 1.5-2.5 GB。
批量处理数百个此类文件时，即使有 GC，峰值仍可能超过可用内存。
默认 `max_file_size_mb=500` 可在 API 层调整：

```python
parse_batch("path/", max_file_size_mb=1000)  # 提高限制（需确保 RAM 充足）
```

### `parse_single()` 入口保护

`parse_single()` 同样受保护，默认上限 1000 MB：

```python
from uasset_read import parse_single
from uasset_read.exceptions import ParseError

# 正常解析（< 1000 MB 无感知）
output = parse_single("normal.uasset")

# 超限 → ParseError（可在调用方 except 处理）
try:
    output = parse_single("huge.uasset")
except ParseError as e:
    if "too large" in str(e):
        print(f"跳过超大文件: {e}")

# 禁用检查（已知大文件的受控场景）
output = parse_single("huge.uasset", max_file_size_mb=0)

# 自定义上限
output = parse_single("medium.uasset", max_file_size_mb=200)
```

**CLI 单文件模式**同样受保护，`--max-file-size` 参数同时作用于单文件和批量模式：

```bash
# 单文件超 1000 MB 默认报错
python run.py huge.uasset

# 自定义上限
python run.py huge.uasset --max-file-size 2000

# 禁用检查
python run.py huge.uasset --max-file-size 0
```

### mmap 保护（已有机制）

> 50 MB 的文件自动使用 `mmap`（内存映射），不将整个文件读入 Python 堆。
> 这减少了 RSS，但解析出的 IR 结构仍占用常规内存。

## 全量测试内存安全机制

### conftest.py GC fixture

`tests/conftest.py` 提供 `autouse` fixture，在每个标记了 `@pytest.mark.integration` 或 `@pytest.mark.acceptance` 的测试结束后自动调用 `gc.collect()`。

- 单元测试不受影响（保持速度）
- integration/acceptance 测试峰值内存控制在单测试水平
- 无需手动管理

### 串行保护（test_matrix.py）

`test_matrix.py` 对 `all` 和 `all-with-large` suite 强制注入 `-n 1`，即使用户传入 `-n N` 也会被自动移除并打印警告。

原因：`pytest-xdist` 多进程模式下，每个 worker 独立持有资产 IR，GC fixture 无法跨进程回收。
全量 19,000 文件 × `-n 4` = 每进程 ~11 GB，合计 44 GB → OOM。

### 安全运行全量测试

```bash
# 1. 确认系统资源：可用内存 ≥ 10 GB
# 2. 确保无其他会话跑全量测试
tasklist | findstr python

# 3. 串行运行（自动 GC，自动 -n 1）
python scripts/test_matrix.py all

# 4. 含大资产（单独会话，需 ≥ 16 GB RAM）
python scripts/test_matrix.py all --include-large
```

## 批量解析内存管理

`parse_batch()` 内置三层保护：

```python
from uasset_read import parse_batch

result = parse_batch(
    "path/to/assets",
    max_file_size_mb=500,    # 层 1：单文件硬跳过
    batch_size=50,           # 层 2：每 50 个文件强制 GC
    max_memory_percent=70,   # 层 3：系统内存超 70% 暂停处理
)

# 检查结果
for path, reason in result.skipped_large:
    print(f"跳过（超大）: {path} — {reason}")
for path, reason in result.skipped:
    print(f"跳过（内存）: {path} — {reason}")
```

### 可选依赖：psutil

```bash
pip install psutil
```

安装后 `MemoryMonitor` 启用实时内存检查；未安装时内存检查返回 OK（不阻止处理），大文件跳过仍生效。

## 开发阶段推荐流程

```
编写代码
  → smoke（< 1 GB，随时跑）
  → unit（< 2 GB，随时跑）
  → integration（5-10 GB，最多 2 会话并发）
  → all（强制串行 + GC，仅 1 会话）
  → all --include-large（最终验证，单独会话）
```
