# 变更日志

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
