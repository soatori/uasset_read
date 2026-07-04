# UE Source Audit Skill

## Overview

系统性地将 uasset_read 解析器实现与 UE 引擎 C++ 源码对照，发现实现差异和潜在 bug，输出结构化审计报告。

## 触发场景

当用户需要：
- 审计某个模块（FArchive/FLinkerLoad/PropertyTag 等）的解析实现是否与 UE 源码对齐
- 排查"少读字节""多读字节""偏移错位"类 bug
- 系统性输出审计报告和 issue 列表
- 对比解析器 read 顺序与 UE operator<< 的字段顺序

## 工作流

```
选择审查模块 → 读取 UE 源码 → 对照解析器实现 → 记录差异 → 分类优先级 → 输出报告/issue
```

### Step 1: 选择审查模块

UE 源码路径：`E:\Develop\lib\UnrealEngine`

常见审查目标：

| 模块 | UE 源码位置 | 解析器位置 |
|------|------------|-----------|
| FArchive | `Engine/Source/Runtime/Core/Private/Serialization/Archive.cpp` | `src/uasset_read/archive.py` |
| FLinkerLoad | `Engine/Source/Runtime/CoreUObject/Private/Serialization/LinkerLoad.cpp` | `src/uasset_read/linker.py` |
| PropertyTag | `Engine/Source/Runtime/CoreUObject/Private/Serialization/PropertyTag.cpp` | `src/uasset_read/serializers/property_tags.py` |
| PackageSummary | `Engine/Source/Runtime/CoreUObject/Private/Serialization/ObjectResource.cpp` | `src/uasset_read/serializers/package_summary.py` |
| Import/Export | `Engine/Source/Runtime/CoreUObject/Private/Serialization/ObjectResource.cpp` | `src/uasset_read/serializers/import_export.py` |
| Kismet | `Engine/Source/Runtime/Engine/Classes/Engine/EngineTypes.h` | `src/uasset_read/kismet/` |

### Step 2: 读取 UE 源码

```bash
# 找到对应源码文件
find "E:/Develop/lib/UnrealEngine" -name "LinkerLoad.cpp" -type f

# 读取关键函数
# 关注：Serialize, operator<<, LoadXxx, ReadXxx 等序列化函数
```

### Step 3: 逐字段对照

对照维度：

| 对照项 | UE 源码 | 解析器 | 判定 |
|--------|---------|--------|------|
| 字段顺序 | `operator<<` 中的读取顺序 | `read()` 中的调用顺序 | 必须一致 |
| 数据类型 | `int32`, `uint64`, `FString` 等 | `read_int32()`, `read_uint64()` 等 | 必须匹配 |
| 条件分支 | `if (Ver >= ...)` | `if version >= ...` | 必须对齐 |
| 字节数 | 每个字段的字节大小 | read 方法的字节消耗 | 必须一致 |
| 默认值 | 未显式初始化的字段 | fallback 处理 | 应当对齐 |

### Step 4: 记录差异

差异分类：

| 类型 | 说明 | 优先级 |
|------|------|--------|
| **少读字节** | 漏读了 UE 会读取的字段 | P0 |
| **多读字节** | 读取了 UE 不读取的字段 | P0 |
| **偏移错位** | 后续字段因前面的差异而错位 | P0 |
| **类型不匹配** | 读取类型与 UE 不一致 | P1 |
| **条件分支缺失** | 缺少版本门控或条件判断 | P1 |
| **默认值差异** | 未处理的 fallback 场景 | P2 |

### Step 5: 输出审计报告

保存到 `temp/ue-source-audit-findings.md`：

```markdown
# UE 源码审计报告 — {模块名}

## 审计范围
- UE 源码: `{path}`
- 解析器: `{path}`
- 审计日期: {date}

## 发现

### P0 — 少读/多读字节
1. **{字段名}** (line {UE_line} vs line {parser_line})
   - UE: 读取 {type} ({bytes} bytes)
   - 解析器: 未读取 / 读取了额外字段
   - 影响: 后续所有字段偏移 {N} bytes

### P1 — 类型/条件差异
2. ...

### P2 — 默认值/边缘情况
3. ...

## 建议修复
- Issue #N: {描述}
- Issue #N: {描述}
```

### Step 6: 批量提交 Issue

```bash
# 整理后批量提交
gh issue create --title "audit: {模块} {发现数} 项差异" \
    --body-file temp/ue-source-audit-findings.md \
    --label "audit,needs-triage"
```

## 审查原则

- **先读 UE 源码，再对照实现**：不要凭印象判断
- **明确区分差异类型**：
  - UE 等价加载输出（解析器正确）
  - tolerant extraction（有意的宽松处理）
  - partial_metadata（部分字段提取）
  - opaque（未解析的 payload）
  - fallback（未知类型的回退）
- **不要把"能解析一些字段"描述成"符合 UE 原始加载输出"**
- **重点关注**：少读/多读字节、archive 错位、错误 success 状态、raw 值被 resolved 展示覆盖
- **不要直接改 UE 源码**：只提交 issue，本地记录到 `temp/ue-source-audit-findings.md`

## 已完成审计

| 模块 | 日期 | 发现数 | 状态 |
|------|------|--------|------|
| PackageSummary | 2026-06 | 3 | 已修复（LegacyGuid + OwnerPersistentGuid + ChunkIDs） |
| Import/Export | 2026-06 | 5 | 已提交 issue |
| FString | 2026-06 | 2 | 已修复（UTF-16 LE 编码） |
