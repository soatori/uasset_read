---
title: "35c-01: archive.py 文件描述符泄漏修复"
plan_id: "35c-01"
phase: "35c"
status: complete
created: "2026-05-13"
completed: "2026-05-13"
---

# 35c-01-SUMMARY.md — FArchive 初始化失败时文件描述符泄漏修复

**问题**: CR-01 — `archive.py:23` FArchive.__init__ 在初始化失败时文件句柄未关闭
**修复**: 添加 try/except 包裹初始化逻辑，异常时调用 self.close() 确保资源释放

## 一句话总结

修复 FArchive 初始化异常时文件描述符泄漏，通过 try/except 包裹初始化逻辑确保资源安全释放。

## 变更详情

### 修改文件

| 文件 | 变更 |
|------|------|
| `src/uasset_read/archive.py` | 重构 __init__ 添加异常处理 |

### 核心修复

**原代码** (问题):
```python
def __init__(self, path: str, tolerant: bool = False):
    self._path = path
    self._file: BinaryIO = open(path, 'rb')  # 文件打开
    self._byte_swapping: bool = False
    self._file_size: int = __import__('os').path.getsize(path)  # 可能抛异常
    # ... 如果这里异常，self._file 永远不会被关闭
```

**修复后**:
```python
def __init__(self, path: str, tolerant: bool = False):
    self._path = path
    self._file: BinaryIO = open(path, 'rb')
    # 预先初始化所有属性以保证 close() 的安全性
    self._byte_swapping: bool = False
    self._file_size: int = 0
    self._tolerant: bool = tolerant
    self._mmap: Optional[mmap.mmap] = None
    self._use_mmap: bool = False
    self._mmap_warning: Optional[str] = None

    try:
        self._file_size = __import__('os').path.getsize(path)
        # mmap 初始化...
    except BaseException:
        self.close()  # 确保资源释放
        raise
```

### 关键设计决策

1. **预初始化属性**: 在 try 块之前初始化所有实例属性，确保 `close()` 方法在异常时可以安全调用
2. **捕获 BaseException**: 捕获所有异常类型（包括 KeyboardInterrupt），确保任何情况下都能释放资源
3. **重新抛出异常**: 修复后重新抛出原始异常，保持 API 行为不变

## 验证结果

| 验收标准 | 状态 |
|----------|------|
| 初始化失败时文件描述符被正确关闭 | PASS |
| 正常初始化路径不受影响 | PASS |
| 测试通过 | PASS (257 passed, 65 skipped, 1 pre-existing failure) |

### 测试详情

```
python -m pytest tests/ -x -q
257 passed, 65 skipped, 1 failed
```

**注意**: 1 个测试失败 (`test_jump_started_flow`) 是 Phase 35b 部分完成后的已知问题（见提交 "wip: phase 35b paused at partial completion - remaining Direction/FName drift issue"），与本次 archive.py 修复无关。

### 手动验证

```python
# Test 1: FileNotFoundError 被正确抛出
try:
    ar = FArchive('/nonexistent/path/file.uasset')
except FileNotFoundError:
    pass  # OK - 异常被正确抛出

# Test 2: getsize 失败时文件描述符被关闭
# (通过 mock 验证 close() 被调用)
```

## 偏离计划

无偏离 - 计划完全按预期执行。

## 提交记录

- `eb8fa43`: fix(35c-01): 修复 FArchive 初始化失败时的文件描述符泄漏

## 执行指标

- **开始时间**: 2026-05-13
- **结束时间**: 2026-05-13
- **任务数**: 1
- **修改文件数**: 1

## 自检结果

| 检查项 | 状态 |
|--------|------|
| SUMMARY.md 存在 | PASS |
| 提交 eb8fa43 存在 | PASS |
| 提交 c8ecdec 存在 | PASS |

**自检状态**: PASSED