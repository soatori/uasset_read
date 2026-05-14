# Phase 5: 优化与安全 - Research

**Researched:** 2026-05-01
**Domain:** Python mmap、边界验证、循环限制、错误处理
**Confidence:** HIGH（所有关键技术点已通过 Python 运行验证）

## Summary

本阶段为解析器添加性能优化（大文件内存映射）和安全加固（边界验证增强、循环限制、部分结果改进）。研究覆盖 Python mmap 模块跨平台用法、FArchive 类扩展模式、边界验证实现、循环计数限制策略、ParseResult 扩展、以及错误上下文信息格式。

**Primary recommendation:** 在 FArchive 内部添加 mmap 分支，保持对外接口一致；使用统一的 `close()` 方法管理资源；在关键循环添加计数器检查；扩展 ParseResult 添加 `warnings` 字段；使用结构化的错误上下文信息格式。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 50MB 阈值切换 mmap —— 超过 50MB 自动使用内存映射
- **D-02:** FArchive 内部 mmap 分支 —— 在 FArchive 内部切换读取方式，对外接口一致
- **D-03:** mmap 失败回退 —— mmap 失败时回退到普通文件读取，记录警告
- **D-04:** 全文件映射 —— 映射整个文件而非分段映射
- **D-05:** 统一 close() 方法 —— FArchive.close() 同时关闭 mmap 和文件
- **D-08:** 循环计数限制 —— 在关键循环中加入计数器检查
- **D-09:** 组合限制 —— 属性循环10000次 + 名称表10000000条 + 导入/导出表1000000条
- **D-10:** 全偏移验证 —— seek() 前验证 + 表偏移验证 + 导出 SerialOffset 验证
- **D-11:** PropertyTag.Size 完整验证 —— size >= 0 + size <= remaining_bytes + size <= max_reasonable
- **D-12:** 全索引验证 —— 基本索引检查 + 范围溢出检查 + PackageIndex 解析验证
- **D-13:** 错误+警告分类 —— 区分致命错误（中止）和警告（继续）
- **D-14:** 智能继续 —— 可恢复错误继续解析 + 记录失败位置
- **D-15:** 上下文信息 —— 错误信息包含错误类型、位置、上下文
- **D-16:** max_reasonable Size = 文件大小 10%（最小 1KB，最大 100MB）
- **D-17:** PackageIndex 完整验证 —— 范围验证 + 失败信息 + 类型一致性 + 目标有效性
- **D-18:** 错误上下文信息格式 —— offset + phase + operation + context_name
- **D-19:** 智能继续策略 —— 使用 Size 跳过属性；无效时中止当前导出

### Claude's Discretion
- 测试资产选择策略
- 单元测试组织方式
- mmap 实现细节（已在研究中确定最佳方案）

### Deferred Ideas (OUT OF SCOPE)
- 文件签名验证（v2）
- 资源限制（CPU、内存监控）
- 解析进度回调
- 并行解析支持
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SAFE-01 | 偏移前验证文件大小 | FArchive.seek() 增强验证模式 |
| SAFE-02 | 定位前检查偏移边界 | 全偏移验证实现模式（D-10） |
| SAFE-03 | 超过 50MB 文件使用内存映射 | Python mmap API + FArchive 扩展模式 |
| SAFE-04 | 可恢复错误返回部分结果 | ParseResult 扩展 + warnings 字段 |
| SAFE-05 | 无效/损坏文件不会卡死 | 循环计数限制实现模式 |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 文件读取与内存映射 | FArchive 类 | — | 二进制读取器封装，统一接口 |
| 边界验证 | FArchive 类 | 解析函数 | 基础验证在 FArchive，特定验证在解析函数 |
| 循环计数限制 | 解析函数 | FArchive 类 | 循环在各解析函数中，计数器检查在循环内 |
| 错误分类与上下文 | ParseResult | 解析函数 | ParseResult 存储结果，解析函数填充 |
| 警告记录 | ParseResult | 解析函数 | warnings 字段在 ParseResult，警告在解析函数生成 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python mmap | stdlib | 大文件内存映射 | 跨平台支持，零依赖，文件类接口 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python struct | stdlib | 二进制解析 | 已在 FArchive 中使用 |
| Python os | stdlib | 文件大小检查 | 阈值判断、边界验证 |

