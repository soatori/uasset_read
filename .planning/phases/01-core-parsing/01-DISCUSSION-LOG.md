# Phase 1: Core Parsing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 01-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-28
**Phase:** 01-core-parsing
**Areas discussed:** Architecture, Version Support, Testing, Data Model, Error Handling, File Layout, FString Encoding, PackageIndex Resolution, Name Table Format, BulkData, Header Fields, Version Validation, Custom Versions, PackageFlags, Endianness Detection

---

## Architecture Design

| Option | Description | Selected |
|--------|-------------|----------|
| 单一 FArchive 类 | 所有读取方法在一个类中，简单直接，适合单文件版本 | ✓ |
| 分层设计 | 类似 UE 源码模式，便于测试和扩展，代码更清晰 | |
| 最小化设计 | Phase 1 用单一类，Phase 5 添加 MappedArchive | |

**User's choice:** 单一 FArchive 类（推荐）
**Notes:** Simple is better for Phase 1 foundation

---

## Version Support

| Option | Description | Selected |
|--------|-------------|----------|
| 仅 UE 5.x | UE 5.x 格式稳定，与源码参考匹配，降低初期复杂度 | ✓ |
| UE 4.x + 5.x | 覆盖更广，但需处理更多版本差异分支 | |
| 宽松兼容 | 尝试解析所有版本，不支持的返回错误 | |

**User's choice:** 仅 UE 5.x（推荐）
**Notes:** Aligns with UE 5.7 source reference

---

## Testing Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| 单元测试 + 合成数据 | 可控的测试场景，验证边界条件，不依赖外部文件 | |
| 集成测试 + 真实 .uasset | 真实格式验证，但需要获取样本文件 | |
| 两者结合 | 双重保障，Phase 1 先单元测试，后续添加集成测试 | ✓ |

**User's choice:** 两者结合
**Notes:** Combined approach for comprehensive validation

---

## Data Model

| Option | Description | Selected |
|--------|-------------|----------|
| dataclasses | Python 3.10+ 原生支持，asdict() 直接转 JSON，类型清晰 | ✓ |
| dict-based | 更灵活，但缺少类型提示，JSON 输出需手动处理 | |
| TypedDict + 转换函数 | 可扩展性更好，但增加复杂度，Phase 1 不必要 | |

**User's choice:** dataclasses（推荐）
**Notes:** Native Python support, clean JSON serialization

---

## Error Handling

| Option | Description | Selected |
|--------|-------------|----------|
| 验证 + 部分结果 | 检查偏移、大小、标签，返回带错误信息的部分结果 | ✓ |
| 严格异常 | 任何无效数据立即抛异常，简洁但可能丢失部分数据 | |
| 静默容错 | 跳过错误继续解析，风险较高 | |

**User's choice:** 验证 + 部分结果（推荐）
**Notes:** Matches SAFE-04 requirement; AI agents need partial data

---

## File Layout

| Option | Description | Selected |
|--------|-------------|----------|
| 单文件 | 所有代码在一个文件中，便于直接运行，符合零依赖原则 | |
| src/ 模块结构 | 分离更清晰，但需要安装或打包 | |
| 渐进拆分 | Phase 1 单文件，后续阶段可拆分 | ✓ |

**User's choice:** 渐进拆分
**Notes:** Start simple, refactor when needed

---

## Integration Test Samples

| Option | Description | Selected |
|--------|-------------|----------|
| 用户提供样本 | 你自己提供测试文件，我有完整 UE 环境 | ✓ |
| 创建测试项目 | 我创建一个最小 UE 项目生成样本文件 | |
| 推迟集成测试 | 先只做单元测试，后续再添加集成测试 | |

**User's choice:** 用户提供样本
**Notes:** User has UE environment for sample .uasset files

---

## FString Encoding

| Option | Description | Selected |
|--------|-------------|----------|
| 仅 UTF-8 | UE 5.x 默认 UTF-8，简单直接，无需转换 | ✓ |
| UTF-8 + UTF-16 检测 | 更健壮，兼容 UTF-16 文件（如从 UE 4.x 迁移） | |
| 从长度前缀判断 | 从 FString 镀度符号判断：负数是 UTF-16，正数是 UTF-8 | |

