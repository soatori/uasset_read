# Issue 并行修复分组方案

**生成日期**：2026-06-09  
**状态**：待执行  
**总 Issue 数**：24 个 open issues

## 概述

基于 24 个 open issues 的模块归属、文件重叠和优先级分析，建议分为 **5 组**（4 组 agent 可执行 + 1 组需人工决策）。

**分组原则**：
1. 同文件修改不并行（避免冲突）
2. 跨组无文件重叠（可完全并行）
3. P0 issue 优先处理
4. 被依赖的基础模块先修复

---

## 分组总览

| 组别 | 类型 | Issue 数 | 优先级 | 可并行组 | 文件冲突 |
|------|------|---------|--------|---------|---------|
| **第 1 组** | 属性解析修复 | 10 | P1×9 + P2×1 | 第 2 组 | `property_types.py`, `property_parser.py` |
| **第 2 组** | Linker + Export 加载链 | 6 | P0×2 + P2×3 + P3×1 | 第 1 组 | `export/export_loader.py`, `link/linker.py` |
| **第 3 组** | IR/Renderer 诊断与兼容 | 2 | P2×1 + P3×1 | 第 4 组 | `ir_builder.py`, `renderers/*` |
| **第 4 组** | 蓝图 + Kismet + C++ 输出 | 3 | P1×2 + P3×1 | 第 3 组 | `blueprint/`, `kismet/`, `cpp_gen/` |
| **第 5 组** | 元任务 / API 设计 | 3 | - | 独立 | `__init__.py` 等 |

**执行顺序**：
- 第 1、2 组可完全并行（无文件冲突）
- 第 3、4 组需等第 1、2 组完成后并行执行
- 第 5 组独立，随时可启动讨论

---

## 第 1 组：属性解析修复（10 issues）

**优先级**：P1×9 + P2×1  
**核心文件**：`property_types.py`, `property_parser.py`  
**依赖关系**：被第 3、4 组依赖，应优先处理

### Issue 列表

| # | 优先级 | 标题 | 文件 | 执行顺序 |
|---|--------|------|------|---------|
| 64 | P1 | FieldPathProperty 应读取 FName path 和 owner 引用 | `property_types.py:1075-1082` | 1 |
| 63 | P1 | MulticastDelegateProperty 应按 TScriptDelegate 读取 | `property_types.py:1029-1037` | 2 |
| 62 | P1 | OptionalProperty has_value/inner size 语义不一致 | `property_types.py:1085-1098` | 3 |
| 61 | P1 | TextProperty 需按 FText::SerializeText 版本化解析 | `property_types.py` | 4 |
| 59 | P1 | 容器内 StructProperty 不能用 size=0 dummy tag | `property_types.py:510-520` | 5 |
| 60 | P1 | Map/Set 不支持的类型不能静默返回 None | `property_types.py:1284-1302` | 6 |
| 58 | P1 | SoftObjectPath 索引越界应降级处理 | `property_types.py` | 7 |
| 57 | P1 | Linker post_load 必须支持 PropertyValue 引用解析 | `property_parser.py:521-526`, `linker.py:386-430` | 8 |
| 56 | P1 | 保留 PropertyTag 元数据到 IR/JSON | `property_parser.py`, `models/property.py` | 9 |
| 66 | P2 | SkippedSerialize/BinaryOrNative 标志未使用 | `property_parser.py` | 10 |

### 执行建议

- **串行执行**：所有 issue 修改同一文件（`property_types.py` 或 `property_parser.py`），不能并行
- **从底层到高层**：先修具体类型解析（64→63→62→61→59→60→58），再修框架层（57→56→66）
- **测试策略**：每个 issue 完成后运行完整 property 测试套件

### 组内依赖图

```
64 → 63 → 62 → 61 → 59 → 60 → 58 → 57 → 56 → 66
```

---

## 第 2 组：Linker + Export 加载链修复（6 issues）

**优先级**：P0×2 + P2×3 + P3×1  
**核心文件**：`export/export_loader.py`, `link/linker.py`  
**依赖关系**：与第 1 组无冲突，可并行；被第 3、4 组依赖

