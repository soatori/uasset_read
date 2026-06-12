# uasset_read 开发文档

> 虚幻引擎 `.uasset` 文件的 Python 解析器

## 快速导航

| 分类 | 页面 |
|------|------|
| **概览** | [[项目介绍\|Overview]] · [[快速开始\|Quick-Start]] · [[架构设计\|Architecture]] |
| **核心模块** | [[FArchive]] · [[解析管线\|Parse-Pipeline]] · [[包管理\|Package]] · [[常量与配置\|Constants]] · [[异常体系\|Exceptions]] |
| **数据处理** | [[序列化模块\|Serializers]] · [[属性解析器\|Parsers]] · [[数据模型\|Models]] · [[版本管理\|Versioning]] |
| **高级功能** | [[蓝图解析\|Blueprint]] · [[图分析\|Graph]] · [[Kismet 反编译\|Kismet]] · [[对象链接器\|Linker]] |
| **容器系统** | [[PAK 文件读取\|PAK]] · [[IoStore 容器\|IoStore]] · [[原始文件解析\|Raw-Files]] |
| **输出与渲染** | [[渲染器系统\|Renderers]] · [[IR 中间表示\|IR]] · [[CLI 接口\|CLI]] |
| **开发指南** | [[公共 API\|Public-API]] · [[测试指南\|Testing]] · [[开发规范\|Contributing]] · [[UE 源码对照\|UE-Reference]] |

## 项目信息

- **版本**: 0.4.5 (当前分支: develop)
- **Python**: 3.10+
- **测试**: 29 个测试（contracts/units/e2e 三层架构）
- **模块**: 153 个源文件，17 个子包
- **仓库**: [GitHub](https://github.com/soatori/uasset_read)

## v0.4.5 新特性

- **UE 风格加载生命周期**: `link() → preload(idx) × N → post_load()`
- **类序列化策略表**: 4 种策略（FULL_SERIALIZER / TAGGED_PROPERTIES_ONLY / OPAQUE_CLASS_PAYLOAD / SKIP_UNSUPPORTED）
- **统一状态模型**: `success | partial | failed` 三态
- **Payload 偏移策略**: 默认使用 `SerialOffset/SerialSize`（与 UE LinkerLoad.cpp:4793 对齐）
- **SoftObjectPath 索引化**: UE5.7+ 支持索引模式解析
