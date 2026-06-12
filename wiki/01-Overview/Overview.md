---
title: 项目介绍
section: overview
---

# 项目介绍

> [!NOTE] 项目定位
>
> **uasset_read** 是纯 Python 实现的虚幻引擎 `.uasset` 文件解析器，使 AI 代理和开发者无需启动 UE 编辑器即可读取蓝图、资产数据和图结构。专注于**未烘焙/编辑器保存**的资产。

## 基本信息

| 项目 | 详情 |
|------|------|
| 版本信息 | `0.4.5` · Python 3.10+（match/case、类型注解） · 运行时零依赖 |
| 构建系统 | Setuptools（src 布局） · 直接 `python run.py file.uasset` 调用 · PAK 可选依赖 |
| 支持资产 | 18+ 种类型：Blueprint、SkeletalMesh、Material、Texture2D、AnimSequence、Map 等 · 容器：文件系统 / PAK / IoStore |

## 核心能力

- **二进制解析**：完整 FArchive 序列化管线，字节序交换、mmap 大文件优化
- **蓝图提取**：变量、变换、组件、元数据、执行流、数据流
- **Kismet 反编译**：字节码 → AST → C++ 代码翻译，结构化控制流
- **对象链接器**：两阶段对象图重建，跨包引用解析
- **IR 中间表示**：统一数据结构层（PackageIR/ExportIR/GraphIR/NodeIR/PinIR），渲染器只接收 IR 不访问 ParseResult
- **渲染器系统**：JSON/Markdown 两个公开渲染器，通过 RENDERER_REGISTRY 分发
- **容器支持**：PAK（AES 解密、LZ4/Zstd 压缩）、IoStore 容器
- **Core API**：`parse_single`、`parse_batch`、`list_formats` 纯函数入口，无 argparse/sys.exit/print

## 架构演进

| 版本 | 架构 | 说明 |
|------|------|------|
| ≤ 0.3.8 | ParseResult → Exporter → Output | 导出器直接访问 ParseResult |
| 0.4.1 | ParseResult → IR Builder → PackageIR → Renderers → Output | IR 层引入，解析与输出解耦 |
| **0.4.5** | UE 保真度改进：统一状态模型（success\|partial\|failed）、UE 风格加载生命周期、类序列化策略表、SoftObjectPath 索引化解析、DependsMap FPackageIndex 语义、Payload 偏移默认策略对齐 | 当前版本 |

## 关键约束

> [!IMPORTANT] 重要限制
>
> - **仅支持未烘焙/编辑器保存的资产**：Cooked 资产图数据已剥离
> - **只读**：仅解析，不支持修改或写入
> - **零运行时依赖**：不向 dependencies 添加第三方包
> - **必须参考 UE 源码**：格式理解追溯 UE C++ 源码，禁止猜测