**User's choice:** 仅 UTF-8（推荐）
**Notes:** UE 5.x standard, simplifies string handling

---

## PackageIndex Resolution

| Option | Description | Selected |
|--------|-------------|----------|
| 延迟解析 | Phase 1 仅存储原始 PackageIndex 值，Phase 3 再解析 | ✓ |
| 立即解析 | 在读取 Import/Export 时立即解析为可读名称 | |
| 混合方案 | 两种都提供，输出时选择 | |

**User's choice:** 延迟解析（推荐）
**Notes:** Keeps Phase 1 focused on core parsing

---

## Name Table Format

| Option | Description | Selected |
|--------|-------------|----------|
| 原始字节序列 | 直接读取 UTF-8 字节，处理 null 终止符 | |
| FNameEntry 结构 | 按 FNameEntry 结构解析（包含 number 字段） | |
| 版本自适应 | 两种格式都可能存在，根据版本判断 | ✓ |

**User's choice:** 版本自适应
**Notes:** Handle both format variants

---

## BulkData Handling

| Option | Description | Selected |
|--------|-------------|----------|
| 跳过 BulkData | Phase 1 不处理 BulkData，后续阶段再添加 | ✓ |
| 仅读取元数据 | 仅识别 BulkData 元数据（offset、size、flags），不读取实际数据 | |
| 完整处理 | 立即处理所有 BulkData 标志和载荷 | |

**User's choice:** 跳过 BulkData（推荐）
**Notes:** Defer complex BulkData handling to later phases

---

## Header Fields

| Option | Description | Selected |
|--------|-------------|----------|
| 全部字段 | 所有 PackageFileSummary 字段，完整信息便于后续阶段 | ✓ |
| 核心字段 | 仅 Tag、Version、NameOffset/Count、ExportOffset/Count、ImportOffset/Count | |
| 版本动态 | 根据版本动态选择字段 | |

**User's choice:** 全部字段（推荐）
**Notes:** Complete header enables all downstream phases

---

## Version Validation

| Option | Description | Selected |
|--------|-------------|----------|
| 严格验证 + 错误信息 | UE5 >= 1000, LegacyFileVersion in [-2, -9], 输出具体错误 | ✓ |
| 宽松验证 | 尝试解析，遇到异常再判断版本问题 | |
| 记录但不验证 | 记录版本号，不阻止解析，让后续阶段处理 | |

**User's choice:** 严格验证 + 错误信息
**Notes:** Clear error messages for unsupported versions

---

## Custom Versions GUID

| Option | Description | Selected |
|--------|-------------|----------|
| 读取但不验证 | 解析 GUID 和版本号，但不检查具体子系统版本 | ✓ |
| 完整验证 | 维护已知 GUID 列表，检查各子系统版本兼容性 | |
| 跳过 | Phase 1 不处理 Custom Versions | |

**User's choice:** 读取但不验证（推荐）
**Notes:** Store for later use, no subsystem validation

---

## PackageFlags

| Option | Description | Selected |
|--------|-------------|----------|
| 仅存储原始值 | 仅读取 flags 值，后续阶段根据需要解读 | ✓ |
| 解析关键标志 | 解析 PKG_Cooked、PKG_UnversionedProperties 等关键标志 | |
| 完整解析 | 输出所有 flags 的含义解释 | |

**User's choice:** 仅存储原始值（推荐）
**Notes:** Simple storage, interpretation in later phases

---

## Endianness Detection

| Option | Description | Selected |
|--------|-------------|----------|
| Magic Tag 检测 | 读取第一个 u32，与 TAG 和 TAG_SWAPPED 比对，设置字节交换模式 | ✓ |
| 直接假设小端序 | UE 5.x 都是 little-endian，直接假设小端序 | |
| 平台检测 | 检测平台架构后决定 | |

**User's choice:** Magic Tag 检测（推荐）
**Notes:** Proper endianness handling per PITFALLS.md Pitfall 1

---

## Claude's Discretion

- Exact struct.unpack format strings
- FArchive method naming conventions
- Error message format and detail level
- Unit test organization

---

## Deferred Ideas

None — discussion stayed within phase scope.

---

*Phase: 01-core-parsing*
*Discussion completed: 2026-04-28*