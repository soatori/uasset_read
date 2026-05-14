# PLAN: Phase 44b — 替换直接字节读取

**Phase:** 44b  
**Goal:** 消除所有绕过 FArchive 的直接 `struct.unpack` 调用  
**Type:** cleanup / refactor

## Context

代码库中存在 2 处 `struct.unpack` 调用绕过了 FArchive 的字节序管理：
1. `property_types.py:60` — Int16 读取使用 `struct.unpack('<h', ...)`
2. `graph.py:613-616` — 颜色分量读取使用 `struct.unpack('<f', ...)` × 4

`archive.py` 内部的 `struct.unpack` 调用是 FArchive 自身的实现，属于正常保留。

---

## Tasks

### 44b-T1: `archive.py` — 添加 `read_i16()` 方法

文件：`src/uasset_read/archive.py`

在 `read_u16()` 方法（第 171-175 行）之后添加：

```python
def read_i16(self) -> int:
    """读取 signed 16-bit integer（支持字节交换）"""
    import struct
    fmt = '>' if self._byte_swapping else '<'
    return struct.unpack(fmt + 'h', self.read(2))[0]
```

**说明：** 这是 FArchive 内部的 struct.unpack 使用 — 允许保留，因为 FArchive 本身就是字节序管理的底层。

**完成标准：** `archive.read_i16()` 方法存在且遵循其他 `read_*` 方法的模式

---

### 44b-T2: `property_types.py` — Int16 改用 `archive.read_i16()`

文件：`src/uasset_read/parsers/property_types.py`

第 58-60 行：
```python
elif type_name == "Int16Property":
    # TODO: 使用UE编辑器源码的加载方式替换实现代码
    return struct.unpack('<h', archive.read(2))[0]  # TODO: 使用UE编辑器方式读取Int16
```

改为：
```python
elif type_name == "Int16Property":
    return archive.read_i16()
```

然后检查 `import struct` 是否仍在文件中被使用：
```
grep -n 'struct\.' src/uasset_read/parsers/property_types.py
```
- 如无其他用途 → 删除 `import struct`（第 10 行）
- 如仍有其他用途 → 保留

**完成标准：** 文件中无 `struct.unpack` 调用

---

### 44b-T3: `graph.py` — 颜色分量读取改用 `archive.read_f32()`

文件：`src/uasset_read/serializers/graph.py`

第 609-616 行：
```python
# TODO: 使用UE编辑器源码的加载方式替换实现代码
参考 UE C++ EdGraphNode::SerializeComment() 实现
"""
# TODO: 使用UE编辑器源码的加载方式替换实现代码
r = struct.unpack('<f', archive.read(4))[0]  # TODO: 使用UE编辑器方式读取颜色分量
g = struct.unpack('<f', archive.read(4))[0]  # TODO: 使用UE编辑器方式读取颜色分量
b = struct.unpack('<f', archive.read(4))[0]  # TODO: 使用UE编辑器方式读取颜色分量
a = struct.unpack('<f', archive.read(4))[0]  # TODO: 使用UE编辑器方式读取颜色分量
```

改为：
```python
r = archive.read_f32()
g = archive.read_f32()
b = archive.read_f32()
a = archive.read_f32()
```

然后清理 TODO 注释和文件顶部的 `import struct`（如不再有其他用途）：
```
grep -n 'struct\.' src/uasset_read/serializers/graph.py
```

**完成标准：** 文件中无 `struct.unpack` 调用

---

### 44b-T4: 回归测试

```bash
python -m pytest tests/ -v --tb=short
```

**完成标准：** 基线 373 passed（允许已知 pre-existing failures）

---

### 44b-T5: 最终验证

```bash
grep -rn 'struct.unpack' src/
```

**完成标准：** 仅返回 `archive.py` 内部实现行

---

## Execution Order

1. **Wave 1:** 44b-T1（前提：添加 `read_i16()` 方法）
2. **Wave 2:** 44b-T2, 44b-T3（依赖 T1 完成，可并行执行）
3. **Wave 3:** 44b-T4, 44b-T5（验证）

## Success Criteria

1. `grep -rn 'struct.unpack' src/` 仅返回 `archive.py` 内部实现
2. 所有测试通过（基线 373 passed）
3. `uasset-read` 对 BP_FirstPersonCharacter.uasset 完整解析成功

## Risks

- **低风险：** 改动仅限于调用替换，FArchive 的 `read_f32()` 和新增的 `read_i16()` 使用相同的字节序逻辑
- **低风险：** 颜色分量读取通常不涉及字节序问题（UE 蓝图节点注释颜色是小端），`read_f32()` 正确处理字节序
- **低风险：** Int16 属性在 UE5 蓝图中较少使用，但 `read_i16()` 与 `read_i32`/`read_u16` 模式一致
