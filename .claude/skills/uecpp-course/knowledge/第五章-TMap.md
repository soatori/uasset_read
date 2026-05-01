# 第五章：TMap

第五章覆盖 UE C++ 最常用的键值对容器——TMap 的完整使用，包括基本概念、创建填充、查询、移除、排序、运算符、内存管理、自定义键类型等所有操作。

---

## 模块索引

| 模块 | 文档 | 核心内容 |
|------|------|----------|
| 基本概念 | [ch5/overview.md](ch5/overview.md) | TMap 哈希表结构、TPair、TMultiMap、指针失效 |
| 创建与填充 | [ch5/creation.md](ch5/creation.md) | Add vs Emplace、Append、仅添加键、TMultiMap、Blueprint 暴露 |
| 迭代与日志 | [ch5/iteration.md](ch5/iteration.md) | for-range 循环、TPair 显式声明、CreateConstIterator、UE_LOG |
| 查询操作 | [ch5/query.md](ch5/query.md) | Num/Contains/operator[]/Find/FindOrAdd/FindRef/FindKey/GetKeys/GetValues |
| 移除与内存管理 | [ch5/removal-and-memory.md](ch5/removal-and-memory.md) | Remove/FindAndRemoveChecked/RemoveAndCopyValue、Empty/Reset/Reserve、Slack/Compact/Shrink |
| 排序与运算符 | [ch5/sorting-and-operators.md](ch5/sorting-and-operators.md) | KeySort/ValueSort、复制赋值、MoveTemp、UObject 指针语义 |
| 结构体作为 Key 与 KeyFuncs | [ch5/struct-as-key.md](ch5/struct-as-key.md) | operator==/GetTypeHash 重载、自定义 KeyFuncs 模板、FGuid/FCrc |
| 调试工具 | [ch5/utilities.md](ch5/utilities.md) | GetAllocatedSize/Dump/CountBytes、内存操作总结 |

---

> **配套代码**：[005_Map/MapActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/005_Map/MapActor.h) / [MapActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/005_Map/MapActor.cpp)
>
> 查询特定知识点时直接进入对应子页面，无需阅读整章。操作记录见 [log.md](log.md)。
