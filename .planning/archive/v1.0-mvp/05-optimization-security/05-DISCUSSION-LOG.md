# Phase 5: 优化与安全 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 05-optimization-security
**Areas discussed:** 大文件处理策略, 超时与卡死防护, 边界验证增强, 部分结果改进

---

## 大文件处理策略

### 大文件阈值

| Option | Description | Selected |
|--------|-------------|----------|
| 50MB（需求指定） | REQUIREMENTS.md SAFE-03 指定的阈值，常见大文件分界线 | ✓ |
| 10MB | 更激进的优化，更多文件使用 mmap，但可能增加复杂性 | |
| 100MB | 仅对真正大文件优化，减少切换逻辑复杂性 | |

**User's choice:** 50MB（需求指定）
**Notes:** 阶段 1 D-02 已决定阶段 5 添加 MappedArchive 支持

### mmap 实现方式

| Option | Description | Selected |
|--------|-------------|----------|
| FArchive 内部 mmap 分支（推荐） | 代码复用更好，FArchive 内部切换读取方式，对外接口一致 | ✓ |
| 独立 MappedArchive 类 | 独立 MappedArchive 类继承 FArchive，更清晰的分离，但增加类数量 | |
| 仅分段解析无 mmap | 不切换实现，仅对大文件限制读取范围（分段解析），简化实现 | |

**User's choice:** FArchive 内部 mmap 分支（推荐）

### mmap 失败回退

| Option | Description | Selected |
|--------|-------------|----------|
| 回退到普通读取（推荐） | mmap 失败时回退到普通文件读取，保证解析继续，记录警告 | ✓ |
| 返回错误/部分结果 | mmap 失败视为解析错误，返回部分结果 | |
| 拒绝解析大文件 | 要求大文件必须 mmap，失败则拒绝解析 | |

**User's choice:** 回退到普通读取（推荐）

### mmap 映射范围

| Option | Description | Selected |
|--------|-------------|----------|
| 全文件映射（推荐） | 整个文件映射，简单直接，适合大多数情况 | ✓ |
| 分段映射（滑动窗口） | 仅映射当前读取区域，节省内存但增加复杂性，适合超大文件 | |
| 头部+活跃区映射 | 映射文件头+活跃解析区域，平衡内存和性能 | |

**User's choice:** 全文件映射（推荐）

### mmap 资源释放

| Option | Description | Selected |
|--------|-------------|----------|
| 统一 close() 方法 | FArchive.close() 同时关闭 mmap 和文件，简单一致 | ✓ |
| 单独 unmap() 方法 | 提供单独的 unmap() 方法，允许提前释放映射，保持文件打开 | |

**User's choice:** 统一 close() 方法

### 大文件测试策略

| Option | Description | Selected |
|--------|-------------|----------|
| 合成大文件测试 | 使用 pytest fixture 生成大文件，验证 mmap 分支逻辑 | |
| 真实大文件测试 | 找到或创建真实 >50MB .uasset 文件测试 | |
| 合成+真实组合 | 合成测试 mmap 分支，真实文件验证回退逻辑 | ✓ |

**User's choice:** 合成+真实组合

### mmap 跨平台处理

| Option | Description | Selected |
|--------|-------------|----------|
| 统一 mmap 调用 | Python mmap 跨平台，仅需处理大小限制差异 | ✓ |
| 平台特定分支 | Windows/Linux/macOS 分别处理 mmap 参数差异 | |

**User's choice:** 统一 mmap 调用

---

## 超时与卡死防护

### 超时实现机制

| Option | Description | Selected |
|--------|-------------|----------|
| 信号/Alarm 超时 | 信号中断主循环，Unix 仅限主线程，Windows 需要特殊处理 | |
| 线程超时 | 解析在子线程运行，主线程监控超时后终止，跨平台但复杂 | |
| 循环计数限制（推荐） | 在关键循环中加入计数器检查，超过阈值则中止，简单但不够精确 | ✓ |

**User's choice:** 循环计数限制（推荐）

### 循环计数阈值

| Option | Description | Selected |
|--------|-------------|----------|
| 属性循环10000次 | 限制属性循环最多10000次，防止无限属性解析 | |
| 表大小限制（已实现） | 限制名称表最多10000000条，导入/导出表最多1000000条（已实现） | |
| 组合限制（推荐） | 属性循环10000次 + 名称表10000000 + 导入/导出表1000000 | ✓ |

**User's choice:** 组合限制（推荐）

---

## 边界验证增强

### 偏移验证范围

| Option | Description | Selected |
|--------|-------------|----------|
| 读取前验证（已实现） | seek() 前检查 offset + size <= file_size，防止读取越界 | |
| 表偏移验证 | 解析 NameOffset/ExportOffset 前验证其是否在合理范围 | |
| 全偏移验证（推荐） | 读取前验证 + 表偏移验证 + 导出 SerialOffset 验证 | ✓ |

**User's choice:** 全偏移验证（推荐）

### PropertyTag.Size 验证

| Option | Description | Selected |
|--------|-------------|----------|
| 基本检查（已实现） | 仅检查 size >= 0，防止负数 size 导致错误 | |
| 范围检查 | 检查 size 在合理范围（如 <= file_size），防止异常大值 | |
| 完整验证（推荐） | 检查 size >= 0 + size <= remaining_bytes + size <= max_reasonable | ✓ |