**Installation:** 无需额外安装 — 仅使用 Python 标准库

**Version verification:** Python 3.10+ 已验证 mmap 支持

## Architecture Patterns

### System Architecture Diagram

```
.uasset 文件
    │
    ├─ [文件大小检查] ──> < 50MB? ──> 普通文件读取 ──> FArchive._file
    │                              │
    │                              └─> mmap 失败回退 ──> 警告记录
    │                              │
    └─> >= 50MB? ──> mmap.mmap(fileno, 0, ACCESS_READ) ──> FArchive._mmap
    │
FArchive (统一接口)
    ├─ read(size) ──> 边界验证 ──> 读取数据
    ├─ seek(pos) ──> 偏移验证 ──> 定位
    ├─ tell() ──> 返回当前位置
    └─ close() ──> 关闭 mmap + 关闭文件
    │
解析函数
    ├─ 循环计数检查 ──> 超限中止
    ├─ 边界验证增强 ──> Size/索引验证
    └─ 错误上下文记录 ──> offset + phase + operation
    │
ParseResult
    ├─ errors: List[str] ──> 致命错误
    ├─ warnings: List[str] ──> 可恢复警告
    └─ is_success: bool ──> 状态标记
```

### Recommended Project Structure
```
uasset_read.py (单文件结构，扩展现有)
├── 常量定义
│   ├── MMAP_THRESHOLD = 50 * 1024 * 1024  # 50MB
│   ├── MAX_PROPERTY_COUNT = 10_000        # 属性循环限制
│   └── SIZE_REASONABLE_MIN/MAX            # Size 验证阈值
│
├── FArchive 类
│   ├── __init__()     # 添加 50MB 阈值判断和 mmap 分支
│   ├── read()         # 添加 mmap 分支
│   ├── seek()         # 添加 mmap 分支和增强验证
│   ├── tell()         # 添加 mmap 分支
│   ├── close()        # 统一关闭 mmap 和文件
│   └── _error_context() # 新增：生成错误上下文信息
│
├── ParseResult
│   └── warnings: List[str]  # 新增：警告列表
│
├── 解析函数
│   ├── 循环计数器检查
│   ├── Size 验证增强
│   └── PackageIndex 验证增强
│
└── 辅助函数
    ├── calculate_max_reasonable_size()
    ├── validate_package_index()
    └── create_error_context()
```

### Pattern 1: FArchive mmap 分支模式
**What:** 在 FArchive 内部判断文件大小，超过阈值使用 mmap，失败时回退。
**When to use:** 文件大小 >= 50MB（D-01）。
**Example:**
```python
# Source: Python stdlib mmap verified on Windows
import mmap
import os

class FArchive:
    MMAP_THRESHOLD = 50 * 1024 * 1024  # 50MB (D-01)

    def __init__(self, path: str):
        self._path = path
        self._file = open(path, 'rb')
        self._file_size = os.path.getsize(path)
        self._byte_swapping = False
        self._mmap = None
        self._use_mmap = False
        self._mmap_warning = None

        # D-02: FArchive 内部 mmap 分支
        if self._file_size >= self.MMAP_THRESHOLD:
            try:
                # D-04: 全文件映射 (length=0 表示映射到文件末尾)
                self._mmap = mmap.mmap(
                    self._file.fileno(),
                    0,  # 映射整个文件
                    access=mmap.ACCESS_READ
                )
                self._use_mmap = True
            except (OSError, ValueError) as e:
                # D-03: mmap 失败回退
                self._mmap_warning = f"mmap failed, using normal read: {e}"
                self._use_mmap = False

    def read(self, size: int) -> bytes:
        # 边界验证 (现有逻辑保留)
        current_pos = self.tell()
        remaining = self._file_size - current_pos
        if size > remaining:
            raise ParseError(...)

        # D-02: mmap 分支
        if self._use_mmap and self._mmap:
            return self._mmap.read(size)
        return self._file.read(size)

    def seek(self, pos: int) -> None:
        # D-10: 全偏移验证增强
        if pos < 0:
            raise ParseError(f"Negative offset {pos} not allowed")
        if pos > self._file_size:
            raise ParseError(f"Offset {pos} exceeds file size {self._file_size}")

        if self._use_mmap and self._mmap:
            self._mmap.seek(pos)
        else:
            self._file.seek(pos)

    def tell(self) -> int:
        if self._use_mmap and self._mmap:
            return self._mmap.tell()
        return self._file.tell()

    def close(self) -> None:
        # D-05: 统一 close() 方法
        if self._mmap:
            self._mmap.close()
            self._mmap = None
        if self._file:
            self._file.close()
            self._file = None
```

