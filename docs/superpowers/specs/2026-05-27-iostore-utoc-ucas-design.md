# IoStore .utoc/.ucas 解析

## 背景

Phase 79 为 v14.0 CUE4Parse 核心对齐的一部分，实现 UE IoStore 格式的文件解析支持。

## 目标

1. FIoStoreTocResource 解析（Chunk ID 表、偏移量、压缩块信息）
2. .ucas 数据段提取
3. DefaultFileProvider 路径扫描
4. 解析 .utoc/.ucas 对，提取有效 Container 条目

## 架构

新建 `io_store/` 和 `file_provider/` 模块目录。IoStore 解析依赖 Phase 78 建立的 Provider 接口边界。

关键组件：
- `io_store/toc_parser.py` — FIoStoreTocResource 解析
- `io_store/ucas_reader.py` — .ucas 数据段读取
- `file_provider/default_provider.py` — DefaultFileProvider 路径扫描

## 验收标准

- 解析 .utoc/.ucas 对，提取有效 Container 条目
- 压缩块信息正确分派到 Zlib/LZ4/Zstd/Oodle
- Phase 78 Provider 接口已就绪后再执行
