# 第六章：TSet

第六章覆盖 UE C++ 的基于哈希表的无序集合容器——TSet 的完整使用，包括基本概念、创建填充、迭代查询、移除、排序与运算符、Slack 管理、自定义键类型、内存调试等所有操作。与 TMap 的核心区别是 TSet 以**元素本身作为键**，不存在键值对分离。

---

## 模块索引

| 模块 | 文档 | 核心内容 |
|------|------|----------|
| 基本概念 | [ch6/overview.md](ch6/overview.md) | TSet 哈希表结构、element-as-key 范式、与 TMap 的对比 |
| 创建与填充 | [ch6/creation.md](ch6/creation.md) | Add vs Emplace、Append、初始化列表、Blueprint 暴露 |
| 迭代与查询 | [ch6/iteration-and-query.md](ch6/iteration-and-query.md) | for-range/CreateIterator/CreateConstIterator、Num/Contains/Find/FSetElementId/Array() |
| 移除、排序与 Slack | [ch6/removal-sort-operators.md](ch6/removal-sort-operators.md) | Remove/Reset/Empty/Reserve、Sort/StableSort、拷贝赋值、Compact/Shrink |
| KeyFuncs 与实用工具 | [ch6/defaultkeyfuncs-and-utilities.md](ch6/defaultkeyfuncs-and-utilities.md) | 结构体作为键、DefaultKeyFuncs 模板、GetAllocatedSize/Dump/CountBytes |

---

> **配套代码**：[SetActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.h) / [SetActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/006_Set/SetActor.cpp)
>
> 查询特定知识点时直接进入对应子页面，无需阅读整章。操作记录见 [log.md](log.md)。