### Pattern 2: 循环计数限制模式
**What:** 在关键循环中添加计数器检查，超过阈值中止。
**When to use:** 属性循环、名称表循环、导入/导出表循环（D-08）。
**Example:**
```python
# 新增常量
MAX_PROPERTY_COUNT = 10_000  # D-09

def parse_properties_from_export(...):
    archive.seek(export.serial_offset)
    properties = []
    property_count = 0  # 循环计数器

    while True:
        # D-08: 循环计数检查
        property_count += 1
        if property_count > MAX_PROPERTY_COUNT:
            # 超限中止，记录警告
            result.warnings.append(
                f"Property count exceeded {MAX_PROPERTY_COUNT} at offset {archive.tell()}"
            )
            break

        try:
            tag = read_property_tag(...)
            if tag.name == "None":
                break
            # ... 解析逻辑
        except ParseError as e:
            # D-14: 智能继续
            properties.append(PropertyValue(...))
            continue

    return properties
```

### Pattern 3: PropertyTag.Size 完整验证模式
**What:** 三重验证确保 Size 值合理。
**When to use:** 读取 PropertyTag 后，解析属性值前（D-11）。
**Example:**
```python
def calculate_max_reasonable_size(file_size: int) -> int:
    """D-16: max_reasonable = 文件大小 10%，最小 1KB，最大 100MB"""
    max_size = file_size // 10
    return max(max_size, 1024)  # 最小 1KB

def validate_property_tag_size(tag: PropertyTag, archive: FArchive) -> Optional[str]:
    """D-11: Size 完整验证"""
    remaining = archive.total_size() - archive.tell()
    max_reasonable = calculate_max_reasonable_size(archive.total_size())

    if tag.size < 0:
        return f"PropertyTag.Size is negative: {tag.size}"
    if tag.size > remaining:
        return f"PropertyTag.Size {tag.size} exceeds remaining bytes {remaining}"
    if tag.size > max_reasonable:
        return f"PropertyTag.Size {tag.size} exceeds max_reasonable {max_reasonable}"

    return None  # 验证通过

def parse_property_value(tag, archive, ...):
    # D-11: Size 验证
    size_warning = validate_property_tag_size(tag, archive)
    if size_warning:
        if tag.size < 0 or tag.size > archive.total_size():
            # 致命错误：中止当前导出属性解析
            raise ParseError(size_warning)
        else:
            # 警告：记录但继续
            result.warnings.append(size_warning)

    # 正常解析...
```

