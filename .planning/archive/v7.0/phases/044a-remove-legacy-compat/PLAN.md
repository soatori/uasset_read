# Phase 44a: 执行计划

## Wave 0: 验证清理范围

### Task 0.1: 验证 UE4 兼容代码不存在
**Action**: 运行 grep 命令验证代码已干净
**Command**: `grep -rn 'is_ue4_file\|UE4_\|legacy_file_version >' src/`
**Expected**: 0 结果（已验证）

### Task 0.2: 确认 `read_bool()` 使用情况
**Action**: 搜索所有 `read_bool()` 调用位置
**Files**: `archive.py`, `graph.py`, `object_resources.py`
**Count**: ~20+ 处调用

**Decision**: 根据研究结果，实际需要清理的范围很小：
- 代码已声明"UE5.7 专用"
- 无 UE4 条件分支代码
- 仅需处理 `read_bool()` 方法命名

## Wave 1: bool 方法重构

### Task 1.1: 重命名 bool 方法（`archive.py`）
**File**: `src/uasset_read/archive.py`
**Changes**:
1. 删除 `read_bool()` 方法（第 183-185 行）
2. 将 `read_bool_ue5()` 重命名为 `read_bool()`（第 187-193 行）
3. 更新方法注释：明确说明这是 UE5 专用方法（序列化为 uint8，1 byte）

**Rationale**: 
- UE5 使用 1-byte bool 序列化
- 当前 `read_bool()` 实际是 UE4 格式（4-byte uint32）
- 所有调用点应使用 UE5 的 1-byte bool

### Task 1.2: 更新调用点（无需修改）
**Files**: `graph.py`, `object_resources.py`, 其他
**Action**: 无需修改（`read_bool()` 名称不变）
**Rationale**: 方法重命名后，现有调用继续工作

## Wave 2: 验证与测试

### Task 2.1: 运行测试套件
**Command**: `python -m pytest tests/ -v`
**Expected**: 全部通过（无回归）

### Task 2.2: 验证 UE5 资产解析
**Action**: 使用 FirstPerson 示例资产验证解析正常
**Files**: `E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset`
**Expected**: 解析成功，输出格式不变

## Wave 3: 文档更新（可选）

### Task 3.1: 更新 API 文档（可选）
**File**: `CLAUDE.md` 或 `README.md`
**Action**: 说明 `read_bool()` 为 UE5 专用方法
**Priority**: 低（内部 API，用户不直接调用）

## Summary

Phase 44a 是一个小型清理任务，主要工作是重构 `archive.py` 的 bool 读取方法。

执行时间估计：~5-10 分钟（单个文件修改 + 测试）

**Dependencies**: 无（Phase 44 已完成）

**Risk**: 低（方法重命名，调用点无需修改）

*Created: 2026-05-14*