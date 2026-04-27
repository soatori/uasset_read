# 研究摘要

**项目：** uasset_read —— Python .uasset 解析器（面向 AI agent）
**综合日期：** 2026-04-27

## 执行摘要

本项目构建 Python 工具解析 Unreal Engine .uasset 文件，使 AI agent 能直接读取蓝图内容无需 UE 编辑器依赖。.uasset 格式无文档但可从 UE 5.7 源码逆向工程（位于 `D:/Program Files/Epic Games/Engine/UE_5.7`）。

**关键洞察：** 专注于未 cooked/编辑器保存的资产，其含完整图数据。Cooked 资产已剥离编辑器数据且使用不同序列化（无版本属性）。

---

## 技术栈摘要

**零运行时依赖** —— 仅 Python 3.10+ 标准库。

| 层级 | 组件 | 模式 |
|------|------|------|
| 输入 | pathlib、mmap | 大资产内存映射文件访问 |
| 读取器 | struct、自定义 FArchive 类 | 显式字节序字节级解析 |
| 模型 | dataclasses | 清晰数据结构、内置 JSON 序列化 |
| 输出 | json、文本格式化 | agent 用结构化 JSON、人类用可读文本 |
| CLI | argparse | 单文件执行：`python uasset_read.py file.uasset` |

**架构：** 分层管道（Reader → Deserializer → Model → Output），镜像 UE FArchive 模式。

---

## 功能摘要

### 基础功能（必须有）

1. **解析 .uasset 文件头** —— PackageFileSummary 含魔术标签、版本、偏移
2. **提取名称表** —— 所有对象/属性名称引用此表
3. **提取导出/导入表** —— 对象和依赖定义于此
4. **识别资产类** —— Blueprint、Material、Texture 等
5. **基本属性解析** —— Int、Float、String、Bool、Array 值
6. **JSON 输出** —— AI agent 消费核心需求
7. **人类可读文本** —— 语义描述，非原始数据
8. **单文件解析** —— 无需 UE 编辑器或 pak 提取

### 差异化功能（增值）

1. **蓝图图提取** —— 节点、引脚、连接（高复杂度）
2. **变量定义** —— 名称、类型、默认值（中复杂度）
3. **函数定义** —— 签名、参数（高复杂度）
4. **依赖图** —— 此资产使用哪些其他资产（中复杂度）
5. **语义节点描述** —— "调用函数 X"而非"K2Node_CallFunction"

### 反功能（明确超出范围）

- 二进制资产导出（纹理、模型）
- 资产修改/写入
- 蓝图字节码反编译
- Pak 文件提取
- UE 编辑器集成
- Cooked 资产解析（专注未 cooked/编辑器保存）

---

## 架构摘要

### 分层管道

```
.uasset 文件 → BinaryReader → AssetDeserializer → Models → OutputFormatter
```

### 关键组件

1. **FArchive** —— 二进制读取抽象基类（镜像 UE 模式）
2. **PackageSummary** —— 文件头 dataclass 含各区块偏移
3. **NameTable** —— FName 索引引用的字符串池
4. **ImportMap/ExportMap** —— 对象引用和定义
5. **TypeHandlers** —— 资产特定解析插件注册表
6. **BlueprintHandler** —— 蓝图特定提取逻辑

### 数据流

```
1. 读取文件头（PackageFileSummary）
2. 读取名称表（在 NameOffset）
3. 读取导入表（在 ImportOffset）
4. 读取导出表（在 ExportOffset）
5. 对每个导出：
   - 解析类类型
   - 分发到处理器
   - 解析属性和类型特定数据
6. 格式化输出（JSON/文本/概要）
```

### 构建顺序

1. 读取层（FArchive、二进制操作）
2. 模型层核心（PackageSummary、PackageIndex、Import/Export）
3. 反序列化器核心（文件头、名称表、导入/导出解析）
4. 模型层类型（UObject、Blueprint、Properties）
5. 处理器层（类型注册表、BlueprintHandler）
6. 输出层（JSON、文本、概要格式器）
7. 性能/优化（mmap、延迟解析、版本处理）

---

## 陷阱摘要

### 关键（导致重写）

1. **字节序检测** —— 检查魔术标签；检测到交换标签时启用字节交换
2. **版本处理** —— UE4/UE5/自定义版本；无版本包需特殊处理
3. **BulkData 标志** —— PayloadAtEndOfFile、SeparateFile、Compression、64 位大小
4. **FName 索引 vs 字符串** —— FName 是 NameMap 索引非字符串；先加载 NameMap
5. **偏移算术** —— 绝对 vs 相对偏移；BulkDataStartOffset 为载荷基准
6. **无版本属性** —— Schema 基序列化（无属性标签）；需要类布局知识
7. **PropertyTag演进** —— GUID、扩展、类型名标志；版本依赖字段
8. **UE5 包 Trailer** —— Payload TOC、数据资源、从文件末尾反向读取

