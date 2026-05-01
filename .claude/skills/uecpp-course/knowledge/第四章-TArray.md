# 第四章：TArray

第四章覆盖 UE C++ 最核心的容器——TArray 的完整使用，包括创建、添加、查询、排序、移除、内存管理等所有操作。配套代码工程为最新项目（有别于前三章的 001_XGSampleDemo）。

---

## 模块索引

| 模块 | 文档 | 核心内容 |
|------|------|----------|
| 创建与初始化 | [ch4/creation.md](ch4/creation.md) | TArray 声明、Init()、初始值设定项列表 |
| 添加元素 | [ch4/adding.md](ch4/adding.md) | Add vs Emplace、Append、Insert、AddUnique、AddDefaulted |
| 相等性判断 | [ch4/equality.md](ch4/equality.md) | 结构体 operator== 重载、跨类型 operator== |
| 迭代 | [ch4/iteration.md](ch4/iteration.md) | for-range 循环、索引循环、CreateConstIterator、安全移除 |
| 排序 | [ch4/sorting.md](ch4/sorting.md) | Sort/HeapSort/StableSort、结构体默认排序 |
| 二元谓词与 Lambda | [ch4/predicate.md](ch4/predicate.md) | 自定义排序、Lambda 表达式语法、值/引用捕获 |
| 查询与访问 | [ch4/querying.md](ch4/querying.md) | Num/SetNum/GetData/GetAllocatedSize/GetTypeSize |
| 索引 | [ch4/indexing.md](ch4/indexing.md) | [] 操作符、IsValidIndex、Last/Top |
| 查找函数 | [ch4/finding.md](ch4/finding.md) | Contains/Find/FindLast/INDEX_NONE |
| 高级查询 | [ch4/advanced-query.md](ch4/advanced-query.md) | IndexOfByKey/FindByKey/FindByPredicate/FilterByPredicate/IndexOfByPredicate |
| 移除操作 | [ch4/removing.md](ch4/removing.md) | Remove/RemoveSingle/RemoveAt/RemoveAll/RemoveAtSwap/RemoveSwap/RemoveAllSwap、Empty/Reset/Shrink |
| 运算符 | [ch4/operators.md](ch4/operators.md) | 拷贝/赋值、`+=`、MoveTemp、`==`/`!=`、Exchange |
| 堆操作 | [ch4/heap.md](ch4/heap.md) | Heapify/HeapPush/HeapPop/HeapRemoveTop/HeapTop |
| 内存管理 | [ch4/memory.md](ch4/memory.md) | Slack、扩容因子 16、Reserve、Empty vs Reset、Shrink |
| 原始内存 | [ch4/raw-memory.md](ch4/raw-memory.md) | GetData、AddUninitialized/InsertUninitialized、AddZeroed/SetNumZeroed、Swap/SwapMemory |

---

> **配套代码**：[004_Array/XGArrayActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.h) / [XGArrayActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/004_Array/XGArrayActor.cpp)
>
> 查询特定知识点时直接进入对应子页面，无需阅读整章。操作记录见 [log.md](log.md)。