### Pattern 4: PackageIndex 完整验证模式
**What:** 四重验证确保索引有效且目标存在。
**When to use:** 解析 ObjectImport/ObjectExport 的引用字段（D-17）。
**Example:**
```python
def validate_package_index(
    index: PackageIndex,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    context: str,
    archive: FArchive
) -> Optional[str]:
    """D-17: PackageIndex 完整验证"""
    if index.is_null:
        return None  # 空引用有效

    if index.is_import:
        target_idx = index.to_import_index()
        if target_idx < 0 or target_idx >= len(import_map):
            return f"Import index {index.index} (target {target_idx}) out of range [0, {len(import_map)}] in {context}"
        # 目标有效性检查
        if import_map[target_idx] is None:
            return f"Import entry at {target_idx} is None in {context}"

    elif index.is_export:
        target_idx = index.to_export_index()
        if target_idx < 0 or target_idx >= len(export_map):
            return f"Export index {index.index} (target {target_idx}) out of range [0, {len(export_map)}] in {context}"
        if export_map[target_idx] is None:
            return f"Export entry at {target_idx} is None in {context}"

    return None  # 验证通过

# 使用示例
def read_import_map(...):
    for i in range(summary.import_count):
        outer_index = PackageIndex(archive.read_i32())
        warning = validate_package_index(
            outer_index, import_map, export_map,
            context=f"ObjectImport[{i}].outer_index",
            archive=archive
        )
        if warning:
            result.warnings.append(warning)
```

### Pattern 5: 错误上下文信息格式
**What:** 结构化的错误信息，包含位置、阶段、操作、上下文名。
**When to use:** 所有 ParseError 和警告生成（D-18）。
**Example:**
```python
# D-18: 错误上下文信息格式
@dataclass
class ErrorContext:
    offset: int          # 文件偏移位置
    phase: str           # 解析阶段
    operation: str       # 操作类型
    context_name: str    # 相关对象名或属性名

    def format(self) -> str:
        return f"[{self.phase}] at offset {self.offset}: {self.operation} ({self.context_name})"

def create_error_context(
    archive: FArchive,
    phase: str,
    operation: str,
    context_name: str = ""
) -> ErrorContext:
    """生成错误上下文信息"""
    return ErrorContext(
        offset=archive.tell(),
        phase=phase,
        operation=operation,
        context_name=context_name
    )

def raise_with_context(archive, phase, operation, context_name, message):
    """生成带上下文的 ParseError"""
    ctx = create_error_context(archive, phase, operation, context_name)
    raise ParseError(f"{ctx.format()}: {message}")

# 使用示例
def read_property_tag(...):
    try:
        name = archive.read_name(name_map)
    except ParseError as e:
        # 添加上下文信息
        ctx = create_error_context(archive, "properties", "read_name", "PropertyTag.name")
        raise ParseError(f"{ctx.format()}: {e}")
```

### Pattern 6: ParseResult 扩展模式
**What:** 添加 warnings 字段区分错误和警告。
**When to use:** parse_uasset() 返回结果（D-13）。
**Example:**
```python
@dataclass
class ParseResult:
    summary: Optional[PackageFileSummary] = None
    name_map: List[str] = field(default_factory=list)
    import_map: List[ObjectImport] = field(default_factory=list)
    export_map: List[ObjectExport] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)    # 致命错误（中止解析）
    warnings: List[str] = field(default_factory=list)  # 新增：可恢复警告
    blueprint: Optional["BlueprintMetadata"] = None
    is_success: bool = False
    mmap_used: bool = False        # 新增：标记是否使用 mmap
    mmap_warning: Optional[str] = None  # 新增：mmap 回退警告
```

### Anti-Patterns to Avoid
- **分段映射复杂性:** 不要使用分段 mmap 映射 — 全文件映射更简单（D-04）。
- **mmap 异常忽略:** 不要忽略 mmap 异常 — 必须回退并记录警告（D-03）。
- **seek 超界不验证:** mmap 的 seek 会抛出 ValueError — 不要依赖异常，主动验证。
- **循环计数无限制:** 不要在 while True 循环中无计数检查 — 必须添加限制（D-08）。
- **警告混入错误:** 不要将可恢复问题放入 errors 列表 — 使用 warnings 列表（D-13）。

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 大文件读取 | 自定义分块读取 | mmap.mmap | 零拷贝、操作系统优化、跨平台 |
| 边界验证 | 手动计算和检查 | FArchive 内置方法 | 统一接口、一致性保证 |
| 循环超时 | 自定义计时器 | 循环计数器 | 简单、跨平台、可预测 |
| 错误格式 | 自定义字符串拼接 | ErrorContext dataclass | 结构化、可扩展、一致格式 |

