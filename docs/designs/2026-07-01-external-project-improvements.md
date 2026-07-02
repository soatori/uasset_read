# 外部项目对标改进计划

> 日期: 2026-07-01
> 状态: **待评审**
> 对标项目: uasset-reader-js / UnrealBPInspect / AssetToJson

## 1. 背景

通过对比三个外部 `.uasset` 解析项目，识别出五个值得借鉴的改进方向。本文档整理调研结论、冲突分析和实施计划。

### 对标项目概况

| 项目 | 语言 | 定位 | 核心优势 |
|---|---|---|---|
| uasset-reader-js | JavaScript | 浏览器端头部检查器 | HexView 调试体验、零安装 |
| UnrealBPInspect | Rust | 蓝图专用 CLI 工具 | CFG 字节码反编译、Git textconv、`--diff` |
| AssetToJson | C++ UE Plugin | 编辑器内 AI 代理导出器 | Pin 类型细粒度表达、Schema 版本化 |

## 2. 改进方向

### 2.1 CFG 反编译架构

**现状**: 扁平列表 + 两套不一致的模式匹配 (`JumpAnalyzer` + `StructuredControlFlow`)

**核心差距**:
- 无基本块 (Basic Block) 构建
- 无支配树 / 后支配树
- 无 CFG 边 (predecessor/successor) 追踪
- 循环检测基于 ad-hoc 偏移比较，非支配树分析
- if/else 检测依赖 Push/Pop 启发式或特定 Jump 搜索
- 两套检测器可能对同一输入产生不同结果

**参考**: UnrealBPInspect 的 `bytecode/` 模块 (100+ 文件) 实现了完整的 CFG 构建、支配树、区域检测、死语句消除、CSE、级联折叠。

**方案**: 拆为两阶段

#### Issue A: CFG 基础设施 (P2)

**依赖**: #249 M-15 (合并 structured_flow 重复逻辑)

**范围**:
- 新建 `kismet/cfg/` 子模块
- `BasicBlock` 数据结构: leader 识别、指令分割、单入口单出口
- CFG 边构建: fall-through / conditional / unconditional / exceptional
- 支配树算法 (Lengauer-Tarjan 或简单迭代)
- 基于支配树的循环检测 (back-edge → loop header)
- 统一 `JumpAnalyzer` + `StructuredControlFlow` 为单一 CFG 分析

**不包含**: 数据流分析、优化变换、结构化输出生成

#### Issue B: CFG 结构化输出 (P2)

**依赖**: Issue A

**范围**:
- 后支配树 → join point 检测 → if/else 区域重建
- 循环体边界细化 (break/continue 识别)
- PushExecutionFlow / PopExecutionFlow 配对解析
- 结构化输出生成: 遍历 CFG 按支配序输出嵌套结构
- 替换现有 `body_builder.py` 的结构化输出路径

**关键文件**:
- 新建: `kismet/cfg/basic_block.py`, `kismet/cfg/cfg_builder.py`, `kismet/cfg/dominator.py`, `kismet/cfg/structured_emitter.py`
- 修改: `kismet/body_builder.py` (调用 CFG 输出), `kismet/pipeline.py` (集成 CFG)
- 删除: `kismet/structured_flow.py` (合并后移除)

### 2.2 Git textconv 集成 (P3, 独立)

**现状**: 无任何实现，无已有 issue

**参考**: UnrealBPInspect 的 `--diff` 模式 + `.gitattributes` textconv 配置

**范围**:
- `--diff <file1.uasset> <file2.uasset>`: 解析两个资产并输出结构化差异
- `.gitattributes` 配置脚本 + textconv 驱动脚本
- 支持 JSON diff (字段级比较) 和文本摘要 diff (人可读)
- 使用文档: `docs/guides/git-textconv.md`

**关键约束**:
- 依赖现有 JSON 输出结构
- diff 输出需要 stable field ordering
- 不修改解析核心，纯输出层功能

### 2.3 JSON 输出 Schema 版本化 (P2, 待决策)

**现状**:
- `output_version: "5.0"` 语义模糊（parser version vs output format version）
- 无正式 JSON Schema 文件
- `RenderOptions.include_schema` 是死选项 (从未使用)
- 两份设计文档方向矛盾

**设计文档冲突**:

| 文档 | 立场 | 理由 |
|---|---|---|
| `2026-06-03-output-format-ir-design.md` | 消除 `output_version` | IR 数据类即 Schema，版本号无意义 |
| `output-refactor.md` | 升级到 `"6.0"` | 输出结构大幅扩展，需要版本追踪 |

**⚠️ 待决策**: 需在实现前确定方向。两个可选方案:

**方案 A: 消除 version + 启用 Schema**
- 移除 `output_version` 字段
- 启用 `include_schema=True`，输出中嵌入 `$schema` 引用
- 为每种资产类型生成 `.schema.json` 文件
- 与已批准的 IR 设计文档对齐

**方案 B: 保留 version + 升级到 6.0**
- `output_version` 升级到 `"6.0"`
- 同时生成正式 JSON Schema 文件
- 与 `output-refactor.md` 对齐

