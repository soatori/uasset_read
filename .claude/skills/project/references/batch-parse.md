# 批量解析报告

对指定目录执行批量解析，收集所有错误和警告，生成分组错误报告。

## 参数

用户可指定目录和限制数量，默认 `E:\Develop\lib\Samples`。

## Step 1: 确定解析目标

```python
import os, sys
from pathlib import Path

target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"E:\Develop\lib\Samples")
limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

files = []
for root, dirs, fnames in os.walk(target):
    for f in fnames:
        if f.endswith('.uasset'):
            files.append(os.path.join(root, f))
            if limit and len(files) >= limit:
                break
    if limit and len(files) >= limit:
        break
print(f"Found {len(files)} .uasset files")
```

## Step 2: 批量解析

使用 `parse_package()`（非 `parse_single()`），以访问 errors/warnings 属性：

```python
from uasset_read.core import parse_package
from uasset_read.models.result import ParseResult

results = {"success": 0, "partial": 0, "failed": 0}
errors, warnings = [], []

for i, fpath in enumerate(files):
    try:
        result: ParseResult = parse_package(fpath, tolerant=True)
        results[result.status.value] += 1
        for err in result.errors:
            errors.append({"file": fpath, "error": str(err)})
        for warn in result.warnings:
            warnings.append({"file": fpath, "warning": str(warn)})
    except Exception as e:
        results["failed"] += 1
        errors.append({"file": fpath, "error": f"UNHANDLED: {e}"})
    if (i + 1) % 100 == 0:
        print(f"Progress: {i+1}/{len(files)}")
```

## Step 3: 分组归类

```python
from collections import Counter

error_types = Counter()
for e in errors:
    msg = e["error"]
    error_type = msg.split(":")[0].strip() if ":" in msg else msg[:60]
    error_types[error_type] += 1
```

## Step 4: 生成报告

输出到 `temp/batch_parse_report.md`：

```markdown
## 批量解析报告

- **时间**: YYYY-MM-DD HH:MM
- **目标目录**: <path>
- **文件总数**: N
- **解析耗时**: Xs (Y files/s)

### 汇总

| 状态 | 数量 | 占比 |
|------|------|------|
| success | N | X% |
| partial | N | X% |
| failed | N | X% |

### 错误分类 (Top 20)

| 类型 | 次数 | 示例文件 |
|------|------|----------|
| <error_type> | N | <sample_path> |

### 警告分类 (Top 10)

| 类型 | 次数 |
|------|------|
| <warn_type> | N |
```

## 约束

- 使用 `parse_package()` 获取完整错误信息
- `tolerant=True` 避免单文件失败中断批量
- 报告保存到 `temp/batch_parse_report.md`
- 超过 500 文件时显示进度