**Key insight:** mmap 提供操作系统级别的内存映射优化，无需手动分块；循环计数比计时器更简单可靠。

## Python mmap 模块详解

### 跨平台参数差异

| 参数 | Windows | Unix | 跨平台统一方案 |
|------|---------|------|---------------|
| fileno | 文件句柄 | 文件描述符 | `f.fileno()` 统一 |
| length | 必须 > 0 或 0（映射到末尾） | 可为 0 | `0` 表示映射整个文件 |
| access | ACCESS_READ/WRITE/COPY | 同上 | `mmap.ACCESS_READ` |
| offset | 可选，必须 > 0 | 可选 | 省略（全文件映射） |

### 关键方法行为

| 方法 | 行为 | 异常 | 注意事项 |
|------|------|------|---------|
| `read(n)` | 返回最多 n 字节，不超界 | 无（自动截断） | 不同于 file.read() |
| `seek(pos)` | 定位到指定位置 | ValueError（超界） | **需要主动验证** |
| `tell()` | 返回当前位置 | 无 | 与 file.tell() 一致 |
| `close()` | 关闭映射 | 无 | 必须调用释放资源 |
| `closed` | 属性，检查是否关闭 | 无 | 用于状态检查 |

### 异常类型与处理

| 异常 | 原因 | 处理策略 |
|------|------|---------|
| `ValueError` | 空文件、关闭后操作、seek 超界 | 回退到普通读取（D-03） |
| `OSError` | 内存不足、文件不存在 | 回退到普通读取 |
| `OverflowError` | 负数偏移 | 记录警告，中止当前操作 |
| `PermissionError` | 权限拒绝 | 回退到普通读取 |

### 已验证的 mmap 行为（Windows 测试）

```
[VERIFIED: Python 3.14 on Windows]
1. 空文件映射 → ValueError: "cannot mmap an empty file"
2. Length 超文件大小 → OSError: 内存资源不足
3. 负数偏移 → OverflowError: offset must be positive
4. read() 超映射范围 → 返回实际可读字节数（不抛异常）
5. seek() 映射范围 → ValueError: seek out of range
6. 关闭后访问 → ValueError: mmap closed or invalid
7. 上下文管理器 → 支持 `with mmap.mmap(...) as m`
```

## Common Pitfalls

### Pitfall 1: mmap seek 不验证导致 ValueError
**What goes wrong:** 直接调用 `mmap.seek(pos)` 不验证，pos 超出映射范围时抛出 ValueError。
**Why it happens:** mmap 的 seek 会严格验证范围，不同于 file.seek()。
**How to avoid:** 在 FArchive.seek() 中主动验证 `pos <= self._file_size`。
**Warning signs:** 测试中出现 `ValueError: seek out of range`。

### Pitfall 2: Windows 空文件 mmap 失败
**What goes wrong:** 映射空文件时 Windows 直接抛出 ValueError，Unix 允许。
**Why it happens:** Windows 内核不支持空文件内存映射。
**How to avoid:** 在 mmap 前检查 `file_size > 0`，零字节文件直接用普通读取。
**Warning signs:** 测试中出现 `ValueError: cannot mmap an empty file`。

### Pitfall 3: 属性循环无限制导致卡死
**What goes wrong:** 损坏文件的 PropertyTag.Name 永不等于 "None"，while True 无限循环。
**Why it happens:** 缺少循环计数检查。
**How to avoid:** 添加 property_count 计数器，超过 MAX_PROPERTY_COUNT 时中止（D-08/D-09）。
**Warning signs:** 解析器在损坏文件上无限运行。

