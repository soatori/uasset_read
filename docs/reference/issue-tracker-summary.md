# Issue Tracker 整理报告

> 生成时间：2026-06-10  
> 数据来源：GitHub Issues（共 82 个，截至 #103）

---

## 总览

| 状态 | 数量 |
|---|---|
| **OPEN** | 12 |
| **CLOSED** | 70 |
| **总计** | 82 |

---

## OPEN Issues（12 个）

### 🔴 P1 — 高优先级（3 个）

| # | 标题 | 标签 | 创建时间 |
|---|---|---|---|
| [#102](https://github.com/soatori/uasset_read/issues/102) | FBPVariableDescription + FEdGraphPinType 数据模型与 UE 源码字段对照偏差 | `bug` `P1` `ue-source-audit` | 2026-06-10 |
| [#95](https://github.com/soatori/uasset_read/issues/95) | 多模块序列化版本门控缺失（FEdGraphPinType + PropertyTag + FText） | `bug` `P1` `ue-source-audit` `deferred` | 2026-06-10 |
| [#94](https://github.com/soatori/uasset_read/issues/94) | constants.py 版本常量定义系统性错误（CustomVersion GUID + UE4 enum 值偏差） | `bug` `P1` `ue-source-audit` `deferred` | 2026-06-10 |

### 🟡 P2 — 中优先级（4 个）

| # | 标题 | 标签 | 创建时间 |
|---|---|---|---|
| [#98](https://github.com/soatori/uasset_read/issues/98) | LWC 类型大小映射错误与 Kismet 字节码版本门控缺失 | `bug` `P2` `ue-source-audit` | 2026-06-10 |
| [#97](https://github.com/soatori/uasset_read/issues/97) | 二进制格式结构与 UE 源码不一致（Unversioned Header + FScriptText + EdGraphPinOptimized + SoftObjectPath） | `bug` `P2` `ue-source-audit` | 2026-06-10 |
| [#96](https://github.com/soatori/uasset_read/issues/96) | PackageSummary UE5 字段版本门控缺失（PayloadTocOffset + PreloadDependencies + NamesReferenced） | `bug` `P2` `ue-source-audit` | 2026-06-10 |
| [#99](https://github.com/soatori/uasset_read/issues/99) | Kismet EX_SetArray 缺少 VER_UE4_CHANGE_SETARRAY_BYTECODE 版本门控 | `bug` `P2` `ue-source-audit` `deferred` | 2026-06-10 |

### 🟢 P3 / 文档 / 功能增强（3 个）

| # | 标题 | 标签 | 创建时间 |
|---|---|---|---|
| [#103](https://github.com/soatori/uasset_read/issues/103) | 补全 UE 反射系统常量定义和元数据解析（EClassFlags/EFunctionFlags/UFunction/UEnum） | `documentation` `enhancement` | 2026-06-10 |
| [#100](https://github.com/soatori/uasset_read/issues/100) | ScriptSerialization 偏移计算架构决策需文档化 | `documentation` `P3` `ue-source-audit` | 2026-06-10 |

### ⚪ 无标签（3 个，需 triage）

| # | 标题 | 创建时间 |
|---|---|---|
| [#84](https://github.com/soatori/uasset_read/issues/84) | Payload 偏移策略文档缺失（SerialOffset/SerialSize vs ScriptSerialization） | 2026-06-09 |
| [#83](https://github.com/soatori/uasset_read/issues/83) | UClass::Serialize 专用 parser 缺失（FuncMap/ClassFlags/Interfaces/Link/CDO） | 2026-06-09 |
| [#82](https://github.com/soatori/uasset_read/issues/82) | BlueprintGeneratedClass 序列化分类错误（应为 opaque 或专用 parser） | 2026-06-09 |

### 🔧 待处理（ready-for-agent）（1 个）

| # | 标题 | 标签 | 创建时间 |
|---|---|---|---|
| [#77](https://github.com/soatori/uasset_read/issues/77) | Kismet bytecode fallback scan 不能当作真实 bytecode 输出 | `needs-triage` `ready-for-agent` | 2026-06-09 |

---

## 分类统计

### 按类型

| 类型 | OPEN | 说明 |
|---|---|---|
| `bug` | 9 | 二进制解析与 UE 源码不一致 |
| `enhancement` | 1 | 反射系统常量补全 |
| `documentation` | 2 | 架构决策文档化 |
| 无标签 | 3 | 需 triage 分类 |

### 按来源

| 来源 | 数量 | 说明 |
|---|---|---|
| `ue-source-audit` | 9 | UE 源码审计发现（#94-#102） |
| 架构审查 | 3 | 序列化架构问题（#77, #82-#84） |
| 反射系统对比 | 1 | 本次新增（#103） |

### 特殊标记

| 标签 | 数量 | 说明 |
|---|---|---|
| `deferred` | 3 | 已合并的 UE4 兼容性问题，待计划（#94, #95, #99） |
| `ready-for-agent` | 1 | 可分配给 agent 执行（#77） |
| `needs-triage` | 1 | 需维护者评估（#77） |

---

## CLOSED Issues 汇总（70 个）

### 按优先级分布

| 优先级 | 数量 | 代表性 Issue |
|---|---|---|
| P0（紧急） | 8 | #55 SerializationControlExtensions, #42 FPackageIndex, #29 ScriptSerializationStartOffset |
| P1（高） | 18 | #64 FieldPathProperty, #63 MulticastDelegate, #62 OptionalProperty, #61 TextProperty |
| P2（中） | 10 | #47 废弃字段补全, #46 PackageFileSummary, #45 FGenerationInfo |
| P3（低） | 4 | #73 轻量解析 fallback, #71 Kismet EExprToken 覆盖度 |
| 无标签 | 30 | 早期批量创建，后合并关闭 |

### 已完成的重大工作

| 领域 | 相关 Issue | 状态 |
|---|---|---|
| 属性类型解析修复 | #55-#66（12 个 P0/P1 bug） | ✅ 全部关闭 |
| 序列化管线重构 | #28-#32, #42-#44 | ✅ 全部关闭 |
| 代码清理/重构 | #34-#40, #53, #93 | ✅ 全部关闭 |
| PackageFileSummary 补全 | #45-#47, #54 | ✅ 全部关闭 |
| 图/节点/引脚 IR | #67-#70, #72-#78 | ✅ 全部关闭 |
| CustomVersion 审计 | #81, #86-#92 | ✅ 全部关闭 |
| C++ 函数体生成 | #52, #101 | ✅ 全部关闭 |

---

## 建议行动

### 立即处理

1. **为 #82-#84 添加标签** — 这三个无标签 issue 需 triage：
   - #82 → `bug` `P2`
   - #83 → `enhancement` `P2`（注：uclass.py 已部分实现）
   - #84 → `documentation` `P3`（与 #100 重复，建议合并）

2. **合并重复 issue**：
   - #84 与 #100 主题重叠（均关于 Payload 偏移策略文档），建议关闭 #84 并关联 #100

3. **检查 #83 状态** — UClass::Serialize parser 已在 `parsers/asset_types/uclass.py` 实现，可能已解决

### 短期计划（本周）

4. **处理 `deferred` 标签 issue**（#94, #95, #99）— 评估是否纳入 v0.4.5 修复范围
5. **处理 #77**（ready-for-agent）— 分配 agent 执行

### 中期计划（本月）

6. **ue-source-audit 批次**（#96-#102）— 按 P1→P2 顺序修复
7. **#103 反射系统** — 按报告中 4 周路线图实施

---

*报告结束*