### 中等（导致问题）

1. **内存管理** —— 不全量读取文件；大文件使用 mmap
2. **struct 对齐** —— C++ 填充与 Python 不同；逐字段解析
3. **字符串编码** —— UE5+ UTF-8，旧版本 UTF-16；处理 LengthPrefix
4. **Import/Export 结构** —— 版本依赖字段；FPackageIndex 有符号编码
5. **错误恢复** —— 验证大小/偏移；返回部分结果，不崩溃
6. **蓝图图复杂性** —— 无文档；专注元数据，接受限制

### 次要

1. .umap vs .uasset（关卡包有额外结构）
2. Generations 数组（历史版本数据）
3. Package flags（PKG_Cooked、PKG_UnversionedProperties）
4. SoftObjectPath 列表（UE5+ 依赖跟踪）

---

## 关键 UE 源码参考

| 文件 | 目的 |
|------|------|
| `PackageFileSummary.h` | 文件头结构、偏移、版本 |
| `ObjectResource.h` | 导入/导出结构、PackageIndex |
| `PropertyTag.h` | 属性序列化格式 |
| `Archive.h` | FArchive 抽象模式 |
| `BulkData.cpp` | BulkData 标志和载荷处理 |
| `Blueprint.h` | 蓝图数据结构 |
| `EdGraph/EdGraphPin.h` | 引脚类型、连接 |
| `K2Node.h` | 蓝图节点层次 |

---

## 推荐阶段

基于研究，建议此路线图结构：

### 阶段 1：核心解析（基础）

- FArchive 基类配字节交换
- PackageFileSummary 文件头解析
- 名称表提取
- 导入/导出表解析
- 版本检测和处理
- 错误处理框架

**成功：** 能读取文件头、名称表并识别 .uasset 文件中有哪些对象。

### 阶段 2：属性解析（数据提取）

- PropertyTag 解析
- 基本属性类型（Int、Float、String、Bool、Name、Object）
- 数组属性处理
- Struct 属性基础
- 属性值输出

**成功：** 能从简单导出读取属性值。

### 阶段 3：蓝图基础（目标功能）

- 蓝图类型检测
- 变量定义提取
- 父类解析
- 基本蓝图元数据
- 蓝图聚焦输出格式

**成功：** 能从蓝图 .uasset 列出蓝图变量和父类。

### 阶段 4：蓝图图（高级）

- 图结构解析（UEdGraph）
- 节点识别（UK2Node 类型）
- 引脚解析和连接
- 语义节点描述
- 图可视化文本输出

**成功：** 能用节点/引脚描述追踪蓝图逻辑流。

### 阶段 5：优化与性能

- 大文件内存映射归档
- 延迟导出解析
- 全面错误恢复
- 版本兼容矩阵
- 输出格式优化

**成功：** 处理边缘情况、大文件并提供清晰输出。

---

## 置信度评估

| 区域 | 水平 | 备注 |
|------|------|------|
| 包结构 | 高 | 直接来自 UE 5.7 源码 |
| 导入/导出格式 | 高 | 直接来自 UE 5.7 源码 |
| 属性序列化 | 中 | 复杂但有文档 |
| 蓝图元数据 | 中 | 结构已知，提取需谨慎 |
| 蓝图图 | 低 | 无文档，可能遇限制 |
| AI-agent 输出模式 | 低 | 从需求推断，无研究 |

---

## 缺口与未知

1. **Cooked vs Uncooked** —— 需明确目标资产类型；假设未 cooked 以获取完整图数据
2. **版本矩阵** —— 初始支持哪些 UE 版本？推荐先 UE 5.x
3. **属性值反序列化** —— 如何读取实际值（非仅元数据）
4. **节点类型目录** —— 语义描述需完整 UK2Node 子类列表
5. **测试文件** —— 需示例 .uasset 文件测试；创建简单 UE 项目

---

## 下一步

1. 在 REQUIREMENTS.md 定义正式需求
2. 在 ROADMAP.md 创建带阶段分解的路线图
3. 初始化 STATE.md 用于项目记忆
4. 通过 `/gsd-plan-phase 1` 开始阶段 1 规划

---

*综合自：STACK.md、FEATURES.md、ARCHITECTURE.md、PITFALLS.md*
*研究置信度：核心解析高，蓝图提取中*