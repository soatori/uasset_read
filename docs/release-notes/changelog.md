# 变更日志

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

## [0.4.5] — 2026-06-09

### 新增
- UE 风格加载生命周期（`link() → preload(idx) × N → post_load()`）
- 类序列化策略表（`class_serialization_strategy.py`）
- SoftObjectPath 索引化解析（UE5.7+）
- DependsMap FPackageIndex 语义
- 统一状态模型（`success | partial | failed`）
- Payload 偏移策略默认使用 `SerialOffset/SerialSize`

### 改进
- 74 个新测试覆盖 UE 保真度改进
- Archive 生命周期管理重构
- StaticMesh 等类正确标记为 opaque

### 修复
- `parse_uasset_with_linker(preload_all=True)` 生命周期问题
- LinkerParseResult 缺少 status 属性
- Opaque 类状态同步到 export 对象

## [0.4.4] — 2026-06-07

### 新增
- 测试重组为 contracts/units/e2e 三层架构
- 源码大小预算检查和报告
- extras 模块用于可选高级功能
- FArchive 上下文管理器支持

### 改进
- 根 API 精简为稳定公共接口
- `_parse_package_core` 拆分为 7 个显式阶段
- export payload 策略层提取
- 统一状态模型实现
- `_post_process` 拆为显式 stage pipeline

### 修复
- Kismet 字节码 LWC 版本门控
- SoftObjectPath 三阶段版本门控
- UE5 路径 PreloadDependencies 版本门控
- 缓存清理机制（FunctionRefResolver + ClassHandlerRegistry）
- 文件处理类 `__del__` 安全网
- 路径遍历安全检查
- 批量处理路径分隔符清理

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