**User's choice:** 完整验证（推荐）

### 索引范围验证

| Option | Description | Selected |
|--------|-------------|----------|
| 基本索引检查（已实现） | 仅检查 0 <= index < len(table)，当前 read_name() 实现 | |
| 范围溢出检查 | 检查索引 + 计数不超过表大小，防止表溢出 | |
| 全索引验证（推荐） | 基本索引检查 + 范围溢出检查 + PackageIndex 解析验证 | ✓ |

**User's choice:** 全索引验证（推荐）

---

## 部分结果改进

### 错误级别分类

| Option | Description | Selected |
|--------|-------------|----------|
| 单一错误级别 | 所有错误同等对待，记录到 errors 列表 | |
| 错误+警告分类（推荐） | 区分致命错误（中止解析）和警告（继续解析），记录到不同列表 | ✓ |
| 三级分类 | 错误、警告、信息三个级别，更细粒度控制 | |

**User's choice:** 错误+警告分类（推荐）

### 解析失败继续策略

| Option | Description | Selected |
|--------|-------------|----------|
| 立即中止 | 任何解析失败立即中止，返回已解析部分 | |
| 可恢复继续（已实现） | 可恢复错误（单属性失败）继续解析，致命错误（文件头损坏）中止 | |
| 智能继续（推荐） | 可恢复继续 + 记录失败位置 + 尝试跳过到下一个有效点 | ✓ |

**User's choice:** 智能继续（推荐）

### 错误信息详细程度

| Option | Description | Selected |
|--------|-------------|----------|
| 简洁信息 | 仅包含错误类型和位置，简洁但不够详细 | |
| 上下文信息（推荐） | 包含错误类型、位置、上下文（如当前解析阶段、偏移） | ✓ |
| 详细建议信息 | 包含错误类型、位置、上下文、建议修复方案 | |

**User's choice:** 上下文信息（推荐）

---

## Claude's Discretion 具体化讨论 (2026-05-01 更新)

以下领域用户选择让 Claude 自行决定具体实现，现已具体化：

### max_reasonable Size 阈值

| Option | Description | Selected |
|--------|-------------|----------|
| 1MB 固定阈值 | 保守阈值，单个属性最大 1MB（适用于大多数属性） | |
| 文件大小 10%（动态） | 动态计算，适应不同大小文件 | ✓ |
| 10MB 固定阈值 | 保守固定阈值 10MB，覆盖大型结构体属性 | |
| 仅检查越界 | 不设 max_reasonable 限制，仅检查 remaining_bytes | |

**User's choice:** 文件大小 10%（动态）
**Notes:** 最小 1KB，最大 100MB，防止异常大 PropertyTag.Size 值

### PackageIndex 解析验证维度

| Option | Description | Selected |
|--------|-------------|----------|
| 范围验证（已实现） | 基础范围检查：0 <= index < len(map) | ✓ |
| 失败信息记录 | 记录失败的 PackageIndex 信息（原始值、目标表、解析位置） | ✓ |
| 类型一致性检查 | 引用对象类型与期望类型匹配检查 | ✓ |
| 目标对象有效性 | 验证 PackageIndex 指向的对象确实存在 | ✓ |

**User's choice:** 全部 4 个维度
**Notes:** 完整验证策略，覆盖范围、信息记录、类型一致性、目标有效性

### 错误信息上下文字段

| Option | Description | Selected |
|--------|-------------|----------|
| 偏移位置 (offset) | 错误发生时的文件偏移位置 | ✓ |
| 解析阶段 (phase) | 当前解析阶段（header、name_table、import_map 等） | ✓ |
| 操作类型 (operation) | 失败的具体操作（read_i32、read_name、seek 等） | ✓ |
| 上下文对象名 (context_name) | 相关的对象名或属性名 | ✓ |

**User's choice:** 全部 4 个字段
**Notes:** 丰富的错误上下文帮助定位问题

### 智能继续策略

| Option | Description | Selected |
|--------|-------------|----------|
| 按 Size 跳过属性（推荐） | 使用 PropertyTag.Size 跳过当前属性，继续下一个 | ✓ |
| 立即中止 | 遇到错误立即中止解析，返回已收集的数据 | |
| 扫描 'None' 标记 | 扫描寻找下一个 'None' FName 终止标记（启发式） | |
| 不跳过，继续解析 | 记录错误位置，不尝试跳过 | |

**User's choice:** 按 Size 跳过属性（推荐）
**Notes:** 当 Size 无效（负数或越界）时中止当前导出的属性解析，尝试下一个导出

---

## Claude's Discretion (原始记录)

以下领域用户最初选择让 Claude 自行决定具体实现：

- max_reasonable Size 具体阈值选择 → 已具体化
- PackageIndex 解析验证的具体逻辑 → 已具体化
- 失败位置记录格式 → 已具体化
- 跳到下一个有效点的启发式方法 → 已具体化
- 单元测试组织和测试用例设计 → 待实现时决定

---

## Deferred Ideas

无 —— 讨论保持在阶段范围内。

---

*Phase: 05-optimization-security*
*Discussion completed: 2026-05-01*