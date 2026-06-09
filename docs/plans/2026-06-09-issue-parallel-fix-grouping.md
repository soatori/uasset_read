# Issue 并行修复分组方案

**生成日期**：2026-06-09  
**最后更新**：2026-06-09 (v2.0)  
**状态**：部分修复完成，重新评估执行顺序  
**当前 Open Issues**：22 个（原 44 个，14 个已合并关闭，8 个已修复关闭）

## 合并记录（Issue 去重）

| 保留 Issue | 合并来源 | 说明 |
|---|---|---|
| #91 | #89 | CustomVersion 注册完整性审计 |
| #74 | #90 | FEdGraphPinType.Serialize 版本门控 |
| #83 | #82, #80, #81 | UClass::Serialize 专用 parser 缺失 |
| #51 | #84, #85 | 类级 Serialize 等价性矩阵 |
| #33 | #86, #87, #88 | UE4.27 兼容层设计 |
| #77 | #71 | Kismet bytecode fallback 与 token 覆盖 |
| #78 | #72, #73, #76 | Graph fallback/IR 状态传递 |

## 已关闭 Issues（代码已合入 develop）

| Issue | 优先级 | 修复 Commit | 说明 |
|---|---|---|---|
| #42 | P0 | 9901f53 | FPackageIndex 语义解析（Import/Export 区分） |
| #55 | P0 | f269b19 | SerializationControlExtensions 仅 UClass 条件读取 |
| #57 | P1 | f269b19 | Linker post_load 支持 PropertyValue dataclass |
| #58 | P1 | f269b19 | SoftObjectPath 索引越界返回 PropertyFallback |
| #59 | P1 | f269b19 | 容器内 StructProperty 使用正确 size |
| #67 | P2 | 2be9fba | ScriptSerializationStartOffset 偏移调整 |
| #68 | P2 | 2be9fba | 循环依赖 defer 机制 |
| #69 | P3 | 2be9fba | SuperStruct 链递归预加载 |

> ⚠️ **commit f269b19 修复范围说明**：commit message 声称修复 #55-#66 共 12 个属性解析问题，但实际代码仅修改了 SoftObjectProperty (#58) 和 linker.py PropertyValue 支持 (#57)。property_parser.py 的 dispatch 路由已更新（为 MulticastDelegate/FieldPath/TextProperty/OptionalProperty 传递 name_map/summary 参数），但 property_types.py 中对应的 handler 函数签名未同步更新，运行时会 TypeError 后被 tolerant 模式静默捕获转为 PropertyFallback。**#60-#64 实际未修复**，已 reopen。

---

## 当前 Open Issues 总览（22 个）

| 优先级 | 数量 | Issues |
|---|---|---|
| P0 | 0 | — |
| P1 | 8 | #26, #33, #51, #56, #60, #61, #62, #63, #64 |
| P2 | 7 | #65, #66, #70, #74, #75, #83, #91, #92 |
| P3 | 2 | #77, #78 |
| 未分配 | 3 | #36, #38, #53 |

---

## 执行计划

### Phase 0：紧急修复 — dispatch 断链（4 issues）

**优先级**：🔴 最高  
**原因**：property_parser.py dispatch 路由已更新，但 handler 签名未同步，导致 #61-#64 运行时 TypeError，属性值静默降级为 PropertyFallback  
**核心文件**：`property_types.py`

| # | 优先级 | 标题 | 修复内容 |
|---|---|---|---|
| 63 | P1 | MulticastDelegateProperty TScriptDelegate | handler 接受 name_map，按 TScriptDelegate 读取 |
| 64 | P1 | FieldPathProperty FName path + owner | handler 接受 name_map+summary，读 FName 路径 |
| 62 | P1 | OptionalProperty structured 语义 | handler 已接受 params，需实现 structured optional |
| 61 | P1 | TextProperty FText::SerializeText | handler 接受 summary，实现完整版本化解析 |

**执行顺序**：串行（同文件）  
**依赖关系**：被 Phase 1-3 依赖

### Phase 1：属性解析补全（5 issues）

**优先级**：🟠 高  
**核心文件**：`property_types.py`, `property_parser.py`

| # | 优先级 | 标题 | 修复内容 |
|---|---|---|---|
| 60 | P1 | Map/Set 不支持类型 PropertyFallback | handler 内部 unsupported type 返回 Fallback |
| 56 | P1 | PropertyTag 元数据保留到 IR/JSON | flags/guid/offsets 传递到 IR 层 |
| 65 | P2 | PropertyTag Extensions (UE5.3+) | 解析 extension header，修正偏移 |
| 66 | P2 | SkippedSerialize/BinaryOrNative | 标志位用于解析分派 |
| 92 | P2 | LWC 类型大小映射 | LargeWorldCoordinates 类型注册 |

**执行顺序**：串行（同文件）  
**依赖关系**：被 Phase 2-3 依赖

