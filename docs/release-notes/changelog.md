# 变更日志

## [0.5.1.19] — 2026-06-28

自 v0.5.0 以来完成 18 个 issue 修复（#169 ~ #186）。

### 新增
- PackageFlags 完整定义：从 UE 源码 ObjectMacros.h 迁移 30 个 PKG_ 常量（Issue #179）
- PackageFlags 解码输出：JSON 和 Markdown 渲染器新增 `package_flags_decoded` 字段
- AssetRegistryData 解析：提取资产元数据标签（ObjectPath、ObjectClassName、Tags）（Issue #185）
- HexView 调试系统：结构化字节偏移追踪，支持所有读取方法（u8/u16/u32/i32/f32/f64/fstring 等）（Issue #182）
- BlueprintDescription 提取：从蓝图元数据中提取描述信息（Issue #169）
- ImplementedInterfaces 提取：接口列表暴露到输出（Issue #169）
- --full-parse CLI 标志：强制完整蓝图解析（跳过 export_count > 300 的轻量解析）
- 动画蓝图 AnimGraph 嵌套子图解析支持（Issue #178）
- GatherableTextData 本地化数据解析（Issue #184）
- UE4/UE5 版本枚举注释完善（Issue #181）
- UE5 条件字段解析完整性验证（Issue #180）
- UE5.7 SavedPackageHash 字段顺序验证（Issue #186）

### 修复
- BlueprintVariable.var_type 字段：从泛型属性中正确提取 pin_category 和 pin_subcategory（Issue #172）
- ReceiveBeginPlay 事件分类：K2Node_Event 标记 is_implemented=False，与 MCP 语义对齐（Issue #171）
- 非蓝图资产 JSON 输出：修复 exports 为空的问题（Issue #175）
- package_name 填充：修复 summary.package_name 为字符串 "None" 的问题（Issue #175）
- BoxSphereBounds 多格式支持：3f/3d/LWC/pre-LWC/compact 格式（Issue #175）
- FString UTF-16 解码：使用 utf-16-le 显式字节序，修复代理对解码错误（Issue #183）
- HexView 空字符串条目：修复 read_fstring 空字符串时的记录问题
- ImplementedInterfaces 解析为 opaque 空字段修复（Issue #173）
- BP_FirstPersonPlayerController 变量 Category 解析失败修复（Issue #170）

### 改进
- 继承事件与实现函数区分：解析器现在正确区分 K2Node_Event 和 K2Node_FunctionEntry
- IR 构建器：object_class 正确解析非蓝图 export
- 蓝图解析器与 MCP 数据对比差异分析（Issue #177）

## [0.5.0] — 2026-06-12

### 新增
- 解析器模块拆分：blueprint/cpp_gen/kismet/parsers/serializers 独立子包
- IR Builder 增强，更完整的中间表示构建

### 变更
- **输出格式精简**：仅保留 JSON/Markdown 两种输出格式，移除 Text/BlueprintText/BlueprintUE/CppSkeleton
- 移除 cpp_gen/cpp_skeleton C++ 代码生成能力
- 移除 formatters/ 模块，所有格式化通过渲染器系统完成

### 改进
- 大文件拆分为子模块，改善代码组织结构
- 文档清理：移除已废弃模块的引用
- 测试重组为 contracts/units/e2e 三层架构

### 修复
- Kismet fallback class detection 和 self-referencing parent_class
- Graph detection fallback 和 node class_name resolution
- blueprint_text 渲染改进
- SerializationControlExtensions 语义映射与结构化诊断
- partial/opaque 状态必须附带可追踪诊断原因

## [0.4.5] — 2026-06-20

### 修复
- PackageFileSummary UE 5.8 对齐：修复 LegacyGuid 缺失读取（UE5 < 1016 资产偏移错位根因）
- 修正 OwnerPersistentGuid 条件：FileVersionUE4 >= 519 && < 520
- 修正 ChunkIDs 读取：TArray\<int32\>（4 bytes/元素）替代误用的 16 bytes
- 两个偏移 bug 相互抵消的隐性问题修复

### 改进
- UE 5.8 ObjectVersion.h 版本常量对齐（18 项全部确认一致）
- UE 5.8 样本验收：Blueprint、StaticMesh、Material、SkeletalMesh、Animation、DataTable 全部通过
- StructProperty size mismatch 警告消除
- FString 损坏恢复、Texture2D 边界检查
- Transform struct_binary_decoded 支持 + Input Action 绑定收集
- BinaryOrNative handler None 返回修复 + UE5 旧格式 PropertyTag 支持
- SerializationControlExtensions 虚假未知位警告消除

### 文档
- 新增 ue5-evolution.md UE 5.8 对齐修复记录
- 补充 FPropertyTag 完整字段表 + UPROPERTY 说明符 + CDO 机制文档
- 补充 K2Node 语义参考 + 蓝图通信机制 + UE 模块映射文档

## [0.4.3] — 2026-06-05

### 新增
- IR → Renderer 架构
- 8 种输出格式（JSON, Text, Markdown, 等）
- Kismet 反编译器改进
- C++ 骨架生成质量增强

### 改进
- 直接脚本运行（无需 pip install）
- 12+ 资产类型支持

### 修复
- 签名解析器修复
- 测试可移植性改进

## [0.4.2] — 2026-05-20

### 新增
- function_graphs 字段从 result.graphs 填充
- IR 构建器 function_graphs 支持

## [0.4.1] — 2026-05-15

### 改进
- JSON 渲染器 function_graphs 改用 ir.function_graphs