### Issue 列表

| # | 优先级 | 标题 | 文件 | 执行顺序 |
|---|--------|------|------|---------|
| **55** | **P0** | SerializationControlExtensions 条件读取 | `export/export_loader.py` | **1** |
| **42** | **P0** | FPackageIndex 语义解析（Import/Export 区分） | `link/linker.py` | **2** |
| 67 | P2 | ScriptSerializationStartOffset 未在 preload 中使用 | `export/export_loader.py`, `link/linker.py` | 3 |
| 68 | P2 | 缺少循环依赖 defer 机制 | `link/linker.py` | 4 |
| 69 | P3 | Preload 不递归加载 SuperStruct 链 | `link/linker.py` | 5 |
| 70 | P2 | BlueprintGeneratedClass SCS 组件树序列化完整性 | `blueprint/`, `export/` | 6 |

### 执行建议

- **#55 优先**：P0 issue，SerializationControlExtensions 只能对 UClass 条件读取
- **#42 其次**：P0 基础 issue，FPackageIndex 语义是后续引用的基础
- **#67-69 串行**：都修改 `link/linker.py`，需顺序执行
- **#70 最后**：涉及 blueprint 层，需等 export 加载链修复完成

### 组内依赖图

```
55 (P0) → 42 (P0) → 67 → 68 → 69 → 70
```

---

## 第 3 组：IR/Renderer 诊断与兼容性（2 issues）

**优先级**：P2×1 + P3×1  
**核心文件**：`ir_builder.py`, `renderers/*`, `parse_uasset.py`  
**依赖关系**：需第 1、2 组完成

### Issue 列表

| # | 优先级 | 标题 | 文件 | 执行顺序 |
|---|--------|------|------|---------|
| 72 | P2 | IR/Renderer 诊断信息传递完整性 | `ir_builder.py`, `renderers/*` | 1 |
| 73 | P3 | 轻量解析 fallback 输出结构与 IR 兼容性 | `parse_uasset.py` | 2 |

### 执行建议

- **#72 优先**：P2 issue，确认诊断信息在各 renderer 中的传递
- **#73 其次**：P3 issue，验证轻量解析输出的 IR 兼容性
- **可并行**：两个 issue 修改不同文件

---

## 第 4 组：蓝图 + Kismet + C++ 输出（3 issues）

**优先级**：P1×2 + P3×1  
**核心文件**：`blueprint/`, `kismet/`, `cpp_gen/`  
**依赖关系**：需第 1、2 组完成

### Issue 列表

| # | 优先级 | 标题 | 文件 | 执行顺序 |
|---|--------|------|------|---------|
| 51 | P1 | 建立类级 Serialize() 等价性矩阵 | `export/`, `class_serialization_strategy.py` | 1 |
| 71 | P3 | Kismet 字节码 EExprToken 覆盖度审计 | `kismet/` | 2 |
| 26 | P1 | 补齐接口/枚举/结构体/委托/复制等 C++ 对称语义输出 | `cpp_gen/` | 3 |

### 执行建议

- **#51 优先**：P1 issue，需等第 2 组 export 加载修复完成
- **#71 其次**：P3 issue，Kismet 字节码审计，相对独立
- **#26 最后**：P1 issue，C++ 输出补齐，工作量大

### 组内依赖图

```
51 (需第 2 组) → 71 → 26
```

---

## 第 5 组：元任务 / API 设计（3 issues，需人工决策）

**优先级**：-  
**标签**：ready-for-human / needs-triage  
**依赖关系**：独立，随时可启动

### Issue 列表

| # | 标题 | 说明 |
|---|------|------|
| 53 | Issue 清理与拆解：基于当前代码状态刷新 cleanup 队列 | 管理类任务 |
| 36 | Define stable root API and deprecate oversized __all__ exports | API 设计决策 |
| 38 | Deprecate or remove legacy objects and bulk modules from public API | 架构决策 |

### 执行建议

- **不适合 agent 自动修复**：需要人工确定 API 方向和废弃策略
- **可并行讨论**：三个 issue 相互独立，可同时推进
- **建议先做 #53**：清理 issue 队列，明确优先级