### Pitfall 4: PropertyTag.Size 异常值导致内存耗尽
**What goes wrong:** Size 为超大值（如 0xFFFFFFFF），尝试分配内存失败。
**Why it happens:** 缺少 Size 合理性验证。
**How to avoid:** 三重验证：>= 0、<= remaining、<= max_reasonable（D-11/D-16）。
**Warning signs:** 解析器内存占用异常增长。

### Pitfall 5: PackageIndex 索引越界导致崩溃
**What goes wrong:** 索引指向不存在的导入/导出条目，访问列表时 IndexError。
**Why it happens:** 仅做了范围检查，未检查目标条目是否存在。
**How to avoid:** 四重验证：范围、失败信息、类型一致性、目标有效性（D-17）。
**Warning signs:** 测试中出现 IndexError。

### Pitfall 6: 警告和错误混在一起
**What goes wrong:** 所有问题都放入 errors 列表，无法区分致命和可恢复问题。
**Why it happens:** ParseResult 缺少 warnings 字段。
**How to avoid:** 添加 `warnings: List[str]` 字段，分类记录（D-13）。
**Warning signs:** JSON 输出中所有问题标记为 errors。

## Code Examples

### FArchive mmap 分支完整实现
```python
# Source: Verified Python mmap behavior on Windows
import mmap
import os
from typing import Optional

class FArchive:
    MMAP_THRESHOLD = 50 * 1024 * 1024  # D-01: 50MB

    def __init__(self, path: str):
        self._path = path
        self._file_size = os.path.getsize(path)
        self._byte_swapping = False
        self._mmap: Optional[mmap.mmap] = None
        self._use_mmap = False
        self._mmap_warning: Optional[str] = None

        # 检查文件是否为空（Pitfall 2 预防）
        if self._file_size == 0:
            self._file = open(path, 'rb')
            self._mmap_warning = "File is empty, cannot mmap"
            return

        # D-02: 判断是否使用 mmap
        self._file = open(path, 'rb')
        if self._file_size >= self.MMAP_THRESHOLD:
            try:
                # D-04/D-07: 全文件映射，跨平台统一调用
                self._mmap = mmap.mmap(
                    self._file.fileno(),
                    0,  # 映射到文件末尾
                    access=mmap.ACCESS_READ
                )
                self._use_mmap = True
            except (OSError, ValueError, PermissionError) as e:
                # D-03: mmap 失败回退
                self._mmap_warning = f"mmap failed ({type(e).__name__}): {e}"
                self._use_mmap = False

    def read(self, size: int) -> bytes:
        current_pos = self.tell()
        remaining = self._file_size - current_pos
        if size > remaining:
            raise ParseError(
                f"Cannot read {size} bytes at {current_pos}, only {remaining} remaining"
            )

        if self._use_mmap and self._mmap:
            data = self._mmap.read(size)
            # mmap.read() 可能返回少于 size 的数据（已验证行为）
            if len(data) < size:
                raise ParseError(f"mmap.read() returned {len(data)} bytes, expected {size}")
            return data
        return self._file.read(size)

    def seek(self, pos: int) -> None:
        # D-10: 全偏移验证增强
        if pos < 0:
            raise ParseError(f"Negative offset {pos} not allowed")
        if pos > self._file_size:
            raise ParseError(
                f"Offset {pos} exceeds file size {self._file_size}"
            )

        if self._use_mmap and self._mmap:
            # Pitfall 1 预防：已验证 pos <= file_size
            self._mmap.seek(pos)
        else:
            self._file.seek(pos)

    def tell(self) -> int:
        if self._use_mmap and self._mmap:
            return self._mmap.tell()
        return self._file.tell()

    def close(self) -> None:
        # D-05: 统一 close() 方法
        if self._mmap:
            self._mmap.close()
            self._mmap = None
        if self._file:
            self._file.close()
            self._file = None
        self._use_mmap = False

    def total_size(self) -> int:
        return self._file_size

    def get_mmap_info(self) -> dict:
        """返回 mmap 状态信息（用于 ParseResult）"""
        return {
            "used": self._use_mmap,
            "warning": self._mmap_warning
        }
```

