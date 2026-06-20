# 变更日志

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
