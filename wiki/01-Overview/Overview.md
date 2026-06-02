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
| 版本信息 | `0.3.6-dev` · Python 3.10+（match/case、类型注解） · 运行时零依赖 |
| 构建系统 | Setuptools（src 布局） · `pip install -e ".[dev]"` · `pip install -e ".[pak]"` PAK 支持 |
| 支持资产 | 18+ 种类型：Blueprint、SkeletalMesh、Material、Texture2D、AnimSequence、Map 等 · 容器：文件系统 / PAK / IoStore |

## 核心能力

- **二进制解析**：完整 FArchive 序列化管线，字节序交换、mmap 大文件优化
- **蓝图提取**：变量、变换、组件、元数据、执行流、数据流
- **Kismet 反编译**：字节码 → AST → C++ 代码翻译，结构化控制流
- **对象链接器**：两阶段对象图重建，跨包引用解析
- **多格式输出**：JSON / Text / Markdown / Mermaid / UE 格式文本 / C++ 骨架
- **容器支持**：PAK（AES 解密、LZ4/Zstd 压缩）、IoStore 容器
- **N2C 中间格式**：标准化蓝图图结构，验证和双向转换

## 关键约束

> [!IMPORTANT] 重要限制
>
> - **仅支持未烘焙/编辑器保存的资产**：Cooked 资产图数据已剥离
> - **只读**：仅解析，不支持修改或写入
> - **零运行时依赖**：不向 dependencies 添加第三方包
> - **必须参考 UE 源码**：格式理解追溯 UE C++ 源码，禁止猜测