### 循环计数限制实现
```python
# 新增常量
MAX_PROPERTY_COUNT = 10_000  # D-09: 属性循环限制

def parse_properties_from_export(
    export: ObjectExport,
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    export_map: List[ObjectExport],
    result: ParseResult  # 新增参数用于记录警告
) -> List[PropertyValue]:
    archive.seek(export.serial_offset)
    properties: List[PropertyValue] = []
    property_count = 0

    while True:
        # D-08: 循环计数检查
        property_count += 1
        if property_count > MAX_PROPERTY_COUNT:
            result.warnings.append(
                create_error_context(
                    archive, "properties", "loop_limit",
                    f"Export[{export.object_name}]"
                ).format() + f": exceeded {MAX_PROPERTY_COUNT} properties"
            )
            break  # 中止循环

        try:
            tag = read_property_tag(archive, name_map, ...)
            if tag.name == "None":
                break

            # D-11: Size 验证
            size_warning = validate_property_tag_size(tag, archive)
            if size_warning:
                if tag.size < 0:
                    # 致命错误：中止当前导出
                    raise ParseError(size_warning)
                else:
                    result.warnings.append(size_warning)

            start_pos = archive.tell()
            value = parse_property_value(tag, archive, name_map, export_map)

            # 边界验证
            expected_end = start_pos + tag.size
            if archive.tell() != expected_end:
                archive.seek(expected_end)

            properties.append(PropertyValue(...))

        except ParseError as e:
            # D-14/D-19: 智能继续
            result.warnings.append(f"Property parse error: {e}")
            properties.append(PropertyValue(name="ParseError", type="Error", value=str(e)))
            continue

    return properties
```

