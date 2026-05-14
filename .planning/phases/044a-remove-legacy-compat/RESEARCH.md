# Phase 44a: 研究报告 — UE4/旧版本兼容代码移除

## 状态
✅ 研究完成

## 研究目标
识别所有 UE4/旧版本兼容代码，确定哪些需要删除，哪些需要保留。

## 研究方法
通过 grep 搜索关键字：
- `is_ue4_file`、`UE4_` 前缀、`legacy_file_version >` 比较运算符
- `read_bool_ue5`、`read_bool()` 方法
- 版本条件分支 `if.*version`

## 研究发现

### 1. 已移除的 UE4 兼容代码
大部分文件头部注释已声明"UE5.7 专用 — 已移除 UE4 兼容代码"：
- `package_summary.py` - 仅检查 `legacy_file_version != UE5_LEGACY_VERSION`，无 UE4 分支
- `property_tags.py` - 无版本分支
- `object_resources.py` - 注释中提到"UE5 >= X"，但无实际版本条件分支

### 2. 需要清理的代码

#### 2.1 `archive.py` - `read_bool()` 方法
**当前状态**：
- `read_bool()` - 读取 UE4 bool（序列化为 uint32，4 bytes）
- `read_bool_ue5()` - 读取 UE5 bool（序列化为 uint8，1 byte）

**问题**：
- `read_bool()` 的注释误导（提到"UE bool 值"和"序列化为 uint32，4 bytes"）
- 大部分代码使用 `read_bool()`，但实际应使用 UE5 的 1-byte bool

**建议**：
- **重命名** `read_bool_ue5()` → `read_bool()`
- **删除** 原 `read_bool()`（4-byte uint32 bool）或重命名为 `read_bool_legacy()`
- **更新所有调用点**：当前代码中 `read_bool()` 实际用于 UE5 格式，应改用 1-byte bool

#### 2.2 `json_formatter.py` - `legacy_version` 输出
**当前状态**：
- 第 49 行：输出 `"legacy_version": result.summary.legacy_file_version`
- 第 251 行：输出 `"legacy": result.summary.legacy_file_version`

**问题**：
- `legacy_file_version` 字段名称具有误导性
- 实际是 UE5 的固定值 `-8`，不是"旧版本"

**建议**：
- **保留字段**：仍需从文件头读取（用于验证）
- **可选改名**：改为 `ue5_legacy_version` 或直接使用原名称（UE 官方命名）

#### 2.3 版本条件分支 - UE5 内部版本检查
**当前状态**：
- `property_parser.py:130,137,145` - `if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET`
- `graph.py:719` - `if summary.file_version_ue5 >= 1011`

**问题**：
- 这些是 **UE5 内部版本检查**，不是 **UE4 兼容代码**
- 用于处理 UE5 不同子版本之间的格式变化

**建议**：
- **保留**：这些是 UE5 内部兼容性检查，属于当前版本支持
- **不符合删除条件**：不属于"UE4/旧版本兼容路径"

### 3. 不需要清理的代码

#### 3.1 `constants.py`
- 无 UE4_* 前缀常量
- 所有版本常量都是 UE5 相关
- **已干净**

#### 3.2 `object_resources.py` 注释
- 注释如"UE5 >= 1003 always present"是说明性注释，不是版本分支代码
- **不需要删除**

## 结论

### 需要执行的操作
1. ✅ **`archive.py`** - 重命名/重构 `read_bool()` 和 `read_bool_ue5()`
   - 建议：删除 `read_bool()`（4-byte），将 `read_bool_ue5()` 重命名为 `read_bool()`
   - 影响范围：所有调用 `read_bool()` 的代码（约 20+ 处）

2. ⚠️ **`json_formatter.py`** - 可选：改进 `legacy_version` 字段命名
   - 低优先级：字段名称是 UE 官方命名，保留即可
   - 或改名为 `ue5_file_version_legacy`（可选）

### 不需要执行的操作
- ❌ 删除 `property_parser.py` 和 `graph.py` 的版本条件分支（属于 UE5 内部版本支持）
- ❌ 删除 `constants.py` 的版本常量（都是 UE5 相关）
- ❌ 删除 `object_resources.py` 的注释（仅说明性）

## 成功标准验证
根据 CONTEXT.md 的成功标准：

```bash
grep -rn 'is_ue4_file\|UE4_\|legacy_file_version >' src/
```

**预期结果**：0 结果（已验证，当前代码中无这些模式）

## 建议

Phase 44a 的主要清理工作集中在 **`archive.py` 的 bool 读取方法**。

其他代码已经符合"UE5.7 专用"要求，不需要额外清理。

*Created: 2026-05-14*