---

## 并行调度时间线

```
阶段 1（并行）
├─ 第 1 组：属性解析修复（10 issues，串行）
│  └─ 64 → 63 → 62 → 61 → 59 → 60 → 58 → 57 → 56 → 66
│
└─ 第 2 组：Linker+Export 加载链（6 issues，串行）
   └─ 55(P0) → 42(P0) → 67 → 68 → 69 → 70

阶段 2（并行，需阶段 1 完成）
├─ 第 3 组：IR/Renderer 诊断（2 issues，可并行）
│  ├─ 72
│  └─ 73
│
└─ 第 4 组：蓝图+Kismet+C++（3 issues，串行）
   └─ 51 → 71 → 26

阶段 3（独立）
└─ 第 5 组：元任务/API 设计（3 issues，人工决策）
   ├─ 53
   ├─ 36
   └─ 38
```

---

## 执行建议

### 最大并行度
- **阶段 1**：2 组并行（第 1 组 + 第 2 组）
- **阶段 2**：2 组并行（第 3 组 + 第 4 组）
- **阶段 3**：1 组（第 5 组，人工决策）

### 优先级策略
1. **P0 优先**：#55、#42 必须在阶段 1 最先处理
2. **基础模块优先**：属性解析（第 1 组）和 Linker（第 2 组）是后续组的基础
3. **避免冲突**：同文件修改不并行，跨组无文件重叠

### 测试策略
- **每组完成后**：运行完整测试套件（`python scripts/test_matrix.py all`）
- **每个 issue 完成后**：运行相关模块测试
- **阶段转换时**：运行回归测试（`python scripts/test_matrix.py regression`）

### 分支策略
- 每组在独立分支开发：`fix/group-1-property-parsing`, `fix/group-2-linker-export`, etc.
- 每组完成后创建 PR，合并到 `develop`
- 所有组完成后，从 `develop` 合并到 `master` 发布

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 第 1 组工作量过大（10 issues） | 延期 | 可考虑拆分为 1a（property_types）+ 1b（property_parser） |
| 第 2 组 #55/#42 修复复杂 | 阻塞后续 | 优先投入资源，必要时人工介入 |
| 第 5 组人工决策延迟 | 不影响执行 | 可并行讨论，不阻塞 agent 执行 |
| 组间依赖未完全识别 | 集成失败 | 阶段转换时运行完整测试 |

---

## 附录：Issue 完整列表

### P0（Critical）
- #55: SerializationControlExtensions 条件读取
- #42: FPackageIndex 语义解析

### P1（High）
- #64: FieldPathProperty FName path + owner 引用
- #63: MulticastDelegateProperty TScriptDelegate 读取
- #62: OptionalProperty has_value/inner size 语义
- #61: TextProperty FText::SerializeText 版本化解析
- #60: Map/Set 不支持类型静默返回 None
- #59: 容器内 StructProperty size=0 dummy tag
- #58: SoftObjectPath 索引越界降级
- #57: Linker post_load PropertyValue 引用解析
- #56: PropertyTag 元数据保留到 IR/JSON
- #51: 类级 Serialize() 等价性矩阵
- #26: C++ 对称语义输出补齐

### P2（Medium）
- #72: IR/Renderer 诊断信息传递
- #70: BPGC SCS 组件树序列化
- #68: 循环依赖 defer 机制
- #67: ScriptSerializationStartOffset 未使用
- #66: SkippedSerialize/BinaryOrNative 标志未使用

### P3（Low）
- #73: 轻量解析 fallback 输出 IR 兼容性
- #71: Kismet EExprToken 覆盖度审计
- #69: Preload 递归 SuperStruct 链

### 其他（需人工决策）
- #53: Issue 清理与拆解（needs-triage）
- #36: 定义稳定 root API（ready-for-human）
- #38: 废弃 legacy objects/bulk 模块（ready-for-human）
- #33: UE4.27 兼容层设计（enhancement，未分配）

---

**文档版本**：v1.0  
**最后更新**：2026-06-09
