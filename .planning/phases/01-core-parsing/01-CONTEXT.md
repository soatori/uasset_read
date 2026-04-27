# 阶段 1：核心解析 - 上下文

**收集日期：** 2026-04-28
**状态：** 准备规划

<domain>
## 阶段边界

解析 .uasset 文件头、名称表、导入表和导出表；识别资产结构和类型。此阶段交付所有后续阶段依赖的基础层。

**固定范围（来自 ROADMAP.md）：**
- PackageFileSummary 文件头解析
- 名称表提取（NameMap）
- 导入表解析（FObjectImport）
- 导出表解析（FObjectExport）
- 从 ClassIndex 识别资产类
- 版本处理（UE4/UE5/自定义版本）
- 错误处理框架

</domain>

<decisions>
## 实现决策

### 架构设计
- **D-01:** 单一 FArchive 类 —— 所有读取方法在一类中（非分层 FArchive + FileReader + MemoryReader）
- **D-02:** 阶段 1 单文件实现；阶段 5 添加 MappedArchive 支持大文件
- **原因：** 初始实现更简单，符合零依赖理念

### 版本支持
- **D-03:** 仅 UE 5.x —— 专注 UE 5.x 格式（稳定，与 UE 5.7 源码参考匹配）
- **D-04:** 严格版本验证配清晰错误信息 —— UE5 版本 >= 1000，LegacyFileVersion 在 [-2, -9]
- **D-05:** 自定义版本 GUID —— 读取并存储，但不验证特定子系统版本
- **原因：** 降低初始复杂度；UE 5.x 格式与 D:/Program Files/Epic Games/Engine/UE_5.7 源码参考对齐

### 数据模型
- **D-06:** 所有解析结构使用 dataclasses（PackageFileSummary、ObjectImport、ObjectExport 等）
- **D-07:** PackageIndex 存储为原始有符号 int32 —— 延迟解析（阶段 1 存索引，阶段 3+ 解析名称）
- **原因：** Python 3.10+ 原生 dataclasses，asdict() → JSON 直接；延迟解析保持阶段 1 专注

### 文件头解析
- **D-08:** 读取所有 PackageFileSummary 字段 —— 完整文件头供下游阶段
- **D-09:** 名称表格式 —— 版本自适应（处理 UTF-8 和 FNameEntry 结构变体）
- **D-10:** FString 编码 —— 仅 UTF-8（UE 5.x 标准）
- **D-11:** 通过魔术标签检测字节序 —— 比对首 u32 与 PACKAGE_FILE_TAG（0x9E2A83C1）和 PACKAGE_FILE_TAG_SWAPPED（0xC1832A9E）
- **D-12:** PackageFlags —— 仅存储原始值（阶段 1 不解释标志）
- **原因：** 完整文件头启用所有下游阶段；UTF-8 简化字符串处理

### BulkData 处理
- **D-13:** 阶段 1 跳过 BulkData —— 不解析嵌入载荷
- **原因：** BulkData 复杂；推迟到后续阶段或 v2

### 错误处理
- **D-14:** 定位前验证偏移/大小 —— 可恢复错误返回带错误信息的部分结果
- **D-15:** 无效/损坏文件绝不崩溃 —— 优雅降级
- **原因：** 匹配 SAFE-04 需求；AI agent 需部分数据，非异常

### 测试策略
- **D-16:** 组合方案 —— 合成数据单元测试 + 真实 .uasset 集成测试
- **D-17:** 集成测试样本由用户提供 —— 用户有 UE 环境提供示例文件
- **原因：** 合成数据验证边缘情况；真实文件验证实际格式

### 文件布局
- **D-18:** 渐进拆分 —— 阶段 1 单文件，后续阶段可模块化
- **原因：** 先简单；需要时重构

### Claude 自行决定
- 具体 struct.unpack 格式字符串
- FArchive 方法命名约定
- 错误信息格式和详细程度
- 单元测试组织

</decisions>

<specifics>
## 具体想法

- "让 AI agent 能直接读取 .uasset 文件内容，无需人工介入 UE 编辑器" —— PROJECT.md 核心价值
- UE 5.7 源码在 `D:/Program Files/Epic Games/Engine/UE_5.7` 为权威参考
- 专注于未 cooked/编辑器保存的资产（完整蓝图数据可用）

</specifics>

<canonical_refs>
## 权威参考

**下游 agent 必须在规划或实现前阅读这些。**

### UE 源码参考
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/PackageFileSummary.h` —— 文件头结构、所有字段、偏移
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h` —— 导入/导出结构、FPackageIndex 编码
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/Serialization/Archive.h` —— FArchive 模式参考

### 项目规划
- `.planning/PROJECT.md` —— 项目上下文、核心价值、约束
- `.planning/REQUIREMENTS.md` —— CORE-01 至 CORE-08 需求
- `.planning/ROADMAP.md` —— 阶段 1 成功标准、主要工作、风险
- `.planning/research/STACK.md` —— Python 技术栈决策、struct/mmap 模式
- `.planning/research/ARCHITECTURE.md` —— 分层管道模式、FArchive 实现示例
- `.planning/research/PITFALLS.md` —— 关键陷阱（字节序、版本、偏移、FName）

</canonical_refs>

<code_context>
## 现有代码洞察

### 无现有项目代码
这是新项目。无可复用资产。

### UE 源码模式
- FArchive 模式含 read_u8、read_u32、read_fstring、read_name 方法
- PackageFileSummary 结构含 NameOffset、ExportOffset、ImportOffset
- FPackageIndex 有符号编码：>0 导出、<0 导入、0 null
- FName = NameMap 索引 + 实例编号

### 外部参考
- CUE4Parse（C#）：处理器注册模式、版本感知解析
- FModel：分层架构、输出格式器

</code_context>

<deferred>
## 推迟想法

无 —— 讨论保持在阶段范围内。

**后续阶段将处理：**
- 属性解析（阶段 2）
- 蓝图提取（阶段 3）
- 输出格式器（阶段 4）
- 性能/mmap（阶段 5）

</deferred>

---

*阶段：01-core-parsing*
*上下文收集：2026-04-28*