**无论哪种方案，以下工作相同**:
- 为 PackageIR 输出结构编写 JSON Schema
- 在 `docs/formats/output/` 文档化输出格式
- 启用 `RenderOptions.include_schema`

### 2.4 Pin 类型细粒度表达 (P2, 合并到 #247)

**现状**: PinIR 仅 6 字段，`pin_type` 被 `_safe_str()` stringify 丢失所有结构

**核心问题**: `FEdGraphPinType` 在解析层已完整提取 (13 个字段)，但 `_build_pin_ir()` 调用 `str()` 将其扁平化为字符串。`flow_builder.py` 已正确提取这些字段证明数据可达。

**缺失字段对照**:

| 字段 | FEdGraphPinType | PinIR | 状态 |
|---|---|---|---|
| `pin_category` | ✅ | ❌ (嵌在字符串中) | 缺失 |
| `pin_subcategory` | ✅ | ❌ | 缺失 |
| `pin_subcategory_object_name` | ✅ | ❌ | 缺失 |
| `container_type` | ✅ (int: 0/1/2/3) | ❌ | 缺失 |
| `is_reference` | ✅ (bool) | ❌ | 缺失 |
| `is_const` | ✅ (bool) | ❌ | 缺失 |
| `is_weak_pointer` | ✅ (bool) | ❌ | 缺失 |
| `is_uobject_wrapper` | ✅ (bool) | ❌ | 缺失 |
| `is_map_key` | ✅ (bool) | ❌ | 缺失 |
| `is_map_value` | ✅ (bool) | ❌ | 缺失 |
| `pin_type_value` | N/A | ❌ (总是 None) | 死字段 |

**方案**: 在 PinIR 中补充结构化类型字段，保留 `pin_type` 字符串作为向后兼容的摘要

```python
@dataclass
class PinIR:
    pin_name: str
    pin_type: str                    # 保留: 向后兼容的字符串摘要
    pin_category: str = ""           # 新增: "bool", "object", "struct", "exec"
    pin_subcategory: str = ""        # 新增: 具体类型名
    pin_subcategory_object: str | None = None  # 新增: 解析后的对象名
    container_type: str = "None"     # 新增: "None" | "Array" | "Set" | "Map"
    is_reference: bool = False       # 新增
    is_const: bool = False           # 新增
    is_weak_pointer: bool = False    # 新增
    is_uobject_wrapper: bool = False # 新增
    is_map_key: bool = False         # 新增
    is_map_value: bool = False       # 新增
    linked_to: list[str]
    direction: str
    default_value: str | None
```

**合并到 #247**: 作为新增 M-18 item，与 M-6 (PinSubCategoryObject 提取) 同属 Pin 类型补全。

**涉及文件**:
- `models/ir.py` — PinIR dataclass 扩展
- `ir_builder.py` — `_build_pin_ir()` 从 FEdGraphPinType 提取结构化字段
- `renderers/json_renderer.py` — `_pin_to_dict()` 输出新字段

### 2.5 HexView 解析轨迹集成 (P3, 独立)

**现状**: 7 个 HexView issue 全部 CLOSED，系统已完成。但 `hex_view_entries` 未进入 `PackageIR` 或 JSON 输出。

**参考**: uasset-reader-js 的 "每次读取记录到 hexView 数组" 模式

**范围**:
- 将 `hex_view_entries` 从 `ParseResult` 传递到 `PackageIR`
- JSON 输出增加 `debug.hex_view` 字段 (需 `--debug` 或 `--hex-view` 启用)
- 增强 `HexViewEntry`: 添加 `field_path` (层级路径如 `Export[0].Properties[2].Value`)
- 增强 `HexViewEntry`: 添加 `semantic_type` (分类: header / name_table / import / export / property / bytecode)
- JSON 解析轨迹格式: `{offset, length, type, value, path, semantic_type}`

**涉及文件**:
- `debug/hex_view.py` — HexViewEntry 扩展
- `models/ir.py` — PackageIR 增加 debug 字段
- `ir_builder.py` — 传递 hex_view_entries
- `renderers/json_renderer.py` — 条件输出 debug.hex_view

## 3. 冲突处理汇总

| 冲突类型 | 涉及 | 处理 |
|---|---|---|
| 功能重叠 | PinIR 字段补全 ↔ #247 M-6 | **合并**: 新增 M-18 到 #247 |
| 功能重叠 | CFG 统一 ↔ #249 M-15 | **合并**: 新增 M-18 到 #249 |
| 设计矛盾 | JSON Schema 方向 (两份设计文档) | **待决策**: 实现前需确定 |
| 前置依赖 | CFG → #249 M-15 | **顺序**: #249 完成后再启动 CFG |

## 4. 执行计划