### Phase 2：Graph/Pin 版本门控（2 issues）

**优先级**：🟡 中  
**核心文件**：`serializers/graph.py`, `property_types.py`

| # | 优先级 | 标题 | 修复内容 |
|---|---|---|---|
| 74 | P2 | FEdGraphPinType.Serialize 版本门控 | 版本化字段读取 |
| 75 | P2 | UEdGraphPin::Serialize 版本门控 | WITH_EDITORONLY_DATA 条件读取 |

**执行顺序**：串行（同文件）  
**依赖关系**：被 Phase 3 依赖

### Phase 3：IR/Renderer 状态传递（1 issue）

**优先级**：🟡 中  
**核心文件**：`ir_builder.py`, `renderers/*`

| # | 优先级 | 标题 | 修复内容 |
|---|---|---|---|
| 78 | P3 | Graph/Node/Pin IR fallback 状态传递 | partial/fallback 状态从解析层传递到输出 |

**依赖关系**：需 Phase 2 完成

### Phase 4：Class 序列化 + Kismet（5 issues）

**优先级**：🟡 中  
**核心文件**：`class_serialization_strategy.py`, `export/`, `kismet/`, `blueprint/`

| # | 优先级 | 标题 | 修复内容 |
|---|---|---|---|
| 51 | P1 | 类级 Serialize() 等价性矩阵 | 定义各 BPGC 类的序列化策略 |
| 83 | — | UClass::Serialize 专用 parser | FuncMap/ClassFlags/Interfaces/Link/CDO |
| 91 | — | CustomVersion 注册完整性审计 | 核对 UE 源码 CustomVersion 列表 |
| 70 | P2 | BPGC SCS 组件树完整性 | SimpleConstructionScript 完整解析 |
| 77 | P3 | Kismet bytecode fallback | fallback scan 不作为真实 bytecode 输出 |

**执行顺序**：51 → 83 → 91 → 70，#77 可并行

### Phase 5：C++ 输出 + 兼容层（2 issues）

**优先级**：🟢 低  
**核心文件**：`cpp_gen/`, 多文件

| # | 优先级 | 标题 | 修复内容 |
|---|---|---|---|
| 26 | P1 | C++ 对称语义输出补齐 | 接口/枚举/结构体/委托/复制 |
| 33 | P1 | UE4.27 兼容层 | 版本门控兼容 |

**执行顺序**：串行，需 Phase 1-4 完成  
**注意**：当前有 22 个 C++ skeleton 测试失败，与 #26 相关

### Phase 6：Meta / 人工决策（3 issues）

**优先级**：人工  
**标签**：ready-for-human / needs-triage

| # | 标题 | 说明 |
|---|---|---|
| 53 | Issue 清理与拆解 | 管理类任务 |
| 36 | Stable root API | API 设计决策 |
| 38 | Deprecate legacy modules | 架构决策 |

---

## 并行调度时间线

```
Phase 0（紧急，串行）
└─ dispatch 断链修复：#63 → #64 → #62 → #61

Phase 1（串行）
└─ 属性解析补全：#60 → #56 → #65 → #66 → #92

Phase 2（串行，需 Phase 0）
└─ Pin 版本门控：#74 → #75

Phase 3（需 Phase 2）
└─ IR 状态传递：#78

Phase 4（可与 Phase 2-3 并行）
├─ Class 序列化：#51 → #83 → #91 → #70
└─ Kismet：#77（独立）

Phase 5（需 Phase 1-4）
├─ C++ 输出：#26
└─ 兼容层：#33

Phase 6（独立，人工）
└─ #53, #36, #38
```

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| dispatch 断链导致属性静默降级 | 🔴 高 | Phase 0 最高优先级修复 |
| #83 UClass parser 工作量大 | 🟠 高 | 分步实现：先核心字段，后扩展 |
| C++ skeleton 22 个测试失败 | 🟡 中 | Phase 5 #26 修复 |
| #33 需要 UE4.27 测试资产 | 🟡 中 | 需用户提供样本 |
| Phase 4 Class 序列化依赖 Phase 1 | 🟡 中 | 可提前设计矩阵（#51），不等 Phase 1 |

---

## 测试策略

- **Phase 0 完成后**：运行 `python scripts/test_matrix.py unit` 验证 dispatch 修复
- **Phase 1 完成后**：运行属性解析相关测试
- **Phase 2-3 完成后**：运行图序列化 + IR 测试
- **Phase 4 完成后**：运行类序列化 + Kismet 测试
- **Phase 5 完成后**：运行全量测试 + 质量门禁
- **每个 Phase**：确保 0 回归

---

**文档版本**：v2.0  
**最后更新**：2026-06-09  
**变更记录**：  
- v2.0 — 基于代码实际状态重新评估，纠正 commit f269b19 修复范围，重新分组为 7 个 Phase
- v1.1 — 第 2 组修复完成，更新状态和进度
- v1.0 — 初始分组方案