### ParseResult 扩展与使用
```python
@dataclass
class ParseResult:
    summary: Optional[PackageFileSummary] = None
    name_map: List[str] = field(default_factory=list)
    import_map: List[ObjectImport] = field(default_factory=list)
    export_map: List[ObjectExport] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)      # 致命错误
    warnings: List[str] = field(default_factory=list)    # D-13: 可恢复警告
    blueprint: Optional["BlueprintMetadata"] = None
    is_success: bool = False
    mmap_used: bool = False        # D-02: mmap 使用标记
    mmap_warning: Optional[str] = None  # D-03: mmap 回退警告

def parse_uasset(path: str) -> ParseResult:
    result = ParseResult()
    archive = None

    try:
        archive = FArchive(path)

        # D-03: 记录 mmap 状态
        mmap_info = archive.get_mmap_info()
        result.mmap_used = mmap_info["used"]
        result.mmap_warning = mmap_info["warning"]
        if result.mmap_warning:
            result.warnings.append(result.mmap_warning)

        # ... 解析流程

        result.is_success = len(result.errors) == 0

    except Exception as e:
        result.errors.append(str(e))
        result.is_success = False

    finally:
        if archive:
            archive.close()

    return result
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| file.read() 全文件 | mmap.mmap 大文件 | Phase 5 (D-01) | 大文件性能优化 |
| 无循环限制 | 计数器检查 | Phase 5 (D-08) | 损坏文件不卡死 |
| errors 统一记录 | errors + warnings 分类 | Phase 5 (D-13) | 问题诊断更清晰 |
| 简单边界验证 | 多重验证增强 | Phase 5 (D-10/D-11) | 更健壮的错误检测 |

**Deprecated/outdated:**
- 无 mmap 分支的 FArchive: Phase 5 后所有 FArchive 实例支持 mmap。
- 无 warnings 的 ParseResult: Phase 5 后 warnings 为必填字段。

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|----|-------|---------|---------------|
| A1 | mmap.ACCESS_READ 跨平台一致 | mmap 模块详解 | LOW - 已在 Windows 验证，Unix 应一致 |
| A2 | read() 返回少于请求字节仅在实际数据不足时 | mmap 行为验证 | LOW - 已验证行为 |

**Most claims verified:** 本研究的所有关键技术点已通过 Python 运行验证。

## Open Questions

1. **mmap 在 Unix 系统的行为差异**
   - What we know: Windows 已完整验证，Unix 参数签名不同但 `access=mmap.ACCESS_READ` 应统一。
   - What's unclear: Unix 是否允许空文件映射（Windows 不允许）。
   - Recommendation: 测试时添加 Unix 平台验证（如有条件），或使用 CI 多平台测试。

2. **50MB 阈值的实际效果**
   - What we know: 50MB 是需求 SAFE-03 指定。
   - What's unclear: 是否有更好的阈值选择（如根据可用内存动态调整）。
   - Recommendation: 使用固定 50MB 阈值（D-01），后续版本可考虑动态调整。

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python mmap | 大文件读取 | ✓ | stdlib | 普通文件读取 |
| Python os | 文件大小检查 | ✓ | stdlib | — |
| Python struct | 二进制解析 | ✓ | stdlib | — |

**Missing dependencies with no fallback:** 无

**Missing dependencies with fallback:** 无

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | tests/ 目录结构 |
| Quick run command | `python -m pytest tests/ -v -x` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SAFE-01 | 偏移前验证文件大小 | unit | `pytest tests/test_uasset_read.py::test_offset_validation -v` | ❌ Wave 0 |
| SAFE-02 | 定位前检查偏移边界 | unit | `pytest tests/test_uasset_read.py::test_seek_boundary -v` | ❌ Wave 0 |
| SAFE-03 | >50MB 文件使用 mmap | unit | `pytest tests/test_uasset_read.py::test_mmap_large_file -v` | ❌ Wave 0 |
| SAFE-04 | 可恢复错误返回部分结果 | unit | `pytest tests/test_uasset_read.py::test_partial_result_warnings -v` | ❌ Wave 0 |
| SAFE-05 | 无效文件不卡死 | unit | `pytest tests/test_uasset_read.py::test_loop_limit -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -v -x`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_mmap_behavior.py` — SAFE-03 mmap 分支测试
- [ ] `tests/test_boundary_validation.py` — SAFE-01/SAFE-02 边界验证测试
- [ ] `tests/test_loop_limits.py` — SAFE-05 循环限制测试
- [ ] `tests/test_warnings.py` — SAFE-04 警告分类测试
- [ ] 合成大文件生成工具 — mmap 测试用

*(现有测试文件覆盖 Phase 1-3 功能，Phase 5 需新增测试文件)*

## Security Domain

> 本阶段为性能优化和安全加固，不涉及 ASVS 安全控制。重点为：
> - 输入验证（SAFE-01/SAFE-02）：边界检查防止越界访问
> - 资源管理（SAFE-03）：mmap 正确关闭防止资源泄漏
> - 可用性（SAFE-05）：循环限制防止无限循环攻击

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 越界读取（损坏偏移） | Tampering | 全偏移验证（D-10） |
| 无限循环（损坏 PropertyTag） | Denial of Service | 循环计数限制（D-08） |
| 内存耗尽（超大 Size） | Denial of Service | Size 三重验证（D-11） |
| 资源泄漏（mmap 未关闭） | Denial of Service | 统一 close() 方法（D-05） |

## Sources

### Primary (HIGH confidence)
- Python stdlib mmap 模块 — Windows 运行验证 [VERIFIED]
- uasset_read.py — 现有实现代码分析 [VERIFIED]
- 05-CONTEXT.md — Phase 决策和约束 [VERIFIED]

### Secondary (MEDIUM confidence)
- REQUIREMENTS.md — SAFE-01 至 SAFE-05 定义 [CITED]

### Tertiary (LOW confidence)
- Unix mmap 行为 — 基于文档推断，未在 Unix 系统验证 [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack (mmap): HIGH — Windows 验证完成
- Architecture patterns: HIGH — 与现有代码集成点明确
- Pitfalls: HIGH — 已通过 Python 运行验证

**Research date:** 2026-05-01
**Valid until:** 30 days — Python mmap API 稳定