```
Phase 0 — 立即 (P1 bug fix)
├── #243 CPF_* 标志修正
└── #245 wildcard 空格修正

Phase 1 — 模块清理 (P2, 依赖 Phase 0)
├── #247 blueprint 模块修复 + PinIR 补全 (M-6~M-9 + M-18)
├── #248 graph 模块 SubGraphs + 硬编码清理 (M-10~M-13)
└── #249 kismet 模块重构 + CFG 统一 (M-14~M-18)

Phase 2 — 新功能 (P2/P3, 依赖 Phase 1)
├── Issue A: CFG 基础设施 (依赖 #249 M-15/M-18)
├── Issue E: HexView 集成 (独立)
└── Issue D: JSON Schema (待决策后实现)

Phase 3 — 高级功能 (P2/P3, 依赖 Phase 2)
├── Issue B: CFG 结构化输出 (依赖 Issue A)
└── Issue C: Git textconv (独立, 可并行)
```

## 5. Issue 模板

### Issue A: feat: CFG 基础设施 — 基本块 + 支配树 + 循环检测

```
标题: feat: CFG 基础设施 — 基本块构建 + 支配树 + 循环检测
标签: P2, kismet, architecture
依赖: #249 (M-15/M-18 完成后)

## 目标
将 Kismet 字节码反编译从"扁平列表 + 模式匹配"升级为"CFG 图分析"，
统一 JumpAnalyzer 和 StructuredControlFlow 为单一分析管线。

## 技术方案
1. 新建 kismet/cfg/ 子模块
2. BasicBlock: leader 识别 + 指令分割
3. CFG 边: fall-through / conditional / unconditional
4. 支配树: Lengauer-Tarjan 或迭代算法
5. 循环检测: back-edge → loop header (基于支配树)
6. 统一 JumpAnalyzer + StructuredControlFlow

## 不包含
- 数据流分析、优化变换、结构化输出生成 (见后续 issue)

## 验证
- 对比 JumpAnalyzer/StructuredControlFlow 现有检测结果
- 新增测试: 嵌套循环、多出口循环、复杂 if/else 链
```

### Issue B: feat: CFG 结构化输出 — if/else + while + for 重建

```
标题: feat: CFG 结构化输出 — 基于 CFG 的控制流重建
标签: P2, kismet
依赖: Issue A

## 目标
基于 CFG 分析结果重建结构化控制流，替换现有 pattern-matching 输出。

## 技术方案
1. 后支配树 → join point → if/else 区域
2. 循环体边界细化 (break/continue)
3. PushExecutionFlow/PopExecutionFlow 配对
4. 结构化输出: 支配序遍历 + 嵌套结构
5. 替换 body_builder.py 结构化路径

## 验证
- StructuredRateReport 指标提升
- 复杂蓝图 (嵌套循环 + if/else 链) 输出对比
```

### Issue C: feat: Git textconv 集成

```
标题: feat: Git textconv 集成 — .uasset 二进制 diff 可读化
标签: P3, cli, git
依赖: 无

## 目标
让 git diff 直接展示 .uasset 蓝图变更的可读文本。

## 技术方案
1. --diff <file1> <file2> 模式
2. .gitattributes 配置脚本
3. textconv 驱动脚本
4. JSON diff + 文本摘要 diff
5. 使用文档

## 参考
UnrealBPInspect 的 --diff + git textconv 实现
```

### Issue D: feat: JSON 输出 Schema 版本化

```
标题: feat: JSON 输出 Schema 版本化与文档化
标签: P2, output, schema
⚠️ 待决策: output_version 方向确定后实施

## 目标
为 JSON 输出建立正式的 Schema 定义和版本管理。

## 待决策
- 方案 A: 消除 output_version，启用 include_schema
- 方案 B: 保留 output_version 并升级到 6.0

## 通用范围 (无论哪种方案)
1. 编写 JSON Schema 文件
2. 文档化输出格式
3. 启用 RenderOptions.include_schema
```

### Issue E: feat: HexView 解析轨迹集成到 IR/JSON

```
标题: feat: HexView 解析轨迹集成到 IR/JSON 输出
标签: P3, debug
依赖: 无

## 目标
将 HexView 解析轨迹从独立调试工具集成到标准输出管线。

## 技术方案
1. hex_view_entries → PackageIR → JSON
2. 增强 HexViewEntry: field_path + semantic_type
3. 条件输出: --debug 启用
4. JSON 格式: {offset, length, type, value, path, semantic_type}
```

### #247 新增 M-18

```
**M-18:** PinIR 类型字段细粒度补全 — _build_pin_ir() 将 FEdGraphPinType 
stringify 丢失结构。需补充: pin_category, pin_subcategory, 
pin_subcategory_object, container_type, is_reference, is_const, 
is_weak_pointer, is_uobject_wrapper, is_map_key, is_map_value。
移除死字段 pin_type_value (总是 None)。
文件: models/ir.py, ir_builder.py, renderers/json_renderer.py
```

### #249 新增 M-18

```
**M-18:** CFG 统一 — JumpAnalyzer 和 StructuredControlFlow 是两套不一致的
模式检测器，可能对同一输入产生不同结果。需统一为单一 CFG 分析管线
(基本块 + 支配树 + 循环检测)。此为后续 CFG 基础设施 issue 的前置依赖。
文件: kismet/jump_analyzer.py, kismet/structured_flow.py, kismet/cfg/(新建)
```
